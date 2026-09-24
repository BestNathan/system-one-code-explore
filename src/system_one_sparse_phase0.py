#!/usr/bin/env python3
"""Sparse Phase0 + Choice-policy relevance frontier v4.

Phase0 is deliberately *not* a coarse scan. It performs a constant-budget
micro-sampling pass whose cost is independent of file length:

1. Read three tiny bootstrap samples (head / middle / tail).
2. Generate legal micro-probe actions from the remaining gaps and local
   neighborhoods around observations.
3. Ask System One Choice which single probe to execute next, or whether to stop
   Phase0.
4. Stop after a small fixed probe budget (default: 8 probes x 8 lines).
5. Build a provisional relevance field from only those sparse observations.

Phase1 then uses the existing Choice policy + Noul value refresh frontier.
Final evidence uses the v3 group-aware closure stage.
"""
from __future__ import annotations

from system_one_code_locator import (
    empty_usage,
    merge_ranges,
    merge_usage,
    read_range,
    sanitize_source,
)
from system_one_relevance_frontier import (
    ClosureChoiceRelevanceFrontierDecider,
    OfflineClosureChoiceRelevanceFrontierDecider,
    append_observation,
    apply_scores,
    current_score,
    execute_action,
    fine_candidates,
    frontier_leaves,
    frontier_summary,
    generate_actions,
    merge_selected_candidates,
    new_file_state,
    unique_source_coverage,
)


DEFAULT_PHASE0_SAMPLE_LINES = 8
DEFAULT_PHASE0_MAX_PROBES = 8
DEFAULT_PHASE0_MAX_ACTIONS = 10


