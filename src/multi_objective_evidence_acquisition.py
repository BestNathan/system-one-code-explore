#!/usr/bin/env python3
"""R13: multi-objective evidence acquisition with semantic closure.

R13 separates three concerns that R12 compressed into one marginal-evidence
score:

1. frontier coverage: have high-value Phase0 regions been materially inspected?
2. task utility: does a materialized source region help solve the goal?
3. semantic completeness: is the useful region complete enough to understand
   the relevant code unit, or must adjacent source be expanded?

The runtime is intentionally syntax-agnostic. System One decides semantic
closure from literal source; the harness only knows line ranges and adjacency.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from system_one_code_locator import Trace, empty_usage, merge_usage, sanitize_source
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider


DEFAULT_TILE_LINES = 32
DEFAULT_COVERAGE_THRESHOLD = 0.65
DEFAULT_UTILITY_THRESHOLD = 0.65
DEFAULT_COMPLETENESS_THRESHOLD = 0.70
DEFAULT_EXPANSION_THRESHOLD = 0.60
DEFAULT_BATCH_SIZE = 12


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mean(values):
    return sum(values) / len(values) if values else 0.0


def partition_actions(line_count, tile_lines=DEFAULT_TILE_LINES):
    actions = []
    index = 1
    for left in range(1, int(line_count) + 1, int(tile_lines)):
        right = min(int(line_count), left + int(tile_lines) - 1)
        actions.append({
            "id": f"tile_{index:03d}",
            "start_line": left,
            "end_line": right,
        })
        index += 1
    return actions


def enrich_action(action, frontier):
    left = int(action["start_line"])
    right = int(action["end_line"])
    relevance = frontier["relevance"][left - 1:right]
    uncertainty = frontier["uncertainty"][left - 1:right]
    observed = frontier["observed"][left - 1:right]
    return {
        **action,
        "phase0_mean_relevance": mean(relevance),
        "phase0_max_relevance": max(relevance) if relevance else 0.0,
        "phase0_mean_uncertainty": mean(uncertainty),
        "phase0_observed_fraction": (
            sum(bool(x) for x in observed) / len(observed)
            if observed else 0.0
        ),
    }


def read_tile(source_lines, action, *, reason, round_number):
    left = int(action["start_line"])
    right = int(action["end_line"])
    return {
        **action,
        "reason": reason,
        "selected_round": int(round_number),
        "content": "\n".join(
            f"{line}: {source_lines[line - 1]}"
            for line in range(left, right + 1)
        ),
    }


def merge_regions(selected):
    if not selected:
        return []
    ordered = sorted(
        selected,
        key=lambda item: (item["start_line"], item["end_line"]),
    )
    regions = []
    for item in ordered:
        left = int(item["start_line"])
        right = int(item["end_line"])
        if not regions or left > regions[-1]["end_line"] + 1:
            regions.append({
                "start_line": left,
                "end_line": right,
                "tile_ids": [item["id"]],
                "items": [item],
            })
        else:
            regions[-1]["end_line"] = max(
                regions[-1]["end_line"],
                right,
            )
            regions[-1]["tile_ids"].append(item["id"])
            regions[-1]["items"].append(item)
    return regions


def region_content(source_lines, region, char_budget=18000):
    left = int(region["start_line"])
    right = int(region["end_line"])
    text = "\n".join(
        f"{line}: {source_lines[line - 1]}"
        for line in range(left, right + 1)
    )
    if len(text) <= int(char_budget):
        return text
    half = int(char_budget) // 2
    return text[:half] + "\n...\n" + text[-half:]


def evidence_summary(selected, source_lines, char_budget=24000):
    regions = merge_regions(selected)
    visible = []
    used = 0
    for region in reversed(regions):
        text = region_content(source_lines, region)
        cost = len(text)
        if visible and used + cost > int(char_budget):
            continue
        visible.append({
            "range": [
                region["start_line"],
                region["end_line"],
            ],
            "content": sanitize_source(text),
        })
        used += cost
        if used >= int(char_budget):
            break
    visible.reverse()
    return {
        "total_regions": len(regions),
        "visible_regions": len(visible),
        "items": visible,
    }


def adjacent_unread_tiles(region, remaining):
    before = None
    after = None
    for action in remaining:
        if int(action["end_line"]) + 1 == int(region["start_line"]):
            before = action
        if int(region["end_line"]) + 1 == int(action["start_line"]):
            after = action
    return before, after


class MultiObjectiveEvidenceDecider(ClosureChoiceRelevanceFrontierDecider):
    def score_acquisition_actions(
        self,
        goal,
        path,
        phase0_run,
        remaining,
        selected,
        source_lines,
        *,
        batch_size=DEFAULT_BATCH_SIZE,
    ):
        """Score frontier-coverage need and task utility independently."""
        usage = empty_usage()
        out = []
        state = {
            "goal": goal,
            "phase": "r13_acquisition",
            "file": {
                "path": path,
                "line_count": phase0_run["frontier"]["line_count"],
            },
            "selected_evidence": evidence_summary(
                selected,
                source_lines,
            ),
            "semantics": (
                "Frontier coverage and task utility are separate objectives. "
                "Do not lower frontier-coverage need merely because some useful "
                "evidence has already been found elsewhere."
            ),
        }

        size = max(1, int(batch_size))
        for offset in range(0, len(remaining), size):
            batch = remaining[offset:offset + size]
            questions = {}
            for i, action in enumerate(batch):
                metadata = {
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
                    "phase0_observed_fraction": round(
                        action["phase0_observed_fraction"],
                        4,
                    ),
                }
                questions[f"coverage_{i}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "action": metadata,
                        "question": (
                            "How strongly does this unread range represent a "
                            "high-value part of the Phase0 probability frontier "
                            "that should be materially inspected before this "
                            "file can be considered adequately covered? Judge "
                            "coverage obligation, not whether current evidence "
                            "already feels sufficient."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "This range is an important unresolved high-value "
                            "frontier region and should be inspected."
                        ),
                        "false": (
                            "This range is low-value or already adequately "
                            "represented by inspected neighboring frontier."
                        ),
                    },
                }
                questions[f"utility_{i}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "action": metadata,
                        "question": (
                            "How likely is this unread range to contain source "
                            "that will materially help solve the task? Use the "
                            "Phase0 frontier as a prior. This is independent of "
                            "whether other evidence has already been found."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "This range is likely to contain material task "
                            "evidence."
                        ),
                        "false": (
                            "This range is likely incidental or irrelevant."
                        ),
                    },
                }

            response, current = self.send(
                "r13_acquisition_scores",
                state,
                questions,
            )
            merge_usage(usage, current)
            answers = response.get("answers", {})
            for i, action in enumerate(batch):
                coverage = answers.get(f"coverage_{i}", {})
                utility = answers.get(f"utility_{i}", {})
                if (
                    coverage.get("type") != "noul"
                    or utility.get("type") != "noul"
                ):
                    raise RuntimeError(
                        "unexpected R13 acquisition answer"
                    )
                out.append({
                    **action,
                    "coverage_probability": float(
                        coverage["noul"]
                    ),
                    "utility_probability": float(
                        utility["noul"]
                    ),
                })

        out.sort(
            key=lambda item: (
                -max(
                    item["coverage_probability"],
                    item["utility_probability"],
                ),
                item["start_line"],
            )
        )
        return out, usage

    def assess_regions(
        self,
        goal,
        path,
        regions,
        remaining,
        source_lines,
        *,
        batch_size=8,
    ):
        """Judge utility, semantic completeness, and directional expansion."""
        usage = empty_usage()
        assessments = []
        size = max(1, int(batch_size))

        for offset in range(0, len(regions), size):
            batch = regions[offset:offset + size]
            questions = {}
            adjacency = {}

            for i, region in enumerate(batch):
                before, after = adjacent_unread_tiles(
                    region,
                    remaining,
                )
                adjacency[i] = (before, after)
                source = sanitize_source(
                    region_content(source_lines, region)
                )
                common = {
                    "goal": goal,
                    "file": path,
                    "materialized_range": [
                        region["start_line"],
                        region["end_line"],
                    ],
                    "source": source,
                }
                questions[f"useful_{i}"] = {
                    "type": "noul",
                    "instructions": {
                        **common,
                        "question": (
                            "How useful is this materialized source fragment for "
                            "solving the goal? Judge the literal code now visible."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "The fragment contains material implementation or "
                            "behavioral evidence for the task."
                        ),
                        "false": (
                            "The fragment is incidental or not useful."
                        ),
                    },
                }
                questions[f"complete_{i}"] = {
                    "type": "noul",
                    "instructions": {
                        **common,
                        "question": (
                            "Is this fragment semantically complete enough to "
                            "understand the relevant code unit or behavior it "
                            "reveals? A fragment is incomplete when it cuts off "
                            "a function/body, branch, match arm, loop, state "
                            "transition, error path, data-flow step, or other "
                            "continuation needed to understand what the relevant "
                            "code actually does. Do NOT mark complete merely "
                            "because the fragment is relevant."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "The relevant semantic unit and its important local "
                            "control/data flow are sufficiently visible."
                        ),
                        "false": (
                            "The relevant evidence is truncated or needs adjacent "
                            "source to be understood correctly."
                        ),
                    },
                }

                if before is not None:
                    questions[f"before_{i}"] = {
                        "type": "noul",
                        "instructions": {
                            **common,
                            "candidate_adjacent_range": [
                                before["start_line"],
                                before["end_line"],
                            ],
                            "question": (
                                "How likely is reading the immediately preceding "
                                "range necessary to complete or disambiguate the "
                                "relevant semantic unit in this fragment?"
                            ),
                        },
                        "criteria": {
                            "true": (
                                "The preceding range is likely needed for semantic "
                                "closure or essential context."
                            ),
                            "false": (
                                "The fragment is understandable without it."
                            ),
                        },
                    }

                if after is not None:
                    questions[f"after_{i}"] = {
                        "type": "noul",
                        "instructions": {
                            **common,
                            "candidate_adjacent_range": [
                                after["start_line"],
                                after["end_line"],
                            ],
                            "question": (
                                "How likely is reading the immediately following "
                                "range necessary to complete or disambiguate the "
                                "relevant semantic unit in this fragment?"
                            ),
                        },
                        "criteria": {
                            "true": (
                                "The following range is likely needed to reveal "
                                "the rest of the relevant function/branch/"
                                "transition/behavior."
                            ),
                            "false": (
                                "The fragment is understandable without it."
                            ),
                        },
                    }

            response, current = self.send(
                "r13_semantic_closure",
                {
                    "goal": goal,
                    "phase": "r13_semantic_closure",
                    "file": path,
                    "important": (
                        "Relevance and completeness are different. A highly "
                        "relevant fragment may still be incomplete."
                    ),
                },
                questions,
            )
            merge_usage(usage, current)
            answers = response.get("answers", {})

            for i, region in enumerate(batch):
                before, after = adjacency[i]
                useful = answers.get(f"useful_{i}", {})
                complete = answers.get(f"complete_{i}", {})
                if (
                    useful.get("type") != "noul"
                    or complete.get("type") != "noul"
                ):
                    raise RuntimeError(
                        "unexpected R13 region assessment"
                    )
                item = {
                    "start_line": region["start_line"],
                    "end_line": region["end_line"],
                    "tile_ids": list(region["tile_ids"]),
                    "utility_probability": float(
                        useful["noul"]
                    ),
                    "completeness_probability": float(
                        complete["noul"]
                    ),
                    "before": None,
                    "after": None,
                }
                if before is not None:
                    answer = answers.get(f"before_{i}", {})
                    if answer.get("type") != "noul":
                        raise RuntimeError(
                            "unexpected R13 before expansion answer"
                        )
                    item["before"] = {
                        "action": before,
                        "probability": float(answer["noul"]),
                    }
                if after is not None:
                    answer = answers.get(f"after_{i}", {})
                    if answer.get("type") != "noul":
                        raise RuntimeError(
                            "unexpected R13 after expansion answer"
                        )
                    item["after"] = {
                        "action": after,
                        "probability": float(answer["noul"]),
                    }
                assessments.append(item)

        return assessments, usage


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
    max_rounds=12,
):
    source_lines = Path(source).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    frontier = phase0_run["frontier"]
    if len(source_lines) != int(frontier["line_count"]):
        raise ValueError("source/frontier line mismatch")

    all_actions = [
        enrich_action(item, frontier)
        for item in partition_actions(
            frontier["line_count"],
            tile_lines,
        )
    ]
    remaining = list(all_actions)
    selected = []
    usage = empty_usage()
    history = []
    termination = None

    for round_number in range(1, int(max_rounds) + 1):
        if not remaining:
            termination = "action_space_exhausted"
            break

        scored, current = decider.score_acquisition_actions(
            goal,
            phase0_run["subject"]["path"],
            phase0_run,
            remaining,
            selected,
            source_lines,
        )
        merge_usage(usage, current)

        acquire = [
            item for item in scored
            if (
                item["coverage_probability"]
                >= float(coverage_threshold)
                or item["utility_probability"]
                >= float(utility_threshold)
            )
        ]

        round_record = {
            "round": round_number,
            "remaining_before": len(remaining),
            "acquisition_scores": [
                {
                    "id": item["id"],
                    "coverage_probability": item[
                        "coverage_probability"
                    ],
                    "utility_probability": item[
                        "utility_probability"
                    ],
                }
                for item in scored
            ],
            "acquired": [],
            "closure_expansions": [],
            "region_assessments": [],
        }

        acquired_ids = set()
        for action in acquire:
            evidence = read_tile(
                source_lines,
                action,
                reason="frontier_or_utility",
                round_number=round_number,
            )
            evidence["coverage_probability"] = float(
                action["coverage_probability"]
            )
            evidence["utility_probability"] = float(
                action["utility_probability"]
            )
            selected.append(evidence)
            acquired_ids.add(action["id"])
            round_record["acquired"].append({
                "id": action["id"],
                "range": [
                    action["start_line"],
                    action["end_line"],
                ],
                "coverage_probability": action[
                    "coverage_probability"
                ],
                "utility_probability": action[
                    "utility_probability"
                ],
            })

        remaining = [
            item for item in remaining
            if item["id"] not in acquired_ids
        ]

        # Semantic closure is evaluated even if acquisition found nothing new:
        # already-materialized regions may still be incomplete.
        regions = merge_regions(selected)
        assessments, current = decider.assess_regions(
            goal,
            phase0_run["subject"]["path"],
            regions,
            remaining,
            source_lines,
        )
        merge_usage(usage, current)
        round_record["region_assessments"] = [
            {
                key: value
                for key, value in item.items()
                if key not in {"before", "after"}
            }
            for item in assessments
        ]

        expansion_candidates = {}
        for assessment in assessments:
            if (
                assessment["utility_probability"]
                < float(utility_threshold)
            ):
                continue
            if (
                assessment["completeness_probability"]
                >= float(completeness_threshold)
            ):
                continue
            for side in ("before", "after"):
                request = assessment.get(side)
                if (
                    request is not None
                    and request["probability"]
                    >= float(expansion_threshold)
                ):
                    action = request["action"]
                    existing = expansion_candidates.get(
                        action["id"]
                    )
                    if (
                        existing is None
                        or request["probability"]
                        > existing["probability"]
                    ):
                        expansion_candidates[action["id"]] = {
                            "action": action,
                            "probability": request["probability"],
                            "side": side,
                            "source_region": [
                                assessment["start_line"],
                                assessment["end_line"],
                            ],
                        }

        expansion_ids = set()
        for item in sorted(
            expansion_candidates.values(),
            key=lambda row: (
                -row["probability"],
                row["action"]["start_line"],
            ),
        ):
            action = item["action"]
            evidence = read_tile(
                source_lines,
                action,
                reason=f"semantic_closure_{item['side']}",
                round_number=round_number,
            )
            evidence["closure_probability"] = float(
                item["probability"]
            )
            selected.append(evidence)
            expansion_ids.add(action["id"])
            round_record["closure_expansions"].append({
                "id": action["id"],
                "range": [
                    action["start_line"],
                    action["end_line"],
                ],
                "probability": item["probability"],
                "side": item["side"],
                "source_region": item["source_region"],
            })

        remaining = [
            item for item in remaining
            if item["id"] not in expansion_ids
        ]
        round_record["remaining_after"] = len(remaining)
        history.append(round_record)

        if not acquire and not expansion_candidates:
            termination = "coverage_utility_and_closure_satisfied"
            break
    else:
        termination = "safety_cap"

    final_regions = merge_regions(selected)
    return {
        "schema_version": 1,
        "kind": "r13-multi-objective-evidence-acquisition",
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
        },
        "termination": termination,
        "rounds": len(history),
        "selected_count": len(selected),
        "selected_lines": sum(
            item["end_line"] - item["start_line"] + 1
            for item in selected
        ),
        "selected_evidence": selected,
        "final_regions": [
            {
                "start_line": item["start_line"],
                "end_line": item["end_line"],
                "tile_ids": item["tile_ids"],
            }
            for item in final_regions
        ],
        "remaining_actions": remaining,
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
    parser.add_argument(
        "--tile-lines",
        type=int,
        default=DEFAULT_TILE_LINES,
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=DEFAULT_COVERAGE_THRESHOLD,
    )
    parser.add_argument(
        "--utility-threshold",
        type=float,
        default=DEFAULT_UTILITY_THRESHOLD,
    )
    parser.add_argument(
        "--completeness-threshold",
        type=float,
        default=DEFAULT_COMPLETENESS_THRESHOLD,
    )
    parser.add_argument(
        "--expansion-threshold",
        type=float,
        default=DEFAULT_EXPANSION_THRESHOLD,
    )
    parser.add_argument("--max-rounds", type=int, default=12)
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

    key = os.getenv("TYPESAFE_API_KEY", "")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY is required")

    phase0 = load(args.phase0_run)
    trace = Trace(args.trace_file)
    decider = MultiObjectiveEvidenceDecider(
        key,
        trace,
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
        max_rounds=args.max_rounds,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "termination": result["termination"],
        "rounds": result["rounds"],
        "selected_count": result["selected_count"],
        "selected_lines": result["selected_lines"],
        "final_regions": result["final_regions"],
        "usage": result["usage"],
    }, indent=2))


if __name__ == "__main__":
    main()
