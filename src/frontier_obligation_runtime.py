#!/usr/bin/env python3
"""R15: deterministic frontier obligations + directional semantic closure.

Coverage is a Harness invariant derived from Phase0 geometry. System One is
used only for:
- directional closure of one anchor-specific local semantic unit;
- final utility after that unit is directionally closed.

The runtime has no global Stop prediction and no scalar completeness gate.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from system_one_code_locator import (
    Trace,
    empty_usage,
    merge_usage,
    sanitize_source,
)
from system_one_relevance_frontier import (
    ClosureChoiceRelevanceFrontierDecider,
)
from multi_objective_evidence_acquisition import (
    enrich_action,
    partition_actions,
    read_tile,
)


DEFAULT_TILE_LINES = 32
DEFAULT_FRONTIER_QUANTILE = 0.75
DEFAULT_EXPANSION_THRESHOLD = 0.60
DEFAULT_FINAL_UTILITY_THRESHOLD = 0.65
DEFAULT_MAX_ANCHOR_TILES = 12


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def quantile_threshold(values, quantile):
    if not values:
        return 0.0
    ordered = sorted(float(x) for x in values)
    q = min(1.0, max(0.0, float(quantile)))
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def tile_score(action):
    return float(action["phase0_mean_relevance"])


def candidate_order(component):
    """High score first; ties prefer a representative near component center."""
    indices = [int(item["_index"]) for item in component]
    center = (min(indices) + max(indices)) / 2.0
    return [
        item["id"]
        for item in sorted(
            component,
            key=lambda item: (
                -tile_score(item),
                abs(int(item["_index"]) - center),
                int(item["_index"]),
            ),
        )
    ]


def build_frontier_obligations(
    frontier,
    *,
    tile_lines=DEFAULT_TILE_LINES,
    quantile=DEFAULT_FRONTIER_QUANTILE,
):
    actions = [
        enrich_action(action, frontier)
        for action in partition_actions(
            frontier["line_count"],
            tile_lines,
        )
    ]
    for index, action in enumerate(actions):
        action["_index"] = index

    scores = [tile_score(action) for action in actions]
    threshold = quantile_threshold(scores, quantile)
    qualifying = [
        action
        for action in actions
        if tile_score(action) >= threshold
    ]

    # A quantile always includes at least one tile, but keep a defensive
    # fallback for malformed/non-finite input.
    if not qualifying and actions:
        qualifying = [
            max(actions, key=tile_score)
        ]
        threshold = tile_score(qualifying[0])

    components = []
    current = []
    previous_index = None
    for action in qualifying:
        index = int(action["_index"])
        if previous_index is None or index == previous_index + 1:
            current.append(action)
        else:
            components.append(current)
            current = [action]
        previous_index = index
    if current:
        components.append(current)

    obligations = []
    for number, component in enumerate(components, 1):
        left = min(int(item["start_line"]) for item in component)
        right = max(int(item["end_line"]) for item in component)
        obligations.append({
            "id": f"obligation_{number:03d}",
            "range": [left, right],
            "tile_ids": [item["id"] for item in component],
            "representative_candidates": candidate_order(component),
            "attempted_seed_ids": [],
            "anchor_ids": [],
            "status": "unresolved",
            "frontier_threshold": threshold,
            "frontier_peak": max(tile_score(item) for item in component),
            "frontier_mean": (
                sum(tile_score(item) for item in component)
                / len(component)
            ),
        })

    for action in actions:
        action.pop("_index", None)

    return actions, obligations, {
        "quantile": float(quantile),
        "threshold": float(threshold),
        "tile_count": len(actions),
        "qualifying_tile_count": len(qualifying),
        "obligation_count": len(obligations),
    }


def anchor_range(anchor, actions_by_id):
    tiles = [
        actions_by_id[tile_id]
        for tile_id in anchor["tile_ids"]
    ]
    return (
        min(int(item["start_line"]) for item in tiles),
        max(int(item["end_line"]) for item in tiles),
    )


def anchor_source(anchor, actions_by_id, source_lines):
    left, right = anchor_range(anchor, actions_by_id)
    return "\n".join(
        f"{line}: {source_lines[line - 1]}"
        for line in range(left, right + 1)
    )


def adjacent_ids(anchor, ordered_ids):
    positions = {
        action_id: index
        for index, action_id in enumerate(ordered_ids)
    }
    indices = sorted(
        positions[tile_id]
        for tile_id in anchor["tile_ids"]
    )
    before_id = (
        ordered_ids[indices[0] - 1]
        if indices[0] > 0 else None
    )
    after_id = (
        ordered_ids[indices[-1] + 1]
        if indices[-1] + 1 < len(ordered_ids)
        else None
    )
    return before_id, after_id


def merge_retained_anchor_ranges(retained, actions_by_id):
    ranges = []
    for anchor in retained:
        left, right = anchor_range(anchor, actions_by_id)
        ranges.append({
            "start_line": left,
            "end_line": right,
            "anchor_ids": [anchor["id"]],
            "obligation_ids": [anchor["obligation_id"]],
        })
    ranges.sort(key=lambda item: (item["start_line"], item["end_line"]))

    merged = []
    for item in ranges:
        if (
            not merged
            or item["start_line"] > merged[-1]["end_line"] + 1
        ):
            merged.append(dict(item))
            continue
        merged[-1]["end_line"] = max(
            merged[-1]["end_line"],
            item["end_line"],
        )
        merged[-1]["anchor_ids"].extend(item["anchor_ids"])
        merged[-1]["obligation_ids"].extend(item["obligation_ids"])
    return merged


class FrontierObligationDecider(
    ClosureChoiceRelevanceFrontierDecider
):
    def assess_directional_closure(
        self,
        goal,
        path,
        anchor,
        actions_by_id,
        ordered_ids,
        source_lines,
    ):
        left, right = anchor_range(anchor, actions_by_id)
        before_id, after_id = adjacent_ids(anchor, ordered_ids)
        source = sanitize_source(
            anchor_source(anchor, actions_by_id, source_lines)
        )

        common = {
            "goal": goal,
            "file": path,
            "frontier_obligation": anchor["obligation_range"],
            "anchor_seed_range": anchor["seed_range"],
            "current_anchor_range": [left, right],
            "source": source,
            "important": (
                "Judge only the SAME local semantic unit intersected by the "
                "anchor seed. Do not expand to discover a different related "
                "function or another task-relevant construct."
            ),
        }
        questions = {}
        if before_id is not None:
            before = actions_by_id[before_id]
            questions["need_before"] = {
                "type": "noul",
                "instructions": {
                    **common,
                    "candidate_adjacent_range": [
                        before["start_line"],
                        before["end_line"],
                    ],
                    "question": (
                        "How likely is the immediately preceding tile required "
                        "to recover the beginning, setup, enclosing branch, "
                        "function header, or other context necessary to "
                        "understand THIS SAME local semantic unit?"
                    ),
                },
                "criteria": {
                    "true": (
                        "The preceding tile is likely required to close this "
                        "anchor-specific local construct."
                    ),
                    "false": (
                        "The currently visible local construct is understandable "
                        "without the preceding tile."
                    ),
                },
            }
        if after_id is not None:
            after = actions_by_id[after_id]
            questions["need_after"] = {
                "type": "noul",
                "instructions": {
                    **common,
                    "candidate_adjacent_range": [
                        after["start_line"],
                        after["end_line"],
                    ],
                    "question": (
                        "How likely is the immediately following tile required "
                        "to see the continuation, body, branch outcome, state "
                        "transition, error path, or follow-up necessary to "
                        "understand THIS SAME local semantic unit?"
                    ),
                },
                "criteria": {
                    "true": (
                        "The following tile is likely required to close this "
                        "anchor-specific local construct."
                    ),
                    "false": (
                        "The currently visible local construct is understandable "
                        "without the following tile."
                    ),
                },
            }

        if not questions:
            return {
                "before": {
                    "tile_id": None,
                    "probability": 0.0,
                },
                "after": {
                    "tile_id": None,
                    "probability": 0.0,
                },
            }, empty_usage()

        response, usage = self.send(
            "r15_directional_semantic_closure",
            {
                "goal": goal,
                "phase": "r15_directional_closure",
                "file": path,
                "obligation_id": anchor["obligation_id"],
                "anchor_id": anchor["id"],
            },
            questions,
        )
        answers = response.get("answers", {})

        def parse(name, tile_id):
            if tile_id is None:
                return {
                    "tile_id": None,
                    "probability": 0.0,
                }
            answer = answers.get(name, {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected R15 directional answer {name}: {answer!r}"
                )
            return {
                "tile_id": tile_id,
                "probability": float(answer["noul"]),
            }

        return {
            "before": parse("need_before", before_id),
            "after": parse("need_after", after_id),
        }, usage

    def assess_final_utility(
        self,
        goal,
        path,
        anchor,
        actions_by_id,
        source_lines,
    ):
        left, right = anchor_range(anchor, actions_by_id)
        source = sanitize_source(
            anchor_source(anchor, actions_by_id, source_lines)
        )
        response, usage = self.send(
            "r15_post_closure_utility",
            {
                "goal": goal,
                "phase": "r15_post_closure_utility",
                "file": path,
                "obligation_id": anchor["obligation_id"],
                "anchor_id": anchor["id"],
            },
            {
                "utility": {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "file": path,
                        "frontier_obligation": anchor[
                            "obligation_range"
                        ],
                        "anchor_seed_range": anchor["seed_range"],
                        "closed_anchor_range": [left, right],
                        "source": source,
                        "question": (
                            "The anchor-specific local semantic unit has now "
                            "finished directional closure: neither immediate "
                            "side is currently judged necessary. How likely does "
                            "this CLOSED local unit contain material evidence "
                            "needed to solve the user's goal?"
                        ),
                    },
                    "criteria": {
                        "true": (
                            "This closed local unit contains distinct material "
                            "implementation, control-flow, state, contract, "
                            "dependency, edge-case, or constraint evidence."
                        ),
                        "false": (
                            "This closed local unit is incidental, redundant, "
                            "or not materially useful for the goal."
                        ),
                    },
                }
            },
        )
        answer = response.get("answers", {}).get("utility", {})
        if answer.get("type") != "noul":
            raise RuntimeError(
                f"unexpected R15 final utility answer: {answer!r}"
            )
        return float(answer["noul"]), usage


def run(
    source,
    goal,
    phase0_run,
    decider,
    *,
    tile_lines=DEFAULT_TILE_LINES,
    frontier_quantile=DEFAULT_FRONTIER_QUANTILE,
    expansion_threshold=DEFAULT_EXPANSION_THRESHOLD,
    final_utility_threshold=DEFAULT_FINAL_UTILITY_THRESHOLD,
    max_anchor_tiles=DEFAULT_MAX_ANCHOR_TILES,
):
    source_lines = Path(source).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    frontier = phase0_run["frontier"]
    if len(source_lines) != int(frontier["line_count"]):
        raise ValueError("source/frontier line mismatch")

    actions, obligations, geometry = build_frontier_obligations(
        frontier,
        tile_lines=tile_lines,
        quantile=frontier_quantile,
    )
    actions_by_id = {item["id"]: item for item in actions}
    ordered_ids = [item["id"] for item in actions]

    materialized = {}
    anchors = []
    usage = empty_usage()
    anchor_counter = 0

    def materialize(tile_id, reason):
        if tile_id not in materialized:
            materialized[tile_id] = read_tile(
                source_lines,
                actions_by_id[tile_id],
                reason=reason,
                round_number=0,
            )

    for obligation in obligations:
        for seed_id in obligation["representative_candidates"]:
            if obligation["status"] != "unresolved":
                break

            obligation["attempted_seed_ids"].append(seed_id)
            materialize(
                seed_id,
                f"r15_seed:{obligation['id']}",
            )
            action = actions_by_id[seed_id]
            anchor_counter += 1
            anchor = {
                "id": f"anchor_{anchor_counter:03d}",
                "obligation_id": obligation["id"],
                "obligation_range": list(obligation["range"]),
                "seed_tile_id": seed_id,
                "seed_range": [
                    action["start_line"],
                    action["end_line"],
                ],
                "tile_ids": [seed_id],
                "status": "closing",
                "closure_steps": [],
                "final_utility_probability": None,
            }
            anchors.append(anchor)
            obligation["anchor_ids"].append(anchor["id"])

            while anchor["status"] == "closing":
                directional, current = (
                    decider.assess_directional_closure(
                        goal,
                        phase0_run["subject"]["path"],
                        anchor,
                        actions_by_id,
                        ordered_ids,
                        source_lines,
                    )
                )
                merge_usage(usage, current)

                requests = [
                    ("before", directional["before"]),
                    ("after", directional["after"]),
                ]
                selected = [
                    (side, item)
                    for side, item in requests
                    if (
                        item["tile_id"] is not None
                        and float(item["probability"])
                        >= float(expansion_threshold)
                    )
                ]

                step = {
                    "range_before": list(
                        anchor_range(anchor, actions_by_id)
                    ),
                    "need_before": directional["before"],
                    "need_after": directional["after"],
                    "expanded": [],
                }

                if not selected:
                    anchor["status"] = "directionally_closed"
                    step["range_after"] = step["range_before"]
                    anchor["closure_steps"].append(step)
                    break

                available_slots = (
                    int(max_anchor_tiles) - len(anchor["tile_ids"])
                )
                if available_slots <= 0:
                    anchor["status"] = "closure_safety_cap"
                    step["range_after"] = step["range_before"]
                    anchor["closure_steps"].append(step)
                    break

                selected.sort(
                    key=lambda pair: (
                        -float(pair[1]["probability"]),
                        0 if pair[0] == "before" else 1,
                    )
                )
                selected = selected[:available_slots]

                for side, item in selected:
                    tile_id = item["tile_id"]
                    materialize(
                        tile_id,
                        f"r15_closure_{side}:{anchor['id']}",
                    )
                    if tile_id not in anchor["tile_ids"]:
                        anchor["tile_ids"].append(tile_id)
                        anchor["tile_ids"].sort(
                            key=ordered_ids.index
                        )
                    step["expanded"].append({
                        "side": side,
                        "tile_id": tile_id,
                        "probability": float(item["probability"]),
                    })

                step["range_after"] = list(
                    anchor_range(anchor, actions_by_id)
                )
                anchor["closure_steps"].append(step)

                if len(anchor["tile_ids"]) >= int(max_anchor_tiles):
                    # Reassess once at the cap on the next loop; if either
                    # direction is still needed the anchor becomes capped.
                    continue

            if anchor["status"] == "closure_safety_cap":
                continue

            utility, current = decider.assess_final_utility(
                goal,
                phase0_run["subject"]["path"],
                anchor,
                actions_by_id,
                source_lines,
            )
            merge_usage(usage, current)
            anchor["final_utility_probability"] = utility

            if utility >= float(final_utility_threshold):
                anchor["status"] = "retained"
                obligation["status"] = "satisfied"
                obligation["satisfying_anchor_id"] = anchor["id"]
            else:
                anchor["status"] = "rejected_low_utility"

        if obligation["status"] == "unresolved":
            obligation["status"] = "exhausted"

    retained = [
        anchor
        for anchor in anchors
        if anchor["status"] == "retained"
    ]
    termination = (
        "all_obligations_resolved"
        if all(
            item["status"] in {"satisfied", "exhausted"}
            for item in obligations
        )
        else "invariant_violation"
    )

    return {
        "schema_version": 1,
        "kind": "r15-frontier-obligations-directional-closure",
        "goal": goal,
        "subject": phase0_run.get("subject"),
        "phase0_source": {
            "posterior_estimator": phase0_run.get(
                "posterior_estimator"
            ),
            "probes": phase0_run.get("probes"),
        },
        "policy": {
            "tile_lines": int(tile_lines),
            "frontier_quantile": float(frontier_quantile),
            "expansion_threshold": float(expansion_threshold),
            "final_utility_threshold": float(
                final_utility_threshold
            ),
            "max_anchor_tiles_safety": int(max_anchor_tiles),
            "closure_rule": (
                "closed iff need_before and need_after are both below "
                "expansion threshold"
            ),
            "utility_timing": "after_directional_closure_only",
        },
        "frontier_geometry": geometry,
        "termination": termination,
        "obligations": obligations,
        "anchors": anchors,
        "retained_anchor_ids": [
            item["id"] for item in retained
        ],
        "materialized_count": len(materialized),
        "materialized_lines": sum(
            int(item["end_line"]) - int(item["start_line"]) + 1
            for item in materialized.values()
        ),
        "materialized_evidence": [
            materialized[action_id]
            for action_id in ordered_ids
            if action_id in materialized
        ],
        "final_regions": merge_retained_anchor_ranges(
            retained,
            actions_by_id,
        ),
        "usage": usage,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--phase0-run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trace-file")
    parser.add_argument("--tile-lines", type=int, default=32)
    parser.add_argument(
        "--frontier-quantile",
        type=float,
        default=0.75,
    )
    parser.add_argument(
        "--expansion-threshold",
        type=float,
        default=0.60,
    )
    parser.add_argument(
        "--final-utility-threshold",
        type=float,
        default=0.65,
    )
    parser.add_argument(
        "--max-anchor-tiles",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", "jev-latest"),
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv(
            "TYPESAFE_API_URL",
            "https://api.typesafe.ai/v1/systemone",
        ),
    )
    args = parser.parse_args(argv)

    api_key = os.getenv("TYPESAFE_API_KEY", "")
    if not api_key:
        raise SystemExit("TYPESAFE_API_KEY is required")

    phase0_run = load(args.phase0_run)
    decider = FrontierObligationDecider(
        api_key,
        Trace(args.trace_file),
        args.endpoint,
        args.model,
    )
    result = run(
        args.source,
        args.goal,
        phase0_run,
        decider,
        tile_lines=args.tile_lines,
        frontier_quantile=args.frontier_quantile,
        expansion_threshold=args.expansion_threshold,
        final_utility_threshold=args.final_utility_threshold,
        max_anchor_tiles=args.max_anchor_tiles,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "termination": result["termination"],
        "frontier_geometry": result["frontier_geometry"],
        "obligations": {
            "total": len(result["obligations"]),
            "satisfied": sum(
                item["status"] == "satisfied"
                for item in result["obligations"]
            ),
            "exhausted": sum(
                item["status"] == "exhausted"
                for item in result["obligations"]
            ),
        },
        "anchors": len(result["anchors"]),
        "retained": len(result["retained_anchor_ids"]),
        "materialized_count": result["materialized_count"],
        "materialized_lines": result["materialized_lines"],
        "usage": result["usage"],
    }, indent=2))


if __name__ == "__main__":
    main()
