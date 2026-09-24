#!/usr/bin/env python3
"""Benchmark R14 anchor-centered semantic closure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reference_field(reference):
    n = int(reference["line_count"])
    field = [0.0] * n
    for item in reference["ranges"]:
        score = float(item["relevance"])
        left = max(1, int(item["start_line"]))
        right = min(n, int(item["end_line"]))
        for line in range(left, right + 1):
            field[line - 1] = max(
                field[line - 1],
                score,
            )
    return field


def selected_lines(run):
    lines = set()
    for item in run.get("materialized_evidence", []):
        lines.update(
            range(
                int(item["start_line"]),
                int(item["end_line"]) + 1,
            )
        )
    return lines


def evaluate(reference, phase0_run, run):
    truth = reference_field(reference)
    frontier = phase0_run["frontier"]
    chosen = selected_lines(run)
    n = len(truth)

    high = {
        i + 1
        for i, value in enumerate(truth)
        if value >= 0.70
    }
    frontier_high = {
        i + 1
        for i, value in enumerate(frontier["relevance"])
        if float(value) >= 0.65
    }
    total_mass = sum(truth)
    selected_mass = sum(
        truth[line - 1]
        for line in chosen
    )
    selected_high = len(chosen & high)

    anchors = run.get("anchors", [])
    complete = [
        anchor
        for anchor in anchors
        if anchor.get("status") == "complete"
    ]
    unresolved = [
        anchor
        for anchor in anchors
        if anchor.get("status") == "unresolved_incomplete"
    ]
    low_utility = [
        anchor
        for anchor in anchors
        if anchor.get("status") == "low_utility"
    ]
    capped = [
        anchor
        for anchor in anchors
        if anchor.get("status") == "closure_safety_cap"
    ]

    final_completeness = [
        float(anchor["final_completeness_probability"])
        for anchor in anchors
        if anchor.get("final_completeness_probability") is not None
    ]
    final_utility = [
        float(anchor["final_utility_probability"])
        for anchor in anchors
        if anchor.get("final_utility_probability") is not None
    ]

    closure_tiles = [
        item
        for item in run.get("materialized_evidence", [])
        if str(item.get("reason", "")).startswith("anchor_closure_")
    ]

    anchor_spans = []
    growth = []
    for anchor in anchors:
        seed_left, seed_right = anchor["seed_range"]
        seed_span = seed_right - seed_left + 1
        tile_ids = anchor.get("tile_ids", [])
        if not tile_ids:
            continue
        # All tiles are equal width except possibly the last one.
        span = len(tile_ids) * int(
            run.get("policy", {}).get("tile_lines", 32)
        )
        anchor_spans.append(span)
        growth.append(span / seed_span)

    remaining_truth = []
    for item in run.get("remaining_actions", []):
        left = int(item["start_line"])
        right = int(item["end_line"])
        values = truth[left - 1:right]
        remaining_truth.append({
            "id": item["id"],
            "start_line": left,
            "end_line": right,
            "mean_reference_relevance": (
                sum(values) / len(values)
                if values else 0.0
            ),
            "max_reference_relevance": (
                max(values)
                if values else 0.0
            ),
        })
    best_remaining = (
        max(
            remaining_truth,
            key=lambda x: (
                x["mean_reference_relevance"],
                x["max_reference_relevance"],
            ),
        )
        if remaining_truth else None
    )

    return {
        "schema_version": 1,
        "kind": "r14-anchor-semantic-closure-benchmark",
        "metrics": {
            "materialized_tiles": run.get(
                "materialized_count",
                0,
            ),
            "materialized_lines": len(chosen),
            "source_fraction": (
                len(chosen) / n if n else 0.0
            ),
            "mean_reference_relevance": (
                selected_mass / len(chosen)
                if chosen else 0.0
            ),
            "high_line_precision": (
                selected_high / len(chosen)
                if chosen else 0.0
            ),
            "high_line_recall": (
                selected_high / len(high)
                if high else 0.0
            ),
            "weighted_relevance_recall": (
                selected_mass / total_mass
                if total_mass else 0.0
            ),
            "phase0_high_frontier_coverage": (
                len(chosen & frontier_high)
                / len(frontier_high)
                if frontier_high else 0.0
            ),
            "anchor_count": len(anchors),
            "complete_anchor_count": len(complete),
            "unresolved_incomplete_count": len(unresolved),
            "low_utility_anchor_count": len(low_utility),
            "closure_safety_cap_count": len(capped),
            "closure_expansion_tiles": len(closure_tiles),
            "mean_anchor_span_lines": (
                sum(anchor_spans) / len(anchor_spans)
                if anchor_spans else 0.0
            ),
            "max_anchor_span_lines": (
                max(anchor_spans)
                if anchor_spans else 0.0
            ),
            "mean_anchor_growth_ratio": (
                sum(growth) / len(growth)
                if growth else 0.0
            ),
            "mean_final_completeness": (
                sum(final_completeness)
                / len(final_completeness)
                if final_completeness else None
            ),
            "min_final_completeness": (
                min(final_completeness)
                if final_completeness else None
            ),
            "mean_final_utility": (
                sum(final_utility) / len(final_utility)
                if final_utility else None
            ),
        },
        "stop": {
            "termination": run.get("termination"),
            "best_remaining": best_remaining,
            "premature_by_hidden_cc": bool(
                best_remaining is not None
                and best_remaining[
                    "mean_reference_relevance"
                ] >= 0.70
            ),
        },
        "anchors": [
            {
                "id": anchor["id"],
                "seed_range": anchor["seed_range"],
                "tile_ids": anchor["tile_ids"],
                "status": anchor["status"],
                "final_utility_probability": anchor.get(
                    "final_utility_probability"
                ),
                "final_completeness_probability": anchor.get(
                    "final_completeness_probability"
                ),
            }
            for anchor in anchors
        ],
        "final_regions": run.get("final_regions", []),
    }


def markdown(result):
    m = result["metrics"]
    lines = [
        "# R14 anchor semantic closure benchmark",
        "",
        f"- termination: {result['stop']['termination']}",
        f"- materialized tiles: {m['materialized_tiles']}",
        f"- materialized lines: {m['materialized_lines']}",
        f"- anchors: {m['anchor_count']}",
        f"- complete anchors: {m['complete_anchor_count']}",
        f"- unresolved incomplete: {m['unresolved_incomplete_count']}",
        f"- closure expansions: {m['closure_expansion_tiles']}",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| mean CC relevance | {m['mean_reference_relevance']:.4f} |",
        f"| high precision | {m['high_line_precision']:.4f} |",
        f"| high recall | {m['high_line_recall']:.4f} |",
        f"| relevance mass recall | {m['weighted_relevance_recall']:.4f} |",
        f"| Phase0 frontier coverage | {m['phase0_high_frontier_coverage']:.4f} |",
        f"| mean anchor span | {m['mean_anchor_span_lines']:.1f} |",
        f"| max anchor span | {m['max_anchor_span_lines']:.1f} |",
        f"| mean anchor growth | {m['mean_anchor_growth_ratio']:.2f}x |",
        "",
        "## Anchors",
        "",
    ]
    for anchor in result["anchors"]:
        lines.append(
            f"- {anchor['id']} seed={anchor['seed_range']} "
            f"tiles={len(anchor['tile_ids'])} "
            f"status={anchor['status']} "
            f"utility={anchor['final_utility_probability']} "
            f"complete={anchor['final_completeness_probability']}"
        )
    best = result["stop"]["best_remaining"]
    lines += ["", "## Hidden stop diagnostic", ""]
    if best is None:
        lines.append("- no remaining tile")
    else:
        lines.append(
            f"- best remaining {best['start_line']}-{best['end_line']}: "
            f"CC mean={best['mean_reference_relevance']:.4f}"
        )
        lines.append(
            f"- premature={result['stop']['premature_by_hidden_cc']}"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--phase0-run", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    result = evaluate(
        load(args.reference),
        load(args.phase0_run),
        load(args.run),
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    Path(args.output_markdown).write_text(
        markdown(result)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
