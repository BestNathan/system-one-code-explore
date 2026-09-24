#!/usr/bin/env python3
"""Project System One evidence onto a Claude full-read relevance field."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def merge_ranges(ranges):
    out = []
    for start, end in sorted(ranges):
        if not out or start > out[-1][1] + 1:
            out.append([start, end])
        else:
            out[-1][1] = max(out[-1][1], end)
    return out


def overlap_fraction(target, coverage):
    start, end = target
    length = end - start + 1
    if length <= 0:
        return 0.0
    hit = 0
    for left, right in coverage:
        hit += max(0, min(end, right) - max(start, left) + 1)
    return min(1.0, hit / length)


def line_field(reference):
    field = [0.0] * (int(reference["line_count"]) + 1)
    core = [False] * len(field)
    for item in reference["ranges"]:
        score = float(item["relevance"])
        role_core = item["role"] == "core"
        for line in range(
            int(item["start_line"]),
            int(item["end_line"]) + 1,
        ):
            field[line] = max(field[line], score)
            core[line] = core[line] or role_core
    return field, core


def evaluate(reference, candidate, high_threshold=0.70):
    coverage = merge_ranges([
        (int(e["start_line"]), int(e["end_line"]))
        for item in candidate.get("files", [])
        for e in item.get("evidence", [])
    ])
    field, core = line_field(reference)
    line_count = int(reference["line_count"])

    total_mass = sum(field[1:])
    covered_mass = sum(
        field[line]
        for left, right in coverage
        for line in range(left, min(right, line_count) + 1)
    )
    covered_lines = sum(right - left + 1 for left, right in coverage)
    weighted_recall = covered_mass / total_mass if total_mass else 0.0

    high_windows = [
        item for item in reference["ranges"]
        if float(item["relevance"]) >= high_threshold
    ]
    high_hits = sum(
        overlap_fraction(
            (int(item["start_line"]), int(item["end_line"])),
            coverage,
        ) >= 0.5
        for item in high_windows
    )
    core_windows = [
        item for item in reference["ranges"]
        if item["role"] == "core"
    ]
    core_hits = sum(
        overlap_fraction(
            (int(item["start_line"]), int(item["end_line"])),
            coverage,
        ) >= 0.5
        for item in core_windows
    )

    candidate_mass = covered_mass
    precision = candidate_mass / covered_lines if covered_lines else 0.0
    normalized_precision = precision / max(1e-9, max(field[1:] or [1.0]))

    return {
        "reference": {
            "path": reference["path"],
            "line_count": line_count,
            "ranges": len(reference["ranges"]),
            "high_relevance_threshold": high_threshold,
            "high_relevance_ranges": len(high_windows),
            "core_ranges": len(core_windows),
            "relevance_mass": round(total_mass, 6),
        },
        "candidate": {
            "source_coverage": round(covered_lines / max(1, line_count), 6),
            "evidence_ranges": sum(
                len(item.get("evidence", []))
                for item in candidate.get("files", [])
            ),
        },
        "metrics": {
            "weighted_relevance_recall": round(weighted_recall, 6),
            "high_relevance_window_recall": round(
                high_hits / len(high_windows) if high_windows else 0.0,
                6,
            ),
            "core_window_recall": round(
                core_hits / len(core_windows) if core_windows else 0.0,
                6,
            ),
            "relevance_weighted_precision": round(precision, 6),
            "normalized_relevance_precision": round(
                normalized_precision,
                6,
            ),
        },
        "coverage": coverage,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--high-threshold", type=float, default=0.70)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    result = evaluate(
        load(args.reference),
        load(args.candidate),
        args.high_threshold,
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
