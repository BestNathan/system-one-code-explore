#!/usr/bin/env python3
"""Benchmark R15 frontier obligations and directional semantic closure."""
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
            field[line - 1] = max(field[line - 1], score)
    return field


def range_lines(left, right):
    return set(range(int(left), int(right) + 1))


def selected_lines(run):
    lines = set()
    for item in run.get("materialized_evidence", []):
        lines.update(
            range_lines(item["start_line"], item["end_line"])
        )
    return lines


def retained_lines(run):
    lines = set()
    for region in run.get("final_regions", []):
        lines.update(
            range_lines(region["start_line"], region["end_line"])
        )
    return lines


def high_regions(field, threshold=0.70):
    regions = []
    start = None
    for index, value in enumerate(field, 1):
        high = float(value) >= float(threshold)
        if high and start is None:
            start = index
        if not high and start is not None:
            regions.append((start, index - 1))
            start = None
    if start is not None:
        regions.append((start, len(field)))
    return regions


def evaluate(reference, phase0_run, run):
    truth = reference_field(reference)
    n = len(truth)
    materialized = selected_lines(run)
    retained = retained_lines(run)
    high = {
        i + 1 for i, value in enumerate(truth)
        if value >= 0.70
    }
    mass = sum(truth)

    def evidence_metrics(lines):
        selected_mass = sum(truth[line - 1] for line in lines)
        selected_high = len(lines & high)
        return {
            "lines": len(lines),
            "source_fraction": len(lines) / n if n else 0.0,
            "mean_reference_relevance": (
                selected_mass / len(lines) if lines else 0.0
            ),
            "high_line_precision": (
                selected_high / len(lines) if lines else 0.0
            ),
            "high_line_recall": (
                selected_high / len(high) if high else 0.0
            ),
            "weighted_relevance_recall": (
                selected_mass / mass if mass else 0.0
            ),
        }

    obligation_rows = []
    for obligation in run.get("obligations", []):
        left, right = obligation["range"]
        obligation_truth = truth[left - 1:right]
        anchors = [
            anchor
            for anchor in run.get("anchors", [])
            if anchor["obligation_id"] == obligation["id"]
        ]
        retained_anchor = next(
            (
                anchor for anchor in anchors
                if anchor["status"] == "retained"
            ),
            None,
        )
        obligation_rows.append({
            "id": obligation["id"],
            "range": obligation["range"],
            "status": obligation["status"],
            "candidate_count": len(
                obligation["representative_candidates"]
            ),
            "attempted_seed_count": len(
                obligation["attempted_seed_ids"]
            ),
            "anchor_count": len(anchors),
            "reference_mean": (
                sum(obligation_truth) / len(obligation_truth)
                if obligation_truth else 0.0
            ),
            "reference_max": (
                max(obligation_truth)
                if obligation_truth else 0.0
            ),
            "retained_anchor_id": (
                retained_anchor["id"]
                if retained_anchor else None
            ),
            "retained_utility": (
                retained_anchor[
                    "final_utility_probability"
                ]
                if retained_anchor else None
            ),
        })

    anchors = run.get("anchors", [])
    anchor_spans = []
    anchor_growth = []
    directional_steps = 0
    closure_expansion_tiles = 0
    for anchor in anchors:
        seed_left, seed_right = anchor["seed_range"]
        seed_span = seed_right - seed_left + 1
        tile_count = len(anchor["tile_ids"])
        span = tile_count * int(
            run.get("policy", {}).get("tile_lines", 32)
        )
        anchor_spans.append(span)
        anchor_growth.append(span / seed_span)
        directional_steps += len(anchor.get("closure_steps", []))
        closure_expansion_tiles += max(0, tile_count - 1)

    cc_regions = high_regions(truth, threshold=0.70)
    obligation_ranges = [
        tuple(item["range"])
        for item in run.get("obligations", [])
    ]
    uncovered_cc_regions = []
    for cc_left, cc_right in cc_regions:
        overlaps = any(
            not (ob_right < cc_left or ob_left > cc_right)
            for ob_left, ob_right in obligation_ranges
        )
        if not overlaps:
            uncovered_cc_regions.append(
                [cc_left, cc_right]
            )

    retained_metrics = evidence_metrics(retained)
    materialized_metrics = evidence_metrics(materialized)

    return {
        "schema_version": 1,
        "kind": "r15-frontier-obligation-benchmark",
        "metrics": {
            "obligation_count": len(obligation_rows),
            "satisfied_obligations": sum(
                item["status"] == "satisfied"
                for item in obligation_rows
            ),
            "exhausted_obligations": sum(
                item["status"] == "exhausted"
                for item in obligation_rows
            ),
            "mean_seed_attempts_per_obligation": (
                sum(
                    item["attempted_seed_count"]
                    for item in obligation_rows
                ) / len(obligation_rows)
                if obligation_rows else 0.0
            ),
            "anchor_count": len(anchors),
            "retained_anchor_count": len(
                run.get("retained_anchor_ids", [])
            ),
            "rejected_anchor_count": sum(
                item["status"] == "rejected_low_utility"
                for item in anchors
            ),
            "closure_safety_cap_count": sum(
                item["status"] == "closure_safety_cap"
                for item in anchors
            ),
            "directional_closure_steps": directional_steps,
            "closure_expansion_tiles": closure_expansion_tiles,
            "mean_anchor_span_lines": (
                sum(anchor_spans) / len(anchor_spans)
                if anchor_spans else 0.0
            ),
            "max_anchor_span_lines": (
                max(anchor_spans) if anchor_spans else 0.0
            ),
            "mean_anchor_growth_ratio": (
                sum(anchor_growth) / len(anchor_growth)
                if anchor_growth else 0.0
            ),
            "hidden_cc_high_region_count": len(cc_regions),
            "hidden_cc_high_regions_without_phase0_obligation": len(
                uncovered_cc_regions
            ),
            "materialized": materialized_metrics,
            "retained": retained_metrics,
        },
        "frontier_geometry": run.get("frontier_geometry"),
        "obligations": obligation_rows,
        "hidden_cc_regions_without_obligation": uncovered_cc_regions,
        "termination": run.get("termination"),
    }


