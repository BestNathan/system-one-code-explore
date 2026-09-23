#!/usr/bin/env python3
"""Algorithm A: Explore-Guided Evidence Filtering.

This variant preserves the per-file range-runtime state machine and action-space
generation. Only the System One decision semantics change: reads are scored by
their expected contribution of NEW MATERIAL EVIDENCE, not topical relevance.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from system_one_code_locator import API_URL, MODEL, Trace, empty_usage, merge_usage
from system_one_range_runtime import (
    DEFAULT_DIRECTORY_THRESHOLD,
    DEFAULT_EVIDENCE_THRESHOLD,
    DEFAULT_FILE_THRESHOLD,
    DEFAULT_MAX_FILE_EPOCHS,
    DEFAULT_MAX_JUMPS,
    DEFAULT_PARALLEL_THRESHOLD,
    DEFAULT_WINDOW_LINES,
    OfflineFileDecider,
    SystemOneFileDecider,
    decision_view,
    observation_view,
    run,
    sanitize_source,
)


EVIDENCE_TAXONOMY = (
    "implementation details; control flow; state transitions; dependencies and "
    "contracts; edge cases; invariants and constraints"
)


class EvidenceGuidedDecider(SystemOneFileDecider):
    """Same runtime, evidence-first scoring semantics."""

    def decide_file_actions(self, goal, file_state, actions):
        stop_action = next(
            item for item in actions
            if item["kind"] == "stop_file"
        )
        reads = [
            item for item in actions
            if item["kind"] == "read_range"
        ]

        questions = {
            "control": {
                "type": "choice",
                "instructions": {
                    "goal": goal,
                    "file": file_state["path"],
                    "question": (
                        "Act as a codebase-search specialist. Decide whether the "
                        "current observations already contain enough MATERIAL "
                        "EVIDENCE to support the downstream task, or whether one "
                        "more read is needed to close a concrete evidence gap. "
                        "Choose stop once the result contains a minimal but "
                        "sufficient representative evidence set. Do not continue "
                        "just because unread text exists or because another range "
                        "might be topically related. Prefer continue only when a "
                        "specific missing fact about implementation, control flow, "
                        "state transitions, dependencies/contracts, edge cases, "
                        "or constraints could materially change or complete the "
                        "downstream answer."
                    ),
                },
                "criteria": {
                    "stop": {
                        "action": "StopFile",
                        "meaning": (
                            "The existing evidence is sufficient and additional "
                            "reads are likely redundant or merely confirmatory."
                        ),
                    },
                    "continue": {
                        "action": "ContinueFile",
                        "meaning": (
                            "A concrete material evidence gap remains and another "
                            "read can plausibly close it."
                        ),
                    },
                },
            },
        }

        for index, action in enumerate(reads):
            questions[f"read_{index}"] = {
                "type": "noul",
                "instructions": {
                    "goal": goal,
                    "action": {
                        "path": action["path"],
                        "start_line": action["start_line"],
                        "end_line": action["end_line"],
                        "navigation": action["navigation"],
                        "reason": action["reason"],
                        "source": action.get("source"),
                    },
                    "question": (
                        "How likely is this exact ReadRange to add NEW MATERIAL "
                        "EVIDENCE needed for the downstream task, beyond the "
                        "observations already present? Material evidence is new "
                        "information that could materially change, complete, or "
                        "ground the answer. Merely topical code, wrappers, logging, "
                        "debug/status plumbing, or redundant repetition of a fact "
                        "already established should score low. Prefer evidence "
                        f"about {EVIDENCE_TAXONOMY}."
                    ),
                },
                "criteria": {
                    "true": (
                        "This range is likely to add a new fact or concrete "
                        "grounding that materially improves the downstream answer."
                    ),
                    "false": (
                        "This range is likely redundant, merely topical, "
                        "confirmatory, or low-value for answering the goal."
                    ),
                },
            }

        response, usage = self.send(
            "evidence_guided_control_and_actions",
            decision_view(goal, file_state),
            questions,
        )
        answers = response.get("answers", {})

        control = answers.get("control", {})
        if control.get("type") != "choice":
            raise RuntimeError(
                f"unexpected evidence-guided control answer: {control!r}"
            )
        choice = control.get("choice")
        if choice not in {"stop", "continue"}:
            raise RuntimeError(
                f"unexpected evidence-guided control choice: {choice!r}"
            )
        probabilities = control.get("probabilities", {})

        scored = []
        for index, action in enumerate(reads):
            answer = answers.get(f"read_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected evidence-guided read answer: {answer!r}"
                )
            scored.append({
                **action,
                "score": float(answer["noul"]),
            })
        scored.sort(key=lambda item: (-item["score"], item["id"]))

        stop_decision = {
            **stop_action,
            "choice": choice,
            "probability": float(
                probabilities.get(choice, 0.0) or 0.0
            ),
            "stop_probability": float(
                probabilities.get("stop", 0.0) or 0.0
            ),
            "continue_probability": float(
                probabilities.get("continue", 0.0) or 0.0
            ),
            "confidence": float(
                control.get("confidence", 0.0) or 0.0
            ),
            "decision_semantics": "material_evidence_sufficiency",
        }
        return stop_decision, scored, usage

    def score_file_evidence(self, goal, file_state, batch_size=2):
        observations = file_state["observations"]
        if not observations:
            return [], empty_usage()

        total_usage = empty_usage()
        scored = []
        context = {
            "goal": goal,
            "file": file_state["path"],
            "existing_observations": observation_view(
                file_state,
                char_budget=24000,
            ),
            "instruction": (
                "Use existing observations only to judge whether each "
                "candidate adds a DISTINCT material fact. Do not reward "
                "repetition of evidence already established."
            ),
        }

        def score_batch(batch):
            questions = {}
            for local_index, item in enumerate(batch):
                questions[f"evidence_{local_index}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "path": item["path"],
                        "start_line": item["start_line"],
                        "end_line": item["end_line"],
                        "content": sanitize_source(item["content"]),
                        "question": (
                            "Does this range contribute NEW MATERIAL EVIDENCE "
                            "that should survive into the minimal final evidence "
                            "set? Score high only when it adds a distinct fact or "
                            "concrete grounding needed for the downstream answer. "
                            "Penalize redundancy with existing observations."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "Distinct, material, grounded evidence useful for "
                            "implementation/control flow/state/dependency/"
                            "contract/edge-case/constraint reasoning."
                        ),
                        "false": (
                            "Redundant, merely topical, incidental, or unlikely "
                            "to help the downstream task progress."
                        ),
                    },
                }

            try:
                response, usage = self.send(
                    "evidence_guided_result_filter",
                    context,
                    questions,
                )
            except RuntimeError as exc:
                if (
                    "max_tokens_exceeded" in str(exc)
                    and len(batch) > 1
                ):
                    midpoint = len(batch) // 2
                    left, left_usage = score_batch(batch[:midpoint])
                    right, right_usage = score_batch(batch[midpoint:])
                    merge_usage(left_usage, right_usage)
                    return left + right, left_usage
                raise

            answers = response.get("answers", {})
            out = []
            for local_index, item in enumerate(batch):
                answer = answers.get(f"evidence_{local_index}", {})
                if answer.get("type") != "noul":
                    raise RuntimeError(
                        f"unexpected evidence filter answer: {answer!r}"
                    )
                value = float(answer["noul"])
                out.append({
                    **item,
                    "relevance": value,
                    "evidence_value": value,
                })
            return out, usage

        for start in range(0, len(observations), batch_size):
            batch = observations[start:start + batch_size]
            current, usage = score_batch(batch)
            scored.extend(current)
            merge_usage(total_usage, usage)

        return scored, total_usage



class OfflineEvidenceGuidedDecider(OfflineFileDecider):
    model = "offline-evidence-guided-fixture"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("query")
    parser.add_argument(
        "--directory-threshold",
        type=float,
        default=DEFAULT_DIRECTORY_THRESHOLD,
    )
    parser.add_argument(
        "--file-threshold",
        type=float,
        default=DEFAULT_FILE_THRESHOLD,
    )
    parser.add_argument(
        "--window-lines",
        type=int,
        default=DEFAULT_WINDOW_LINES,
    )
    parser.add_argument(
        "--parallel-threshold",
        type=float,
        default=DEFAULT_PARALLEL_THRESHOLD,
    )
    parser.add_argument(
        "--evidence-threshold",
        type=float,
        default=DEFAULT_EVIDENCE_THRESHOLD,
    )
    parser.add_argument(
        "--max-jumps",
        type=int,
        default=DEFAULT_MAX_JUMPS,
    )
    parser.add_argument(
        "--max-file-epochs",
        type=int,
        default=DEFAULT_MAX_FILE_EPOCHS,
    )
    parser.add_argument("--offline-decider", action="store_true")
    parser.add_argument("--trace-file")
    parser.add_argument("--output-json")
    parser.add_argument(
        "--typesafe-endpoint",
        default=os.getenv("TYPESAFE_API_URL", API_URL),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", MODEL),
    )
    args = parser.parse_args(argv)

    trace = Trace(args.trace_file)
    if args.offline_decider:
        decider = OfflineEvidenceGuidedDecider(trace)
    else:
        key = os.getenv("TYPESAFE_API_KEY", "")
        if not key:
            print(
                "TYPESAFE_API_KEY is required unless --offline-decider is used.",
                file=sys.stderr,
            )
            return 2
        decider = EvidenceGuidedDecider(
            key,
            trace,
            args.typesafe_endpoint,
            args.model,
        )

    result = run(
        args.root,
        args.query,
        decider,
        trace,
        directory_threshold=args.directory_threshold,
        file_threshold=args.file_threshold,
        window_lines=args.window_lines,
        parallel_threshold=args.parallel_threshold,
        evidence_threshold=args.evidence_threshold,
        max_jumps=args.max_jumps,
        max_file_epochs=args.max_file_epochs,
    )
    result["architecture"] = "explore_guided_evidence_filtering_v0"

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
        print(json.dumps(result["metrics"], ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
