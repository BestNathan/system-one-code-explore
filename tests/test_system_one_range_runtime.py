import importlib.util
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "system_one_range_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "system_one_range_runtime",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RangeActionSpaceTest(unittest.TestCase):
    def test_unread_file_gets_head_middle_tail_without_text_analysis(self):
        file_state = {
            "path": "docs/guide.md",
            "line_count": 1000,
            "coverage": [],
            "last_selected_ranges": [],
        }
        actions = MODULE.generate_file_actions(
            file_state,
            window_lines=100,
            max_jumps=2,
        )
        read_actions = [
            item for item in actions
            if item["kind"] == "read_range"
        ]
        self.assertEqual(
            ["seed_head", "seed_middle", "seed_tail"],
            [item["navigation"] for item in read_actions],
        )
        self.assertEqual((1, 100), (
            actions[0]["start_line"],
            actions[0]["end_line"],
        ))

    def test_read_file_gets_expand_and_geometry_jump_actions(self):
        file_state = {
            "path": "src/large.txt",
            "line_count": 1000,
            "coverage": [[1, 100]],
            "last_selected_ranges": [[1, 100]],
        }
        actions = MODULE.generate_file_actions(
            file_state,
            window_lines=100,
            max_jumps=2,
        )
        by_navigation = {}
        for item in actions:
            if item["kind"] != "read_range":
                continue
            by_navigation.setdefault(item["navigation"], []).append(item)

        self.assertNotIn("expand_before", by_navigation)
        self.assertEqual(
            (101, 200),
            (
                by_navigation["expand_after"][0]["start_line"],
                by_navigation["expand_after"][0]["end_line"],
            ),
        )
        jump = by_navigation["jump"][0]
        self.assertGreaterEqual(jump["start_line"], 101)
        self.assertLessEqual(jump["end_line"], 1000)
        self.assertTrue(
            MODULE.fully_uncovered(
                jump["start_line"],
                jump["end_line"],
                [[1, 100]],
            )
        )

    def test_file_space_always_contains_stop(self):
        file_state = {
            "path": "README.md",
            "line_count": 20,
            "coverage": [],
            "last_selected_ranges": [],
        }
        actions = MODULE.generate_file_actions(
            file_state,
            window_lines=140,
        )
        self.assertEqual("stop_file", actions[-1]["kind"])


