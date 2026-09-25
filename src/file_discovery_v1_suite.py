#!/usr/bin/env python3
"""Run the frozen File Discovery V1 primary-target suite."""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from file_discovery_v1 import run
from file_discovery_v1_benchmark import evaluate
from system_one_code_locator import API_URL, MODEL, SystemOneDecider, Trace


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--file-threshold", type=float, default=0.65)
    parser.add_argument("--transport-batch-size", type=int, default=64)
    parser.add_argument(
        "--endpoint",
        default=os.getenv("TYPESAFE_API_URL", API_URL),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", MODEL),
    )
    args = parser.parse_args(argv)

    key = os.getenv("TYPESAFE_API_KEY", "")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY is required")

    fixture = load(args.cases)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in fixture["cases"]:
        case_dir = output_dir / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        trace = Trace(case_dir / "trace.jsonl")
        decider = SystemOneDecider(
            key,
            trace,
            args.endpoint,
            args.model,
        )
        result = run(
            args.root,
            case["goal"],
            decider,
            file_threshold=args.file_threshold,
            transport_batch_size=args.transport_batch_size,
        )
        benchmark = evaluate(result, case)
        (case_dir / "run.json").write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "benchmark.json").write_text(
            json.dumps(benchmark, indent=2) + "\n",
            encoding="utf-8",
        )
        rows.append(benchmark)

    failures = Counter(
        row["failure"]["kind"]
        for row in rows
        if row["failure"] is not None
    )
    suite = {
        "schema_version": 1,
        "kind": "file-discovery-v1-primary-target-suite",
        "repository": fixture["repository"],
        "revision": fixture["revision"],
        "policy": {
            "file_threshold": args.file_threshold,
            "transport_batch_size": args.transport_batch_size,
        },
        "cases": len(rows),
        "primary_recovered": sum(
            row["primary_recovered"] for row in rows
        ),
        "primary_recall": (
            sum(row["primary_recovered"] for row in rows) / len(rows)
            if rows else 0.0
        ),
        "all_primary_recovered": all(
            row["primary_recovered"] for row in rows
        ),
        "mean_selected_files": (
            sum(row["selected_file_count"] for row in rows) / len(rows)
            if rows else 0.0
        ),
        "max_selected_files": max(
            (row["selected_file_count"] for row in rows),
            default=0,
        ),
        "total_model_calls": sum(
            row["usage"].get("model_calls", 0) for row in rows
        ),
        "total_input_tokens": sum(
            row["usage"].get("input_tokens", 0) for row in rows
        ),
        "total_output_tokens": sum(
            row["usage"].get("output_tokens", 0) for row in rows
        ),
        "total_model_wall_time_ms": sum(
            row["usage"].get("model_wall_time_ms", 0) for row in rows
        ),
        "total_metadata_items_seen": sum(
            row["usage"].get("metadata_items_seen", 0) for row in rows
        ),
        "failure_kinds": dict(failures),
        "results": rows,
    }
    (output_dir / "suite.json").write_text(
        json.dumps(suite, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(suite, indent=2))


if __name__ == "__main__":
    main()
