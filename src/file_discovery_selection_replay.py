"""Replay final selection over prior Workflow artifacts without model calls."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from file_discovery_selection import select_relevant


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def replay(root, cases):
    case_by_id = {case["id"]: case for case in cases["cases"]}
    rows = []
    for metrics_path in sorted(Path(root).glob("**/metrics.json")):
        metrics = load(metrics_path)
        if metrics.get("status") != "success":
            continue
        run_path = metrics_path.with_name("run.json")
        if not run_path.exists():
            continue
        run = load(run_path)
        case = case_by_id[metrics["case_id"]]
        selected, policy = select_relevant(
            run["file_scores"],
            enumerated_file_count=run["enumerated_file_count"],
        )
        old_selected = {item["path"] for item in run["relevant_files"]}
        new_selected = {item["path"] for item in selected}
        primary = set(case["primary_files"])
        ordered = sorted(run["file_scores"], key=lambda path: (-run["file_scores"][path], path))
        ranks = {path: index + 1 for index, path in enumerate(ordered)}
        rows.append({
            "case_id": metrics["case_id"],
            "repository": metrics["repository"],
            "arm": metrics["arm"],
            "enumerated_file_count": run["enumerated_file_count"],
            "scored_file_count": run["scored_file_count"],
            "old_selected_file_count": len(old_selected),
            "replay_selected_file_count": len(new_selected),
            "old_primary_recall": len(primary & old_selected) / len(primary),
            "replay_primary_recall": len(primary & new_selected) / len(primary),
            "primary_scores": {path: run["file_scores"].get(path) for path in sorted(primary)},
            "primary_candidate_ranks": {path: ranks.get(path) for path in sorted(primary)},
            "newly_selected_primary": sorted((primary & new_selected) - old_selected),
            "policy": policy,
        })
    return rows


def markdown(payload):
    lines = ["# File Discovery 稳定相对保护回放", "",
             f"- 来源 Workflow: {payload['source_run_url']}",
             f"- 回放 Workflow: {payload['replay_run_url']}",
             "- 模型调用：0；仅重放已保存的候选分数。", "",
             "| Case | Arm | 文件打分 | 旧入选 | 回放入选 | 旧召回 | 回放召回 | 保护名额 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in payload["rows"]:
        lines.append(
            f"| {row['case_id']} | {row['arm']} | {row['scored_file_count']} | "
            f"{row['old_selected_file_count']} | {row['replay_selected_file_count']} | "
            f"{row['old_primary_recall']:.0%} | {row['replay_primary_recall']:.0%} | "
            f"{row['policy']['relative_fallback_min_count']} |"
        )
    groups = defaultdict(list)
    for row in payload["rows"]:
        groups[row["arm"]].append(row)
    lines += ["", "## 汇总", "",
              "| Arm | 案例 | 旧召回 | 回放召回 | 入选文件均值 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for arm, rows in sorted(groups.items()):
        old = sum(r["old_primary_recall"] for r in rows) / len(rows)
        new = sum(r["replay_primary_recall"] for r in rows) / len(rows)
        selected = sum(r["replay_selected_file_count"] for r in rows) / len(rows)
        lines.append(f"| {arm} | {len(rows)} | {old:.1%} | {new:.1%} | {selected:.1f} |")
    lines += ["", "## 新恢复目标", ""]
    recovered = [(r["case_id"], r["arm"], path) for r in payload["rows"] for path in r["newly_selected_primary"]]
    lines.extend(f"- {case} / {arm}: `{path}`" for case, arm, path in recovered)
    if not recovered:
        lines.append("- 无。")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--cases", default="fixtures/file-discovery/system1-vs-system2-cases.json")
    parser.add_argument("--source-run-url", required=True)
    parser.add_argument("--replay-run-url", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "source_run_url": args.source_run_url,
               "replay_run_url": args.replay_run_url,
               "rows": replay(args.artifact_root, load(args.cases))}
    if not payload["rows"]:
        raise SystemExit("no successful experiment artifacts found")
    write_json(output / "replay.json", payload)
    (output / "report.md").write_text(markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
