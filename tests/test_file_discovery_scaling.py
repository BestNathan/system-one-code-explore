import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def candidate(path):
    return {"id": f"file:{path}", "path": path, "kind": "file",
            "payload": {"path": path, "filename": Path(path).name,
                        "extension": Path(path).suffix, "size_bytes": 1}}


class FakeDecider:
    model = "fake"
    profile = "baseline_v1"
    endpoint = "offline"

    def __init__(self, route=0.1, uncertainty=0.1, file_score=0.9):
        self.route = route
        self.uncertainty = uncertainty
        self.file_score = file_score
        self.active = 0
        self.peak = 0
        self.calls = 0
        self.lock = threading.Lock()

    def score_candidates(self, query, stage, candidates):
        with self.lock:
            self.active += 1
            self.calls += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.01)
        with self.lock:
            self.active -= 1
        return [dict(c, score=self.route if stage == "route" else self.file_score,
                     uncertainty=self.uncertainty) for c in reversed(candidates)], {
                         "model_calls": 1, "input_tokens": len(candidates) * 10,
                         "output_tokens": len(candidates)}


class ScalingTests(unittest.TestCase):
    def setUp(self):
        for name in ("file_discovery_scoring", "file_discovery_adaptive"):
            self.assertIsNotNone(importlib.util.find_spec(name), f"missing feature: {name}")
        from file_discovery_scoring import BatchScorer
        from file_discovery_adaptive import discover
        self.Scorer = BatchScorer
        self.discover = discover

    def test_concurrency_preserves_every_candidate_and_stable_order(self):
        items = [candidate(f"src/item_{i:03}.py") for i in range(40)]
        decider = FakeDecider()
        scorer = self.Scorer("task", decider, workers=4, batch_size=3)
        result = scorer.score("file", list(reversed(items)))
        self.assertEqual([x["id"] for x in result], sorted(x["id"] for x in items))
        self.assertGreater(decider.peak, 1)
        self.assertLessEqual(decider.peak, 4)
        self.assertEqual(scorer.usage["input_tokens"], 400)

    def test_cache_reuses_identical_batches_but_not_changed_query(self):
        cache = {}
        decider = FakeDecider()
        items = [candidate("src/example.py")]
        first = self.Scorer("alpha", decider, cache=cache)
        first.score("file", items)
        second = self.Scorer("alpha", decider, cache=cache)
        second.score("file", items)
        self.assertEqual(second.usage["model_calls"], 0)
        self.assertEqual(second.usage["logical_input_tokens"], 10)
        self.Scorer("beta", decider, cache=cache).score("file", items)
        self.assertEqual(decider.calls, 2)

    def test_missing_answer_fails_instead_of_silently_dropping_file(self):
        class Missing(FakeDecider):
            def score_candidates(self, query, stage, candidates):
                return [], {"model_calls": 1}
        with self.assertRaises(ValueError):
            self.Scorer("task", Missing()).score("file", [candidate("a.py")])

    def test_nonfinite_answer_fails(self):
        with self.assertRaises(ValueError):
            self.Scorer("task", FakeDecider(file_score=float("nan"))).score(
                "file", [candidate("a.py")])

    def test_more_than_2000_files_are_not_capped(self):
        items = [candidate(f"src/area{i}/reconnect.py") for i in range(2051)]
        scorer = self.Scorer("reconnect", FakeDecider(), batch_size=64)
        result = self.discover(items, "reconnect", scorer, policy="lexical")
        self.assertEqual(result["scored_file_count"], 2051)

    def test_global_lexical_rescue_bypasses_low_scoring_parent(self):
        items = [candidate("opaque/deep/reconnect.py"), candidate("other/unrelated.py")]
        scorer = self.Scorer("reconnect", FakeDecider(route=0.01))
        result = self.discover(items, "reconnect", scorer, policy="hybrid")
        self.assertIn("opaque/deep/reconnect.py", result["file_scores"])

    def test_uncertain_route_expands_instead_of_pruning(self):
        items = [candidate("opaque/hidden.py"), candidate("different/other.py")]
        scorer = self.Scorer("network lifecycle", FakeDecider(route=0.01, uncertainty=0.9))
        result = self.discover(items, "network lifecycle", scorer, policy="hierarchy")
        self.assertEqual(result["scored_file_count"], 2)
        self.assertGreater(result["route_scored_count"], 0)

    def test_hybrid_follows_siblings_until_no_new_candidates(self):
        items = [candidate("pkg/reconnect.py"), candidate("pkg/opaque.py"),
                 candidate("other/unrelated.py")]
        scorer = self.Scorer("reconnect", FakeDecider(route=0.01))
        result = self.discover(items, "reconnect", scorer, policy="hybrid")
        self.assertIn("pkg/opaque.py", result["file_scores"])
        self.assertNotIn("other/unrelated.py", result["file_scores"])

    def test_no_targets_produces_explicit_empty_result(self):
        scorer = self.Scorer("quux", FakeDecider(route=0.01))
        result = self.discover([candidate("src/other.py")], "quux", scorer, policy="hierarchy")
        self.assertEqual(result["scored_file_count"], 0)
        self.assertGreater(result["deferred_module_count"], 0)

    def test_module_summary_breaks_frequency_ties_lexically(self):
        from file_discovery_adaptive import module_card
        node = {"id": "module:test", "prefix": "test", "children": [],
                "members": ["alpha.py", "bravo.py", "charlie.py"]}
        self.assertEqual(module_card(node, "task")["payload"]["common_descendant_tokens"],
                         ["alpha", "bravo", "charlie"])

    def test_semantic_path_tokens_expand_common_code_abbreviations(self):
        from file_discovery_adaptive import semantic_tokens
        self.assertTrue({"filesystem", "fs"} <= semantic_tokens("filesystem safety"))
        self.assertTrue({"websocket", "ws"} <= semantic_tokens("WebSocket dispatch"))

    def test_semantic_lexical_recovers_first_round_misses(self):
        from file_discovery_adaptive import semantic_lexical_matches
        items = [candidate("crates/nession-agent/src/fs/sandbox.rs"),
                 candidate("src/gateway/server/ws-connection/message-handler.ts"),
                 candidate("docs/unrelated.md")]
        fs = semantic_lexical_matches(items, "filesystem symlink delete safety")
        ws = semantic_lexical_matches(items, "Gateway WebSocket request dispatch")
        self.assertIn("crates/nession-agent/src/fs/sandbox.rs", fs)
        self.assertIn("src/gateway/server/ws-connection/message-handler.ts", ws)

    def test_adaptive_v2_starts_below_lossy_root_and_has_no_sibling_expansion(self):
        items = [candidate("alpha/reconnect.py"), candidate("alpha/opaque.py"),
                 candidate("beta/unrelated.py")]
        decider = FakeDecider(route=0.01, uncertainty=0.01)
        scorer = self.Scorer("reconnect", decider)
        result = self.discover(items, "reconnect", scorer, policy="adaptive_v2")
        route_ids = [x["id"] for x in result["route_decisions"]]
        self.assertNotIn("module:.", route_ids)
        self.assertIn("alpha/reconnect.py", result["file_scores"])
        self.assertNotIn("alpha/opaque.py", result["file_scores"])

    def test_trace_retains_billed_usage_even_before_answer_validation(self):
        from file_discovery_scoring import LockedTrace
        trace = LockedTrace(None)
        trace.emit("system_one_response", latency_ms=42, model="pinned-model",
                   usage={"input_tokens": 123, "output_tokens": 4}, answers={})
        self.assertEqual(getattr(trace, "input_tokens", None), 123)
        self.assertEqual(getattr(trace, "response_count", None), 1)

    def test_model_call_trace_links_request_to_full_raw_response(self):
        from system_one_code_locator import SystemOneDecider, Trace

        class OfflineDecider(SystemOneDecider):
            def request(self, payload):
                return {"id": "response-1", "model": "pinned-model",
                        "usage": {"input_tokens": 7, "output_tokens": 2},
                        "answers": {"question": {"type": "noul", "noul": 0.75}},
                        "server_metadata": {"revision": "2026-09-26"}}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            decider = OfflineDecider("secret", Trace(path), model="pinned-model")
            decider.send("file_scoring", {"goal": "find target"}, {
                "question": {"type": "noul"},
            })
            events = [json.loads(line) for line in path.read_text().splitlines()]

        request = next(event for event in events if event["event"] == "system_one_request")
        response = next(event for event in events if event["event"] == "system_one_response")
        self.assertTrue(request["call_id"])
        self.assertEqual(response["call_id"], request["call_id"])
        self.assertEqual(response["request_hash"], request["request_hash"])
        self.assertEqual(response["response"]["id"], "response-1")
        self.assertEqual(response["response"]["server_metadata"]["revision"], "2026-09-26")

    def test_model_call_trace_records_terminal_failure(self):
        from system_one_code_locator import SystemOneDecider, Trace

        class FailingDecider(SystemOneDecider):
            def request(self, payload):
                raise RuntimeError("offline failure")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            decider = FailingDecider("secret", Trace(path))
            with self.assertRaisesRegex(RuntimeError, "offline failure"):
                decider.send("file_scoring", {"goal": "find target"}, {})
            events = [json.loads(line) for line in path.read_text().splitlines()]

        request = next(event for event in events if event["event"] == "system_one_request")
        failure = next(event for event in events if event["event"] == "system_one_error")
        self.assertEqual(failure["call_id"], request["call_id"])
        self.assertEqual(failure["error_type"], "RuntimeError")
        self.assertEqual(failure["message"], "offline failure")

    def test_call_dataset_pairs_events_and_writes_checksum_manifest(self):
        import file_discovery_scoring

        writer = getattr(file_discovery_scoring, "write_call_dataset", None)
        self.assertIsNotNone(writer, "missing raw-call dataset writer")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace.jsonl"
            calls = root / "raw-model-calls.jsonl"
            manifest = root / "call-manifest.json"
            trace.write_text("\n".join(json.dumps(event) for event in [
                {"event": "system_one_request", "call_id": "call-1",
                 "request_hash": "sha256:request", "request": {"model": "m"}},
                {"event": "system_one_retry", "call_id": "call-1", "status": 429},
                {"event": "system_one_response", "call_id": "call-1",
                 "request_hash": "sha256:request", "response": {"id": "r-1"}},
                {"event": "system_one_cache_reuse", "logical_call_id": "logical-1",
                 "source_call_id": "call-1", "request_hash": "sha256:request"},
            ]) + "\n")
            result = writer(trace, calls, manifest)
            records = [json.loads(line) for line in calls.read_text().splitlines()]
            persisted = json.loads(manifest.read_text())

        self.assertEqual(records[0]["request"]["call_id"], "call-1")
        self.assertEqual(records[0]["retries"][0]["status"], 429)
        self.assertEqual(records[0]["outcome"]["response"]["id"], "r-1")
        self.assertEqual(result, persisted)
        self.assertEqual(persisted["physical_calls"], 1)
        self.assertEqual(persisted["cache_reuses"], 1)
        self.assertTrue(persisted["complete"])
        self.assertRegex(persisted["calls_sha256"], r"^[0-9a-f]{64}$")

    def test_cache_reuse_links_logical_decision_to_physical_call(self):
        class RecordingTrace:
            def __init__(self):
                self.events = []

            def emit(self, event, **data):
                self.events.append({"event": event, **data})

        class TracedDecider(FakeDecider):
            def __init__(self, trace):
                super().__init__()
                self.trace = trace

            def score_candidates(self, query, stage, candidates):
                results, usage = super().score_candidates(query, stage, candidates)
                return results, {**usage, "call_id": "call-source",
                                 "request_hash": "sha256:request"}

        cache = {}
        trace = RecordingTrace()
        items = [candidate("src/example.py")]
        self.Scorer("task", TracedDecider(trace), cache=cache).score("file", items)
        self.Scorer("task", TracedDecider(trace), cache=cache).score("file", items)
        event = next(item for item in trace.events if item["event"] == "system_one_cache_reuse")
        self.assertEqual(event["source_call_id"], "call-source")
        self.assertEqual(event["request_hash"], "sha256:request")
        self.assertTrue(event["logical_call_id"].startswith("logical-"))