def _micro_range(center, line_count, width):
    width = max(1, min(int(width), int(line_count)))
    center = max(1, min(int(center), int(line_count)))
    left = max(1, center - width // 2)
    right = min(line_count, left + width - 1)
    left = max(1, right - width + 1)
    return left, right


def bootstrap_micro_ranges(line_count, sample_lines=DEFAULT_PHASE0_SAMPLE_LINES):
    """Return O(1) bootstrap samples regardless of file length."""
    if line_count <= 0:
        return []
    centers = [1, (line_count + 1) // 2, line_count]
    rows = []
    seen = set()
    for kind, center in zip(
        ("bootstrap_head", "bootstrap_middle", "bootstrap_tail"),
        centers,
    ):
        left, right = _micro_range(center, line_count, sample_lines)
        if (left, right) in seen:
            continue
        seen.add((left, right))
        rows.append((kind, left, right))
    return rows


def _observation_ranges(state):
    return [
        (int(item["start_line"]), int(item["end_line"]))
        for item in state["observations"]
    ]


def _uncovered_gaps(line_count, covered):
    merged = merge_ranges(covered)
    gaps = []
    cursor = 1
    for left, right in merged:
        if cursor < left:
            gaps.append((cursor, left - 1))
        cursor = max(cursor, right + 1)
    if cursor <= line_count:
        gaps.append((cursor, line_count))
    return gaps


def _leaf_for_line(state, line):
    for node in frontier_leaves(state):
        if int(node["start_line"]) <= line <= int(node["end_line"]):
            return node
    raise RuntimeError(f"no frontier leaf contains line {line}")


def _overlaps_existing(left, right, covered):
    for a, b in covered:
        if max(left, a) <= min(right, b):
            return True
    return False


def phase0_probe_actions(
    state,
    *,
    sample_lines=DEFAULT_PHASE0_SAMPLE_LINES,
    max_actions=DEFAULT_PHASE0_MAX_ACTIONS,
):
    """Generate sparse micro-probe choices without reading the candidate ranges.

    Candidate geometry comes from:
    - the largest uncovered gaps, at 25/50/75% positions;
    - immediate left/right neighborhoods of recent observations.

    The model sees only legal positions plus already-read micro snippets. It
    decides which *next* position is worth paying to read.
    """
    line_count = int(state["line_count"])
    covered = _observation_ranges(state)
    gaps = sorted(
        _uncovered_gaps(line_count, covered),
        key=lambda row: (-(row[1] - row[0] + 1), row[0]),
    )

    actions = []
    seen = set()

    def add(kind, center, reason, priority):
        left, right = _micro_range(center, line_count, sample_lines)
        if _overlaps_existing(left, right, covered):
            return
        key = (left, right)
        if key in seen:
            return
        seen.add(key)
        node = _leaf_for_line(state, (left + right) // 2)
        actions.append({
            "kind": kind,
            "node_id": node["id"],
            "priority": float(priority),
            "reason": reason,
            "sample_start": left,
            "sample_end": right,
            "side": None,
            "source": {"range": [left, right]},
        })

    for gap_index, (left, right) in enumerate(gaps[:4]):
        span = right - left + 1
        for fraction, label in ((0.5, "mid"), (0.25, "left"), (0.75, "right")):
            center = left + int((span - 1) * fraction)
            add(
                "sample_gap",
                center,
                (
                    f"sample {label} of uncovered gap {left}-{right}; "
                    "reduces uncertainty without scanning the interval"
                ),
                100.0 - gap_index,
            )

    for observation in state["observations"][-4:]:
        add(
            "sample_neighbor",
            int(observation["start_line"]) - sample_lines,
            "sample immediately before a known snippet to test local continuity",
            80.0,
        )
        add(
            "sample_neighbor",
            int(observation["end_line"]) + sample_lines,
            "sample immediately after a known snippet to test local continuity",
            80.0,
        )

    # Preserve geometry diversity rather than returning only candidates from
    # the single largest gap.
    actions.sort(
        key=lambda item: (
            -item["priority"],
            item["sample_start"],
            item["kind"],
        )
    )
    return actions[: max(1, int(max_actions))]


def execute_phase0_probe(root, state, action):
    observation = read_range(
        root,
        {
            "path": state["path"],
            "start_line": int(action["sample_start"]),
            "end_line": int(action["sample_end"]),
        },
    )
    node = _leaf_for_line(
        state,
        (int(action["sample_start"]) + int(action["sample_end"])) // 2,
    )
    item = append_observation(
        state,
        node,
        observation,
        action["kind"],
    )
    return {
        "action": action,
        "target_node_id": node["id"],
        "observation": item,
    }


class SparsePhase0ClosureChoiceRelevanceFrontierDecider(
    ClosureChoiceRelevanceFrontierDecider
):
    """Adds a dedicated Choice policy for selecting the next micro-probe."""

    def choose_phase0_probe(self, goal, state, actions):
        if not actions:
            raise RuntimeError("cannot choose from an empty sparse probe action set")

        by_id = {}
        action_views = []
        for index, action in enumerate(actions):
            action_id = f"p{index + 1}"
            by_id[action_id] = action
            action_views.append({
                "id": action_id,
                "kind": action["kind"],
                "range": [action["sample_start"], action["sample_end"]],
                "reason": action["reason"],
            })

        stop_id = "stop"
        state_view = {
            "goal": goal,
            "phase": "sparse_phase0_micro_sampling",
            "file": {
                "path": state["path"],
                "line_count": state["line_count"],
            },
            "budget": state.get("phase0_budget", {}),
            "observations": [
                {
                    "range": [item["start_line"], item["end_line"]],
                    "content": sanitize_source(item["content"]),
                    "navigation": item["navigation"],
                }
                for item in state["observations"]
            ],
            "candidate_probes": action_views,
            "semantics": (
                "Phase0 is sparse sensing, not coverage. Each candidate reads "
                "only a tiny source block. Choose the next position that has "
                "the highest expected information gain for localizing the task. "
                "Do not try to cover every region."
            ),
        }
        criteria = {
            action_id: (
                f"Read only lines {action['sample_start']}-"
                f"{action['sample_end']} ({action['reason']})."
            )
            for action_id, action in by_id.items()
        }
        criteria[stop_id] = (
            "Stop sparse Phase0 when the current snippets are sufficient to "
            "hand off to focused frontier refinement."
        )

        response, usage = self.send(
            "relevance_frontier_sparse_phase0_choice",
            state_view,
            {
                "next_probe": {
                    "type": "choice",
                    "instructions": {
                        "goal": goal,
                        "question": (
                            "Choose exactly one next micro-probe, or stop. "
                            "Optimize expected information gain per source line."
                        ),
                        "probes": action_views,
                    },
                    "criteria": criteria,
                }
            },
        )
        answer = response.get("answers", {}).get("next_probe", {})
        if answer.get("type") != "choice":
            raise RuntimeError(f"unexpected sparse Phase0 choice: {answer!r}")
        choice = answer.get("choice")
        if choice == stop_id:
            action = {
                "kind": "stop_phase0",
                "node_id": "file",
                "priority": 0.0,
                "reason": "System One ended sparse sensing",
                "sample_start": None,
                "sample_end": None,
                "side": None,
                "source": None,
            }
        elif choice in by_id:
            action = by_id[choice]
        else:
            raise RuntimeError(f"unknown sparse Phase0 choice: {choice!r}")

        return {
            "action": action,
            "choice": choice,
            "confidence": float(answer.get("confidence", 0.0) or 0.0),
            "probabilities": answer.get("probabilities", {}),
        }, usage


class OfflineSparsePhase0ClosureDecider(
    OfflineClosureChoiceRelevanceFrontierDecider
):
    model = "offline-sparse-phase0-closure-fixture"

    def choose_phase0_probe(self, goal, state, actions):
        # Keep tests deterministic and demonstrate early stopping: bootstrap
        # plus two model-selected micro probes is enough for the fixture.
        if len(state["observations"]) >= 5:
            return {
                "action": {
                    "kind": "stop_phase0",
                    "node_id": "file",
                    "priority": 0.0,
                    "reason": "fixture stop",
                    "sample_start": None,
                    "sample_end": None,
                    "side": None,
                    "source": None,
                },
                "choice": "stop",
                "confidence": 1.0,
                "probabilities": {},
            }, empty_usage()
        return {
            "action": actions[0],
            "choice": "p1",
            "confidence": 1.0,
            "probabilities": {},
        }, empty_usage()

    def choose_next_action(self, goal, state, actions):
        non_stop = [item for item in actions if item["kind"] != "stop_frontier"]
        selected = (
            sorted(
                non_stop,
                key=lambda item: (
                    -float(item["priority"]),
                    item["node_id"],
                    item["kind"],
                ),
            )[0]
            if non_stop
            else actions[-1]
        )
        return {
            "action": selected,
            "choice": selected["kind"],
            "confidence": 1.0,
            "probabilities": {},
        }, empty_usage()


def phase0_sparse_scan(
    root,
    goal,
    state,
    decider,
    trace,
    *,
    sample_lines=DEFAULT_PHASE0_SAMPLE_LINES,
    max_probes=DEFAULT_PHASE0_MAX_PROBES,
    max_actions_per_choice=DEFAULT_PHASE0_MAX_ACTIONS,
):
    if max_probes < 1:
        raise ValueError("max_probes must be positive")

    usage = empty_usage()
    state["phase0_budget"] = {
        "sample_lines": int(sample_lines),
        "max_probes": int(max_probes),
        "max_source_lines": int(sample_lines) * int(max_probes),
    }

    executed = []
    for kind, left, right in bootstrap_micro_ranges(
        int(state["line_count"]),
        sample_lines,
    ):
        if len(state["observations"]) >= max_probes:
            break
        action = {
            "kind": kind,
            "node_id": _leaf_for_line(state, (left + right) // 2)["id"],
            "priority": 0.0,
            "reason": "constant-cost bootstrap micro sample",
            "sample_start": left,
            "sample_end": right,
            "side": None,
            "source": {"range": [left, right]},
        }
        executed.append(execute_phase0_probe(root, state, action))

    decisions = []
    while len(state["observations"]) < max_probes:
        actions = phase0_probe_actions(
            state,
            sample_lines=sample_lines,
            max_actions=max_actions_per_choice,
        )
        if not actions:
            break
        policy, current = decider.choose_phase0_probe(
            goal,
            state,
            actions,
        )
        merge_usage(usage, current)
        decisions.append(policy)
        if policy["action"]["kind"] == "stop_phase0":
            break
        executed.append(
            execute_phase0_probe(root, state, policy["action"])
        )

    # Build a *provisional* coarse value field only after sparse sensing.
    # Unobserved frontier leaves stay unknown; they are not treated as zero.
    scores, current = decider.score_frontier(goal, state)
    merge_usage(usage, current)
    apply_scores(state, scores)

    sampled_lines = unique_source_coverage(state)
    state["phase0"] = {
        "kind": "sparse_micro_sampling",
        "sample_lines": int(sample_lines),
        "max_probes": int(max_probes),
        "reads": len(state["observations"]),
        "sampled_source_lines": sampled_lines,
        "sampled_source_coverage": sampled_lines / max(1, int(state["line_count"])),
        "all_regions_observed": all(
            bool(node["observation_ids"]) for node in frontier_leaves(state)
        ),
        "observed_leaf_count": sum(
            bool(node["observation_ids"]) for node in frontier_leaves(state)
        ),
        "leaf_count": len(frontier_leaves(state)),
        "decisions": decisions,
        "bootstrap": "head_middle_tail_micro_blocks",
    }
    trace.emit(
        "relevance_frontier_sparse_phase0_completed",
        path=state["path"],
        phase0=state["phase0"],
    )
    return usage


def run_frontier_file_sparse_phase0_choice_closure_v4(
    root,
    goal,
    candidate,
    decider,
    trace,
    *,
    phase0_sample_lines=8,
    phase0_max_probes=8,
    phase0_max_actions_per_choice=10,
    max_rounds=12,
    max_actions_per_choice=6,
    phase1_probe_lines=64,
    target_region_lines=48,
    final_window_lines=32,
    refine_threshold=0.72,
    candidate_threshold=0.55,
    gradient_threshold=0.15,
    volatility_threshold=0.10,
    max_frontier_leaves=24,
    final_max_candidates=24,
):
    usage = empty_usage()
    state = new_file_state(root, candidate, max_frontier_leaves)
    if state is None:
        return None, usage

    trace.emit(
        "relevance_frontier_sparse_v4_started",
        path=state["path"],
        line_count=state["line_count"],
        initial_frontier=frontier_summary(state),
    )

    current = phase0_sparse_scan(
        root,
        goal,
        state,
        decider,
        trace,
        sample_lines=phase0_sample_lines,
        max_probes=phase0_max_probes,
        max_actions_per_choice=phase0_max_actions_per_choice,
    )
    merge_usage(usage, current)

    phase0_observation_ids = {
        item["id"] for item in state["observations"]
    }

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
                "finalize when current evidence is sufficient and remaining "
                "actions have lower expected information gain"
            ),
            "side": None,
            "source": None,
        })

        policy, current = decider.choose_next_action(goal, state, actions)
        merge_usage(usage, current)
        chosen = policy["action"]
        if chosen["kind"] == "stop_frontier":
            state["termination"] = "model_stop"
            state["policy_stop"] = policy
            break

        result = execute_action(
            root,
            state,
            chosen,
            phase1_probe_lines,
        )
        if result is None:
            state["termination"] = "frontier_exhausted"
            break

        rescored, current = decider.score_frontier(goal, state)
        merge_usage(usage, current)
        apply_scores(state, rescored)
        state["action_history"].append({
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
        })
    else:
        state["termination"] = "round_budget_exhausted"

    candidates = fine_candidates(
        state,
        candidate_threshold=candidate_threshold,
        final_window_lines=final_window_lines,
        max_candidates=final_max_candidates,
    )
    selected, current = decider.finalize_group_choices(
        goal,
        state,
        candidates,
    )
    merge_usage(usage, current)

    state["final_candidates"] = candidates
    state["evidence"] = merge_selected_candidates(selected)
    state["source_coverage"] = (
        unique_source_coverage(state) / max(1, int(state["line_count"]))
    )
    leaves = frontier_leaves(state)
    state["frontier_coverage"] = (
        sum(bool(node["observation_ids"]) for node in leaves)
        / max(1, len(leaves))
    )
    state["phase0_observation_count"] = len(phase0_observation_ids)
    state["phase1_observation_count"] = (
        len(state["observations"]) - len(phase0_observation_ids)
    )

    trace.emit(
        "relevance_frontier_sparse_v4_completed",
        path=state["path"],
        termination=state["termination"],
        rounds=state["round"],
        phase0=state.get("phase0"),
        observations=len(state["observations"]),
        source_coverage=state["source_coverage"],
        observed_leaf_ratio=state["frontier_coverage"],
        final_candidates=len(candidates),
        evidence=len(state["evidence"]),
    )
    return state, usage
