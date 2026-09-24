import tempfile
import unittest
from pathlib import Path

from multi_objective_evidence_acquisition import (
    merge_regions,
    partition_actions,
    run,
)
from system_one_code_locator import empty_usage


class FakeDecider:
    def __init__(self, acquisitions, assessments):
        self.acquisitions = list(acquisitions)
        self.assessments = list(assessments)

    def score_acquisition_actions(
        self,
        goal,
        path,
        phase0_run,
        remaining,
        selected,
        source_lines,
        *,
        batch_size=12,
    ):
        values = self.acquisitions.pop(0)
        out = []
        for action in remaining:
            coverage, utility = values.get(
                action["id"],
                (0.0, 0.0),
            )
            out.append({
                **action,
                "coverage_probability": coverage,
                "utility_probability": utility,
            })
        out.sort(
            key=lambda x: (
                -max(
                    x["coverage_probability"],
                    x["utility_probability"],
                ),
                x["start_line"],
            )
        )
        return out, empty_usage()

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
        values = self.assessments.pop(0)
        out = []
        by_range = {
            (x["start_line"], x["end_line"]): x
            for x in remaining
        }
        for region in regions:
            key = (region["start_line"], region["end_line"])
            spec = values.get(
                key,
                {
                    "utility": 0.0,
                    "complete": 1.0,
                    "before": 0.0,
                    "after": 0.0,
                },
            )
            before = by_range.get(
                (
                    region["start_line"] - 32,
                    region["start_line"] - 1,
                )
            )
            after = by_range.get(
                (
                    region["end_line"] + 1,
                    region["end_line"] + 32,
                )
            )
            out.append({
                "start_line": region["start_line"],
                "end_line": region["end_line"],
                "tile_ids": list(region["tile_ids"]),
                "utility_probability": spec["utility"],
                "completeness_probability": spec["complete"],
                "before": (
                    {
                        "action": before,
                        "probability": spec["before"],
                    }
                    if before else None
                ),
                "after": (
                    {
                        "action": after,
                        "probability": spec["after"],
                    }
                    if after else None
                ),
            })
        return out, empty_usage()


class R13Tests(unittest.TestCase):
    def phase0(self, n):
        return {
            "subject": {"path": "demo.rs"},
            "posterior_estimator": "demo",
            "probes": 4,
            "frontier": {
                "line_count": n,
                "relevance": [0.5] * n,
                "uncertainty": [0.8] * n,
                "observed": [False] * n,
            },
        }

    def test_partition_and_merge(self):
        actions = partition_actions(96, 32)
        self.assertEqual(
            [(x["start_line"], x["end_line"]) for x in actions],
            [(1, 32), (33, 64), (65, 96)],
        )
        merged = merge_regions([
            {**actions[0], "content": "a"},
            {**actions[1], "content": "b"},
        ])
        self.assertEqual(
            [(x["start_line"], x["end_line"]) for x in merged],
            [(1, 64)],
        )

    def test_incomplete_useful_fragment_expands_after(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 97)
        )
        decider = FakeDecider(
            acquisitions=[
                {
                    "tile_002": (0.8, 0.8),
                    "tile_001": (0.2, 0.2),
                    "tile_003": (0.2, 0.2),
                },
                {
                    "tile_001": (0.2, 0.2),
                },
            ],
            assessments=[
                {
                    (33, 64): {
                        "utility": 0.9,
                        "complete": 0.2,
                        "before": 0.1,
                        "after": 0.9,
                    }
                },
                {
                    (33, 96): {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.1,
                        "after": 0.0,
                    }
                },
                {
                    (33, 96): {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.1,
                        "after": 0.0,
                    }
                },
            ],
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "understand the target function",
                self.phase0(96),
                decider,
                max_rounds=4,
            )

        self.assertEqual(
            result["termination"],
            "coverage_utility_and_closure_satisfied",
        )
        self.assertEqual(
            [(x["start_line"], x["end_line"])
             for x in result["final_regions"]],
            [(33, 96)],
        )
        reasons = {
            x["reason"]
            for x in result["selected_evidence"]
        }
        self.assertIn("frontier_or_utility", reasons)
        self.assertIn("semantic_closure_after", reasons)

    def test_relevant_but_complete_fragment_does_not_expand(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 65)
        )
        decider = FakeDecider(
            acquisitions=[
                {
                    "tile_001": (0.8, 0.8),
                    "tile_002": (0.2, 0.2),
                },
                {
                    "tile_002": (0.2, 0.2),
                },
            ],
            assessments=[
                {
                    (1, 32): {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.0,
                        "after": 0.1,
                    }
                },
                {
                    (1, 32): {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.0,
                        "after": 0.1,
                    }
                },
                {
                    (1, 32): {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.0,
                        "after": 0.1,
                    }
                },
            ],
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "find target",
                self.phase0(64),
                decider,
                max_rounds=4,
            )

        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(
            result["selected_evidence"][0]["reason"],
            "frontier_or_utility",
        )


if __name__ == "__main__":
    unittest.main()
