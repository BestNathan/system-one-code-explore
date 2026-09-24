import unittest

from posterior_reconstruction import (
    adaptive_gaussian,
    coverage_uncertainty,
    multi_scale_gaussian,
    multi_scale_gaussian_coverage_guard,
    reconstruct,
    sequential_exponential,
)


SAMPLES = [
    {"start_line": 10, "end_line": 17, "score": 0.9},
    {"start_line": 90, "end_line": 97, "score": 0.1},
    {"start_line": 50, "end_line": 57, "score": 0.7},
]


class PosteriorReconstructionTests(unittest.TestCase):
    def test_adaptive_gaussian_is_path_independent(self):
        a = adaptive_gaussian(SAMPLES, 120, kth_neighbor=3)
        b = adaptive_gaussian(
            list(reversed(SAMPLES)),
            120,
            kth_neighbor=3,
        )
        for left, right in zip(a["relevance"], b["relevance"]):
            self.assertAlmostEqual(left, right, places=14)
        for left, right in zip(a["uncertainty"], b["uncertainty"]):
            self.assertAlmostEqual(left, right, places=14)

    def test_sequential_baseline_is_order_sensitive(self):
        a = sequential_exponential(SAMPLES, 120)
        b = sequential_exponential(
            list(reversed(SAMPLES)),
            120,
        )
        self.assertNotEqual(a["relevance"], b["relevance"])

    def test_more_nearby_support_reduces_adaptive_uncertainty(self):
        sparse = adaptive_gaussian(SAMPLES[:1], 120, kth_neighbor=2)
        dense = adaptive_gaussian(SAMPLES, 120, kth_neighbor=2)
        self.assertLess(
            dense["uncertainty"][49],
            sparse["uncertainty"][49],
        )

    def test_multi_scale_preserves_file_length(self):
        result = multi_scale_gaussian(SAMPLES, 120)
        self.assertEqual(len(result["relevance"]), 120)
        self.assertEqual(len(result["uncertainty"]), 120)

    def test_coverage_uncertainty_rises_with_distance_from_observation(self):
        u = coverage_uncertainty(
            [{"start_line": 100, "end_line": 107, "score": 0.9}],
            1000,
        )
        self.assertAlmostEqual(u[99], 0.03, places=12)
        self.assertAlmostEqual(u[106], 0.03, places=12)
        self.assertLess(u[107], u[199])
        self.assertLess(u[199], u[499])
        self.assertGreater(u[899], 0.99)

    def test_coverage_guard_does_not_change_multi_scale_relevance(self):
        plain = multi_scale_gaussian(SAMPLES, 120)
        guarded = multi_scale_gaussian_coverage_guard(SAMPLES, 120)
        self.assertEqual(plain["relevance"], guarded["relevance"])
        self.assertEqual(len(guarded["uncertainty"]), 120)
        self.assertTrue(
            all(
                guarded_u >= plain_u
                for guarded_u, plain_u in zip(
                    guarded["uncertainty"],
                    plain["uncertainty"],
                )
            )
        )

    def test_coverage_guard_preserves_uncertainty_in_sparse_unread_regions(self):
        samples = [{"start_line": 10, "end_line": 17, "score": 0.9}]
        guarded = multi_scale_gaussian_coverage_guard(samples, 1000)
        self.assertLess(
            guarded["uncertainty"][17],
            guarded["uncertainty"][199],
        )
        self.assertLess(
            guarded["uncertainty"][199],
            guarded["uncertainty"][899],
        )
        self.assertGreater(guarded["uncertainty"][899], 0.99)

    def test_reconstruct_exposes_coverage_guard_estimator(self):
        guarded = reconstruct(
            "multi_scale_gaussian_coverage_guard",
            SAMPLES,
            120,
        )
        plain = reconstruct("multi_scale_gaussian", SAMPLES, 120)
        self.assertEqual(guarded["relevance"], plain["relevance"])
        self.assertEqual(
            guarded["name"],
            "multi_scale_gaussian_k2_k4_coverage_guard",
        )


if __name__ == "__main__":
    unittest.main()
