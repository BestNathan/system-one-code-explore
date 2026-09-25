import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from frontier_obligation_runtime import (
    build_frontier_obligations,
    run,
)
from system_one_code_locator import empty_usage


class FakeDecider:
    def __init__(self, directional, utilities):
        self.directional = list(directional)
        self.utilities = list(utilities)

    def assess_directional_closure(
        self,
        goal,
        path,
        anchor,
        actions_by_id,
        ordered_ids,
        source_lines,
    ):
        spec = self.directional.pop(0)
        before_id = None
        after_id = None
        positions = {
            action_id: index
            for index, action_id in enumerate(ordered_ids)
        }
        indices = sorted(
            positions[tile_id]
            for tile_id in anchor["tile_ids"]
        )
        if indices[0] > 0:
            before_id = ordered_ids[indices[0] - 1]
        if indices[-1] + 1 < len(ordered_ids):
            after_id = ordered_ids[indices[-1] + 1]
        return {
            "before": {
                "tile_id": before_id,
                "probability": spec.get("before", 0.0),
            },
            "after": {
                "tile_id": after_id,
                "probability": spec.get("after", 0.0),
            },
        }, empty_usage()

    def assess_final_utility(
        self,
        goal,
        path,
        anchor,
        actions_by_id,
        source_lines,
    ):
        return float(self.utilities.pop(0)), empty_usage()


class R15Tests(unittest.TestCase):
    def frontier(self, tile_scores, tile_lines=32):
        relevance = []
        for score in tile_scores:
            relevance.extend([score] * tile_lines)
        return {
            "line_count": len(relevance),
            "relevance": relevance,
            "uncertainty": [0.5] * len(relevance),
            "observed": [False] * len(relevance),
        }

    def phase0(self, tile_scores):
        frontier = self.frontier(tile_scores)
        return {
            "subject": {"path": "demo.rs"},
            "posterior_estimator": "demo",
            "probes": 4,
            "frontier": frontier,
        }

    def test_flat_high_plateau_becomes_one_obligation(self):
        actions, obligations, geometry = build_frontier_obligations(
            self.frontier([0.8] * 8),
            tile_lines=32,
            quantile=0.75,
        )
        self.assertEqual(len(actions), 8)
        self.assertEqual(len(obligations), 1)
        self.assertEqual(
            obligations[0]["range"],
            [1, 256],
        )
        self.assertEqual(
            len(obligations[0]["tile_ids"]),
            8,
        )
        self.assertEqual(
            geometry["qualifying_tile_count"],
            8,
        )

    def test_separated_high_modes_become_separate_obligations(self):
        _, obligations, _ = build_frontier_obligations(
            self.frontier([
                0.10,
                0.20,
                0.90,
                0.85,
                0.10,
                0.15,
                0.80,
                0.82,
            ]),
            tile_lines=32,
            quantile=0.75,
        )
        self.assertEqual(len(obligations), 2)
        self.assertEqual(
            obligations[0]["tile_ids"],
            ["tile_003", "tile_004"],
        )
        self.assertEqual(
            obligations[1]["tile_ids"],
            ["tile_008"],
        )

    def test_directional_closure_happens_before_utility(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 161)
        )
        decider = FakeDecider(
            directional=[
                {"before": 0.2, "after": 0.9},
                {"before": 0.2, "after": 0.2},
            ],
            utilities=[0.9],
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "understand target",
                self.phase0([
                    0.1,
                    0.2,
                    0.9,
                    0.4,
                    0.1,
                ]),
                decider,
                frontier_quantile=0.75,
                expansion_threshold=0.60,
                final_utility_threshold=0.65,
            )

        self.assertEqual(
            result["termination"],
            "all_obligations_resolved",
        )
        self.assertEqual(
            result["obligations"][0]["status"],
            "satisfied",
        )
        anchor = result["anchors"][0]
        self.assertEqual(
            anchor["status"],
            "retained",
        )
        self.assertEqual(
            len(anchor["tile_ids"]),
            2,
        )
        self.assertEqual(
            anchor["final_utility_probability"],
            0.9,
        )
        self.assertEqual(
            len(anchor["closure_steps"]),
            2,
        )

    def test_low_post_closure_utility_tries_next_seed(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 257)
        )
        decider = FakeDecider(
            directional=[
                {"before": 0.1, "after": 0.1},
                {"before": 0.1, "after": 0.1},
            ],
            utilities=[0.2, 0.9],
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "find material behavior",
                self.phase0([0.8] * 8),
                decider,
                frontier_quantile=0.75,
                expansion_threshold=0.60,
                final_utility_threshold=0.65,
            )

        self.assertEqual(len(result["obligations"]), 1)
        obligation = result["obligations"][0]
        self.assertEqual(
            obligation["status"],
            "satisfied",
        )
        self.assertEqual(
            len(obligation["attempted_seed_ids"]),
            2,
        )
        self.assertEqual(len(result["anchors"]), 2)
        self.assertEqual(
            result["anchors"][0]["status"],
            "rejected_low_utility",
        )
        self.assertEqual(
            result["anchors"][1]["status"],
            "retained",
        )

    def test_obligation_exhausts_only_after_all_candidates_fail(self):
        source = "\n".join(
            f"line {i}"
            for i in range(1, 129)
        )
        decider = FakeDecider(
            directional=[
                {"before": 0.1, "after": 0.1},
                {"before": 0.1, "after": 0.1},
                {"before": 0.1, "after": 0.1},
                {"before": 0.1, "after": 0.1},
            ],
            utilities=[0.1, 0.2, 0.3, 0.4],
        )

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run(
                path,
                "find target",
                self.phase0([0.8] * 4),
                decider,
                frontier_quantile=0.75,
            )

        self.assertEqual(
            result["obligations"][0]["status"],
            "exhausted",
        )
        self.assertEqual(
            len(result["obligations"][0]["attempted_seed_ids"]),
            4,
        )


if __name__ == "__main__":
    unittest.main()
