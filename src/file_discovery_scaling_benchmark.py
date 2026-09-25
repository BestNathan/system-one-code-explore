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
from file_discovery_scoring import BatchScorer, LockedTrace
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
    lines = ["# File Discovery 算法缩减与并发实验报告", "",
             f"- Workflow: {payload['run_url']}", f"- Code commit: `{payload['code_sha']}`",
             f"- 已记录 {len(rows)}/{payload['expected_rows']} 个实验单元；成功 {len(completed)}。",
             "- 文件/目录无数量上限、无固定 top-k、无通道配额。",
             "- 此轮为既有九任务诊断；主要目标标签并非完整支持文件真值。单次结果不证明稳定性。",
             "- quality 组复用完全相同的批次决策；其实际耗时包含缓存收益，不能视作独立运行延迟。",
             "- cold 组不共享缓存，适合观察真实端到端耗时；不同请求的模型噪声仍可能影响结果。",
             "- 逻辑 tokens/费用包括缓存命中；物理 tokens/费用来自响应 usage，包含已返回但解析失败的响应。",
             "- 未返回 usage 的失败请求费用未知；HTTP attempts 是 send 数与重试事件数之和。", "",
             "## 每任务结果", "",
             "| Case | Arm | 状态 | 总文件 | 打分文件 | 缩减倍数 | 目录判断 | 候选召回 | 最终召回 | 入选 | 物理调用 | 逻辑输入 tokens | 逻辑 USD | 实际秒 | 缓存批次 |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        if r["status"] != "success":
            detail = str(r.get("error", "未完成")).replace("|", "/").replace("\n", " ")
            lines.append(f"| {r['case_id']} | {r['arm']} | {r['status']}: {detail[:240]} | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        u = r["usage"]
        reduction = f"{r['reduction_factor']:.2f}" if r["reduction_factor"] is not None else "无文件打分"
        lines.append(f"| {r['case_id']} | {r['arm']} | success | {r['enumerated_file_count']} | {r['scored_file_count']} | {reduction} | {r['route_scored_count']} | {r['candidate_recall']:.0%} | {r['primary_recall']:.0%} | {r['selected_file_count']} | {u['model_calls']} | {u['logical_input_tokens']} | {r['logical_pricing']['estimated_cost_usd']:.5f} | {r['wall_time_ms']/1000:.2f} | {u['cache_hits']} |")
    lines += ["", "## 分仓库与方案汇总", "",
              "| Repository | Arm | 完成/计划 | 主要目标召回均值 | 文件数均值 | 目录数均值 | 输入 tokens 均值（逻辑） | 实际秒均值 |",
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
    lines += ["", "## 遗漏与失败", ""]
    misses = [r for r in completed if r["missing_primary"]]
    for r in misses:
        lines.append(f"- {r['case_id']} / {r['arm']}: {json.dumps(r['missing_primary'], ensure_ascii=False)}")
    if not misses:
        lines.append("- 已完成实验未发现主要目标遗漏；不代表支持文件完整召回。")
    for r in rows:
        if r["status"] != "success":
            lines.append(f"- {r['case_id']} / {r['arm']}: {r['status']}；{r.get('error', '未完成')}；已知用量 {json.dumps(r.get('usage', {}))}")
    lines += ["", "## 解释边界与下一步", "",
              "- 对比并发组时固定候选与提示；对比算法组时同时查看文件数、目录数和逻辑 tokens，不能仅看最终输出大小。",
              "- 延后模块可能仍含相关文件，停止仅表示当前策略的探索队列耗尽，不是完整覆盖证明。",
              "- 重点分析召回退化所在阶段；首轮诊断后再冻结配置做重复与三仓库新任务验证。",
              "- 原始配置、每条用量、路由轨迹、候选来源及响应模型名在同一运行的 artifacts 中。", ""]
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
                              file_threshold=config["file_threshold"])
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
            usage.update(request_time_sum_ms=trace.response_time_sum_ms,
                         logical_sends=trace.requests, http_attempts=trace.requests + trace.retries,
                         retry_events=trace.retries, rate_limit_retry_events=trace.rate_limits,
                         max_request_bytes=trace.max_request_bytes,
                         returned_models=sorted(trace.returned_models))
            row["usage"], row["stage_usage"] = usage, scorer.stages
            row["physical_pricing"] = jev_cost_record(usage["input_tokens"], usage["output_tokens"])
            row["logical_pricing"] = jev_cost_record(usage["logical_input_tokens"], usage["logical_output_tokens"])
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
