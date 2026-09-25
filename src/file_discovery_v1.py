#!/usr/bin/env python3
"""Canonical File Discovery V1.

Metadata-only hierarchical progressive disclosure:
- root expands mechanically;
- every newly disclosed directory/file is independently Noul-scored once;
- directories above threshold expose direct children;
- files above threshold become RelevantFile;
- no top-k, source reads, global model Stop, or unchanged-state rescoring.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from system_one_code_locator import (
    API_URL,
    MODEL,
    IGNORE,
    SUFFIXES,
    SystemOneDecider,
    Trace,
)

DEFAULT_DIRECTORY_THRESHOLD = 0.50
DEFAULT_FILE_THRESHOLD = 0.65
DEFAULT_TRANSPORT_BATCH_SIZE = 64
IMPLEMENTATION_SUFFIXES = {
    ".py", ".rs", ".go", ".java", ".ts", ".tsx",
    ".js", ".jsx", ".vue", ".proto", ".sql", ".sh",
}


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


def _visible_entries(path):
    try:
        return sorted(
            [
                item
                for item in path.iterdir()
                if not item.name.startswith(".")
                and item.name not in IGNORE
            ],
            key=lambda item: item.name,
        )
    except OSError:
        return []


def directory_candidate(root, path, parent):
    entries = _visible_entries(path)
    child_directories = [
        item.name for item in entries if item.is_dir()
    ]
    direct_files = [
        item.name
        for item in entries
        if item.is_file() and item.suffix.lower() in SUFFIXES
    ]
    implementation_files = [
        item.name
        for item in entries
        if item.is_file()
        and item.suffix.lower() in IMPLEMENTATION_SUFFIXES
    ]
    rel = path.relative_to(root).as_posix()
    return {
        "id": f"dir:{rel}",
        "kind": "directory",
        "path": rel,
        "parent": parent,
        "payload": {
            "kind": "directory",
            "path": rel,
            "name": path.name,
            "child_directories": child_directories[:24],
            "direct_files": direct_files[:40],
            "implementation_files": implementation_files[:40],
            "structural_container": (
                bool(child_directories) and not implementation_files
            ),
        },
    }


def file_candidate(root, path, parent):
    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = None
    rel = path.relative_to(root).as_posix()
    return {
        "id": f"file:{rel}",
        "kind": "file",
        "path": rel,
        "parent": parent,
        "payload": {
            "kind": "file",
            "path": rel,
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": size_bytes,
        },
    }


def disclose_children(root, relative_directory):
    root = Path(root).resolve()
    base = root if not relative_directory else root / relative_directory
    entries = _visible_entries(base)
    out = []
    parent = relative_directory or "."
    for path in entries:
        if path.is_dir():
            out.append(directory_candidate(root, path, parent))
        elif path.is_file() and path.suffix.lower() in SUFFIXES:
            out.append(file_candidate(root, path, parent))
    return out


def score_once(
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

    results.sort(key=lambda item: (item["kind"], item["path"]))
    return results


def run(
    root,
    query,
    decider,
    *,
    directory_threshold=DEFAULT_DIRECTORY_THRESHOLD,
    file_threshold=DEFAULT_FILE_THRESHOLD,
    transport_batch_size=DEFAULT_TRANSPORT_BATCH_SIZE,
):
    root = Path(root).resolve()
    usage = empty_usage()
    cache = {}
    node_scores = {}
    directory_status = {}
    relevant_files = []
    expanded_directories = []
    frontier = [""]

    started = time.perf_counter()

    while frontier:
        current_frontier = sorted(set(frontier))
        frontier = []
        newly_disclosed = []

        for relative_directory in current_frontier:
            expanded_directories.append(relative_directory or ".")
            children = disclose_children(root, relative_directory)
            usage["metadata_items_seen"] += len(children)
            for candidate in children:
                if candidate["id"] not in node_scores:
                    newly_disclosed.append(candidate)

        if not newly_disclosed:
            continue

        mechanical = []
        semantic = []
        for candidate in newly_disclosed:
            if (
                candidate["kind"] == "directory"
                and candidate["payload"].get("structural_container")
            ):
                mechanical.append(candidate)
            else:
                semantic.append(candidate)

        for item in mechanical:
            node_scores[item["id"]] = {
                "kind": item["kind"],
                "path": item["path"],
                "parent": item["parent"],
                "score": None,
                "decision": "mechanical_expand",
            }
            directory_status[item["path"]] = "mechanical_expand"
            frontier.append(item["path"])

        scored = score_once(
            query,
            decider,
            semantic,
            usage,
            cache,
            batch_size=transport_batch_size,
        )

        for item in scored:
            node_scores[item["id"]] = {
                "kind": item["kind"],
                "path": item["path"],
                "parent": item["parent"],
                "score": float(item["score"]),
                "decision": "semantic_score",
            }
            if item["kind"] == "directory":
                if item["score"] >= float(directory_threshold):
                    directory_status[item["path"]] = "expanded"
                    frontier.append(item["path"])
                else:
                    directory_status[item["path"]] = "pruned"
            else:
                if item["score"] >= float(file_threshold):
                    relevant_files.append({
                        "path": item["path"],
                        "score": float(item["score"]),
                        "parent_directory": item["parent"],
                    })

    relevant_files.sort(
        key=lambda item: (-item["score"], item["path"])
    )
    wall_time_ms = (time.perf_counter() - started) * 1000.0

    return {
        "schema_version": 1,
        "kind": "file-discovery-v1",
        "goal": query,
        "root": str(root),
        "policy": {
            "directory_threshold": float(directory_threshold),
            "file_threshold": float(file_threshold),
            "transport_batch_size": int(transport_batch_size),
            "structural_container_rule": (
                "mechanically expand directories with child directories "
                "and no direct implementation files"
            ),
            "stop_rule": "frontier_exhausted",
            "source_body_visible": False,
            "top_k": None,
        },
        "relevant_files": relevant_files,
        "node_scores": node_scores,
        "directory_status": directory_status,
        "expanded_directories": expanded_directories,
        "termination": "frontier_exhausted",
        "usage": usage,
        "wall_time_ms": wall_time_ms,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("query")
    parser.add_argument(
        "--directory-threshold",
        type=float,
        default=DEFAULT_DIRECTORY_THRESHOLD,
    )
    parser.add_argument(
        "--file-threshold",
        type=float,
        default=DEFAULT_FILE_THRESHOLD,
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
        directory_threshold=args.directory_threshold,
        file_threshold=args.file_threshold,
        transport_batch_size=args.transport_batch_size,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "termination": result["termination"],
        "relevant_files": len(result["relevant_files"]),
        "expanded_directories": len(result["expanded_directories"]),
        "usage": result["usage"],
        "wall_time_ms": result["wall_time_ms"],
    }, indent=2))


if __name__ == "__main__":
    main()
