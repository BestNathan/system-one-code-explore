import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "system_one_code_locator.py"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("system_one_code_locator", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DemoTest(unittest.TestCase):
    def fixture(self):
        return PROJECT_ROOT / "fixtures" / "repository"

    def test_progressive_localization_produces_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            decider = MODULE.OfflineDecider(trace)
            result = MODULE.run(
                self.fixture(),
                "Help me optimize the websocket connection implementation",
                decider,
                trace,
                directory_threshold=0.50,
                file_threshold=0.65,
                reader_file_activation_threshold=0.65,
                reader_window_lines=40,
                reader_soft_reads=2,
                reader_hard_reads=4,
                reader_action_threshold=0.40,
                observation_threshold=0.65,
            )

            self.assertIn(
                "web/src/ws",
                [item["id"] for item in result["directories"]],
            )
            self.assertIn(
                "web/src/ws/client.ts",
                [item["id"] for item in result["files"]],
            )
            self.assertTrue(any(
                item["path"] == "web/src/ws/client.ts"
                and "WebSocket" in item["content"]
                for item in result["snippets"]
            ))
            self.assertEqual(
                "two_phase_global_file_scheduler_progressive_reader",
                result["architecture"],
            )

    def test_file_frontier_uses_direct_files_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            parent = root / "src"
            child = parent / "nested"
            child.mkdir(parents=True)

            (parent / "direct.py").write_text("DIRECT = True\n", encoding="utf-8")
            (child / "nested.py").write_text("NESTED = True\n", encoding="utf-8")

            selected_parent = [{
                "id": "src",
                "payload": {"path": "src"},
                "score": 0.9,
            }]
            parent_files = MODULE.files(root, selected_parent)
            self.assertEqual(["src/direct.py"], [item["id"] for item in parent_files])

            selected_both = [
                *selected_parent,
                {
                    "id": "src/nested",
                    "payload": {"path": "src/nested"},
                    "score": 0.9,
                },
            ]
            both_files = MODULE.files(root, selected_both)
            self.assertEqual(
                ["src/direct.py", "src/nested/nested.py"],
                [item["id"] for item in both_files],
            )

    def test_source_stat_does_not_expose_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            source = root / "src"
            source.mkdir(parents=True)
            path = source / "client.ts"
            path.write_text(
                "const secretMarker = 'websocket';\nconst other = 1;\n",
                encoding="utf-8",
            )
            file = {
                "id": "src/client.ts",
                "payload": {
                    "path": "src/client.ts",
                    "filename": "client.ts",
                    "extension": ".ts",
                    "size_bytes": path.stat().st_size,
                },
                "score": 0.9,
            }

            stat = MODULE.source_stat(root, file)

            self.assertEqual(2, stat["line_count"])
            self.assertNotIn("content", stat)
            self.assertNotIn("websocket", json.dumps(stat).lower())

    def test_initial_action_space_is_stat_driven(self):
        file_state = {
            "path": "src/large.ts",
            "stat": {"line_count": 1000, "size_bytes": 10000, "extension": ".ts"},
            "coverage": [],
            "observations": [],
            "stopped": False,
        }

        actions = MODULE.generate_read_actions(file_state, 100)
        reads = [item for item in actions if item["kind"] == "read_range"]

        self.assertEqual(3, len(reads))
        self.assertEqual((1, 100), (reads[0]["start_line"], reads[0]["end_line"]))
        self.assertTrue(any(
            item["start_line"] > 400 and item["end_line"] < 700
            for item in reads
        ))
        self.assertEqual("stop_file", actions[-1]["kind"])

    def test_high_relevance_observation_changes_next_actions(self):
        file_state = {
            "path": "src/client.ts",
            "stat": {"line_count": 800, "size_bytes": 10000, "extension": ".ts"},
            "coverage": [[281, 420]],
            "observations": [{
                "id": "obs-1",
                "path": "src/client.ts",
                "start_line": 281,
                "end_line": 420,
                "content": "reconnect",
                "relevance": 0.95,
            }],
            "stopped": False,
        }

        actions = MODULE.generate_read_actions(file_state, 140)
        reads = [item for item in actions if item["kind"] == "read_range"]

        self.assertTrue(any(
            item["start_line"] == 421
            and "after" in item["reason"]
            for item in reads
        ))
        self.assertTrue(any(
            item["end_line"] == 280
            and "before" in item["reason"]
            for item in reads
        ))

    def test_multiple_relevant_regions_generate_independent_neighbor_actions(self):
        file_state = {
            "path": "src/large.ts",
            "stat": {"line_count": 3000, "size_bytes": 10000, "extension": ".ts"},
            "coverage": [
                [1, 140],
                [141, 280],
                [1500, 1639],
            ],
            "observations": [
                {
                    "id": "obs-head",
                    "path": "src/large.ts",
                    "start_line": 1,
                    "end_line": 140,
                    "content": "websocket server",
                    "relevance": 0.87,
                },
                {
                    "id": "obs-low",
                    "path": "src/large.ts",
                    "start_line": 141,
                    "end_line": 280,
                    "content": "unrelated",
                    "relevance": 0.60,
                },
                {
                    "id": "obs-second-hotspot",
                    "path": "src/large.ts",
                    "start_line": 1500,
                    "end_line": 1639,
                    "content": "heartbeat reconnect",
                    "relevance": 0.74,
                },
            ],
            "stopped": False,
        }

        regions = MODULE.relevant_regions(file_state, 0.65)
        actions = MODULE.generate_read_actions(file_state, 140, 0.65)
        reads = [item for item in actions if item["kind"] == "read_range"]

        self.assertEqual(2, len(regions))
        self.assertEqual((1, 140), (
            regions[0]["start_line"],
            regions[0]["end_line"],
        ))
        self.assertEqual((1500, 1639), (
            regions[1]["start_line"],
            regions[1]["end_line"],
        ))

        # The first hotspot's immediate continuation is already covered by the
        # low-relevance 141-280 observation. The second hotspot must still
        # receive its own before/after actions.
        self.assertTrue(any(
            item["start_line"] == 1640
            and "relevant region" in item["reason"]
            for item in reads
        ))
        self.assertTrue(any(
            item["end_line"] == 1499
            and "relevant region" in item["reason"]
            for item in reads
        ))

    def test_adjacent_high_relevance_observations_merge_into_one_region(self):
        file_state = {
            "path": "src/client.ts",
            "stat": {"line_count": 800, "size_bytes": 10000, "extension": ".ts"},
            "coverage": [[1, 280]],
            "observations": [
                {
                    "id": "obs-1",
                    "path": "src/client.ts",
                    "start_line": 1,
                    "end_line": 140,
                    "content": "connect",
                    "relevance": 0.89,
                },
                {
                    "id": "obs-2",
                    "path": "src/client.ts",
                    "start_line": 141,
                    "end_line": 280,
                    "content": "reconnect",
                    "relevance": 0.77,
                },
            ],
            "stopped": False,
        }

        regions = MODULE.relevant_regions(file_state, 0.65)

        self.assertEqual(1, len(regions))
        self.assertEqual((1, 280), (
            regions[0]["start_line"],
            regions[0]["end_line"],
        ))
        self.assertEqual(0.89, regions[0]["max_relevance"])
        self.assertEqual(2, regions[0]["observation_count"])

    def test_multiple_files_are_decided_in_one_choice_request(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            decider = MODULE.SystemOneDecider("test", trace)
            calls = []

            def fake_request(payload):
                calls.append(payload)
                answers = {}
                for question_id, question in payload["questions"].items():
                    self.assertEqual("choice", question["type"])
                    options = list(question["criteria"])
                    chosen = next(option for option in options if option != "stop")
                    answers[question_id] = {
                        "type": "choice",
                        "choice": chosen,
                        "probabilities": {
                            option: (0.8 if option == chosen else 0.2 / (len(options) - 1))
                            for option in options
                        },
                        "confidence": 0.75,
                    }
                return {
                    "model": "jev-test",
                    "answers": answers,
                    "usage": {"input_tokens": 10, "output_tokens": 10},
                }

            decider.request = fake_request
            state = {
                "goal": "locate websocket",
                "batch_index": 0,
                "round": 1,
                "files": [
                    {
                        "path": "a.ts",
                        "phase1_score": 0.9,
                        "stat": {"line_count": 400, "size_bytes": 1000, "extension": ".ts"},
                        "coverage": [],
                        "observations": [],
                        "stopped": False,
                        "stop_reason": None,
                    },
                    {
                        "path": "b.ts",
                        "phase1_score": 0.8,
                        "stat": {"line_count": 300, "size_bytes": 800, "extension": ".ts"},
                        "coverage": [],
                        "observations": [],
                        "stopped": False,
                        "stop_reason": None,
                    },
                ],
                "observations": [],
            }
            action_sets = [
                {
                    "path": item["path"],
                    "actions": MODULE.generate_read_actions(item, 100),
                }
                for item in state["files"]
            ]

            decisions, usage = decider.choose_read_actions(
                "locate websocket",
                state,
                action_sets,
            )

            self.assertEqual(1, len(calls))
            self.assertEqual(2, len(calls[0]["questions"]))
            self.assertEqual(2, len(decisions))
            self.assertEqual(1, usage["model_calls"])

    def test_observation_enters_state_before_scoring(self):
        class InspectingDecider:
            model = "inspect-test"

            def score_candidates(self, query, stage, candidates):
                return (
                    [{**item, "score": 0.99} for item in candidates],
                    MODULE.empty_usage(),
                )

            def score_reader_files(self, query, state, file_states):
                return (
                    [
                        {"path": item["path"], "score": 0.99}
                        for item in file_states
                    ],
                    MODULE.empty_usage(),
                )

            def choose_read_actions(self, query, state, action_sets):
                decisions = []
                for item in action_sets:
                    action = next(
                        action
                        for action in item["actions"]
                        if action["kind"] == "read_range"
                    )
                    decisions.append({
                        "path": item["path"],
                        "action": action,
                        "choice": "read_0",
                        "probability": 0.9,
                        "confidence": 0.9,
                        "probabilities": {"read_0": 0.9, "stop": 0.1},
                    })
                return decisions, MODULE.empty_usage()

            def score_observations(self, query, state, observation_ids):
                self_observations = {
                    item["id"]: item
                    for item in state["observations"]
                }
                for observation_id in observation_ids:
                    self.assert_in_state = observation_id in self_observations
                    self.assert_has_content = bool(
                        self_observations[observation_id]["content"]
                    )
                return (
                    {observation_id: 0.99 for observation_id in observation_ids},
                    MODULE.empty_usage(),
                )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            src = root / "src"
            src.mkdir(parents=True)
            (src / "client.py").write_text(
                "def connect():\n    return 'websocket'\n",
                encoding="utf-8",
            )
            file = {
                "id": "src/client.py",
                "payload": {
                    "path": "src/client.py",
                    "filename": "client.py",
                    "extension": ".py",
                    "size_bytes": 40,
                },
                "score": 0.99,
            }
            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            decider = InspectingDecider()

            states, snippets, metrics = MODULE.progressive_read(
                root,
                "locate websocket",
                decider,
                [file],
                trace,
                file_activation_threshold=0.65,
                window_lines=20,
                soft_reads=1,
                hard_reads=1,
                action_threshold=0.4,
                observation_threshold=0.65,
            )

            self.assertTrue(decider.assert_in_state)
            self.assertTrue(decider.assert_has_content)
            self.assertEqual(1, len(states[0]["observations"]))
            self.assertEqual(1, len(snippets))
            self.assertEqual(1, metrics["reads_executed"])

    def test_soft_round_budget_extends_while_new_high_signal_arrives(self):
        class BudgetDecider:
            model = "budget-test"

            def __init__(self):
                self.score_round = 0

            def score_reader_files(self, query, state, file_states):
                return (
                    [
                        {"path": item["path"], "score": 0.99}
                        for item in file_states
                    ],
                    MODULE.empty_usage(),
                )

            def choose_read_actions(self, query, state, action_sets):
                decisions = []
                for item in action_sets:
                    action = next(
                        action
                        for action in item["actions"]
                        if action["kind"] == "read_range"
                    )
                    decisions.append({
                        "path": item["path"],
                        "action": action,
                        "choice": "read_0",
                        "probability": 0.95,
                        "confidence": 0.95,
                        "probabilities": {"read_0": 0.95, "stop": 0.05},
                    })
                return decisions, MODULE.empty_usage()

            def score_observations(self, query, state, observation_ids):
                self.score_round += 1
                score = {
                    1: 0.90,
                    2: 0.80,
                    3: 0.20,
                }[self.score_round]
                return (
                    {observation_id: score for observation_id in observation_ids},
                    MODULE.empty_usage(),
                )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            src = root / "src"
            src.mkdir(parents=True)
            source = src / "client.py"
            source.write_text(
                "\n".join(
                    f"line_{index} = 'websocket'"
                    for index in range(1, 101)
                ) + "\n",
                encoding="utf-8",
            )
            file = {
                "id": "src/client.py",
                "payload": {
                    "path": "src/client.py",
                    "filename": "client.py",
                    "extension": ".py",
                    "size_bytes": source.stat().st_size,
                },
                "score": 0.99,
            }
            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")

            states, snippets, metrics = MODULE.progressive_read(
                root,
                "locate websocket",
                BudgetDecider(),
                [file],
                trace,
                file_activation_threshold=0.65,
                window_lines=20,
                soft_reads=2,
                hard_reads=5,
                action_threshold=0.4,
                observation_threshold=0.65,
            )

            self.assertEqual(4, states[0]["round"])
            self.assertEqual(3, metrics["reads_executed"])
            self.assertEqual(1, metrics["soft_budget_extensions"])
            self.assertEqual(0, metrics["hard_budget_hits"])
            self.assertEqual(2, len(snippets))

            events = [
                json.loads(line)["event"]
                for line in (pathlib.Path(temp) / "trace.jsonl").read_text().splitlines()
            ]
            self.assertIn("reader_file_budget_extended", events)
            self.assertIn("reader_file_soft_budget_stop", events)

    def test_hard_round_budget_caps_continuous_high_signal(self):
        class AlwaysRelevantDecider:
            model = "budget-test"

            def score_reader_files(self, query, state, file_states):
                return (
                    [
                        {"path": item["path"], "score": 0.99}
                        for item in file_states
                    ],
                    MODULE.empty_usage(),
                )

            def choose_read_actions(self, query, state, action_sets):
                decisions = []
                for item in action_sets:
                    action = next(
                        action
                        for action in item["actions"]
                        if action["kind"] == "read_range"
                    )
                    decisions.append({
                        "path": item["path"],
                        "action": action,
                        "choice": "read_0",
                        "probability": 0.95,
                        "confidence": 0.95,
                        "probabilities": {"read_0": 0.95, "stop": 0.05},
                    })
                return decisions, MODULE.empty_usage()

            def score_observations(self, query, state, observation_ids):
                return (
                    {observation_id: 0.90 for observation_id in observation_ids},
                    MODULE.empty_usage(),
                )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            src = root / "src"
            src.mkdir(parents=True)
            source = src / "client.py"
            source.write_text(
                "\n".join(
                    f"line_{index} = 'websocket'"
                    for index in range(1, 121)
                ) + "\n",
                encoding="utf-8",
            )
            file = {
                "id": "src/client.py",
                "payload": {
                    "path": "src/client.py",
                    "filename": "client.py",
                    "extension": ".py",
                    "size_bytes": source.stat().st_size,
                },
                "score": 0.99,
            }
            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")

            states, _, metrics = MODULE.progressive_read(
                root,
                "locate websocket",
                AlwaysRelevantDecider(),
                [file],
                trace,
                file_activation_threshold=0.65,
                window_lines=20,
                soft_reads=1,
                hard_reads=3,
                action_threshold=0.4,
                observation_threshold=0.65,
            )

            self.assertEqual(3, states[0]["round"])
            self.assertEqual(3, metrics["reads_executed"])
            self.assertEqual(2, metrics["soft_budget_extensions"])
            self.assertEqual(1, metrics["hard_budget_hits"])

    def test_soft_budget_extension_is_file_scoped_in_global_scheduler(self):
        class PerFileBudgetDecider:
            model = "budget-test"

            def __init__(self):
                self.round_paths = []

            def score_reader_files(self, query, state, file_states):
                return (
                    [
                        {"path": item["path"], "score": 0.99}
                        for item in file_states
                    ],
                    MODULE.empty_usage(),
                )

            def choose_read_actions(self, query, state, action_sets):
                self.round_paths.append([
                    item["path"] for item in action_sets
                ])
                decisions = []
                for item in action_sets:
                    action = next(
                        action
                        for action in item["actions"]
                        if action["kind"] == "read_range"
                    )
                    decisions.append({
                        "path": item["path"],
                        "action": action,
                        "choice": "read_0",
                        "probability": 0.95,
                        "confidence": 0.95,
                        "probabilities": {"read_0": 0.95, "stop": 0.05},
                    })
                return decisions, MODULE.empty_usage()

            def score_observations(self, query, state, observation_ids):
                by_id = {
                    item["id"]: item
                    for item in state["observations"]
                }
                scores = {}
                for observation_id in observation_ids:
                    path = by_id[observation_id]["path"]
                    round_number = state["round"]
                    if path.endswith("hot.py") and round_number == 1:
                        scores[observation_id] = 0.90
                    else:
                        scores[observation_id] = 0.20
                return scores, MODULE.empty_usage()

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            src = root / "src"
            src.mkdir(parents=True)

            files = []
            for name in ("hot.py", "cold.py"):
                source = src / name
                source.write_text(
                    "\n".join(
                        f"line_{index} = 'websocket'"
                        for index in range(1, 81)
                    ) + "\n",
                    encoding="utf-8",
                )
                files.append({
                    "id": f"src/{name}",
                    "payload": {
                        "path": f"src/{name}",
                        "filename": name,
                        "extension": ".py",
                        "size_bytes": source.stat().st_size,
                    },
                    "score": 0.99,
                })

            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            decider = PerFileBudgetDecider()

            states, _, metrics = MODULE.progressive_read(
                root,
                "locate websocket",
                decider,
                files,
                trace,
                file_activation_threshold=0.65,
                window_lines=20,
                soft_reads=1,
                hard_reads=3,
                action_threshold=0.4,
                observation_threshold=0.65,
            )

            self.assertEqual(
                [["src/hot.py", "src/cold.py"], ["src/hot.py"]],
                decider.round_paths,
            )
            by_path = {
                item["path"]: item
                for item in states[0]["files"]
            }
            self.assertEqual(
                "soft_budget_no_high_signal",
                by_path["src/cold.py"]["stop_reason"],
            )
            self.assertEqual(1, metrics["soft_budget_extensions"])
            self.assertEqual(2, metrics["files_stopped_by_soft_budget"])
            self.assertEqual(3, metrics["reads_executed"])

    def test_phase1_keeps_all_threshold_files_in_reader_state(self):
        class Phase1Decider:
            model = "phase1-test"

            def score_candidates(self, query, stage, candidates):
                scored = []
                for index, item in enumerate(candidates):
                    scored.append({
                        **item,
                        "score": 0.99 - (index * 0.01),
                    })
                scored.sort(key=lambda item: (-item["score"], item["id"]))
                return scored, MODULE.empty_usage()

            def score_reader_files(self, query, state, file_states):
                return (
                    [
                        {"path": item["path"], "score": 0.99}
                        for item in file_states
                    ],
                    MODULE.empty_usage(),
                )

            def choose_read_actions(self, query, state, action_sets):
                return (
                    [{
                        "path": item["path"],
                        "action": next(
                            action for action in item["actions"]
                            if action["kind"] == "stop_file"
                        ),
                        "choice": "stop",
                        "probability": 0.99,
                        "confidence": 0.99,
                        "probabilities": {"stop": 0.99},
                    } for item in action_sets],
                    MODULE.empty_usage(),
                )

            def score_observations(self, query, state, observation_ids):
                return {}, MODULE.empty_usage()

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            src = root / "src"
            src.mkdir(parents=True)
            for index in range(10):
                (src / f"file_{index}.py").write_text(
                    "value = 1\n",
                    encoding="utf-8",
                )

            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            result = MODULE.run(
                root,
                "find implementation",
                Phase1Decider(),
                trace,
                directory_threshold=0.5,
                file_threshold=0.65,
                reader_file_activation_threshold=0.65,
                reader_window_lines=20,
                reader_soft_reads=1,
                reader_hard_reads=1,
                reader_action_threshold=0.4,
                observation_threshold=0.65,
            )

            self.assertEqual(10, len(result["files"]))
            self.assertEqual(10, len(result["reader_states"][0]["files"]))
            self.assertEqual(
                10,
                result["metrics"]["reader_file_activations"],
            )

    def test_global_scheduler_can_defer_then_activate_a_file(self):
        class GlobalSchedulerDecider:
            model = "scheduler-test"

            def __init__(self):
                self.priority_round = 0
                self.action_round_paths = []

            def score_reader_files(self, query, state, file_states):
                self.priority_round += 1
                scores = []
                for item in file_states:
                    if self.priority_round == 1:
                        score = 0.95 if item["path"].endswith("first.py") else 0.20
                    else:
                        score = 0.95 if item["path"].endswith("second.py") else 0.20
                    scores.append({"path": item["path"], "score": score})
                return scores, MODULE.empty_usage()

            def choose_read_actions(self, query, state, action_sets):
                self.action_round_paths.append([
                    item["path"] for item in action_sets
                ])
                decisions = []
                for item in action_sets:
                    action = next(
                        action for action in item["actions"]
                        if action["kind"] == "read_range"
                    )
                    decisions.append({
                        "path": item["path"],
                        "action": action,
                        "choice": "read_0",
                        "probability": 0.95,
                        "confidence": 0.95,
                        "probabilities": {"read_0": 0.95, "stop": 0.05},
                    })
                return decisions, MODULE.empty_usage()

            def score_observations(self, query, state, observation_ids):
                return (
                    {observation_id: 0.20 for observation_id in observation_ids},
                    MODULE.empty_usage(),
                )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "repo"
            src = root / "src"
            src.mkdir(parents=True)
            files = []
            for name in ("first.py", "second.py"):
                source = src / name
                source.write_text(
                    "\n".join(f"line_{i} = 1" for i in range(1, 41)) + "\n",
                    encoding="utf-8",
                )
                files.append({
                    "id": f"src/{name}",
                    "payload": {
                        "path": f"src/{name}",
                        "filename": name,
                        "extension": ".py",
                        "size_bytes": source.stat().st_size,
                    },
                    "score": 0.9,
                })

            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            decider = GlobalSchedulerDecider()
            states, _, metrics = MODULE.progressive_read(
                root,
                "find implementation",
                decider,
                files,
                trace,
                file_activation_threshold=0.65,
                window_lines=20,
                soft_reads=1,
                hard_reads=1,
                action_threshold=0.4,
                observation_threshold=0.65,
            )

            self.assertEqual(
                [["src/first.py"], ["src/second.py"]],
                decider.action_round_paths,
            )
            self.assertEqual(2, metrics["unique_files_read"])
            self.assertEqual(2, len(states[0]["files"]))

    def test_transient_520_is_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = MODULE.Trace(pathlib.Path(temp) / "trace.jsonl")
            decider = MODULE.SystemOneDecider("test", trace)
            calls = {"count": 0}
            original_urlopen = MODULE.urllib.request.urlopen
            original_sleep = MODULE.time.sleep

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self):
                    return b'{"answers":{},"usage":{}}'

            def fake_urlopen(*args, **kwargs):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise MODULE.urllib.error.HTTPError(
                        "https://api.typesafe.ai/v1/systemone",
                        520,
                        "origin error",
                        hdrs=None,
                        fp=None,
                    )
                return Response()

            try:
                MODULE.urllib.request.urlopen = fake_urlopen
                MODULE.time.sleep = lambda _: None
                decider.request({"model": "jev-latest", "questions": {}})
            finally:
                MODULE.urllib.request.urlopen = original_urlopen
                MODULE.time.sleep = original_sleep

            self.assertEqual(2, calls["count"])


if __name__ == "__main__":
    unittest.main()
