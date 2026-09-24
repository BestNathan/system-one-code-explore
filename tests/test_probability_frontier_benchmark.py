import unittest

from probability_frontier_benchmark import (
    evaluate_snapshot,
    js_divergence,
    pearson,
    spearman,
    wasserstein_position,
)


class ProbabilityFrontierBenchmarkTests(unittest.TestCase):
    def test_identical_fields_have_zero_distance_and_unit_correlation(self):
        values = [0.1, 0.2, 0.8, 0.9]
        self.assertAlmostEqual(pearson(values, values), 1.0)
        self.assertAlmostEqual(spearman(values, values), 1.0)
        self.assertAlmostEqual(js_divergence(values, values), 0.0)
        self.assertAlmostEqual(wasserstein_position(values, values), 0.0)

    def test_snapshot_metrics_reward_matching_distribution(self):
        truth = [0.1, 0.2, 0.8, 0.9]
        snapshot = {
            "probes": 4,
            "sampled_source_lines": 32,
            "relevance": [0.1, 0.2, 0.8, 0.9],
            "uncertainty": [0.2, 0.2, 0.1, 0.1],
            "usage": {"model_calls": 2, "input_tokens": 100, "output_tokens": 20},
        }
        metrics = evaluate_snapshot(snapshot, truth, 0.7)
        self.assertAlmostEqual(metrics["mae"], 0.0)
        self.assertAlmostEqual(metrics["rmse"], 0.0)
        self.assertAlmostEqual(metrics["pearson"], 1.0)
        self.assertAlmostEqual(metrics["spearman"], 1.0)
        self.assertAlmostEqual(metrics["top_k_recall"], 1.0)
        self.assertAlmostEqual(metrics["high_relevance_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
