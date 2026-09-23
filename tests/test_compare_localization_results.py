import importlib.util
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "compare_localization_results.py"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
SPEC = importlib.util.spec_from_file_location(
    "compare_localization_results",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def result(system, files):
    return {
        "schema_version": 1,
        "kind": "code-localization-result",
        "task": "same task",
        "subject": {
            "repository": "BestNathan/nession",
            "revision": "abc123",
        },
        "producer": {
            "system": system,
            "model": system,
        },
        "summary": "",
        "confidence": None,
        "cost": {
            "elapsed_ms": 1000 if system == "system_one" else 2000,
            "api_elapsed_ms": None,
            "elapsed_semantics": "test",
            "model_calls": 4 if system == "system_one" else None,
            "turns": None if system == "system_one" else 10,
            "tool_calls": 0 if system == "system_one" else 6,
            "tokens": {
                "input": 100 if system == "system_one" else 200,
                "output": 20 if system == "system_one" else 40,
                "cache_read_input": 0,
                "cache_creation_input": 0,
                "thinking": 0,
            },
            "provider_cost_usd": None if system == "system_one" else 0.5,
            "stages": [],
        },
        "files": files,
    }


class CompareLocalizationResultsTest(unittest.TestCase):
    def test_symmetric_file_and_region_comparison(self):
        left = result("system_one", [{
            "path": "src/a.py",
            "role": "relevant",
            "confidence": {
                "score": 0.9,
                "label": "high",
                "type": "noul_relevance",
            },
            "reason": "evidence",
            "evidence": [{
                "start_line": 10,
                "end_line": 30,
                "confidence": {
                    "score": 0.9,
                    "label": "high",
                    "type": "noul_relevance",
                },
                "reason": "range",
                "content": "",
            }],
        }, {
            "path": "src/left.py",
            "role": "relevant",
            "confidence": None,
            "reason": "",
            "evidence": [{
                "start_line": 1,
                "end_line": 10,
                "confidence": None,
                "reason": "",
                "content": "",
            }],
        }])
        right = result("claude_code", [{
            "path": "src/a.py",
            "role": "primary",
            "confidence": {
                "score": 0.8,
                "label": "high",
                "type": "model_self_assessment",
            },
            "reason": "implementation",
            "evidence": [{
                "start_line": 20,
                "end_line": 40,
                "confidence": {
                    "score": 0.8,
                    "label": "high",
                    "type": "model_self_assessment",
                },
                "reason": "range",
                "content": "",
            }],
        }, {
            "path": "src/right.py",
            "role": "supporting",
            "confidence": None,
            "reason": "",
            "evidence": [{
                "start_line": 1,
                "end_line": 5,
                "confidence": None,
                "reason": "",
                "content": "",
            }],
        }])

        report = MODULE.compare(left, right)

        self.assertEqual(["src/a.py"], report["files"]["shared"])
        self.assertEqual(["src/left.py"], report["files"]["left_only"])
        self.assertEqual(["src/right.py"], report["files"]["right_only"])
        self.assertEqual(1 / 3, report["files"]["jaccard"])
        self.assertEqual(
            0.5,
            report["evidence"]["left_covered_by_right"]["region_overlap_rate"],
        )
        self.assertEqual(
            0.5,
            report["evidence"]["right_covered_by_left"]["region_overlap_rate"],
        )
        self.assertEqual(1000, report["left"]["cost"]["elapsed_ms"])
        self.assertEqual(2000, report["right"]["cost"]["elapsed_ms"])
        self.assertEqual(100, report["left"]["cost"]["input_tokens"])
        self.assertEqual(0.5, report["right"]["cost"]["provider_cost_usd"])

        pair = report["files"]["confidence_pairs"][0]
        self.assertEqual(0.9, pair["left_score"])
        self.assertEqual(0.8, pair["right_score"])
        self.assertEqual(
            {"repository": "BestNathan/nession", "revision": "abc123"},
            report["subject"],
        )

    def test_rejects_different_subject_revisions(self):
        left = result("system_one", [])
        right = result("claude_code", [])
        right["subject"]["revision"] = "different"

        with self.assertRaisesRegex(ValueError, "different subjects"):
            MODULE.compare(left, right)

    def test_rejects_missing_subject_identity(self):
        left = result("system_one", [])
        right = result("claude_code", [])
        del right["subject"]

        with self.assertRaisesRegex(ValueError, "missing canonical subject"):
            MODULE.compare(left, right)


if __name__ == "__main__":
    unittest.main()
