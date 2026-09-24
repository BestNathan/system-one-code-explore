import unittest

from posterior_reconstruction import (
    adaptive_gaussian,
    multi_scale_gaussian,
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
        self.assertEqual(a["relevance"], b["relevance"])
        self.assertEqual(a["uncertainty"], b["uncertainty"])

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


if __name__ == "__main__":
    unittest.main()
