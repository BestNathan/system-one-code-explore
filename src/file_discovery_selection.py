"""Stable post-scoring selection policies for candidate-shaped discovery."""
from __future__ import annotations

import math


def select_relevant(
    file_scores,
    *,
    enumerated_file_count,
    file_threshold=0.65,
    relative_fallback_fraction=0.01,
):
    ordered = sorted(file_scores, key=lambda path: (-float(file_scores[path]), path))
    population = max(0, int(enumerated_file_count))
    fraction = max(0.0, float(relative_fallback_fraction))
    requested = max(1, math.ceil(population * fraction)) if ordered and fraction else 0
    protected = min(len(ordered), requested)
    cutoff = float(file_scores[ordered[protected - 1]]) if protected else None
    selected = []
    for path in ordered:
        score = float(file_scores[path])
        reasons = []
        if score >= float(file_threshold):
            reasons.append("absolute_threshold")
        if cutoff is not None and score >= cutoff:
            reasons.append("repository_population_relative_guard")
        if reasons:
            selected.append({"path": path, "score": score, "selection_reasons": reasons})
    return selected, {
        "file_threshold": float(file_threshold),
        "relative_fallback_fraction": fraction,
        "relative_fallback_population": population,
        "relative_fallback_min_count": requested,
        "relative_fallback_scored_count": protected,
        "relative_fallback_cutoff": cutoff,
    }
