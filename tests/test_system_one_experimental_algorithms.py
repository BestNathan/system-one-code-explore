import importlib.util
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))


def load(name):
    path = SRC / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


A = load("system_one_evidence_guided_runtime")
B = load("system_one_adaptive_zoom")


class EvidenceGuidedTest(unittest.TestCase):
    def test_prompt_targets_new_material_evidence_not_topical_relevance(self):
        decider = object.__new__(A.EvidenceGuidedDecider)
        captured = {}

        def send(stage, state, questions):
            captured["stage"] = stage
            captured["state"] = state
            captured["questions"] = questions
            return {
                "answers": {
                    "control": {
                        "type": "choice",
                        "choice": "continue",
                        "probabilities": {
                            "stop": 0.2,
                            "continue": 0.8,
                        },
                        "confidence": 0.8,
                    },
                    "read_0": {
                        "type": "noul",
                        "noul": 0.77,
                    },
                }
            }, {
                "model_calls": 1,
                "input_tokens": 10,
                "output_tokens": 2,
            }

        decider.send = send
        state = {
            "path": "src/x.py",
            "phase1_score": 0.8,
            "line_count": 100,
            "coverage": [],
            "read_count": 0,
            "epoch": 1,
            "observations": [],
        }
        actions = [
            {
                "id": "read",
                "kind": "read_range",
                "path": "src/x.py",
                "start_line": 1,
                "end_line": 50,
                "navigation": "seed_head",
                "reason": "probe",
                "source": None,
            },
            {
                "id": "stop",
                "kind": "stop_file",
                "path": "src/x.py",
            },
        ]

        stop, reads, _ = decider.decide_file_actions(
            "optimize websocket",
            state,
            actions,
        )

        self.assertEqual("continue", stop["choice"])
        self.assertEqual(0.77, reads[0]["score"])
        prompt = captured["questions"]["read_0"]["instructions"]["question"]
        self.assertIn("NEW MATERIAL EVIDENCE", prompt)
        self.assertIn("redundant", prompt)
        control = captured["questions"]["control"]["instructions"]["question"]
        self.assertIn("minimal", control)
        self.assertIn("evidence gap", control)


class AdaptiveZoomGeometryTest(unittest.TestCase):
    def test_partition_covers_file_without_overlap(self):
        regions = B.initial_regions(1000, 16)
        self.assertEqual(16, len(regions))
        self.assertEqual(1, regions[0]["start_line"])
        self.assertEqual(1000, regions[-1]["end_line"])
        for left, right in zip(regions, regions[1:]):
            self.assertEqual(
                left["end_line"] + 1,
                right["start_line"],
            )

    def test_beam_preserves_multiple_hotspots_and_exploration(self):
        frontier = [
            B.new_region(f"r{i}", 1 + i * 100, (i + 1) * 100, 0)
            for i in range(5)
        ]
        probabilities = {
            "r0": 0.42,
            "r1": 0.31,
            "r2": 0.15,
            "r3": 0.08,
            "r4": 0.04,
        }

        exploit, exploration, mass = B.choose_beam(
            frontier,
            probabilities,
            beam_width=3,
            beam_mass=0.80,
            exploration_slots=1,
        )

        self.assertEqual(["r0", "r1", "r2"], [x["id"] for x in exploit])
        self.assertGreaterEqual(mass, 0.80)
        self.assertEqual(1, len(exploration))
        self.assertNotIn(
            exploration[0]["id"],
            {x["id"] for x in exploit},
        )

    def test_refinement_is_range_only_and_binary(self):
        parent = B.new_region("r1", 1, 1000, 0)
        children = B.split_region(parent)
        self.assertEqual(2, len(children))
        self.assertEqual((1, 500), (
            children[0]["start_line"],
            children[0]["end_line"],
        ))
        self.assertEqual((501, 1000), (
            children[1]["start_line"],
            children[1]["end_line"],
        ))
        self.assertEqual("r1", children[0]["root_id"])
        self.assertEqual(1, children[0]["depth"])

    def test_offline_zoom_runs_without_semantic_parser(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path = root / "notes.md"
            path.write_text(
                "\n".join(f"line {i}" for i in range(1, 401)) + "\n",
                encoding="utf-8",
            )
            candidate = {
                "score": 0.9,
                "payload": {
                    "path": "notes.md",
                    "extension": ".md",
                },
            }
            trace = type(
                "Trace",
                (),
                {"emit": lambda self, *args, **kwargs: None},
            )()
            decider = B.OfflineAdaptiveZoomDecider(trace)

            state, _ = B.run_zoom_file(
                root,
                "find useful content",
                candidate,
                decider,
                trace,
                coarse_regions=8,
                probe_lines=16,
                beam_width=3,
                beam_mass=0.8,
                exploration_slots=1,
                target_region_lines=25,
                exploration_floor=0.05,
                max_rounds=4,
                stable_rounds=2,
            )

            self.assertGreater(len(state["observations"]), 0)
            self.assertIn(
                state["termination"],
                {
                    "probability_frontier_converged",
                    "round_budget_exhausted",
                    "frontier_exhausted",
                },
            )


if __name__ == "__main__":
    unittest.main()
