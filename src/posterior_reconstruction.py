#!/usr/bin/env python3
"""Path-independent posterior estimators for sparse relevance observations.

These estimators intentionally consume only probe geometry and local System One
scores. They do not inspect source text or the System 2 reference field.
"""
from __future__ import annotations

import math


DEFAULT_PRIOR = 0.5
DEFAULT_PRIOR_WEIGHT = 0.25


def sample_center(sample):
    return (float(sample["start_line"]) + float(sample["end_line"])) / 2.0


def _clamp(value, low, high):
    return max(low, min(high, value))


def sequential_exponential(
    samples,
    line_count,
    *,
    prior=DEFAULT_PRIOR,
    decay_lines=48.0,
):
    """Replay the v5 sequential exponential updater.

    This is the historical baseline. It is path dependent because each new
    observation updates the already-updated field.
    """
    n = int(line_count)
    relevance = [float(prior)] * n
    uncertainty = [1.0] * n

    for sample in samples:
        left = max(1, int(sample["start_line"]))
        right = min(n, int(sample["end_line"]))
        score = _clamp(float(sample["score"]), 0.0, 1.0)

        for line in range(1, n + 1):
            if left <= line <= right:
                influence = 1.0
            else:
                distance = left - line if line < left else line - right
                influence = math.exp(-distance / max(1.0, float(decay_lines)))
                if influence < 0.02:
                    continue

            idx = line - 1
            old_u = uncertainty[idx]
            old_p = relevance[idx]
            prior_weight = max(0.05, old_u)
            relevance[idx] = (
                old_p * prior_weight + score * influence
            ) / (prior_weight + influence)
            uncertainty[idx] = max(
                0.03 if influence >= 1.0 else 0.15,
                old_u * (1.0 - 0.72 * influence),
            )

    return {
        "name": "sequential_exponential",
        "relevance": relevance,
        "uncertainty": uncertainty,
    }


def adaptive_gaussian(
    samples,
    line_count,
    *,
    sample_lines=8,
    kth_neighbor=3,
    prior=DEFAULT_PRIOR,
    prior_weight=DEFAULT_PRIOR_WEIGHT,
):
    """Recompute the entire field from all observations.

    The bandwidth at each source line is derived only from observation
    geometry: distance to the k-th nearest sample center, clamped between four
    probe widths and one twelfth of the file length.

    This makes the estimator path independent and lets sparse areas use a wider
    kernel than densely observed areas.
    """
    n = int(line_count)
    rows = [
        (sample_center(item), _clamp(float(item["score"]), 0.0, 1.0))
        for item in samples
    ]
    if not rows:
        return {
            "name": f"adaptive_gaussian_k{kth_neighbor}",
            "relevance": [float(prior)] * n,
            "uncertainty": [1.0] * n,
        }

    min_bandwidth = max(1.0, float(sample_lines) * 4.0)
    max_bandwidth = max(min_bandwidth, float(n) / 12.0)
    kth = max(1, int(kth_neighbor))

    relevance = []
    uncertainty = []
    for line in range(1, n + 1):
        distances = sorted(abs(float(line) - center) for center, _ in rows)
        neighbor_distance = distances[min(kth - 1, len(distances) - 1)]
        bandwidth = _clamp(
            neighbor_distance,
            min_bandwidth,
            max_bandwidth,
        )

        support = 0.0
        numerator = float(prior) * float(prior_weight)
        for center, score in rows:
            z = (float(line) - center) / bandwidth
            weight = math.exp(-0.5 * z * z)
            support += weight
            numerator += weight * score

        denominator = float(prior_weight) + support
        relevance.append(numerator / denominator)
        uncertainty.append(
            float(prior_weight) / denominator
            if denominator > 0.0
            else 1.0
        )

    return {
        "name": f"adaptive_gaussian_k{kth}",
        "relevance": relevance,
        "uncertainty": uncertainty,
    }


def multi_scale_gaussian(
    samples,
    line_count,
    *,
    sample_lines=8,
    prior=DEFAULT_PRIOR,
    prior_weight=DEFAULT_PRIOR_WEIGHT,
):
    """Blend a local (k=2) and broad (k=4) geometry-adaptive posterior.

    The blend is deterministic and reference-free. The local field receives
    twice the confidence weight so sharp observed structure is retained while
    the broad field supplies context in sparse areas.
    """
    local = adaptive_gaussian(
        samples,
        line_count,
        sample_lines=sample_lines,
        kth_neighbor=2,
        prior=prior,
        prior_weight=prior_weight,
    )
    broad = adaptive_gaussian(
        samples,
        line_count,
        sample_lines=sample_lines,
        kth_neighbor=4,
        prior=prior,
        prior_weight=prior_weight,
    )

    relevance = []
    uncertainty = []
    for local_p, local_u, broad_p, broad_u in zip(
        local["relevance"],
        local["uncertainty"],
        broad["relevance"],
        broad["uncertainty"],
    ):
        local_confidence = 1.0 - local_u
        broad_confidence = 1.0 - broad_u
        local_weight = 2.0 * local_confidence
        broad_weight = broad_confidence
        total = local_weight + broad_weight

        relevance.append(
            (
                local_weight * local_p + broad_weight * broad_p
            ) / total
            if total > 0.0
            else float(prior)
        )
        uncertainty.append((local_u + broad_u) / 2.0)

    return {
        "name": "multi_scale_gaussian_k2_k4",
        "relevance": relevance,
        "uncertainty": uncertainty,
    }


def reconstruct(
    estimator,
    samples,
    line_count,
    *,
    sample_lines=8,
):
    if estimator == "sequential_exponential":
        return sequential_exponential(samples, line_count)
    if estimator == "adaptive_gaussian_k2":
        return adaptive_gaussian(
            samples,
            line_count,
            sample_lines=sample_lines,
            kth_neighbor=2,
        )
    if estimator == "adaptive_gaussian_k3":
        return adaptive_gaussian(
            samples,
            line_count,
            sample_lines=sample_lines,
            kth_neighbor=3,
        )
    if estimator == "adaptive_gaussian_k4":
        return adaptive_gaussian(
            samples,
            line_count,
            sample_lines=sample_lines,
            kth_neighbor=4,
        )
    if estimator == "multi_scale_gaussian":
        return multi_scale_gaussian(
            samples,
            line_count,
            sample_lines=sample_lines,
        )
    raise ValueError(f"unknown posterior estimator: {estimator}")


ESTIMATORS = (
    "sequential_exponential",
    "adaptive_gaussian_k2",
    "adaptive_gaussian_k3",
    "adaptive_gaussian_k4",
    "multi_scale_gaussian",
)
