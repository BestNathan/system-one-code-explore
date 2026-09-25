import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from file_discovery_v1 import enumerate_files, run


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

    def test_mechanical_enumeration_has_no_directory_pruning(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            candidates = enumerate_files(root)
            paths = {item["path"] for item in candidates}

        self.assertEqual(
            paths,
            {
                "src/net/client.rs",
                "src/net/retry.rs",
                "src/db/store.rs",
                "docs/notes.md",
            },
        )
        self.assertNotIn("target/ignored.rs", paths)

    def test_multi_hit_without_top_k(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net/client.rs": 0.91,
                "src/net/retry.rs": 0.88,
                "src/db/store.rs": 0.70,
                "docs/notes.md": 0.10,
            })
            result = run(
                root,
                "connection retries",
                decider,
                file_threshold=0.65,
                transport_batch_size=64,
            )

        self.assertEqual(
            {item["path"] for item in result["relevant_files"]},
            {
                "src/net/client.rs",
                "src/net/retry.rs",
                "src/db/store.rs",
            },
        )
        self.assertFalse(
            result["policy"]["directory_semantic_pruning"]
        )
        self.assertIsNone(result["policy"]["top_k"])
        self.assertEqual(
            result["termination"],
            "all_file_metadata_scored",
        )

    def test_file_below_threshold_remains_auditable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net/client.rs": 0.90,
                "src/net/retry.rs": 0.64,
            })
            result = run(
                root,
                "connection",
                decider,
                file_threshold=0.65,
            )

        self.assertEqual(
            [item["path"] for item in result["relevant_files"]],
            ["src/net/client.rs"],
        )
        self.assertEqual(
            result["file_scores"]["src/net/retry.rs"],
            0.64,
        )

    def test_relative_recall_guard_recovers_low_absolute_score(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            decider = FakeDecider({
                "src/net/client.rs": 0.47,
                "src/net/retry.rs": 0.40,
                "src/db/store.rs": 0.30,
                "docs/notes.md": 0.10,
            })
            result = run(
                root,
                "connection",
                decider,
                file_threshold=0.65,
                relative_fallback_fraction=0.25,
            )

        self.assertEqual(
            [item["path"] for item in result["relevant_files"]],
            ["src/net/client.rs"],
        )
        self.assertEqual(
            result["relevant_files"][0]["selection_reasons"],
            ["relative_recall_guard"],
        )

    def test_transport_batches_do_not_change_semantics(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_repo(root)
            scores = {
                "src/net/client.rs": 0.90,
                "src/net/retry.rs": 0.80,
                "src/db/store.rs": 0.70,
                "docs/notes.md": 0.10,
            }
            small = FakeDecider(scores)
            large = FakeDecider(scores)
            a = run(
                root,
                "task",
                small,
                file_threshold=0.65,
                transport_batch_size=1,
            )
            b = run(
                root,
                "task",
                large,
                file_threshold=0.65,
                transport_batch_size=64,
            )

        self.assertEqual(a["relevant_files"], b["relevant_files"])
        self.assertEqual(a["file_scores"], b["file_scores"])
        self.assertGreater(small.calls, large.calls)


if __name__ == "__main__":
    unittest.main()