class SelectorTest(unittest.TestCase):
    def test_threshold_controls_parallelism(self):
        scored = [
            {
                "id": "a",
                "kind": "read_range",
                "start_line": 1,
                "end_line": 100,
                "score": 0.91,
            },
            {
                "id": "b",
                "kind": "read_range",
                "start_line": 201,
                "end_line": 300,
                "score": 0.72,
            },
            {
                "id": "c",
                "kind": "read_range",
                "start_line": 401,
                "end_line": 500,
                "score": 0.50,
            },
            {"id": "stop", "kind": "stop_file", "score": 0.40},
        ]
        selected, mode = MODULE.select_file_actions(scored, 0.65)
        self.assertEqual(["a", "b"], [item["id"] for item in selected])
        self.assertEqual("parallel_above_threshold", mode)

    def test_no_action_above_threshold_executes_best_read(self):
        scored = [
            {"id": "a", "kind": "read_range", "score": 0.58},
            {"id": "b", "kind": "read_range", "score": 0.40},
            {"id": "stop", "kind": "stop_file", "score": 0.20},
        ]
        selected, mode = MODULE.select_file_actions(scored, 0.65)
        self.assertEqual(["a"], [item["id"] for item in selected])
        self.assertEqual("fallback_top1", mode)

    def test_stop_must_be_high_and_best(self):
        scored = [
            {"id": "read", "kind": "read_range", "score": 0.70},
            {"id": "stop", "kind": "stop_file", "score": 0.76},
        ]
        selected, mode = MODULE.select_file_actions(scored, 0.65)
        self.assertEqual(["stop"], [item["id"] for item in selected])
        self.assertEqual("model_stop", mode)

        scored = [
            {"id": "read", "kind": "read_range", "score": 0.83},
            {"id": "stop", "kind": "stop_file", "score": 0.76},
        ]
        selected, mode = MODULE.select_file_actions(scored, 0.65)
        self.assertEqual(["read"], [item["id"] for item in selected])
        self.assertEqual("parallel_above_threshold", mode)

    def test_parallel_selection_drops_overlapping_ranges(self):
        scored = [
            {
                "id": "a",
                "kind": "read_range",
                "start_line": 100,
                "end_line": 239,
                "score": 0.90,
            },
            {
                "id": "b",
                "kind": "read_range",
                "start_line": 180,
                "end_line": 319,
                "score": 0.85,
            },
            {
                "id": "c",
                "kind": "read_range",
                "start_line": 400,
                "end_line": 539,
                "score": 0.80,
            },
            {"id": "stop", "kind": "stop_file", "score": 0.20},
        ]
        selected, mode = MODULE.select_file_actions(scored, 0.65)
        self.assertEqual(["a", "c"], [item["id"] for item in selected])
        self.assertEqual("parallel_above_threshold", mode)

    def test_control_choice_stop_is_terminal_without_threshold_gate(self):
        stop = {
            "id": "stop",
            "kind": "stop_file",
            "choice": "stop",
            "stop_probability": 0.58,
        }
        reads = [
            {
                "id": "read",
                "kind": "read_range",
                "start_line": 1,
                "end_line": 100,
                "score": 0.95,
            },
        ]
        selected, mode = MODULE.select_file_actions_with_control(
            stop,
            reads,
            0.65,
        )
        self.assertEqual(["stop"], [item["id"] for item in selected])
        self.assertEqual("model_stop", mode)

    def test_unreconciled_continue_below_threshold_is_rejected(self):
        stop = {
            "id": "stop",
            "kind": "stop_file",
            "choice": "continue",
            "stop_probability": 0.61,
        }
        reads = [
            {
                "id": "a",
                "kind": "read_range",
                "start_line": 1,
                "end_line": 100,
                "score": 0.58,
            },
            {
                "id": "b",
                "kind": "read_range",
                "start_line": 201,
                "end_line": 300,
                "score": 0.40,
            },
        ]
        with self.assertRaises(RuntimeError):
            MODULE.select_file_actions_with_control(
                stop,
                reads,
                0.65,
            )

    def test_reconciled_continue_can_authorize_low_utility_read(self):
        stop = {
            "id": "stop",
            "kind": "stop_file",
            "choice": "continue",
            "stop_probability": 0.39,
            "reconciled": True,
            "reconcile_choice": "read",
            "read_authorized": True,
        }
        reads = [{
            "id": "a",
            "kind": "read_range",
            "start_line": 1,
            "end_line": 100,
            "score": 0.58,
        }]
        selected, mode = MODULE.select_file_actions_with_control(
            stop,
            reads,
            0.65,
        )
        self.assertEqual(["a"], [item["id"] for item in selected])
        self.assertEqual("reconciled_top1", mode)

    def test_exploration_view_tracks_low_utility_streak(self):
        state = {
            "parallel_threshold": 0.65,
            "action_history": [
                {
                    "epoch": 1,
                    "stop_decision": {"choice": "continue"},
                    "scores": [{"score": 0.82}],
                    "selected_ids": ["read:1"],
                    "selection_mode": "parallel_above_threshold",
                },
                {
                    "epoch": 2,
                    "stop_decision": {"choice": "continue"},
                    "scores": [{"score": 0.54}],
                    "selected_ids": ["read:2"],
                    "selection_mode": "reconciled_top1",
                },
                {
                    "epoch": 3,
                    "stop_decision": {"choice": "continue"},
                    "scores": [{"score": 0.43}],
                    "selected_ids": ["read:3"],
                    "selection_mode": "reconciled_top1",
                },
            ],
        }
        view = MODULE.exploration_view(state)
        self.assertEqual(2, view["consecutive_low_utility_epochs"])
        self.assertEqual(
            0.43,
            view["recent_epochs"][-1]["max_read_utility"],
        )

    def test_low_stop_never_terminates_when_read_exists(self):
        scored = [
            {"id": "read", "kind": "read_range", "score": 0.31},
            {"id": "stop", "kind": "stop_file", "score": 0.29},
        ]
        selected, mode = MODULE.select_file_actions(scored, 0.65)
        self.assertEqual(["read"], [item["id"] for item in selected])
        self.assertEqual("fallback_top1", mode)


if __name__ == "__main__":
    unittest.main()
