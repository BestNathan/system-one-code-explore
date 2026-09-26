"""Workflow-only exact recall-safe score-threshold analysis."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from file_discovery_adaptive import semantic_weighted_primary_safe_frontier
from file_discovery_v1 import enumerate_files


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def analyze_repository(root, repository, cases):
    candidates = enumerate_files(root)
    case_state = []
    all_target_scores = []
    for case in cases:
        frontier = semantic_weighted_primary_safe_frontier(
            candidates, case["goal"], case["primary_files"])
        all_target_scores.extend(frontier["primary_scores"].values())
        case_state.append((case, frontier))
    shared_threshold = min(all_target_scores) if all_target_scores else None
    rows = []
    for case, frontier in case_state:
        score_by_path = frontier.pop("score_by_path")
        if shared_threshold is None:
            shared_candidates = set()
        else:
            shared_candidates = {path for path, score in score_by_path.items()
                                 if score >= shared_threshold}
        primary = set(case["primary_files"])
        rows.append({
            "case_id": case["id"], "repository": repository,
            "revision": case["revision"], "enumerated_file_count": len(candidates),
            "oracle_minimum": {key: value for key, value in frontier.items()
                               if key not in {"candidate_paths", "score_by_path"}},
            "repository_shared_threshold": shared_threshold,
            "repository_shared_candidate_count": len(shared_candidates),
            "repository_shared_recovered_primary_count": len(primary & shared_candidates),
            "repository_shared_primary_recall": len(primary & shared_candidates) / len(primary) if primary else 1.0,
            "repository_shared_missing_primary": sorted(primary - shared_candidates),
        })
    return {"schema_version": 1, "run_url": os.getenv("RUN_URL", "unknown"),
            "code_sha": os.getenv("GITHUB_SHA", "unknown"),
            "repository": repository, "enumerated_file_count": len(candidates),
            "case_count": len(rows), "model_calls": 0,
            "directory_model_decisions": 0,
            "repository_shared_threshold": shared_threshold, "cases": rows}


def summarize(reports):
    repos = []
    for report in reports:
        cases = report["cases"]
        target_count = sum(row["oracle_minimum"]["primary_target_count"] for row in cases)
        oracle_recovered = sum(row["oracle_minimum"]["recovered_primary_count"] for row in cases)
        shared_recovered = sum(row["repository_shared_recovered_primary_count"] for row in cases)
        repos.append({
            "repository": report["repository"], "task_count": len(cases),
            "target_count": target_count,
            "oracle_minimum_candidate_mean": sum(row["oracle_minimum"]["candidate_count"] for row in cases) / len(cases) if cases else 0,
            "oracle_minimum_primary_recall": oracle_recovered / target_count if target_count else 1.0,
            "repository_shared_threshold": report["repository_shared_threshold"],
            "repository_shared_candidate_mean": sum(row["repository_shared_candidate_count"] for row in cases) / len(cases) if cases else 0,
            "repository_shared_primary_recall": shared_recovered / target_count if target_count else 1.0,
        })
    openclaw = next((row for row in repos if row["repository"] == "openclaw/openclaw"), None)
    if openclaw is None:
        return {"repositories": repos, "openclaw_gate_passed": False,
                "decision": "OpenClaw report missing; operational conclusion unavailable"}
    gate = (openclaw["oracle_minimum_primary_recall"] == 1.0
            and openclaw["oracle_minimum_candidate_mean"] < 2000)
    return {"repositories": repos, "openclaw_gate_passed": gate,
            "openclaw_gate": {"required_primary_recall": 1.0,
                              "required_mean_candidate_count_below": 2000,
                              "oracle_minimum_candidate_mean": openclaw["oracle_minimum_candidate_mean"],
                              "oracle_minimum_primary_recall": openclaw["oracle_minimum_primary_recall"]},
            "decision": "a scalar weighted threshold can meet the OpenClaw gate" if gate else
            "even per-task oracle thresholds cannot meet the OpenClaw scale gate"}


def render_report(payload):
    summary = payload["summary"]
    lines = ["# Exact Primary-Safe Weighted Score Frontier", "",
             f"- Workflow: {payload['run_url']}", f"- Code commit: `{payload['code_sha']}`",
             "- Model calls: 0; directory model decisions: 0.",
             "- The per-task oracle threshold is the minimum target score. It yields the smallest candidate set for that task at 100% labeled primary recall.",
             "- The repository-shared threshold is the minimum primary score across all tasks in that repository.",
             "- No candidate cap, quota, or top-k selection is used.", "",
             "| Repository | Tasks | Oracle threshold mean candidates | Oracle recall | Shared threshold | Shared mean candidates | Shared recall |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in summary["repositories"]:
        threshold = row["repository_shared_threshold"]
        threshold_text = f"{threshold:.4f}" if threshold is not None else "—"
        lines.append(f"| {row['repository']} | {row['task_count']} | {row['oracle_minimum_candidate_mean']:.1f} | {row['oracle_minimum_primary_recall']:.1%} | {threshold_text} | {row['repository_shared_candidate_mean']:.1f} | {row['repository_shared_primary_recall']:.1%} |")
    lines += ["", "## Decision", "", summary["decision"], "",
              "## Per-Task Exact Counts", "",
              "| Repository | Task | Minimum target score | Minimum candidates | Recall | Shared-threshold candidates | Shared recall |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for report in payload["repository_reports"]:
        for row in report["cases"]:
            oracle = row["oracle_minimum"]
            threshold = oracle["threshold"]
            threshold_text = f"{threshold:.4f}" if threshold is not None else "no evidence"
            lines.append(f"| {row['repository']} | {row['case_id']} | {threshold_text} | {oracle['candidate_count']} | {oracle['primary_recall']:.1%} | {row['repository_shared_candidate_count']} | {row['repository_shared_primary_recall']:.1%} |")
    lines += ["", "## Missing Targets", ""]
    misses = [(row["repository"], row["case_id"], path)
              for report in payload["repository_reports"] for row in report["cases"]
              for path in row["oracle_minimum"]["missing_primary"]]
    lines.extend(f"- {repo} / {case}: `{path}`" for repo, case, path in misses)
    if not misses:
        lines.append("- None under each task's oracle threshold.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--repository")
    parser.add_argument("--cases", default="fixtures/file-discovery/system1-vs-system2-cases.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--aggregate")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.aggregate:
        reports = [load(path) for path in sorted(Path(args.aggregate).glob("**/primary-safe.json"))]
        payload = {"schema_version": 1, "run_url": args.run_url,
                   "code_sha": os.getenv("GITHUB_SHA", "unknown"),
                   "repository_reports": reports, "summary": summarize(reports)}
        write_json(output / "primary-safe.json", payload)
        (output / "report.md").write_text(render_report(payload), encoding="utf-8")
        return
    cases = [case for case in load(args.cases)["cases"]
             if case["repository"] == args.repository]
    payload = analyze_repository(args.root, args.repository, cases)
    payload["run_url"] = args.run_url
    write_json(output / "primary-safe.json", payload)
    (output / "report.md").write_text(
        f"# Primary-Safe Frontier — {args.repository}\n\n"
        f"- Workflow: {args.run_url}\n- Model calls: 0\n"
        f"- Tasks: {len(cases)}\n- Repository-wide threshold: {payload['repository_shared_threshold']}\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
