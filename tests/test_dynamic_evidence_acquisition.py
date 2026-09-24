import tempfile
import unittest
from pathlib import Path

from dynamic_evidence_acquisition import (
    partition_actions,
    run_dynamic_evidence,
)
from system_one_code_locator import empty_usage


class FakeDecider:
    def __init__(self, rounds):
        self.rounds = list(rounds)

    def score_actions(
        self,
        goal,
        path,
        phase0_run,
        remaining,
        selected,
        *,
        batch_size,
    ):
        probabilities = self.rounds.pop(0)
        scored = [
            {
                **action,
                "noul_probability": float(
                    probabilities.get(action["id"], 0.0)
                ),
            }
            for action in remaining
        ]
        scored.sort(
            key=lambda item: (
                -item["noul_probability"],
                item["start_line"],
            )
        )
        return scored, empty_usage()


class DynamicEvidenceAcquisitionTests(unittest.TestCase):
    def phase0(self, line_count):
        return {
            "posterior_estimator": "demo",
            "probes": 4,
            "sample_lines": 8,
            "subject": {"path": "demo.rs"},
            "frontier": {
                "line_count": line_count,
                "relevance": [0.5] * line_count,
                "uncertainty": [0.8] * line_count,
                "observed": [False] * line_count,
            },
        }

    def test_partition_actions_cover_file_without_overlap(self):
        actions = partition_actions(70, tile_lines=32)
        self.assertEqual(
            [(x["start_line"], x["end_line"]) for x in actions],
            [(1, 32), (33, 64), (65, 70)],
        )

    def test_reads_all_actions_above_threshold_in_same_round(self):
        source = "\n".join(f"line {i}" for i in range(1, 97))
        decider = FakeDecider([
            {
                "tile_001": 0.83,
                "tile_002": 0.72,
                "tile_003": 0.31,
            },
            {
                "tile_003": 0.44,
            },
        ])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run_dynamic_evidence(
                path,
                "find target",
                self.phase0(96),
                decider,
                tile_lines=32,
                threshold=0.65,
                max_rounds=10,
            )

        self.assertEqual(
            result["termination"],
            "all_remaining_below_threshold",
        )
        self.assertEqual(result["selected_count"], 2)
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(
            [x["id"] for x in result["selected_evidence"]],
            ["tile_001", "tile_002"],
        )
        self.assertEqual(
            [x["id"] for x in result["remaining_actions"]],
            ["tile_003"],
        )

    def test_selected_evidence_changes_next_round_action_set(self):
        source = "\n".join(f"line {i}" for i in range(1, 65))
        decider = FakeDecider([
            {
                "tile_001": 0.9,
                "tile_002": 0.8,
            },
        ])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run_dynamic_evidence(
                path,
                "find target",
                self.phase0(64),
                decider,
                tile_lines=32,
                threshold=0.65,
                max_rounds=10,
            )

        self.assertEqual(
            result["termination"],
            "action_space_exhausted",
        )
        self.assertEqual(result["selected_count"], 2)
        self.assertEqual(result["remaining_actions"], [])

    def test_stops_immediately_when_all_noul_scores_are_low(self):
        source = "\n".join(f"line {i}" for i in range(1, 65))
        decider = FakeDecider([{
            "tile_001": 0.52,
            "tile_002": 0.61,
        }])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run_dynamic_evidence(
                path,
                "find target",
                self.phase0(64),
                decider,
                tile_lines=32,
                threshold=0.65,
                max_rounds=10,
            )

        self.assertEqual(
            result["termination"],
            "all_remaining_below_threshold",
        )
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["rounds"], 1)


if __name__ == "__main__":
    unittest.main()
