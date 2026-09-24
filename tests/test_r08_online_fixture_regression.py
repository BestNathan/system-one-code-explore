import json
import unittest
from pathlib import Path

from posterior_reconstruction import reconstruct
from probability_frontier_benchmark import cc_line_field, evaluate_snapshot


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "fixtures/research/r07-websocket-cc-reference.json"
SEQ = ROOT / "fixtures/research/r08-online-sequential-trajectory.json"
MULTI = ROOT / "fixtures/research/r08-online-multiscale-trajectory.json"


class R08OnlineFixtureRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(REFERENCE.read_text())
        cls.truth = cc_line_field(cls.reference)

    def metrics(self, path, estimator):
        trajectory = json.loads(path.read_text())
        posterior = reconstruct(
            estimator,
            trajectory["samples"],
            self.reference["line_count"],
            sample_lines=trajectory["sample_lines"],
        )
        return evaluate_snapshot(
            {
                "probes": len(trajectory["samples"]),
                "sampled_source_lines": 256,
                "relevance": posterior["relevance"],
                "uncertainty": posterior["uncertainty"],
                "usage": trajectory["usage"],
            },
            self.truth,
            0.70,
        )

    def test_sequential_online_fixture_is_pinned(self):
        row = self.metrics(SEQ, "sequential_exponential")
        self.assertAlmostEqual(row["mae"], 0.2519849767, places=6)
        self.assertAlmostEqual(row["pearson"], 0.4961653057, places=6)
        self.assertAlmostEqual(row["spearman"], 0.4336216424, places=6)

    def test_multiscale_online_fixture_is_pinned(self):
        row = self.metrics(MULTI, "multi_scale_gaussian")
        self.assertAlmostEqual(row["mae"], 0.1995452887, places=6)
        self.assertAlmostEqual(row["pearson"], 0.7280074366, places=6)
        self.assertAlmostEqual(row["spearman"], 0.6877041297, places=6)

    def test_multiscale_online_trajectory_beats_sequential_fixture(self):
        sequential = self.metrics(SEQ, "sequential_exponential")
        multiscale = self.metrics(MULTI, "multi_scale_gaussian")
        self.assertLess(multiscale["mae"], sequential["mae"] - 0.04)
        self.assertGreater(
            multiscale["pearson"],
            sequential["pearson"] + 0.20,
        )
        self.assertGreater(
            multiscale["spearman"],
            sequential["spearman"] + 0.20,
        )


if __name__ == "__main__":
    unittest.main()
