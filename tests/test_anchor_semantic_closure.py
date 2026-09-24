import tempfile
import unittest
from pathlib import Path

from anchor_semantic_closure import (
    merge_final_anchor_ranges,
    run,
)
from system_one_code_locator import empty_usage


class FakeDecider:
    def __init__(self, acquisition_rounds, anchor_rounds, final_round):
        self.acquisition_rounds = list(acquisition_rounds)
        self.anchor_rounds = list(anchor_rounds)
        self.final_round = final_round

    def score_acquisition(
        self,
        goal,
        path,
        remaining,
        materialized,
    ):
        values = self.acquisition_rounds.pop(0)
        scored = []
        for action in remaining:
            coverage, utility = values.get(
                action["id"],
                (0.0, 0.0),
            )
            scored.append({
                **action,
                "coverage_probability": coverage,
                "utility_probability": utility,
            })
        scored.sort(
            key=lambda x: (
                -max(
                    x["coverage_probability"],
                    x["utility_probability"],
                ),
                x["start_line"],
            )
        )
        return scored, empty_usage()

    def assess_anchors(
        self,
        goal,
        path,
        anchors,
        actions_by_id,
        ordered_ids,
        materialized,
        source_lines,
    ):
        if self.anchor_rounds:
            values = self.anchor_rounds.pop(0)
        else:
            values = self.final_round

        out = []
        positions = {
            action_id: i
            for i, action_id in enumerate(ordered_ids)
        }
        for anchor in anchors:
            spec = values.get(
                anchor["id"],
                {
                    "utility": 0.0,
                    "complete": 1.0,
                    "before": 0.0,
                    "after": 0.0,
                },
            )
            indices = sorted(
                positions[tile_id]
                for tile_id in anchor["tile_ids"]
            )
            before_id = (
                ordered_ids[indices[0] - 1]
                if indices[0] > 0 else None
            )
            after_id = (
                ordered_ids[indices[-1] + 1]
                if indices[-1] + 1 < len(ordered_ids)
                else None
            )
            out.append({
                "anchor_id": anchor["id"],
                "utility_probability": spec["utility"],
                "completeness_probability": spec["complete"],
                "before": (
                    {
                        "tile_id": before_id,
                        "probability": spec["before"],
                    }
                    if before_id else None
                ),
                "after": (
                    {
                        "tile_id": after_id,
                        "probability": spec["after"],
                    }
                    if after_id else None
                ),
            })
        return out, empty_usage()


class AnchorClosureTests(unittest.TestCase):
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

    def test_anchor_expands_only_its_own_local_unit(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 129)
        )
        decider = FakeDecider(
            acquisition_rounds=[
                {
                    "tile_002": (0.8, 0.8),
                    "tile_004": (0.8, 0.8),
                },
                {},
            ],
            anchor_rounds=[
                {
                    "anchor_001": {
                        "utility": 0.9,
                        "complete": 0.2,
                        "before": 0.1,
                        "after": 0.9,
                    },
                    "anchor_002": {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.1,
                        "after": 0.1,
                    },
                },
                {
                    "anchor_001": {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.1,
                        "after": 0.1,
                    },
                    "anchor_002": {
                        "utility": 0.9,
                        "complete": 0.95,
                        "before": 0.1,
                        "after": 0.1,
                    },
                },
            ],
            final_round={
                "anchor_001": {
                    "utility": 0.9,
                    "complete": 0.95,
                    "before": 0.1,
                    "after": 0.1,
                },
                "anchor_002": {
                    "utility": 0.9,
                    "complete": 0.95,
                    "before": 0.1,
                    "after": 0.1,
                },
            },
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "understand two local behaviors",
                self.phase0(128),
                decider,
                max_rounds=4,
            )

        anchors = {
            item["id"]: item
            for item in result["anchors"]
        }
        self.assertEqual(
            anchors["anchor_001"]["tile_ids"],
            ["tile_002", "tile_003"],
        )
        self.assertEqual(
            anchors["anchor_002"]["tile_ids"],
            ["tile_004"],
        )
        self.assertEqual(
            anchors["anchor_001"]["status"],
            "complete",
        )
        self.assertEqual(
            anchors["anchor_002"]["status"],
            "complete",
        )

    def test_false_positive_anchor_does_not_expand(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 65)
        )
        decider = FakeDecider(
            acquisition_rounds=[
                {"tile_001": (0.8, 0.8)},
                {},
            ],
            anchor_rounds=[
                {
                    "anchor_001": {
                        "utility": 0.2,
                        "complete": 0.1,
                        "before": 0.0,
                        "after": 0.9,
                    },
                },
            ],
            final_round={},
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "find target",
                self.phase0(64),
                decider,
                max_rounds=3,
            )

        self.assertEqual(
            result["anchors"][0]["status"],
            "low_utility",
        )
        self.assertEqual(
            result["anchors"][0]["tile_ids"],
            ["tile_001"],
        )
        self.assertEqual(
            result["materialized_count"],
            1,
        )

    def test_merge_happens_only_in_final_output(self):
        actions = {
            "tile_001": {
                "id": "tile_001",
                "start_line": 1,
                "end_line": 32,
            },
            "tile_002": {
                "id": "tile_002",
                "start_line": 33,
                "end_line": 64,
            },
        }
        anchors = [
            {
                "id": "anchor_001",
                "tile_ids": ["tile_001"],
                "status": "complete",
            },
            {
                "id": "anchor_002",
                "tile_ids": ["tile_002"],
                "status": "complete",
            },
        ]
        merged = merge_final_anchor_ranges(
            anchors,
            actions,
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(
            (merged[0]["start_line"], merged[0]["end_line"]),
            (1, 64),
        )
        self.assertEqual(
            set(merged[0]["anchor_ids"]),
            {"anchor_001", "anchor_002"},
        )


if __name__ == "__main__":
    unittest.main()
