#!/usr/bin/env python3
"""Full-read System 2 teacher labels for exact micro-target code blocks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from full_read_relevance_baseline import extract_json, numbered_source, ROLES


def micro_targets(line_count, target_lines=8, stride_lines=8):
    out = []
    start = 1
    index = 1
    while start <= line_count:
        end = min(line_count, start + int(target_lines) - 1)
        out.append({
            "id": f"t{index:04d}",
            "start_line": start,
            "end_line": end,
        })
        if end == line_count:
            break
        start += max(1, int(stride_lines))
        index += 1
    return out


def build_prompt(path, query, source, line_count, targets, target_lines, stride_lines):
    return f"""You are the full-read teacher for a code relevance calibration benchmark.

TASK:
{query}

You have the COMPLETE target file below. Read and reason about the whole file
before scoring.

For every listed TARGET range, score ONLY the exact target lines from 0 to 1
for how directly and materially those lines themselves contribute evidence
needed for the task.

The full file gives you context to understand symbols, callers, state, and
control flow, but relevance must NOT smear from nearby code into the target.
If a neighboring function is highly relevant while the exact target is only
setup, unrelated validation, logging, boilerplate, or another mechanism, score
the exact target low.

Use role: core, supporting, context, incidental, or irrelevant.

Return ONLY JSON. Preserve every target id and geometry exactly.

Shape:
{{
  "schema_version": 1,
  "kind": "claude-full-read-micro-target-reference",
  "task": {json.dumps(query)},
  "path": {json.dumps(path)},
  "line_count": {line_count},
  "target_lines": {int(target_lines)},
  "stride_lines": {int(stride_lines)},
  "full_read": true,
  "targets": [
    {{
      "id": "t0001",
      "start_line": 1,
      "end_line": 8,
      "relevance": 0.0,
      "role": "core",
      "reason": "brief rationale about these exact target lines"
    }}
  ]
}}

TARGETS:
{json.dumps(targets, indent=2, ensure_ascii=False)}

FULL SOURCE:
--- BEGIN ---
{source}
--- END ---
"""


def normalize(raw_text, expected, path, query, line_count, target_lines, stride_lines):
    value = extract_json(raw_text)
    if value.get("kind") != "claude-full-read-micro-target-reference":
        raise ValueError(f"unexpected kind: {value.get('kind')!r}")
    if value.get("full_read") is not True:
        raise ValueError("teacher must declare full_read=true")
    actual = value.get("targets")
    if not isinstance(actual, list):
        raise ValueError("targets must be a list")

    by_id = {}
    for item in actual:
        if not isinstance(item, dict):
            raise ValueError("target must be an object")
        target_id = item.get("id")
        if target_id in by_id:
            raise ValueError(f"duplicate target id: {target_id}")
        by_id[target_id] = item

    expected_ids = {item["id"] for item in expected}
    if set(by_id) != expected_ids:
        raise ValueError(
            "target id mismatch: "
            f"missing={sorted(expected_ids - set(by_id))} "
            f"extra={sorted(set(by_id) - expected_ids)}"
        )

    normalized = []
    for expected_item in expected:
        item = by_id[expected_item["id"]]
        for key in ("start_line", "end_line"):
            if int(item.get(key, -1)) != expected_item[key]:
                raise ValueError(
                    f"{expected_item['id']} changed {key}: {item.get(key)!r}"
                )
        score = float(item.get("relevance"))
        if not 0.0 <= score <= 1.0:
            raise ValueError(
                f"{expected_item['id']} relevance outside [0,1]: {score}"
            )
        role = item.get("role")
        if role not in ROLES:
            raise ValueError(
                f"{expected_item['id']} invalid role: {role!r}"
            )
        reason = str(item.get("reason", "")).strip()
        if not reason:
            raise ValueError(f"{expected_item['id']} reason is required")
        normalized.append({
            **expected_item,
            "relevance": round(score, 6),
            "role": role,
            "reason": reason,
        })

    return {
        "schema_version": 1,
        "kind": "claude-full-read-micro-target-reference",
        "task": query,
        "path": path,
        "line_count": int(line_count),
        "target_lines": int(target_lines),
        "stride_lines": int(stride_lines),
        "full_read": True,
        "targets": normalized,
    }


def prepare(args):
    source_path = Path(args.source)
    source, line_count = numbered_source(source_path)
    targets = micro_targets(
        line_count,
        args.target_lines,
        args.stride_lines,
    )
    prompt = build_prompt(
        str(source_path),
        args.query,
        source,
        line_count,
        targets,
        args.target_lines,
        args.stride_lines,
    )
    Path(args.output_prompt).write_text(prompt, encoding="utf-8")
    if args.output_manifest:
        Path(args.output_manifest).write_text(
            json.dumps({
                "schema_version": 1,
                "kind": "claude-full-read-micro-target-prompt",
                "task": args.query,
                "path": str(source_path),
                "line_count": line_count,
                "target_lines": args.target_lines,
                "stride_lines": args.stride_lines,
                "targets": targets,
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "line_count": line_count,
        "targets": len(targets),
    }))


def normalize_command(args):
    source_path = Path(args.source)
    _, line_count = numbered_source(source_path)
    targets = micro_targets(
        line_count,
        args.target_lines,
        args.stride_lines,
    )
    result = normalize(
        Path(args.raw_output).read_text(encoding="utf-8"),
        targets,
        str(source_path),
        args.query,
        line_count,
        args.target_lines,
        args.stride_lines,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    counts = {"high": 0, "mid": 0, "low": 0}
    for item in result["targets"]:
        score = item["relevance"]
        counts["high" if score >= 0.70 else "mid" if score >= 0.35 else "low"] += 1
    print(json.dumps({
        "targets": len(result["targets"]),
        "buckets": counts,
        "full_read": True,
    }, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--source", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--target-lines", type=int, default=8)
    p.add_argument("--stride-lines", type=int, default=8)
    p.add_argument("--output-prompt", required=True)
    p.add_argument("--output-manifest")
    p.set_defaults(func=prepare)

    p = sub.add_parser("normalize")
    p.add_argument("--source", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--target-lines", type=int, default=8)
    p.add_argument("--stride-lines", type=int, default=16)
    p.add_argument("--raw-output", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=normalize_command)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
