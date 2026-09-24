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


class Phase0ChoiceV2Tests(unittest.TestCase):
    def test_choice_action_space_can_expose_multiple_legal_actions(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "demo.rs"
            path.write_text("\n".join("TARGET" if i in {500, 1500} else f"line {i}" for i in range(1, 2001)))
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
                max_actions=6,
                target_region_lines=48,
                refine_threshold=0.72,
                gradient_threshold=0.15,
                volatility_threshold=0.10,
            )
            self.assertGreaterEqual(len(actions), 2)
            self.assertLessEqual(len(actions), 6)


if __name__ == "__main__":
    unittest.main()
