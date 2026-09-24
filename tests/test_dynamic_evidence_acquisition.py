import json
import tempfile
import unittest
from pathlib import Path

from dynamic_evidence_acquisition import (
    partition_actions,
    run_dynamic_evidence,
)
from system_one_code_locator import empty_usage


class FakeDecider:
    def __init__(self, decisions):
        self.decisions = list(decisions)

    def choose_next(self, goal, path, phase0_run, remaining, selected):
        return self.decisions.pop(0), empty_usage()


class DynamicEvidenceAcquisitionTests(unittest.TestCase):
    def test_partition_actions_cover_file_without_overlap(self):
        actions = partition_actions(70, tile_lines=32)
        self.assertEqual(
            [(x["start_line"], x["end_line"]) for x in actions],
            [(1, 32), (33, 64), (65, 70)],
        )

    def test_reads_one_tile_then_stops_on_stop_anchor(self):
        source = "\n".join(f"line {i}" for i in range(1, 65))
        phase0 = {
            "posterior_estimator": "demo",
            "probes": 4,
            "sample_lines": 8,
            "subject": {"path": "demo.rs"},
            "frontier": {
                "line_count": 64,
                "relevance": [0.5] * 64,
                "uncertainty": [0.8] * 64,
                "observed": [False] * 64,
            },
        }
        decider = FakeDecider([
            {
                "choice": "tile_002",
                "confidence": 0.8,
                "probabilities": {
                    "tile_001": 0.20,
                    "tile_002": 0.65,
                    "stop": 0.15,
                },
            },
            {
                "choice": "stop",
                "confidence": 0.9,
                "probabilities": {
                    "tile_001": 0.25,
                    "stop": 0.75,
                },
            },
        ])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run_dynamic_evidence(
                path,
                "find target",
                phase0,
                decider,
                tile_lines=32,
                minimum_lift=1.1,
                max_rounds=10,
            )

        self.assertEqual(result["termination"], "stop_outweighs_best_read")
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(
            (
                result["selected_evidence"][0]["start_line"],
                result["selected_evidence"][0]["end_line"],
            ),
            (33, 64),
        )
        self.assertEqual(
            [x["id"] for x in result["remaining_actions"]],
            ["tile_001"],
        )

    def test_stops_when_choice_is_not_above_uniform_lift(self):
        source = "\n".join(f"line {i}" for i in range(1, 65))
        phase0 = {
            "posterior_estimator": "demo",
            "probes": 4,
            "sample_lines": 8,
            "subject": {"path": "demo.rs"},
            "frontier": {
                "line_count": 64,
                "relevance": [0.5] * 64,
                "uncertainty": [0.8] * 64,
                "observed": [False] * 64,
            },
        }
        decider = FakeDecider([{
            "choice": "tile_001",
            "confidence": 0.4,
            "probabilities": {
                "tile_001": 0.35,
                "tile_002": 0.34,
                "stop": 0.31,
            },
        }])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.rs"
            path.write_text(source + "\n", encoding="utf-8")
            result = run_dynamic_evidence(
                path,
                "find target",
                phase0,
                decider,
                tile_lines=32,
                minimum_lift=1.1,
                max_rounds=10,
            )

        self.assertEqual(
            result["termination"],
            "no_read_above_uniform_lift",
        )
        self.assertEqual(result["selected_count"], 0)


if __name__ == "__main__":
    unittest.main()
