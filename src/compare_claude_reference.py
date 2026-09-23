#!/usr/bin/env python3
"""Record agreement between System One and an independent Claude Code run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def unique(items):
    return list(dict.fromkeys(items))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def claude_files(reference):
    rows = reference.get("relevant_files", [])
    return {
        item["path"]: item
        for item in rows
        if isinstance(item, dict) and item.get("path")
    }


def system_one_phase1_files(result):
    return {
        item["id"]
        for item in result.get("files", [])
        if isinstance(item, dict) and item.get("id")
    }


def system_one_evidence(result):
    by_path = {}
    for item in result.get("snippets", []):
        path = item.get("path")
        if not path:
            continue
        by_path.setdefault(path, []).append(item)
    return by_path


def ranges_overlap(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) <= min(a_end, b_end)


def reference_ranges(item):
    out = []
    for evidence in item.get("evidence", []) or []:
        try:
            start = int(evidence["start_line"])
            end = int(evidence["end_line"])
        except (KeyError, TypeError, ValueError):
            continue
        if start > 0 and end >= start:
            out.append((start, end))
    return out


def evidence_range_overlap(s1_rows, ref_item):
    refs = reference_ranges(ref_item)
    if not refs:
        return None
    for row in s1_rows:
        try:
            s_start = int(row["start_line"])
            s_end = int(row["end_line"])
        except (KeyError, TypeError, ValueError):
            continue
        if any(ranges_overlap(s_start, s_end, r_start, r_end) for r_start, r_end in refs):
            return True
    return False


def covered_reference_lines(s1_rows, ref_start, ref_end):
    intersections = []
    for row in s1_rows:
        try:
            s_start = int(row["start_line"])
            s_end = int(row["end_line"])
        except (KeyError, TypeError, ValueError):
            continue
        start = max(ref_start, s_start)
        end = min(ref_end, s_end)
        if start <= end:
            intersections.append((start, end))

    intersections.sort()
    merged = []
    for start, end in intersections:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return sum(end - start + 1 for start, end in merged)


def region_metrics(reference, evidence, relevance=None):
    total_regions = 0
    overlap_regions = 0
    total_lines = 0
    covered_lines = 0
    missed_regions = []

    for path, item in reference.items():
        if relevance is not None and item.get("relevance") != relevance:
            continue
        s1_rows = evidence.get(path, [])
        for region in item.get("evidence", []) or []:
            try:
                start = int(region["start_line"])
                end = int(region["end_line"])
            except (KeyError, TypeError, ValueError):
                continue
            if start <= 0 or end < start:
                continue

            total_regions += 1
            total_lines += end - start + 1
            covered = covered_reference_lines(s1_rows, start, end)
            covered_lines += covered
            if covered:
                overlap_regions += 1
            else:
                missed_regions.append({
                    "path": path,
                    "relevance": item.get("relevance"),
                    "start_line": start,
                    "end_line": end,
                    "description": region.get("description"),
                })

    return {
        "total_regions": total_regions,
        "overlap_regions": overlap_regions,
        "region_recall": ratio(overlap_regions, total_regions),
        "total_lines": total_lines,
        "covered_lines": covered_lines,
        "line_coverage": ratio(covered_lines, total_lines),
        "missed_regions": missed_regions,
    }


def ratio(numerator, denominator):
    return None if denominator == 0 else numerator / denominator


def compare(system_one, claude):
    ref = claude_files(claude)
    phase1 = system_one_phase1_files(system_one)
    evidence = system_one_evidence(system_one)

    ref_all = set(ref)
    ref_primary = {
        path
        for path, item in ref.items()
        if item.get("relevance") == "primary"
    }
    ref_supporting = {
        path
        for path, item in ref.items()
        if item.get("relevance") == "supporting"
    }
    evidence_paths = set(evidence)

    phase1_hit = phase1 & ref_all
    evidence_hit = evidence_paths & ref_all
    primary_phase1_hit = phase1 & ref_primary
    primary_evidence_hit = evidence_paths & ref_primary

    shared_range_status = {}
    for path in sorted(evidence_hit):
        shared_range_status[path] = evidence_range_overlap(
            evidence[path],
            ref[path],
        )

    region_all = region_metrics(ref, evidence)
    region_primary = region_metrics(ref, evidence, "primary")
    region_supporting = region_metrics(ref, evidence, "supporting")
    region_context = region_metrics(ref, evidence, "context")

    comparable_ranges = {
        path: status
        for path, status in shared_range_status.items()
        if status is not None
    }
    range_hits = sum(status is True for status in comparable_ranges.values())

    missed = sorted(ref_all - evidence_paths)
    phase1_missed = sorted(ref_all - phase1)
    s1_only = sorted(evidence_paths - ref_all)

    return {
        "reference_kind": "claude-code-system2-observation-not-ground-truth-or-target",
        "query": system_one.get("query"),
        "counts": {
            "claude_reference_files": len(ref_all),
            "claude_primary_files": len(ref_primary),
            "claude_supporting_files": len(ref_supporting),
            "system_one_phase1_files": len(phase1),
            "system_one_evidence_files": len(evidence_paths),
            "phase1_reference_hits": len(phase1_hit),
            "evidence_reference_hits": len(evidence_hit),
            "primary_phase1_hits": len(primary_phase1_hit),
            "primary_evidence_hits": len(primary_evidence_hit),
            "comparable_shared_files_with_reference_ranges": len(comparable_ranges),
            "shared_files_with_any_range_overlap": range_hits,
            "reference_evidence_regions": region_all["total_regions"],
            "reference_evidence_regions_overlapped": region_all["overlap_regions"],
            "primary_evidence_regions": region_primary["total_regions"],
            "primary_evidence_regions_overlapped": region_primary["overlap_regions"],
            "supporting_evidence_regions": region_supporting["total_regions"],
            "supporting_evidence_regions_overlapped": region_supporting["overlap_regions"],
        },
        "metrics": {
            "phase1_reference_recall": ratio(len(phase1_hit), len(ref_all)),
            "evidence_reference_recall": ratio(len(evidence_hit), len(ref_all)),
            "primary_phase1_recall": ratio(len(primary_phase1_hit), len(ref_primary)),
            "primary_evidence_recall": ratio(len(primary_evidence_hit), len(ref_primary)),
            "evidence_reference_precision_proxy": ratio(len(evidence_hit), len(evidence_paths)),
            "shared_file_range_overlap_rate": ratio(range_hits, len(comparable_ranges)),
            "reference_evidence_region_recall": region_all["region_recall"],
            "primary_evidence_region_recall": region_primary["region_recall"],
            "supporting_evidence_region_recall": region_supporting["region_recall"],
            "context_evidence_region_recall": region_context["region_recall"],
            "reference_evidence_line_coverage": region_all["line_coverage"],
            "primary_evidence_line_coverage": region_primary["line_coverage"],
            "supporting_evidence_line_coverage": region_supporting["line_coverage"],
            "context_evidence_line_coverage": region_context["line_coverage"],
        },
        "agreement": {
            "phase1_and_claude": sorted(phase1_hit),
            "evidence_and_claude": sorted(evidence_hit),
            "claude_missed_by_phase1": phase1_missed,
            "claude_missed_by_evidence": missed,
            "system_one_evidence_not_in_claude_reference": s1_only,
            "shared_file_range_overlap": shared_range_status,
            "missed_reference_regions": region_all["missed_regions"],
        },
        "claude_reference": {
            path: {
                "relevance": item.get("relevance"),
                "reason": item.get("reason"),
                "evidence": item.get("evidence", []),
            }
            for path, item in sorted(ref.items())
        },
        "system_one_evidence": {
            path: [
                {
                    "start_line": item.get("start_line"),
                    "end_line": item.get("end_line"),
                    "score": item.get("score"),
                }
                for item in rows
            ]
            for path, rows in sorted(evidence.items())
        },
    }


def markdown(report):
    c = report["counts"]
    m = report["metrics"]
    a = report["agreement"]

    def pct(value):
        return "n/a" if value is None else f"{value * 100:.1f}%"

    lines = [
        "# System One / Claude Code localization record",
        "",
        "> Claude Code is a separate System 2 execution record, not ground truth or an optimization target.",
        "",
        "## Metrics",
        "",
        f"- Claude reference files: {c['claude_reference_files']} "
        f"(primary: {c['claude_primary_files']}, supporting: {c['claude_supporting_files']})",
        f"- System One Phase-1 files: {c['system_one_phase1_files']}",
        f"- System One evidence files: {c['system_one_evidence_files']}",
        f"- Phase-1 reference recall: {pct(m['phase1_reference_recall'])}",
        f"- Final-evidence reference recall: {pct(m['evidence_reference_recall'])}",
        f"- Primary-file Phase-1 recall: {pct(m['primary_phase1_recall'])}",
        f"- Primary-file final-evidence recall: {pct(m['primary_evidence_recall'])}",
        f"- Evidence precision proxy vs reference: {pct(m['evidence_reference_precision_proxy'])}",
        f"- Shared-file any-range overlap rate: {pct(m['shared_file_range_overlap_rate'])}",
        f"- Claude evidence-region recall: {pct(m['reference_evidence_region_recall'])}",
        f"- Primary evidence-region recall: {pct(m['primary_evidence_region_recall'])}",
        f"- Supporting evidence-region recall: {pct(m['supporting_evidence_region_recall'])}",
        f"- Claude evidence line coverage: {pct(m['reference_evidence_line_coverage'])}",
        f"- Primary evidence line coverage: {pct(m['primary_evidence_line_coverage'])}",
        f"- Supporting evidence line coverage: {pct(m['supporting_evidence_line_coverage'])}",
        "",
        "## Claude reference files missed by final System One evidence",
        "",
    ]
    lines += [f"- `{path}`" for path in a["claude_missed_by_evidence"]] or ["- None"]
    lines += [
        "",
        "## System One evidence files absent from Claude reference",
        "",
    ]
    lines += [
        f"- `{path}`"
        for path in a["system_one_evidence_not_in_claude_reference"]
    ] or ["- None"]
    lines += [
        "",
        "## Shared files",
        "",
    ]
    lines += [f"- `{path}`" for path in a["evidence_and_claude"]] or ["- None"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--system-one", required=True)
    parser.add_argument("--claude", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    report = compare(load(args.system_one), load(args.claude))
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
