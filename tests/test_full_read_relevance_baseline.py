import json
import unittest

from full_read_relevance_baseline import canonical_ranges, normalize


class FullReadBaselineTests(unittest.TestCase):
    def test_overlapping_grid(self):
        rows = canonical_ranges(150, 64, 32)
        self.assertEqual(
            [(r["start_line"], r["end_line"]) for r in rows],
            [(1, 64), (33, 96), (65, 128), (97, 150)],
        )

    def test_normalize_requires_every_range(self):
        expected = canonical_ranges(100, 64, 32)
        payload = {
            "kind": "claude-full-read-relevance-field",
            "full_read": True,
            "ranges": [
                {
                    **r,
                    "relevance": 0.8,
                    "role": "core",
                    "continuity": "self_contained",
                    "reason": "relevant",
                }
                for r in expected
            ],
        }
        result = normalize(
            json.dumps(payload),
            expected,
            "demo.rs",
            "find reconnect",
            100,
        )
        self.assertEqual(len(result["ranges"]), len(expected))
        self.assertTrue(result["full_read"])

    def test_normalize_rejects_missing_range(self):
        expected = canonical_ranges(100, 64, 32)
        payload = {
            "kind": "claude-full-read-relevance-field",
            "full_read": True,
            "ranges": [
                {
                    **r,
                    "relevance": 0.8,
                    "role": "core",
                    "continuity": "self_contained",
                    "reason": "relevant",
                }
                for r in expected[:-1]
            ],
        }
        with self.assertRaises(ValueError):
            normalize(
                json.dumps(payload),
                expected,
                "demo.rs",
                "find reconnect",
                100,
            )

    def test_normalize_rejects_geometry_change(self):
        expected = canonical_ranges(100, 64, 32)
        rows = [
            {
                **r,
                "relevance": 0.8,
                "role": "core",
                "continuity": "self_contained",
                "reason": "relevant",
            }
            for r in expected
        ]
        rows[0]["end_line"] = 63
        payload = {
            "kind": "claude-full-read-relevance-field",
            "full_read": True,
            "ranges": rows,
        }
        with self.assertRaises(ValueError):
            normalize(
                json.dumps(payload),
                expected,
                "demo.rs",
                "find reconnect",
                100,
            )


if __name__ == "__main__":
    unittest.main()
