import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from file_discovery_v1 import disclose_children, run


class FakeDecider:
    def __init__(self, scores):
        self.scores = scores
        self.calls = 0

    def score_candidates(self, query, stage, candidates):
        self.calls += 1
        out = []
        for candidate in candidates:
            path = candidate["payload"]["path"]
            out.append({
                **candidate,
                "score": float(self.scores.get(path, 0.0)),
            })
        return out, {
            "model_calls": 1,
            "input_tokens": 10 * len(candidates),
            "output_tokens": len(candidates),
        }


class FileDiscoveryV1Tests(unittest.TestCase):
    def make_repo(self, root):
        (root / "src" / "net").mkdir(parents=True)
        (root / "src" / "db").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "target").mkdir()
        (root / "src" / "net" / "client.rs").write_text(
            "fn connect() {}\n",
            encoding="utf-8",
        )
        (root / "src" / "net" / "retry.rs").write_text(
            "fn retry() {}\n",
            encoding="utf-8",
        )
        (root / "src" / "db" / "store.rs").write_text(
            "fn store() {}\n",
            encoding="utf-8",
        )
        (root / "docs" / "notes.md").write_text(
            "notes\n",
            encoding="utf-8",
        )
        (root / "target" / "ignored.rs").write_text(
            "ignored\n",
            encoding="utf-8",
        )

    def test_direct_children_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            children = disclose_children(root, "")
            paths = {item["path"] for item in children}
            self.assertIn("src", paths)
            self.assertIn("docs", paths)
            self.assertNotIn("src/net/client.rs", paths)
            self.assertNotIn("target", paths)

    def test_hierarchical_multi_hit_without_top_k(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net": 0.92,
                "src/db": 0.80,
                "src/net/client.rs": 0.91,
                "src/net/retry.rs": 0.88,
                "src/db/store.rs": 0.70,
            })
            result = run(
                root,
                "connection retries",
                decider,
                directory_threshold=0.50,
                file_threshold=0.65,
                transport_batch_size=64,
            )

        paths = {
            item["path"]
            for item in result["relevant_files"]
        }
        self.assertEqual(
            paths,
            {
                "src/net/client.rs",
                "src/net/retry.rs",
                "src/db/store.rs",
            },
        )
        self.assertEqual(
            result["directory_status"]["docs"],
            "pruned",
        )
        self.assertEqual(
            result["termination"],
            "frontier_exhausted",
        )
        self.assertIsNone(result["policy"]["top_k"])

    def test_top_level_directory_is_mechanically_expanded(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net": 0.90,
                "src/db": 0.10,
                "src/net/client.rs": 0.90,
                "src/net/retry.rs": 0.10,
            })
            result = run(
                root,
                "connection",
                decider,
                directory_threshold=0.50,
                file_threshold=0.65,
            )

        self.assertEqual(
            result["directory_status"]["src"],
            "mechanical_expand",
        )
        self.assertIn(
            "src/net/client.rs",
            {item["path"] for item in result["relevant_files"]},
        )

    def test_pruned_ancestor_hides_descendants(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net": 0.40,
                "src/db": 0.10,
                "src/net/client.rs": 0.99,
            })
            result = run(
                root,
                "connection",
                decider,
                directory_threshold=0.50,
                file_threshold=0.65,
            )

        self.assertEqual(result["relevant_files"], [])
        self.assertEqual(
            result["directory_status"]["src"],
            "mechanical_expand",
        )
        self.assertEqual(
            result["directory_status"]["src/net"],
            "pruned",
        )
        self.assertNotIn(
            "file:src/net/client.rs",
            result["node_scores"],
        )

    def test_file_threshold_does_not_limit_other_hits(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net": 0.90,
                "src/db": 0.10,
                "src/net/client.rs": 0.90,
                "src/net/retry.rs": 0.64,
            })
            result = run(
                root,
                "connection",
                decider,
                directory_threshold=0.50,
                file_threshold=0.65,
            )

        self.assertEqual(
            [item["path"] for item in result["relevant_files"]],
            ["src/net/client.rs"],
        )
        self.assertEqual(
            result["node_scores"]["file:src/net/retry.rs"]["score"],
            0.64,
        )


if __name__ == "__main__":
    unittest.main()
