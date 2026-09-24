#!/usr/bin/env python3
"""R12: probability-frontier-guided dynamic evidence acquisition.

Phase0 is frozen. This phase partitions the complete source file into equal
read actions and lets System One repeatedly choose the next block with the
highest *marginal evidence value*. After a block is read it is removed from the
action space and its source is added to state. The phase terminates naturally
when Stop outranks every remaining read action or no read action is
meaningfully above the uniform categorical prior.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from system_one_code_locator import Trace, empty_usage, merge_usage, sanitize_source
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider


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
    out = []
    used = 0
    # Keep recent evidence visible first because it is most likely to affect the
    # next marginal decision. Earlier evidence is retained while budget allows.
    for item in reversed(selected):
        content = sanitize_source(item["content"])
        cost = len(content)
        if out and used + cost > int(char_budget):
            break
        out.append({
            "range": [item["start_line"], item["end_line"]],
            "choice_probability": round(
                float(item["choice_probability"]),
                6,
            ),
            "phase0_mean_relevance": round(
                float(item["phase0_mean_relevance"]),
                6,
            ),
            "content": content,
        })
        used += cost
    out.reverse()
    return out


class DynamicEvidenceDecider(ClosureChoiceRelevanceFrontierDecider):
    def choose_next(
        self,
        goal,
        path,
        phase0_run,
        remaining,
        selected,
    ):
        questions = {
            "next_evidence": {
                "type": "choice",
                "instructions": {
                    "goal": goal,
                    "question": (
                        "Choose the single next source range with the greatest "
                        "MARGINAL evidence value for solving the goal, or Stop "
                        "when the evidence already read is sufficient and no "
                        "remaining range is likely to add a distinct material "
                        "fact. Probabilities should reflect expected marginal "
                        "value, not merely topical similarity."
                    ),
                },
                "criteria": {},
            }
        }
        criteria = questions["next_evidence"]["criteria"]

        for action in remaining:
            criteria[action["id"]] = {
                "action": "ReadRange",
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
                "meaning": (
                    "Read this equal-size source block if it is likely to add "
                    "distinct implementation/control-flow/state/contract/"
                    "edge-case evidence not already covered."
                ),
            }

        criteria["stop"] = {
            "action": "Stop",
            "meaning": (
                "Existing evidence is sufficient for the goal and every "
                "remaining source block is unlikely to add a distinct material "
                "fact worth its read cost."
            ),
        }

        response, usage = self.send(
            "dynamic_evidence_next_range",
            {
                "goal": goal,
                "phase": "phase1_dynamic_evidence_acquisition",
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
                    "summary": (
                        "Per-action Phase0 relevance, uncertainty, and observed "
                        "fraction are attached to every remaining ReadRange."
                    ),
                },
                "selected_evidence": evidence_view(selected),
                "remaining_action_count": len(remaining),
            },
            questions,
        )
        answer = response.get("answers", {}).get("next_evidence", {})
        if answer.get("type") != "choice":
            raise RuntimeError(
                f"unexpected dynamic evidence choice: {answer!r}"
            )
        return {
            "choice": answer.get("choice"),
            "confidence": float(answer.get("confidence", 0.0) or 0.0),
            "probabilities": {
                key: float(value)
                for key, value in (
                    answer.get("probabilities", {}) or {}
                ).items()
            },
        }, usage


def run_dynamic_evidence(
    source,
    goal,
    phase0_run,
    decider,
    *,
    tile_lines=32,
    minimum_lift=1.1,
    max_rounds=32,
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

        decision, current = decider.choose_next(
            goal,
            phase0_run["subject"]["path"],
            phase0_run,
            remaining,
            selected,
        )
        merge_usage(usage, current)

        probabilities = decision["probabilities"]
        stop_probability = float(probabilities.get("stop", 0.0))
        by_id = {item["id"]: item for item in remaining}
        best_id = max(
            by_id,
            key=lambda action_id: float(
                probabilities.get(action_id, 0.0)
            ),
        )
        best_probability = float(probabilities.get(best_id, 0.0))
        uniform_probability = 1.0 / (len(remaining) + 1)
        best_lift = (
            best_probability / uniform_probability
            if uniform_probability else 0.0
        )

        stop_reason = None
        if stop_probability >= best_probability:
            stop_reason = "stop_outweighs_best_read"
        elif best_lift < float(minimum_lift):
            stop_reason = "no_read_above_uniform_lift"

        row = {
            "round": round_number,
            "remaining_actions": len(remaining),
            "uniform_probability": uniform_probability,
            "stop_probability": stop_probability,
            "best_read_id": best_id,
            "best_read_probability": best_probability,
            "best_read_lift": best_lift,
            "argmax": decision["choice"],
            "probabilities": probabilities,
            "stop_reason": stop_reason,
        }

        if stop_reason is not None:
            history.append(row)
            termination = stop_reason
            break

        action = by_id[best_id]
        evidence = read_action(source_lines, action)
        evidence["choice_probability"] = best_probability
        evidence["choice_lift"] = best_lift
        selected.append(evidence)
        remaining = [
            item for item in remaining
            if item["id"] != best_id
        ]
        row["read"] = {
            "id": best_id,
            "range": [
                action["start_line"],
                action["end_line"],
            ],
            "phase0_mean_relevance": action[
                "phase0_mean_relevance"
            ],
        }
        history.append(row)
    else:
        termination = "safety_cap"

    return {
        "schema_version": 1,
        "kind": "dynamic-evidence-acquisition",
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
            "tile_lines": int(tile_lines),
            "minimum_lift": float(minimum_lift),
            "max_rounds_safety_cap": int(max_rounds),
            "stopping": (
                "stop >= best read OR best read probability is below "
                "minimum_lift * uniform categorical prior"
            ),
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
    parser.add_argument("--minimum-lift", type=float, default=1.1)
    parser.add_argument("--max-rounds", type=int, default=32)
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
        minimum_lift=args.minimum_lift,
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
