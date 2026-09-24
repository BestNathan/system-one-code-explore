import tempfile
import unittest
from pathlib import Path

from system_one_relevance_frontier import (
    OfflineChoiceRelevanceFrontierDecider,
    generate_actions,
    new_file_state,
    phase0_coarse_scan,
)


class DummyTrace:
    def __init__(self):
        self.events = []

    def emit(self, kind, **payload):
        self.events.append((kind, payload))


class Phase0ChoiceTests(unittest.TestCase):
    def test_phase0_observes_every_coarse_region(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "demo.rs"
            path.write_text(
                "\n".join(
                    "TARGET" if i == 500 else f"line {i}"
                    for i in range(1, 1001)
                ),
                encoding="utf-8",
            )
            candidate = {
                "id": "f1",
                "score": 0.9,
                "payload": {"path": "demo.rs", "extension": ".rs"},
            }
            state = new_file_state(root, candidate, 24)
            trace = DummyTrace()
            decider = OfflineChoiceRelevanceFrontierDecider(trace)

            usage = phase0_coarse_scan(
                root,
                "find TARGET",
                state,
                decider,
                trace,
                64,
            )

            coarse = [
                node for node in state["nodes"].values()
                if node["depth"] == 0
            ]
            self.assertEqual(len(coarse), 3)
            self.assertTrue(all(node["observation_ids"] for node in coarse))
            self.assertTrue(state["phase0"]["all_regions_observed"])
            self.assertEqual(usage["model_calls"], 0)

    def test_after_phase0_missing_frontier_cannot_starve_coarse_regions(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "demo.rs"
            path.write_text("\n".join(f"line {i}" for i in range(1, 1001)))
            candidate = {
                "id": "f1",
                "score": 0.9,
                "payload": {"path": "demo.rs", "extension": ".rs"},
            }
            state = new_file_state(root, candidate, 24)
            trace = DummyTrace()
            decider = OfflineChoiceRelevanceFrontierDecider(trace)

            phase0_coarse_scan(
                root,
                "find target",
                state,
                decider,
                trace,
                64,
            )
            actions = generate_actions(
                state,
                max_actions=1,
                target_region_lines=48,
                refine_threshold=0.72,
                gradient_threshold=0.18,
                volatility_threshold=0.12,
            )
            self.assertTrue(actions)
            self.assertTrue(
                all(
                    state["nodes"][a["node_id"]]["depth"] >= 0
                    for a in actions
                )
            )


if __name__ == "__main__":
    unittest.main()
