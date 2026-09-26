#!/usr/bin/env python3
"""Progressive repository disclosure with durable, non-pruned deferred nodes."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from file_discovery_adaptive import semantic_weighted_evidence
from file_discovery_profiles import ProfiledFileDiscoveryDecider
from file_discovery_scoring import BatchScorer, LockedTrace, write_call_dataset
from file_discovery_v1 import IGNORE, SUFFIXES, enumerate_files
from model_pricing import jev_cost_record
from system_one_code_locator import API_URL, MODEL

EXPANSION_THRESHOLD = 0.55
FILE_THRESHOLD = 0.65
WORKERS = 4
BATCH_SIZE = 64


def _eligible_entry(entry):
    name = entry.name
    if name.startswith(".") or name in IGNORE:
        return False
    try:
        if entry.is_dir(follow_symlinks=False):
            return True
        return entry.is_file(follow_symlinks=True) and Path(name).suffix.lower() in SUFFIXES
    except OSError:
        return False


def direct_children(root, relative):
    """Read metadata for exactly one directory level; never read file bodies."""
    absolute = root if relative == "." else root / relative
    result = []
    with os.scandir(absolute) as entries:
        for entry in sorted(entries, key=lambda item: item.name):
            if not _eligible_entry(entry):
                continue
            path = entry.name if relative == "." else f"{relative}/{entry.name}"
            if entry.is_dir(follow_symlinks=False):
                with os.scandir(entry.path) as grandchildren:
                    summary = {"direct_entry_count": sum(1 for item in grandchildren if _eligible_entry(item))}
                result.append({"id": f"directory:{path}", "kind": "directory", "path": path,
                               "metadata_count": summary["direct_entry_count"],
                               "payload": {"kind": "directory", "path": path, **summary}})
            else:
                try:
                    size = entry.stat(follow_symlinks=True).st_size
                except OSError:
                    continue
                result.append({"id": f"file:{path}", "kind": "file", "path": path,
                               "payload": {"kind": "file", "path": path,
                                           "parent": relative,
                                           "filename": entry.name,
                                           "extension": Path(entry.name).suffix.lower(),
                                           "size_bytes": size}})
    return result


class ProgressiveDecider(ProfiledFileDiscoveryDecider):
    def score_candidates(self, query, stage, candidates):
        if stage == "file":
            return super().score_candidates(query, "file_discovery_v1", candidates)
        questions = {}
        for i, candidate in enumerate(candidates):
            for key, question in (
                ("relevance", "How likely is this directory to contain any material implementation or necessary supporting file for the task? Judge existence, not average relevance."),
                ("uncertainty", "How likely is it that relevant descendants remain hidden and expanding this directory would materially reduce that uncertainty? A generic directory name alone is not enough."),
            ):
                questions[f"{key}_{i}"] = {
                    "type": "noul",
                    "instructions": {"directory": candidate["payload"], "question": question},
                    "criteria": {"true": "Task-specific evidence supports this judgment.",
                                 "false": "The visible metadata gives little task-specific support."},
                }
        response, usage = self.send("progressive_repository_directory", {
            "goal": query, "phase": "repository_progressive_disclosure",
            "source_visible": False,
            "contract": "Only direct-child metadata is exposed after expansion. Low-scoring directories remain deferred and reachable; never prune descendants based on an ancestor score.",
        }, questions)
        answers = response.get("answers", {})
        result = []
        for i, candidate in enumerate(candidates):
            rel, unc = answers.get(f"relevance_{i}", {}), answers.get(f"uncertainty_{i}", {})
            if rel.get("type") != "noul" or unc.get("type") != "noul":
                raise ValueError(f"missing directory judgments for {candidate['id']}")
            result.append({**candidate, "score": float(rel["noul"]),
                           "uncertainty": float(unc["noul"])})
        return result, usage


def _score(scorer, stage, candidates):
    if not candidates:
        return []
    return scorer.score(stage, candidates)


def progressive(root, query, scorer, *, expansion_threshold=EXPANSION_THRESHOLD,
                file_threshold=FILE_THRESHOLD, checkpoint=None):
    root = Path(root).resolve()
    started = time.perf_counter()
    visible, dirs_to_expand = direct_children(root, "."), {"."}
    scored_dirs, deferred, promoted = {}, {}, {}
    scored_files, steps, metadata_seen = {}, 0, len(visible)
    max_live = len(visible)
    while dirs_to_expand:
        wave = sorted(dirs_to_expand)
        dirs_to_expand = set()
        newly_visible = []
        wave_metadata_count = 0
        for parent in wave:
            # The directory itself is already visible; expansion reveals its direct children.
            children = direct_children(root, parent)
            newly_visible.extend(children)
            wave_metadata_count += len(children) + sum(node.get("metadata_count", 0) for node in children)
        metadata_seen += wave_metadata_count
        max_live = max(max_live, len(newly_visible))
        dirs = [node for node in newly_visible if node["kind"] == "directory"]
        files = [node for node in newly_visible if node["kind"] == "file"]
        for node in _score(scorer, "route", dirs):
            scored_dirs[node["path"]] = node
            if max(node["score"], node["uncertainty"]) >= expansion_threshold:
                dirs_to_expand.add(node["path"])
                deferred.pop(node["path"], None)
            else:
                deferred[node["path"]] = {"path": node["path"], "score": node["score"],
                                           "uncertainty": node["uncertainty"],
                                           "status": "deferred_unresolved"}
        for node in _score(scorer, "file", files):
            scored_files[node["path"]] = node
            if node["score"] >= file_threshold:
                promoted[node["path"]] = node
        steps += 1
        if checkpoint is not None:
            checkpoint({"step": steps, "expanded_directories": sorted(set(scored_dirs) - set(deferred)),
                        "deferred_unresolved": sorted(deferred.values(), key=lambda item: item["path"]),
                        "next_expansion_queue": sorted(dirs_to_expand),
                        "promoted_files": sorted(promoted),
                        "directory_decisions": len(scored_dirs),
                        "file_decisions": len(scored_files),
                        "metadata_nodes_seen": metadata_seen,
                        "status": "running" if dirs_to_expand else "scheduler_exhausted"})
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "algorithm": "progressive_repository_state_machine",
        "policy": {"expansion_threshold": expansion_threshold, "file_threshold": file_threshold,
                   "workers": WORKERS, "batch_size": BATCH_SIZE,
                   "hard_candidate_cap": None, "ancestor_pruning": False},
        "metadata_nodes_seen": metadata_seen, "directory_decisions": len(scored_dirs),
        "file_decisions": len(scored_files), "model_visible_nodes": len(scored_dirs) + len(scored_files),
        "expanded_directories": sorted(set(scored_dirs) - set(deferred)),
        "deferred_unresolved": sorted(deferred.values(), key=lambda item: item["path"]),
        "promoted_files": sorted(({"path": p, "score": item["score"]} for p, item in promoted.items()),
                                 key=lambda item: (-item["score"], item["path"])),
        "file_scores": {p: item["score"] for p, item in scored_files.items()},
        "step_count": steps, "max_live_wave_nodes": max_live, "wall_time_ms": elapsed,
        "completion": "scheduler_exhausted; deferred nodes remain unresolved",
    }


def flat_path_baseline(root, query, scorer):
    candidates = enumerate_files(root)
    matched = semantic_weighted_evidence(candidates, query)
    selected = set(matched)
    subset = [candidate for candidate in candidates if candidate["path"] in selected]
    scored = _score(scorer, "file", subset)
    promoted = [item for item in scored if item["score"] >= FILE_THRESHOLD]
    return {"algorithm": "uncapped_semantic_weighted_path_then_file_score",
            "policy": {"file_threshold": FILE_THRESHOLD, "hard_candidate_cap": None},
            "enumerated_file_count": len(candidates), "candidate_file_count": len(subset),
            "file_decisions": len(scored), "directory_decisions": 0,
            "model_visible_nodes": len(scored),
            "promoted_files": sorted(({"path": item["path"], "score": item["score"]}
                                       for item in promoted), key=lambda item: (-item["score"], item["path"])),
            "file_scores": {item["path"]: item["score"] for item in scored}}


def run_case(args):
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    cases = [case for case in cases if case["repository"] == args.repository]
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        for arm in ("flat_path", "progressive"):
            folder = output / case["id"] / arm
            folder.mkdir(parents=True, exist_ok=True)
            trace = LockedTrace(folder / "trace.jsonl")
            decider = ProgressiveDecider(os.environ["TYPESAFE_API_KEY"], trace,
                                         profile="compact_state_v4", repository_context={},
                                         endpoint=os.getenv("TYPESAFE_API_URL", API_URL),
                                         model=os.getenv("TYPESAFE_MODEL", MODEL))
            scorer = BatchScorer(case["goal"], decider, workers=WORKERS, batch_size=BATCH_SIZE)
            started = time.perf_counter()
            try:
                result = (flat_path_baseline(args.root, case["goal"], scorer) if arm == "flat_path"
                          else progressive(args.root, case["goal"], scorer,
                                           expansion_threshold=config["expansion_threshold"],
                                           file_threshold=config["file_threshold"],
                                           checkpoint=lambda state: (folder / "state.json").write_text(
                                               json.dumps(state, indent=2) + "\n", encoding="utf-8")))
                selected = {item["path"] for item in result["promoted_files"]}
                primary = set(case["primary_files"])
                scored = set(result["file_scores"])
                missing = primary - selected
                causes = {}
                for path in sorted(missing):
                    if path in scored:
                        causes[path] = "file_score_rejected"
                    elif arm == "flat_path":
                        causes[path] = "path_retrieval_omission"
                    else:
                        ancestors = [node["path"] for node in result["deferred_unresolved"]
                                     if path.startswith(node["path"].rstrip("/") + "/")]
                        causes[path] = ("deferred_frontier_miss: " + max(ancestors, key=len)
                                        if ancestors else "unvisited_without_deferred_ancestor")
                row = {"case_id": case["id"], "repository": args.repository,
                       "arm": arm, "status": "success", **result,
                       "primary_recall": len(primary & selected) / len(primary),
                       "candidate_recall": len(primary & scored) / len(primary),
                       "missing_primary": sorted(missing), "missing_primary_causes": causes,
                       "primary_scores": {path: result["file_scores"].get(path) for path in sorted(primary)},
                       "usage": scorer.usage}
            except Exception as exc:
                row = {"case_id": case["id"], "repository": args.repository, "arm": arm,
                       "status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:1000]}",
                       "usage": scorer.usage}
            finally:
                row["wall_time_ms"] = (time.perf_counter() - started) * 1000
                row["physical_usage"] = {"model_calls": trace.response_count,
                                         "input_tokens": trace.input_tokens,
                                         "output_tokens": trace.output_tokens,
                                         "http_attempts": trace.requests + trace.retries,
                                         "retry_events": trace.retries,
                                         "max_request_bytes": trace.max_request_bytes}
                row["pricing"] = jev_cost_record(trace.input_tokens, trace.output_tokens)
                row["call_data"] = write_call_dataset(folder / "trace.jsonl",
                                                       folder / "raw-model-calls.jsonl",
                                                       folder / "call-manifest.json")
                (folder / "result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
            rows.append(row)
            (output / "progress.json").write_text(json.dumps({"repository": args.repository,
                "completed": len(rows), "expected": len(cases) * 2, "rows": rows}, indent=2) + "\n",
                encoding="utf-8")
            (output / "report.md").write_text(render_report({"run_url": args.run_url,
                "repository": args.repository, "rows": rows}), encoding="utf-8")
    inventory_count = len(enumerate_files(args.root))
    for row in rows:
        row["total_repository_file_count"] = inventory_count
    (output / "progress.json").write_text(json.dumps({"repository": args.repository,
        "completed": len(rows), "expected": len(cases) * 2, "rows": rows}, indent=2) + "\n",
        encoding="utf-8")
    (output / "report.md").write_text(render_report({"run_url": args.run_url,
        "repository": args.repository, "rows": rows}), encoding="utf-8")
    return rows


def render_report(payload):
    lines = ["# Issue 13 — Progressive Repository State Machine", "",
             f"- Workflow: {payload['run_url']}",
             *([f"- Report aggregation run: {payload['report_run_url']}"] if payload.get("report_run_url") else []),
             f"- Repository: `{payload.get('repository', 'aggregate')}`",
             "- Deferred directories remain unresolved state; scheduler exhaustion is not semantic completion.",
             "- No fixed candidate cap or ancestor-score pruning is used.", "",
             "| Case | Arm | Status | Primary recall | Candidate recall | Total files | Files scored | Directory decisions | Model-visible nodes | Unresolved dirs | Input tokens | Calls | Wall seconds |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in payload["rows"]:
        if row.get("status") != "success":
            lines.append(f"| {row.get('case_id')} | {row.get('arm')} | {row.get('status')}: {str(row.get('error', 'missing'))[:120]} | — | — | — | — | — | — | — | — | — | — |")
            continue
        usage = row.get("physical_usage", {})
        unresolved = len(row.get("deferred_unresolved", []))
        lines.append(f"| {row['case_id']} | {row['arm']} | success | {row['primary_recall']:.0%} | {row['candidate_recall']:.0%} | {row.get('total_repository_file_count', '—')} | {row['file_decisions']} | {row.get('directory_decisions', 0)} | {row['model_visible_nodes']} | {unresolved} | {usage.get('input_tokens', 0)} | {usage.get('model_calls', 0)} | {row['wall_time_ms']/1000:.1f} |")
    lines += ["", "## Omitted Primary Targets", ""]
    misses = [row for row in payload["rows"] if row.get("status") == "success" and row.get("missing_primary")]
    lines.extend([f"- {row['case_id']} / {row['arm']}: " + "; ".join(
        f"{path} ({row.get('missing_primary_causes', {}).get(path, 'unclassified')})"
        for path in row["missing_primary"]) for row in misses]
                 or ["- None among successful task arms."])
    lines += ["", "## Methodology Notes", "",
              "- The flat/path and progressive arms are full-policy comparisons. System One decisions are not counterfactually shared across different batch states; interpret recall differences together with this decision-noise limitation.",
              "- The nine primary targets are diagnostic labels, not complete supporting-file ground truth.",
              "- A deferred node is retained in the final state and may be revisited by a future scheduler event; this run stops when no visible directory exceeds either expansion threshold.", ""]
    if payload.get("state_size_summary"):
        summary = payload["state_size_summary"]
        lines += ["## State-Size Distribution", "",
                  f"- p50 model-visible nodes: {summary['p50_model_visible_nodes']}",
                  f"- p95 model-visible nodes: {summary['p95_model_visible_nodes']}",
                  f"- maximum model-visible nodes: {summary['max_model_visible_nodes']}", ""]
    groups = sorted({(row.get("repository", "unknown"), row.get("arm", "unknown")) for row in payload["rows"]})
    lines += ["## Repository and Arm Summary", "",
              "| Repository | Arm | Completed | Mean primary recall | Mean files scored | Mean directories | Mean visible nodes | Mean input tokens |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for repository, arm in groups:
        group = [row for row in payload["rows"] if row.get("repository") == repository and row.get("arm") == arm]
        done = [row for row in group if row.get("status") == "success"]
        if not done:
            lines.append(f"| {repository} | {arm} | 0/{len(group)} | — | — | — | — | — |")
            continue
        mean = lambda key: sum(float(row.get(key, 0)) for row in done) / len(done)
        tokens = sum(float(row.get("physical_usage", {}).get("input_tokens", 0)) for row in done) / len(done)
        lines.append(f"| {repository} | {arm} | {len(done)}/{len(group)} | {mean('primary_recall'):.1%} | {mean('file_decisions'):.1f} | {mean('directory_decisions'):.1f} | {mean('model_visible_nodes'):.1f} | {tokens:.0f} |")
    lines.append("")
    return "\n".join(lines)


def aggregate(args):
    root = Path(args.aggregate)
    reports = [json.loads(path.read_text(encoding="utf-8"))
               for path in sorted(root.glob("**/progress.json"))]
    rows = [row for report in reports for row in report.get("rows", [])]
    for row in rows:
        if row.get("status") != "success" or not row.get("missing_primary"):
            continue
        causes = row.setdefault("missing_primary_causes", {})
        for path in row["missing_primary"]:
            if path in row.get("file_scores", {}):
                causes[path] = "file_score_rejected"
            elif row.get("arm") == "flat_path":
                causes[path] = "path_retrieval_omission"
            else:
                ancestors = [node["path"] for node in row.get("deferred_unresolved", [])
                             if path.startswith(node["path"].rstrip("/") + "/")]
                causes[path] = ("deferred_frontier_miss: " + max(ancestors, key=len)
                                if ancestors else "unvisited_without_deferred_ancestor")
    expected = 18
    seen = {(row.get("case_id"), row.get("arm")) for row in rows}
    for case in json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]:
        for arm in ("flat_path", "progressive"):
            if (case["id"], arm) not in seen:
                rows.append({"case_id": case["id"], "repository": case["repository"],
                             "arm": arm, "status": "missing", "error": "repository job or artifact missing"})
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    payload = {"run_url": args.run_url, "rows": rows, "expected_rows": expected,
               "run_id": args.run_id, "commit": args.commit,
               "report_run_url": args.report_run_url, "report_run_id": args.report_run_id}
    def percentile(values, fraction):
        ordered = sorted(values)
        if not ordered:
            return None
        index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
        return ordered[index]
    successful = [row for row in rows if row.get("status") == "success"]
    payload["state_size_summary"] = {
        "p50_model_visible_nodes": percentile([row["model_visible_nodes"] for row in successful], 0.50),
        "p95_model_visible_nodes": percentile([row["model_visible_nodes"] for row in successful], 0.95),
        "max_model_visible_nodes": max((row["model_visible_nodes"] for row in successful), default=0),
        "p95_peak_in_flight": percentile([row.get("usage", {}).get("peak_in_flight", 0) for row in successful], 0.95),
    }
    (output / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(payload), encoding="utf-8")
    inventory = []
    for path in sorted(root.glob("**/call-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        inventory.append({"name": str(path.relative_to(root)), "purpose": "Immutable raw System One calls, retries, outcomes and SHA manifest", "retention_days": 90, "physical_calls": manifest.get("physical_calls", 0), "complete": manifest.get("complete", False)})
    inventory.append({"name": f"issue13-progressive-report-{args.run_id}", "purpose": "Aggregate metrics, Workflow metadata and experiment report", "retention_days": 90})
    (output / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    metadata = {"workflow_url": args.run_url, "run_id": args.run_id,
                "commit_sha": args.commit,
                "status": "success" if args.validate_status == "success" and args.experiment_status == "success" and len(rows) == expected and all(row.get("status") == "success" for row in rows) else "incomplete",
                "report_workflow_url": args.report_run_url,
                "report_workflow_run_id": args.report_run_id,
                "jobs": {"validate": args.validate_status, "experiment": args.experiment_status,
                         "source_report": args.source_report_status, "report": "success"},
                "artifacts": inventory}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--repository")
    parser.add_argument("--cases", default="fixtures/file-discovery/system1-vs-system2-cases.json")
    parser.add_argument("--config", default="fixtures/file-discovery/progressive-state-machine.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--aggregate")
    parser.add_argument("--run-id")
    parser.add_argument("--commit")
    parser.add_argument("--validate-status", default="unknown")
    parser.add_argument("--experiment-status", default="unknown")
    parser.add_argument("--report-run-url")
    parser.add_argument("--report-run-id")
    parser.add_argument("--source-report-status")
    args = parser.parse_args()
    if args.aggregate:
        aggregate(args)
        print((Path(args.output_dir) / "report.md").read_text(encoding="utf-8"))
        return
    if not args.repository:
        parser.error("--repository is required when running an experiment")
    rows = run_case(args)
    print(json.dumps({"repository": args.repository, "rows": len(rows),
                      "failed": sum(row["status"] != "success" for row in rows)}, indent=2))
    raise SystemExit(int(any(row["status"] != "success" for row in rows)))


if __name__ == "__main__":
    main()
