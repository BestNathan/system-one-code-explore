import unittest

from system_one_probability_frontier import (
    append_probability_sample,
    generate_probe_actions,
    new_probability_frontier,
    quantize,
    rebuild_probability_frontier,
    select_choice_batch,
    update_probability_frontier,
)


class ProbabilityFrontierV5Tests(unittest.TestCase):
    def test_frontier_length_matches_file_length(self):
        f = new_probability_frontier(3030)
        self.assertEqual(len(f["relevance"]), 3030)
        self.assertEqual(len(f["uncertainty"]), 3030)
        self.assertEqual(len(f["observed"]), 3030)
        self.assertEqual(len(quantize(f["relevance"])), 3030)

    def test_sparse_update_does_not_collapse_far_unknown_lines(self):
        f = new_probability_frontier(3000)
        update_probability_frontier(f, 100, 107, 0.9, decay_lines=32)
        self.assertTrue(all(f["observed"][99:107]))
        self.assertGreater(f["relevance"][102], 0.65)
        self.assertAlmostEqual(f["relevance"][2500], 0.5, places=6)
        self.assertAlmostEqual(f["uncertainty"][2500], 1.0, places=6)

    def test_pluggable_sequential_posterior_matches_legacy_updates(self):
        samples = [
            (100, 107, 0.9),
            (500, 507, 0.2),
            (250, 257, 0.7),
        ]
        legacy = new_probability_frontier(800)
        plugin = new_probability_frontier(800)

        for left, right, score in samples:
            update_probability_frontier(
                legacy,
                left,
                right,
                score,
            )
            append_probability_sample(
                plugin,
                left,
                right,
                score,
            )
            rebuild_probability_frontier(
                plugin,
                estimator="sequential_exponential",
                sample_lines=8,
            )

        self.assertEqual(legacy["relevance"], plugin["relevance"])
        self.assertEqual(legacy["uncertainty"], plugin["uncertainty"])
        self.assertEqual(legacy["observed"], plugin["observed"])

    def test_online_frontier_can_switch_to_multiscale_posterior(self):
        frontier = new_probability_frontier(800)
        for left, right, score in [
            (100, 107, 0.9),
            (500, 507, 0.2),
            (250, 257, 0.7),
        ]:
            append_probability_sample(
                frontier,
                left,
                right,
                score,
            )
        rebuild_probability_frontier(
            frontier,
            estimator="multi_scale_gaussian",
            sample_lines=8,
        )
        self.assertEqual(
            frontier["posterior_estimator"],
            "multi_scale_gaussian_k2_k4",
        )
        self.assertEqual(len(frontier["relevance"]), 800)
        self.assertEqual(len(frontier["uncertainty"]), 800)

    def test_action_generation_is_diverse_and_reproducible(self):
        f = new_probability_frontier(3000)
        a = generate_probe_actions(
            f, path="demo.rs", epoch=3, sample_lines=8, max_actions=16
        )
        b = generate_probe_actions(
            f, path="demo.rs", epoch=3, sample_lines=8, max_actions=16
        )
        self.assertEqual(a, b)
        self.assertGreaterEqual(len(a), 8)
        starts = [x["start_line"] for x in a]
        self.assertGreater(max(starts) - min(starts), 1500)
        kinds = {x["kind"] for x in a}
        self.assertIn("random_stratified", kinds)
        self.assertIn("uncertainty", kinds)
        self.assertIn("gradient", kinds)
        self.assertIn("peak_neighbor", kinds)

        centers = sorted((x["start_line"] + x["end_line"]) // 2 for x in a)
        self.assertTrue(
            all(right - left >= 24 for left, right in zip(centers, centers[1:]))
        )

    def test_choice_distribution_selects_multiple_probes(self):
        ids = ["p1", "p2", "p3", "p4"]
        selected = select_choice_batch(
            {"p1": 0.31, "p2": 0.22, "p3": 0.07, "p4": 0.05, "stop": 0.35},
            ids,
            threshold=0.08,
            max_batch=4,
        )
        self.assertEqual(selected, ["p1", "p2"])

    def test_choice_can_stop_when_no_probe_clears_threshold(self):
        ids = ["p1", "p2", "p3"]
        selected = select_choice_batch(
            {"p1": 0.12, "p2": 0.10, "p3": 0.08, "stop": 0.70},
            ids,
            threshold=0.20,
            max_batch=4,
        )
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
