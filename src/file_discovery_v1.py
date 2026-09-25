#!/usr/bin/env python3
"""Canonical File Discovery V1.

Final converged mechanism:
- Harness mechanically enumerates supported file metadata.
- System One independently Noul-scores every file exactly once.
- No semantic directory pruning, top-k, source reads, global model Stop, or
  unchanged-state rescoring.
- Transport batching is implementation-only and does not affect semantics.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import math
from pathlib import Path

from system_one_code_locator import (
    API_URL,
    MODEL,
    IGNORE,
    SUFFIXES,
    SystemOneDecider,
    Trace,
)

DEFAULT_FILE_THRESHOLD = 0.65
DEFAULT_RELATIVE_FALLBACK_FRACTION = 0.01
DEFAULT_TRANSPORT_BATCH_SIZE = 64


def empty_usage():
    return {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "model_wall_time_ms": 0.0,
        "metadata_items_seen": 0,
        "cache_hits": 0,
        "cache_misses": 0,
    }


def merge_usage(total, current):
    for key in ("model_calls", "input_tokens", "output_tokens"):
        total[key] += int(current.get(key, 0) or 0)


def enumerate_files(root):
    root = Path(root).resolve()
    out = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(
            name
            for name in dirs
            if not name.startswith(".") and name not in IGNORE
        )
        base = Path(current)
        for name in sorted(names):
            if name.startswith("."):
                continue
            path = base / name
            if path.suffix.lower() not in SUFFIXES:
                continue
            try:
                size_bytes = path.stat().st_size
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            out.append({
                "id": f"file:{rel}",
                "kind": "file",
                "path": rel,
                "parent": (
                    path.parent.relative_to(root).as_posix()
                    if path.parent != root else "."
                ),
                "payload": {
                    "kind": "file",
                    "path": rel,
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": size_bytes,
                },
            })
    return out


def score_files(
    query,
    decider,
    candidates,
    usage,
    cache,
    *,
    batch_size=DEFAULT_TRANSPORT_BATCH_SIZE,
):
    results = []
    misses = []

    for candidate in candidates:
        key = json.dumps(
            {
                "query": query,
                "candidate": candidate["payload"],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if key in cache:
            usage["cache_hits"] += 1
            results.append({**candidate, "score": cache[key]})
        else:
            usage["cache_misses"] += 1
            misses.append((key, candidate))

    for offset in range(0, len(misses), max(1, int(batch_size))):
        batch = misses[offset:offset + max(1, int(batch_size))]
        started = time.perf_counter()
        scored, current = decider.score_candidates(
            query,
            "file_discovery_v1",
            [candidate for _, candidate in batch],
        )
        usage["model_wall_time_ms"] += (
            time.perf_counter() - started
        ) * 1000.0
        merge_usage(usage, current)

        by_id = {item["id"]: item for item in scored}
        for key, candidate in batch:
            score = float(by_id[candidate["id"]]["score"])
            cache[key] = score
            results.append({**candidate, "score": score})

    results.sort(key=lambda item: item["path"])
    return results


def run(
    root,
    query,
    decider,
    *,
    file_threshold=DEFAULT_FILE_THRESHOLD,
    relative_fallback_fraction=DEFAULT_RELATIVE_FALLBACK_FRACTION,
    transport_batch_size=DEFAULT_TRANSPORT_BATCH_SIZE,
):
    root = Path(root).resolve()
    usage = empty_usage()
    cache = {}

    started = time.perf_counter()
    candidates = enumerate_files(root)
    usage["metadata_items_seen"] = len(candidates)

    scored = score_files(
        query,
        decider,
        candidates,
        usage,
        cache,
        batch_size=transport_batch_size,
    )

    ordered = sorted(
        scored,
        key=lambda item: (-float(item["score"]), item["path"]),
    )
    fallback_fraction = max(0.0, float(relative_fallback_fraction))
    fallback_count = (
        max(1, math.ceil(len(ordered) * fallback_fraction))
        if ordered and fallback_fraction > 0.0
        else 0
    )
    fallback_cutoff = (
        float(ordered[fallback_count - 1]["score"])
        if fallback_count else None
    )

    relevant_files = []
    for item in ordered:
        absolute = float(item["score"]) >= float(file_threshold)
        relative = (
            fallback_cutoff is not None
            and float(item["score"]) >= fallback_cutoff
        )
        if not (absolute or relative):
            continue
        reasons = []
        if absolute:
            reasons.append("absolute_threshold")
        if relative:
            reasons.append("relative_recall_guard")
        relevant_files.append({
            "path": item["path"],
            "score": float(item["score"]),
            "parent_directory": item["parent"],
            "selection_reasons": reasons,
        })

    file_scores = {
        item["path"]: float(item["score"])
        for item in scored
    }
    wall_time_ms = (time.perf_counter() - started) * 1000.0

    return {
        "schema_version": 2,
        "kind": "file-discovery-v1",
        "goal": query,
        "root": str(root),
        "policy": {
            "file_threshold": float(file_threshold),
            "relative_fallback_fraction": fallback_fraction,
            "relative_fallback_cutoff": fallback_cutoff,
            "relative_fallback_min_count": fallback_count,
            "transport_batch_size": int(transport_batch_size),
            "directory_semantic_pruning": False,
            "stop_rule": "all_file_metadata_scored",
            "source_body_visible": False,
            "top_k": None,
        },
        "relevant_files": relevant_files,
        "file_scores": file_scores,
        "enumerated_file_count": len(candidates),
        "termination": "all_file_metadata_scored",
        "usage": usage,
        "wall_time_ms": wall_time_ms,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("query")
    parser.add_argument(
        "--file-threshold",
        type=float,
        default=DEFAULT_FILE_THRESHOLD,
    )
    parser.add_argument(
        "--relative-fallback-fraction",
        type=float,
        default=DEFAULT_RELATIVE_FALLBACK_FRACTION,
    )
    parser.add_argument(
        "--transport-batch-size",
        type=int,
        default=DEFAULT_TRANSPORT_BATCH_SIZE,
    )
    parser.add_argument("--trace-file")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--typesafe-endpoint",
        default=os.getenv("TYPESAFE_API_URL", API_URL),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", MODEL),
    )
    args = parser.parse_args(argv)

    key = os.getenv("TYPESAFE_API_KEY", "")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY is required")

    decider = SystemOneDecider(
        key,
        Trace(args.trace_file),
        args.typesafe_endpoint,
        args.model,
    )
    result = run(
        args.root,
        args.query,
        decider,
        file_threshold=args.file_threshold,
        relative_fallback_fraction=args.relative_fallback_fraction,
        transport_batch_size=args.transport_batch_size,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "termination": result["termination"],
        "enumerated_files": result["enumerated_file_count"],
        "relevant_files": len(result["relevant_files"]),
        "usage": result["usage"],
        "wall_time_ms": result["wall_time_ms"],
    }, indent=2))


if __name__ == "__main__":
    main()
