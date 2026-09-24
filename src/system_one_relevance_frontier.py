#!/usr/bin/env python3
"""Adaptive Relevance Frontier Search v1.

Belief-driven coarse-to-fine code localization:
1. Build a coarse interval frontier whose leaves cover the whole file.
2. Read a bounded number of probes each round.
3. Re-score every observed frontier leaf after new observations arrive.
4. Generate new actions from missing frontier coverage, parent/child score
   gradients, high relevance, and score volatility.
5. Stop after frontier stabilization or at most ten rounds.
6. Split observed high-relevance probes into fine-grained candidates and let
   System One Choice retain the final evidence set.

The 0..1 frontier value is a relevance potential, not an additive probability.
The harness uses only range geometry and score history; it never parses source
semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

from localization_result import build_system_one_relevance_frontier_result
from system_one_code_locator import (
    API_URL,
    MODEL,
    SystemOneDecider,
    Trace,
    empty_usage,
    merge_ranges,
    merge_usage,
    read_range,
    sanitize_source,
    source_stat,
)
from system_one_range_runtime import (
    DEFAULT_DIRECTORY_THRESHOLD,
    DEFAULT_FILE_THRESHOLD,
    run_phase1,
)

DEFAULT_MAX_ROUNDS = 10
DEFAULT_MAX_ACTIONS_PER_ROUND = 3
DEFAULT_PROBE_LINES = 96
DEFAULT_TARGET_REGION_LINES = 48
DEFAULT_FINAL_WINDOW_LINES = 32
DEFAULT_REFINE_THRESHOLD = 0.72
DEFAULT_CANDIDATE_THRESHOLD = 0.55
DEFAULT_GRADIENT_THRESHOLD = 0.18
DEFAULT_VOLATILITY_THRESHOLD = 0.12
DEFAULT_STABLE_DELTA = 0.08
DEFAULT_STABLE_ROUNDS = 2
DEFAULT_MAX_FRONTIER_LEAVES = 24
DEFAULT_VIEW_CHAR_BUDGET = 48000
DEFAULT_FINAL_MAX_CANDIDATES = 24


def partition_range(start, end, parts):
    if start > end:
        return []
    length = end - start + 1
    count = max(1, min(int(parts), length))
    base, remainder = divmod(length, count)
    out = []
    cursor = start
    for index in range(count):
        width = base + (1 if index < remainder else 0)
        right = cursor + width - 1
        out.append((cursor, right))
        cursor = right + 1
    return out


def initial_region_count(line_count):
    if line_count <= 160:
        return 1
    if line_count <= 600:
        return 2
    if line_count <= 1500:
        return 3
    if line_count <= 3500:
        return 4
    return 6


def new_node(node_id, start, end, depth=0, parent_id=None):
    return {
        "id": node_id,
        "start_line": int(start),
        "end_line": int(end),
        "depth": int(depth),
        "parent_id": parent_id,
        "children": [],
        "status": "leaf",
        "score_history": [],
        "observation_ids": [],
        "last_scored_round": 0,
    }


def node_span(node):
    return int(node["end_line"]) - int(node["start_line"]) + 1


def current_score(node):
    history = node.get("score_history") or []
    return float(history[-1]) if history else None


def score_delta(node):
    history = node.get("score_history") or []
    if len(history) < 2:
        return 0.0
    return float(history[-1]) - float(history[-2])


def volatility(node):
    history = node.get("score_history") or []
    if len(history) < 2:
        return 0.0
    diffs = [
        abs(float(right) - float(left))
        for left, right in zip(history, history[1:])
    ]
    return max(diffs) if diffs else 0.0


def midpoint_probe(start, end, probe_lines):
    length = end - start + 1
    if length <= probe_lines:
        return start, end
    midpoint = (start + end) // 2
    left = max(start, midpoint - probe_lines // 2)
    right = min(end, left + probe_lines - 1)
    if right - left + 1 < probe_lines:
        left = max(start, right - probe_lines + 1)
    return left, right


def frontier_leaves(state):
    return [
        state["nodes"][node_id]
        for node_id in state["leaf_ids"]
        if state["nodes"][node_id]["status"] == "leaf"
    ]


def split_bounds(node):
    start = int(node["start_line"])
    end = int(node["end_line"])
    if start >= end:
        return None
    midpoint = (start + end) // 2
    return ((start, midpoint), (midpoint + 1, end))


def split_node(state, node_id):
    node = state["nodes"][node_id]
    if node["status"] != "leaf":
        return [state["nodes"][child] for child in node["children"]]
    bounds = split_bounds(node)
    if bounds is None:
        return []
    if len(state["leaf_ids"]) + 1 > state["max_frontier_leaves"]:
        return []

    children = []
    for suffix, (start, end) in zip(("L", "R"), bounds):
        child_id = f"{node_id}.{suffix}"
        child = new_node(
            child_id,
            start,
            end,
            node["depth"] + 1,
            node_id,
        )
        state["nodes"][child_id] = child
        children.append(child)

    node["status"] = "internal"
    node["children"] = [item["id"] for item in children]
    state["leaf_ids"] = [
        item for item in state["leaf_ids"] if item != node_id
    ] + [item["id"] for item in children]
    return children


def bounded_observation_view(state, char_budget=DEFAULT_VIEW_CHAR_BUDGET):
    visible = []
    used = 0
    for item in reversed(state["observations"]):
        content = sanitize_source(item["content"])
        size = len(content)
        if visible and used + size > char_budget:
            continue
        if not visible and size > char_budget:
            content = content[-char_budget:]
            size = len(content)
        visible.append({
            "id": item["id"],
            "node_id": item["node_id"],
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
        "total_count": len(state["observations"]),
        "visible_count": len(visible),
        "omitted_count": len(state["observations"]) - len(visible),
        "used_chars": used,
        "char_budget": char_budget,
        "items": visible,
    }


def frontier_summary(state):
    rows = []
    for node in frontier_leaves(state):
        parent = (
            state["nodes"].get(node["parent_id"])
            if node.get("parent_id")
            else None
        )
        rows.append({
            "id": node["id"],
            "range": [node["start_line"], node["end_line"]],
            "span": node_span(node),
            "depth": node["depth"],
            "observed": bool(node["observation_ids"]),
            "score": current_score(node),
            "score_history": [
                round(float(value), 6)
                for value in node.get("score_history", [])[-4:]
            ],
            "score_delta": round(score_delta(node), 6),
            "volatility": round(volatility(node), 6),
            "parent_id": node.get("parent_id"),
            "parent_score": current_score(parent) if parent else None,
        })
    rows.sort(key=lambda item: item["range"][0])
    return rows


def score_state_view(goal, state):
    return {
        "goal": goal,
        "phase": "adaptive_relevance_frontier_v1",
        "file": {
            "path": state["path"],
            "line_count": state["line_count"],
            "phase1_score": state["phase1_score"],
            "round": state["round"],
        },
        "frontier": frontier_summary(state),
        "observations": bounded_observation_view(state),
        "semantics": (
            "Frontier scores are relevance potentials on [0,1], not additive "
            "probability mass. Sibling scores do not need to sum to one. "
            "Re-score an interval when new observations elsewhere change how "
            "useful or likely-to-contain-material-evidence that interval is."
        ),
    }


class RelevanceFrontierDecider(SystemOneDecider):
    def score_frontier(self, goal, state):
        nodes = [
            node
            for node in frontier_leaves(state)
            if node["observation_ids"]
        ]
        if not nodes:
            return {}, empty_usage()

        questions = {}
        for index, node in enumerate(nodes):
            questions[f"node_{index}"] = {
                "type": "noul",
                "instructions": {
                    "goal": goal,
                    "path": state["path"],
                    "node_id": node["id"],
                    "range": [
                        node["start_line"],
                        node["end_line"],
                    ],
                    "previous_scores": node.get("score_history", [])[-4:],
                    "question": (
                        "Given the complete current frontier and all visible "
                        "observations, score this interval's RELEVANCE "
                        "POTENTIAL: how strongly does this interval itself "
                        "appear to contain material source evidence worth "
                        "retaining or refining for the task? This is not "
                        "probability mass and sibling scores need not sum to 1."
                    ),
                },
                "criteria": {
                    "true": (
                        "The interval contains, or increasingly appears to "
                        "contain, implementation/control-flow/state/dependency/"
                        "contract evidence material to the task."
                    ),
                    "false": (
                        "The interval is incidental, redundant, low-value, or "
                        "unlikely to improve localization if refined."
                    ),
                },
            }

        response, usage = self.send(
            "relevance_frontier_score",
            score_state_view(goal, state),
            questions,
        )
        answers = response.get("answers", {})
        scores = {}
        for index, node in enumerate(nodes):
            answer = answers.get(f"node_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected frontier score answer: {answer!r}"
                )
            scores[node["id"]] = float(answer["noul"])
        return scores, usage

    def finalize_choices(self, goal, state, candidates):
        if not candidates:
            return [], empty_usage()

        state_view = {
            "goal": goal,
            "phase": "relevance_frontier_final_resolution",
            "file": state["path"],
            "frontier": frontier_summary(state),
            "candidates": [
                {
                    "id": item["id"],
                    "range": [item["start_line"], item["end_line"]],
                    "frontier_score": item["score"],
                    "frontier_node_id": item["frontier_node_id"],
                    "content": sanitize_source(item["content"]),
                }
                for item in candidates
            ],
            "instruction": (
                "Resolve the final localization evidence. Prefer a minimal "
                "non-redundant set that preserves distinct material evidence. "
                "Do not keep a range merely because it is topically related."
            ),
        }
        questions = {}
        for index, item in enumerate(candidates):
            questions[f"candidate_{index}"] = {
                "type": "choice",
                "instructions": {
                    "goal": goal,
                    "candidate_id": item["id"],
                    "range": [item["start_line"], item["end_line"]],
                    "question": (
                        "Should this fine-grained candidate be retained in the "
                        "FINAL localization evidence set, considering all other "
                        "candidates and the complete frontier?"
                    ),
                },
                "criteria": {
                    "keep": (
                        "Retain because this range contributes distinct "
                        "material evidence needed downstream."
                    ),
                    "drop": (
                        "Drop because it is redundant, incidental, or not "
                        "material enough for the final result."
                    ),
                },
            }

        response, usage = self.send(
            "relevance_frontier_final_choice",
            state_view,
            questions,
        )
        answers = response.get("answers", {})
        selected = []
        for index, item in enumerate(candidates):
            answer = answers.get(f"candidate_{index}", {})
            if answer.get("type") != "choice":
                raise RuntimeError(
                    f"unexpected final choice answer: {answer!r}"
                )
            if answer.get("choice") == "keep":
                selected.append({
                    **item,
                    "final_choice": {
                        "choice": "keep",
                        "confidence": float(
                            answer.get("confidence", 0.0) or 0.0
                        ),
                        "probabilities": answer.get("probabilities", {}),
                    },
                })
        return selected, usage


class OfflineRelevanceFrontierDecider:
    model = "offline-relevance-frontier-fixture"

    def __init__(self, trace):
        self.trace = trace

    def score_candidates(self, query, stage, candidates):
        return [
            {**item, "score": 0.9}
            for item in candidates
        ], empty_usage()

    def score_frontier(self, goal, state):
        scores = {}
        for node in frontier_leaves(state):
            if not node["observation_ids"]:
                continue
            text = " ".join(
                state["observation_by_id"][oid]["content"]
                for oid in node["observation_ids"]
            )
            scores[node["id"]] = 0.9 if "TARGET" in text else 0.55
        return scores, empty_usage()

    def finalize_choices(self, goal, state, candidates):
        selected = [
            {
                **item,
                "final_choice": {
                    "choice": "keep",
                    "confidence": 1.0,
                    "probabilities": {"keep": 1.0, "drop": 0.0},
                },
            }
            for item in candidates
            if item["score"] >= 0.65
        ]
        return selected, empty_usage()


def new_file_state(root, candidate, max_frontier_leaves):
    stat = source_stat(root, candidate)
    if stat is None:
        return None
    line_count = int(stat["line_count"])
    count = initial_region_count(line_count)
    nodes = {}
    leaf_ids = []
    for index, (start, end) in enumerate(
        partition_range(1, line_count, count),
        1,
    ):
        node = new_node(f"c{index}", start, end)
        nodes[node["id"]] = node
        leaf_ids.append(node["id"])
    return {
        "path": candidate["payload"]["path"],
        "phase1_score": candidate["score"],
        "line_count": line_count,
        "round": 0,
        "nodes": nodes,
        "leaf_ids": leaf_ids,
        "observations": [],
        "observation_by_id": {},
        "action_history": [],
        "termination": None,
        "stable_rounds": 0,
        "previous_signature": None,
        "max_frontier_leaves": max_frontier_leaves,
    }


def append_observation(state, node, observation, navigation):
    oid = (
        f"{state['path']}:{observation['start_line']}-"
        f"{observation['end_line']}#{len(state['observations']) + 1}"
    )
    item = {
        "id": oid,
        "node_id": node["id"],
        "path": state["path"],
        "start_line": observation["start_line"],
        "end_line": observation["end_line"],
        "content": observation["content"],
        "navigation": navigation,
    }
    state["observations"].append(item)
    state["observation_by_id"][oid] = item
    node["observation_ids"].append(oid)
    return item


def deterministic_side(path, node_id, round_number):
    seed = hashlib.sha256(
        f"{path}:{node_id}:{round_number}".encode()
    ).hexdigest()
    return "L" if int(seed[:8], 16) % 2 == 0 else "R"


def random_rank(path, node_id, round_number):
    seed = hashlib.sha256(
        f"explore:{path}:{node_id}:{round_number}".encode()
    ).hexdigest()
    return int(seed[:16], 16)


def make_probe_action(node, kind, priority, reason, side=None, source=None):
    return {
        "kind": kind,
        "node_id": node["id"],
        "priority": float(priority),
        "reason": reason,
        "side": side,
        "source": source,
    }


def gradient_missing_actions(state, gradient_threshold):
    out = []
    for node in state["nodes"].values():
        if node["status"] != "internal" or len(node["children"]) != 2:
            continue
        parent_score = current_score(node)
        if parent_score is None:
            continue
        children = [state["nodes"][cid] for cid in node["children"]]
        observed = [
            child for child in children
            if current_score(child) is not None
        ]
        missing = [
            child for child in children
            if current_score(child) is None
        ]
        if len(observed) != 1 or len(missing) != 1:
            continue
        known = observed[0]
        gap = abs(parent_score - current_score(known))
        if gap < gradient_threshold:
            continue
        out.append(make_probe_action(
            missing[0],
            "resolve_gradient",
            120.0 + gap,
            (
                f"parent {node['id']} score={parent_score:.3f} but "
                f"sibling {known['id']} score={current_score(known):.3f}; "
                "probe the missing sibling to resolve the relevance gradient"
            ),
            source={
                "parent_id": node["id"],
                "known_child_id": known["id"],
                "gradient": gap,
            },
        ))
    return out


def generate_actions(
    state,
    *,
    max_actions,
    target_region_lines,
    refine_threshold,
    gradient_threshold,
    volatility_threshold,
):
    leaves = frontier_leaves(state)
    candidates = []

    candidates.extend(
        gradient_missing_actions(state, gradient_threshold)
    )

    # Missing frontier comes next. Initial coarse leaves receive a stronger
    # priority than newly-created child leaves so the whole file gets a
    # coarse relevance field before deep refinement dominates.
    for node in leaves:
        if node["observation_ids"]:
            continue
        priority = 100.0 if node["depth"] == 0 else 75.0
        candidates.append(make_probe_action(
            node,
            "missing_frontier",
            priority,
            "probe an unobserved frontier interval",
        ))

    refinable = [
        node for node in leaves
        if node["observation_ids"]
        and node_span(node) > target_region_lines * 2
    ]

    for node in refinable:
        score = current_score(node)
        if score is not None and score >= refine_threshold:
            candidates.append(make_probe_action(
                node,
                "refine_high",
                90.0 + score,
                (
                    f"refine high-relevance interval "
                    f"score={score:.3f}"
                ),
                side=deterministic_side(
                    state["path"], node["id"], state["round"]
                ),
            ))

        vol = volatility(node)
        if vol >= volatility_threshold:
            candidates.append(make_probe_action(
                node,
                "volatility_revisit",
                85.0 + vol,
                (
                    f"refine volatile interval; max score change={vol:.3f}"
                ),
                side=deterministic_side(
                    state["path"],
                    node["id"],
                    state["round"] + 17,
                ),
            ))

    # One low-priority deterministic stochastic exploration candidate guards
    # against a false-negative frontier collapse.
    explore_pool = [
        node for node in refinable
        if current_score(node) is not None
    ]
    if explore_pool:
        node = min(
            explore_pool,
            key=lambda item: random_rank(
                state["path"], item["id"], state["round"]
            ),
        )
        candidates.append(make_probe_action(
            node,
            "stochastic_revisit",
            10.0,
            "sample a previously observed interval to guard against belief collapse",
            side=deterministic_side(
                state["path"], node["id"], state["round"] + 31
            ),
        ))

    # Keep at most one refinement action per parent leaf.
    candidates.sort(
        key=lambda item: (
            -item["priority"],
            item["node_id"],
            item["kind"],
        )
    )
    selected = []
    refined_parents = set()
    selected_nodes = set()
    for item in candidates:
        if len(selected) >= max_actions:
            break
        node_id = item["node_id"]
        if item["kind"] in {
            "refine_high",
            "volatility_revisit",
            "stochastic_revisit",
        }:
            if node_id in refined_parents:
                continue
            refined_parents.add(node_id)
        else:
            if node_id in selected_nodes:
                continue
            selected_nodes.add(node_id)
        selected.append(item)
    return selected


def execute_action(root, state, action, probe_lines):
    node = state["nodes"][action["node_id"]]
    target = node
    navigation = action["kind"]

    if action["kind"] in {
        "refine_high",
        "volatility_revisit",
        "stochastic_revisit",
    }:
        children = split_node(state, node["id"])
        if not children:
            return None
        wanted = action.get("side") or "L"
        target = next(
            child for child in children
            if child["id"].endswith(f".{wanted}")
        )
        navigation = action["kind"]

    start, end = midpoint_probe(
        target["start_line"],
        target["end_line"],
        probe_lines,
    )
    observation = read_range(
        root,
        {
            "path": state["path"],
            "start_line": start,
            "end_line": end,
        },
    )
    item = append_observation(
        state,
        target,
        observation,
        navigation,
    )
    return {
        "action": action,
        "target_node_id": target["id"],
        "observation": item,
    }


def apply_scores(state, scores):
    for node_id, score in scores.items():
        node = state["nodes"][node_id]
        node["score_history"].append(float(score))
        node["last_scored_round"] = state["round"]


def frontier_signature(state, threshold):
    return tuple(
        (
            node["start_line"],
            node["end_line"],
        )
        for node in sorted(
            frontier_leaves(state),
            key=lambda item: item["start_line"],
        )
        if current_score(node) is not None
        and current_score(node) >= threshold
    )


def frontier_max_delta(state):
    return max(
        [abs(score_delta(node)) for node in frontier_leaves(state)]
        or [0.0]
    )


def update_stability(state, threshold, stable_delta):
    signature = frontier_signature(state, threshold)
    max_delta = frontier_max_delta(state)
    all_observed = all(
        node["observation_ids"]
        for node in frontier_leaves(state)
    )
    if (
        all_observed
        and signature == state["previous_signature"]
        and max_delta <= stable_delta
    ):
        state["stable_rounds"] += 1
    else:
        state["stable_rounds"] = 0
    state["previous_signature"] = signature
    return {
        "signature": [list(item) for item in signature],
        "max_delta": max_delta,
        "all_frontier_observed": all_observed,
        "stable_rounds": state["stable_rounds"],
    }


def unique_source_coverage(state):
    ranges = [
        (item["start_line"], item["end_line"])
        for item in state["observations"]
    ]
    return sum(
        right - left + 1
        for left, right in merge_ranges(ranges)
    )


def observed_frontier_coverage(state):
    total = max(1, int(state["line_count"]))
    covered = sum(
        node_span(node)
        for node in frontier_leaves(state)
        if node["observation_ids"]
    )
    return min(1.0, covered / total)


def line_map(content):
    out = {}
    for line in content.splitlines():
        prefix, sep, value = line.partition(": ")
        if not sep:
            continue
        try:
            out[int(prefix)] = value
        except ValueError:
            continue
    return out


def fine_candidates(
    state,
    *,
    candidate_threshold,
    final_window_lines,
    max_candidates,
):
    leaves = [
        node for node in frontier_leaves(state)
        if current_score(node) is not None
        and node["observation_ids"]
    ]
    chosen = [
        node for node in leaves
        if current_score(node) >= candidate_threshold
    ]
    if not chosen:
        chosen = sorted(
            leaves,
            key=lambda node: -current_score(node),
        )[:2]

    candidates = []
    seen = set()
    for node in sorted(
        chosen,
        key=lambda item: (-current_score(item), item["start_line"]),
    ):
        for oid in node["observation_ids"]:
            observation = state["observation_by_id"][oid]
            start = observation["start_line"]
            end = observation["end_line"]
            lines = line_map(observation["content"])
            for left, right in partition_range(
                start,
                end,
                max(1, (end - start + final_window_lines) // final_window_lines),
            ):
                key = (left, right)
                if key in seen:
                    continue
                seen.add(key)
                content = "\n".join(
                    f"{number}: {lines[number]}"
                    for number in range(left, right + 1)
                    if number in lines
                )
                candidates.append({
                    "id": f"final:{state['path']}:{left}-{right}",
                    "start_line": left,
                    "end_line": right,
                    "score": current_score(node),
                    "content": content,
                    "frontier_node_id": node["id"],
                    "observation_id": oid,
                    "score_history": [
                        float(value)
                        for value in node["score_history"]
                    ],
                    "navigation": observation["navigation"],
                })

    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["start_line"],
            item["end_line"],
        )
    )
    return candidates[:max_candidates]


def merge_selected_candidates(selected):
    # Preserve fine-grained choices. Only exact duplicates are eliminated;
    # adjacent candidates may represent distinct evidence and remain separate.
    out = []
    seen = set()
    for item in sorted(
        selected,
        key=lambda row: (row["start_line"], row["end_line"]),
    ):
        key = (item["start_line"], item["end_line"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def run_frontier_file(
    root,
    goal,
    candidate,
    decider,
    trace,
    *,
    max_rounds=DEFAULT_MAX_ROUNDS,
    max_actions_per_round=DEFAULT_MAX_ACTIONS_PER_ROUND,
    probe_lines=DEFAULT_PROBE_LINES,
    target_region_lines=DEFAULT_TARGET_REGION_LINES,
    final_window_lines=DEFAULT_FINAL_WINDOW_LINES,
    refine_threshold=DEFAULT_REFINE_THRESHOLD,
    candidate_threshold=DEFAULT_CANDIDATE_THRESHOLD,
    gradient_threshold=DEFAULT_GRADIENT_THRESHOLD,
    volatility_threshold=DEFAULT_VOLATILITY_THRESHOLD,
    stable_delta=DEFAULT_STABLE_DELTA,
    stable_rounds=DEFAULT_STABLE_ROUNDS,
    max_frontier_leaves=DEFAULT_MAX_FRONTIER_LEAVES,
    final_max_candidates=DEFAULT_FINAL_MAX_CANDIDATES,
):
    usage = empty_usage()
    state = new_file_state(root, candidate, max_frontier_leaves)
    if state is None:
        return None, usage

    trace.emit(
        "relevance_frontier_file_started",
        path=state["path"],
        line_count=state["line_count"],
        initial_frontier=frontier_summary(state),
    )

    for round_number in range(1, max_rounds + 1):
        state["round"] = round_number
        actions = generate_actions(
            state,
            max_actions=max_actions_per_round,
            target_region_lines=target_region_lines,
            refine_threshold=refine_threshold,
            gradient_threshold=gradient_threshold,
            volatility_threshold=volatility_threshold,
        )
        if not actions:
            state["termination"] = "frontier_exhausted"
            break

        executed = []
        for action in actions:
            result = execute_action(
                root,
                state,
                action,
                probe_lines,
            )
            if result is not None:
                executed.append(result)

        if not executed:
            state["termination"] = "frontier_exhausted"
            break

        scores, current = decider.score_frontier(goal, state)
        merge_usage(usage, current)
        apply_scores(state, scores)
        stability = update_stability(
            state,
            candidate_threshold,
            stable_delta,
        )

        snapshot = {
            "round": round_number,
            "actions": actions,
            "executed": [
                {
                    "kind": item["action"]["kind"],
                    "source_node_id": item["action"]["node_id"],
                    "target_node_id": item["target_node_id"],
                    "range": [
                        item["observation"]["start_line"],
                        item["observation"]["end_line"],
                    ],
                }
                for item in executed
            ],
            "frontier": frontier_summary(state),
            "stability": stability,
        }
        state["action_history"].append(snapshot)
        trace.emit(
            "relevance_frontier_round_completed",
            path=state["path"],
            **snapshot,
        )

        next_actions = generate_actions(
            state,
            max_actions=max_actions_per_round,
            target_region_lines=target_region_lines,
            refine_threshold=refine_threshold,
            gradient_threshold=gradient_threshold,
            volatility_threshold=volatility_threshold,
        )
        non_stochastic = [
            item for item in next_actions
            if item["kind"] != "stochastic_revisit"
        ]
        if (
            stability["stable_rounds"] >= stable_rounds
            and not non_stochastic
        ):
            state["termination"] = "frontier_stable"
            break
    else:
        state["termination"] = "round_budget_exhausted"

    candidates = fine_candidates(
        state,
        candidate_threshold=candidate_threshold,
        final_window_lines=final_window_lines,
        max_candidates=final_max_candidates,
    )
    selected, current = decider.finalize_choices(
        goal,
        state,
        candidates,
    )
    merge_usage(usage, current)
    state["final_candidates"] = candidates
    state["evidence"] = merge_selected_candidates(selected)
    state["frontier_coverage"] = observed_frontier_coverage(state)
    state["source_coverage"] = (
        unique_source_coverage(state) / max(1, state["line_count"])
    )

    trace.emit(
        "relevance_frontier_file_completed",
        path=state["path"],
        termination=state["termination"],
        rounds=state["round"],
        observations=len(state["observations"]),
        frontier_coverage=state["frontier_coverage"],
        source_coverage=state["source_coverage"],
        final_candidates=len(candidates),
        evidence=len(state["evidence"]),
    )
    return state, usage


def canonical_results(file_states):
    files = []
    for state in file_states:
        evidence = state.get("evidence", [])
        if not evidence:
            continue
        files.append({
            "path": state["path"],
            "score": max(item["score"] for item in evidence),
            "phase1_score": state["phase1_score"],
            "termination": state["termination"],
            "rounds": state["round"],
            "frontier_coverage": state["frontier_coverage"],
            "source_coverage": state["source_coverage"],
            "evidence": evidence,
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
    max_rounds=DEFAULT_MAX_ROUNDS,
    max_actions_per_round=DEFAULT_MAX_ACTIONS_PER_ROUND,
    probe_lines=DEFAULT_PROBE_LINES,
    target_region_lines=DEFAULT_TARGET_REGION_LINES,
    final_window_lines=DEFAULT_FINAL_WINDOW_LINES,
    refine_threshold=DEFAULT_REFINE_THRESHOLD,
    candidate_threshold=DEFAULT_CANDIDATE_THRESHOLD,
    gradient_threshold=DEFAULT_GRADIENT_THRESHOLD,
    volatility_threshold=DEFAULT_VOLATILITY_THRESHOLD,
    stable_delta=DEFAULT_STABLE_DELTA,
    stable_rounds=DEFAULT_STABLE_ROUNDS,
    max_frontier_leaves=DEFAULT_MAX_FRONTIER_LEAVES,
    final_max_candidates=DEFAULT_FINAL_MAX_CANDIDATES,
    subject_repository=None,
    subject_revision=None,
):
    started = time.perf_counter()
    directories, selected_files, phase1_metrics = run_phase1(
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
        state, current = run_frontier_file(
            root,
            query,
            candidate,
            decider,
            trace,
            max_rounds=max_rounds,
            max_actions_per_round=max_actions_per_round,
            probe_lines=probe_lines,
            target_region_lines=target_region_lines,
            final_window_lines=final_window_lines,
            refine_threshold=refine_threshold,
            candidate_threshold=candidate_threshold,
            gradient_threshold=gradient_threshold,
            volatility_threshold=volatility_threshold,
            stable_delta=stable_delta,
            stable_rounds=stable_rounds,
            max_frontier_leaves=max_frontier_leaves,
            final_max_candidates=final_max_candidates,
        )
        merge_usage(usage, current)
        if state is not None:
            file_states.append(state)

    result_files = canonical_results(file_states)
    metrics = {
        **phase1_metrics,
        **usage,
        "file_runtimes": len(file_states),
        "observations": sum(
            len(state["observations"]) for state in file_states
        ),
        "reads_executed": sum(
            len(state["observations"]) for state in file_states
        ),
        "valuable_files": len(result_files),
        "evidence_regions": sum(
            len(item["evidence"]) for item in result_files
        ),
        "frontier_stable": sum(
            state["termination"] == "frontier_stable"
            for state in file_states
        ),
        "frontier_exhausted": sum(
            state["termination"] == "frontier_exhausted"
            for state in file_states
        ),
        "round_budget_exhausted": sum(
            state["termination"] == "round_budget_exhausted"
            for state in file_states
        ),
        "mean_frontier_coverage": (
            sum(state["frontier_coverage"] for state in file_states)
            / len(file_states)
            if file_states else 0.0
        ),
        "mean_source_coverage": (
            sum(state["source_coverage"] for state in file_states)
            / len(file_states)
            if file_states else 0.0
        ),
        "max_rounds": max_rounds,
        "max_actions_per_round": max_actions_per_round,
        "elapsed_ms": round(
            (time.perf_counter() - started) * 1000,
            3,
        ),
    }

    result = {
        "query": query,
        "root": str(Path(root).resolve()),
        "model": decider.model,
        "architecture": "adaptive_relevance_frontier_search_v1",
        "parameters": {
            "max_rounds": max_rounds,
            "max_actions_per_round": max_actions_per_round,
            "probe_lines": probe_lines,
            "target_region_lines": target_region_lines,
            "final_window_lines": final_window_lines,
            "refine_threshold": refine_threshold,
            "candidate_threshold": candidate_threshold,
            "gradient_threshold": gradient_threshold,
            "volatility_threshold": volatility_threshold,
            "stable_delta": stable_delta,
            "stable_rounds": stable_rounds,
            "max_frontier_leaves": max_frontier_leaves,
            "final_max_candidates": final_max_candidates,
        },
        "directories": directories,
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
    result["localization_result"] = build_system_one_relevance_frontier_result(
        result,
        decider.model,
    )
    trace.emit("relevance_frontier_completed", result=result)
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
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
    )
    parser.add_argument(
        "--max-actions-per-round",
        type=int,
        default=DEFAULT_MAX_ACTIONS_PER_ROUND,
    )
    parser.add_argument(
        "--probe-lines",
        type=int,
        default=DEFAULT_PROBE_LINES,
    )
    parser.add_argument(
        "--target-region-lines",
        type=int,
        default=DEFAULT_TARGET_REGION_LINES,
    )
    parser.add_argument(
        "--final-window-lines",
        type=int,
        default=DEFAULT_FINAL_WINDOW_LINES,
    )
    parser.add_argument(
        "--refine-threshold",
        type=float,
        default=DEFAULT_REFINE_THRESHOLD,
    )
    parser.add_argument(
        "--candidate-threshold",
        type=float,
        default=DEFAULT_CANDIDATE_THRESHOLD,
    )
    parser.add_argument(
        "--gradient-threshold",
        type=float,
        default=DEFAULT_GRADIENT_THRESHOLD,
    )
    parser.add_argument(
        "--volatility-threshold",
        type=float,
        default=DEFAULT_VOLATILITY_THRESHOLD,
    )
    parser.add_argument(
        "--stable-delta",
        type=float,
        default=DEFAULT_STABLE_DELTA,
    )
    parser.add_argument(
        "--stable-rounds",
        type=int,
        default=DEFAULT_STABLE_ROUNDS,
    )
    parser.add_argument(
        "--max-frontier-leaves",
        type=int,
        default=DEFAULT_MAX_FRONTIER_LEAVES,
    )
    parser.add_argument(
        "--final-max-candidates",
        type=int,
        default=DEFAULT_FINAL_MAX_CANDIDATES,
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

    trace = Trace(args.trace_file)
    if args.offline_decider:
        decider = OfflineRelevanceFrontierDecider(trace)
    else:
        key = os.getenv("TYPESAFE_API_KEY", "")
        if not key:
            print(
                "TYPESAFE_API_KEY is required unless --offline-decider is used.",
                file=sys.stderr,
            )
            return 2
        decider = RelevanceFrontierDecider(
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
        max_rounds=args.max_rounds,
        max_actions_per_round=args.max_actions_per_round,
        probe_lines=args.probe_lines,
        target_region_lines=args.target_region_lines,
        final_window_lines=args.final_window_lines,
        refine_threshold=args.refine_threshold,
        candidate_threshold=args.candidate_threshold,
        gradient_threshold=args.gradient_threshold,
        volatility_threshold=args.volatility_threshold,
        stable_delta=args.stable_delta,
        stable_rounds=args.stable_rounds,
        max_frontier_leaves=args.max_frontier_leaves,
        final_max_candidates=args.final_max_candidates,
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
    if args.output_json or args.output_localization_json:
        print(json.dumps(result["metrics"], ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


class ChoiceRelevanceFrontierDecider(RelevanceFrontierDecider):
    """Phase-0 + Choice-policy frontier runtime.

    Phase 0 is an independent coarse scan: every depth-0 region is observed
    exactly once before adaptive refinement is allowed. Phase 1 exposes the
    harness-generated legal actions to one Choice question. Noul scores remain
    auxiliary value signals for already-observed regions.
    """

    def choose_next_action(self, goal, state, actions):
        if not actions:
            raise RuntimeError("cannot choose from an empty frontier action space")

        action_by_id = {}
        action_views = []
        for index, action in enumerate(actions):
            action_id = f"a{index + 1}"
            action_by_id[action_id] = action
            node = state["nodes"].get(action["node_id"])
            action_views.append({
                "id": action_id,
                "kind": action["kind"],
                "node_id": action["node_id"],
                "range": (
                    [node["start_line"], node["end_line"]]
                    if node is not None
                    else [1, state["line_count"]]
                ),
                "priority_hint": action["priority"],
                "reason": action["reason"],
                "source": action.get("source"),
            })

        response, usage = self.send(
            "relevance_frontier_choice_policy",
            score_state_view(goal, state),
            {
                "next_action": {
                    "type": "choice",
                    "instructions": {
                        "goal": goal,
                        "file": state["path"],
                        "phase": "adaptive_frontier_policy",
                        "question": (
                            "Choose the SINGLE next exploration action from the "
                            "legal action set. The harness owns all effects and "
                            "will execute exactly the selected action. Prefer "
                            "global coverage when relevant, then evidence "
                            "completion/refinement, and choose stop only when "
                            "current evidence is sufficient."
                        ),
                        "actions": action_views,
                    },
                    "criteria": {
                        action_id: (
                            f"Select this legal action: {action['kind']} on "
                            f"{action['node_id']}."
                        )
                        for action_id, action in action_by_id.items()
                    },
                }
            },
        )
        answer = response.get("answers", {}).get("next_action", {})
        if answer.get("type") != "choice":
            raise RuntimeError(
                f"unexpected frontier policy answer: {answer!r}"
            )
        chosen_id = answer.get("choice")
        if chosen_id not in action_by_id:
            raise RuntimeError(
                f"frontier policy selected unknown action: {chosen_id!r}"
            )

        return {
            "action": action_by_id[chosen_id],
            "choice": chosen_id,
            "confidence": float(
                answer.get("confidence", 0.0) or 0.0
            ),
            "probabilities": answer.get("probabilities", {}),
        }, usage



class OfflineChoiceRelevanceFrontierDecider(
    ChoiceRelevanceFrontierDecider
):
    model = "offline-choice-relevance-frontier-fixture"

    def __init__(self, trace):
        self.trace = trace

    def score_frontier(self, goal, state):
        scores = {}
        for node in frontier_leaves(state):
            if not node["observation_ids"]:
                continue
            text = " ".join(
                state["observation_by_id"][oid]["content"]
                for oid in node["observation_ids"]
            )
            scores[node["id"]] = 0.9 if "TARGET" in text else 0.55
        return scores, empty_usage()

    def choose_next_action(self, goal, state, actions):
        ranked = sorted(
            actions,
            key=lambda item: (
                -float(item["priority"]),
                item["node_id"],
                item["kind"],
            ),
        )
        selected = ranked[0]
        scores = {}
        for node in frontier_leaves(state):
            if not node["observation_ids"]:
                continue
            text = " ".join(
                state["observation_by_id"][oid]["content"]
                for oid in node["observation_ids"]
            )
            scores[node["id"]] = 0.9 if "TARGET" in text else 0.55
        return {
            "action": selected,
            "choice": selected["kind"] + ":" + selected["node_id"],
            "confidence": 1.0,
            "probabilities": {},
        }, scores, empty_usage()


def phase0_coarse_scan(root, goal, state, decider, trace, probe_lines):
    coarse = [
        node for node in frontier_leaves(state)
        if node["depth"] == 0
    ]
    executed = []
    for node in coarse:
        action = make_probe_action(
            node,
            "coarse_probe",
            100.0,
            "phase0: establish the initial full-file coarse relevance field",
        )
        result = execute_action(
            root,
            state,
            action,
            probe_lines,
        )
        if result is not None:
            executed.append(result)

    if len(executed) != len(coarse):
        raise RuntimeError(
            "phase0 coarse scan failed to observe every depth-0 region"
        )

    scores, usage = decider.score_frontier(goal, state)
    apply_scores(state, scores)
    state["phase0"] = {
        "kind": "coarse_scan",
        "regions": [
            {
                "id": node["id"],
                "range": [node["start_line"], node["end_line"]],
                "score": current_score(node),
            }
            for node in coarse
        ],
        "all_regions_observed": True,
        "reads": len(executed),
    }
    trace.emit(
        "relevance_frontier_phase0_completed",
        path=state["path"],
        regions=state["phase0"]["regions"],
        reads=len(executed),
    )
    return usage


def run_frontier_file_phase0_choice(
    root,
    goal,
    candidate,
    decider,
    trace,
    *,
    max_rounds=10,
    probe_lines=96,
    target_region_lines=48,
    final_window_lines=32,
    refine_threshold=0.72,
    candidate_threshold=0.55,
    gradient_threshold=0.18,
    volatility_threshold=0.12,
    stable_delta=0.08,
    stable_rounds=2,
    max_frontier_leaves=24,
    final_max_candidates=24,
):
    usage = empty_usage()
    state = new_file_state(root, candidate, max_frontier_leaves)
    if state is None:
        return None, usage

    trace.emit(
        "relevance_frontier_phase0_choice_file_started",
        path=state["path"],
        line_count=state["line_count"],
        initial_frontier=frontier_summary(state),
    )

    current = phase0_coarse_scan(
        root,
        goal,
        state,
        decider,
        trace,
        probe_lines,
    )
    merge_usage(usage, current)

    if not state.get("phase0", {}).get("all_regions_observed"):
        raise RuntimeError("phase0 coarse bootstrap invariant failed")

    for round_number in range(1, max_rounds + 1):
        state["round"] = round_number
        actions = generate_actions(
            state,
            max_actions=1,
            target_region_lines=target_region_lines,
            refine_threshold=refine_threshold,
            gradient_threshold=gradient_threshold,
            volatility_threshold=volatility_threshold,
        )
        actions.append({
            "kind": "stop_frontier",
            "node_id": "file",
            "priority": 0.0,
            "reason": (
                "finalize when current coarse-to-fine evidence is sufficient "
                "and remaining actions have low expected information gain"
            ),
            "side": None,
            "source": None,
        })

        # Stop is a file-level action and has no node in the frontier.
        policy, scores, current = decider.choose_next_action(
            goal,
            state,
            actions,
        )
        merge_usage(usage, current)
        apply_scores(state, scores)

        chosen = policy["action"]
        if chosen["kind"] == "stop_frontier":
            state["termination"] = "model_stop"
            state["policy_stop"] = policy
            trace.emit(
                "relevance_frontier_phase1_stop",
                path=state["path"],
                round=round_number,
                policy=policy,
                frontier=frontier_summary(state),
            )
            break

        result = execute_action(
            root,
            state,
            chosen,
            probe_lines,
        )
        if result is None:
            state["termination"] = "frontier_exhausted"
            break

        # Re-score after the new observation so the next Choice sees updated
        # value state. This is intentionally a separate policy epoch.
        rescored, current = decider.score_frontier(goal, state)
        merge_usage(usage, current)
        apply_scores(state, rescored)

        stability = update_stability(
            state,
            candidate_threshold,
            stable_delta,
        )
        snapshot = {
            "round": round_number,
            "policy": policy,
            "executed": [{
                "kind": chosen["kind"],
                "source_node_id": chosen["node_id"],
                "target_node_id": result["target_node_id"],
                "range": [
                    result["observation"]["start_line"],
                    result["observation"]["end_line"],
                ],
            }],
            "frontier": frontier_summary(state),
            "stability": stability,
        }
        state["action_history"].append(snapshot)
        trace.emit(
            "relevance_frontier_phase1_round_completed",
            path=state["path"],
            **snapshot,
        )

        next_actions = generate_actions(
            state,
            max_actions=1,
            target_region_lines=target_region_lines,
            refine_threshold=refine_threshold,
            gradient_threshold=gradient_threshold,
            volatility_threshold=volatility_threshold,
        )
        if (
            stability["stable_rounds"] >= stable_rounds
            and not next_actions
        ):
            state["termination"] = "frontier_stable"
            break
    else:
        state["termination"] = "round_budget_exhausted"

    candidates = fine_candidates(
        state,
        candidate_threshold=candidate_threshold,
        final_window_lines=final_window_lines,
        max_candidates=final_max_candidates,
    )
    selected, current = decider.finalize_choices(
        goal,
        state,
        candidates,
    )
    merge_usage(usage, current)
    state["final_candidates"] = candidates
    state["evidence"] = merge_selected_candidates(selected)
    state["frontier_coverage"] = observed_frontier_coverage(state)
    state["source_coverage"] = (
        unique_source_coverage(state) / max(1, state["line_count"])
    )

    trace.emit(
        "relevance_frontier_phase0_choice_file_completed",
        path=state["path"],
        termination=state["termination"],
        rounds=state["round"],
        phase0=state.get("phase0"),
        observations=len(state["observations"]),
        frontier_coverage=state["frontier_coverage"],
        source_coverage=state["source_coverage"],
        final_candidates=len(candidates),
        evidence=len(state["evidence"]),
    )
    return state, usage


def run_frontier_file_phase0_choice_v2(
    root,
    goal,
    candidate,
    decider,
    trace,
    *,
    max_rounds=10,
    max_actions_per_choice=6,
    probe_lines=112,
    target_region_lines=48,
    final_window_lines=32,
    refine_threshold=0.72,
    candidate_threshold=0.55,
    gradient_threshold=0.15,
    volatility_threshold=0.10,
    stable_delta=0.06,
    stable_rounds=2,
    max_frontier_leaves=24,
    final_max_candidates=24,
):
    """Phase 0 coarse field + Choice policy + periodic value refresh.

    Phase 0 establishes the only initial relevance distribution. Phase 1 then
    lets Choice select one action from a larger harness-generated action set.
    After each executed action the value field is refreshed before the next
    policy epoch. This deliberately separates policy (Choice) from value
    estimation (Noul) instead of asking independent Noul questions to decide
    the next action.
    """
    usage = empty_usage()
    state = new_file_state(root, candidate, max_frontier_leaves)
    if state is None:
        return None, usage

    trace.emit(
        "relevance_frontier_phase0_choice_v2_started",
        path=state["path"],
        line_count=state["line_count"],
        initial_frontier=frontier_summary(state),
    )

    current = phase0_coarse_scan(
        root,
        goal,
        state,
        decider,
        trace,
        probe_lines,
    )
    merge_usage(usage, current)
    state["coarse_coverage"] = 1.0

    if not state.get("phase0", {}).get("all_regions_observed"):
        raise RuntimeError("phase0 coarse bootstrap invariant failed")

    for round_number in range(1, max_rounds + 1):
        state["round"] = round_number
        actions = generate_actions(
            state,
            max_actions=max_actions_per_choice,
            target_region_lines=target_region_lines,
            refine_threshold=refine_threshold,
            gradient_threshold=gradient_threshold,
            volatility_threshold=volatility_threshold,
        )
        actions.append({
            "kind": "stop_frontier",
            "node_id": "file",
            "priority": 0.0,
            "reason": (
                "finalize when current evidence is sufficient and every "
                "remaining legal action has lower expected information gain"
            ),
            "side": None,
            "source": None,
        })

        policy, current = decider.choose_next_action(
            goal,
            state,
            actions,
        )
        merge_usage(usage, current)

        chosen = policy["action"]
        if chosen["kind"] == "stop_frontier":
            state["termination"] = "model_stop"
            state["policy_stop"] = policy
            trace.emit(
                "relevance_frontier_phase0_choice_v2_stop",
                path=state["path"],
                round=round_number,
                policy=policy,
                frontier=frontier_summary(state),
            )
            break

        result = execute_action(
            root,
            state,
            chosen,
            probe_lines,
        )
        if result is None:
            state["termination"] = "frontier_exhausted"
            break

        # Value refresh happens after execution, so the next Choice epoch sees
        # the new observation and an updated relevance field.
        rescored, current = decider.score_frontier(goal, state)
        merge_usage(usage, current)
        apply_scores(state, rescored)

        stability = update_stability(
            state,
            candidate_threshold,
            stable_delta,
        )
        snapshot = {
            "round": round_number,
            "policy": policy,
            "executed": [{
                "kind": chosen["kind"],
                "source_node_id": chosen["node_id"],
                "target_node_id": result["target_node_id"],
                "range": [
                    result["observation"]["start_line"],
                    result["observation"]["end_line"],
                ],
            }],
            "frontier": frontier_summary(state),
            "stability": stability,
        }
        state["action_history"].append(snapshot)
        trace.emit(
            "relevance_frontier_phase0_choice_v2_round_completed",
            path=state["path"],
            **snapshot,
        )

    else:
        state["termination"] = "round_budget_exhausted"

    candidates = fine_candidates(
        state,
        candidate_threshold=candidate_threshold,
        final_window_lines=final_window_lines,
        max_candidates=final_max_candidates,
    )
    selected, current = decider.finalize_choices(
        goal,
        state,
        candidates,
    )
    merge_usage(usage, current)

    state["final_candidates"] = candidates
    state["evidence"] = merge_selected_candidates(selected)
    state["frontier_coverage"] = observed_frontier_coverage(state)
    state["source_coverage"] = (
        unique_source_coverage(state) / max(1, state["line_count"])
    )

    trace.emit(
        "relevance_frontier_phase0_choice_v2_completed",
        path=state["path"],
        termination=state["termination"],
        rounds=state["round"],
        phase0=state.get("phase0"),
        coarse_coverage=state.get("coarse_coverage"),
        observations=len(state["observations"]),
        frontier_coverage=state["frontier_coverage"],
        source_coverage=state["source_coverage"],
        final_candidates=len(candidates),
        evidence=len(state["evidence"]),
    )
    return state, usage
