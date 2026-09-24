#!/usr/bin/env python3
"""Evaluate R12 dynamic evidence acquisition against a full-read reference."""
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


def tile_truth(field, left, right, high_threshold=0.70):
    values = field[left - 1:right]
    high = sum(value >= high_threshold for value in values)
    return {
        "mean_relevance": (
            sum(values) / len(values) if values else 0.0
        ),
        "max_relevance": max(values) if values else 0.0,
        "relevance_mass": sum(values),
        "high_lines": high,
        "high_fraction": (
            high / len(values) if values else 0.0
        ),
        "lines": len(values),
    }


def evaluate(reference, dynamic_run, high_threshold=0.70):
    field = reference_field(reference)
    n = len(field)
    selected = dynamic_run.get("selected_evidence", [])
    remaining = dynamic_run.get("remaining_actions", [])

    selected_truth = []
    chosen_lines = set()
    for index, item in enumerate(selected, 1):
        left = int(item["start_line"])
        right = int(item["end_line"])
        truth = tile_truth(
            field,
            left,
            right,
            high_threshold=high_threshold,
        )
        selected_truth.append({
            "order": index,
            "id": item["id"],
            "start_line": left,
            "end_line": right,
            "noul_probability": float(
                item["noul_probability"]
            ),
            
            "phase0_mean_relevance": float(
                item["phase0_mean_relevance"]
            ),
            **truth,
        })
        chosen_lines.update(range(left, right + 1))

    high_lines = {
        i + 1
        for i, value in enumerate(field)
        if value >= high_threshold
    }
    total_mass = sum(field)
    chosen_mass = sum(field[line - 1] for line in chosen_lines)
    chosen_high = len(chosen_lines & high_lines)

    selected_metrics = {
        "selected_tiles": len(selected_truth),
        "selected_lines": len(chosen_lines),
        "source_fraction": (
            len(chosen_lines) / n if n else 0.0
        ),
        "mean_reference_relevance": (
            chosen_mass / len(chosen_lines)
            if chosen_lines else 0.0
        ),
        "high_line_precision": (
            chosen_high / len(chosen_lines)
            if chosen_lines else 0.0
        ),
        "high_line_recall": (
            chosen_high / len(high_lines)
            if high_lines else 0.0
        ),
        "weighted_relevance_recall": (
            chosen_mass / total_mass
            if total_mass else 0.0
        ),
    }

    # Same action-space, same selected tile count: what is the best possible
    # evidence under the exact R12 partition?
    tile_lines = int(
        dynamic_run.get("policy", {}).get("tile_lines", 32)
    )
    all_tiles = []
    tile_index = 1
    for left in range(1, n + 1, tile_lines):
        right = min(n, left + tile_lines - 1)
        truth = tile_truth(
            field,
            left,
            right,
            high_threshold=high_threshold,
        )
        all_tiles.append({
            "id": f"tile_{tile_index:03d}",
            "start_line": left,
            "end_line": right,
            **truth,
        })
        tile_index += 1

    k = len(selected_truth)
    oracle = sorted(
        all_tiles,
        key=lambda item: (
            -item["relevance_mass"],
            item["start_line"],
        ),
    )[:k]
    oracle_lines = set()
    for item in oracle:
        oracle_lines.update(
            range(item["start_line"], item["end_line"] + 1)
        )
    oracle_mass = sum(field[line - 1] for line in oracle_lines)
    oracle_high = len(oracle_lines & high_lines)
    oracle_metrics = {
        "selected_tiles": len(oracle),
        "selected_lines": len(oracle_lines),
        "mean_reference_relevance": (
            oracle_mass / len(oracle_lines)
            if oracle_lines else 0.0
        ),
        "high_line_precision": (
            oracle_high / len(oracle_lines)
            if oracle_lines else 0.0
        ),
        "high_line_recall": (
            oracle_high / len(high_lines)
            if high_lines else 0.0
        ),
        "weighted_relevance_recall": (
            oracle_mass / total_mass
            if total_mass else 0.0
        ),
    }

    remaining_truth = []
    for item in remaining:
        truth = tile_truth(
            field,
            int(item["start_line"]),
            int(item["end_line"]),
            high_threshold=high_threshold,
        )
        remaining_truth.append({
            "id": item["id"],
            "start_line": int(item["start_line"]),
            "end_line": int(item["end_line"]),
            **truth,
        })
    best_remaining = (
        max(
            remaining_truth,
            key=lambda item: (
                item["mean_relevance"],
                item["high_fraction"],
                -item["start_line"],
            ),
        )
        if remaining_truth else None
    )
    remaining_high_tiles = sum(
        item["mean_relevance"] >= high_threshold
        for item in remaining_truth
    )

    stop = {
        "termination": dynamic_run.get("termination"),
        "remaining_tiles": len(remaining_truth),
        "remaining_high_tiles_by_mean": remaining_high_tiles,
        "best_remaining": best_remaining,
        "premature_stop": bool(
            best_remaining is not None
            and best_remaining["mean_relevance"] >= high_threshold
            and dynamic_run.get("termination") != "safety_cap"
        ),
    }

    return {
        "schema_version": 1,
        "kind": "dynamic-evidence-acquisition-benchmark",
        "high_threshold": float(high_threshold),
        "metrics": selected_metrics,
        "oracle_same_tile_budget": oracle_metrics,
        "oracle_ratio": {
            key: (
                selected_metrics[key] / oracle_metrics[key]
                if oracle_metrics[key] else 0.0
            )
            for key in (
                "mean_reference_relevance",
                "high_line_recall",
                "weighted_relevance_recall",
            )
        },
        "stop": stop,
        "selected_truth": selected_truth,
        "oracle_tiles": oracle,
    }


