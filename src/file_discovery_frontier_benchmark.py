"""Workflow-only replay of uncapped metadata retrieval score thresholds."""
from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

from file_discovery_adaptive import semantic_concepts, semantic_weighted_threshold_frontier
from file_discovery_v1 import enumerate_files


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def analyze_repository(root, repository, cases, thresholds):
    candidates = enumerate_files(root)
    rows = []
    for case in cases:
        frontier = semantic_weighted_threshold_frontier(candidates, case["goal"], thresholds)
        primary = set(case["primary_files"])
        metrics = []
        for point in frontier:
            selected = set(point["paths"])
            metrics.append({
                "threshold": point["threshold"],
                "candidate_count": len(selected),
                "primary_target_count": len(primary),
                "recovered_primary_count": len(primary & selected),
                "primary_recall": len(primary & selected) / len(primary),
                "missing_primary": sorted(primary - selected),
            })
        rows.append({
            "case_id": case["id"], "repository": repository,
            "revision": case["revision"], "enumerated_file_count": len(candidates),
            "query_concept_count": len(semantic_concepts(case["goal"])),
            "frontier": metrics,
        })
    return {"schema_version": 1, "run_url": os.getenv("RUN_URL", "unknown"),
            "code_sha": os.getenv("GITHUB_SHA", "unknown"),
            "repository": repository, "enumerated_file_count": len(candidates),
            "case_count": len(rows), "thresholds": sorted(float(x) for x in thresholds),
            "model_calls": 0, "directory_model_decisions": 0, "cases": rows}


def summarize(reports, thresholds):
    cases = [case for report in reports for case in report["cases"]]
    rows = []
    for threshold in sorted(float(value) for value in thresholds):
        points = [next(point for point in case["frontier"]
                       if point["threshold"] == threshold) for case in cases]
        total_targets = sum(point["primary_target_count"] for point in points)
        recovered = sum(point["recovered_primary_count"] for point in points)
        openclaw = [point["candidate_count"] for case, point in zip(cases, points)
                    if case["repository"] == "openclaw/openclaw"]
        rows.append({
            "threshold": threshold, "case_count": len(points),
            "primary_target_count": total_targets, "recovered_primary_count": recovered,
            "primary_recall": recovered / total_targets if total_targets else 1.0,
            "mean_candidate_count": statistics.fmean(p["candidate_count"] for p in points) if points else 0,
            "max_candidate_count": max((p["candidate_count"] for p in points), default=0),
            "openclaw_mean_candidate_count": statistics.fmean(openclaw) if openclaw else None,
        })
    has_openclaw = any(row["openclaw_mean_candidate_count"] is not None for row in rows)
    passing = [row["threshold"] for row in rows
               if row["primary_recall"] == 1.0
               and row["openclaw_mean_candidate_count"] is not None
               and row["openclaw_mean_candidate_count"] < 2000]
    return {"schema_version": 1, "model_calls": 0, "directory_model_decisions": 0,
            "rows": rows, "passing_thresholds": passing,
            "decision": ("candidate frontier found" if passing else
                         "no configured threshold meets both recall and OpenClaw scale gates")
            if has_openclaw else "partial repository frontier; operational gate is reported in the aggregate"}


def render_report(payload):
    summary = payload["summary"]
    lines = ["# Uncapped Metadata Retrieval Threshold Frontier", "",
             f"- Workflow: {payload['run_url']}", f"- Code commit: `{payload['code_sha']}`",
             f"- Model calls: 0; directory model decisions: 0.",
             "- Each row is a score threshold over every concept-matching path; no top-k limit or candidate quota is applied.",
             "- Primary labels are incomplete supporting-file truth, and this diagnostic replay does not establish generalization.", "",
             "| Threshold | Primary recall | Mean candidates | Maximum candidates | OpenClaw mean candidates |",
             "| ---: | ---: | ---: | ---: | ---: |"]
    for row in summary["rows"]:
        openclaw = row["openclaw_mean_candidate_count"]
        openclaw_text = f"{openclaw:.1f}" if openclaw is not None else "—"
        lines.append(f"| {row['threshold']:g} | {row['primary_recall']:.1%} ({row['recovered_primary_count']}/{row['primary_target_count']}) | {row['mean_candidate_count']:.1f} | {row['max_candidate_count']} | {openclaw_text} |")
    lines += ["", "## Decision", "", summary["decision"], "",
              f"Thresholds meeting both the 100% primary recall and under-2,000 OpenClaw mean gates: {summary['passing_thresholds'] or 'none'}.",
              "", "## Per-Task Misses", ""]
    misses = [(case["case_id"], point["threshold"], point["missing_primary"])
              for report in payload["repository_reports"] for case in report["cases"]
              for point in case["frontier"] if point["missing_primary"]]
    if misses:
        lines.extend(f"- {case} at threshold {threshold:g}: {json.dumps(paths)}"
                     for case, threshold, paths in misses)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--repository")
    parser.add_argument("--cases", default="fixtures/file-discovery/system1-vs-system2-cases.json")
    parser.add_argument("--config", default="fixtures/file-discovery/frontier-experiment.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--aggregate")
    args = parser.parse_args()
    config = load(args.config)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.aggregate:
        reports = [load(path) for path in sorted(Path(args.aggregate).glob("**/frontier.json"))]
        payload = {"schema_version": 1, "run_url": args.run_url,
                   "code_sha": os.getenv("GITHUB_SHA", "unknown"),
                   "repository_reports": reports,
                   "summary": summarize(reports, config["thresholds"])}
        write_json(output / "frontier.json", payload)
        (output / "report.md").write_text(render_report(payload), encoding="utf-8")
        return
    cases = [case for case in load(args.cases)["cases"]
             if case["repository"] == args.repository]
    payload = analyze_repository(args.root, args.repository, cases, config["thresholds"])
    payload["run_url"] = args.run_url
    write_json(output / "frontier.json", payload)
    (output / "report.md").write_text(
        render_report({"run_url": args.run_url, "code_sha": payload["code_sha"],
                       "summary": summarize([payload], config["thresholds"]),
                       "repository_reports": [payload]}), encoding="utf-8")


if __name__ == "__main__":
    main()
