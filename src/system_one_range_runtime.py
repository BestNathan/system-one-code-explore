#!/usr/bin/env python3
"""Per-file range-only System One Harness Runtime v0.

Phase 1 locates plausible files. Phase 2 creates one independent FileRuntime
per file. A FileRuntime never sees another file's observations. The harness
only understands line counts, ranges, coverage, and history; it never parses
source semantics.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from localization_result import build_system_one_range_result
from system_one_code_locator import (
    API_URL,
    MODEL,
    DEFAULT_DIRECTORY_THRESHOLD,
    DEFAULT_FILE_THRESHOLD,
    SystemOneDecider,
    Trace,
    directories,
    empty_usage,
    files,
    merge_ranges,
    merge_usage,
    read_range,
    sanitize_source,
    source_stat,
    unread_gaps,
)

DEFAULT_WINDOW_LINES = 140
DEFAULT_PARALLEL_THRESHOLD = 0.65
DEFAULT_EVIDENCE_THRESHOLD = 0.65
DEFAULT_MAX_JUMPS = 2
DEFAULT_MAX_FILE_EPOCHS = 32
DEFAULT_DECISION_OBSERVATION_CHAR_BUDGET = 48000
DEFAULT_EVIDENCE_SCORE_BATCH_SIZE = 4


def bounded_range(start, end, line_count):
    start = max(1, int(start))
    end = min(int(line_count), int(end))
    if start > end:
        return None
    return start, end


def fully_uncovered(start, end, coverage):
    for left, right in merge_ranges(coverage):
        if not (end < left or start > right):
            return False
    return True


def gap_midpoint_window(gap_start, gap_end, window_lines):
    length = gap_end - gap_start + 1
    if length <= window_lines:
        return gap_start, gap_end
    midpoint = (gap_start + gap_end) // 2
    start = max(gap_start, midpoint - window_lines // 2)
    end = min(gap_end, start + window_lines - 1)
    if end - start + 1 < window_lines:
        start = max(gap_start, end - window_lines + 1)
    return start, end


def make_read_action(
    file_state,
    start,
    end,
    navigation,
    reason,
    source=None,
):
    return {
        "id": (
            f"read:{file_state['path']}:{start}-{end}:"
            f"{navigation}"
        ),
        "kind": "read_range",
        "path": file_state["path"],
        "start_line": int(start),
        "end_line": int(end),
        "navigation": navigation,
        "reason": reason,
        "source": source,
    }


def generate_file_actions(
    file_state,
    window_lines,
    max_jumps=DEFAULT_MAX_JUMPS,
):
    """Generate a bounded action space using coverage geometry only."""
    line_count = int(file_state["line_count"])
    coverage = merge_ranges(file_state["coverage"])
    if line_count <= 0:
        return [{
            "id": f"stop:{file_state['path']}",
            "kind": "stop_file",
            "path": file_state["path"],
            "reason": "the file is empty",
        }]

    reads = []
    seen = set()

    def add(start, end, navigation, reason, source=None):
        bounded = bounded_range(start, end, line_count)
        if bounded is None:
            return
        start, end = bounded
        key = (start, end)
        if key in seen or not fully_uncovered(
            start,
            end,
            coverage,
        ):
            return
        seen.add(key)
        reads.append(
            make_read_action(
                file_state,
                start,
                end,
                navigation,
                reason,
                source,
            )
        )

    if not coverage:
        add(
            1,
            min(line_count, window_lines),
            "seed_head",
            "probe the beginning of this unread file",
        )
        if line_count > window_lines:
            middle_start = max(
                1,
                line_count // 2 - window_lines // 2,
            )
            add(
                middle_start,
                middle_start + window_lines - 1,
                "seed_middle",
                "probe near the middle of this unread file",
            )
        if line_count > window_lines * 2:
            add(
                max(1, line_count - window_lines + 1),
                line_count,
                "seed_tail",
                "probe the end of this unread file",
            )
    else:
        # Expand mechanically around every range selected in the previous
        # epoch. These are runtime-history anchors, not semantic anchors.
        anchors = file_state.get("last_selected_ranges", [])
        if not anchors and file_state["observations"]:
            latest = file_state["observations"][-1]
            anchors = [[
                latest["start_line"],
                latest["end_line"],
            ]]

        for start, end in anchors:
            add(
                start - window_lines,
                start - 1,
                "expand_before",
                "read immediately before a range chosen last epoch",
                {"start_line": start, "end_line": end},
            )
            add(
                end + 1,
                end + window_lines,
                "expand_after",
                "read immediately after a range chosen last epoch",
                {"start_line": start, "end_line": end},
            )

        # Jump probes are purely geometric: midpoint of the largest unread
        # gaps. The harness never inspects the gap's text.
        gaps = sorted(
            unread_gaps(line_count, coverage),
            key=lambda item: (
                -(item[1] - item[0] + 1),
                item[0],
            ),
        )[:max_jumps]
        for index, (gap_start, gap_end) in enumerate(gaps, 1):
            start, end = gap_midpoint_window(
                gap_start,
                gap_end,
                window_lines,
            )
            add(
                start,
                end,
                "jump",
                (
                    f"probe midpoint of unread gap #{index} "
                    f"{gap_start}-{gap_end}"
                ),
                {
                    "gap_start": gap_start,
                    "gap_end": gap_end,
                },
            )

    reads.append({
        "id": f"stop:{file_state['path']}",
        "kind": "stop_file",
        "path": file_state["path"],
        "reason": (
            "stop exploring this file only when further reads are "
            "unlikely to materially improve localization for the goal"
        ),
    })
    return reads


def observation_view(
    file_state,
    char_budget=DEFAULT_DECISION_OBSERVATION_CHAR_BUDGET,
):
    """Bound model context mechanically; durable FileState keeps everything."""
    visible = []
    used = 0
    for item in reversed(file_state["observations"]):
        content = sanitize_source(item["content"])
        size = len(content)
        if visible and used + size > char_budget:
            continue
        if not visible and size > char_budget:
            content = content[-char_budget:]
            size = len(content)
        visible.append({
            "path": item["path"],
            "start_line": item["start_line"],
            "end_line": item["end_line"],
            "navigation": item["navigation"],
            "content": content,
        })
        used += size
        if used >= char_budget:
            break
    visible.reverse()
    return {
        "total_count": len(file_state["observations"]),
        "visible_count": len(visible),
        "omitted_count": (
            len(file_state["observations"]) - len(visible)
        ),
        "char_budget": char_budget,
        "used_chars": used,
        "items": visible,
    }


def exploration_view(file_state, limit=8):
    """Expose recent decision yield without interpreting source semantics."""
    threshold = float(file_state.get(
        "parallel_threshold",
        DEFAULT_PARALLEL_THRESHOLD,
    ))
    history = file_state.get("action_history", [])
    recent = []
    for item in history[-limit:]:
        scores = item.get("scores") or []
        max_read_utility = (
            max(float(score["score"]) for score in scores)
            if scores
            else None
        )
        recent.append({
            "epoch": item.get("epoch"),
            "control_choice": (
                item.get("stop_decision") or {}
            ).get("choice"),
            "max_read_utility": max_read_utility,
            "selection_mode": item.get("selection_mode"),
            "selected_ids": item.get("selected_ids", []),
        })

    low_yield_streak = 0
    for item in reversed(history):
        scores = item.get("scores") or []
        if not scores:
            break
        max_read_utility = max(
            float(score["score"]) for score in scores
        )
        if max_read_utility >= threshold:
            break
        low_yield_streak += 1

    return {
        "parallel_threshold": threshold,
        "recent_epochs": recent,
        "consecutive_low_utility_epochs": low_yield_streak,
    }


def decision_view(goal, file_state):
    coverage = merge_ranges(file_state["coverage"])
    return {
        "goal": goal,
        "phase": "file_range_runtime_v0",
        "file": {
            "path": file_state["path"],
            "phase1_score": file_state["phase1_score"],
            "line_count": file_state["line_count"],
            "coverage": [list(value) for value in coverage],
            "read_count": file_state["read_count"],
            "epoch": file_state["epoch"],
        },
        "exploration": exploration_view(file_state),
        "observations": observation_view(file_state),
    }


class SystemOneFileDecider(SystemOneDecider):
    def score_file_actions(self, goal, file_state, actions):
        questions = {}
        for index, action in enumerate(actions):
            qid = f"action_{index}"
            if action["kind"] == "stop_file":
                questions[qid] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "file": file_state["path"],
                        "question": (
                            "Score how useful executing StopFile would be as "
                            "the NEXT ACTION for achieving the localization "
                            "goal. StopFile means finalize this file now using "
                            "the observations already collected. Use the same "
                            "action-utility scale used for ReadRange actions. "
                            "Give StopFile a high score when the current "
                            "observations are already sufficient for a useful "
                            "final file-level result and the expected marginal "
                            "utility of more reading is low, redundant, or "
                            "mostly confirmatory. Full-file coverage and "
                            "certainty about every unread range are NOT "
                            "required. A clearly irrelevant file can also have "
                            "high StopFile utility. Give StopFile a low score "
                            "when another read has meaningful expected "
                            "information gain that could materially improve "
                            "the final result."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "Stopping now is a useful next action: finalize "
                            "with sufficient evidence because further reading "
                            "has low expected marginal utility."
                        ),
                        "false": (
                            "Stopping now is a poor next action: more reading "
                            "still has meaningful expected information gain "
                            "for the file-level localization result."
                        ),
                    },
                }
            else:
                questions[qid] = {
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
                            "Score how useful executing this exact ReadRange "
                            "would be as the next exploration action for "
                            "localizing content in this file relevant to the "
                            "goal."
                        ),
                    },
                    "criteria": {
                        "true": (
                            "This read is likely to add material information."
                        ),
                        "false": (
                            "This read is likely redundant or low-value."
                        ),
                    },
                }

        response, usage = self.send(
            "file_range_action_score",
            decision_view(goal, file_state),
            questions,
        )
        answers = response.get("answers", {})
        scored = []
        for index, action in enumerate(actions):
            answer = answers.get(f"action_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected file-action answer: {answer!r}"
                )
            scored.append({
                **action,
                "score": float(answer["noul"]),
            })
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        return scored, usage

    def decide_file_actions(self, goal, file_state, actions):
        """One request: Stop/Continue Choice + ReadRange Noul scores."""
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
                        "Choose whether to FINALIZE THIS FILE NOW or CONTINUE "
                        "EXPLORING IT. Stop does not require full-file coverage. "
                        "Choose stop when current observations already provide "
                        "enough evidence for a useful file-level localization "
                        "result, including enough evidence to conclude the "
                        "file is not useful, and more reading would mainly add "
                        "redundant detail or confirmation. Choose continue only "
                        "when another range has meaningful expected information "
                        "gain that could materially improve the final result."
                    ),
                },
                "criteria": {
                    "stop": {
                        "action": "StopFile",
                        "meaning": (
                            "Finalize this file now from current observations; "
                            "full coverage is not required."
                        ),
                    },
                    "continue": {
                        "action": "ContinueFile",
                        "meaning": (
                            "Keep exploring because another range can "
                            "materially improve the localization result."
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
                        "Score how useful executing this exact ReadRange "
                        "would be as the next exploration action for "
                        "localizing content in this file relevant to the goal."
                    ),
                },
                "criteria": {
                    "true": (
                        "This read is likely to add material information."
                    ),
                    "false": (
                        "This read is likely redundant or low-value."
                    ),
                },
            }

        response, usage = self.send(
            "file_range_control_and_actions",
            decision_view(goal, file_state),
            questions,
        )
        answers = response.get("answers", {})
        control = answers.get("control", {})
        if control.get("type") != "choice":
            raise RuntimeError(
                f"unexpected file-control answer: {control!r}"
            )
        choice = control.get("choice")
        if choice not in {"stop", "continue"}:
            raise RuntimeError(
                f"unexpected file-control choice: {choice!r}"
            )
        probabilities = control.get("probabilities", {})

        scored = []
        for index, action in enumerate(reads):
            answer = answers.get(f"read_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected file-read answer: {answer!r}"
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
        }
        return stop_decision, scored, usage

    def resolve_file_control_conflict(
        self,
        goal,
        file_state,
        stop_decision,
        scored_reads,
        threshold,
    ):
        """Reconcile control flow with the best concrete read when they disagree."""
        if not scored_reads:
            return stop_decision, empty_usage()

        best_read = scored_reads[0]
        conflict = None
        if (
            stop_decision["choice"] == "stop"
            and best_read["score"] >= threshold
        ):
            conflict = "stop_with_high_utility_read"
        elif (
            stop_decision["choice"] == "continue"
            and best_read["score"] < threshold
        ):
            conflict = "continue_without_high_utility_read"

        if conflict is None:
            return {
                **stop_decision,
                "reconciled": False,
                "read_authorized": False,
            }, empty_usage()

        response, usage = self.send(
            "file_range_control_conflict",
            decision_view(goal, file_state),
            {
                "resolution": {
                    "type": "choice",
                    "instructions": {
                        "goal": goal,
                        "file": file_state["path"],
                        "conflict": conflict,
                        "current_control": stop_decision,
                        "best_concrete_read": {
                            "path": best_read["path"],
                            "start_line": best_read["start_line"],
                            "end_line": best_read["end_line"],
                            "navigation": best_read["navigation"],
                            "utility": best_read["score"],
                        },
                        "question": (
                            "Resolve the conflict between the file-level "
                            "Stop/Continue decision and the utility of the "
                            "best concrete ReadRange. Choose StopFile when "
                            "the existing observations are sufficient and "
                            "this concrete read is not worth its additional "
                            "cost. Choose ReadRange only when executing this "
                            "specific best read can materially improve the "
                            "final file-level localization result."
                        ),
                    },
                    "criteria": {
                        "stop": {
                            "action": "StopFile",
                            "meaning": (
                                "Finalize the file from current evidence."
                            ),
                        },
                        "read": {
                            "action": "ReadRange",
                            "meaning": (
                                "Execute the displayed best concrete read."
                            ),
                        },
                    },
                },
            },
        )
        answer = response.get("answers", {}).get("resolution", {})
        if answer.get("type") != "choice":
            raise RuntimeError(
                f"unexpected conflict-resolution answer: {answer!r}"
            )
        choice = answer.get("choice")
        if choice not in {"stop", "read"}:
            raise RuntimeError(
                f"unexpected conflict-resolution choice: {choice!r}"
            )
        probabilities = answer.get("probabilities", {})
        return {
            **stop_decision,
            "choice": "stop" if choice == "stop" else "continue",
            "reconciled": True,
            "reconcile_reason": conflict,
            "reconcile_choice": choice,
            "reconcile_probability": float(
                probabilities.get(choice, 0.0) or 0.0
            ),
            "read_authorized": choice == "read",
        }, usage

    def score_file_evidence(
        self,
        goal,
        file_state,
        batch_size=DEFAULT_EVIDENCE_SCORE_BATCH_SIZE,
    ):
        """Post-loop result scoring; never affects navigation or stopping."""
        observations = file_state["observations"]
        if not observations:
            return [], empty_usage()

        total_usage = empty_usage()
        scored = []

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
                            "Does this observed range materially help localize "
                            "file content relevant to the goal?"
                        ),
                    },
                    "criteria": {
                        "true": (
                            "The range contains useful implementation evidence "
                            "or directly relevant context for the goal."
                        ),
                        "false": (
                            "The range does not materially contribute to the goal."
                        ),
                    },
                }

            try:
                response, usage = self.send(
                    "file_evidence_score",
                    {
                        "goal": goal,
                        "file": file_state["path"],
                        "phase": "post_navigation_result_scoring",
                    },
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
                        f"unexpected evidence answer: {answer!r}"
                    )
                out.append({
                    **item,
                    "relevance": float(answer["noul"]),
                })
            return out, usage

        for start in range(0, len(observations), batch_size):
            batch = observations[start:start + batch_size]
            current, usage = score_batch(batch)
            scored.extend(current)
            merge_usage(total_usage, usage)

        return scored, total_usage



class OfflineFileDecider:
    model = "offline-file-range-fixture"

    def __init__(self, trace):
        self.trace = trace

    def score_candidates(self, query, stage, candidates):
        return [
            {**item, "score": 0.9}
            for item in candidates
        ], empty_usage()

    def score_file_actions(self, goal, file_state, actions):
        scored = []
        for action in actions:
            if action["kind"] == "stop_file":
                score = 0.9 if file_state["read_count"] >= 2 else 0.1
            elif action["navigation"] in {
                "seed_head",
                "expand_after",
            }:
                score = 0.8
            else:
                score = 0.4
            scored.append({**action, "score": score})
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        return scored, empty_usage()

    def decide_file_actions(self, goal, file_state, actions):
        stop = next(
            item for item in actions
            if item["kind"] == "stop_file"
        )
        reads = [
            item for item in actions
            if item["kind"] == "read_range"
        ]
        should_stop = file_state["read_count"] >= 2
        decision = {
            **stop,
            "choice": "stop" if should_stop else "continue",
            "probability": 0.9,
            "stop_probability": 0.9 if should_stop else 0.1,
            "continue_probability": 0.1 if should_stop else 0.9,
            "confidence": 0.9,
        }
        scored = []
        for action in reads:
            score = (
                0.8
                if action["navigation"] in {
                    "seed_head",
                    "expand_after",
                }
                else 0.4
            )
            scored.append({**action, "score": score})
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        return decision, scored, empty_usage()

    def resolve_file_control_conflict(
        self,
        goal,
        file_state,
        stop_decision,
        scored_reads,
        threshold,
    ):
        if not scored_reads:
            return stop_decision, empty_usage()
        best = scored_reads[0]
        if (
            stop_decision["choice"] == "stop"
            and best["score"] >= threshold
        ):
            return {
                **stop_decision,
                "choice": "continue",
                "reconciled": True,
                "reconcile_reason": "stop_with_high_utility_read",
                "reconcile_choice": "read",
                "read_authorized": True,
            }, empty_usage()
        if (
            stop_decision["choice"] == "continue"
            and best["score"] < threshold
        ):
            return {
                **stop_decision,
                "choice": "stop",
                "reconciled": True,
                "reconcile_reason": "continue_without_high_utility_read",
                "reconcile_choice": "stop",
                "read_authorized": False,
            }, empty_usage()
        return {
            **stop_decision,
            "reconciled": False,
            "read_authorized": False,
        }, empty_usage()

    def score_file_evidence(self, goal, file_state):
        return [
            {**item, "relevance": 0.8}
            for item in file_state["observations"]
        ], empty_usage()


def select_file_actions_with_control(
    stop_decision,
    scored_reads,
    threshold,
):
    if stop_decision["choice"] == "stop":
        return [stop_decision], "model_stop"

    if not scored_reads:
        return [stop_decision], "action_space_exhausted"

    eligible = [
        item for item in scored_reads
        if item["score"] >= threshold
    ]
    if eligible:
        selected = []
        for item in eligible:
            if any(ranges_overlap(item, chosen) for chosen in selected):
                continue
            selected.append(item)
        if selected:
            return selected, "parallel_above_threshold"

    if stop_decision.get("read_authorized"):
        return [scored_reads[0]], "reconciled_top1"

    raise RuntimeError(
        "unreconciled ContinueFile decision has no ReadRange at or above "
        "the parallel threshold"
    )


def ranges_overlap(left, right):
    return not (
        left["end_line"] < right["start_line"]
        or left["start_line"] > right["end_line"]
    )


def select_file_actions(scored_actions, parallel_threshold):
    stop = next(
        item for item in scored_actions
        if item["kind"] == "stop_file"
    )
    reads = [
        item for item in scored_actions
        if item["kind"] == "read_range"
    ]

    if not reads:
        return [stop], "action_space_exhausted"

    best_read = reads[0]
    if (
        stop["score"] >= parallel_threshold
        and stop["score"] >= best_read["score"]
    ):
        return [stop], "model_stop"

    eligible = [
        item for item in reads
        if item["score"] >= parallel_threshold
    ]
    if eligible:
        # Threshold controls concurrency, but overlapping reads are conflicting
        # effects. Keep the highest-scored non-overlapping set greedily.
        selected = []
        for item in eligible:
            if any(ranges_overlap(item, chosen) for chosen in selected):
                continue
            selected.append(item)
        if selected:
            return selected, "parallel_above_threshold"

    return [best_read], "fallback_top1"



def new_file_state(root, candidate):
    stat = source_stat(root, candidate)
    if stat is None:
        return None
    return {
        "path": candidate["payload"]["path"],
        "phase1_score": candidate["score"],
        "line_count": stat["line_count"],
        "size_bytes": stat["size_bytes"],
        "extension": stat["extension"],
        "epoch": 0,
        "coverage": [],
        "observations": [],
        "last_selected_ranges": [],
        "read_count": 0,
        "termination": None,
        "action_history": [],
    }


def apply_reads(root, file_state, selected):
    observations = []
    selected_ranges = []
    for action in selected:
        observation = read_range(root, action)
        item = {
            "id": (
                f"{observation['path']}:"
                f"{observation['start_line']}-"
                f"{observation['end_line']}#"
                f"{len(file_state['observations']) + 1}"
            ),
            **observation,
            "navigation": action["navigation"],
            "selected_action_score": action["score"],
        }
        file_state["observations"].append(item)
        observations.append(item)
        selected_ranges.append([
            observation["start_line"],
            observation["end_line"],
        ])
        file_state["read_count"] += 1

    file_state["coverage"] = [
        list(value)
        for value in merge_ranges([
            *file_state["coverage"],
            *selected_ranges,
        ])
    ]
    file_state["last_selected_ranges"] = selected_ranges
    return observations


def run_file_runtime(
    root,
    goal,
    candidate,
    decider,
    trace,
    *,
    window_lines,
    parallel_threshold,
    max_jumps,
    max_file_epochs,
):
    usage = empty_usage()
    state = new_file_state(root, candidate)
    if state is None:
        return None, usage
    state["parallel_threshold"] = parallel_threshold

    trace.emit(
        "file_runtime_started",
        path=state["path"],
        phase1_score=state["phase1_score"],
        line_count=state["line_count"],
    )

    for epoch in range(1, max_file_epochs + 1):
        state["epoch"] = epoch
        actions = generate_file_actions(
            state,
            window_lines,
            max_jumps,
        )
        trace.emit(
            "file_action_space",
            path=state["path"],
            epoch=epoch,
            action_count=len(actions),
            actions=actions,
        )

        read_actions = [
            item for item in actions
            if item["kind"] == "read_range"
        ]
        if not read_actions:
            state["termination"] = "action_space_exhausted"
            trace.emit(
                "file_runtime_stopped",
                path=state["path"],
                epoch=epoch,
                reason="action_space_exhausted",
            )
            break

        stop_decision, scored, current = (
            decider.decide_file_actions(
                goal,
                state,
                actions,
            )
        )
        merge_usage(usage, current)
        stop_decision, current = (
            decider.resolve_file_control_conflict(
                goal,
                state,
                stop_decision,
                scored,
                parallel_threshold,
            )
        )
        merge_usage(usage, current)
        selected, mode = select_file_actions_with_control(
            stop_decision,
            scored,
            parallel_threshold,
        )

        state["action_history"].append({
            "epoch": epoch,
            "stop_decision": stop_decision,
            "scores": scored,
            "selected_ids": [item["id"] for item in selected],
            "selection_mode": mode,
        })
        trace.emit(
            "file_action_scores",
            path=state["path"],
            epoch=epoch,
            threshold=parallel_threshold,
            stop_decision=stop_decision,
            scores=scored,
            selected_ids=[item["id"] for item in selected],
            selection_mode=mode,
        )

        if selected[0]["kind"] == "stop_file":
            state["termination"] = mode
            trace.emit(
                "file_runtime_stopped",
                path=state["path"],
                epoch=epoch,
                reason=mode,
                stop_probability=selected[0].get(
                    "stop_probability"
                ),
            )
            break

        observations = apply_reads(
            root,
            state,
            selected,
        )
        trace.emit(
            "file_ranges_observed",
            path=state["path"],
            epoch=epoch,
            observations=observations,
        )
    else:
        state["termination"] = "budget_exhausted"
        trace.emit(
            "file_runtime_stopped",
            path=state["path"],
            epoch=max_file_epochs,
            reason="budget_exhausted",
        )

    evidence, current = decider.score_file_evidence(
        goal,
        state,
    )
    merge_usage(usage, current)
    state["evidence"] = evidence

    trace.emit(
        "file_runtime_completed",
        path=state["path"],
        termination=state["termination"],
        reads=state["read_count"],
        evidence=evidence,
    )
    return state, usage


def run_phase1(
    root,
    query,
    decider,
    trace,
    directory_threshold,
    file_threshold,
):
    usage = empty_usage()
    directory_candidates = directories(root)
    scored_dirs, current = decider.score_candidates(
        query,
        "directory",
        directory_candidates,
    )
    merge_usage(usage, current)
    selected_dirs = [
        item
        for item in scored_dirs
        if item["score"] >= directory_threshold
    ]

    file_candidates = files(root, selected_dirs)
    scored_files, current = decider.score_candidates(
        query,
        "file",
        file_candidates,
    )
    merge_usage(usage, current)
    selected_files = [
        item
        for item in scored_files
        if item["score"] >= file_threshold
    ]

    trace.emit(
        "phase1_completed",
        directories_exposed=len(directory_candidates),
        directories_selected=len(selected_dirs),
        files_exposed=len(file_candidates),
        files_selected=len(selected_files),
        files=selected_files,
    )
    return selected_dirs, selected_files, {
        **usage,
        "directories_exposed": len(directory_candidates),
        "directories_selected": len(selected_dirs),
        "files_exposed": len(file_candidates),
        "files_selected": len(selected_files),
    }


def canonical_file_results(
    file_states,
    evidence_threshold,
):
    files = []
    for state in file_states:
        evidence = [
            item
            for item in state.get("evidence", [])
            if item["relevance"] >= evidence_threshold
        ]
        if not evidence:
            continue
        evidence.sort(
            key=lambda item: (
                -item["relevance"],
                item["start_line"],
            )
        )
        file_score = max(item["relevance"] for item in evidence)
        files.append({
            "path": state["path"],
            "score": file_score,
            "phase1_score": state["phase1_score"],
            "termination": state["termination"],
            "read_count": state["read_count"],
            "coverage": state["coverage"],
            "evidence": [
                {
                    "start_line": item["start_line"],
                    "end_line": item["end_line"],
                    "score": item["relevance"],
                    "content": item["content"],
                    "navigation": item["navigation"],
                    "selected_action_score": item[
                        "selected_action_score"
                    ],
                }
                for item in sorted(
                    evidence,
                    key=lambda row: row["start_line"],
                )
            ],
        })
    files.sort(key=lambda item: (-item["score"], item["path"]))
    return files


def run(
    root,
    query,
    decider,
    trace,
    *,
    directory_threshold=DEFAULT_DIRECTORY_THRESHOLD,
    file_threshold=DEFAULT_FILE_THRESHOLD,
    window_lines=DEFAULT_WINDOW_LINES,
    parallel_threshold=DEFAULT_PARALLEL_THRESHOLD,
    evidence_threshold=DEFAULT_EVIDENCE_THRESHOLD,
    max_jumps=DEFAULT_MAX_JUMPS,
    max_file_epochs=DEFAULT_MAX_FILE_EPOCHS,
    subject_repository=None,
    subject_revision=None,
):
    started = time.perf_counter()
    selected_dirs, selected_files, phase1_metrics = run_phase1(
        root,
        query,
        decider,
        trace,
        directory_threshold,
        file_threshold,
    )
    usage = {
        key: phase1_metrics[key]
        for key in ("model_calls", "input_tokens", "output_tokens")
    }

    file_states = []
    for candidate in selected_files:
        state, current = run_file_runtime(
            root,
            query,
            candidate,
            decider,
            trace,
            window_lines=window_lines,
            parallel_threshold=parallel_threshold,
            max_jumps=max_jumps,
            max_file_epochs=max_file_epochs,
        )
        merge_usage(usage, current)
        if state is not None:
            file_states.append(state)

    result_files = canonical_file_results(
        file_states,
        evidence_threshold,
    )
    metrics = {
        **phase1_metrics,
        **usage,
        "file_runtimes": len(file_states),
        "file_model_stops": sum(
            state["termination"] == "model_stop"
            for state in file_states
        ),
        "file_space_exhausted": sum(
            state["termination"] == "action_space_exhausted"
            for state in file_states
        ),
        "file_budget_exhausted": sum(
            state["termination"] == "budget_exhausted"
            for state in file_states
        ),
        "reads_executed": sum(
            state["read_count"] for state in file_states
        ),
        "valuable_files": len(result_files),
        "evidence_regions": sum(
            len(item["evidence"]) for item in result_files
        ),
        "parallel_threshold": parallel_threshold,
        "evidence_threshold": evidence_threshold,
        "window_lines": window_lines,
        "max_jumps": max_jumps,
        "max_file_epochs": max_file_epochs,
        "elapsed_ms": round(
            (time.perf_counter() - started) * 1000,
            3,
        ),
    }

    result = {
        "query": query,
        "root": str(Path(root).resolve()),
        "model": decider.model,
        "architecture": "phase1_plus_independent_file_range_runtimes_v0",
        "thresholds": {
            "directory": directory_threshold,
            "file": file_threshold,
            "parallel_action": parallel_threshold,
            "result_evidence": evidence_threshold,
        },
        "directories": selected_dirs,
        "files": selected_files,
        "file_states": file_states,
        "result_files": result_files,
        "metrics": metrics,
    }
    if subject_repository and subject_revision:
        result["subject"] = {
            "repository": subject_repository,
            "revision": subject_revision,
        }
    result["localization_result"] = build_system_one_range_result(
        result,
        decider.model,
    )
    trace.emit("range_runtime_completed", result=result)
    return result


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
    parser.add_argument("--output-localization-json")
    parser.add_argument("--subject-repository")
    parser.add_argument("--subject-revision")
    parser.add_argument(
        "--typesafe-endpoint",
        default=os.getenv("TYPESAFE_API_URL", API_URL),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", MODEL),
    )
    args = parser.parse_args(argv)

    if args.window_lines < 1:
        parser.error("--window-lines must be >= 1")
    if args.max_jumps < 0:
        parser.error("--max-jumps must be >= 0")
    if args.max_file_epochs < 1:
        parser.error("--max-file-epochs must be >= 1")
    if not 0 <= args.parallel_threshold <= 1:
        parser.error("--parallel-threshold must be in [0,1]")
    if not 0 <= args.evidence_threshold <= 1:
        parser.error("--evidence-threshold must be in [0,1]")

    trace = Trace(args.trace_file)
    if args.offline_decider:
        decider = OfflineFileDecider(trace)
    else:
        key = os.getenv("TYPESAFE_API_KEY", "")
        if not key:
            print(
                "TYPESAFE_API_KEY is required unless "
                "--offline-decider is used.",
                file=sys.stderr,
            )
            return 2
        decider = SystemOneFileDecider(
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
        subject_repository=args.subject_repository,
        subject_revision=args.subject_revision,
    )

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output_json:
        Path(args.output_json).write_text(
            payload + "\n",
            encoding="utf-8",
        )
    if args.output_localization_json:
        Path(args.output_localization_json).write_text(
            json.dumps(
                result["localization_result"],
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
    if args.output_json:
        print(json.dumps(result["metrics"], ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
