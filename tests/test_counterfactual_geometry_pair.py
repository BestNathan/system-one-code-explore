import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from counterfactual_geometry_pair import (
    CachedFrontierObligationDecider,
    SharedDecisionCache,
    semantic_cache_key,
)
from system_one_code_locator import Trace


class DummyCachedDecider(CachedFrontierObligationDecider):
    request_count = 0

    def request(self, payload):
        type(self).request_count += 1
        return {
            "model": "dummy",
            "usage": {
                "input_tokens": 123,
                "output_tokens": 7,
            },
            "answers": {
                key: {
                    "type": "noul",
                    "noul": 0.61,
                }
                for key in payload["questions"]
            },
        }


class R19CounterfactualCacheTests(unittest.TestCase):
    def setUp(self):
        DummyCachedDecider.request_count = 0

    def test_cache_key_ignores_runtime_ids(self):
        questions = {
            "need_after": {
                "type": "noul",
                "instructions": {
                    "goal": "g",
                    "source": "same",
                },
            }
        }
        a = semantic_cache_key(
            "closure",
            {
                "goal": "g",
                "anchor_id": "anchor_001",
                "obligation_id": "obligation_002",
            },
            questions,
        )
        b = semantic_cache_key(
            "closure",
            {
                "goal": "g",
                "anchor_id": "anchor_999",
                "obligation_id": "obligation_888",
            },
            questions,
        )
        self.assertEqual(a, b)

    def test_cache_key_preserves_semantic_source(self):
        q1 = {
            "need_after": {
                "type": "noul",
                "instructions": {
                    "goal": "g",
                    "source": "source A",
                },
            }
        }
        q2 = {
            "need_after": {
                "type": "noul",
                "instructions": {
                    "goal": "g",
                    "source": "source B",
                },
            }
        }
        self.assertNotEqual(
            semantic_cache_key("closure", {"goal": "g"}, q1),
            semantic_cache_key("closure", {"goal": "g"}, q2),
        )

    def test_identical_semantic_requests_share_exact_response_and_usage(self):
        cache = SharedDecisionCache()
        with tempfile.TemporaryDirectory() as directory:
            first = DummyCachedDecider(
                "key",
                Trace(Path(directory) / "a.jsonl"),
                cache,
                "https://unused.invalid",
                "dummy",
                "baseline",
            )
            second = DummyCachedDecider(
                "key",
                Trace(Path(directory) / "b.jsonl"),
                cache,
                "https://unused.invalid",
                "dummy",
                "hybrid",
            )
            questions = {
                "need_after": {
                    "type": "noul",
                    "instructions": {
                        "goal": "g",
                        "source": "literal code",
                    },
                }
            }
            response_a, usage_a = first.send(
                "closure",
                {
                    "goal": "g",
                    "anchor_id": "anchor_001",
                    "obligation_id": "obligation_001",
                },
                questions,
            )
            response_b, usage_b = second.send(
                "closure",
                {
                    "goal": "g",
                    "anchor_id": "anchor_007",
                    "obligation_id": "obligation_004",
                },
                questions,
            )

        self.assertEqual(response_a, response_b)
        self.assertEqual(usage_a, usage_b)
        self.assertEqual(DummyCachedDecider.request_count, 1)
        self.assertEqual(cache.misses, 1)
        self.assertEqual(cache.hits, 1)
        self.assertEqual(
            cache.physical_usage,
            {
                "model_calls": 1,
                "input_tokens": 123,
                "output_tokens": 7,
            },
        )


if __name__ == "__main__":
    unittest.main()
