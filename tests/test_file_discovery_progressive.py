import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from file_discovery_progressive import progressive


class FakeScorer:
    def score(self, stage, candidates):
        result = []
        for candidate in candidates:
            if stage == "route":
                value = 0.9 if candidate["path"] == "open" else 0.1
                result.append({**candidate, "score": value, "uncertainty": value})
            else:
                result.append({**candidate, "score": 0.9})
        return result


class ProgressiveStateMachineTests(unittest.TestCase):
    def test_low_scoring_parent_remains_deferred_and_is_not_pruned(self):
        snapshots = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "closed").mkdir()
            (root / "closed" / "target.py").write_text("metadata only", encoding="utf-8")
            (root / "open").mkdir()
            (root / "open" / "near.py").write_text("metadata only", encoding="utf-8")

            result = progressive(root, "find the target", FakeScorer(), checkpoint=snapshots.append)

        self.assertFalse(result["policy"]["ancestor_pruning"])
        self.assertEqual(["closed"], [node["path"] for node in result["deferred_unresolved"]])
        self.assertEqual("closed", result["deferred_unresolved"][0]["path"])
        self.assertNotIn("closed/target.py", result["file_scores"])
        self.assertIn("open/near.py", result["file_scores"])
        self.assertIn("unresolved", result["completion"])
        self.assertEqual("closed", snapshots[-1]["deferred_unresolved"][0]["path"])
        self.assertEqual("scheduler_exhausted", snapshots[-1]["status"])

    def test_empty_repository_has_no_model_visible_nodes(self):
        with tempfile.TemporaryDirectory() as temp:
            result = progressive(Path(temp), "find anything", FakeScorer())
        self.assertEqual(0, result["directory_decisions"])
        self.assertEqual(0, result["file_decisions"])
        self.assertIsNone(result["policy"]["hard_candidate_cap"])


if __name__ == "__main__":
    unittest.main()
