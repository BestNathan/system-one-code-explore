"""Workflow-only runner/report for uncapped discovery and concurrency research."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from file_discovery_adaptive import AdaptiveDecider, discover
from file_discovery_profiles import repository_metadata_context
from file_discovery_scoring import BatchScorer, LockedTrace, write_call_dataset
from file_discovery_v1 import enumerate_files
from model_pricing import jev_cost_record
from system_one_code_locator import API_URL, MODEL


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def render_report(payload):
    rows = payload["rows"]
    completed = [r for r in rows if r["status"] == "success"]
    lines = ["# File Discovery Algorithm Reduction and Concurrency Report", "",
             f"- Workflow: {payload['run_url']}", f"- Code commit: `{payload['code_sha']}`",
             f"- Recorded {len(rows)}/{payload['expected_rows']} experiment units; {len(completed)} succeeded.",
             "- File and directory counts are uncapped, with no fixed top-k or channel quota.",
             "- This round diagnoses nine existing tasks; primary labels are not complete supporting-file ground truth, and one run does not establish stability.",
             "- Quality arms reuse identical batch decisions, so their elapsed time includes cache benefits and is not independent-run latency.",
             "- Candidate changes alter batching; shared files may not share decisions, so this is not a strict paired per-file causal comparison.",
             "- Cold arms do not share cache and expose end-to-end latency, although model noise may still vary between requests.",
             "- Logical tokens and cost include cache hits; physical usage includes returned responses that later failed parsing.",
             "- Failed requests without usage have unknown cost; HTTP attempts equal sends plus retry events.", "",
             "## Per-Task Results", "",
             "| Case | Arm | Status | Selection | Total files | Scored files | Reduction | Directory decisions | Candidate recall | Final recall | Selected | Physical calls | Logical input tokens | Logical USD | Wall seconds | Cached batches |",
             "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        if r["status"] != "success":
            detail = str(r.get("error", "incomplete")).replace("|", "/").replace("\n", " ")
            lines.append(f"| {r['case_id']} | {r['arm']} | {r['status']}: {detail[:240]} | — | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        u = r["usage"]
        reduction = f"{r['reduction_factor']:.2f}" if r["reduction_factor"] is not None else "no file scoring"
        lines.append(f"| {r['case_id']} | {r['arm']} | success | {r['selection_policy']} | {r['enumerated_file_count']} | {r['scored_file_count']} | {reduction} | {r['route_scored_count']} | {r['candidate_recall']:.0%} | {r['primary_recall']:.0%} | {r['selected_file_count']} | {u['model_calls']} | {u['logical_input_tokens']} | {r['logical_pricing']['estimated_cost_usd']:.5f} | {r['wall_time_ms']/1000:.2f} | {u['cache_hits']} |")
    lines += ["", "## Repository and Policy Summary", "",
              "| Repository | Arm | Completed/planned | Mean primary recall | Mean files | Mean directories | Mean logical input tokens | Mean wall seconds |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    groups = sorted({(r.get("repository", "unknown"), r["arm"]) for r in rows})
    for repo, arm in groups:
        group = [r for r in rows if r.get("repository", "unknown") == repo and r["arm"] == arm]
        ok = [r for r in group if r["status"] == "success"]
        if not ok:
            lines.append(f"| {repo} | {arm} | 0/{len(group)} | — | — | — | — | — |")
            continue
        mean = lambda key: statistics.fmean(r[key] for r in ok)
        inputs = statistics.fmean(r["usage"]["logical_input_tokens"] for r in ok)
        lines.append(f"| {repo} | {arm} | {len(ok)}/{len(group)} | {mean('primary_recall'):.1%} | {mean('scored_file_count'):.1f} | {mean('route_scored_count'):.1f} | {inputs:.0f} | {mean('wall_time_ms')/1000:.2f} |")
    lines += ["", "## Omissions and Failures", ""]
    misses = [r for r in completed if r["missing_primary"]]
    for r in misses:
        lines.append(f"- {r['case_id']} / {r['arm']}: {json.dumps(r['missing_primary'], ensure_ascii=False)}")
    if not misses:
        lines.append("- Completed units had no primary-target omissions; this does not imply complete supporting-file recall.")
    for r in rows:
        if r["status"] != "success":
            lines.append(f"- {r['case_id']} / {r['arm']}: {r['status']}; {r.get('error', 'incomplete')}; known usage {json.dumps(r.get('usage', {}))}")
    lines += ["", "## Interpretation Boundaries and Next Step", "",
              "- Concurrency comparisons fix candidates and prompts; algorithm comparisons must consider files, directories, and logical tokens together.",
              "- Deferred modules may contain relevant files; stopping means only that the current exploration queue is exhausted.",
              "- Diagnose the stage of each recall loss, then freeze repeats and fresh tasks across all three repositories.",
              "- Raw configuration, usage, routing traces, provenance, and response model names are stored in the run artifacts.", ""]
    return "\n".join(lines)


def save_report(output, payload):
    write_json(output / "experiment.json", payload)
    (output / "report.md").write_text(render_report(payload), encoding="utf-8")


def benchmark(args):
    config = load(args.config)
    cases = [c for c in load(args.cases)["cases"] if c["repository"] == args.repository]
    if not cases:
        raise ValueError("no cases for repository")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = [{"case_id": c["id"], "repository": c["repository"], "revision": c["revision"],
             "arm": a["name"], "repeat": repeat, "status": "pending"}
            for repeat in range(config["repeats"]) for c in cases for a in config["arms"]]
    payload = {"schema_version": 1, "run_url": args.run_url,
               "code_sha": os.getenv("GITHUB_SHA", "unknown"), "config": config,
               "expected_rows": len(rows), "rows": rows}
    save_report(output, payload)
    tick = time.perf_counter()
    candidates = enumerate_files(args.root)
    context = repository_metadata_context(candidates)
    enumeration_ms = (time.perf_counter() - tick) * 1000
    payload["enumeration_ms"] = enumeration_ms
    payload["enumerated_file_count"] = len(candidates)
    case_by_id = {c["id"]: c for c in cases}
    arms = {a["name"]: a for a in config["arms"]}
    caches = {}
    for row in rows:
        case, arm = case_by_id[row["case_id"]], arms[row["arm"]]
        folder = output / row["case_id"] / f"{row['arm']}-r{row['repeat']}"
        folder.mkdir(parents=True, exist_ok=True)
        trace = LockedTrace(folder / "trace.jsonl")
        decider = AdaptiveDecider(os.environ["TYPESAFE_API_KEY"], trace,
                                 profile=config["profile"], repository_context=context,
                                 endpoint=os.getenv("TYPESAFE_API_URL", API_URL),
                                 model=os.getenv("TYPESAFE_MODEL", MODEL))
        group = arm.get("cache_group")
        cache = caches.setdefault((case["id"], row["repeat"], group), {}) if group else {}
        scorer = BatchScorer(case["goal"], decider, workers=arm["workers"],
                             batch_size=config["batch_size"], cache=cache)
        row.update(status="running", cache_group=group, requested_model=decider.model)
        save_report(output, payload)
        print(f"START {case['id']} {arm['name']} files={len(candidates)}", flush=True)
        tick = time.perf_counter()
        try:
            # Hidden labels are only used below, after the runtime has returned.
            result = discover(candidates, case["goal"], scorer, policy=arm["policy"],
                              route_threshold=config["route_threshold"],
                              uncertainty_threshold=config["uncertainty_threshold"],
                              file_threshold=config["file_threshold"],
                              selection_policy=arm.get("selection_policy", "stable_population"),
                              rescue_threshold=config.get("rescue_threshold", 0.50))
            write_json(folder / "run.json", result)
            primary = set(case["primary_files"])
            scored_paths = set(result["file_scores"])
            selected = {x["path"] for x in result["relevant_files"]}
            row.update(status="success", enumerated_file_count=len(candidates),
                       scored_file_count=len(scored_paths), route_scored_count=result["route_scored_count"],
                       reduction_factor=len(candidates) / len(scored_paths) if scored_paths else None,
                       candidate_recall=len(primary & scored_paths) / len(primary),
                       primary_recall=len(primary & selected) / len(primary),
                       primary_scores={p: result["file_scores"].get(p) for p in sorted(primary)},
                       selected_file_count=len(selected), deferred_module_count=result["deferred_module_count"],
                       selection_policy=result["selection"]["selection_policy"],
                       selection_metadata=result["selection"],
                       retrieval_evidence_count=len(result["retrieval_evidence"]),
                       index_build_ms=result["index_build_ms"],
                       missing_primary={p: "file_score_rejected" if p in scored_paths else "candidate_not_discovered"
                                        for p in sorted(primary - selected)})
        except Exception as exc:
            row.update(status="failed", error=f"{type(exc).__name__}: {str(exc)[:1200]}")
        finally:
            row["wall_time_ms"] = (time.perf_counter() - tick) * 1000
            row["cold_enumeration_plus_wall_ms"] = enumeration_ms + row["wall_time_ms"]
            usage = dict(scorer.usage)
            # Capture costs even if the API returned usage but answer parsing failed.
            for key, actual in (("model_calls", trace.response_count), ("input_tokens", trace.input_tokens),
                                ("output_tokens", trace.output_tokens)):
                usage[f"logical_{key}"] += max(0, actual - usage[key])
                usage[key] = actual
            usage.pop("request_time_sum_ms", None)
            usage.update(returned_response_time_sum_ms=trace.response_time_sum_ms,
                         logical_sends=trace.requests, http_attempts=trace.requests + trace.retries,
                         retry_events=trace.retries, rate_limit_retry_events=trace.rate_limits,
                         max_request_bytes=trace.max_request_bytes,
                         returned_models=sorted(trace.returned_models))
            row["usage"], row["stage_usage"] = usage, scorer.stages
            row["stage_usage_complete"] = row["status"] == "success"
            row["physical_pricing"] = jev_cost_record(usage["input_tokens"], usage["output_tokens"])
            row["logical_pricing"] = jev_cost_record(usage["logical_input_tokens"], usage["logical_output_tokens"])
            row["call_data"] = write_call_dataset(
                folder / "trace.jsonl", folder / "raw-model-calls.jsonl",
                folder / "call-manifest.json")
            write_json(folder / "metrics.json", row)
            save_report(output, payload)
            print(f"END {case['id']} {arm['name']} {row['status']} wall={row['wall_time_ms']/1000:.2f}s files={row.get('scored_file_count')} recall={row.get('primary_recall')}", flush=True)
    return any(r["status"] != "success" for r in rows)


def aggregate(args):
    config = load(args.config)
    cases = load(args.cases)["cases"]
    reports = [load(p) for p in sorted(Path(args.aggregate).glob("**/experiment.json"))]
    rows = [r for report in reports for r in report["rows"]]
    seen = {(r["case_id"], r["arm"], r["repeat"]) for r in rows}
    for case in cases:
        for arm in config["arms"]:
            for repeat in range(config["repeats"]):
                if (case["id"], arm["name"], repeat) not in seen:
                    rows.append(dict(case_id=case["id"], repository=case["repository"], arm=arm["name"],
                                     repeat=repeat, status="missing", error="job artifact unavailable"))
    payload = {"schema_version": 1, "run_url": args.run_url, "code_sha": os.getenv("GITHUB_SHA", "unknown"),
               "config": config, "expected_rows": len(cases) * len(config["arms"]) * config["repeats"],
               "rows": rows, "repository_metadata": [{k: v for k, v in r.items() if k != "rows"} for r in reports]}
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    save_report(output, payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--repository")
    parser.add_argument("--cases", default="fixtures/file-discovery/system1-vs-system2-cases.json")
    parser.add_argument("--config", default="fixtures/file-discovery/scaling-experiment.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--aggregate")
    args = parser.parse_args()
    if args.aggregate:
        aggregate(args)
    else:
        raise SystemExit(int(benchmark(args)))


if __name__ == "__main__":
    main()
