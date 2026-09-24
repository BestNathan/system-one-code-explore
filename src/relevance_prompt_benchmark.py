#!/usr/bin/env python3
"""Benchmark System One relevance prompts against a full-read System 2 field."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from probability_frontier_benchmark import pearson, spearman
from system_one_code_locator import Trace, empty_usage, merge_usage
from system_one_relevance_frontier import ClosureChoiceRelevanceFrontierDecider


PROMPTS = {
    "generic_relevance": (
        "How relevant is the TARGET code block to the user's goal? Return high "
        "probability when the target directly helps answer or implement the goal."
    ),
    "material_evidence": (
        "How likely is the TARGET block to contain MATERIAL EVIDENCE needed for "
        "the goal: implementation details, control flow, state transitions, "
        "contracts or dependencies, edge cases, invariants, or constraints? "
        "Penalize merely topical names, boilerplate, logging, and redundant scaffolding."
    ),
    "counterfactual_answer_impact": (
        "Imagine a strong coding agent must solve the goal but this TARGET block "
        "is removed from its evidence. How likely is the final technical answer "
        "to lose a concrete necessary fact, mechanism, constraint, or edge case?"
    ),
    "minimal_evidence_keep": (
        "An expert is building the smallest evidence set sufficient to solve the "
        "goal. How likely would the expert KEEP this TARGET block because it adds "
        "distinct grounded information that should survive into that minimal set?"
    ),
    "mechanism_match": (
        "Does the TARGET block directly explain a mechanism the goal asks about: "
        "implementation, control flow, lifecycle or state transition, data movement, "
        "dependency or contract, failure mode, or constraint? Score direct mechanism "
        "evidence high and nearby but incidental context low."
    ),
}


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


def bucket(score):
    if score >= 0.70:
        return "high"
    if score >= 0.35:
        return "mid"
    return "low"


def evenly_take(items, count):
    if len(items) <= count:
        return list(items)
    if count <= 1:
        return [items[len(items) // 2]]
    positions = [
        round(i * (len(items) - 1) / (count - 1))
        for i in range(count)
    ]
    return [items[i] for i in positions]


def build_examples(
    reference,
    source_path,
    *,
    target_lines=8,
    context_lines=24,
    per_bucket=10,
):
    truth = reference_field(reference)
    source = Path(source_path).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    if len(source) != len(truth):
        raise ValueError(
            f"source/reference mismatch: {len(source)} != {len(truth)}"
        )

    candidates = []
    stride = max(4, int(target_lines) * 2)
    for start in range(1, len(source) + 1, stride):
        end = min(len(source), start + int(target_lines) - 1)
        values = truth[start - 1:end]
        score = sum(values) / len(values)
        before_start = max(1, start - int(context_lines))
        after_end = min(len(source), end + int(context_lines))
        candidates.append({
            "id": f"l{start}-{end}",
            "start_line": start,
            "end_line": end,
            "reference_score": score,
            "bucket": bucket(score),
            "context_before": "\n".join(
                f"{i}: {source[i - 1]}"
                for i in range(before_start, start)
            ),
            "target": "\n".join(
                f"{i}: {source[i - 1]}"
                for i in range(start, end + 1)
            ),
            "context_after": "\n".join(
                f"{i}: {source[i - 1]}"
                for i in range(end + 1, after_end + 1)
            ),
        })

    selected = []
    for name in ("high", "mid", "low"):
        group = [x for x in candidates if x["bucket"] == name]
        selected.extend(evenly_take(group, int(per_bucket)))
    selected.sort(key=lambda item: item["start_line"])
    return selected


def roc_auc(scores, labels):
    positives = [s for s, y in zip(scores, labels) if y]
    negatives = [s for s, y in zip(scores, labels) if not y]
    if not positives or not negatives:
        return None
    wins = 0.0
    total = len(positives) * len(negatives)
    for pos in positives:
        for neg in negatives:
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / total


def evaluate_predictions(examples, predictions):
    truth = [float(item["reference_score"]) for item in examples]
    pred = [float(predictions[item["id"]]) for item in examples]
    high = [value >= 0.70 for value in truth]
    high_scores = [
        p for p, item in zip(pred, examples)
        if item["bucket"] == "high"
    ]
    mid_scores = [
        p for p, item in zip(pred, examples)
        if item["bucket"] == "mid"
    ]
    low_scores = [
        p for p, item in zip(pred, examples)
        if item["bucket"] == "low"
    ]

    k = sum(high)
    ranked = sorted(range(len(pred)), key=lambda i: (-pred[i], i))
    top = ranked[:k] if k else []
    precision_at_k = (
        sum(high[i] for i in top) / len(top)
        if top else 0.0
    )
    brier = (
        sum(
            (score - (1.0 if label else 0.0)) ** 2
            for score, label in zip(pred, high)
        ) / len(pred)
        if pred else 0.0
    )

    mean_high = (
        sum(high_scores) / len(high_scores) if high_scores else None
    )
    mean_mid = (
        sum(mid_scores) / len(mid_scores) if mid_scores else None
    )
    mean_low = (
        sum(low_scores) / len(low_scores) if low_scores else None
    )

    return {
        "examples": len(examples),
        "high_examples": sum(high),
        "pearson": pearson(pred, truth),
        "spearman": spearman(pred, truth),
        "high_vs_rest_auc": roc_auc(pred, high),
        "precision_at_high_count": precision_at_k,
        "brier_high_label": brier,
        "mean_high_probability": mean_high,
        "mean_mid_probability": mean_mid,
        "mean_low_probability": mean_low,
        "high_low_separation": (
            mean_high - mean_low
            if mean_high is not None and mean_low is not None
            else None
        ),
    }


def score_prompt(
    decider,
    goal,
    file_path,
    examples,
    prompt_name,
    prompt_text,
    batch_size=6,
):
    usage = empty_usage()
    predictions = {}
    for offset in range(0, len(examples), int(batch_size)):
        batch = examples[offset:offset + int(batch_size)]
        questions = {}
        for index, item in enumerate(batch):
            questions[f"sample_{index}"] = {
                "type": "noul",
                "instructions": {
                    "goal": goal,
                    "file": file_path,
                    "target_range": [
                        item["start_line"],
                        item["end_line"],
                    ],
                    "context_before": item["context_before"],
                    "target": item["target"],
                    "context_after": item["context_after"],
                    "question": prompt_text,
                    "important": (
                        "Score TARGET only. Surrounding code exists only to "
                        "resolve references and control flow."
                    ),
                },
                "criteria": {
                    "true": (
                        "TARGET itself is direct useful evidence for the goal."
                    ),
                    "false": (
                        "TARGET is incidental, redundant, generic, or does not "
                        "materially help solve the goal."
                    ),
                },
            }

        response, current_usage = decider.send(
            f"prompt_calibration_{prompt_name}",
            {
                "goal": goal,
                "file": file_path,
                "prompt_variant": prompt_name,
            },
            questions,
        )
        merge_usage(usage, current_usage)
        answers = response.get("answers", {})
        for index, item in enumerate(batch):
            answer = answers.get(f"sample_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected Noul answer: {answer!r}"
                )
            predictions[item["id"]] = float(answer["noul"])
    return predictions, usage


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trace-file")
    parser.add_argument("--per-bucket", type=int, default=10)
    parser.add_argument(
        "--model",
        default=os.getenv("TYPESAFE_MODEL", "jev-latest"),
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv(
            "TYPESAFE_API_URL",
            "https://api.typesafe.ai/v1/systemone",
        ),
    )
    args = parser.parse_args(argv)

    api_key = os.getenv("TYPESAFE_API_KEY", "")
    if not api_key:
        raise SystemExit("TYPESAFE_API_KEY is required")

    reference = load(args.reference)
    examples = build_examples(
        reference,
        args.source,
        per_bucket=args.per_bucket,
    )
    trace = Trace(args.trace_file)
    decider = ClosureChoiceRelevanceFrontierDecider(
        api_key,
        trace,
        args.endpoint,
        args.model,
    )

    result = {
        "schema_version": 1,
        "kind": "system-one-relevance-prompt-calibration",
        "goal": args.goal,
        "file_path": args.file_path,
        "model": args.model,
        "examples": [
            {
                key: value
                for key, value in item.items()
                if key not in {
                    "context_before",
                    "target",
                    "context_after",
                }
            }
            for item in examples
        ],
        "prompts": {},
    }

    for name, prompt in PROMPTS.items():
        predictions, usage = score_prompt(
            decider,
            args.goal,
            args.file_path,
            examples,
            name,
            prompt,
        )
        result["prompts"][name] = {
            "prompt": prompt,
            "metrics": evaluate_predictions(examples, predictions),
            "predictions": predictions,
            "usage": usage,
        }

    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            name: value["metrics"]
            for name, value in result["prompts"].items()
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
