#!/usr/bin/env python3
"""Compare File Discovery V1 with an independent System2 repository search."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def case_from_fixture(fixture, case_id):
    for case in fixture["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def compare(system_one, system_two, case):
    primary = set(case["primary_files"])
    one_files = {
        item["path"] for item in system_one.get("relevant_files", [])
    }
    two_files = {
        item["path"] for item in system_two.get("files", [])
    }

    one_cost = (
        system_one.get("usage", {})
        .get("pricing", {})
        .get("estimated_cost_usd")
    )
    two_cost = system_two.get("provider_cost_usd")
    one_wall = system_one.get("usage", {}).get(
        "model_wall_time_ms"
    )
    two_wall = system_two.get("duration_ms")

    return {
        "schema_version": 1,
        "kind": "file-discovery-system1-vs-system2-comparison",
        "case_id": case["id"],
        "domain": case["domain"],
        "language": case["language"],
        "goal": case["goal"],
        "primary_files": sorted(primary),
        "system_one": {
            "primary_recall": (
                len(primary & one_files) / len(primary)
                if primary else 1.0
            ),
            "primary_recovered": sorted(primary & one_files),
            "selected_file_count": len(one_files),
            "model_calls": system_one.get("usage", {}).get(
                "model_calls"
            ),
            "input_tokens": system_one.get("usage", {}).get(
                "input_tokens"
            ),
            "output_tokens": system_one.get("usage", {}).get(
                "output_tokens"
            ),
            "model_wall_time_ms": one_wall,
            "estimated_cost_usd": one_cost,
        },
        "system_two": {
            "primary_recall": system_two.get("primary_recall"),
            "primary_recovered": system_two.get(
                "primary_recovered", []
            ),
            "selected_file_count": len(two_files),
            "tool_calls": system_two.get("tool_calls"),
            "turns": system_two.get("turns"),
            "duration_ms": two_wall,
            "usage": system_two.get("usage"),
            "provider_cost_usd": two_cost,
            "model": system_two.get("producer", {}).get("model"),
        },
        "descriptive_overlap": {
            "intersection": sorted(one_files & two_files),
            "intersection_count": len(one_files & two_files),
            "union_count": len(one_files | two_files),
            "jaccard": (
                len(one_files & two_files) / len(one_files | two_files)
                if one_files | two_files else 1.0
            ),
            "system_one_only": sorted(one_files - two_files),
            "system_two_only": sorted(two_files - one_files),
        },
        "ratios_when_available": {
            "system2_to_system1_cost": (
                float(two_cost) / float(one_cost)
                if one_cost not in (None, 0)
                and two_cost is not None else None
            ),
            "system2_to_system1_wall_time": (
                float(two_wall) / float(one_wall)
                if one_wall not in (None, 0)
                and two_wall is not None else None
            ),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--system-one", required=True)
    parser.add_argument("--system-two", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    fixture = load(args.cases)
    case = case_from_fixture(fixture, args.case_id)
    result = compare(
        load(args.system_one),
        load(args.system_two),
        case,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