def render_markdown(result):
    m = result["metrics"]
    o = result["oracle_same_tile_budget"]
    stop = result["stop"]
    lines = [
        "# R12 dynamic evidence acquisition benchmark",
        "",
        f"- termination: {stop['termination']}",
        f"- selected tiles: {m['selected_tiles']}",
        f"- selected lines: {m['selected_lines']}",
        f"- source fraction: {m['source_fraction']:.4f}",
        f"- premature stop: {stop['premature_stop']}",
        "",
        "| metric | dynamic | same-budget tile oracle |",
        "| --- | ---: | ---: |",
        (
            "| mean reference relevance | "
            f"{m['mean_reference_relevance']:.4f} | "
            f"{o['mean_reference_relevance']:.4f} |"
        ),
        (
            "| high-line precision | "
            f"{m['high_line_precision']:.4f} | "
            f"{o['high_line_precision']:.4f} |"
        ),
        (
            "| high-line recall | "
            f"{m['high_line_recall']:.4f} | "
            f"{o['high_line_recall']:.4f} |"
        ),
        (
            "| weighted relevance recall | "
            f"{m['weighted_relevance_recall']:.4f} | "
            f"{o['weighted_relevance_recall']:.4f} |"
        ),
        "",
        "## Selected sequence",
        "",
        "| # | range | Noul p | Phase0 mean | CC mean | CC high fraction |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in result["selected_truth"]:
        lines.append(
            f"| {item['order']} | "
            f"{item['start_line']}-{item['end_line']} | "
            f"{item['noul_probability']:.4f} | "
            f"{item['phase0_mean_relevance']:.4f} | "
            f"{item['mean_relevance']:.4f} | "
            f"{item['high_fraction']:.4f} |"
        )

    best = stop["best_remaining"]
    lines += ["", "## Stop diagnostic", ""]
    if best is None:
        lines.append("- no remaining tile")
    else:
        lines += [
            (
                "- best remaining CC tile: "
                f"{best['start_line']}-{best['end_line']}"
            ),
            f"- best remaining CC mean: {best['mean_relevance']:.4f}",
            f"- best remaining high fraction: {best['high_fraction']:.4f}",
            (
                "- remaining tiles with CC mean >= threshold: "
                f"{stop['remaining_high_tiles_by_mean']}"
            ),
        ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    parser.add_argument(
        "--high-threshold",
        type=float,
        default=0.70,
    )
    args = parser.parse_args(argv)

    result = evaluate(
        load(args.reference),
        load(args.run),
        high_threshold=args.high_threshold,
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        render_markdown(result),
        encoding="utf-8",
    )
    print(json.dumps({
        "metrics": result["metrics"],
        "stop": result["stop"],
    }, indent=2))


if __name__ == "__main__":
    main()
