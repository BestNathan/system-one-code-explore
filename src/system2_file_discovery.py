#!/usr/bin/env python3
"""System2 (Claude Code) file-discovery reference runner helpers."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from claude_reference_trace import parse_stream, strip_json_fence
from localization_result import claude_stage_cost


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def case_from_fixture(fixture, case_id):
    for case in fixture["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def build_prompt(case, model):
    return f"""User task (verbatim):
{case['goal']}

Perform an independent System2 repository investigation for FILE DISCOVERY only.

Your goal is to identify the repository files that materially matter to this task.

You MAY inspect source using Read, Glob, Grep, and read-only Bash commands.
Do not edit files. Do not use the network, git history, GitHub issues, or external context.

This is intentionally different from the System One arm:
- System One sees file metadata only.
- You are allowed to search and read source normally as a System2 coding agent.

Investigate enough to produce a precise relevant-file set.
Do not optimize for or guess any hidden expected file list.

Return ONLY valid JSON, no markdown fences:

{{
  "schema_version": 1,
  "kind": "system2-file-discovery",
  "task": {json.dumps(case['goal'])},
  "producer": {{
    "system": "claude_code",
    "model": {json.dumps(model)}
  }},
  "files": [
    {{
      "path": "repository-relative/path",
      "role": "primary|supporting|context",
      "reason": "why this file materially matters"
    }}
  ]
}}

Definitions:
- primary: directly implements the requested behavior.
- supporting: direct dependency/caller/state/test needed to understand it.
- context: useful wiring but not core implementation.

Requirements:
- Inspect a file before returning it.
- Prefer precision over keyword matches.
- Rank files from most to least relevant.
- Do not propose edits.
"""


def normalize_result(raw, subject_root, case, model, steps, terminal):
    root = Path(subject_root).resolve()
    files = []
    seen = set()
    for item in raw.get("files", []):
        path = str(item.get("path", "")).strip().replace("\\", "/")
        if not path or path in seen:
            continue
        full = (root / path).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            continue
        if not full.is_file():
            continue
        role = item.get("role", "context")
        if role not in {"primary", "supporting", "context"}:
            role = "context"
        seen.add(path)
        files.append({
            "path": path,
            "role": role,
            "reason": str(item.get("reason", "")),
        })

    primary = set(case["primary_files"])
    selected = {item["path"] for item in files}
    stage = claude_stage_cost(
        "file_discovery",
        terminal,
        len(steps),
    )
    counts = Counter(step["tool"] for step in steps)

    return {
        "schema_version": 1,
        "kind": "system2-file-discovery-result",
        "case_id": case["id"],
        "goal": case["goal"],
        "producer": {
            "system": "claude_code",
            "model": model,
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
        "tool_counts": dict(sorted(counts.items())),
        "duration_ms": terminal.get("duration_ms"),
        "duration_api_ms": terminal.get("duration_api_ms"),
        "turns": terminal.get("num_turns"),
        "usage": terminal.get("usage"),
        "model_usage": terminal.get("modelUsage"),
        "provider_cost_usd": stage.get("provider_cost_usd"),
    }


def cmd_prompt(args):
    fixture = load(args.cases)
    case = case_from_fixture(fixture, args.case_id)
    Path(args.output).write_text(
        build_prompt(case, args.model),
        encoding="utf-8",
    )


def cmd_parse(args):
    fixture = load(args.cases)
    case = case_from_fixture(fixture, args.case_id)
    steps, terminal, final_text = parse_stream(
        args.raw_jsonl,
        Path(args.subject_root).resolve(),
    )
    raw = json.loads(strip_json_fence(final_text))
    result = normalize_result(
        raw,
        args.subject_root,
        case,
        args.model,
        steps,
        terminal,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--cases", required=True)
    prompt.add_argument("--case-id", required=True)
    prompt.add_argument("--model", required=True)
    prompt.add_argument("--output", required=True)
    prompt.set_defaults(func=cmd_prompt)

    parse = sub.add_parser("parse")
    parse.add_argument("--cases", required=True)
    parse.add_argument("--case-id", required=True)
    parse.add_argument("--model", required=True)
    parse.add_argument("--raw-jsonl", required=True)
    parse.add_argument("--subject-root", required=True)
    parse.add_argument("--output", required=True)
    parse.set_defaults(func=cmd_parse)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
