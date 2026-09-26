"""Concurrent, deterministic batch scoring with exact-request caching."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from system_one_code_locator import Trace


def write_call_dataset(trace_path, calls_path, manifest_path):
    trace_path, calls_path, manifest_path = map(Path, (trace_path, calls_path, manifest_path))
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    requests = {}
    retries = {}
    outcomes = {}
    cache_reuses = []
    orphan_outcomes = 0
    for event in events:
        kind = event.get("event")
        call_id = event.get("call_id")
        if kind == "system_one_request" and call_id:
            requests[call_id] = event
        elif kind == "system_one_retry" and call_id:
            retries.setdefault(call_id, []).append(event)
        elif kind in {"system_one_response", "system_one_error"} and call_id:
            outcomes[call_id] = event
            orphan_outcomes += call_id not in requests
        elif kind == "system_one_cache_reuse":
            cache_reuses.append(event)
    records = [{"schema_version": 1, "call_id": call_id,
                "request_hash": request.get("request_hash"), "request": request,
                "retries": retries.get(call_id, []), "outcome": outcomes.get(call_id)}
               for call_id, request in requests.items()]
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    calls_bytes = ("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                           for record in records)).encode("utf-8")
    calls_path.write_bytes(calls_bytes)
    trace_bytes = trace_path.read_bytes()
    status_counts = {}
    for record in records:
        status = (record["outcome"] or {}).get("event", "missing_outcome")
        status_counts[status] = status_counts.get(status, 0) + 1
    manifest = {
        "schema_version": 1,
        "trace_file": trace_path.name,
        "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "trace_bytes": len(trace_bytes),
        "calls_file": calls_path.name,
        "calls_sha256": hashlib.sha256(calls_bytes).hexdigest(),
        "calls_bytes": len(calls_bytes),
        "physical_calls": len(records),
        "cache_reuses": len(cache_reuses),
        "status_counts": status_counts,
        "orphan_outcomes": orphan_outcomes,
        "complete": orphan_outcomes == 0 and all(record["outcome"] for record in records),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    return manifest


class LockedTrace(Trace):
    def __init__(self, path):
        super().__init__(path)
        self.lock = threading.RLock()
        self.retries = 0
        self.rate_limits = 0
        self.requests = 0
        self.max_request_bytes = 0
        self.returned_models = set()
        self.input_tokens = 0
        self.output_tokens = 0
        self.response_count = 0
        self.response_time_sum_ms = 0.0

    def emit(self, event, **data):
        with self.lock:
            if event == "system_one_retry":
                self.retries += 1
                self.rate_limits += data.get("status") == 429
            if event == "system_one_request":
                self.requests += 1
                self.max_request_bytes = max(self.max_request_bytes, data["request_bytes"])
            if event == "system_one_response" and data.get("model"):
                self.returned_models.add(str(data["model"]))
            if event == "system_one_response":
                self.response_count += 1
                usage = data.get("usage", {})
                self.input_tokens += int(usage.get("input_tokens", 0) or 0)
                self.output_tokens += int(usage.get("output_tokens", 0) or 0)
                self.response_time_sum_ms += float(data.get("latency_ms", 0))
            super().emit(event, **data)


class BatchScorer:
    def __init__(self, query, decider, *, workers=4, batch_size=64,
                 cache=None, max_candidate_bytes=48000):
        if workers < 1 or batch_size < 1 or max_candidate_bytes < 1:
            raise ValueError("positive transport settings required")
        self.query, self.decider = query, decider
        self.workers, self.batch_size = workers, batch_size
        self.max_candidate_bytes = max_candidate_bytes
        self.cache = {} if cache is None else cache
        self.usage = dict(model_calls=0, input_tokens=0, output_tokens=0,
                          logical_model_calls=0, logical_input_tokens=0,
                          logical_output_tokens=0, cache_hits=0, cache_misses=0,
                          request_time_sum_ms=0.0, scoring_wall_time_ms=0.0,
                          peak_in_flight=0, failed_batches=0)
        self.stages = {}
        self.active = 0
        self.lock = threading.Lock()

    def _batches(self, candidates):
        ordered = sorted(candidates, key=lambda x: x["id"])
        if len({c["id"] for c in ordered}) != len(ordered):
            raise ValueError("duplicate candidate IDs")
        sizes = [len(json.dumps(c["payload"], ensure_ascii=False).encode("utf-8")) for c in ordered]
        # Validate the entire wave before starting any billable request.
        for c, n in zip(ordered, sizes):
            if n > self.max_candidate_bytes:
                raise ValueError(f"single candidate exceeds transport size: {c['id']}")
        batch, size = [], 0
        for c, n in zip(ordered, sizes):
            if batch and (len(batch) >= self.batch_size or size + n > self.max_candidate_bytes):
                yield batch
                batch, size = [], 0
            batch.append(c)
            size += n
        if batch:
            yield batch

    def _key(self, stage, batch):
        obj = {"version": 1, "query": self.query, "stage": stage,
               "model": getattr(self.decider, "model", None),
               "endpoint": getattr(self.decider, "endpoint", None),
               "profile": getattr(self.decider, "profile", None),
               "repository_context": getattr(self.decider, "repository_context", None),
               "batch": [{"id": c["id"], "payload": c["payload"]} for c in batch]}
        return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

    def _call(self, stage, batch):
        with self.lock:
            self.active += 1
            self.usage["peak_in_flight"] = max(self.usage["peak_in_flight"], self.active)
        started = time.perf_counter()
        try:
            result, usage = self.decider.score_candidates(self.query, stage, batch)
            return result, usage, (time.perf_counter() - started) * 1000
        finally:
            with self.lock:
                self.active -= 1

    def _record(self, stage, current, elapsed, cached):
        stats = self.stages.setdefault(stage, dict(logical_candidates=0, model_calls=0,
                                                  input_tokens=0, output_tokens=0))
        for key in ("model_calls", "input_tokens", "output_tokens"):
            value = int(current.get(key, 0) or 0)
            self.usage[f"logical_{key}"] += value
            if not cached:
                self.usage[key] += value
                stats[key] += value
        self.usage["cache_hits" if cached else "cache_misses"] += 1
        if not cached:
            self.usage["request_time_sum_ms"] += elapsed

    @staticmethod
    def _validate(batch, results, stage):
        expected = {c["id"] for c in batch}
        if len(results) != len(batch) or {c["id"] for c in results} != expected:
            raise ValueError("missing, extra or duplicate answer IDs")
        for item in results:
            for field in (("score", "uncertainty") if stage == "route" else ("score",)):
                value = float(item[field])
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError(f"invalid {field}: {value}")

    def score(self, stage, candidates):
        started = time.perf_counter()
        results = []
        # Only workers requests are submitted at once. Candidate batches remain lazy.
        batches = iter(self._batches(candidates))
        pending, failures = {}, []
        exhausted = False
        try:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                while pending or not exhausted:
                    while len(pending) < self.workers and not exhausted and not failures:
                        batch = next(batches, None)
                        if batch is None:
                            exhausted = True
                            break
                        key = self._key(stage, batch)
                        if key in self.cache:
                            scored, usage, elapsed = copy.deepcopy(self.cache[key])
                            trace = getattr(self.decider, "trace", None)
                            if trace is not None:
                                trace.emit("system_one_cache_reuse",
                                           logical_call_id="logical-" + uuid.uuid4().hex,
                                           source_call_id=usage.get("call_id"),
                                           request_hash=usage.get("request_hash"),
                                           cache_key=key, stage=stage,
                                           candidate_ids=[item["id"] for item in batch])
                            self._validate(batch, scored, stage)
                            self._record(stage, usage, elapsed, True)
                            self.stages[stage]["logical_candidates"] += len(batch)
                            results.extend(scored)
                        else:
                            pending[pool.submit(self._call, stage, batch)] = (key, batch)
                    if not pending:
                        break
                    done, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        key, batch = pending.pop(future)
                        try:
                            scored, usage, elapsed = future.result()
                            self._record(stage, usage, elapsed, False)
                            self._validate(batch, scored, stage)
                            self.stages[stage]["logical_candidates"] += len(batch)
                            self.cache[key] = copy.deepcopy((scored, usage, elapsed))
                            results.extend(scored)
                        except Exception as exc:
                            self.usage["failed_batches"] += 1
                            failures.append(exc)
                    if failures:
                        exhausted = True
            if failures:
                raise failures[0]
            return sorted(results, key=lambda x: x["id"])
        finally:
            self.usage["scoring_wall_time_ms"] += (time.perf_counter() - started) * 1000
