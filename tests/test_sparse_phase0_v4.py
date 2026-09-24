import tempfile
import unittest
from pathlib import Path

from system_one_code_locator import Trace
from system_one_relevance_frontier import new_file_state
from system_one_sparse_phase0 import (
    OfflineSparsePhase0ClosureDecider,
    bootstrap_micro_ranges,
    phase0_probe_actions,
    phase0_sparse_scan,
)


class DummyTrace:
    def emit(self, *args, **kwargs):
        pass


class SparsePhase0Tests(unittest.TestCase):
    def test_bootstrap_cost_does_not_scale_with_file_length(self):
        short = bootstrap_micro_ranges(3000, 8)
        huge = bootstrap_micro_ranges(300000, 8)
        self.assertEqual(len(short), 3)
        self.assertEqual(len(huge), 3)
        self.assertTrue(all(right - left + 1 <= 8 for _, left, right in huge))

    def test_sparse_phase0_reads_only_micro_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "demo.rs"
            path.write_text(
                "\n".join(f"line {i}" for i in range(1, 10001)) + "\n",
                encoding="utf-8",
            )
            candidate = {
                "score": 0.9,
                "payload": {"path": "demo.rs", "extension": ".rs"},
            }
            state = new_file_state(root, candidate, 24)
            decider = OfflineSparsePhase0ClosureDecider(DummyTrace())
            usage = phase0_sparse_scan(
                root,
                "find useful code",
                state,
                decider,
                DummyTrace(),
                sample_lines=8,
                max_probes=8,
                max_actions_per_choice=10,
            )

            self.assertEqual(usage["model_calls"], 0)
            self.assertEqual(state["phase0"]["reads"], 5)
            self.assertLessEqual(state["phase0"]["sampled_source_lines"], 40)
            self.assertLessEqual(
                state["phase0"]["sampled_source_coverage"],
                40 / 10000,
            )
            self.assertEqual(state["phase0"]["kind"], "sparse_micro_sampling")

    def test_generated_actions_are_unread_micro_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "demo.rs"
            path.write_text(
                "\n".join(f"line {i}" for i in range(1, 1001)) + "\n",
                encoding="utf-8",
            )
            candidate = {
                "score": 0.9,
                "payload": {"path": "demo.rs", "extension": ".rs"},
            }
            state = new_file_state(root, candidate, 24)
            decider = OfflineSparsePhase0ClosureDecider(DummyTrace())
            phase0_sparse_scan(
                root,
                "find useful code",
                state,
                decider,
                DummyTrace(),
                sample_lines=8,
                max_probes=3,
                max_actions_per_choice=10,
            )
            actions = phase0_probe_actions(
                state,
                sample_lines=8,
                max_actions=10,
            )
            self.assertTrue(actions)
            observed = [
                (item["start_line"], item["end_line"])
                for item in state["observations"]
            ]
            for action in actions:
                self.assertLessEqual(
                    action["sample_end"] - action["sample_start"] + 1,
                    8,
                )
                self.assertFalse(
                    any(
                        max(action["sample_start"], left)
                        <= min(action["sample_end"], right)
                        for left, right in observed
                    )
                )


if __name__ == "__main__":
    unittest.main()
