#!/usr/bin/env python3
"""Turn a completed Phase0 trajectory into final evidence snippets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reference_field(reference):
    n = int(reference["line_count"])
    field = [0.0] * n
    for item in reference["ranges"]:
        score = float(item["relevance"])
        left = max(1, int(item["start_line"]))
        right = min(n, int(item["end_line"]))
        for line in range(left, right + 1):
            field[line - 1] = max(field[line - 1], score)
    return field


def expand(center, line_count, width):
    width = max(1, min(int(width), int(line_count)))
    left = max(1, int(center) - width // 2)
    right = min(int(line_count), left + width - 1)
    left = max(1, right - width + 1)
    return left, right


def overlaps(left, right, selected):
    return any(
        not (right < item["start_line"] or left > item["end_line"])
        for item in selected
    )


def select_phase0_snippets(run, line_count, snippet_lines=32, max_snippets=6):
    samples = sorted(
        run.get("frontier", {}).get("samples", []),
        key=lambda item: (
            -float(item["score"]),
            int(item["start_line"]),
        ),
    )
    selected = []
    for sample in samples:
        center = (
            int(sample["start_line"]) + int(sample["end_line"])
        ) // 2
        left, right = expand(center, line_count, snippet_lines)
        if overlaps(left, right, selected):
            continue
        selected.append({
            "start_line": left,
            "end_line": right,
            "phase0_score": float(sample["score"]),
            "source_probe": [
                int(sample["start_line"]),
                int(sample["end_line"]),
            ],
        })
        if len(selected) >= int(max_snippets):
            break
    return selected


def truth_metrics(selected, truth, high_threshold=0.70):
    chosen = set()
    for item in selected:
        chosen.update(
            range(int(item["start_line"]), int(item["end_line"]) + 1)
        )
    high = {
        i + 1 for i, value in enumerate(truth)
        if value >= high_threshold
    }
    total_mass = sum(truth)
    selected_mass = sum(truth[line - 1] for line in chosen)
    selected_high = len(chosen & high)
    return {
        "selected_lines": len(chosen),
        "mean_reference_relevance": (
            selected_mass / len(chosen) if chosen else 0.0
        ),
        "high_line_precision": (
            selected_high / len(chosen) if chosen else 0.0
        ),
        "high_line_recall": (
            selected_high / len(high) if high else 0.0
        ),
        "weighted_relevance_recall": (
            selected_mass / total_mass if total_mass else 0.0
        ),
    }


def oracle_snippets(truth, snippet_lines=32, max_snippets=6):
    n = len(truth)
    stride = max(1, int(snippet_lines) // 4)
    candidates = []
    for left in range(1, n + 1, stride):
        right = min(n, left + int(snippet_lines) - 1)
        left = max(1, right - int(snippet_lines) + 1)
        candidates.append(
            (sum(truth[left - 1:right]), left, right)
        )

    selected = []
    for score, left, right in sorted(
        candidates,
        key=lambda row: (-row[0], row[1]),
    ):
        if overlaps(left, right, selected):
            continue
        selected.append({
            "start_line": left,
            "end_line": right,
            "reference_mass": score,
        })
        if len(selected) >= int(max_snippets):
            break
    return selected


def annotate(selected, truth, source):
    lines = Path(source).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    if len(lines) != len(truth):
        raise ValueError(
            f"source/reference line mismatch: {len(lines)} != {len(truth)}"
        )
    out = []
    for item in selected:
        left = int(item["start_line"])
        right = int(item["end_line"])
        values = truth[left - 1:right]
        out.append({
            **item,
            "reference_mean": (
                sum(values) / len(values) if values else 0.0
            ),
            "reference_max": max(values) if values else 0.0,
            "high_line_count": sum(x >= 0.70 for x in values),
            "content": "\n".join(
                f"{i}: {lines[i - 1]}"
                for i in range(left, right + 1)
            ),
        })
    return out


def evaluate(reference, run, source, snippet_lines=32, max_snippets=6):
    truth = reference_field(reference)
    selected = select_phase0_snippets(
        run,
        len(truth),
        snippet_lines=snippet_lines,
        max_snippets=max_snippets,
    )
    oracle = oracle_snippets(
        truth,
        snippet_lines=snippet_lines,
        max_snippets=max_snippets,
    )
    metrics = truth_metrics(selected, truth)
    oracle_metrics = truth_metrics(oracle, truth)

    return {
        "schema_version": 1,
        "kind": "phase0-final-evidence-quality",
        "subject": run.get("subject"),
        "query": run.get("query"),
        "posterior_estimator": run.get("posterior_estimator"),
        "phase0_probes": run.get("probes"),
        "evidence_policy": {
            "kind": "top-phase0-score-spatially-diverse-context",
            "snippet_lines": int(snippet_lines),
            "max_snippets": int(max_snippets),
        },
        "metrics": metrics,
        "oracle_same_budget": oracle_metrics,
        "oracle_ratio": {
            key: (
                metrics[key] / oracle_metrics[key]
                if oracle_metrics[key] else 0.0
            )
            for key in (
                "mean_reference_relevance",
                "high_line_recall",
                "weighted_relevance_recall",
            )
        },
        "snippets": annotate(selected, truth, source),
        "oracle_snippets": annotate(oracle, truth, source),
    }


def markdown(report):
    m = report["metrics"]
    o = report["oracle_same_budget"]
    lines = [
        "# Phase0 final evidence quality",
        "",
        f"- estimator: {report['posterior_estimator']}",
        f"- Phase0 probes: {report['phase0_probes']}",
        f"- final snippets: {len(report['snippets'])}",
        f"- selected source lines: {m['selected_lines']}",
        "",
        "| metric | Phase0 evidence | oracle same budget |",
        "| --- | ---: | ---: |",
        (
            "| mean reference relevance | "
            f"{m['mean_reference_relevance']:.4f} | "
            f"{o['mean_reference_relevance']:.4f} |"
        ),
        (
            "| high-line precision | "
            f"{m['high_line_precision']:.4f} | "
            f"{o['high_line_precision']:.4f} |"
        ),
        (
            "| high-line recall | "
            f"{m['high_line_recall']:.4f} | "
            f"{o['high_line_recall']:.4f} |"
        ),
        (
            "| weighted relevance recall | "
            f"{m['weighted_relevance_recall']:.4f} | "
            f"{o['weighted_relevance_recall']:.4f} |"
        ),
        "",
        "## Selected snippets",
        "",
    ]
    for index, item in enumerate(report["snippets"], 1):
        lines += [
            (
                f"### Snippet {index}: "
                f"{item['start_line']}-{item['end_line']}"
            ),
            "",
            f"- Phase0 score: {item['phase0_score']:.4f}",
            f"- CC reference mean: {item['reference_mean']:.4f}",
            f"- high-reference lines: {item['high_line_count']}",
            "",
            "~~~text",
            item["content"],
            "~~~",
            "",
        ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--snippet-lines", type=int, default=32)
    parser.add_argument("--max-snippets", type=int, default=6)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    result = evaluate(
        load(args.reference),
        load(args.run),
        args.source,
        snippet_lines=args.snippet_lines,
        max_snippets=args.max_snippets,
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        markdown(result),
        encoding="utf-8",
    )
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