class ScalingReportTests(unittest.TestCase):
    def test_report_preserves_failed_arm_and_expected_count(self):
        self.assertIsNotNone(importlib.util.find_spec("file_discovery_scaling_benchmark"),
                             "missing feature: scaling benchmark report")
        from file_discovery_scaling_benchmark import render_report
        report = render_report({"run_url": "https://example.test/run", "code_sha": "abc",
                                "expected_rows": 2, "rows": [
                                    {"case_id": "case-a", "arm": "hybrid", "status": "failed",
                                     "error": "missing answer"}]})
        self.assertIn("missing answer", report)
        self.assertIn("1/2", report)
        self.assertIn("https://example.test/run", report)


class StableSelectionTests(unittest.TestCase):
    def test_relative_guard_uses_original_repository_population(self):
        self.assertIsNotNone(importlib.util.find_spec("file_discovery_selection"),
                             "missing feature: stable selection")
        from file_discovery_selection import select_relevant
        selected, policy = select_relevant(
            {"best.py": 0.9, "target.py": 0.53},
            enumerated_file_count=1096,
            file_threshold=0.65,
            relative_fallback_fraction=0.01,
        )
        self.assertEqual({x["path"] for x in selected}, {"best.py", "target.py"})
        self.assertEqual(policy["relative_fallback_population"], 1096)
        self.assertEqual(policy["relative_fallback_min_count"], 11)

    def test_relative_guard_never_discards_scored_candidates_when_guard_is_larger(self):
        from file_discovery_selection import select_relevant
        scores = {f"file-{i}.py": i / 100 for i in range(20)}
        selected, _ = select_relevant(scores, enumerated_file_count=5000)
        self.assertEqual(len(selected), 20)


if __name__ == "__main__":
    unittest.main()
