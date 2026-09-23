#!/usr/bin/env python3
"""Algorithm B: Adaptive Semantic Zoom Search.

Language-agnostic coarse-to-fine range search:
1. Stratified coarse probes cover the file.
2. System One Choice produces a probability distribution over regions.
3. A beam keeps up to top-k regions covering the target probability mass.
4. One geometry-only exploration slot prevents winner-take-all collapse.
5. Selected regions split and receive finer midpoint probes.
6. Final observed ranges are independently scored as material evidence.

The harness never parses source content.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from system_one_code_locator import (
    API_URL,
    MODEL,
    SystemOneDecider,
    Trace,
    empty_usage,
    merge_usage,
    read_range,
    sanitize_source,
    source_stat,
)
from system_one_range_runtime import (
    DEFAULT_DIRECTORY_THRESHOLD,
    DEFAULT_EVIDENCE_THRESHOLD,
    DEFAULT_FILE_THRESHOLD,
    run_phase1,
)


DEFAULT_COARSE_REGIONS = 16
DEFAULT_PROBE_LINES = 32
DEFAULT_BEAM_WIDTH = 3
DEFAULT_BEAM_MASS = 0.80
DEFAULT_EXPLORATION_SLOTS = 1
DEFAULT_TARGET_REGION_LINES = 40
DEFAULT_EXPLORATION_FLOOR = 0.05
DEFAULT_MAX_ZOOM_ROUNDS = 8
DEFAULT_STABLE_ROUNDS = 2
DEFAULT_VIEW_CHAR_BUDGET = 48000


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
        region_end = cursor + width - 1
        out.append((cursor, region_end))
        cursor = region_end + 1
    return out


def midpoint_probe(start, end, probe_lines):
    length = end - start + 1
    if length <= probe_lines:
        return start, end
    midpoint = (start + end) // 2
    probe_start = max(start, midpoint - probe_lines // 2)
    probe_end = min(end, probe_start + probe_lines - 1)
    if probe_end - probe_start + 1 < probe_lines:
        probe_start = max(start, probe_end - probe_lines + 1)
    return probe_start, probe_end


def new_region(region_id, start, end, depth, parent=None, root=None):
    return {
        "id": region_id,
        "start_line": int(start),
        "end_line": int(end),
        "depth": int(depth),
        "parent_id": parent,
        "root_id": root or region_id,
        "probability": None,
        "probe": None,
        "status": "active",
    }


def initial_regions(line_count, coarse_regions):
    return [
        new_region(
            f"r{index}",
            start,
            end,
            depth=0,
        )
        for index, (start, end) in enumerate(
            partition_range(1, line_count, coarse_regions),
            1,
        )
    ]


def read_region_probe(root, path, region, probe_lines):
    start, end = midpoint_probe(
        region["start_line"],
        region["end_line"],
        probe_lines,
    )
    action = {
        "path": path,
        "start_line": start,
        "end_line": end,
    }
    observation = read_range(root, action)
    return {
        "region_id": region["id"],
        "path": path,
        "start_line": observation["start_line"],
        "end_line": observation["end_line"],
        "content": observation["content"],
        "depth": region["depth"],
    }


def split_region(region):
    start = region["start_line"]
    end = region["end_line"]
    if start >= end:
        return []
    midpoint = (start + end) // 2
    root = region["root_id"]
    depth = region["depth"] + 1
    return [
        new_region(
            f"{region['id']}.L",
            start,
            midpoint,
            depth,
            parent=region["id"],
            root=root,
        ),
        new_region(
            f"{region['id']}.R",
            midpoint + 1,
            end,
            depth,
            parent=region["id"],
            root=root,
        ),
    ]


def bounded_observation_view(observations, char_budget):
    visible = []
    used = 0
    for item in reversed(observations):
        content = sanitize_source(item["content"])
        size = len(content)
        if visible and used + size > char_budget:
            continue
        if not visible and size > char_budget:
            content = content[-char_budget:]
            size = len(content)
        visible.append({
            "region_id": item["region_id"],
            "start_line": item["start_line"],
            "end_line": item["end_line"],
            "depth": item["depth"],
            "content": content,
        })
        used += size
        if used >= char_budget:
            break
    visible.reverse()
    return {
        "total_count": len(observations),
        "visible_count": len(visible),
        "omitted_count": len(observations) - len(visible),
        "used_chars": used,
        "char_budget": char_budget,
        "items": visible,
    }


def zoom_decision_view(goal, file_state, frontier):
    return {
        "goal": goal,
        "phase": "adaptive_semantic_zoom_v0",
        "file": {
            "path": file_state["path"],
            "line_count": file_state["line_count"],
            "phase1_score": file_state["phase1_score"],
            "round": file_state["round"],
        },
        "frontier": [
            {
                "id": item["id"],
                "start_line": item["start_line"],
                "end_line": item["end_line"],
                "span": item["end_line"] - item["start_line"] + 1,
                "depth": item["depth"],
                "root_id": item["root_id"],
            }
            for item in frontier
        ],
        "observations": bounded_observation_view(
            file_state["observations"],
            DEFAULT_VIEW_CHAR_BUDGET,
        ),
    }


class AdaptiveZoomDecider(SystemOneDecider):
    def rank_regions(self, goal, file_state, frontier):
        if not frontier:
            return {}, empty_usage()

        criteria = {}
        for region in frontier:
            criteria[region["id"]] = {
                "range": [
                    region["start_line"],
                    region["end_line"],
                ],
                "meaning": (
                    "Spend the next refinement budget on this region because "
                    "finer inspection is likely to reveal material evidence "
                    "needed for the goal."
                ),
            }

        response, usage = self.send(
            "adaptive_zoom_region_choice",
            zoom_decision_view(goal, file_state, frontier),
            {
                "focus": {
                    "type": "choice",
                    "instructions": {
                        "goal": goal,
                        "question": (
                            "Which visible region most deserves finer-grained "
                            "inspection next? Prefer regions likely to contain "
                            "material evidence that changes or completes the "
                            "downstream answer. Topical similarity alone is not "
                            "enough; prefer implementation, control flow, state "
                            "transitions, dependencies/contracts, edge cases, "
                            "and constraints."
                        ),
                    },
                    "criteria": criteria,
                },
            },
        )
        answer = response.get("answers", {}).get("focus", {})
        if answer.get("type") != "choice":
            raise RuntimeError(
                f"unexpected zoom choice answer: {answer!r}"
            )
        probabilities = {
            region["id"]: float(
                answer.get("probabilities", {}).get(
                    region["id"],
                    0.0,
                ) or 0.0
            )
            for region in frontier
        }
        return {
            "choice": answer.get("choice"),
            "probabilities": probabilities,
            "confidence": float(
                answer.get("confidence", 0.0) or 0.0
            ),
        }, usage

    def score_evidence(self, goal, file_state, batch_size=4):
        observations = file_state["observations"]
        if not observations:
            return [], empty_usage()

        total_usage = empty_usage()
        scored = []
        for offset in range(0, len(observations), batch_size):
            batch = observations[offset:offset + batch_size]
            questions = {}
            for index, item in enumerate(batch):
                questions[f"evidence_{index}"] = {
                    "type": "noul",
                    "instructions": {
                        "goal": goal,
                        "path": item["path"],
                        "start_line": item["start_line"],
                        "end_line": item["end_line"],
                        "content": sanitize_source(item["content"]),
                        "question": (
                            "Does this observed range contain distinct MATERIAL "
                            "EVIDENCE that should be retained for the downstream "
                            "task?"
                        ),
                    },
                    "criteria": {
                        "true": (
                            "Distinct implementation/control-flow/state/"
                            "dependency/contract/edge-case/constraint evidence."
                        ),
                        "false": (
                            "Redundant, merely topical, incidental, or "
                            "insufficiently useful evidence."
                        ),
                    },
                }
            response, usage = self.send(
                "adaptive_zoom_evidence_score",
                {
                    "goal": goal,
                    "file": file_state["path"],
                },
                questions,
            )
            merge_usage(total_usage, usage)
            answers = response.get("answers", {})
            for index, item in enumerate(batch):
                answer = answers.get(f"evidence_{index}", {})
                if answer.get("type") != "noul":
                    raise RuntimeError(
                        f"unexpected zoom evidence answer: {answer!r}"
                    )
                scored.append({
                    **item,
                    "relevance": float(answer["noul"]),
                })
        return scored, total_usage


class OfflineAdaptiveZoomDecider:
    model = "offline-adaptive-zoom-fixture"

    def __init__(self, trace):
        self.trace = trace

    def score_candidates(self, query, stage, candidates):
        return [
            {**item, "score": 0.9}
            for item in candidates
        ], empty_usage()

    def rank_regions(self, goal, file_state, frontier):
        weights = {
            region["id"]: float(
                region["end_line"] - region["start_line"] + 1
            )
            for region in frontier
        }
        total = sum(weights.values()) or 1.0
        probabilities = {
            key: value / total
            for key, value in weights.items()
        }
        choice = max(probabilities, key=probabilities.get)
        return {
            "choice": choice,
            "probabilities": probabilities,
            "confidence": probabilities[choice],
        }, empty_usage()

    def score_evidence(self, goal, file_state, batch_size=4):
        return [
            {**item, "relevance": 0.8}
            for item in file_state["observations"]
        ], empty_usage()


def choose_beam(
    frontier,
    probabilities,
    *,
    beam_width,
    beam_mass,
    exploration_slots,
):
    ranked = sorted(
        frontier,
        key=lambda item: (
            -probabilities.get(item["id"], 0.0),
            item["start_line"],
        ),
    )

    exploit = []
    cumulative = 0.0
    for region in ranked:
        if len(exploit) >= beam_width:
            break
        exploit.append(region)
        cumulative += probabilities.get(region["id"], 0.0)
        if cumulative >= beam_mass:
            break

    exploit_ids = {item["id"] for item in exploit}
    remaining = [
        item for item in frontier
        if item["id"] not in exploit_ids
    ]
    # Exploration is geometry-only: prefer the largest still-coarse regions
    # outside the probability beam.
    exploration = sorted(
        remaining,
        key=lambda item: (
            -(item["end_line"] - item["start_line"] + 1),
            item["depth"],
            item["start_line"],
        ),
    )[:exploration_slots]

    return exploit, exploration, cumulative


def active_regions(frontier, probabilities, exploration_floor):
    return [
        item
        for item in frontier
        if probabilities.get(item["id"], 0.0) >= exploration_floor
    ]


def region_roots(regions):
    return tuple(sorted({item["root_id"] for item in regions}))


def new_zoom_file_state(root, candidate):
    stat = source_stat(root, candidate)
    if stat is None:
        return None
    return {
        "path": candidate["payload"]["path"],
        "phase1_score": candidate["score"],
        "line_count": stat["line_count"],
        "round": 0,
        "observations": [],
        "frontier_history": [],
        "termination": None,
    }


def probe_regions(root, file_state, regions, probe_lines):
    observations = []
    for region in regions:
        observation = read_region_probe(
            root,
            file_state["path"],
            region,
            probe_lines,
        )
        region["probe"] = {
            "start_line": observation["start_line"],
            "end_line": observation["end_line"],
        }
        observations.append(observation)
        file_state["observations"].append(observation)
    return observations


def refine_selected_regions(
    root,
    file_state,
    frontier,
    selected,
    probe_lines,
    target_region_lines,
):
    selected_ids = {item["id"] for item in selected}
    next_frontier = [
        item for item in frontier
        if item["id"] not in selected_ids
    ]
    new_children = []
    for region in selected:
        span = region["end_line"] - region["start_line"] + 1
        if span <= target_region_lines:
            resolved = dict(region)
            resolved["status"] = "resolved"
            next_frontier.append(resolved)
            continue
        children = split_region(region)
        new_children.extend(children)
        next_frontier.extend(children)

    observations = probe_regions(
        root,
        file_state,
        new_children,
        probe_lines,
    )
    return next_frontier, observations


def run_zoom_file(
    root,
    goal,
    candidate,
    decider,
    trace,
    *,
    coarse_regions,
    probe_lines,
    beam_width,
    beam_mass,
    exploration_slots,
    target_region_lines,
    exploration_floor,
    max_rounds,
    stable_rounds,
):
    usage = empty_usage()
    state = new_zoom_file_state(root, candidate)
    if state is None:
        return None, usage

    frontier = initial_regions(
        state["line_count"],
        coarse_regions,
    )
    probe_regions(root, state, frontier, probe_lines)
    trace.emit(
        "zoom_file_started",
        path=state["path"],
        line_count=state["line_count"],
        coarse_regions=len(frontier),
        initial_frontier=frontier,
    )

    previous_roots = None
    stable_count = 0

    for round_number in range(1, max_rounds + 1):
        state["round"] = round_number
        ranking, current = decider.rank_regions(
            goal,
            state,
            frontier,
        )
        merge_usage(usage, current)
        probabilities = ranking["probabilities"]

        for region in frontier:
            region["probability"] = probabilities.get(
                region["id"],
                0.0,
            )

        exploit, exploration, cumulative = choose_beam(
            frontier,
            probabilities,
            beam_width=beam_width,
            beam_mass=beam_mass,
            exploration_slots=exploration_slots,
        )
        selected = exploit + [
            item for item in exploration
            if item["id"] not in {row["id"] for row in exploit}
        ]

        active = active_regions(
            frontier,
            probabilities,
            exploration_floor,
        )
        roots = region_roots(exploit)
        if roots == previous_roots:
            stable_count += 1
        else:
            stable_count = 1
            previous_roots = roots

        snapshot = {
            "round": round_number,
            "choice": ranking["choice"],
            "confidence": ranking["confidence"],
            "probabilities": probabilities,
            "beam_ids": [item["id"] for item in exploit],
            "exploration_ids": [
                item["id"] for item in exploration
            ],
            "beam_mass": cumulative,
            "active_ids": [item["id"] for item in active],
            "stable_root_rounds": stable_count,
        }
        state["frontier_history"].append(snapshot)
        trace.emit(
            "zoom_frontier_ranked",
            path=state["path"],
            **snapshot,
        )

        high_value_coarse = [
            item for item in active
            if item["end_line"] - item["start_line"] + 1
            > target_region_lines
        ]
        if (
            not high_value_coarse
            and stable_count >= stable_rounds
        ):
            state["termination"] = "probability_frontier_converged"
            break

        if not selected:
            state["termination"] = "frontier_exhausted"
            break

        frontier, observations = refine_selected_regions(
            root,
            state,
            frontier,
            selected,
            probe_lines,
            target_region_lines,
        )
        trace.emit(
            "zoom_regions_refined",
            path=state["path"],
            round=round_number,
            selected_ids=[item["id"] for item in selected],
            observations=observations,
        )
    else:
        state["termination"] = "round_budget_exhausted"

    evidence, current = decider.score_evidence(
        goal,
        state,
    )
    merge_usage(usage, current)
    state["frontier"] = frontier
    state["evidence"] = evidence
    trace.emit(
        "zoom_file_completed",
        path=state["path"],
        termination=state["termination"],
        rounds=state["round"],
        observations=len(state["observations"]),
        evidence=evidence,
    )
    return state, usage


def canonical_zoom_results(file_states, evidence_threshold):
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
                item["start_line"],
                item["end_line"],
            )
        )
        files.append({
            "path": state["path"],
            "score": max(
                item["relevance"] for item in evidence
            ),
            "phase1_score": state["phase1_score"],
            "termination": state["termination"],
            "rounds": state["round"],
            "evidence": [
                {
                    "start_line": item["start_line"],
                    "end_line": item["end_line"],
                    "score": item["relevance"],
                    "content": item["content"],
                    "region_id": item["region_id"],
                    "depth": item["depth"],
                }
                for item in evidence
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
    evidence_threshold=DEFAULT_EVIDENCE_THRESHOLD,
    coarse_regions=DEFAULT_COARSE_REGIONS,
    probe_lines=DEFAULT_PROBE_LINES,
    beam_width=DEFAULT_BEAM_WIDTH,
    beam_mass=DEFAULT_BEAM_MASS,
    exploration_slots=DEFAULT_EXPLORATION_SLOTS,
    target_region_lines=DEFAULT_TARGET_REGION_LINES,
    exploration_floor=DEFAULT_EXPLORATION_FLOOR,
    max_rounds=DEFAULT_MAX_ZOOM_ROUNDS,
    stable_rounds=DEFAULT_STABLE_ROUNDS,
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
        state, current = run_zoom_file(
            root,
            query,
            candidate,
            decider,
            trace,
            coarse_regions=coarse_regions,
            probe_lines=probe_lines,
            beam_width=beam_width,
            beam_mass=beam_mass,
            exploration_slots=exploration_slots,
            target_region_lines=target_region_lines,
            exploration_floor=exploration_floor,
            max_rounds=max_rounds,
            stable_rounds=stable_rounds,
        )
        merge_usage(usage, current)
        if state is not None:
            file_states.append(state)

    result_files = canonical_zoom_results(
        file_states,
        evidence_threshold,
    )
    metrics = {
        **phase1_metrics,
        **usage,
        "file_runtimes": len(file_states),
        "observations": sum(
            len(item["observations"]) for item in file_states
        ),
        "valuable_files": len(result_files),
        "evidence_regions": sum(
            len(item["evidence"]) for item in result_files
        ),
        "probability_frontier_converged": sum(
            item["termination"] == "probability_frontier_converged"
            for item in file_states
        ),
        "round_budget_exhausted": sum(
            item["termination"] == "round_budget_exhausted"
            for item in file_states
        ),
        "elapsed_ms": round(
            (time.perf_counter() - started) * 1000,
            3,
        ),
    }

    result = {
        "query": query,
        "root": str(Path(root).resolve()),
        "model": decider.model,
        "architecture": "adaptive_semantic_zoom_search_v0",
        "parameters": {
            "coarse_regions": coarse_regions,
            "probe_lines": probe_lines,
            "beam_width": beam_width,
            "beam_mass": beam_mass,
            "exploration_slots": exploration_slots,
            "target_region_lines": target_region_lines,
            "exploration_floor": exploration_floor,
            "max_rounds": max_rounds,
            "stable_rounds": stable_rounds,
        },
        "directories": directories,
        "files": selected_files,
        "file_states": file_states,
        "result_files": result_files,
        "metrics": metrics,
    }
    trace.emit("adaptive_zoom_completed", result=result)
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
        "--evidence-threshold",
        type=float,
        default=DEFAULT_EVIDENCE_THRESHOLD,
    )
    parser.add_argument(
        "--coarse-regions",
        type=int,
        default=DEFAULT_COARSE_REGIONS,
    )
    parser.add_argument(
        "--probe-lines",
        type=int,
        default=DEFAULT_PROBE_LINES,
    )
    parser.add_argument(
        "--beam-width",
        type=int,
        default=DEFAULT_BEAM_WIDTH,
    )
    parser.add_argument(
        "--beam-mass",
        type=float,
        default=DEFAULT_BEAM_MASS,
    )
    parser.add_argument(
        "--exploration-slots",
        type=int,
        default=DEFAULT_EXPLORATION_SLOTS,
    )
    parser.add_argument(
        "--target-region-lines",
        type=int,
        default=DEFAULT_TARGET_REGION_LINES,
    )
    parser.add_argument(
        "--exploration-floor",
        type=float,
        default=DEFAULT_EXPLORATION_FLOOR,
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ZOOM_ROUNDS,
    )
    parser.add_argument(
        "--stable-rounds",
        type=int,
        default=DEFAULT_STABLE_ROUNDS,
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
        decider = OfflineAdaptiveZoomDecider(trace)
    else:
        key = os.getenv("TYPESAFE_API_KEY", "")
        if not key:
            print(
                "TYPESAFE_API_KEY is required unless --offline-decider is used.",
                file=sys.stderr,
            )
            return 2
        decider = AdaptiveZoomDecider(
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
        evidence_threshold=args.evidence_threshold,
        coarse_regions=args.coarse_regions,
        probe_lines=args.probe_lines,
        beam_width=args.beam_width,
        beam_mass=args.beam_mass,
        exploration_slots=args.exploration_slots,
        target_region_lines=args.target_region_lines,
        exploration_floor=args.exploration_floor,
        max_rounds=args.max_rounds,
        stable_rounds=args.stable_rounds,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
        print(json.dumps(result["metrics"], ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
