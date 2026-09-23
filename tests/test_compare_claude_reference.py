import importlib.util
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "compare_claude_reference.py"
SPEC = importlib.util.spec_from_file_location("compare_claude_reference", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CompareClaudeReferenceTest(unittest.TestCase):
    def test_file_and_range_metrics(self):
        system_one = {
            "query": "same question",
            "files": [
                {"id": "src/a.py"},
                {"id": "src/b.py"},
                {"id": "src/noise.py"},
            ],
            "snippets": [
                {
                    "path": "src/a.py",
                    "start_line": 90,
                    "end_line": 130,
                    "score": 0.9,
                },
                {
                    "path": "src/noise.py",
                    "start_line": 1,
                    "end_line": 20,
                    "score": 0.7,
                },
            ],
        }
        claude = {
            "relevant_files": [
                {
                    "path": "src/a.py",
                    "relevance": "primary",
                    "reason": "implementation",
                    "evidence": [{
                        "start_line": 100,
                        "end_line": 120,
                        "description": "core implementation",
                    }],
                },
                {
                    "path": "src/b.py",
                    "relevance": "supporting",
                    "reason": "dependency",
                    "evidence": [{
                        "start_line": 40,
                        "end_line": 60,
                        "description": "helper",
                    }],
                },
            ],
        }

        report = MODULE.compare(system_one, claude)

        self.assertEqual(1.0, report["metrics"]["phase1_reference_recall"])
        self.assertEqual(0.5, report["metrics"]["evidence_reference_recall"])
        self.assertEqual(1.0, report["metrics"]["primary_phase1_recall"])
        self.assertEqual(1.0, report["metrics"]["primary_evidence_recall"])
        self.assertEqual(0.5, report["metrics"]["evidence_reference_precision_proxy"])
        self.assertEqual(1.0, report["metrics"]["shared_file_range_overlap_rate"])
        self.assertEqual(0.5, report["metrics"]["reference_evidence_region_recall"])
        self.assertEqual(1.0, report["metrics"]["primary_evidence_region_recall"])
        self.assertEqual(0.5, report["metrics"]["reference_evidence_line_coverage"])
        self.assertEqual(
            ["src/b.py"],
            report["agreement"]["claude_missed_by_evidence"],
        )
        self.assertEqual(
            ["src/noise.py"],
            report["agreement"]["system_one_evidence_not_in_claude_reference"],
        )

    def test_missing_reference_ranges_are_not_counted_as_failures(self):
        system_one = {
            "files": [{"id": "src/a.py"}],
            "snippets": [{
                "path": "src/a.py",
                "start_line": 1,
                "end_line": 10,
                "score": 0.8,
            }],
        }
        claude = {
            "relevant_files": [{
                "path": "src/a.py",
                "relevance": "primary",
                "reason": "implementation",
                "evidence": [],
            }],
        }

        report = MODULE.compare(system_one, claude)

        self.assertIsNone(
            report["metrics"]["shared_file_range_overlap_rate"]
        )


if __name__ == "__main__":
    unittest.main()
