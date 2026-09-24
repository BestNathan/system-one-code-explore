#!/usr/bin/env python3
"""Measure whether a probability-frontier policy improves search, not just fit.

The reference is a fixed full-read relevance field. The candidate run is an
online sparse-probe trajectory. Metrics are cumulative over the actual probe
order and therefore answer questions such as:

- how many probes are needed before a high-relevance region is touched?
- how much high-relevance/reference mass is recovered at a fixed source budget?
- how useful are the probes selected by the online policy?
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reference_fields(reference):
    n = int(reference["line_count"])
    relevance = [0.0] * n
    core = [False] * n
    for item in reference.get("ranges", []):
        left = max(1, int(item["start_line"]))
        right = min(n, int(item["end_line"]))
        score = float(item["relevance"])
        is_core = item.get("role") == "core"
        for line in range(left, right + 1):
            idx = line - 1
            relevance[idx] = max(relevance[idx], score)
            core[idx] = core[idx] or is_core
    return relevance, core


def extract_probes(run):
    probes = []
    for row in run.get("history", []):
        actions = row.get("actions")
        if actions is None:
            actions = row.get("policy", {}).get("selected_actions", [])
        for action in actions or []:
            probes.append({
                "start_line": int(action["start_line"]),
                "end_line": int(action["end_line"]),
                "kind": action.get("kind"),
            })
    if probes:
        return probes

    # Compact/pinned trajectories may only retain samples.
    samples = run.get("samples")
    if samples is None:
        samples = run.get("frontier", {}).get("samples", [])
    for sample in samples or []:
        probes.append({
            "start_line": int(sample["start_line"]),
            "end_line": int(sample["end_line"]),
            "kind": sample.get("kind"),
        })
    return probes


def _recall(hit, total):
    return hit / total if total else 0.0


def _probe_mean(field, left, right):
    values = field[left - 1:right]
    return sum(values) / len(values) if values else 0.0


def _first_probe_for_recall(curve, key, target):
    for row in curve:
        if float(row[key]) >= target:
            return int(row["probe"])
    return None


def evaluate(reference, run, high_threshold=0.70):
    field, core = reference_fields(reference)
    n = len(field)
    probes = extract_probes(run)

    high_lines = {i + 1 for i, value in enumerate(field) if value >= high_threshold}
    core_lines = {i + 1 for i, value in enumerate(core) if value}
    total_mass = sum(field)

    observed = set()
    curve = []
    first_high_hit = None
    first_core_hit = None
    useful_probes = 0
    probe_truth_means = []

    for index, probe in enumerate(probes, 1):
        left = max(1, int(probe["start_line"]))
        right = min(n, int(probe["end_line"]))
        lines = set(range(left, right + 1))
        observed.update(lines)

        touches_high = bool(lines & high_lines)
        touches_core = bool(lines & core_lines)
        if touches_high:
            useful_probes += 1
            if first_high_hit is None:
                first_high_hit = index
        if touches_core and first_core_hit is None:
            first_core_hit = index

        probe_mean = _probe_mean(field, left, right)
        probe_truth_means.append(probe_mean)

        high_hit = len(observed & high_lines)
        core_hit = len(observed & core_lines)
        observed_mass = sum(field[line - 1] for line in observed)
        source_coverage = len(observed) / max(1, n)
        high_recall = _recall(high_hit, len(high_lines))
        weighted_recall = _recall(observed_mass, total_mass)

        curve.append({
            "probe": index,
            "start_line": left,
            "end_line": right,
            "kind": probe.get("kind"),
            "probe_reference_mean": round(probe_mean, 6),
            "touches_high_relevance": touches_high,
            "touches_core": touches_core,
            "sampled_source_lines": len(observed),
            "source_coverage": round(source_coverage, 6),
            "high_line_recall": round(high_recall, 6),
            "core_line_recall": round(_recall(core_hit, len(core_lines)), 6),
            "weighted_relevance_recall": round(weighted_recall, 6),
        })

    final = curve[-1] if curve else {
        "sampled_source_lines": 0,
        "source_coverage": 0.0,
        "high_line_recall": 0.0,
        "core_line_recall": 0.0,
        "weighted_relevance_recall": 0.0,
    }
    count = max(1, len(curve))
    high_auc = sum(float(row["high_line_recall"]) for row in curve) / count
    weighted_auc = (
        sum(float(row["weighted_relevance_recall"]) for row in curve) / count
    )

    source_coverage = float(final["source_coverage"])
    return {
        "schema_version": 1,
        "kind": "probability-frontier-search-effect",
        "reference": {
            "line_count": n,
            "high_threshold": float(high_threshold),
            "high_lines": len(high_lines),
            "core_lines": len(core_lines),
            "relevance_mass": round(total_mass, 6),
        },
        "run": {
            "posterior_estimator": run.get("posterior_estimator"),
            "probes": len(probes),
            "sample_lines": run.get("sample_lines"),
        },
        "final": {
            "sampled_source_lines": int(final["sampled_source_lines"]),
            "source_coverage": source_coverage,
            "high_line_recall": float(final["high_line_recall"]),
            "core_line_recall": float(final["core_line_recall"]),
            "weighted_relevance_recall": float(
                final["weighted_relevance_recall"]
            ),
            "high_recall_efficiency": round(
                float(final["high_line_recall"]) / source_coverage
                if source_coverage else 0.0,
                6,
            ),
            "weighted_recall_efficiency": round(
                float(final["weighted_relevance_recall"]) / source_coverage
                if source_coverage else 0.0,
                6,
            ),
        },
        "search": {
            "first_high_hit_probe": first_high_hit,
            "first_core_hit_probe": first_core_hit,
            "probes_to_50pct_high_recall": _first_probe_for_recall(
                curve, "high_line_recall", 0.50
            ),
            "probes_to_80pct_high_recall": _first_probe_for_recall(
                curve, "high_line_recall", 0.80
            ),
            "useful_probe_rate": round(useful_probes / count, 6),
            "mean_probe_reference_relevance": round(
                sum(probe_truth_means) / count if probe_truth_means else 0.0,
                6,
            ),
            "high_recall_auc_per_probe": round(high_auc, 6),
            "weighted_recall_auc_per_probe": round(weighted_auc, 6),
        },
        "curve": curve,
    }


def render_markdown(result):
    final = result["final"]
    search = result["search"]
    rows = [
        "# Search-effect benchmark",
        "",
        f"- estimator: {result['run']['posterior_estimator']}",
        f"- probes: {result['run']['probes']}",
        f"- source coverage: {final['source_coverage']:.3f}",
        f"- final high-line recall: {final['high_line_recall']:.3f}",
        f"- final weighted relevance recall: {final['weighted_relevance_recall']:.3f}",
        f"- first high-relevance hit: {search['first_high_hit_probe']}",
        f"- useful probe rate: {search['useful_probe_rate']:.3f}",
        f"- high-recall AUC/probe: {search['high_recall_auc_per_probe']:.3f}",
        f"- weighted-recall AUC/probe: {search['weighted_recall_auc_per_probe']:.3f}",
        "",
        "| probe | range | ref mean | high? | high recall | weighted recall |",
        "| ---: | --- | ---: | :---: | ---: | ---: |",
    ]
    for row in result["curve"]:
        rows.append(
            f"| {row['probe']} | {row['start_line']}-{row['end_line']} | "
            f"{row['probe_reference_mean']:.3f} | "
            f"{'yes' if row['touches_high_relevance'] else 'no'} | "
            f"{row['high_line_recall']:.3f} | "
            f"{row['weighted_relevance_recall']:.3f} |"
        )
    return "\n".join(rows) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--high-threshold", type=float, default=0.70)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    result = evaluate(load(args.reference), load(args.run), args.high_threshold)
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        render_markdown(result),
        encoding="utf-8",
    )
    print(json.dumps(result["search"], indent=2))


if __name__ == "__main__":
    main()
