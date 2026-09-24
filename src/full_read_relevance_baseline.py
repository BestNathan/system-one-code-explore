#!/usr/bin/env python3
"""Full-read Claude relevance-field baseline utilities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_WINDOW_LINES = 64
DEFAULT_STRIDE_LINES = 32
ROLES = {"core", "supporting", "context", "incidental", "irrelevant"}
CONTINUITY = {"self_contained", "requires_left", "requires_right", "requires_both"}


def numbered_source(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    source = "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1))
    return source, len(lines)


def canonical_ranges(line_count, window_lines=64, stride_lines=32):
    if line_count <= 0:
        return []
    ranges = []
    start = 1
    index = 0
    while start <= line_count:
        end = min(line_count, start + window_lines - 1)
        ranges.append({
            "id": f"r{index + 1:04d}",
            "start_line": start,
            "end_line": end,
        })
        index += 1
        if end == line_count:
            break
        start += max(1, stride_lines)
    return ranges


def build_prompt(path, query, source, line_count, ranges):
    range_json = json.dumps(ranges, indent=2, ensure_ascii=False)
    return f"""You are building a reference relevance field for code localization.

Task:
{query}

The COMPLETE target file is supplied below. Treat every line as already read.
Do not explore only individual ranges. Use the full file context before scoring.

Score every canonical range from 0 to 1 for how materially it contributes to
the task. A range may be highly relevant even if it is only a fragment of a
larger function; use continuity to record that fact.

Role: one of core, supporting, context, incidental, irrelevant.
Continuity: one of self_contained, requires_left, requires_right, requires_both.

Return ONLY JSON. Return every range exactly once and preserve its geometry.

Shape:
{{
  "schema_version": 1,
  "kind": "claude-full-read-relevance-field",
  "task": {json.dumps(query)},
  "path": {json.dumps(path)},
  "line_count": {line_count},
  "window_lines": 64,
  "stride_lines": 32,
  "full_read": true,
  "ranges": [
    {{
      "id": "r0001",
      "start_line": 1,
      "end_line": 64,
      "relevance": 0.0,
      "role": "core",
      "continuity": "self_contained",
      "reason": "brief evidence-based rationale"
    }}
  ]
}}

Canonical ranges:
{range_json}

FULL SOURCE:
--- BEGIN ---
{source}
--- END ---
"""


def extract_json(text):
    text = text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Claude output did not contain a JSON object")


def normalize(raw_text, expected, path, query, line_count,
              window_lines=64, stride_lines=32):
    value = extract_json(raw_text)
    if value.get("kind") != "claude-full-read-relevance-field":
        raise ValueError(f"unexpected kind: {value.get('kind')!r}")
    if value.get("full_read") is not True:
        raise ValueError("baseline must declare full_read=true")
    actual = value.get("ranges")
    if not isinstance(actual, list):
        raise ValueError("ranges must be a list")

    by_id = {}
    for item in actual:
        if not isinstance(item, dict):
            raise ValueError("range item must be an object")
        rid = item.get("id")
        if rid in by_id:
            raise ValueError(f"duplicate range id: {rid}")
        by_id[rid] = item

    expected_ids = {item["id"] for item in expected}
    if set(by_id) != expected_ids:
        raise ValueError(
            "range id mismatch: "
            f"missing={sorted(expected_ids - set(by_id))} "
            f"extra={sorted(set(by_id) - expected_ids)}"
        )

    normalized = []
    for expected_item in expected:
        item = by_id[expected_item["id"]]
        for key in ("start_line", "end_line"):
            if int(item.get(key, -1)) != expected_item[key]:
                raise ValueError(
                    f"{expected_item['id']} changed {key}: "
                    f"{item.get(key)!r}"
                )
        relevance = float(item.get("relevance"))
        if not 0.0 <= relevance <= 1.0:
            raise ValueError(
                f"{expected_item['id']} relevance outside [0,1]: {relevance}"
            )
        role = item.get("role")
        continuity = item.get("continuity")
        if role not in ROLES:
            raise ValueError(f"{expected_item['id']} invalid role: {role!r}")
        if continuity not in CONTINUITY:
            raise ValueError(
                f"{expected_item['id']} invalid continuity: {continuity!r}"
            )
        reason = str(item.get("reason", "")).strip()
        if not reason:
            raise ValueError(f"{expected_item['id']} reason is required")
        normalized.append({
            **expected_item,
            "relevance": round(relevance, 6),
            "role": role,
            "continuity": continuity,
            "reason": reason,
        })

    return {
        "schema_version": 1,
        "kind": "claude-full-read-relevance-field",
        "task": query,
        "path": path,
        "line_count": int(line_count),
        "window_lines": int(window_lines),
        "stride_lines": int(stride_lines),
        "full_read": True,
        "ranges": normalized,
    }


def prepare(args):
    path = Path(args.source)
    source, line_count = numbered_source(path)
    ranges = canonical_ranges(
        line_count,
        args.window_lines,
        args.stride_lines,
    )
    prompt = build_prompt(
        str(path),
        args.query,
        source,
        line_count,
        ranges,
    )
    Path(args.output_prompt).write_text(prompt, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "kind": "claude-full-read-relevance-field-prompt",
        "task": args.query,
        "path": str(path),
        "line_count": line_count,
        "window_lines": args.window_lines,
        "stride_lines": args.stride_lines,
        "ranges": ranges,
    }
    if args.output_manifest:
        Path(args.output_manifest).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def normalize_command(args):
    source_path = Path(args.source)
    _, line_count = numbered_source(source_path)
    ranges = canonical_ranges(
        line_count,
        args.window_lines,
        args.stride_lines,
    )
    raw = Path(args.raw_output).read_text(encoding="utf-8")
    result = normalize(
        raw,
        ranges,
        str(source_path),
        args.query,
        line_count,
        args.window_lines,
        args.stride_lines,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ranges": len(result["ranges"]),
        "full_read": result["full_read"],
        "path": result["path"],
        "line_count": result["line_count"],
    }, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--source", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--window-lines", type=int, default=DEFAULT_WINDOW_LINES)
    p.add_argument("--stride-lines", type=int, default=DEFAULT_STRIDE_LINES)
    p.add_argument("--output-prompt", required=True)
    p.add_argument("--output-manifest")
    p.set_defaults(func=prepare)

    p = sub.add_parser("normalize")
    p.add_argument("--source", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--window-lines", type=int, default=DEFAULT_WINDOW_LINES)
    p.add_argument("--stride-lines", type=int, default=DEFAULT_STRIDE_LINES)
    p.add_argument("--raw-output", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=normalize_command)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
