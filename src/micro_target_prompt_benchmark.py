#!/usr/bin/env python3
"""Calibrate System One prompts against exact full-read teacher micro-target labels."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from relevance_prompt_benchmark import (
    PROMPTS as BASE_PROMPTS,
    evaluate_predictions,
    score_prompt,
)
from system_one_code_locator import Trace
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider


PROMPTS = {
    **BASE_PROMPTS,
    "direct_target_relevance": (
        "How directly relevant are the TARGET lines themselves to the user's "
        "goal? Use surrounding code only to understand the target. Give high "
        "probability only when TARGET itself implements, explains, constrains, "
        "or provides concrete evidence for the requested mechanism. Do not give "
        "credit merely because nearby code, shared symbols, the file theme, or "
        "an adjacent function is relevant."
    ),
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bucket(score):
    if score >= 0.70:
        return "high"
    if score >= 0.35:
        return "mid"
    return "low"


def evenly_take(items, count):
    if len(items) <= count:
        return list(items)
    if count <= 1:
        return [items[len(items) // 2]]
    positions = [
        round(i * (len(items) - 1) / (count - 1))
        for i in range(count)
    ]
    return [items[i] for i in positions]


def build_examples(reference, source_path, *, context_lines=24, per_bucket=10):
    if reference.get("kind") != "claude-full-read-micro-target-reference":
        raise ValueError(f"unexpected reference kind: {reference.get('kind')!r}")

    source = Path(source_path).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    if len(source) != int(reference["line_count"]):
        raise ValueError("source/reference line mismatch")

    rows = []
    for target in reference["targets"]:
        start = int(target["start_line"])
        end = int(target["end_line"])
        score = float(target["relevance"])
        before_start = max(1, start - int(context_lines))
        after_end = min(len(source), end + int(context_lines))
        rows.append({
            "id": target["id"],
            "start_line": start,
            "end_line": end,
            "reference_score": score,
            "teacher_role": target.get("role"),
            "teacher_reason": target.get("reason"),
            "bucket": bucket(score),
            "context_before": "\n".join(
                f"{i}: {source[i - 1]}"
                for i in range(before_start, start)
            ),
            "target": "\n".join(
                f"{i}: {source[i - 1]}"
                for i in range(start, end + 1)
            ),
            "context_after": "\n".join(
                f"{i}: {source[i - 1]}"
                for i in range(end + 1, after_end + 1)
            ),
        })

    selected = []
    for name in ("high", "mid", "low"):
        selected.extend(
            evenly_take(
                [item for item in rows if item["bucket"] == name],
                int(per_bucket),
            )
        )
    selected.sort(key=lambda item: item["start_line"])
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trace-file")
    parser.add_argument("--per-bucket", type=int, default=10)
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", "jev-latest"),
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv(
            "TYPESAFE_API_URL",
            "https://api.typesafe.ai/v1/systemone",
        ),
    )
    args = parser.parse_args(argv)

    key = os.getenv("TYPESAFE_API_KEY", "")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY is required")

    reference = load(args.reference)
    examples = build_examples(
        reference,
        args.source,
        per_bucket=args.per_bucket,
    )
    decider = ClosureChoiceRelevanceFrontierDecider(
        key,
        Trace(args.trace_file),
        args.endpoint,
        args.model,
    )

    result = {
        "schema_version": 1,
        "kind": "system-one-micro-target-prompt-calibration",
        "goal": args.goal,
        "file_path": args.file_path,
        "model": args.model,
        "teacher_kind": reference["kind"],
        "teacher_full_read": reference.get("full_read"),
        "examples": [
            {
                key: value
                for key, value in item.items()
                if key not in {
                    "context_before",
                    "target",
                    "context_after",
                }
            }
            for item in examples
        ],
        "prompts": {},
    }

    for name, prompt in PROMPTS.items():
        predictions, usage = score_prompt(
            decider,
            args.goal,
            args.file_path,
            examples,
            name,
            prompt,
        )
        result["prompts"][name] = {
            "prompt": prompt,
            "metrics": evaluate_predictions(examples, predictions),
            "predictions": predictions,
            "usage": usage,
        }

    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "geometry": {
            name: sum(1 for item in examples if item["bucket"] == name)
            for name in ("high", "mid", "low")
        },
        "prompts": {
            name: payload["metrics"]
            for name, payload in result["prompts"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
