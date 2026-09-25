#!/usr/bin/env python3
"""Evaluate File Discovery V1 against a frozen primary-target case."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ancestors_for_file(path):
    parts = Path(path).parts[:-1]
    out = []
    for index in range(1, len(parts) + 1):
        out.append(Path(*parts[:index]).as_posix())
    return out


def evaluate(run, case):
    primary = case["primary_file"]
    selected = {
        item["path"]: item
        for item in run.get("relevant_files", [])
    }
    node_scores = run.get("node_scores", {})
    directory_status = run.get("directory_status", {})

    recovered = primary in selected
    failure = None

    if not recovered:
        file_node = node_scores.get(f"file:{primary}")
        if file_node is not None:
            failure = {
                "kind": "file_rejected",
                "path": primary,
                "score": float(file_node["score"]),
                "threshold": float(
                    run["policy"]["file_threshold"]
                ),
            }
        else:
            pruned = []
            for ancestor in ancestors_for_file(primary):
                if directory_status.get(ancestor) == "pruned":
                    node = node_scores.get(f"dir:{ancestor}", {})
                    pruned.append({
                        "path": ancestor,
                        "score": node.get("score"),
                    })
            if pruned:
                failure = {
                    "kind": "ancestor_pruned",
                    "first_pruned_ancestor": pruned[0],
                    "all_pruned_ancestors": pruned,
                    "threshold": float(
                        run["policy"]["directory_threshold"]
                    ),
                }
            else:
                failure = {
                    "kind": "unsupported_or_not_disclosed",
                    "path": primary,
                }

    primary_node = node_scores.get(f"file:{primary}")
    return {
        "schema_version": 1,
        "kind": "file-discovery-v1-primary-target-benchmark",
        "case_id": case["id"],
        "primary_file": primary,
        "primary_recovered": recovered,
        "primary_score": (
            float(primary_node["score"])
            if primary_node is not None else None
        ),
        "selected_file_count": len(
            run.get("relevant_files", [])
        ),
        "expanded_directory_count": len(
            run.get("expanded_directories", [])
        ),
        "scored_directory_count": sum(
            item.get("kind") == "directory"
            for item in node_scores.values()
        ),
        "scored_file_count": sum(
            item.get("kind") == "file"
            for item in node_scores.values()
        ),
        "selected_files": run.get("relevant_files", []),
        "failure": failure,
        "usage": run.get("usage", {}),
        "wall_time_ms": run.get("wall_time_ms"),
        "policy": run.get("policy"),
    }


def markdown(result):
    lines = [
        "# File Discovery V1 benchmark",
        "",
        f"- case: {result['case_id']}",
        f"- primary: {result['primary_file']}",
        f"- recovered: {result['primary_recovered']}",
        f"- primary score: {result['primary_score']}",
        f"- selected files: {result['selected_file_count']}",
        f"- expanded directories: {result['expanded_directory_count']}",
        f"- scored directories: {result['scored_directory_count']}",
        f"- scored files: {result['scored_file_count']}",
        "",
        "## Cost",
        "",
        f"- model calls: {result['usage'].get('model_calls', 0)}",
        f"- input tokens: {result['usage'].get('input_tokens', 0)}",
        f"- output tokens: {result['usage'].get('output_tokens', 0)}",
        f"- model wall ms: {result['usage'].get('model_wall_time_ms', 0):.1f}",
        f"- total wall ms: {result.get('wall_time_ms', 0):.1f}",
        f"- metadata items: {result['usage'].get('metadata_items_seen', 0)}",
    ]
    if result["failure"]:
        lines += [
            "",
            "## Failure",
            "",
            json.dumps(result["failure"], indent=2),
        ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    result = evaluate(load(args.run), load(args.case))
    Path(args.output_json).write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        markdown(result),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
