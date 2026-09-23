import importlib.util
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "claude_confidence_finalize.py"
SPEC = importlib.util.spec_from_file_location(
    "claude_confidence_finalize",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ClaudeConfidenceFinalizeTest(unittest.TestCase):
    def test_promotes_files_accidentally_nested_under_overall(self):
        assessment = {
            "schema_version": 1,
            "kind": "code-localization-confidence-assessment",
            "task": "find websocket",
            "overall": {
                "score": 0.85,
                "reason": "good",
                "files": [{
                    "path": "src/ws.py",
                    "score": 0.9,
                    "reason": "core",
                    "evidence": [],
                }],
            },
        }

        normalized = MODULE.normalize_confidence_assessment(assessment)

        self.assertEqual(1, len(normalized["files"]))
        self.assertNotIn("files", normalized["overall"])
        self.assertEqual(0.85, normalized["overall"]["score"])

    def test_keeps_valid_top_level_files_unchanged(self):
        assessment = {
            "overall": {"score": 0.8, "reason": "ok"},
            "files": [],
        }

        normalized = MODULE.normalize_confidence_assessment(assessment)

        self.assertIs(assessment, normalized)


if __name__ == "__main__":
    unittest.main()
