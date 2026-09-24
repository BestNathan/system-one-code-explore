#!/usr/bin/env python3
"""R14: anchor-centered semantic closure.

Global acquisition and local semantic closure are separate:

- acquisition selects representative unresolved high-value frontier areas and
  likely-useful task evidence;
- every materialized seed becomes an independent semantic anchor;
- each useful anchor expands only as needed to complete the local construct it
  originally revealed;
- anchors are merged only for final output, never before completeness is judged.

This prevents the R13 failure where adjacent selected tiles became one giant
region whose completeness remained low indefinitely.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from system_one_code_locator import Trace, empty_usage, merge_usage, sanitize_source
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider
from multi_objective_evidence_acquisition import (
    enrich_action,
    partition_actions,
    read_tile,
)


DEFAULT_TILE_LINES = 32
DEFAULT_COVERAGE_THRESHOLD = 0.65
DEFAULT_UTILITY_THRESHOLD = 0.65
DEFAULT_COMPLETENESS_THRESHOLD = 0.70
DEFAULT_EXPANSION_THRESHOLD = 0.60
DEFAULT_MAX_ANCHOR_TILES = 12


def materialized_ranges(materialized):
    return [
        [item["start_line"], item["end_line"]]
        for item in sorted(
            materialized.values(),
            key=lambda x: x["start_line"],
        )
    ]


def anchor_range(anchor, actions_by_id):
    tiles = [
        actions_by_id[tile_id]
        for tile_id in anchor["tile_ids"]
    ]
    return (
        min(item["start_line"] for item in tiles),
        max(item["end_line"] for item in tiles),
    )


def anchor_source(anchor, actions_by_id, materialized, source_lines):
    left, right = anchor_range(anchor, actions_by_id)
    return "\n".join(
        f"{line}: {source_lines[line - 1]}"
        for line in range(left, right + 1)
    )


def adjacent_ids(anchor, actions_by_id, ordered_ids):
    positions = {
        action_id: index
        for index, action_id in enumerate(ordered_ids)
    }
    indices = sorted(
        positions[action_id]
        for action_id in anchor["tile_ids"]
    )
    before = (
        ordered_ids[indices[0] - 1]
        if indices[0] > 0 else None
    )
    after = (
        ordered_ids[indices[-1] + 1]
        if indices[-1] + 1 < len(ordered_ids) else None
    )
    return before, after


def merge_final_anchor_ranges(anchors, actions_by_id):
    ranges = []
    for anchor in anchors:
        left, right = anchor_range(anchor, actions_by_id)
        ranges.append({
            "start_line": left,
            "end_line": right,
            "anchor_ids": [anchor["id"]],
            "statuses": [anchor["status"]],
        })
    ranges.sort(
        key=lambda item: (
            item["start_line"],
            item["end_line"],
        )
    )
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
        merged[-1]["anchor_ids"].extend(
            item["anchor_ids"]
        )
        merged[-1]["statuses"].extend(
            item["statuses"]
        )
    return merged


class AnchorClosureDecider(ClosureChoiceRelevanceFrontierDecider):
    def score_acquisition(
        self,
        goal,
        path,
        remaining,
        materialized,
    ):
        usage = empty_usage()
        scored = []
        visible_coverage = materialized_ranges(materialized)

        for offset in range(0, len(remaining), 12):
            batch = remaining[offset:offset + 12]
            questions = {}
            for index, action in enumerate(batch):
                meta = {
                    "range": [
                        action["start_line"],
                        action["end_line"],
                    ],
                    "phase0_mean_relevance": round(
                        action["phase0_mean_relevance"],
                        4,
                    ),
                    "phase0_max_relevance": round(
                        action["phase0_max_relevance"],
                        4,
                    ),
                    "phase0_mean_uncertainty": round(
                        action["phase0_mean_uncertainty"],
                        4,
                    ),
                }
                questions[f"coverage_{index}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "action": meta,
                        "already_materialized_ranges": visible_coverage,
                        "question": (
                            "How strongly is this tile a DISTINCT unresolved "
                            "high-value region of the Phase0 frontier that still "
                            "needs representative source coverage? Score low when "
                            "nearby materialized tiles already represent the same "
                            "smooth frontier plateau. Do NOT score low merely "
                            "because enough evidence has been found elsewhere "
                            "for answering the task."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "This tile covers a distinct unresolved frontier "
                            "mode/peak/region that needs representative inspection."
                        ),
                        "false": (
                            "This tile is low-value or spatially redundant with "
                            "already materialized coverage of the same frontier "
                            "region."
                        ),
                    },
                }
                questions[f"utility_{index}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "action": meta,
                        "question": (
                            "Using the Phase0 frontier as the only semantic prior, "
                            "how likely is this unread tile to contain material "
                            "source evidence for the task? Judge intrinsic task "
                            "utility, not whether current evidence is already "
                            "sufficient."
                        ),
                    },
                    "criteria": {
                        "true": "Likely to contain material task evidence.",
                        "false": "Likely incidental or irrelevant.",
                    },
                }

            response, current = self.send(
                "r14_representative_acquisition",
                {
                    "goal": goal,
                    "phase": "r14_acquisition",
                    "file": path,
                    "already_materialized_ranges": visible_coverage,
                },
                questions,
            )
            merge_usage(usage, current)
            answers = response.get("answers", {})
            for index, action in enumerate(batch):
                coverage = answers.get(
                    f"coverage_{index}",
                    {},
                )
                utility = answers.get(
                    f"utility_{index}",
                    {},
                )
                if (
                    coverage.get("type") != "noul"
                    or utility.get("type") != "noul"
                ):
                    raise RuntimeError(
                        "unexpected R14 acquisition answer"
                    )
                scored.append({
                    **action,
                    "coverage_probability": float(
                        coverage["noul"]
                    ),
                    "utility_probability": float(
                        utility["noul"]
                    ),
                })

        scored.sort(
            key=lambda item: (
                -max(
                    item["coverage_probability"],
                    item["utility_probability"],
                ),
                item["start_line"],
            )
        )
        return scored, usage

    def assess_anchors(
        self,
        goal,
        path,
        anchors,
        actions_by_id,
        ordered_ids,
        materialized,
        source_lines,
    ):
        usage = empty_usage()
        results = []

        for offset in range(0, len(anchors), 8):
            batch = anchors[offset:offset + 8]
            questions = {}
            neighbors = {}

            for index, anchor in enumerate(batch):
                before_id, after_id = adjacent_ids(
                    anchor,
                    actions_by_id,
                    ordered_ids,
                )
                neighbors[index] = (
                    before_id,
                    after_id,
                )
                left, right = anchor_range(
                    anchor,
                    actions_by_id,
                )
                source = sanitize_source(
                    anchor_source(
                        anchor,
                        actions_by_id,
                        materialized,
                        source_lines,
                    )
                )
                common = {
                    "goal": goal,
                    "file": path,
                    "anchor_seed_range": anchor["seed_range"],
                    "current_anchor_range": [left, right],
                    "source": source,
                    "important": (
                        "Judge ONLY the semantic unit originally revealed by "
                        "this anchor. Do not expand merely to discover additional "
                        "related functions or other interesting code outside the "
                        "anchor's local construct."
                    ),
                }
                questions[f"utility_{index}"] = {
                    "type": "noul",
                    "instructions": {
                        **common,
                        "question": (
                            "How useful is this anchor's currently materialized "
                            "source for the task?"
                        ),
                    },
                    "criteria": {
                        "true": (
                            "The anchor contains material evidence for the task."
                        ),
                        "false": (
                            "The anchor is incidental or a false-positive hit."
                        ),
                    },
                }
                questions[f"complete_{index}"] = {
                    "type": "noul",
                    "instructions": {
                        **common,
                        "question": (
                            "Is the LOCAL semantic unit revealed by this anchor "
                            "complete enough to understand what the relevant "
                            "code does? Mark false if the anchor cuts off the "
                            "function/body, branch, match arm, loop, state "
                            "transition, error path, or locally necessary "
                            "setup/follow-up. Mark true once this specific local "
                            "construct is closed, even if other related code "
                            "exists elsewhere in the file."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "The anchor-specific relevant construct is locally "
                            "complete and understandable."
                        ),
                        "false": (
                            "The anchor-specific construct is visibly truncated "
                            "or depends on an immediately adjacent continuation."
                        ),
                    },
                }
                if before_id is not None:
                    before = actions_by_id[before_id]
                    questions[f"before_{index}"] = {
                        "type": "noul",
                        "instructions": {
                            **common,
                            "candidate_adjacent_range": [
                                before["start_line"],
                                before["end_line"],
                            ],
                            "question": (
                                "Is the immediately preceding tile likely needed "
                                "to COMPLETE THIS SAME ANCHOR-SPECIFIC semantic "
                                "unit? Do not use it merely to explore another "
                                "related construct."
                            ),
                        },
                        "criteria": {
                            "true": (
                                "Needed for this anchor's semantic closure."
                            ),
                            "false": (
                                "Not needed to close this anchor's local unit."
                            ),
                        },
                    }
                if after_id is not None:
                    after = actions_by_id[after_id]
                    questions[f"after_{index}"] = {
                        "type": "noul",
                        "instructions": {
                            **common,
                            "candidate_adjacent_range": [
                                after["start_line"],
                                after["end_line"],
                            ],
                            "question": (
                                "Is the immediately following tile likely needed "
                                "to COMPLETE THIS SAME ANCHOR-SPECIFIC semantic "
                                "unit? Do not use it merely to explore another "
                                "related construct."
                            ),
                        },
                        "criteria": {
                            "true": (
                                "Needed for this anchor's semantic closure."
                            ),
                            "false": (
                                "Not needed to close this anchor's local unit."
                            ),
                        },
                    }

            response, current = self.send(
                "r14_anchor_semantic_closure",
                {
                    "goal": goal,
                    "phase": "r14_anchor_closure",
                    "file": path,
                    "important": (
                        "Each anchor is independent. Completeness refers to the "
                        "anchor's local semantic unit, not the whole file or all "
                        "task-relevant code."
                    ),
                },
                questions,
            )
            merge_usage(usage, current)
            answers = response.get("answers", {})

            for index, anchor in enumerate(batch):
                before_id, after_id = neighbors[index]
                utility = answers.get(
                    f"utility_{index}",
                    {},
                )
                complete = answers.get(
                    f"complete_{index}",
                    {},
                )
                if (
                    utility.get("type") != "noul"
                    or complete.get("type") != "noul"
                ):
                    raise RuntimeError(
                        "unexpected R14 anchor answer"
                    )

                result = {
                    "anchor_id": anchor["id"],
                    "utility_probability": float(
                        utility["noul"]
                    ),
                    "completeness_probability": float(
                        complete["noul"]
                    ),
                    "before": None,
                    "after": None,
                }
                if before_id is not None:
                    before = answers.get(
                        f"before_{index}",
                        {},
                    )
                    if before.get("type") != "noul":
                        raise RuntimeError(
                            "unexpected R14 before answer"
                        )
                    result["before"] = {
                        "tile_id": before_id,
                        "probability": float(
                            before["noul"]
                        ),
                    }
                if after_id is not None:
                    after = answers.get(
                        f"after_{index}",
                        {},
                    )
                    if after.get("type") != "noul":
                        raise RuntimeError(
                            "unexpected R14 after answer"
                        )
                    result["after"] = {
                        "tile_id": after_id,
                        "probability": float(
                            after["noul"]
                        ),
                    }
                results.append(result)

        return results, usage


def run(
    source,
    goal,
    phase0_run,
    decider,
    *,
    tile_lines=DEFAULT_TILE_LINES,
    coverage_threshold=DEFAULT_COVERAGE_THRESHOLD,
    utility_threshold=DEFAULT_UTILITY_THRESHOLD,
    completeness_threshold=DEFAULT_COMPLETENESS_THRESHOLD,
    expansion_threshold=DEFAULT_EXPANSION_THRESHOLD,
    max_anchor_tiles=DEFAULT_MAX_ANCHOR_TILES,
    max_rounds=10,
):
    source_lines = Path(source).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    frontier = phase0_run["frontier"]
    if len(source_lines) != int(frontier["line_count"]):
        raise ValueError("source/frontier line mismatch")

    actions = [
        enrich_action(action, frontier)
        for action in partition_actions(
            frontier["line_count"],
            tile_lines,
        )
    ]
    actions_by_id = {
        action["id"]: action
        for action in actions
    }
    ordered_ids = [
        action["id"]
        for action in actions
    ]
    remaining_ids = set(ordered_ids)
    materialized = {}
    anchors = []
    usage = empty_usage()
    history = []
    termination = None

    def materialize(tile_id, reason, round_number):
        if tile_id not in materialized:
            materialized[tile_id] = read_tile(
                source_lines,
                actions_by_id[tile_id],
                reason=reason,
                round_number=round_number,
            )
        remaining_ids.discard(tile_id)

    def new_anchor(tile_id, round_number, acquisition):
        action = actions_by_id[tile_id]
        anchor = {
            "id": f"anchor_{len(anchors)+1:03d}",
            "seed_tile_id": tile_id,
            "seed_range": [
                action["start_line"],
                action["end_line"],
            ],
            "tile_ids": [tile_id],
            "status": "active",
            "created_round": round_number,
            "acquisition": {
                "coverage_probability": acquisition[
                    "coverage_probability"
                ],
                "utility_probability": acquisition[
                    "utility_probability"
                ],
            },
            "history": [],
        }
        anchors.append(anchor)
        return anchor

    for round_number in range(1, int(max_rounds) + 1):
        remaining = [
            actions_by_id[action_id]
            for action_id in ordered_ids
            if action_id in remaining_ids
        ]

        acquisitions = []
        if remaining:
            scored, current = decider.score_acquisition(
                goal,
                phase0_run["subject"]["path"],
                remaining,
                materialized,
            )
            merge_usage(usage, current)
            acquisitions = [
                item
                for item in scored
                if (
                    item["coverage_probability"]
                    >= float(coverage_threshold)
                    or item["utility_probability"]
                    >= float(utility_threshold)
                )
            ]
            for item in acquisitions:
                tile_id = item["id"]
                materialize(
                    tile_id,
                    "representative_frontier_or_utility",
                    round_number,
                )
                new_anchor(
                    tile_id,
                    round_number,
                    item,
                )

        active = [
            anchor
            for anchor in anchors
            if anchor["status"] == "active"
        ]
        assessments = []
        expansions = []

        if active:
            assessments, current = decider.assess_anchors(
                goal,
                phase0_run["subject"]["path"],
                active,
                actions_by_id,
                ordered_ids,
                materialized,
                source_lines,
            )
            merge_usage(usage, current)
            by_anchor = {
                item["anchor_id"]: item
                for item in assessments
            }

            requested = {}
            for anchor in active:
                result = by_anchor[anchor["id"]]
                anchor["history"].append({
                    "round": round_number,
                    **result,
                })
                anchor["last_utility_probability"] = result[
                    "utility_probability"
                ]
                anchor["last_completeness_probability"] = result[
                    "completeness_probability"
                ]

                if (
                    result["utility_probability"]
                    < float(utility_threshold)
                ):
                    anchor["status"] = "low_utility"
                    continue
                if (
                    result["completeness_probability"]
                    >= float(completeness_threshold)
                ):
                    anchor["status"] = "complete"
                    continue
                if len(anchor["tile_ids"]) >= int(max_anchor_tiles):
                    anchor["status"] = "closure_safety_cap"
                    continue

                candidates = []
                for side in ("before", "after"):
                    request = result.get(side)
                    if (
                        request is not None
                        and request["probability"]
                        >= float(expansion_threshold)
                    ):
                        candidates.append(
                            (side, request)
                        )

                if not candidates:
                    anchor["status"] = "unresolved_incomplete"
                    continue

                for side, request in candidates:
                    tile_id = request["tile_id"]
                    key = (anchor["id"], tile_id)
                    requested[key] = {
                        "anchor_id": anchor["id"],
                        "tile_id": tile_id,
                        "side": side,
                        "probability": request["probability"],
                    }

            for item in sorted(
                requested.values(),
                key=lambda row: (
                    -row["probability"],
                    row["anchor_id"],
                    row["tile_id"],
                ),
            ):
                anchor = next(
                    a for a in anchors
                    if a["id"] == item["anchor_id"]
                )
                tile_id = item["tile_id"]
                materialize(
                    tile_id,
                    f"anchor_closure_{item['side']}",
                    round_number,
                )
                if tile_id not in anchor["tile_ids"]:
                    anchor["tile_ids"].append(tile_id)
                    anchor["tile_ids"].sort(
                        key=lambda aid: ordered_ids.index(aid)
                    )
                expansions.append(item)

        history.append({
            "round": round_number,
            "acquired": [
                {
                    "id": item["id"],
                    "range": [
                        item["start_line"],
                        item["end_line"],
                    ],
                    "coverage_probability": item[
                        "coverage_probability"
                    ],
                    "utility_probability": item[
                        "utility_probability"
                    ],
                }
                for item in acquisitions
            ],
            "anchor_assessments": assessments,
            "anchor_expansions": expansions,
            "active_after": sum(
                anchor["status"] == "active"
                for anchor in anchors
            ),
            "remaining_after": len(remaining_ids),
        })

        if not acquisitions and not expansions:
            termination = "acquisition_and_anchor_closure_satisfied"
            break
    else:
        termination = "safety_cap"

    # Final anchor audit, without automatically expanding further.
    active_or_complete = [
        anchor for anchor in anchors
        if anchor["status"] in {
            "active",
            "complete",
            "unresolved_incomplete",
            "closure_safety_cap",
        }
    ]
    final_assessments = []
    if active_or_complete:
        final_assessments, current = decider.assess_anchors(
            goal,
            phase0_run["subject"]["path"],
            active_or_complete,
            actions_by_id,
            ordered_ids,
            materialized,
            source_lines,
        )
        merge_usage(usage, current)
        by_anchor = {
            item["anchor_id"]: item
            for item in final_assessments
        }
        for anchor in active_or_complete:
            item = by_anchor[anchor["id"]]
            anchor["final_utility_probability"] = item[
                "utility_probability"
            ]
            anchor["final_completeness_probability"] = item[
                "completeness_probability"
            ]

    return {
        "schema_version": 1,
        "kind": "r14-anchor-centered-semantic-closure",
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
            "coverage_threshold": float(coverage_threshold),
            "utility_threshold": float(utility_threshold),
            "completeness_threshold": float(
                completeness_threshold
            ),
            "expansion_threshold": float(expansion_threshold),
            "max_anchor_tiles_safety": int(max_anchor_tiles),
        },
        "termination": termination,
        "rounds": len(history),
        "materialized_count": len(materialized),
        "materialized_lines": sum(
            item["end_line"] - item["start_line"] + 1
            for item in materialized.values()
        ),
        "materialized_evidence": list(
            sorted(
                materialized.values(),
                key=lambda item: item["start_line"],
            )
        ),
        "anchors": anchors,
        "final_anchor_assessments": final_assessments,
        "final_regions": merge_final_anchor_ranges(
            anchors,
            actions_by_id,
        ),
        "remaining_actions": [
            actions_by_id[action_id]
            for action_id in ordered_ids
            if action_id in remaining_ids
        ],
        "history": history,
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
        "--coverage-threshold",
        type=float,
        default=0.65,
    )
    parser.add_argument(
        "--utility-threshold",
        type=float,
        default=0.65,
    )
    parser.add_argument(
        "--completeness-threshold",
        type=float,
        default=0.70,
    )
    parser.add_argument(
        "--expansion-threshold",
        type=float,
        default=0.60,
    )
    parser.add_argument(
        "--max-anchor-tiles",
        type=int,
        default=DEFAULT_MAX_ANCHOR_TILES,
    )
    parser.add_argument("--max-rounds", type=int, default=10)
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

    phase0 = json.loads(
        Path(args.phase0_run).read_text(
            encoding="utf-8"
        )
    )
    decider = AnchorClosureDecider(
        api_key,
        Trace(args.trace_file),
        args.endpoint,
        args.model,
    )
    result = run(
        args.source,
        args.goal,
        phase0,
        decider,
        tile_lines=args.tile_lines,
        coverage_threshold=args.coverage_threshold,
        utility_threshold=args.utility_threshold,
        completeness_threshold=args.completeness_threshold,
        expansion_threshold=args.expansion_threshold,
        max_anchor_tiles=args.max_anchor_tiles,
        max_rounds=args.max_rounds,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "termination": result["termination"],
        "rounds": result["rounds"],
        "materialized_count": result["materialized_count"],
        "materialized_lines": result["materialized_lines"],
        "anchors": len(result["anchors"]),
        "final_regions": result["final_regions"],
        "usage": result["usage"],
    }, indent=2))


if __name__ == "__main__":
    main()
