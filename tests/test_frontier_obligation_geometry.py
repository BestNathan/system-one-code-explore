import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from frontier_obligation_geometry import (
    local_prominence,
    mass_diverse,
    multiscale_prominence,
    q75_plus_secondary_peaks,
    quantile_components,
    tile_actions,
)


class R16GeometryTests(unittest.TestCase):
    def frontier(self, scores, tile_lines=32):
        relevance = []
        for score in scores:
            relevance.extend([float(score)] * tile_lines)
        return {
            "line_count": len(relevance),
            "relevance": relevance,
            "uncertainty": [0.5] * len(relevance),
            "observed": [False] * len(relevance),
        }

    def actions(self, scores):
        return tile_actions(self.frontier(scores), tile_lines=32)

    def test_q75_matches_connected_component_baseline(self):
        actions = self.actions([
            0.10,
            0.20,
            0.90,
            0.85,
            0.10,
            0.15,
            0.80,
            0.82,
        ])
        obligations = quantile_components(
            actions,
            0.75,
            "q75_components",
        )
        self.assertEqual(len(obligations), 2)
        self.assertEqual(
            obligations[0]["tile_ids"],
            ["tile_003", "tile_004"],
        )
        self.assertEqual(
            obligations[1]["tile_ids"],
            ["tile_008"],
        )

    def test_local_prominence_keeps_secondary_mode_below_global_q75(self):
        actions = self.actions([
            0.80,
            0.78,
            0.76,
            0.74,
            0.20,
            0.18,
            0.42,
            0.46,
            0.43,
            0.17,
            0.15,
            0.14,
        ])
        q75 = quantile_components(
            actions,
            0.75,
            "q75_components",
        )
        local, _ = local_prominence(actions)

        q75_ids = {
            tile_id
            for obligation in q75
            for tile_id in obligation["tile_ids"]
        }
        local_ids = {
            tile_id
            for obligation in local
            for tile_id in obligation["tile_ids"]
        }

        self.assertNotIn("tile_008", q75_ids)
        self.assertIn("tile_008", local_ids)

    def test_flat_field_collapses_to_one_prominence_obligation(self):
        actions = self.actions([0.8] * 10)
        local, metadata = local_prominence(actions)
        self.assertEqual(len(local), 1)
        self.assertEqual(
            local[0]["tile_index_range"],
            [0, 9],
        )
        self.assertTrue(
            metadata["candidate_peaks"][0]["flat_plateau"]
        )

    def test_multiscale_preserves_broad_secondary_mode(self):
        actions = self.actions([
            0.72,
            0.70,
            0.68,
            0.20,
            0.28,
            0.36,
            0.43,
            0.47,
            0.46,
            0.42,
            0.30,
            0.18,
        ])
        obligations, metadata = multiscale_prominence(actions)
        ids = {
            tile_id
            for obligation in obligations
            for tile_id in obligation["tile_ids"]
        }
        self.assertIn("tile_008", ids)
        self.assertGreaterEqual(
            len(metadata["clusters"]),
            1,
        )

    def test_hybrid_adds_narrow_secondary_peak(self):
        actions = self.actions([
            0.80,
            0.78,
            0.76,
            0.74,
            0.20,
            0.18,
            0.42,
            0.46,
            0.43,
            0.17,
            0.15,
            0.14,
        ])
        q75 = quantile_components(
            actions,
            0.75,
            "q75_components",
        )
        _, metadata = local_prominence(actions)
        hybrid, hybrid_meta = q75_plus_secondary_peaks(
            actions,
            q75,
            metadata["candidate_peaks"],
            method="q75_plus_local_seed",
        )
        ranges = [
            item["tile_index_range"]
            for item in hybrid
        ]
        self.assertIn([7, 7], ranges)
        self.assertGreaterEqual(
            hybrid_meta["secondary_count"],
            1,
        )

    def test_hybrid_rejects_bottom_half_local_peak(self):
        actions = self.actions([
            0.90,
            0.88,
            0.86,
            0.84,
            0.82,
            0.80,
            0.10,
            0.25,
            0.10,
            0.79,
            0.78,
            0.77,
        ])
        q75 = quantile_components(
            actions,
            0.75,
            "q75_components",
        )
        _, metadata = local_prominence(actions)
        hybrid, _ = q75_plus_secondary_peaks(
            actions,
            q75,
            metadata["candidate_peaks"],
            method="q75_plus_local_seed",
        )
        ids = {
            tile_id
            for obligation in hybrid
            for tile_id in obligation["tile_ids"]
        }
        self.assertNotIn("tile_008", ids)

    def test_mass_diverse_has_deterministic_cap(self):
        actions = self.actions([
            0.9,
            0.8,
            0.2,
            0.1,
            0.6,
            0.7,
            0.1,
            0.5,
            0.4,
            0.1,
            0.3,
            0.2,
        ])
        obligations, metadata = mass_diverse(actions)
        self.assertLessEqual(
            len(metadata["representatives"]),
            metadata["representative_cap"],
        )
        self.assertGreater(len(obligations), 0)
        self.assertGreaterEqual(
            metadata["represented_mass_fraction"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
