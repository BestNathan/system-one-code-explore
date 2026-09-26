"""Shared transport, observability, and usage boundary for System One calls."""
from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
import uuid

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 522, 523, 524, 529}
MAX_REQUEST_ATTEMPTS = 5


class SystemOneClient:
    """Execute every physical System One request through one stable contract."""

    def __init__(self, key, trace, endpoint=API_URL, model=MODEL, *,
                 max_request_attempts=MAX_REQUEST_ATTEMPTS, opener=None, sleeper=None,
                 call_id_factory=None):
        self.key = key
        self.trace = trace
        self.endpoint = endpoint
        self.model = model
        self.max_request_attempts = int(max_request_attempts)
        self.opener = opener or urllib.request.urlopen
        self.sleeper = sleeper or time.sleep
        self.call_id_factory = call_id_factory or (lambda: "call-" + uuid.uuid4().hex)
        self._call_context = threading.local()

    @staticmethod
    def request_hash(payload):
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def request(self, payload):
        body = json.dumps(payload).encode()
        for attempt in range(self.max_request_attempts):
            request = urllib.request.Request(
                self.endpoint,
                data=body,
                method="POST",
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json"},
            )
            try:
                with self.opener(request, timeout=60) as response:
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                retryable = exc.code in TRANSIENT_HTTP_STATUS
                if not retryable or attempt == self.max_request_attempts - 1:
                    raise RuntimeError(f"TypeSafe HTTP {exc.code}: {detail[:2000]}") from exc
                delay = 2 ** attempt
                self._emit_retry(exc.code, attempt + 1, delay)
                self.sleeper(delay)
            except urllib.error.URLError as exc:
                if attempt == self.max_request_attempts - 1:
                    raise RuntimeError(f"TypeSafe transport error: {exc}") from exc
                delay = 2 ** attempt
                self._emit_retry("transport", attempt + 1, delay)
                self.sleeper(delay)

    def _emit_retry(self, status, attempt, delay):
        self.trace.emit(
            "system_one_retry",
            call_id=getattr(self._call_context, "call_id", None),
            request_hash=getattr(self._call_context, "request_hash", None),
            status=status,
            attempt=attempt,
            delay_seconds=delay,
        )

    def call(self, stage, state, questions, *, transport=None):
        payload = {"state": state, "model": self.model, "questions": questions}
        request_hash = self.request_hash(payload)
        call_id = self.call_id_factory()
        self._call_context.call_id = call_id
        self._call_context.request_hash = request_hash
        self.trace.emit(
            "system_one_request",
            call_id=call_id,
            request_hash=request_hash,
            stage=stage,
            request_bytes=len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            question_count=len(questions),
            request=payload,
        )
        started = time.perf_counter()
        try:
            response = (transport or self.request)(payload)
        except Exception as exc:
            self.trace.emit(
                "system_one_error",
                call_id=call_id,
                request_hash=request_hash,
                stage=stage,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise
        finally:
            self._call_context.call_id = None
            self._call_context.request_hash = None
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        raw_usage = response.get("usage", {})
        self.trace.emit(
            "system_one_response",
            call_id=call_id,
            request_hash=request_hash,
            stage=stage,
            latency_ms=latency_ms,
            model=response.get("model"),
            usage=raw_usage,
            answers=response.get("answers", {}),
            response=response,
        )
        return response, {
            "model_calls": 1,
            "input_tokens": int(raw_usage.get("input_tokens", 0) or 0),
            "output_tokens": int(raw_usage.get("output_tokens", 0) or 0),
            "call_id": call_id,
            "request_hash": request_hash,
        }
