#!/usr/bin/env python3
"""R19: paired geometry evaluation with shared semantic System One decisions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

from frontier_obligation_runtime import (
    FrontierObligationDecider,
    run as run_frontier_obligations,
)
from system_one_code_locator import Trace, empty_usage


VOLATILE_KEYS = {"anchor_id", "obligation_id"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonicalize(value):
    if isinstance(value, dict):
        return {
            key: canonicalize(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def semantic_cache_key(stage, state, questions):
    payload = {
        "stage": stage,
        "state": canonicalize(state),
        "questions": canonicalize(questions),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SharedDecisionCache:
    def __init__(self):
        self.entries = {}
        self.hits = 0
        self.misses = 0
        self.physical_usage = empty_usage()
        self.events = []

    def record_usage(self, usage):
        for key in self.physical_usage:
            self.physical_usage[key] += int(
                usage.get(key, 0) or 0
            )


class CachedFrontierObligationDecider(FrontierObligationDecider):
    def __init__(
        self,
        key,
        trace,
        shared_cache,
        endpoint,
        model,
        arm,
    ):
        super().__init__(key, trace, endpoint, model)
        self.shared_cache = shared_cache
        self.arm = arm
        self.logical_cache_hits = 0
        self.logical_cache_misses = 0

    def send(self, stage, state, questions):
        key = semantic_cache_key(stage, state, questions)
        entry = self.shared_cache.entries.get(key)
        if entry is not None:
            self.shared_cache.hits += 1
            self.logical_cache_hits += 1
            event = {
                "arm": self.arm,
                "stage": stage,
                "cache_key": key,
                "hit": True,
            }
            self.shared_cache.events.append(event)
            self.trace.emit(
                "counterfactual_cache_hit",
                **event,
            )
            # Return original logical usage so standalone cost remains
            # comparable even though the paired experiment made no new call.
            return (
                copy.deepcopy(entry["response"]),
                copy.deepcopy(entry["usage"]),
            )

        response, usage = super().send(stage, state, questions)
        stored = {
            "response": copy.deepcopy(response),
            "usage": copy.deepcopy(usage),
        }
        self.shared_cache.entries[key] = stored
        self.shared_cache.misses += 1
        self.logical_cache_misses += 1
        self.shared_cache.record_usage(usage)
        event = {
            "arm": self.arm,
            "stage": stage,
            "cache_key": key,
            "hit": False,
        }
        self.shared_cache.events.append(event)
        self.trace.emit(
            "counterfactual_cache_miss",
            **event,
        )
        return response, usage


def normalized_semantic_result(result):
    return {
        "materialized_ranges": [
            [
                int(item["start_line"]),
                int(item["end_line"]),
            ]
            for item in result.get("materialized_evidence", [])
        ],
        "final_regions": [
            [
                int(item["start_line"]),
                int(item["end_line"]),
            ]
            for item in result.get("final_regions", [])
        ],
        "anchors": [
            {
                "obligation_range": list(
                    anchor["obligation_range"]
                ),
                "seed_range": list(anchor["seed_range"]),
                "tile_ids": list(anchor["tile_ids"]),
                "status": anchor["status"],
                "final_utility_probability": anchor.get(
                    "final_utility_probability"
                ),
                "closure_steps": [
                    {
                        "range_before": list(
                            step["range_before"]
                        ),
                        "need_before": {
                            "tile_id": step["need_before"][
                                "tile_id"
                            ],
                            "probability": float(
                                step["need_before"][
                                    "probability"
                                ]
                            ),
                        },
                        "need_after": {
                            "tile_id": step["need_after"][
                                "tile_id"
                            ],
                            "probability": float(
                                step["need_after"][
                                    "probability"
                                ]
                            ),
                        },
                        "range_after": list(
                            step["range_after"]
                        ),
                    }
                    for step in anchor.get(
                        "closure_steps",
                        [],
                    )
                ],
            }
            for anchor in result.get("anchors", [])
        ],
    }


def run_pair(
    source,
    goal,
    phase0_run,
    *,
    api_key,
    endpoint,
    model,
    output_dir,
    tile_lines=32,
    frontier_quantile=0.75,
    expansion_threshold=0.60,
    final_utility_threshold=0.65,
    max_anchor_tiles=12,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cache = SharedDecisionCache()
    arms = {}

    for arm, geometry in (
        ("baseline", "q75_components"),
        ("hybrid", "q75_plus_multiscale_seed"),
    ):
        arm_dir = output_dir / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        decider = CachedFrontierObligationDecider(
            api_key,
            Trace(arm_dir / "trace.jsonl"),
            cache,
            endpoint,
            model,
            arm,
        )
        result = run_frontier_obligations(
            source,
            goal,
            phase0_run,
            decider,
            tile_lines=tile_lines,
            frontier_quantile=frontier_quantile,
            expansion_threshold=expansion_threshold,
            final_utility_threshold=final_utility_threshold,
            max_anchor_tiles=max_anchor_tiles,
            obligation_geometry=geometry,
        )
        result["counterfactual_cache"] = {
            "logical_hits": decider.logical_cache_hits,
            "logical_misses": decider.logical_cache_misses,
        }
        (arm_dir / "run.json").write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        arms[arm] = result

    secondary_count = int(
        arms["hybrid"]
        .get("frontier_geometry", {})
        .get("secondary_obligation_count", 0)
    )
    baseline_semantic = normalized_semantic_result(
        arms["baseline"]
    )
    hybrid_semantic = normalized_semantic_result(
        arms["hybrid"]
    )
    identical_when_no_secondary = (
        baseline_semantic == hybrid_semantic
        if secondary_count == 0
        else None
    )
    if secondary_count == 0 and not identical_when_no_secondary:
        raise AssertionError(
            "counterfactual invariant violated: hybrid added no secondary "
            "obligations but semantic evidence diverged"
        )

    pair = {
        "schema_version": 1,
        "kind": "r19-counterfactual-geometry-pair",
        "goal": goal,
        "subject": phase0_run.get("subject"),
        "posterior_estimator": phase0_run.get(
            "posterior_estimator"
        ),
        "secondary_obligation_count": secondary_count,
        "identical_when_no_secondary": identical_when_no_secondary,
        "cache": {
            "entries": len(cache.entries),
            "hits": cache.hits,
            "misses": cache.misses,
            "physical_usage": cache.physical_usage,
            "events": cache.events,
        },
        "logical_usage": {
            "baseline": arms["baseline"]["usage"],
            "hybrid": arms["hybrid"]["usage"],
        },
        "semantic": {
            "baseline": baseline_semantic,
            "hybrid": hybrid_semantic,
        },
    }
    (output_dir / "pair.json").write_text(
        json.dumps(pair, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pair


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--phase0-run", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tile-lines", type=int, default=32)
    parser.add_argument(
        "--frontier-quantile",
        type=float,
        default=0.75,
    )
    parser.add_argument(
        "--expansion-threshold",
        type=float,
        default=0.60,
    )
    parser.add_argument(
        "--final-utility-threshold",
        type=float,
        default=0.65,
    )
    parser.add_argument(
        "--max-anchor-tiles",
        type=int,
        default=12,
    )
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

    pair = run_pair(
        args.source,
        args.goal,
        load(args.phase0_run),
        api_key=api_key,
        endpoint=args.endpoint,
        model=args.model,
        output_dir=args.output_dir,
        tile_lines=args.tile_lines,
        frontier_quantile=args.frontier_quantile,
        expansion_threshold=args.expansion_threshold,
        final_utility_threshold=args.final_utility_threshold,
        max_anchor_tiles=args.max_anchor_tiles,
    )
    print(json.dumps({
        "secondary_obligation_count": pair[
            "secondary_obligation_count"
        ],
        "identical_when_no_secondary": pair[
            "identical_when_no_secondary"
        ],
        "cache": pair["cache"],
    }, indent=2))


if __name__ == "__main__":
    main()
