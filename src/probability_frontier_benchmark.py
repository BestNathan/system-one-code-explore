#!/usr/bin/env python3
"""Compare Phase0 whole-file probability frontier snapshots to a CC full-read field."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


DEFAULT_CHECKPOINTS = [4, 8, 12, 16, 24, 32]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cc_line_field(reference):
    n = int(reference["line_count"])
    field = [0.0] * n
    for item in reference["ranges"]:
        score = float(item["relevance"])
        left = max(1, int(item["start_line"]))
        right = min(n, int(item["end_line"]))
        for line in range(left, right + 1):
            idx = line - 1
            field[idx] = max(field[idx], score)
    return field


def mean(values):
    return sum(values) / len(values) if values else 0.0


def pearson(left, right):
    if len(left) != len(right) or not left:
        return 0.0
    ml, mr = mean(left), mean(right)
    num = sum((a - ml) * (b - mr) for a, b in zip(left, right))
    dl = sum((a - ml) ** 2 for a in left)
    dr = sum((b - mr) ** 2 for b in right)
    den = math.sqrt(dl * dr)
    return num / den if den else 0.0


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        value = values[order[i]]
        while j < len(order) and values[order[j]] == value:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        for k in range(i, j):
            out[order[k]] = avg_rank
        i = j
    return out


def spearman(left, right):
    return pearson(ranks(left), ranks(right))


def normalize_mass(values):
    clipped = [max(0.0, float(x)) for x in values]
    total = sum(clipped)
    if total <= 0:
        return [1.0 / len(clipped)] * len(clipped) if clipped else []
    return [x / total for x in clipped]


def js_divergence(left, right):
    p = normalize_mass(left)
    q = normalize_mass(right)
    if not p:
        return 0.0
    m = [(a + b) / 2.0 for a, b in zip(p, q)]

    def kl(a, b):
        total = 0.0
        for x, y in zip(a, b):
            if x > 0 and y > 0:
                total += x * math.log2(x / y)
        return total

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def wasserstein_position(left, right):
    """1D Wasserstein distance over source-line relevance mass, normalized to [0,1]."""
    p = normalize_mass(left)
    q = normalize_mass(right)
    n = len(p)
    if n <= 1:
        return 0.0
    cumulative = 0.0
    distance = 0.0
    for a, b in zip(p, q):
        cumulative += a - b
        distance += abs(cumulative)
    return distance / (n - 1)


def top_relevance_metrics(pred, truth, high_threshold=0.70):
    relevant = [i for i, x in enumerate(truth) if x >= high_threshold]
    if not relevant:
        return {
            "high_relevance_recall": 0.0,
            "top_k_recall": 0.0,
            "high_relevance_count": 0,
        }

    predicted_high = {i for i, x in enumerate(pred) if x >= high_threshold}
    high_recall = sum(i in predicted_high for i in relevant) / len(relevant)

    k = len(relevant)
    predicted_top = set(
        sorted(range(len(pred)), key=lambda i: (-pred[i], i))[:k]
    )
    top_k_recall = sum(i in predicted_top for i in relevant) / len(relevant)
    return {
        "high_relevance_recall": high_recall,
        "top_k_recall": top_k_recall,
        "high_relevance_count": len(relevant),
    }


def evaluate_snapshot(snapshot, truth, high_threshold=0.70):
    pred = [float(x) for x in snapshot["relevance"]]
    if len(pred) != len(truth):
        raise ValueError(
            f"frontier length mismatch: {len(pred)} != {len(truth)}"
        )
    errors = [a - b for a, b in zip(pred, truth)]
    mae = mean([abs(x) for x in errors])
    rmse = math.sqrt(mean([x * x for x in errors]))
    metrics = {
        "probes": int(snapshot["probes"]),
        "sampled_source_lines": int(snapshot.get("sampled_source_lines", 0)),
        "mae": mae,
        "rmse": rmse,
        "pearson": pearson(pred, truth),
        "spearman": spearman(pred, truth),
        "js_divergence": js_divergence(pred, truth),
        "wasserstein_position": wasserstein_position(pred, truth),
        "mean_uncertainty": mean(
            [float(x) for x in snapshot.get("uncertainty", [])]
        ),
        "usage": snapshot.get("usage", {}),
    }
    metrics.update(top_relevance_metrics(pred, truth, high_threshold))
    return metrics


def nearest_snapshot(snapshots, checkpoint):
    exact = [x for x in snapshots if int(x["probes"]) == checkpoint]
    if exact:
        return exact[-1]
    after = [x for x in snapshots if int(x["probes"]) > checkpoint]
    if after:
        return min(after, key=lambda x: int(x["probes"]))
    return max(snapshots, key=lambda x: int(x["probes"]))


def evaluate(reference, run, checkpoints=None, high_threshold=0.70):
    checkpoints = checkpoints or DEFAULT_CHECKPOINTS
    truth = cc_line_field(reference)
    snapshots = run["snapshots"]
    if not snapshots:
        raise ValueError("probability frontier run has no snapshots")

    rows = []
    seen = set()
    for checkpoint in checkpoints:
        snapshot = nearest_snapshot(snapshots, int(checkpoint))
        probes = int(snapshot["probes"])
        if probes in seen:
            continue
        seen.add(probes)
        row = evaluate_snapshot(snapshot, truth, high_threshold)
        row["requested_checkpoint"] = int(checkpoint)
        rows.append(row)

    final = evaluate_snapshot(snapshots[-1], truth, high_threshold)
    return {
        "reference": {
            "path": reference["path"],
            "line_count": reference["line_count"],
            "range_count": len(reference["ranges"]),
            "high_threshold": high_threshold,
        },
        "run": {
            "kind": run.get("kind"),
            "probes": run.get("probes"),
            "sample_lines": run.get("sample_lines"),
            "respect_stop": run.get("respect_stop"),
        },
        "checkpoints": rows,
        "final": final,
    }


def markdown(report):
    lines = [
        "# Probability Frontier v5 convergence",
        "",
        "| probes | source lines | MAE ↓ | RMSE ↓ | Pearson ↑ | Spearman ↑ | top-K recall ↑ | high≥0.7 recall ↑ | JS ↓ | Wasserstein ↓ | mean uncertainty ↓ | input tokens |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["checkpoints"]:
        usage = row.get("usage", {})
        lines.append(
            "| {probes} | {sampled_source_lines} | {mae:.4f} | {rmse:.4f} | "
            "{pearson:.4f} | {spearman:.4f} | {top_k_recall:.4f} | "
            "{high_relevance_recall:.4f} | {js_divergence:.4f} | "
            "{wasserstein_position:.4f} | {mean_uncertainty:.4f} | {input_tokens} |".format(
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                **row,
            )
        )
    lines.extend([
        "",
        "The reference field is the line-level projection of the validated CC full-read canonical-window scores.",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--checkpoints", default="4,8,12,16,24,32")
    parser.add_argument("--high-threshold", type=float, default=0.70)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    checkpoints = [
        int(x.strip()) for x in args.checkpoints.split(",") if x.strip()
    ]
    report = evaluate(
        load(args.reference),
        load(args.run),
        checkpoints,
        args.high_threshold,
    )
    Path(args.output_json).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
