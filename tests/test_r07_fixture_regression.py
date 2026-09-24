import json
import unittest
from pathlib import Path

from posterior_reconstruction import reconstruct
from probability_frontier_benchmark import cc_line_field, evaluate_snapshot


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "fixtures/research/r07-websocket-v5b-trajectory.json"
REFERENCE = ROOT / "fixtures/research/r07-websocket-cc-reference.json"


class R07FixtureRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trajectory = json.loads(TRAJECTORY.read_text())
        cls.reference = json.loads(REFERENCE.read_text())
        cls.truth = cc_line_field(cls.reference)

    def metrics(self, estimator):
        posterior = reconstruct(
            estimator,
            self.trajectory["samples"],
            self.reference["line_count"],
            sample_lines=self.trajectory["sample_lines"],
        )
        return evaluate_snapshot(
            {
                "probes": len(self.trajectory["samples"]),
                "sampled_source_lines": 256,
                "relevance": posterior["relevance"],
                "uncertainty": posterior["uncertainty"],
                "usage": {},
            },
            self.truth,
            0.70,
        )

    def test_sequential_fixture_reproduces_v5_baseline(self):
        row = self.metrics("sequential_exponential")
        self.assertAlmostEqual(row["mae"], 0.2298120238, places=6)
        self.assertAlmostEqual(row["pearson"], 0.5402906773, places=6)
        self.assertAlmostEqual(row["spearman"], 0.4781654501, places=6)

    def test_multiscale_recovers_more_global_signal(self):
        baseline = self.metrics("sequential_exponential")
        candidate = self.metrics("multi_scale_gaussian")
        self.assertLess(candidate["mae"], baseline["mae"])
        self.assertGreater(candidate["pearson"], baseline["pearson"] + 0.20)
        self.assertGreater(candidate["spearman"], baseline["spearman"] + 0.20)


if __name__ == "__main__":
    unittest.main()
