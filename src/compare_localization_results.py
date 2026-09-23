#!/usr/bin/env python3
"""Compare two canonical code-localization results without treating either as truth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ratio(num, den):
    return None if den == 0 else num / den


def subject_identity(result, side):
    subject = result.get("subject")
    if not isinstance(subject, dict):
        raise ValueError(
            f"{side} localization result is missing canonical subject identity"
        )
    repository = subject.get("repository")
    revision = subject.get("revision")
    if not repository or not revision:
        raise ValueError(
            f"{side} localization subject requires repository and revision"
        )
    return {
        "repository": str(repository),
        "revision": str(revision),
    }


def require_same_subject(left, right):
    left_subject = subject_identity(left, "left")
    right_subject = subject_identity(right, "right")
    if left_subject != right_subject:
        raise ValueError(
            "cannot compare localization results from different subjects: "
            f"left={left_subject} right={right_subject}"
        )
    return left_subject


def ranges_overlap(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) <= min(a_end, b_end)


def merge_ranges(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def covered_lines(target, covering):
    intersections = []
    for t_start, t_end in target:
        for c_start, c_end in covering:
            start = max(t_start, c_start)
            end = min(t_end, c_end)
            if start <= end:
                intersections.append((start, end))
    return sum(end - start + 1 for start, end in merge_ranges(intersections))


def evidence_ranges(file_item):
    return [
        (int(item["start_line"]), int(item["end_line"]))
        for item in file_item.get("evidence", [])
    ]


def file_map(result):
    return {
        item["path"]: item
        for item in result.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }


def cost_summary(result):
    cost = result.get("cost") or {}
    tokens = cost.get("tokens") or {}
    return {
        "elapsed_ms": cost.get("elapsed_ms"),
        "model_calls": cost.get("model_calls"),
        "turns": cost.get("turns"),
        "tool_calls": cost.get("tool_calls"),
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "cache_read_input_tokens": tokens.get("cache_read_input"),
        "cache_creation_input_tokens": tokens.get(
            "cache_creation_input"
        ),
        "thinking_tokens": tokens.get("thinking"),
        "provider_cost_usd": cost.get("provider_cost_usd"),
        "stages": cost.get("stages", []),
    }


def confidence_score(value):
    if not isinstance(value, dict):
        return None
    score = value.get("score")
    return None if score is None else float(score)


def directional_region_coverage(source_files, target_files):
    """How much of source's evidence is overlapped by target evidence."""
    regions = 0
    hit_regions = 0
    lines = 0
    hit_lines = 0
    misses = []

    for path, source in source_files.items():
        target = target_files.get(path)
        target_ranges = evidence_ranges(target) if target else []
        for evidence in source.get("evidence", []):
            start = int(evidence["start_line"])
            end = int(evidence["end_line"])
            regions += 1
            lines += end - start + 1
            covered = covered_lines([(start, end)], target_ranges)
            hit_lines += covered
            if covered:
                hit_regions += 1
            else:
                misses.append({
                    "path": path,
                    "start_line": start,
                    "end_line": end,
                    "reason": evidence.get("reason"),
                    "confidence": evidence.get("confidence"),
                })

    return {
        "regions": regions,
        "overlapped_regions": hit_regions,
        "region_overlap_rate": ratio(hit_regions, regions),
        "lines": lines,
        "overlapped_lines": hit_lines,
        "line_overlap_rate": ratio(hit_lines, lines),
        "missed_regions": misses,
    }


