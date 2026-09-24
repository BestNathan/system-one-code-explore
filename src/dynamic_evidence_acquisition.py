#!/usr/bin/env python3
"""R12 v2: Phase0-guided dynamic evidence acquisition with independent Noul scores.

Phase0 is frozen. The complete file is divided into equal ReadRange actions.
Every remaining action receives an independent Noul probability estimating
whether reading that range is likely to add NEW MATERIAL EVIDENCE given the
Phase0 frontier and evidence already materialized.

All actions at or above the threshold are read in the same round, removed from
the action space, and their literal source is fed back into the next round.
The phase stops naturally when no remaining action clears the threshold.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from system_one_code_locator import Trace, empty_usage, merge_usage, sanitize_source
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider


DEFAULT_EVIDENCE_THRESHOLD = 0.65
DEFAULT_SCORE_BATCH_SIZE = 16


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def partition_actions(line_count, tile_lines=32):
    n = int(line_count)
    width = max(1, int(tile_lines))
    actions = []
    index = 1
    for left in range(1, n + 1, width):
        right = min(n, left + width - 1)
        actions.append({
            "id": f"tile_{index:03d}",
            "start_line": left,
            "end_line": right,
        })
        index += 1
    return actions


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def enrich_action(action, frontier):
    left = int(action["start_line"])
    right = int(action["end_line"])
    relevance = frontier["relevance"][left - 1:right]
    uncertainty = frontier["uncertainty"][left - 1:right]
    observed = frontier["observed"][left - 1:right]
    return {
        **action,
        "phase0_mean_relevance": _mean(relevance),
        "phase0_max_relevance": max(relevance) if relevance else 0.0,
        "phase0_mean_uncertainty": _mean(uncertainty),
        "phase0_observed_fraction": (
            sum(bool(value) for value in observed) / len(observed)
            if observed else 0.0
        ),
    }


def read_action(source_lines, action):
    left = int(action["start_line"])
    right = int(action["end_line"])
    return {
        **action,
        "content": "\n".join(
            f"{line}: {source_lines[line - 1]}"
            for line in range(left, right + 1)
        ),
    }


def evidence_view(selected, *, char_budget=30000):
    if not selected:
        return []
    visible = []
    used = 0
    for item in reversed(selected):
        content = sanitize_source(item["content"])
        size = len(content)
        if visible and used + size > int(char_budget):
            continue
        if not visible and size > int(char_budget):
            content = content[-int(char_budget):]
            size = len(content)
        visible.append({
            "range": [item["start_line"], item["end_line"]],
            "noul_probability": round(
                float(item["noul_probability"]),
                6,
            ),
            "phase0_mean_relevance": round(
                float(item["phase0_mean_relevance"]),
                6,
            ),
            "content": content,
        })
        used += size
        if used >= int(char_budget):
            break
    visible.reverse()
    return {
        "total_count": len(selected),
        "visible_count": len(visible),
        "omitted_count": len(selected) - len(visible),
        "items": visible,
    }


class DynamicEvidenceDecider(ClosureChoiceRelevanceFrontierDecider):
    def score_actions(
        self,
        goal,
        path,
        phase0_run,
        remaining,
        selected,
        *,
        batch_size=DEFAULT_SCORE_BATCH_SIZE,
    ):
        """Return independent marginal-evidence probabilities for all actions."""
        usage = empty_usage()
        scored = []

        state = {
            "goal": goal,
            "phase": "phase1_dynamic_evidence_acquisition_noul_v2",
            "file": {
                "path": path,
                "line_count": phase0_run["frontier"]["line_count"],
            },
            "phase0": {
                "posterior_estimator": phase0_run.get(
                    "posterior_estimator"
                ),
                "probes": phase0_run.get("probes"),
                "sample_lines": phase0_run.get("sample_lines"),
                "semantics": (
                    "Phase0 estimated where task-relevant evidence may exist. "
                    "Per-action Phase0 relevance, uncertainty, and observed "
                    "fraction are supplied below. They are priors, not final "
                    "evidence judgments."
                ),
            },
            "selected_evidence": evidence_view(selected),
            "remaining_action_count": len(remaining),
            "decision_semantics": (
                "Each ReadRange is an independent binary action-utility "
                "judgment. Scores do NOT compete or sum to one."
            ),
        }

        size = max(1, int(batch_size))
        for offset in range(0, len(remaining), size):
            batch = remaining[offset:offset + size]
            questions = {}
            for index, action in enumerate(batch):
                questions[f"read_{index}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "range": [
                            action["start_line"],
                            action["end_line"],
                        ],
                        "phase0": {
                            "mean_relevance": round(
                                action["phase0_mean_relevance"],
                                4,
                            ),
                            "max_relevance": round(
                                action["phase0_max_relevance"],
                                4,
                            ),
                            "mean_uncertainty": round(
                                action["phase0_mean_uncertainty"],
                                4,
                            ),
                            "observed_fraction": round(
                                action["phase0_observed_fraction"],
                                4,
                            ),
                        },
                        "question": (
                            "How likely is reading this exact source range NOW "
                            "to add NEW MATERIAL EVIDENCE needed for the goal, "
                            "beyond evidence already materialized? Score high "
                            "when the Phase0 frontier indicates this range is "
                            "likely to contain a distinct useful mechanism, "
                            "state transition, contract, dependency, edge case, "
                            "constraint, or implementation fact. Score low when "
                            "it is likely irrelevant, redundant with selected "
                            "evidence, or merely confirmatory."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "Reading this range is likely to add a distinct "
                            "material fact worth materializing now."
                        ),
                        "false": (
                            "Reading this range is likely low-value, redundant, "
                            "incidental, or unnecessary for the goal."
                        ),
                    },
                }

            response, current = self.send(
                "dynamic_evidence_noul_scores",
                state,
                questions,
            )
            merge_usage(usage, current)
            answers = response.get("answers", {})
            for index, action in enumerate(batch):
                answer = answers.get(f"read_{index}", {})
                if answer.get("type") != "noul":
                    raise RuntimeError(
                        f"unexpected dynamic evidence Noul answer: {answer!r}"
                    )
                scored.append({
                    **action,
                    "noul_probability": float(answer["noul"]),
                })

        scored.sort(
            key=lambda item: (
                -item["noul_probability"],
                item["start_line"],
            )
        )
        return scored, usage


def run_dynamic_evidence(
    source,
    goal,
    phase0_run,
    decider,
    *,
    tile_lines=32,
    threshold=DEFAULT_EVIDENCE_THRESHOLD,
    score_batch_size=DEFAULT_SCORE_BATCH_SIZE,
    max_rounds=16,
):
    source_lines = Path(source).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    frontier = phase0_run["frontier"]
    line_count = int(frontier["line_count"])
    if len(source_lines) != line_count:
        raise ValueError(
            f"source/frontier line mismatch: {len(source_lines)} != {line_count}"
        )

    remaining = [
        enrich_action(action, frontier)
        for action in partition_actions(line_count, tile_lines)
    ]
    selected = []
    history = []
    usage = empty_usage()
    termination = None

    for round_number in range(1, int(max_rounds) + 1):
        if not remaining:
            termination = "action_space_exhausted"
            break

        scored, current = decider.score_actions(
            goal,
            phase0_run["subject"]["path"],
            phase0_run,
            remaining,
            selected,
            batch_size=score_batch_size,
        )
        merge_usage(usage, current)

        chosen = [
            item
            for item in scored
            if float(item["noul_probability"]) >= float(threshold)
        ]

        row = {
            "round": round_number,
            "remaining_before": len(remaining),
            "threshold": float(threshold),
            "max_probability": (
                float(scored[0]["noul_probability"])
                if scored else 0.0
            ),
            "selected_count": len(chosen),
            "selected": [
                {
                    "id": item["id"],
                    "range": [
                        item["start_line"],
                        item["end_line"],
                    ],
                    "noul_probability": float(
                        item["noul_probability"]
                    ),
                    "phase0_mean_relevance": float(
                        item["phase0_mean_relevance"]
                    ),
                }
                for item in chosen
            ],
            "score_distribution": [
                {
                    "id": item["id"],
                    "noul_probability": float(
                        item["noul_probability"]
                    ),
                }
                for item in scored
            ],
        }

        if not chosen:
            termination = "all_remaining_below_threshold"
            history.append(row)
            break

        chosen_ids = {item["id"] for item in chosen}
        materialized = []
        for action in chosen:
            evidence = read_action(source_lines, action)
            evidence["noul_probability"] = float(
                action["noul_probability"]
            )
            evidence["selected_round"] = round_number
            selected.append(evidence)
            materialized.append({
                "id": evidence["id"],
                "range": [
                    evidence["start_line"],
                    evidence["end_line"],
                ],
                "noul_probability": evidence[
                    "noul_probability"
                ],
            })

        remaining = [
            item
            for item in remaining
            if item["id"] not in chosen_ids
        ]
        row["materialized"] = materialized
        row["remaining_after"] = len(remaining)
        history.append(row)
    else:
        termination = "safety_cap"

    return {
        "schema_version": 2,
        "kind": "dynamic-evidence-acquisition-noul",
        "goal": goal,
        "subject": phase0_run.get("subject"),
        "phase0_source": {
            "posterior_estimator": phase0_run.get(
                "posterior_estimator"
            ),
            "probes": phase0_run.get("probes"),
            "sample_lines": phase0_run.get("sample_lines"),
        },
        "policy": {
            "scoring": "independent_noul_marginal_evidence_probability",
            "tile_lines": int(tile_lines),
            "threshold": float(threshold),
            "score_batch_size": int(score_batch_size),
            "selection": "read_all_actions_at_or_above_threshold",
            "stopping": "no_remaining_action_at_or_above_threshold",
            "max_rounds_safety_cap": int(max_rounds),
        },
        "termination": termination,
        "rounds": len(history),
        "selected_count": len(selected),
        "selected_lines": sum(
            item["end_line"] - item["start_line"] + 1
            for item in selected
        ),
        "selected_evidence": selected,
        "history": history,
        "remaining_actions": remaining,
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
        "--threshold",
        type=float,
        default=DEFAULT_EVIDENCE_THRESHOLD,
    )
    parser.add_argument(
        "--score-batch-size",
        type=int,
        default=DEFAULT_SCORE_BATCH_SIZE,
    )
    parser.add_argument("--max-rounds", type=int, default=16)
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

    phase0_run = load(args.phase0_run)
    trace = Trace(args.trace_file)
    decider = DynamicEvidenceDecider(
        key,
        trace,
        args.endpoint,
        args.model,
    )
    result = run_dynamic_evidence(
        args.source,
        args.goal,
        phase0_run,
        decider,
        tile_lines=args.tile_lines,
        threshold=args.threshold,
        score_batch_size=args.score_batch_size,
        max_rounds=args.max_rounds,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "termination": result["termination"],
        "selected_count": result["selected_count"],
        "selected_lines": result["selected_lines"],
        "rounds": result["rounds"],
        "usage": result["usage"],
    }, indent=2))


if __name__ == "__main__":
    main()
