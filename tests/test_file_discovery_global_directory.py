import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from file_discovery_global_directory import enumerate_directories, enumerate_direct_files, two_stage_discovery


class FakeScorer:
    def __init__(self):
        self.directory_population = []
        self.calls = []

    def score(self, stage, candidates):
        self.calls.append(stage)
        if stage == "directory":
            self.directory_population = [candidate["path"] for candidate in candidates]
            return [{**item, "score": 0.9 if item["path"] == "pkg/sub" else 0.1}
                    for item in candidates]
        return [{**item, "score": 0.9} for item in candidates]


class GlobalDirectoryTests(unittest.TestCase):
    def test_nested_directory_is_visible_even_when_parent_scores_low(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg" / "sub").mkdir(parents=True)
            (root / "pkg" / "parent.py").write_text("x", encoding="utf-8")
            (root / "pkg" / "sub" / "target.py").write_text("x", encoding="utf-8")
            (root / "pkg" / "sub" / "child").mkdir()
            (root / "pkg" / "sub" / "child" / "hidden.py").write_text("x", encoding="utf-8")

            scorer = FakeScorer()
            result = two_stage_discovery(root, "find target", scorer)

        self.assertIn("pkg", scorer.directory_population)
        self.assertIn("pkg/sub", scorer.directory_population)
        self.assertEqual(["directory", "file"], scorer.calls)
        self.assertEqual(["pkg/sub"], result["selected_directories"])
        self.assertEqual(["pkg/sub/target.py"], list(result["file_scores"]))
        self.assertNotIn("pkg/sub/child/hidden.py", result["file_scores"])

    def test_direct_file_enumeration_deduplicates_selected_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "module").mkdir()
            (root / "module" / "a.py").write_text("x", encoding="utf-8")
            files = enumerate_direct_files(root, ["module", "module"])
            dirs = enumerate_directories(root)
        self.assertEqual(["module/a.py"], [item["path"] for item in files])
        self.assertEqual({".", "module"}, {item["path"] for item in dirs})


if __name__ == "__main__":
    unittest.main()
