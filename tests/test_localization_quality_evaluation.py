import importlib.util
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "localization_quality_evaluation.py"
SPEC = importlib.util.spec_from_file_location(
    "localization_quality_evaluation",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class QualityEvaluationTest(unittest.TestCase):
    def test_anonymize_removes_identity_cost_and_confidence(self):
        result = {
            "task": "find websocket",
            "producer": {"system": "system_one"},
            "cost": {"elapsed_ms": 1},
            "files": [{
                "path": "src/ws.py",
                "role": "relevant",
                "reason": "core",
                "confidence": {"score": 0.9},
                "evidence": [{
                    "start_line": 1,
                    "end_line": 20,
                    "reason": "handler",
                    "content": "source",
                    "confidence": {"score": 0.8},
                }],
            }],
        }
        candidate = MODULE.anonymize(result, "candidate-a")
        self.assertNotIn("producer", candidate)
        self.assertNotIn("cost", candidate)
        self.assertNotIn("confidence", candidate["files"][0])
        self.assertNotIn(
            "confidence",
            candidate["files"][0]["evidence"][0],
        )
        self.assertEqual("candidate-a", candidate["candidate_id"])

    def test_weighted_score_uses_fixed_rubric(self):
        dimensions = {
            name: {"score": 10.0, "reason": "ok"}
            for name in MODULE.DIMENSIONS
        }
        self.assertEqual(100.0, MODULE.weighted_score(dimensions))
        dimensions["completeness"]["score"] = 0.0
        self.assertEqual(75.0, MODULE.weighted_score(dimensions))

    def test_parse_assessment_tolerates_prose_and_json_fence(self):
        dimensions = {
            name: {"score": 8.0, "reason": "grounded"}
            for name in MODULE.DIMENSIONS
        }
        payload = {
            "schema_version": 1,
            "kind": "code-localization-quality-evaluation",
            "candidate_id": "candidate-a",
            "task": "find websocket",
            "dimensions": dimensions,
            "strengths": [],
            "important_omissions": [],
            "redundancies": [],
            "downstream_assessment": {
                "can_proceed": True,
                "reason": "enough evidence",
                "recommended_next_step": "continue",
            },
            "summary": "usable",
        }
        import json
        raw = (
            "Evaluation complete.\n\n```json\n"
            + json.dumps(payload)
            + "\n```\n"
        )

        parsed = MODULE.parse_assessment_text(raw)

        self.assertEqual(
            "code-localization-quality-evaluation",
            parsed["kind"],
        )
        self.assertEqual("candidate-a", parsed["candidate_id"])

    def test_parse_assessment_failure_reports_preview(self):
        with self.assertRaisesRegex(
            ValueError,
            "did not contain a valid quality-evaluation JSON object",
        ):
            MODULE.parse_assessment_text(
                "The evaluator completed but emitted no JSON object."
            )

    def test_validation_rejects_missing_dimension(self):
        candidate = {"candidate_id": "candidate-a"}
        assessment = {
            "kind": "code-localization-quality-evaluation",
            "candidate_id": "candidate-a",
            "dimensions": {
                name: {"score": 8.0, "reason": "ok"}
                for name in list(MODULE.DIMENSIONS)[:-1]
            },
            "downstream_assessment": {"can_proceed": True},
        }
        with self.assertRaises(ValueError):
            MODULE.validate_assessment(candidate, assessment)


if __name__ == "__main__":
    unittest.main()