def compare(left, right):
    subject = require_same_subject(left, right)
    left_files = file_map(left)
    right_files = file_map(right)
    left_paths = set(left_files)
    right_paths = set(right_files)
    shared = sorted(left_paths & right_paths)

    role_differences = []
    confidence_pairs = []
    evidence_pairs = []

    for path in shared:
        l = left_files[path]
        r = right_files[path]
        if l.get("role") != r.get("role"):
            role_differences.append({
                "path": path,
                "left_role": l.get("role"),
                "right_role": r.get("role"),
            })

        confidence_pairs.append({
            "path": path,
            "left": l.get("confidence"),
            "right": r.get("confidence"),
            "left_score": confidence_score(l.get("confidence")),
            "right_score": confidence_score(r.get("confidence")),
        })

        l_ranges = evidence_ranges(l)
        r_ranges = evidence_ranges(r)
        evidence_pairs.append({
            "path": path,
            "left_regions": len(l_ranges),
            "right_regions": len(r_ranges),
            "has_any_overlap": any(
                ranges_overlap(a, b, c, d)
                for a, b in l_ranges
                for c, d in r_ranges
            ),
        })

    left_by_right = directional_region_coverage(left_files, right_files)
    right_by_left = directional_region_coverage(right_files, left_files)

    return {
        "schema_version": 1,
        "kind": "code-localization-comparison",
        "task": left.get("task") or right.get("task"),
        "subject": subject,
        "interpretation": (
            "Symmetric observational comparison. Neither side is treated as "
            "ground truth and confidence scores may have different semantics."
        ),
        "left": {
            "producer": left.get("producer"),
            "file_count": len(left_paths),
            "evidence_regions": sum(
                len(item.get("evidence", []))
                for item in left_files.values()
            ),
            "cost": cost_summary(left),
        },
        "right": {
            "producer": right.get("producer"),
            "file_count": len(right_paths),
            "evidence_regions": sum(
                len(item.get("evidence", []))
                for item in right_files.values()
            ),
            "cost": cost_summary(right),
        },
        "files": {
            "shared": shared,
            "left_only": sorted(left_paths - right_paths),
            "right_only": sorted(right_paths - left_paths),
            "intersection_count": len(shared),
            "union_count": len(left_paths | right_paths),
            "jaccard": ratio(
                len(shared),
                len(left_paths | right_paths),
            ),
            "role_differences": role_differences,
            "confidence_pairs": confidence_pairs,
        },
        "evidence": {
            "shared_file_pairs": evidence_pairs,
            "left_covered_by_right": left_by_right,
            "right_covered_by_left": right_by_left,
        },
    }


def pct(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def markdown(report):
    files = report["files"]
    evidence = report["evidence"]
    l = evidence["left_covered_by_right"]
    r = evidence["right_covered_by_left"]

    left_cost = report["left"]["cost"]
    right_cost = report["right"]["cost"]

    lines = [
        "# Localization result comparison",
        "",
        "> Symmetric observation only. Neither side is ground truth.",
        "",
        "## Cost record",
        "",
        f"- Left elapsed ms: {left_cost['elapsed_ms']}",
        f"- Right elapsed ms: {right_cost['elapsed_ms']}",
        f"- Left model calls: {left_cost['model_calls']}",
        f"- Right model calls: {right_cost['model_calls']}",
        f"- Left turns: {left_cost['turns']}",
        f"- Right turns: {right_cost['turns']}",
        f"- Left tool calls: {left_cost['tool_calls']}",
        f"- Right tool calls: {right_cost['tool_calls']}",
        f"- Left input tokens: {left_cost['input_tokens']}",
        f"- Right input tokens: {right_cost['input_tokens']}",
        f"- Left output tokens: {left_cost['output_tokens']}",
        f"- Right output tokens: {right_cost['output_tokens']}",
        f"- Left cache-read tokens: {left_cost['cache_read_input_tokens']}",
        f"- Right cache-read tokens: {right_cost['cache_read_input_tokens']}",
        f"- Left provider cost USD: {left_cost['provider_cost_usd']}",
        f"- Right provider cost USD: {right_cost['provider_cost_usd']}",
        "",
        "## File sets",
        "",
        f"- Shared files: {files['intersection_count']}",
        f"- Union files: {files['union_count']}",
        f"- File-set Jaccard: {pct(files['jaccard'])}",
        f"- Left only: {len(files['left_only'])}",
        f"- Right only: {len(files['right_only'])}",
        "",
        "## Evidence overlap",
        "",
        f"- Left regions overlapped by right: {pct(l['region_overlap_rate'])}",
        f"- Left evidence lines overlapped by right: {pct(l['line_overlap_rate'])}",
        f"- Right regions overlapped by left: {pct(r['region_overlap_rate'])}",
        f"- Right evidence lines overlapped by left: {pct(r['line_overlap_rate'])}",
        "",
        "## Shared files",
        "",
    ]
    lines += [f"- `{path}`" for path in files["shared"]] or ["- None"]
    lines += ["", "## Left-only files", ""]
    lines += [f"- `{path}`" for path in files["left_only"]] or ["- None"]
    lines += ["", "## Right-only files", ""]
    lines += [f"- `{path}`" for path in files["right_only"]] or ["- None"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    report = compare(load(args.left), load(args.right))
    Path(args.output_json).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        markdown(report),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
