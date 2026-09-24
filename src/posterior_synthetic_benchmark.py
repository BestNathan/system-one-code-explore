#!/usr/bin/env python3
"""Synthetic posterior sanity checks for R08.

This benchmark does not use a model or code semantics. It evaluates estimator
inductive bias on several known relevance landscapes using the same deterministic
stratified sample geometry.
"""
from __future__ import annotations

import json
import math
import random

from posterior_reconstruction import reconstruct


LINE_COUNT = 1024
SAMPLE_LINES = 8
SAMPLE_COUNT = 32
SEED = 20260924


def clamp(value):
    return max(0.0, min(1.0, float(value)))


def fields():
    xs = range(1, LINE_COUNT + 1)
    return {
        "single_broad": [
            clamp(
                0.08
                + 0.85 * math.exp(
                    -0.5 * ((x - 500) / 120.0) ** 2
                )
            )
            for x in xs
        ],
        "multi_peak": [
            clamp(
                0.05
                + 0.75 * math.exp(
                    -0.5 * ((x - 220) / 60.0) ** 2
                )
                + 0.85 * math.exp(
                    -0.5 * ((x - 620) / 90.0) ** 2
                )
                + 0.55 * math.exp(
                    -0.5 * ((x - 880) / 40.0) ** 2
                )
            )
            for x in xs
        ],
        "plateau": [
            0.82 if 360 <= x <= 680 else 0.08
            for x in xs
        ],
        "narrow_spike": [
            clamp(
                0.05
                + 0.90 * math.exp(
                    -0.5 * ((x - 700) / 18.0) ** 2
                )
            )
            for x in xs
        ],
        "two_steps": [
            0.72
            if 120 <= x <= 280 or 700 <= x <= 920
            else 0.10
            for x in xs
        ],
    }


def stratified_centers():
    rng = random.Random(SEED)
    out = []
    for index in range(SAMPLE_COUNT):
        left = 1 + LINE_COUNT * index // SAMPLE_COUNT
        right = LINE_COUNT * (index + 1) // SAMPLE_COUNT
        out.append(rng.randint(left, right))
    return sorted(out)


def samples_for(truth):
    out = []
    for center in stratified_centers():
        left = max(1, center - SAMPLE_LINES // 2)
        right = min(LINE_COUNT, left + SAMPLE_LINES - 1)
        left = max(1, right - SAMPLE_LINES + 1)
        score = sum(truth[left - 1:right]) / (right - left + 1)
        out.append({
            "start_line": left,
            "end_line": right,
            "score": score,
        })
    return out


def mean(values):
    return sum(values) / len(values) if values else 0.0


def metrics(predicted, truth):
    mp = mean(predicted)
    mt = mean(truth)
    numerator = sum(
        (a - mp) * (b - mt)
        for a, b in zip(predicted, truth)
    )
    ap = sum((a - mp) ** 2 for a in predicted)
    at = sum((b - mt) ** 2 for b in truth)
    pearson = (
        numerator / math.sqrt(ap * at)
        if ap > 0.0 and at > 0.0
        else 0.0
    )
    errors = [
        a - b
        for a, b in zip(predicted, truth)
    ]
    return {
        "mae": mean([abs(x) for x in errors]),
        "rmse": math.sqrt(mean([x * x for x in errors])),
        "pearson": pearson,
    }


def run():
    estimators = (
        "sequential_exponential",
        "adaptive_gaussian_k2",
        "adaptive_gaussian_k3",
        "adaptive_gaussian_k4",
        "multi_scale_gaussian",
    )
    result = {
        "kind": "r08_synthetic_posterior_sanity",
        "line_count": LINE_COUNT,
        "sample_lines": SAMPLE_LINES,
        "sample_count": SAMPLE_COUNT,
        "seed": SEED,
        "fields": {},
    }

    for name, truth in fields().items():
        samples = samples_for(truth)
        rows = {}
        for estimator in estimators:
            posterior = reconstruct(
                estimator,
                samples,
                LINE_COUNT,
                sample_lines=SAMPLE_LINES,
            )
            rows[estimator] = metrics(
                posterior["relevance"],
                truth,
            )
        result["fields"][name] = rows
    return result


def markdown(report):
    lines = [
        "# R08 synthetic posterior sanity",
        "",
        "| field | estimator | MAE ↓ | RMSE ↓ | Pearson ↑ |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for field, rows in report["fields"].items():
        for estimator, metrics in rows.items():
            lines.append(
                f"| {field} | {estimator} | "
                f"{metrics['mae']:.4f} | "
                f"{metrics['rmse']:.4f} | "
                f"{metrics['pearson']:.4f} |"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2))
    print()
    print(markdown(report))