def markdown(result):
    m = result["metrics"]
    mat = m["materialized"]
    ret = m["retained"]
    lines = [
        "# R15 frontier obligations benchmark",
        "",
        f"- termination: {result['termination']}",
        f"- obligations: {m['obligation_count']}",
        f"- satisfied: {m['satisfied_obligations']}",
        f"- exhausted: {m['exhausted_obligations']}",
        f"- anchors: {m['anchor_count']}",
        f"- retained anchors: {m['retained_anchor_count']}",
        "",
        "| metric | materialized | retained final evidence |",
        "| --- | ---: | ---: |",
        (
            "| source fraction | "
            f"{mat['source_fraction']:.4f} | "
            f"{ret['source_fraction']:.4f} |"
        ),
        (
            "| mean CC relevance | "
            f"{mat['mean_reference_relevance']:.4f} | "
            f"{ret['mean_reference_relevance']:.4f} |"
        ),
        (
            "| high precision | "
            f"{mat['high_line_precision']:.4f} | "
            f"{ret['high_line_precision']:.4f} |"
        ),
        (
            "| high recall | "
            f"{mat['high_line_recall']:.4f} | "
            f"{ret['high_line_recall']:.4f} |"
        ),
        (
            "| relevance mass recall | "
            f"{mat['weighted_relevance_recall']:.4f} | "
            f"{ret['weighted_relevance_recall']:.4f} |"
        ),
        "",
        "## Closure",
        "",
        f"- mean anchor span: {m['mean_anchor_span_lines']:.1f} lines",
        f"- max anchor span: {m['max_anchor_span_lines']:.1f} lines",
        f"- mean anchor growth: {m['mean_anchor_growth_ratio']:.2f}x",
        f"- closure expansion tiles: {m['closure_expansion_tiles']}",
        f"- closure safety caps: {m['closure_safety_cap_count']}",
        "",
        "## Hidden coverage diagnostic",
        "",
        (
            "- CC high regions: "
            f"{m['hidden_cc_high_region_count']}"
        ),
        (
            "- CC high regions with no Phase0 obligation overlap: "
            f"{m['hidden_cc_high_regions_without_phase0_obligation']}"
        ),
        "",
        "## Obligations",
        "",
    ]
    for item in result["obligations"]:
        lines.append(
            f"- {item['id']} {item['range']} "
            f"status={item['status']} "
            f"attempts={item['attempted_seed_count']} "
            f"CCmean={item['reference_mean']:.3f} "
            f"CCmax={item['reference_max']:.3f}"
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
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        markdown(result),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
