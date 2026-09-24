import unittest

from search_effect_benchmark import evaluate


class SearchEffectBenchmarkTests(unittest.TestCase):
    def test_search_metrics_follow_actual_probe_order(self):
        reference = {
            "line_count": 100,
            "ranges": [
                {
                    "start_line": 1,
                    "end_line": 20,
                    "relevance": 0.1,
                    "role": "irrelevant",
                },
                {
                    "start_line": 41,
                    "end_line": 60,
                    "relevance": 0.9,
                    "role": "core",
                },
                {
                    "start_line": 81,
                    "end_line": 100,
                    "relevance": 0.8,
                    "role": "supporting",
                },
            ],
        }
        run = {
            "posterior_estimator": "demo",
            "sample_lines": 10,
            "history": [
                {
                    "epoch": 0,
                    "actions": [
                        {"start_line": 1, "end_line": 10, "kind": "random"},
                        {"start_line": 45, "end_line": 54, "kind": "uncertainty"},
                    ],
                },
                {
                    "epoch": 1,
                    "policy": {
                        "selected_actions": [
                            {"start_line": 85, "end_line": 94, "kind": "peak"}
                        ]
                    },
                },
            ],
        }

        result = evaluate(reference, run, high_threshold=0.70)
        self.assertEqual(result["search"]["first_high_hit_probe"], 2)
        self.assertEqual(result["search"]["first_core_hit_probe"], 2)
        self.assertEqual(result["run"]["probes"], 3)
        self.assertGreater(result["final"]["high_line_recall"], 0.0)
        self.assertGreater(
            result["search"]["weighted_recall_auc_per_probe"], 0.0
        )

    def test_compact_trajectory_samples_are_supported(self):
        reference = {
            "line_count": 20,
            "ranges": [
                {
                    "start_line": 1,
                    "end_line": 20,
                    "relevance": 1.0,
                    "role": "core",
                }
            ],
        }
        run = {
            "posterior_estimator": "demo",
            "sample_lines": 4,
            "samples": [
                {
                    "probe": 1,
                    "start_line": 1,
                    "end_line": 4,
                    "score": 0.9,
                    "kind": "random",
                }
            ],
        }
        result = evaluate(reference, run)
        self.assertEqual(result["search"]["first_high_hit_probe"], 1)
        self.assertAlmostEqual(result["final"]["high_line_recall"], 0.2)


if __name__ == "__main__":
    unittest.main()
