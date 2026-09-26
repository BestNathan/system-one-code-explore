"""Workflow-only leave-one-task-out validation for metadata thresholds."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from file_discovery_adaptive import semantic_weighted_evidence
from file_discovery_v1 import enumerate_files


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def leave_one_out_threshold_predictions(cases):
    predictions = []
    for held_out in cases:
        training = [case for case in cases
                    if case["repository"] == held_out["repository"]
                    and case["case_id"] != held_out["case_id"]]
        training_scores = [score for case in training
                          for score in case["primary_scores"].values()]
        threshold = min(training_scores) if training_scores else None
        score_by_path = held_out["score_by_path"]
        primary = set(held_out.get("primary_paths", held_out["primary_scores"].keys()))
        selected = ({path for path, score in score_by_path.items() if score >= threshold}
                    if threshold is not None else set())
        recovered = primary & selected
        predictions.append({
            "case_id": held_out["case_id"], "repository": held_out["repository"],
            "training_case_ids": sorted(case["case_id"] for case in training),
            "threshold": threshold,
            "candidate_count": len(selected),
            "primary_target_count": len(primary),
            "recovered_primary_count": len(recovered),
            "primary_recall": len(recovered) / len(primary) if primary else 1.0,
            "missing_primary": sorted(primary - recovered),
        })
    return predictions


def analyze_repository(root, repository, cases):
    candidates = enumerate_files(root)
    records = []
    for case in cases:
        evidence = semantic_weighted_evidence(candidates, case["goal"], include_ineligible=True)
        records.append({
            "case_id": case["id"], "repository": repository,
            "primary_paths": sorted(case["primary_files"]),
            "primary_scores": {path: evidence[path]["weighted_score"]
                               for path in case["primary_files"] if path in evidence},
            "score_by_path": {path: item["weighted_score"] for path, item in evidence.items()},
        })
    rows = leave_one_out_threshold_predictions(records)
    return {"schema_version": 1, "run_url": os.getenv("RUN_URL", "unknown"),
            "code_sha": os.getenv("GITHUB_SHA", "unknown"),
            "repository": repository, "enumerated_file_count": len(candidates),
            "model_calls": 0, "directory_model_decisions": 0, "cases": rows}


def summarize(reports):
    repositories = []
    for report in reports:
        cases = report["cases"]
        targets = sum(row["primary_target_count"] for row in cases)
        recovered = sum(row["recovered_primary_count"] for row in cases)
        repositories.append({
            "repository": report["repository"], "task_count": len(cases),
            "target_count": targets,
            "primary_recall": recovered / targets if targets else 1.0,
            "mean_candidate_count": sum(row["candidate_count"] for row in cases) / len(cases) if cases else 0,
        })
    openclaw = next((row for row in repositories
                     if row["repository"] == "openclaw/openclaw"), None)
    passed = bool(openclaw and openclaw["primary_recall"] == 1.0
                  and openclaw["mean_candidate_count"] < 2000)
    return {"repositories": repositories, "openclaw_gate_passed": passed,
            "decision": "leave-one-task-out calibration meets both OpenClaw gates" if passed else
            "leave-one-task-out calibration does not meet both OpenClaw gates"}


def render_report(payload):
    summary = payload["summary"]
    lines = ["# Leave-One-Task-Out Weighted Threshold Validation", "",
             f"- Workflow: {payload['run_url']}", f"- Code commit: `{payload['code_sha']}`",
             "- Model calls: 0; directory model decisions: 0.",
             "- Each threshold is the minimum primary score from the other two tasks in the same repository.",
             "- The held-out task's labels do not participate in its threshold.",
             "- No candidate cap, quota, or top-k selection is used.", "",
             "| Repository | Held-out tasks | Primary recall | Mean candidates |",
             "| --- | ---: | ---: | ---: |"]
    for row in summary["repositories"]:
        lines.append(f"| {row['repository']} | {row['task_count']} | {row['primary_recall']:.1%} ({sum(c['recovered_primary_count'] for r in payload['repository_reports'] if r['repository']==row['repository'] for c in r['cases'])}/{row['target_count']}) | {row['mean_candidate_count']:.1f} |")
    lines += ["", "## Per-Task Predictions", "",
              "| Repository | Held-out task | Training tasks | Threshold | Candidates | Recall | Misses |",
              "| --- | --- | --- | ---: | ---: | ---: | --- |"]
    misses = []
    for report in payload["repository_reports"]:
        for case in report["cases"]:
            threshold = case["threshold"]
            threshold_text = f"{threshold:.4f}" if threshold is not None else "no training score"
            lines.append(f"| {case['repository']} | {case['case_id']} | {', '.join(case['training_case_ids'])} | {threshold_text} | {case['candidate_count']} | {case['primary_recall']:.1%} | {len(case['missing_primary'])} |")
            misses.extend((case["repository"], case["case_id"], path)
                          for path in case["missing_primary"])
    lines += ["", "## Decision", "", summary["decision"], "", "## Missed Targets", ""]
    if misses:
        lines.extend(f"- {repository} / {case}: `{path}`" for repository, case, path in misses)
    else:
        lines.append("- None.")
    lines += ["", "These are three-task leave-one-out diagnostics per repository, not a fresh holdout suite.", ""]
    return "\n".join(lines)


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
        reports = [load(path) for path in sorted(Path(args.aggregate).glob("**/predictions.json"))]
        payload = {"schema_version": 1, "run_url": args.run_url,
                   "code_sha": os.getenv("GITHUB_SHA", "unknown"),
                   "repository_reports": reports, "summary": summarize(reports)}
        write_json(output / "predictions.json", payload)
        (output / "report.md").write_text(render_report(payload), encoding="utf-8")
        return
    cases = [case for case in load(args.cases)["cases"]
             if case["repository"] == args.repository]
    payload = analyze_repository(args.root, args.repository, cases)
    payload["run_url"] = args.run_url
    write_json(output / "predictions.json", payload)
    (output / "report.md").write_text(
        f"# Leave-One-Out Predictions — {args.repository}\n\n"
        f"- Workflow: {args.run_url}\n- Model calls: 0\n- Held-out tasks: {len(cases)}\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
