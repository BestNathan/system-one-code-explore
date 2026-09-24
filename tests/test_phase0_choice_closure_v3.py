import unittest

from system_one_relevance_frontier import (
    OfflineClosureChoiceRelevanceFrontierDecider,
)


class DummyTrace:
    def emit(self, *args, **kwargs):
        pass


class ClosureChoiceTests(unittest.TestCase):
    def test_adjacent_fragments_are_decided_as_one_group(self):
        decider = OfflineClosureChoiceRelevanceFrontierDecider(DummyTrace())
        state = {"path": "demo.rs"}
        candidates = [
            {
                "id": "a",
                "frontier_node_id": "c1",
                "observation_id": "o1",
                "start_line": 100,
                "end_line": 131,
                "score": 0.9,
                "content": "100: TARGET",
                "score_history": [0.9],
                "navigation": "refine_high",
            },
            {
                "id": "b",
                "frontier_node_id": "c1",
                "observation_id": "o1",
                "start_line": 132,
                "end_line": 163,
                "score": 0.9,
                "content": "132: continuation",
                "score_history": [0.9],
                "navigation": "refine_high",
            },
        ]
        selected, usage = decider.finalize_group_choices(
            "find TARGET",
            state,
            candidates,
        )
        self.assertEqual(usage["model_calls"], 0)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["start_line"], 100)
        self.assertEqual(selected[0]["end_line"], 163)
        self.assertEqual(selected[0]["fragment_count"], 2)


if __name__ == "__main__":
    unittest.main()
