#!/usr/bin/env python3
"""Recover a System2 file-discovery result from malformed final JSON.

This is intentionally a serialization-recovery layer only. It does not search
the repository or infer extra files. It extracts file paths/roles explicitly
present in the model's final text preserved in the raw Claude Code stream.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from claude_reference_trace import parse_stream
from localization_result import claude_stage_cost
from system2_file_discovery import case_from_fixture, load


PATH_RE = re.compile(r'"path"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
ROLE_RE = re.compile(r'"role"\s*:\s*"(primary|supporting|context)"')


def unescape_json_string(value):
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return value.replace("\\/", "/").replace("\\\\", "\\")


def recover_files(final_text, subject_root):
    root = Path(subject_root).resolve()
    matches = list(PATH_RE.finditer(final_text))
    out = []
    seen = set()

    for index, match in enumerate(matches):
        raw_path = unescape_json_string(match.group(1))
        path = raw_path.strip().replace("\\", "/")
        if not path or path in seen:
            continue

        full = (root / path).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            continue
        if not full.is_file():
            continue

        end = matches[index + 1].start() if index + 1 < len(matches) else len(final_text)
        local = final_text[match.end():end]
        role_match = ROLE_RE.search(local)
        role = role_match.group(1) if role_match else "context"

        seen.add(path)
        out.append({
            "path": path,
            "role": role,
            "reason": "Recovered from malformed System2 final JSON; path and role were explicitly emitted by the model.",
        })
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--raw-jsonl", required=True)
    parser.add_argument("--subject-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    fixture = load(args.cases)
    case = case_from_fixture(fixture, args.case_id)
    steps, terminal, final_text = parse_stream(
        args.raw_jsonl,
        Path(args.subject_root).resolve(),
    )
    files = recover_files(final_text, args.subject_root)
    if not files:
        raise RuntimeError(
            "System2 serialization recovery found no explicit repository file paths"
        )

    primary = set(case["primary_files"])
    selected = {item["path"] for item in files}
    stage = claude_stage_cost("file_discovery", terminal, len(steps))

    result = {
        "schema_version": 1,
        "kind": "system2-file-discovery-result",
        "case_id": case["id"],
        "goal": case["goal"],
        "producer": {
            "system": "claude_code",
            "model": args.model,
        },
        "files": files,
        "primary_files": sorted(primary),
        "primary_recovered": sorted(primary & selected),
        "primary_recall": (
            len(primary & selected) / len(primary)
            if primary else 1.0
        ),
        "selected_file_count": len(files),
        "tool_calls": len(steps),
        "duration_ms": terminal.get("duration_ms"),
        "duration_api_ms": terminal.get("duration_api_ms"),
        "turns": terminal.get("num_turns"),
        "usage": terminal.get("usage"),
        "model_usage": terminal.get("modelUsage"),
        "provider_cost_usd": stage.get("provider_cost_usd"),
        "serialization_recovered": True,
        "serialization_recovery": {
            "method": "explicit_path_role_extraction_from_final_text",
            "final_text_chars": len(final_text),
        },
    }
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
