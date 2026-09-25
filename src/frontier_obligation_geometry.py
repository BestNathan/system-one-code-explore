#!/usr/bin/env python3
"""R16: compare deterministic Phase0 -> frontier obligation geometries."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from multi_objective_evidence_acquisition import enrich_action, partition_actions


EPS = 1e-12


def quantile_threshold(values, quantile):
    if not values:
        return 0.0
    ordered = sorted(float(x) for x in values)
    q = min(1.0, max(0.0, float(quantile)))
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]



def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tile_actions(frontier, tile_lines=32):
    return [
        enrich_action(action, frontier)
        for action in partition_actions(
            frontier["line_count"],
            tile_lines,
        )
    ]


def tile_scores(actions):
    return [float(item["phase0_mean_relevance"]) for item in actions]


def merge_index_ranges(ranges):
    if not ranges:
        return []
    ordered = sorted((int(a), int(b)) for a, b in ranges)
    merged = [list(ordered[0])]
    for left, right in ordered[1:]:
        if left <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], right)
        else:
            merged.append([left, right])
    return [tuple(item) for item in merged]


def ranges_to_obligations(ranges, actions, method, metadata=None):
    obligations = []
    for number, (left_index, right_index) in enumerate(
        merge_index_ranges(ranges),
        1,
    ):
        left = actions[left_index]
        right = actions[right_index]
        obligations.append({
            "id": f"{method}_{number:03d}",
            "method": method,
            "range": [
                int(left["start_line"]),
                int(right["end_line"]),
            ],
            "tile_index_range": [
                int(left_index),
                int(right_index),
            ],
            "tile_ids": [
                actions[index]["id"]
                for index in range(left_index, right_index + 1)
            ],
            "metadata": metadata or {},
        })
    return obligations


def qualifying_components(scores, threshold):
    indices = [
        index
        for index, score in enumerate(scores)
        if float(score) >= float(threshold)
    ]
    if not indices:
        return []
    ranges = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index == previous + 1:
            previous = index
            continue
        ranges.append((start, previous))
        start = previous = index
    ranges.append((start, previous))
    return ranges


def quantile_components(actions, quantile, method):
    scores = tile_scores(actions)
    threshold = quantile_threshold(scores, quantile)
    ranges = qualifying_components(scores, threshold)
    return ranges_to_obligations(
        ranges,
        actions,
        method,
        metadata={
            "quantile": float(quantile),
            "threshold": float(threshold),
        },
    )


def smooth(scores, radius):
    radius = max(0, int(radius))
    if radius == 0:
        return list(scores)
    out = []
    for index in range(len(scores)):
        left = max(0, index - radius)
        right = min(len(scores), index + radius + 1)
        values = scores[left:right]
        out.append(sum(values) / len(values))
    return out


def plateau_local_maxima(scores):
    """Return one representative index for each local-maximum plateau."""
    n = len(scores)
    if n == 0:
        return []
    maxima = []
    index = 0
    while index < n:
        start = index
        value = scores[index]
        while (
            index + 1 < n
            and abs(scores[index + 1] - value) <= EPS
        ):
            index += 1
        end = index
        left = scores[start - 1] if start > 0 else -math.inf
        right = scores[end + 1] if end + 1 < n else -math.inf
        if value >= left - EPS and value >= right - EPS:
            maxima.append((start + end) // 2)
        index += 1
    return maxima


def peak_prominence(scores, peak):
    if not scores:
        return 0.0
    peak_value = float(scores[peak])
    global_min = min(float(x) for x in scores)
    global_max = max(float(x) for x in scores)

    if global_max - global_min <= EPS:
        return 0.0

    # Global maxima are defined against the file floor. This keeps one stable
    # obligation even when the highest plateau touches an edge.
    if abs(peak_value - global_max) <= EPS:
        return peak_value - global_min

    left_min = peak_value
    index = peak
    while index > 0:
        index -= 1
        value = float(scores[index])
        left_min = min(left_min, value)
        if value > peak_value + EPS:
            break

    right_min = peak_value
    index = peak
    while index + 1 < len(scores):
        index += 1
        value = float(scores[index])
        right_min = min(right_min, value)
        if value > peak_value + EPS:
            break

    saddle = max(left_min, right_min)
    return max(0.0, peak_value - saddle)


def prominence_candidates(
    scores,
    *,
    relative_prominence=0.10,
):
    if not scores:
        return []
    low = min(scores)
    high = max(scores)
    span = high - low

    if span <= EPS:
        return [{
            "peak_index": len(scores) // 2,
            "peak": float(high),
            "prominence": 0.0,
            "relative_prominence": 1.0,
            "basin": [0, len(scores) - 1],
            "flat_plateau": True,
        }]

    candidates = []
    maxima = plateau_local_maxima(scores)
    global_peak = max(
        range(len(scores)),
        key=lambda index: scores[index],
    )

    for peak in maxima:
        prominence = peak_prominence(scores, peak)
        relative = prominence / span
        if (
            relative + EPS < float(relative_prominence)
            and peak != global_peak
        ):
            continue

        peak_value = float(scores[peak])
        if prominence <= EPS:
            floor = peak_value
        else:
            floor = peak_value - 0.5 * prominence

        left = peak
        while (
            left > 0
            and float(scores[left - 1]) >= floor - EPS
        ):
            left -= 1
        right = peak
        while (
            right + 1 < len(scores)
            and float(scores[right + 1]) >= floor - EPS
        ):
            right += 1

        candidates.append({
            "peak_index": int(peak),
            "peak": peak_value,
            "prominence": float(prominence),
            "relative_prominence": float(relative),
            "basin": [int(left), int(right)],
            "flat_plateau": False,
        })

    if not any(
        item["peak_index"] == global_peak
        for item in candidates
    ):
        prominence = peak_prominence(scores, global_peak)
        candidates.append({
            "peak_index": int(global_peak),
            "peak": float(scores[global_peak]),
            "prominence": float(prominence),
            "relative_prominence": float(
                prominence / span if span else 1.0
            ),
            "basin": [int(global_peak), int(global_peak)],
            "flat_plateau": False,
        })

    return candidates


def local_prominence(actions):
    scores = tile_scores(actions)
    candidates = prominence_candidates(
        scores,
        relative_prominence=0.10,
    )
    ranges = [
        tuple(item["basin"])
        for item in candidates
    ]
    obligations = ranges_to_obligations(
        ranges,
        actions,
        "local_prominence",
    )
    return obligations, {
        "candidate_peaks": candidates,
        "relative_prominence": 0.10,
    }


def cluster_peak_candidates(candidates, distance=2):
    clusters = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item["peak_index"],
            item["scale_radius"],
        ),
    ):
        matches = [
            cluster
            for cluster in clusters
            if min(
                abs(
                    candidate["peak_index"]
                    - item["peak_index"]
                )
                for item in cluster
            ) <= int(distance)
        ]
        if not matches:
            clusters.append([candidate])
            continue
        target = matches[0]
        target.append(candidate)
        # If one candidate bridges two nearby clusters, merge them.
        for other in matches[1:]:
            target.extend(other)
            clusters.remove(other)
    return clusters


def multiscale_prominence(actions):
    raw_scores = tile_scores(actions)
    all_candidates = []
    radii = [0, 1, 2, 4]

    for radius in radii:
        smoothed = smooth(raw_scores, radius)
        for candidate in prominence_candidates(
            smoothed,
            relative_prominence=0.10,
        ):
            all_candidates.append({
                **candidate,
                "scale_radius": radius,
            })

    clusters = cluster_peak_candidates(
        all_candidates,
        distance=2,
    )

    if raw_scores:
        global_peak = max(
            range(len(raw_scores)),
            key=lambda index: raw_scores[index],
        )
    else:
        global_peak = None

    retained_clusters = []
    ranges = []
    for cluster in clusters:
        scales = sorted(
            set(item["scale_radius"] for item in cluster)
        )
        contains_global = (
            global_peak is not None
            and any(
                abs(item["peak_index"] - global_peak) <= 2
                for item in cluster
            )
        )
        if len(scales) < 2 and not contains_global:
            continue

        left = min(item["basin"][0] for item in cluster)
        right = max(item["basin"][1] for item in cluster)
        representative = max(
            cluster,
            key=lambda item: (
                item["prominence"],
                item["peak"],
            ),
        )
        retained_clusters.append({
            "scales": scales,
            "peak_index": representative["peak_index"],
            "peak": representative["peak"],
            "max_relative_prominence": max(
                item["relative_prominence"]
                for item in cluster
            ),
            "basin": [left, right],
        })
        ranges.append((left, right))

    obligations = ranges_to_obligations(
        ranges,
        actions,
        "multiscale_prominence",
    )
    return obligations, {
        "radii": radii,
        "cluster_distance": 2,
        "minimum_scale_persistence": 2,
        "clusters": retained_clusters,
    }


def mass_diverse(actions):
    scores = tile_scores(actions)
    if not scores:
        return [], {}
    low = min(scores)
    weights = [
        max(0.0, float(score) - float(low))
        for score in scores
    ]
    total = sum(weights)

    if total <= EPS:
        obligations = ranges_to_obligations(
            [(0, len(actions) - 1)],
            actions,
            "mass_diverse",
        )
        return obligations, {
            "mass_target": 0.70,
            "radius": 2,
            "representative_cap": 1,
            "representatives": [len(actions) // 2],
            "flat_plateau": True,
        }

    radius = 2
    target = 0.70
    cap = max(1, math.ceil(math.log2(len(actions) + 1)))
    represented = set()
    represented_mass = 0.0
    representatives = []
    ranges = []

    while (
        represented_mass / total < target - EPS
        and len(representatives) < cap
    ):
        candidates = [
            index
            for index in range(len(actions))
            if index not in represented
        ]
        if not candidates:
            break

        def candidate_key(index):
            if not representatives:
                distance = len(actions)
            else:
                distance = min(
                    abs(index - other)
                    for other in representatives
                )
            novelty = min(1.0, distance / max(1, radius))
            normalized = (
                weights[index] / max(weights)
                if max(weights) > EPS else 0.0
            )
            return (
                normalized * (0.5 + 0.5 * novelty),
                weights[index],
                distance,
                -index,
            )

        seed = max(candidates, key=candidate_key)
        representatives.append(seed)
        left = max(0, seed - radius)
        right = min(len(actions) - 1, seed + radius)
        ranges.append((left, right))

        for index in range(left, right + 1):
            if index not in represented:
                represented.add(index)
                represented_mass += weights[index]

    obligations = ranges_to_obligations(
        ranges,
        actions,
        "mass_diverse",
    )
    return obligations, {
        "mass_target": target,
        "radius": radius,
        "representative_cap": cap,
        "representatives": representatives,
        "represented_mass_fraction": (
            represented_mass / total if total else 1.0
        ),
        "flat_plateau": False,
    }



def ranges_overlap(a, b):
    return not (int(a[1]) < int(b[0]) or int(b[1]) < int(a[0]))


def q75_plus_secondary_peaks(
    actions,
    q75_obligations,
    candidates,
    *,
    method,
):
    scores = tile_scores(actions)
    median = quantile_threshold(scores, 0.50)
    q75_ranges = [
        tuple(item["tile_index_range"])
        for item in q75_obligations
    ]
    ranges = list(q75_ranges)
    added = []

    for candidate in candidates:
        peak = int(candidate["peak_index"])
        basin = tuple(candidate["basin"])
        if any(
            ranges_overlap(basin, q75_range)
            for q75_range in q75_ranges
        ):
            continue
        if float(scores[peak]) + EPS < float(median):
            continue
        ranges.append((peak, peak))
        added.append({
            "peak_index": peak,
            "peak": float(scores[peak]),
            "basin": [int(basin[0]), int(basin[1])],
        })

    obligations = ranges_to_obligations(
        ranges,
        actions,
        method,
        metadata={
            "base": "q75_components",
            "secondary_width_tiles": 1,
            "secondary_minimum_rank": "q50",
        },
    )
    return obligations, {
        "median_threshold": float(median),
        "added_secondary_peaks": added,
        "secondary_count": len(added),
    }



def representative_order(actions, indexes):
    indexes = [int(index) for index in indexes]
    center = (min(indexes) + max(indexes)) / 2.0
    return [
        actions[index]["id"]
        for index in sorted(
            indexes,
            key=lambda index: (
                -float(actions[index]["phase0_mean_relevance"]),
                abs(index - center),
                index,
            ),
        )
    ]


def build_r15_hybrid_obligations(frontier, *, tile_lines=32):
    """Build R15-compatible q75 + narrow persistent multiscale obligations."""
    actions = tile_actions(frontier, tile_lines=tile_lines)
    scores = tile_scores(actions)
    q75_threshold = quantile_threshold(scores, 0.75)
    q75 = quantile_components(
        actions,
        0.75,
        "q75_components",
    )
    _, multiscale_meta = multiscale_prominence(actions)
    _, hybrid_meta = q75_plus_secondary_peaks(
        actions,
        q75,
        multiscale_meta["clusters"],
        method="q75_plus_multiscale_seed",
    )

    specs = []
    for base in q75:
        left_index, right_index = base["tile_index_range"]
        indexes = list(range(left_index, right_index + 1))
        specs.append({
            "range": list(base["range"]),
            "tile_ids": [actions[i]["id"] for i in indexes],
            "representative_candidates": representative_order(
                actions,
                indexes,
            ),
            "kind": "primary_q75",
        })

    for secondary in hybrid_meta["added_secondary_peaks"]:
        index = int(secondary["peak_index"])
        action = actions[index]
        specs.append({
            "range": [
                int(action["start_line"]),
                int(action["end_line"]),
            ],
            "tile_ids": [action["id"]],
            "representative_candidates": [action["id"]],
            "kind": "secondary_multiscale_peak",
            "secondary_peak": secondary,
        })

    specs.sort(key=lambda item: (item["range"][0], item["range"][1]))
    obligations = []
    for number, spec in enumerate(specs, 1):
        tile_indexes = [
            int(tile_id.split("_")[-1]) - 1
            for tile_id in spec["tile_ids"]
        ]
        values = [scores[index] for index in tile_indexes]
        obligation = {
            "id": f"obligation_{number:03d}",
            "range": list(spec["range"]),
            "tile_ids": list(spec["tile_ids"]),
            "representative_candidates": list(
                spec["representative_candidates"]
            ),
            "attempted_seed_ids": [],
            "anchor_ids": [],
            "status": "unresolved",
            "frontier_threshold": float(q75_threshold),
            "frontier_peak": max(values),
            "frontier_mean": sum(values) / len(values),
            "geometry_kind": spec["kind"],
        }
        if "secondary_peak" in spec:
            obligation["secondary_peak"] = spec["secondary_peak"]
        obligations.append(obligation)

    return actions, obligations, {
        "geometry": "q75_plus_multiscale_seed",
        "q75_threshold": float(q75_threshold),
        "q75_obligation_count": len(q75),
        "secondary_obligation_count": len(
            hybrid_meta["added_secondary_peaks"]
        ),
        "median_threshold": hybrid_meta["median_threshold"],
        "multiscale": {
            "radii": multiscale_meta["radii"],
            "cluster_distance": multiscale_meta["cluster_distance"],
            "minimum_scale_persistence": multiscale_meta[
                "minimum_scale_persistence"
            ],
        },
    }


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


def high_regions(field, threshold=0.70):
    regions = []
    start = None
    for index, value in enumerate(field, 1):
        is_high = float(value) >= float(threshold)
        if is_high and start is None:
            start = index
        elif not is_high and start is not None:
            regions.append([start, index - 1])
            start = None
    if start is not None:
        regions.append([start, len(field)])
    return regions


def obligation_union(obligations):
    lines = set()
    for obligation in obligations:
        left, right = obligation["range"]
        lines.update(range(int(left), int(right) + 1))
    return lines


def evaluate_geometry(reference, obligations):
    field = reference_field(reference)
    n = len(field)
    high = {
        index + 1
        for index, value in enumerate(field)
        if float(value) >= 0.70
    }
    regions = high_regions(field, threshold=0.70)
    covered = obligation_union(obligations)

    region_hits = 0
    for left, right in regions:
        if any(line in covered for line in range(left, right + 1)):
            region_hits += 1

    precise = 0
    per_obligation = []
    for obligation in obligations:
        left, right = obligation["range"]
        lines = range(int(left), int(right) + 1)
        values = [field[line - 1] for line in lines]
        overlaps_high = any(line in high for line in lines)
        precise += int(overlaps_high)
        per_obligation.append({
            "id": obligation["id"],
            "range": obligation["range"],
            "hidden_mean_relevance": (
                sum(values) / len(values) if values else 0.0
            ),
            "hidden_max_relevance": (
                max(values) if values else 0.0
            ),
            "overlaps_hidden_high": overlaps_high,
        })

    covered_high = len(covered & high)
    covered_mass = sum(field[line - 1] for line in covered)

    return {
        "obligation_count": len(obligations),
        "source_coverage": len(covered) / n if n else 0.0,
        "hidden_high_region_recall": (
            region_hits / len(regions) if regions else 0.0
        ),
        "hidden_high_line_coverage": (
            covered_high / len(high) if high else 0.0
        ),
        "obligation_precision": (
            precise / len(obligations) if obligations else 0.0
        ),
        "mean_hidden_relevance": (
            covered_mass / len(covered) if covered else 0.0
        ),
        "hidden_high_region_count": len(regions),
        "per_obligation": per_obligation,
    }


def compare(reference, phase0_run, tile_lines=32):
    actions = tile_actions(
        phase0_run["frontier"],
        tile_lines=tile_lines,
    )

    q75 = quantile_components(
        actions,
        0.75,
        "q75_components",
    )
    q60 = quantile_components(
        actions,
        0.60,
        "q60_components",
    )
    local, local_meta = local_prominence(actions)
    multiscale, multiscale_meta = multiscale_prominence(actions)
    mass, mass_meta = mass_diverse(actions)
    hybrid_local, hybrid_local_meta = q75_plus_secondary_peaks(
        actions,
        q75,
        local_meta["candidate_peaks"],
        method="q75_plus_local_seed",
    )
    hybrid_multiscale, hybrid_multiscale_meta = q75_plus_secondary_peaks(
        actions,
        q75,
        multiscale_meta["clusters"],
        method="q75_plus_multiscale_seed",
    )

    methods = {
        "q75_components": {
            "obligations": q75,
            "metadata": {
                "quantile": 0.75,
            },
        },
        "q60_components": {
            "obligations": q60,
            "metadata": {
                "quantile": 0.60,
            },
        },
        "local_prominence": {
            "obligations": local,
            "metadata": local_meta,
        },
        "multiscale_prominence": {
            "obligations": multiscale,
            "metadata": multiscale_meta,
        },
        "mass_diverse": {
            "obligations": mass,
            "metadata": mass_meta,
        },
        "q75_plus_local_seed": {
            "obligations": hybrid_local,
            "metadata": hybrid_local_meta,
        },
        "q75_plus_multiscale_seed": {
            "obligations": hybrid_multiscale,
            "metadata": hybrid_multiscale_meta,
        },
    }

    for method in methods.values():
        method["metrics"] = evaluate_geometry(
            reference,
            method["obligations"],
        )

    return {
        "schema_version": 1,
        "kind": "r16-frontier-obligation-geometry-comparison",
        "subject": phase0_run.get("subject"),
        "posterior_estimator": phase0_run.get(
            "posterior_estimator"
        ),
        "tile_lines": int(tile_lines),
        "methods": methods,
    }


def markdown(result):
    lines = [
        "# R16 frontier obligation geometry",
        "",
        (
            "- estimator: "
            f"{result.get('posterior_estimator')}"
        ),
        "",
        "| method | obligations | source | high-region recall | high-line coverage | obligation precision | hidden relevance |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in result["methods"].items():
        m = item["metrics"]
        lines.append(
            f"| {name} | "
            f"{m['obligation_count']} | "
            f"{m['source_coverage']:.4f} | "
            f"{m['hidden_high_region_recall']:.4f} | "
            f"{m['hidden_high_line_coverage']:.4f} | "
            f"{m['obligation_precision']:.4f} | "
            f"{m['mean_hidden_relevance']:.4f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--phase0-run", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    parser.add_argument("--tile-lines", type=int, default=32)
    args = parser.parse_args(argv)

    result = compare(
        load(args.reference),
        load(args.phase0_run),
        tile_lines=args.tile_lines,
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        markdown(result),
        encoding="utf-8",
    )
    print(json.dumps({
        name: item["metrics"]
        for name, item in result["methods"].items()
    }, indent=2))


if __name__ == "__main__":
    main()
