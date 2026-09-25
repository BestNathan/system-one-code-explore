import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from model_pricing import jev_cost_record, jev_cost_usd


class ModelPricingTests(unittest.TestCase):
    def test_jev_official_snapshot_rate(self):
        self.assertAlmostEqual(
            jev_cost_usd(1_000_000, 500_000),
            0.042,
            places=12,
        )

    def test_current_file_discovery_example(self):
        record = jev_cost_record(212_584, 10_000)
        self.assertAlmostEqual(
            record["estimated_cost_usd"],
            0.008928528,
            places=12,
        )
        self.assertEqual(record["output_usd_per_million"], 0.0)


if __name__ == "__main__":
    unittest.main()
