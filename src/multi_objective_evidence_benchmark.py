#!/usr/bin/env python3
"""Benchmark R13 multi-objective evidence acquisition."""
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


def selected_lines(run):
    out = set()
    for item in run.get("selected_evidence", []):
        out.update(
            range(
                int(item["start_line"]),
                int(item["end_line"]) + 1,
            )
        )
    return out


def latest_final_assessments(run):
    """Return latest assessments keyed by exact final region range."""
    latest = {}
    for round_item in run.get("history", []):
        for item in round_item.get(
            "region_assessments",
            [],
        ):
            latest[
                (
                    int(item["start_line"]),
                    int(item["end_line"]),
                )
            ] = item
    out = []
    for region in run.get("final_regions", []):
        key = (
            int(region["start_line"]),
            int(region["end_line"]),
        )
        item = latest.get(key)
        if item is not None:
            out.append(item)
    return out


def evaluate(reference, phase0_run, run, high_threshold=0.70, frontier_threshold=0.65):
    truth = reference_field(reference)
    frontier = phase0_run["frontier"]
    chosen = selected_lines(run)
    n = len(truth)

    high = {
        i + 1
        for i, score in enumerate(truth)
        if score >= float(high_threshold)
    }
    frontier_high = {
        i + 1
        for i, score in enumerate(frontier["relevance"])
        if float(score) >= float(frontier_threshold)
    }

    mass = sum(truth)
    chosen_mass = sum(
        truth[line - 1]
        for line in chosen
    )
    chosen_high = len(chosen & high)
    chosen_frontier_high = len(chosen & frontier_high)

    final_assessments = latest_final_assessments(run)
    completeness = [
        float(item["completeness_probability"])
        for item in final_assessments
    ]
    utility = [
        float(item["utility_probability"])
        for item in final_assessments
    ]

    closure_expansions = [
        item
        for round_item in run.get("history", [])
        for item in round_item.get("closure_expansions", [])
    ]
    frontier_acquisitions = [
        item
        for evidence in run.get("selected_evidence", [])
        if evidence.get("reason") == "frontier_or_utility"
        for item in [evidence]
    ]

    remaining = run.get("remaining_actions", [])
    remaining_truth = []
    for item in remaining:
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
                max(values) if values else 0.0
            ),
            "phase0_mean_relevance": float(
                item["phase0_mean_relevance"]
            ),
        })
    best_remaining = (
        max(
            remaining_truth,
            key=lambda item: (
                item["mean_reference_relevance"],
                item["max_reference_relevance"],
            ),
        )
        if remaining_truth else None
    )

    regions = run.get("final_regions", [])
    region_lengths = [
        int(item["end_line"]) - int(item["start_line"]) + 1
        for item in regions
    ]

    return {
        "schema_version": 1,
        "kind": "r13-multi-objective-evidence-benchmark",
        "metrics": {
            "selected_tiles": len(
                run.get("selected_evidence", [])
            ),
            "selected_lines": len(chosen),
            "source_fraction": (
                len(chosen) / n if n else 0.0
            ),
            "mean_reference_relevance": (
                chosen_mass / len(chosen)
                if chosen else 0.0
            ),
            "high_line_precision": (
                chosen_high / len(chosen)
                if chosen else 0.0
            ),
            "high_line_recall": (
                chosen_high / len(high)
                if high else 0.0
            ),
            "weighted_relevance_recall": (
                chosen_mass / mass
                if mass else 0.0
            ),
            "phase0_high_frontier_coverage": (
                chosen_frontier_high
                / len(frontier_high)
                if frontier_high else 0.0
            ),
            "final_regions": len(regions),
            "mean_final_region_lines": (
                sum(region_lengths) / len(region_lengths)
                if region_lengths else 0.0
            ),
            "frontier_acquisition_tiles": len(
                frontier_acquisitions
            ),
            "closure_expansion_tiles": len(
                closure_expansions
            ),
            "mean_final_system1_completeness": (
                sum(completeness) / len(completeness)
                if completeness else None
            ),
            "min_final_system1_completeness": (
                min(completeness)
                if completeness else None
            ),
            "final_regions_below_completeness_threshold": sum(
                score
                < float(
                    run.get("policy", {}).get(
                        "completeness_threshold",
                        0.70,
                    )
                )
                for score in completeness
            ),
            "mean_final_system1_utility": (
                sum(utility) / len(utility)
                if utility else None
            ),
        },
        "stop": {
            "termination": run.get("termination"),
            "best_remaining": best_remaining,
            "premature_by_hidden_cc": bool(
                best_remaining is not None
                and best_remaining[
                    "mean_reference_relevance"
                ] >= float(high_threshold)
            ),
        },
        "final_region_assessments": final_assessments,
        "closure_expansions": closure_expansions,
    }


def markdown(result):
    m = result["metrics"]
    stop = result["stop"]
    lines = [
        "# R13 multi-objective evidence benchmark",
        "",
        f"- termination: {stop['termination']}",
        f"- selected tiles: {m['selected_tiles']}",
        f"- selected lines: {m['selected_lines']}",
        f"- final regions: {m['final_regions']}",
        f"- closure expansions: {m['closure_expansion_tiles']}",
        "",
        "| metric | value |",
        "| --- | ---: |",
        (
            "| mean CC relevance | "
            f"{m['mean_reference_relevance']:.4f} |"
        ),
        (
            "| high-line precision | "
            f"{m['high_line_precision']:.4f} |"
        ),
        (
            "| high-line recall | "
            f"{m['high_line_recall']:.4f} |"
        ),
        (
            "| weighted relevance recall | "
            f"{m['weighted_relevance_recall']:.4f} |"
        ),
        (
            "| Phase0 high-frontier coverage | "
            f"{m['phase0_high_frontier_coverage']:.4f} |"
        ),
        (
            "| mean final region lines | "
            f"{m['mean_final_region_lines']:.1f} |"
        ),
    ]
    if m["mean_final_system1_completeness"] is not None:
        lines.append(
            "| mean System1 completeness | "
            f"{m['mean_final_system1_completeness']:.4f} |"
        )
        lines.append(
            "| min System1 completeness | "
            f"{m['min_final_system1_completeness']:.4f} |"
        )
    lines += [
        "",
        "## Final regions",
        "",
    ]
    for item in result["final_region_assessments"]:
        lines.append(
            f"- {item['start_line']}-{item['end_line']}: "
            f"utility={item['utility_probability']:.3f}, "
            f"complete={item['completeness_probability']:.3f}"
        )
    best = stop["best_remaining"]
    lines += ["", "## Hidden stop diagnostic", ""]
    if best is None:
        lines.append("- no remaining tile")
    else:
        lines += [
            (
                "- best remaining range: "
                f"{best['start_line']}-{best['end_line']}"
            ),
            (
                "- best remaining CC mean: "
                f"{best['mean_reference_relevance']:.4f}"
            ),
            (
                "- premature by hidden CC: "
                f"{stop['premature_by_hidden_cc']}"
            ),
        ]
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
