#!/usr/bin/env python3
"""Phase0 v5: whole-file probability frontier reconstruction.

The Phase0 state is a file-length probability field, not a coarse region tree.
Sparse 5-10 line observations update this field. The model sees quantized
whole-file relevance + uncertainty vectors and a diverse probe action set.
Choice probabilities are used as a multi-probe policy: every probe above the
configured probability threshold is executed, up to a batch cap.
"""
from __future__ import annotations

import hashlib
import math
import random

from system_one_code_locator import empty_usage, merge_usage, read_range, sanitize_source
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider
from posterior_reconstruction import reconstruct as reconstruct_posterior

HEX = "0123456789abcdef"


def new_probability_frontier(line_count, prior=0.5):
    n = int(line_count)
    return {
        "line_count": n,
        "relevance": [float(prior)] * n,
        "uncertainty": [1.0] * n,
        "observed": [False] * n,
        "samples": [],
    }


def quantize(values):
    return "".join(HEX[min(15, max(0, int(round(float(v) * 15))))] for v in values)


def observed_mask(frontier):
    return "".join("1" if x else "0" for x in frontier["observed"])


def snapshot_frontier(frontier, probes, usage):
    return {
        "probes": int(probes),
        "sampled_source_lines": sum(1 for x in frontier["observed"] if x),
        "relevance": [float(x) for x in frontier["relevance"]],
        "uncertainty": [float(x) for x in frontier["uncertainty"]],
        "usage": {k: int(v) for k, v in usage.items()},
    }


def frontier_view(frontier):
    return {
        "line_count": frontier["line_count"],
        "relevance_q16": quantize(frontier["relevance"]),
        "uncertainty_q16": quantize(frontier["uncertainty"]),
        "observed_mask": observed_mask(frontier),
        "samples": [
            {
                "range": [s["start_line"], s["end_line"]],
                "score": round(float(s["score"]), 4),
            }
            for s in frontier["samples"]
        ],
        "encoding": "one hex digit per source line; 0=low, f=high",
    }


def update_probability_frontier(
    frontier,
    start_line,
    end_line,
    score,
    *,
    decay_lines=48.0,
):
    """Update observed lines strongly and nearby lines weakly.

    Far-away lines remain close to the prior with high uncertainty. This is
    intentionally conservative: unseen must not collapse to irrelevant.
    """
    n = frontier["line_count"]
    left = max(1, int(start_line))
    right = min(n, int(end_line))
    score = min(1.0, max(0.0, float(score)))

    for line in range(1, n + 1):
        if left <= line <= right:
            influence = 1.0
        else:
            distance = left - line if line < left else line - right
            influence = math.exp(-distance / max(1.0, float(decay_lines)))
            if influence < 0.02:
                continue

        idx = line - 1
        old_u = frontier["uncertainty"][idx]
        old_p = frontier["relevance"][idx]
        evidence_weight = influence
        prior_weight = max(0.05, old_u)
        frontier["relevance"][idx] = (
            old_p * prior_weight + score * evidence_weight
        ) / (prior_weight + evidence_weight)
        frontier["uncertainty"][idx] = max(
            0.03 if influence >= 1.0 else 0.15,
            old_u * (1.0 - 0.72 * influence),
        )
        if left <= line <= right:
            frontier["observed"][idx] = True

    frontier["samples"].append({
        "start_line": left,
        "end_line": right,
        "score": score,
    })


def append_probability_sample(frontier, start_line, end_line, score):
    """Append durable evidence without choosing a posterior implementation."""
    n = int(frontier["line_count"])
    left = max(1, int(start_line))
    right = min(n, int(end_line))
    score = min(1.0, max(0.0, float(score)))

    frontier["samples"].append({
        "start_line": left,
        "end_line": right,
        "score": score,
    })
    for line in range(left, right + 1):
        frontier["observed"][line - 1] = True


def rebuild_probability_frontier(
    frontier,
    *,
    estimator,
    sample_lines,
):
    """Recompute relevance/uncertainty from durable observations.

    Path-independent estimators no longer depend on the order in which the
    current field happened to be mutated. The sequential estimator remains
    available as a historical baseline and deterministically replays the same
    sample order.
    """
    posterior = reconstruct_posterior(
        estimator,
        frontier["samples"],
        int(frontier["line_count"]),
        sample_lines=int(sample_lines),
    )
    frontier["relevance"] = list(posterior["relevance"])
    frontier["uncertainty"] = list(posterior["uncertainty"])
    frontier["posterior_estimator"] = posterior["name"]
    return posterior


