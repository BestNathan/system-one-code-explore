#!/usr/bin/env python3
"""Two-stage global-directory semantic compression for File Discovery."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path, PurePosixPath

from file_discovery_profiles import ProfiledFileDiscoveryDecider
from file_discovery_progressive import flat_path_baseline
from file_discovery_scoring import BatchScorer, LockedTrace, write_call_dataset
from file_discovery_v1 import IGNORE, SUFFIXES
from model_pricing import jev_cost_record
from system_one_code_locator import API_URL, MODEL

WORKERS = 4
BATCH_SIZE = 64
MAX_CANDIDATE_BYTES = 48000
DIRECTORY_THRESHOLD = 0.65
FILE_THRESHOLD = 0.65


def eligible_file(entry):
    if entry.name.startswith("."):
        return False
    try:
        return entry.is_file(follow_symlinks=True) and Path(entry.name).suffix.lower() in SUFFIXES
    except OSError:
        return False


def eligible_directory(entry):
    if entry.name.startswith(".") or entry.name in IGNORE:
        return False
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def enumerate_directories(root):
    """Enumerate every eligible directory before routing; provide direct counts only."""
    root = Path(root).resolve()
    paths = ["."]
    for current, dirnames, _ in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        dirnames[:] = sorted(name for name in dirnames
                             if not name.startswith(".") and name not in IGNORE
                             and not (base / name).is_symlink())
        relative_parent = base.relative_to(root).as_posix()
        for name in dirnames:
            relative = name if relative_parent == "." else f"{relative_parent}/{name}"
            paths.append(relative)

    result = []
    for relative in sorted(set(paths)):
        absolute = root if relative == "." else root / relative
        direct_files = direct_directories = 0
        try:
            with os.scandir(absolute) as entries:
                for entry in entries:
                    if eligible_file(entry):
                        direct_files += 1
                    elif eligible_directory(entry):
                        direct_directories += 1
        except OSError:
            continue
        path = relative
        result.append({
            "id": f"directory:{path}", "kind": "directory", "path": path,
            "payload": {
                "path": path,
                "basename": root.name if path == "." else PurePosixPath(path).name,
                "depth": 0 if path == "." else len(PurePosixPath(path).parts),
                "direct_file_count": direct_files,
                "direct_directory_count": direct_directories,
            },
        })
    return result


def enumerate_direct_files(root, directory_paths):
    """Return deduplicated supported files directly inside selected directories."""
    root = Path(root).resolve()
    by_path = {}
    for relative in sorted(set(directory_paths)):
        absolute = root if relative == "." else root / relative
        try:
            with os.scandir(absolute) as entries:
                for entry in entries:
                    if not eligible_file(entry):
                        continue
                    path = entry.name if relative == "." else f"{relative}/{entry.name}"
                    try:
                        size = entry.stat(follow_symlinks=True).st_size
                    except OSError:
                        continue
                    by_path[path] = {
                        "id": f"file:{path}", "kind": "file", "path": path,
                        "parent": relative,
                        "payload": {"kind": "file", "path": path, "parent": relative,
                                    "filename": entry.name,
                                    "extension": Path(entry.name).suffix.lower(),
                                    "size_bytes": size},
                    }
        except OSError:
            continue
    return [by_path[path] for path in sorted(by_path)]


class GlobalDirectoryDecider(ProfiledFileDiscoveryDecider):
    def score_candidates(self, query, stage, candidates):
        if stage == "file":
            return super().score_candidates(query, "file_discovery_v1", candidates)
        questions = {}
        for index, candidate in enumerate(candidates):
            questions[f"directory_{index}"] = {
                "type": "noul",
                "instructions": {
                    "task": query,
                    "directory": candidate["payload"],
                    "question": ("How likely is this directory's direct file set to contain material "
                                 "implementation or necessary supporting evidence for the task? "
                                 "Judge these direct files only, not the subtree."),
                },
                "criteria": {
                    "true": "The direct files in this exact directory are likely to contain material task evidence.",
                    "false": "The direct files in this exact directory are unlikely to contain material task evidence.",
                },
            }
        response, usage = self.send("global_directory_direct_file_relevance", {
            "goal": query,
            "phase": "global_directory_classification",
            "population_size": getattr(self, "logical_directory_population", len(candidates)),
            "source_visible": False,
            "contract": ("Independent multi-label decisions over one fixed global directory population. "
                         "Directory scores do not expose, hide, or gate any other directory."),
        }, questions)
        answers = response.get("answers", {})
        result = []
        for index, candidate in enumerate(candidates):
            answer = answers.get(f"directory_{index}", {})
            if answer.get("type") != "noul":
                raise ValueError(f"missing or invalid directory answer for {candidate['id']}")
            result.append({**candidate, "score": float(answer["noul"])})
        return result, usage


def _score_batches(candidates, batch_size=BATCH_SIZE, max_bytes=MAX_CANDIDATE_BYTES):
    ordered = sorted(candidates, key=lambda item: item["id"])
    sizes, current = [], 0
    count = 0
    for candidate in ordered:
        size = len(json.dumps(candidate["payload"], ensure_ascii=False).encode("utf-8"))
        if count and (count >= batch_size or current + size > max_bytes):
            sizes.append(count)
            current = count = 0
        current += size
        count += 1
    if count:
        sizes.append(count)
    return sizes


def two_stage_discovery(root, query, scorer, *, directory_threshold=DIRECTORY_THRESHOLD,
                        file_threshold=FILE_THRESHOLD, workers=WORKERS,
                        batch_size=BATCH_SIZE, max_candidate_bytes=MAX_CANDIDATE_BYTES):
    started = time.perf_counter()
    dirs = enumerate_directories(root)
    if hasattr(scorer, "decider"):
        scorer.decider.logical_directory_population = len(dirs)
    inventory_ms = (time.perf_counter() - started) * 1000

    phase1_started = time.perf_counter()
    dir_scores = scorer.score("directory", dirs) if dirs else []
    phase1_ms = (time.perf_counter() - phase1_started) * 1000
    selected_dirs = sorted(item["path"] for item in dir_scores
                           if float(item["score"]) >= directory_threshold)

    phase2_started = time.perf_counter()
    direct_files = enumerate_direct_files(root, selected_dirs)
    phase2_enumeration_ms = (time.perf_counter() - phase2_started) * 1000
    phase2_scoring_started = time.perf_counter()
    file_scores = scorer.score("file", direct_files) if direct_files else []
    phase2_scoring_ms = (time.perf_counter() - phase2_scoring_started) * 1000
    promoted = sorted((item for item in file_scores if float(item["score"]) >= file_threshold),
                      key=lambda item: (-float(item["score"]), item["path"]))
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "algorithm": "global_directory_classification_then_direct_files",
        "policy": {"directory_threshold": directory_threshold, "file_threshold": file_threshold,
                   "workers": workers, "batch_size": batch_size,
                   "max_candidate_bytes": max_candidate_bytes, "hard_candidate_cap": None,
                   "ancestor_gating": False, "recursive_expansion": False},
        "directory_population": len(dirs),
        "total_repository_file_count": sum(int(item["payload"]["direct_file_count"]) for item in dirs),
        "directory_scores": {item["path"]: float(item["score"]) for item in dir_scores},
        "selected_directories": selected_dirs,
        "deduplicated_file_candidate_count": len(direct_files),
        "directory_batch_sizes": _score_batches(dirs, batch_size, max_candidate_bytes),
        "file_batch_sizes": _score_batches(direct_files, batch_size, max_candidate_bytes),
        "directory_decisions": len(dir_scores),
        "file_decisions": len(file_scores),
        "model_visible_nodes": len(dir_scores) + len(file_scores),
        "promoted_files": [{"path": item["path"], "score": float(item["score"])} for item in promoted],
        "file_scores": {item["path"]: float(item["score"]) for item in file_scores},
        "phase1_wall_time_ms": phase1_ms,
        "phase2_enumeration_wall_time_ms": phase2_enumeration_ms,
        "phase2_scoring_wall_time_ms": phase2_scoring_ms,
        "inventory_wall_time_ms": inventory_ms,
        "wall_time_ms": elapsed,
    }


def trace_phase_usage(trace_path):
    result = {}
    stage_by_call = {}
    for line in Path(trace_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        call_id = event.get("call_id")
        stage = event.get("stage") or stage_by_call.get(call_id, "unknown")
        if event.get("event") == "system_one_request" and call_id:
            stage_by_call[call_id] = stage
        stats = result.setdefault(stage, {"physical_calls": 0, "input_tokens": 0,
                                          "output_tokens": 0, "response_count": 0,
                                          "retry_events": 0, "http_attempts": 0,
                                          "latency_sum_ms": 0.0})
        if event.get("event") == "system_one_request":
            stats["physical_calls"] += 1
        elif event.get("event") == "system_one_retry":
            stats["retry_events"] += 1
        elif event.get("event") == "system_one_response":
            stats["response_count"] += 1
            usage = event.get("usage", {})
            stats["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
            stats["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
            stats["latency_sum_ms"] += float(event.get("latency_ms", 0) or 0)
    for stats in result.values():
        stats["http_attempts"] = stats["physical_calls"] + stats["retry_events"]
    return result


def flat_baseline(root, query, scorer):
    started = time.perf_counter()
    result = flat_path_baseline(root, query, scorer)
    result["algorithm"] = "uncapped_semantic_weighted_path_then_file_score"
    result["directory_decisions"] = 0
    result["model_visible_nodes"] = result["file_decisions"]
    result["directory_population"] = 0
    result["total_repository_file_count"] = result.get("enumerated_file_count")
    result["selected_directories"] = []
    result["deduplicated_file_candidate_count"] = result["candidate_file_count"]
    result["directory_batch_sizes"] = []
    result["file_batch_sizes"] = []
    result["phase1_wall_time_ms"] = 0.0
    result["phase2_enumeration_wall_time_ms"] = 0.0
    result["phase2_scoring_wall_time_ms"] = (time.perf_counter() - started) * 1000
    return result


def run_repository(args):
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    cases = [case for case in cases if case["repository"] == args.repository]
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        for arm in ("flat_path", "global_directory"):
            folder = output / case["id"] / arm
            folder.mkdir(parents=True, exist_ok=True)
            trace = LockedTrace(folder / "trace.jsonl")
            decider = GlobalDirectoryDecider(os.environ["TYPESAFE_API_KEY"], trace,
                profile=config["profile"], repository_context={},
                endpoint=os.getenv("TYPESAFE_API_URL", API_URL),
                model=os.getenv("TYPESAFE_MODEL", config["model"] or MODEL))
            scorer = BatchScorer(case["goal"], decider, workers=int(config["workers"]),
                batch_size=int(config["batch_size"]),
                max_candidate_bytes=int(config["max_candidate_bytes"]))
            started = time.perf_counter()
            try:
                result = (flat_baseline(args.root, case["goal"], scorer) if arm == "flat_path"
                          else two_stage_discovery(args.root, case["goal"], scorer,
                               directory_threshold=config["directory_threshold"],
                               file_threshold=config["file_threshold"],
                               workers=int(config["workers"]),
                               batch_size=int(config["batch_size"]),
                               max_candidate_bytes=int(config["max_candidate_bytes"])))
                selected_files = {item["path"] for item in result["promoted_files"]}
                scored_files = set(result["file_scores"])
                primary = set(case["primary_files"])
                parent_paths = {path: (PurePosixPath(path).parent.as_posix() or ".") for path in primary}
                selected_dirs = set(result.get("selected_directories", []))
                phase_usage = trace_phase_usage(folder / "trace.jsonl")
                missing = primary - selected_files
                causes = {}
                for path in sorted(missing):
                    if path in scored_files:
                        causes[path] = "file_score_rejected"
                    elif arm == "flat_path":
                        causes[path] = "path_retrieval_omission"
                    elif parent_paths[path] not in selected_dirs:
                        causes[path] = "target_directory_not_selected"
                    else:
                        causes[path] = "target_file_not_promoted"
                target_details = [{"path": path, "directory": parent_paths[path],
                    "directory_selected": parent_paths[path] in selected_dirs if arm != "flat_path" else None,
                    "file_scored": path in scored_files,
                    "file_score": result["file_scores"].get(path),
                    "promoted": path in selected_files} for path in sorted(primary)]
                row = {"case_id": case["id"], "repository": args.repository, "arm": arm,
                    "status": "success", **result,
                    "candidate_recall": len(primary & scored_files) / len(primary),
                    "primary_recall": len(primary & selected_files) / len(primary),
                    "missing_primary": sorted(missing), "missing_primary_causes": causes,
                    "target_details": target_details, "phase_usage": phase_usage,
                    "usage": scorer.usage}
            except Exception as exc:
                row = {"case_id": case["id"], "repository": args.repository, "arm": arm,
                    "status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:1000]}",
                    "usage": scorer.usage, "phase_usage": trace_phase_usage(folder / "trace.jsonl")}
            finally:
                row["wall_time_ms"] = (time.perf_counter() - started) * 1000
                row["physical_usage"] = {"model_calls": trace.response_count,
                    "input_tokens": trace.input_tokens, "output_tokens": trace.output_tokens,
                    "http_attempts": trace.requests + trace.retries,
                    "retry_events": trace.retries, "max_request_bytes": trace.max_request_bytes}
                row["pricing"] = jev_cost_record(trace.input_tokens, trace.output_tokens)
                row["call_data"] = write_call_dataset(folder / "trace.jsonl",
                    folder / "raw-model-calls.jsonl", folder / "call-manifest.json")
                (folder / "result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
            rows.append(row)
            save_progress(output, args.run_url, args.repository, rows, len(cases) * 2)
    save_progress(output, args.run_url, args.repository, rows, len(cases) * 2)
    return rows


def save_progress(output, run_url, repository, rows, expected):
    output = Path(output)
    payload = {"run_url": run_url, "repository": repository,
               "expected_rows": expected, "completed_rows": len(rows), "rows": rows}
    (output / "progress.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(payload), encoding="utf-8")


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, int(len(ordered) * fraction + 0.999999))
    return ordered[min(len(ordered) - 1, rank - 1)]


def render_report(payload):
    lines = ["# Issue 14 — Global Directory Classification", "",
        f"- Workflow: {payload['run_url']}", f"- Repository: `{payload.get('repository', 'aggregate')}`",
        "- Directory candidates are globally enumerated before Phase 1; no directory score gates another directory.",
        "- Phase 2 enumerates direct files only. No source bodies, top-k, or hard candidate caps are used.", "",
        "| Case | Arm | Status | Candidate recall | Final recall | Total files | All dirs | Selected dirs | Phase 2 files | Promoted | Visible nodes | P1 calls | P1 in/out tokens | P2 calls | P2 in/out tokens | Total calls | Wall s |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in payload["rows"]:
        if row.get("status") != "success":
            lines.append(f"| {row.get('case_id')} | {row.get('arm')} | {row.get('status')}: {str(row.get('error', 'missing'))[:120]} | — | — | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        usage = row.get("phase_usage", {})
        p1 = usage.get("global_directory_direct_file_relevance", {})
        p2 = usage.get("file_discovery_compact_state_v4", {})
        p1_calls, p2_calls = p1.get("physical_calls", 0), p2.get("physical_calls", 0)
        p1_tokens = f"{p1.get('input_tokens', 0)}/{p1.get('output_tokens', 0)}"
        p2_tokens = f"{p2.get('input_tokens', 0)}/{p2.get('output_tokens', 0)}"
        direct_count = row.get("deduplicated_file_candidate_count", row.get("candidate_file_count", 0))
        promoted = row.get("promoted_file_count", len(row.get("promoted_files", [])))
        lines.append(f"| {row['case_id']} | {row['arm']} | success | {row['candidate_recall']:.0%} | {row['primary_recall']:.0%} | {row.get('total_repository_file_count', row.get('enumerated_file_count', '—'))} | {row.get('directory_population', 0)} | {row.get('selected_directory_count', len(row.get('selected_directories', [])))} | {direct_count} | {promoted} | {row.get('model_visible_nodes', 0)} | {p1_calls} | {p1_tokens} | {p2_calls} | {p2_tokens} | {row.get('physical_usage', {}).get('model_calls', 0)} | {row.get('wall_time_ms', 0)/1000:.1f} |")
    lines += ["", "## Target Routing", ""]
    for row in payload["rows"]:
        if row.get("status") != "success":
            continue
        for target in row.get("target_details", []):
            if target.get("directory_selected") is None:
                route = "directory selection: not applicable"
            else:
                route = f"directory selected: {target['directory_selected']}"
            lines.append(f"- {row['case_id']} / {row['arm']} / `{target['path']}`: {route}; file scored: {target['file_scored']}; score: {target['file_score']}; promoted: {target['promoted']}")
    misses = [row for row in payload["rows"] if row.get("status") == "success" and row.get("missing_primary")]
    lines.extend([f"- {row['case_id']} / {row['arm']}: " + "; ".join(
        f"{path} ({row.get('missing_primary_causes', {}).get(path, 'unclassified')})"
        for path in row["missing_primary"]) for row in misses] or ["- No primary target misses in completed arms."])
    lines += ["", "## Interpretation Notes", "",
        "- Phase 1 batches are fixed from the complete directory population; later batches do not depend on earlier scores.",
        "- Results compare full policies with independent model calls; no counterfactual cache is shared between arms.",
        "- The nine targets are diagnostic primary labels, not complete supporting-file ground truth.", ""]
    if payload.get("cost_summary"):
        lines += ["## End-to-End Cost Distribution", "",
            "| Metric | p50 | p95 | Max |", "| --- | ---: | ---: | ---: |"]
        for name, values in payload["cost_summary"].items():
            lines.append(f"| {name} | {values['p50']} | {values['p95']} | {values['max']} |")
        lines.append("")
    if payload.get("batch_size_summary"):
        lines += ["## Physical Batch-Size Distribution", "",
            "| Phase | p50 | p95 | Max |", "| --- | ---: | ---: | ---: |"]
        for phase, values in payload["batch_size_summary"].items():
            lines.append(f"| {phase} | {values['p50']} | {values['p95']} | {values['max']} |")
        lines.append("")
    groups = sorted({(row.get("repository", "unknown"), row.get("arm", "unknown")) for row in payload["rows"]})
    lines += ["## Repository and Arm Summary", "",
        "| Repository | Arm | Tasks | Mean candidate recall | Mean final recall | Mean Phase 1 dirs | Mean Phase 2 files | Mean visible nodes | Mean input tokens |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for repository, arm in groups:
        group = [row for row in payload["rows"] if row.get("repository") == repository and row.get("arm") == arm]
        done = [row for row in group if row.get("status") == "success"]
        if not done:
            lines.append(f"| {repository} | {arm} | 0/{len(group)} | — | — | — | — | — | — |")
            continue
        mean = lambda key: sum(float(row.get(key, 0) or 0) for row in done) / len(done)
        mean_tokens = sum(float(row.get("physical_usage", {}).get("input_tokens", 0)) for row in done) / len(done)
        dirs = mean("directory_population")
        files = mean("deduplicated_file_candidate_count") if arm == "global_directory" else mean("candidate_file_count")
        lines.append(f"| {repository} | {arm} | {len(done)}/{len(group)} | {mean('candidate_recall'):.1%} | {mean('primary_recall'):.1%} | {dirs:.1f} | {files:.1f} | {mean('model_visible_nodes'):.1f} | {mean_tokens:.0f} |")
    lines.append("")
    return "\n".join(lines)


def aggregate(args):
    root = Path(args.aggregate)
    reports = [json.loads(path.read_text(encoding="utf-8"))
               for path in sorted(root.glob("**/progress.json"))]
    rows = [row for report in reports for row in report.get("rows", [])]
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    expected = len(cases) * 2
    seen = {(row.get("case_id"), row.get("arm")) for row in rows}
    for case in cases:
        for arm in ("flat_path", "global_directory"):
            if (case["id"], arm) not in seen:
                rows.append({"case_id": case["id"], "repository": case["repository"],
                    "arm": arm, "status": "missing", "error": "repository job or artifact missing"})
    successful = [row for row in rows if row.get("status") == "success"]
    batch_sizes = {stage: [size for row in successful for size in row.get(key, [])]
        for stage, key in (("directory", "directory_batch_sizes"), ("file", "file_batch_sizes"))}
    batch_summary = {stage: {"p50": percentile(values, .50), "p95": percentile(values, .95),
                             "max": max(values, default=0)} for stage, values in batch_sizes.items()}
    cost_values = {
        "model_visible_nodes": [row.get("model_visible_nodes", 0) for row in successful],
        "physical_calls": [row.get("physical_usage", {}).get("model_calls", 0) for row in successful],
        "input_tokens": [row.get("physical_usage", {}).get("input_tokens", 0) for row in successful],
        "output_tokens": [row.get("physical_usage", {}).get("output_tokens", 0) for row in successful],
        "phase_1_directory_candidates": [row.get("directory_population", 0) for row in successful],
        "phase_2_file_candidates": [row.get("deduplicated_file_candidate_count", row.get("candidate_file_count", 0)) for row in successful],
    }
    cost_summary = {name: {"p50": percentile(values, .50), "p95": percentile(values, .95),
                           "max": max(values, default=0)} for name, values in cost_values.items()}
    payload = {"run_url": args.run_url, "run_id": args.run_id, "commit": args.commit,
        "report_run_url": args.report_run_url, "report_run_id": args.report_run_id,
        "expected_rows": expected, "rows": rows, "batch_size_summary": batch_summary,
        "cost_summary": cost_summary}
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary_fields = ("case_id", "repository", "arm", "status", "algorithm",
        "directory_population", "selected_directory_count", "deduplicated_file_candidate_count",
        "total_repository_file_count", "directory_batch_sizes", "file_batch_sizes",
        "candidate_file_count", "file_decisions", "directory_decisions", "model_visible_nodes",
        "candidate_recall", "primary_recall", "missing_primary", "missing_primary_causes",
        "target_details", "phase_usage", "physical_usage", "pricing", "phase1_wall_time_ms",
        "phase2_enumeration_wall_time_ms", "phase2_scoring_wall_time_ms", "wall_time_ms", "error")
    compact_rows = []
    for row in rows:
        compact = {key: row[key] for key in summary_fields if key in row}
        compact["selected_directory_count"] = len(row.get("selected_directories", []))
        compact["promoted_file_count"] = len(row.get("promoted_files", []))
        compact_rows.append(compact)
    payload["rows"] = compact_rows
    (output / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(payload), encoding="utf-8")
    inventory = []
    for path in sorted(root.glob("**/call-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        inventory.append({"name": str(path.relative_to(root)),
            "purpose": "Immutable raw System One requests, responses, retries, errors, and SHA manifest",
            "retention_days": 90, "physical_calls": manifest.get("physical_calls", 0),
            "complete": manifest.get("complete", False)})
    inventory.append({"name": f"issue14-aggregate-{args.report_run_id or args.run_id}",
        "purpose": "Aggregate metrics, report, and Workflow metadata", "retention_days": 90})
    metadata = {"workflow_url": args.run_url, "run_id": args.run_id, "commit_sha": args.commit,
        "status": "success" if args.validate_status == "success" and args.experiment_status == "success" and len(rows) == expected and all(row.get("status") == "success" for row in rows) else "incomplete",
        "report_workflow_url": args.report_run_url, "report_workflow_run_id": args.report_run_id,
        "jobs": {"validate": args.validate_status, "experiment": args.experiment_status,
                 "source_report": args.source_report_status, "report": "success"},
        "artifacts": inventory}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--repository")
    parser.add_argument("--cases", default="fixtures/file-discovery/system1-vs-system2-cases.json")
    parser.add_argument("--config", default="fixtures/file-discovery/global-directory-classification.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--aggregate")
    parser.add_argument("--run-id")
    parser.add_argument("--commit")
    parser.add_argument("--validate-status", default="unknown")
    parser.add_argument("--experiment-status", default="unknown")
    parser.add_argument("--source-report-status")
    parser.add_argument("--report-run-url")
    parser.add_argument("--report-run-id")
    args = parser.parse_args()
    if args.aggregate:
        aggregate(args)
        print((Path(args.output_dir) / "report.md").read_text(encoding="utf-8"))
        return
    if not args.repository:
        parser.error("--repository is required for a repository experiment job")
    rows = run_repository(args)
    raise SystemExit(int(any(row["status"] != "success" for row in rows)))


if __name__ == "__main__":
    main()
