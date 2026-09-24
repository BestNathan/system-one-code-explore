#!/usr/bin/env python3
"""Replay one fixed probe trajectory through multiple posterior estimators."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from posterior_reconstruction import ESTIMATORS, reconstruct
from probability_frontier_benchmark import (
    cc_line_field,
    evaluate_snapshot,
)


DEFAULT_CHECKPOINTS = (4, 8, 12, 16, 24, 32)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_estimator(
    estimator,
    trajectory,
    reference,
    checkpoints=DEFAULT_CHECKPOINTS,
):
    samples = trajectory["samples"]
    line_count = int(reference["line_count"])
    truth = cc_line_field(reference)
    sample_lines = int(trajectory.get("sample_lines", 8))

    rows = []
    for checkpoint in checkpoints:
        prefix = samples[: int(checkpoint)]
        posterior = reconstruct(
            estimator,
            prefix,
            line_count,
            sample_lines=sample_lines,
        )
        snapshot = {
            "probes": len(prefix),
            "sampled_source_lines": sum(
                int(item["end_line"]) - int(item["start_line"]) + 1
                for item in prefix
            ),
            "relevance": posterior["relevance"],
            "uncertainty": posterior["uncertainty"],
            "usage": {},
        }
        rows.append(evaluate_snapshot(snapshot, truth, 0.70))

    return rows


def local_score_metrics(trajectory, reference):
    truth = cc_line_field(reference)
    predicted = []
    actual = []
    for sample in trajectory["samples"]:
        left = int(sample["start_line"])
        right = int(sample["end_line"])
        predicted.append(float(sample["score"]))
        actual.append(
            max(truth[left - 1:right])
            if right >= left
            else truth[left - 1]
        )

    def mean(values):
        return sum(values) / len(values) if values else 0.0

    mp = mean(predicted)
    ma = mean(actual)
    numerator = sum(
        (p - mp) * (a - ma)
        for p, a in zip(predicted, actual)
    )
    pvar = sum((p - mp) ** 2 for p in predicted)
    avar = sum((a - ma) ** 2 for a in actual)
    pearson = (
        numerator / (pvar * avar) ** 0.5
        if pvar > 0.0 and avar > 0.0
        else 0.0
    )
    mae = mean(
        [abs(p - a) for p, a in zip(predicted, actual)]
    )
    return {
        "count": len(predicted),
        "pearson": pearson,
        "mae": mae,
    }


def build_report(trajectory, reference, checkpoints):
    estimators = {}
    for name in ESTIMATORS:
        estimators[name] = evaluate_estimator(
            name,
            trajectory,
            reference,
            checkpoints,
        )

    return {
        "research": "R07 posterior reconstruction",
        "trajectory": {
            "source_run": trajectory.get("source_run"),
            "sample_count": len(trajectory["samples"]),
            "sample_lines": trajectory.get("sample_lines"),
            "subject": trajectory.get("subject"),
            "model": trajectory.get("model"),
        },
        "reference": {
            "kind": reference.get("kind"),
            "line_count": reference["line_count"],
            "window_lines": reference.get("window_lines"),
            "stride_lines": reference.get("stride_lines"),
            "range_count": len(reference["ranges"]),
        },
        "local_score": local_score_metrics(
            trajectory,
            reference,
        ),
        "checkpoints": list(checkpoints),
        "estimators": estimators,
    }


def markdown(report):
    lines = [
        "# R07 posterior reconstruction benchmark",
        "",
        "All estimators replay the same recorded System One probes and local scores.",
        "",
        "Local System One score vs CC local reference:",
        "",
        f"- Pearson: {report['local_score']['pearson']:.4f}",
        f"- MAE: {report['local_score']['mae']:.4f}",
        "",
    ]

    checkpoints = report["checkpoints"]
    for name, rows in report["estimators"].items():
        lines.extend([
            f"## {name}",
            "",
            "| probes | MAE ↓ | RMSE ↓ | Pearson ↑ | Spearman ↑ | JS ↓ | Wasserstein ↓ | mean uncertainty |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for checkpoint, row in zip(checkpoints, rows):
            lines.append(
                "| {checkpoint} | {mae:.4f} | {rmse:.4f} | "
                "{pearson:.4f} | {spearman:.4f} | "
                "{js_divergence:.4f} | {wasserstein_position:.4f} | "
                "{mean_uncertainty:.4f} |".format(
                    checkpoint=checkpoint,
                    **row,
                )
            )
        lines.append("")

    lines.extend([
        "## Final checkpoint comparison",
        "",
        "| estimator | MAE ↓ | Pearson ↑ | Spearman ↑ |",
        "| --- | ---: | ---: | ---: |",
    ])
    for name, rows in report["estimators"].items():
        row = rows[-1]
        lines.append(
            f"| {name} | {row['mae']:.4f} | "
            f"{row['pearson']:.4f} | {row['spearman']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument(
        "--checkpoints",
        default=",".join(str(x) for x in DEFAULT_CHECKPOINTS),
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    checkpoints = tuple(
        int(item.strip())
        for item in args.checkpoints.split(",")
        if item.strip()
    )
    report = build_report(
        load(args.trajectory),
        load(args.reference),
        checkpoints,
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