def _micro_range(center, line_count, width):
    width = max(1, min(int(width), int(line_count)))
    center = max(1, min(int(center), int(line_count)))
    left = max(1, center - width // 2)
    right = min(line_count, left + width - 1)
    return max(1, right - width + 1), right


def _overlaps_observed(frontier, left, right):
    return any(frontier["observed"][i - 1] for i in range(left, right + 1))


def generate_probe_actions(
    frontier,
    *,
    path,
    epoch,
    sample_lines=8,
    max_actions=16,
):
    """Generate a spatially diverse, mixed-policy probe action set.

    Every epoch reserves capacity for multiple proposal families so one family
    cannot starve the others:
    - stratified random exploration;
    - high epistemic uncertainty;
    - high relevance gradient;
    - current relevance peaks.

    Candidate ranges are also separated in source space. Choice should compare
    meaningfully different places, not several 8-line windows around one line.
    """
    n = frontier["line_count"]
    rng = random.Random(
        int(hashlib.sha256(f"{path}:{epoch}".encode()).hexdigest()[:16], 16)
    )
    candidates = []
    seen = set()
    min_center_gap = max(sample_lines * 3, 24)

    def add(kind, center):
        left, right = _micro_range(center, n, sample_lines)
        if _overlaps_observed(frontier, left, right):
            return False
        key = (left, right)
        if key in seen:
            return False
        candidate_center = (left + right) // 2
        for item in candidates:
            existing_center = (item["start_line"] + item["end_line"]) // 2
            if abs(candidate_center - existing_center) < min_center_gap:
                return False
        seen.add(key)
        candidates.append({
            "id": f"p{len(candidates)+1}",
            "kind": kind,
            "start_line": left,
            "end_line": right,
        })
        return True

    if max_actions <= 0:
        return []

    # Explicit quotas guarantee policy diversity. Remainders go to random
    # exploration because broad coverage is the safest fallback.
    random_quota = max(1, round(max_actions * 0.375))
    uncertainty_quota = max(1, round(max_actions * 0.25))
    gradient_quota = max(1, round(max_actions * 0.1875))
    peak_quota = max(1, max_actions - random_quota - uncertainty_quota - gradient_quota)

    # 1) Stratified random coverage across the whole file.
    strata = random_quota
    random_added = 0
    for s in range(strata):
        a = 1 + (n * s) // strata
        b = max(a, (n * (s + 1)) // strata)
        for _ in range(6):
            if add("random_stratified", rng.randint(a, b)):
                random_added += 1
                break

    # 2) High uncertainty, with randomized tie breaking.
    uncertainty_order = list(range(1, n + 1))
    tie = {line: rng.random() for line in uncertainty_order}
    uncertainty_order.sort(
        key=lambda line: (-frontier["uncertainty"][line - 1], tie[line])
    )
    uncertainty_added = 0
    for line in uncertainty_order:
        if add("uncertainty", line):
            uncertainty_added += 1
            if uncertainty_added >= uncertainty_quota:
                break

    # 3) High relevance-gradient boundaries.
    p = frontier["relevance"]
    gradients = [
        (abs(p[line] - p[line - 2]), tie.get(line, rng.random()), line)
        for line in range(2, n)
    ]
    gradient_added = 0
    for _, _, line in sorted(gradients, key=lambda row: (-row[0], row[1])):
        if add("gradient", line):
            gradient_added += 1
            if gradient_added >= gradient_quota:
                break

    # 4) Neighborhoods around current relevance peaks.
    peak_order = list(range(1, n + 1))
    peak_order.sort(
        key=lambda line: (
            -frontier["relevance"][line - 1],
            -frontier["uncertainty"][line - 1],
            tie.get(line, rng.random()),
        )
    )
    peak_added = 0
    for line in peak_order:
        if add("peak_neighbor", line):
            peak_added += 1
            if peak_added >= peak_quota:
                break

    # If geometry/observed masks prevented a quota from filling, top up with
    # globally random unobserved positions while preserving spatial diversity.
    attempts = 0
    while len(candidates) < max_actions and attempts < max_actions * 40:
        add("random_fill", rng.randint(1, n))
        attempts += 1

    return candidates[:max_actions]

def select_choice_batch(
    probabilities,
    action_ids,
    *,
    threshold=None,
    threshold_multiplier=1.1,
    max_batch=4,
    stop_id="stop",
):
    """Use the complete Choice distribution, not only its argmax.

    By default the threshold is slightly above a uniform categorical prior,
    making it stable as the number of candidate probes changes.
    """
    if not action_ids:
        return []
    if threshold is None:
        threshold = float(threshold_multiplier) / (len(action_ids) + 1)

    selected = [
        (aid, float(probabilities.get(aid, 0.0)))
        for aid in action_ids
        if float(probabilities.get(aid, 0.0)) >= float(threshold)
    ]
    selected.sort(key=lambda row: (-row[1], row[0]))
    if selected:
        return [aid for aid, _ in selected[: max(1, int(max_batch))]]

    # If stop itself clears the same threshold, allow an empty batch.
    if float(probabilities.get(stop_id, 0.0)) >= float(threshold):
        return []

    # Otherwise make progress with the highest-probability legal probe.
    best = max(action_ids, key=lambda aid: float(probabilities.get(aid, 0.0)))
    return [best]


class ProbabilityFrontierDecider(ClosureChoiceRelevanceFrontierDecider):
    def choose_probe_batch(
        self,
        goal,
        path,
        frontier,
        actions,
        *,
        probability_threshold=None,
        max_batch=4,
    ):
        by_id = {a["id"]: a for a in actions}
        state_view = {
            "goal": goal,
            "phase": "probability_frontier_phase0_v5",
            "file": {"path": path, "line_count": frontier["line_count"]},
            "probability_frontier": frontier_view(frontier),
            "candidate_probes": actions,
            "semantics": (
                "Reconstruct the whole-file relevance distribution. Candidate "
                "source is unread. Use the current relevance/uncertainty shape "
                "to assign probability to probes that can most improve the "
                "distribution estimate."
            ),
        }
        criteria = {
            aid: (
                f"Probe lines {a['start_line']}-{a['end_line']} "
                f"({a['kind']}) because observing it would materially improve "
                "the whole-file relevance distribution estimate."
            )
            for aid, a in by_id.items()
        }
        criteria["stop"] = (
            "The probability frontier is already sufficiently reconstructed "
            "for the remaining Phase0 budget."
        )

        response, usage = self.send(
            "probability_frontier_probe_choice",
            state_view,
            {
                "probe_policy": {
                    "type": "choice",
                    "instructions": {
                        "goal": goal,
                        "question": (
                            "Distribute probability over candidate probes and "
                            "stop according to their value for reconstructing "
                            "the entire file relevance distribution."
                        ),
                    },
                    "criteria": criteria,
                }
            },
        )
        answer = response.get("answers", {}).get("probe_policy", {})
        if answer.get("type") != "choice":
            raise RuntimeError(f"unexpected choice answer: {answer!r}")
        probs = answer.get("probabilities", {}) or {}
        selected_ids = select_choice_batch(
            probs,
            list(by_id),
            threshold=probability_threshold,
            max_batch=max_batch,
        )
        return {
            "argmax": answer.get("choice"),
            "probabilities": probs,
            "selected_ids": selected_ids,
            "selected_actions": [by_id[x] for x in selected_ids],
            "stop_probability": float(probs.get("stop", 0.0) or 0.0),
        }, usage

    def score_probe_observations(self, goal, path, frontier, observations):
        questions = {}
        for i, obs in enumerate(observations):
            questions[f"sample_{i}"] = {
                "type": "noul",
                "instructions": {
                    "goal": goal,
                    "path": path,
                    "range": [obs["start_line"], obs["end_line"]],
                    "content": sanitize_source(obs["content"]),
                    "question": (
                        "How relevant is this observed micro-block to the task? "
                        "Return relevance on [0,1]. Judge only observed content."
                    ),
                },
                "criteria": {
                    "true": "material implementation evidence for the task",
                    "false": "incidental or irrelevant content",
                },
            }
        response, usage = self.send(
            "probability_frontier_sample_score",
            {
                "goal": goal,
                "file": path,
                "frontier": frontier_view(frontier),
            },
            questions,
        )
        answers = response.get("answers", {})
        scores = []
        for i in range(len(observations)):
            ans = answers.get(f"sample_{i}", {})
            if ans.get("type") != "noul":
                raise RuntimeError(f"unexpected sample score: {ans!r}")
            scores.append(float(ans["noul"]))
        return scores, usage


def execute_probe_batch(root, path, actions):
    return [
        read_range(root, {
            "path": path,
            "start_line": int(a["start_line"]),
            "end_line": int(a["end_line"]),
        })
        for a in actions
    ]


def phase0_probability_frontier(
    root,
    goal,
    path,
    line_count,
    decider,
    *,
    sample_lines=8,
    max_epochs=8,
    max_actions=16,
    max_batch=4,
    probability_threshold=None,
    max_total_probes=24,
    respect_stop=True,
    posterior_estimator="sequential_exponential",
):
    """Build a whole-file relevance probability frontier."""
    frontier = new_probability_frontier(line_count)
    usage = empty_usage()
    history = []
    snapshots = []
    total_probes = 0

    # First epoch is a reproducible random/stratified bootstrap batch.
    bootstrap = generate_probe_actions(
        frontier,
        path=path,
        epoch=0,
        sample_lines=sample_lines,
        max_actions=max_actions,
    )[: min(max_batch, max_total_probes)]
    observations = execute_probe_batch(root, path, bootstrap)
    scores, current = decider.score_probe_observations(goal, path, frontier, observations)
    merge_usage(usage, current)
    for action, observation, score in zip(bootstrap, observations, scores):
        append_probability_sample(
            frontier,
            observation["start_line"],
            observation["end_line"],
            score,
        )
        rebuild_probability_frontier(
            frontier,
            estimator=posterior_estimator,
            sample_lines=sample_lines,
        )
        total_probes += 1
        snapshots.append(snapshot_frontier(frontier, total_probes, usage))
    history.append({"epoch": 0, "actions": bootstrap, "scores": scores})

    for epoch in range(1, max_epochs + 1):
        if total_probes >= max_total_probes:
            break
        actions = generate_probe_actions(
            frontier,
            path=path,
            epoch=epoch,
            sample_lines=sample_lines,
            max_actions=max_actions,
        )
        if not actions:
            break
        policy, current = decider.choose_probe_batch(
            goal,
            path,
            frontier,
            actions,
            probability_threshold=probability_threshold,
            max_batch=min(max_batch, max_total_probes - total_probes),
        )
        merge_usage(usage, current)
        if not policy["selected_actions"]:
            if respect_stop and policy["stop_probability"] >= 0.5:
                break
            # Convergence benchmarks may deliberately continue beyond the
            # model's natural stopping point to measure the full budget curve.
            probabilities = policy.get("probabilities", {})
            best = max(
                actions,
                key=lambda item: float(probabilities.get(item["id"], 0.0)),
            )
            policy["selected_actions"] = [best]
            policy["selected_ids"] = [best["id"]]
            policy["forced_progress"] = True
        observations = execute_probe_batch(root, path, policy["selected_actions"])
        scores, current = decider.score_probe_observations(
            goal, path, frontier, observations
        )
        merge_usage(usage, current)
        for action, observation, score in zip(policy["selected_actions"], observations, scores):
            append_probability_sample(
                frontier,
                observation["start_line"],
                observation["end_line"],
                score,
            )
            rebuild_probability_frontier(
                frontier,
                estimator=posterior_estimator,
                sample_lines=sample_lines,
            )
            total_probes += 1
            snapshots.append(snapshot_frontier(frontier, total_probes, usage))
        history.append({
            "epoch": epoch,
            "policy": policy,
            "scores": scores,
        })

    return {
        "kind": "whole_file_probability_frontier_v5",
        "frontier": frontier,
        "history": history,
        "snapshots": snapshots,
        "probes": total_probes,
        "sample_lines": sample_lines,
        "respect_stop": bool(respect_stop),
        "posterior_estimator": posterior_estimator,
    }, usage
