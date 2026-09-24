import unittest

from compare_to_full_read_baseline import evaluate


class FullReadComparisonTests(unittest.TestCase):
    def test_weighted_recall_tracks_reference_mass(self):
        reference = {
            "path": "demo.rs",
            "line_count": 100,
            "ranges": [
                {
                    "start_line": 1,
                    "end_line": 50,
                    "relevance": 1.0,
                    "role": "core",
                },
                {
                    "start_line": 51,
                    "end_line": 100,
                    "relevance": 0.0,
                    "role": "irrelevant",
                },
            ],
        }
        candidate = {
            "files": [{
                "path": "demo.rs",
                "evidence": [{"start_line": 1, "end_line": 25}],
            }]
        }
        result = evaluate(reference, candidate)
        self.assertAlmostEqual(
            result["metrics"]["weighted_relevance_recall"],
            0.5,
        )
        self.assertEqual(
            result["metrics"]["core_window_recall"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
