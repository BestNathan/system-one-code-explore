#!/usr/bin/env python3
"""Blind, rubric-based evaluation of canonical localization results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from claude_reference_trace import (
    claude_stage_cost,
    parse_stream,
    strip_json_fence,
)

DIMENSIONS = {
    "completeness": {
        "weight": 0.25,
        "description": (
            "Coverage of important files and source regions needed to address "
            "the task without redoing localization."
        ),
    },
    "relevance_precision": {
        "weight": 0.15,
        "description": (
            "How consistently the included files and ranges are materially "
            "relevant to the task."
        ),
    },
    "evidence_grounding": {
        "weight": 0.15,
        "description": (
            "How directly and correctly the selected source ranges ground the "
            "claimed relevance."
        ),
    },
    "redundancy_efficiency": {
        "weight": 0.10,
        "description": (
            "How well the result avoids repetitive, overlapping, or excessive "
            "evidence while retaining useful coverage."
        ),
    },
    "downstream_actionability": {
        "weight": 0.20,
        "description": (
            "How effectively an engineer could proceed to design, implement, "
            "review, or debug from this result without repeating discovery."
        ),
    },
    "organization_prioritization": {
        "weight": 0.05,
        "description": (
            "How clearly the output communicates which files/ranges are core "
            "versus supporting context."
        ),
    },
    "risk_uncertainty_coverage": {
        "weight": 0.10,
        "description": (
            "Whether important contextual dependencies, alternative paths, or "
            "uncertainties that could change the downstream plan are covered."
        ),
    },
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def anonymize(result, candidate_id):
    """Remove producer/cost/confidence signals that could anchor the evaluator."""
    files = []
    for item in result.get("files", []):
        files.append({
            "path": item.get("path"),
            "role": item.get("role"),
            "reason": item.get("reason"),
            "evidence": [
                {
                    "start_line": evidence.get("start_line"),
                    "end_line": evidence.get("end_line"),
                    "reason": evidence.get("reason"),
                    "content": evidence.get("content"),
                }
                for evidence in item.get("evidence", [])
            ],
        })
    return {
        "schema_version": 1,
        "kind": "anonymous-code-localization-candidate",
        "candidate_id": candidate_id,
        "task": result.get("task"),
        "summary": result.get("summary"),
        "files": files,
    }


def prompt(candidate):
    rubric = {
        name: {
            "weight_percent": int(spec["weight"] * 100),
            "description": spec["description"],
        }
        for name, spec in DIMENSIONS.items()
    }
    candidate_json = json.dumps(candidate, indent=2, ensure_ascii=False)
    rubric_json = json.dumps(rubric, indent=2, ensure_ascii=False)
    task = candidate.get("task", "")
    candidate_id = candidate["candidate_id"]

    return f"""User task (verbatim):
{task}

You are an independent code-localization quality evaluator.

Evaluate ONE anonymous candidate result against the actual repository at the
checked-out revision. You do not know which system produced it, and you must
not try to infer or identify the producer.

You MAY use Read, Glob, Grep, and read-only Bash to verify the candidate,
inspect potentially important omissions, and determine whether the supplied
evidence is sufficient for the task. Do not modify files. Do not use git
history, GitHub issues, the network, or external context.

This is NOT a request to create a new localization result from scratch.
Investigate only as much as needed to judge the candidate fairly.

Scoring:
- Score every dimension from 0.0 to 10.0.
- Be strict but evidence-based.
- A completeness score does not require exhaustive enumeration of every
  remotely related file. It asks whether important omissions would force a
  downstream engineer to redo discovery or could materially change the plan.
- Redundancy efficiency rewards concise representative evidence, not merely
  fewer lines.
- Downstream actionability asks whether this output can actually advance the
  original task.
- Do not reward or penalize model identity, runtime, token cost, or confidence
  values; those have been intentionally hidden.
- Do not compare against another candidate. Judge only this candidate.

RUBRIC:
{rubric_json}

Return ONLY valid JSON with no Markdown fences in exactly this shape:
{{
  "schema_version": 1,
  "kind": "code-localization-quality-evaluation",
  "candidate_id": "{candidate_id}",
  "task": {task!r},
  "dimensions": {{
    "completeness": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }},
    "relevance_precision": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }},
    "evidence_grounding": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }},
    "redundancy_efficiency": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }},
    "downstream_actionability": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }},
    "organization_prioritization": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }},
    "risk_uncertainty_coverage": {{
      "score": 0.0,
      "reason": "specific evidence-based explanation"
    }}
  }},
  "strengths": [
    "specific strength"
  ],
  "important_omissions": [
    {{
      "path": "repository-relative/path or null",
      "range": "optional line range or null",
      "reason": "why this omission matters"
    }}
  ],
  "redundancies": [
    {{
      "path": "repository-relative/path or null",
      "range": "optional line range or null",
      "reason": "why this content is redundant or excessive"
    }}
  ],
  "downstream_assessment": {{
    "can_proceed": true,
    "reason": "whether an engineer can move forward without substantial rediscovery",
    "recommended_next_step": "what the downstream engineer can do next"
  }},
  "summary": "concise overall quality assessment"
}}

ANONYMOUS CANDIDATE:
{candidate_json}
"""


def parse_assessment_text(value):
    """Extract the evaluation JSON object from model prose/fences robustly."""
    value = strip_json_fence(value)
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(value):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(value[index:])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(parsed, dict)
            and parsed.get("kind")
            == "code-localization-quality-evaluation"
        ):
            return parsed

    preview = value[:1000].replace("\n", " ")
    raise ValueError(
        "evaluator final text did not contain a valid quality-evaluation "
        f"JSON object; preview={preview!r}"
    )


def validate_assessment(candidate, assessment):
    if assessment.get("kind") != "code-localization-quality-evaluation":
        raise ValueError("unexpected evaluation kind")
    if assessment.get("candidate_id") != candidate["candidate_id"]:
        raise ValueError("candidate_id mismatch")

    dimensions = assessment.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("dimensions must be an object")
    if set(dimensions) != set(DIMENSIONS):
        raise ValueError(
            "dimension set mismatch: "
            f"expected={sorted(DIMENSIONS)} actual={sorted(dimensions)}"
        )

    for name in DIMENSIONS:
        item = dimensions[name]
        if not isinstance(item, dict):
            raise ValueError(f"{name} must be an object")
        score = float(item["score"])
        if not 0.0 <= score <= 10.0:
            raise ValueError(f"{name} score outside [0,10]: {score}")
        if not str(item.get("reason", "")).strip():
            raise ValueError(f"{name} reason is required")
        item["score"] = score

    downstream = assessment.get("downstream_assessment")
    if not isinstance(downstream, dict):
        raise ValueError("downstream_assessment is required")
    if not isinstance(downstream.get("can_proceed"), bool):
        raise ValueError("downstream_assessment.can_proceed must be boolean")


def weighted_score(dimensions):
    value = sum(
        float(dimensions[name]["score"]) * DIMENSIONS[name]["weight"]
        for name in DIMENSIONS
    )
    return round(value * 10.0, 2)


def finalize(candidate, raw_jsonl, subject_root, model):
    steps, terminal, final_text = parse_stream(
        raw_jsonl,
        Path(subject_root),
    )
    assessment = parse_assessment_text(final_text)
    validate_assessment(candidate, assessment)

    assessment["overall_score"] = weighted_score(
        assessment["dimensions"]
    )
    assessment["overall_scale"] = "0-100 weighted rubric"
    assessment["rubric"] = {
        name: {
            "weight": spec["weight"],
            "description": spec["description"],
        }
        for name, spec in DIMENSIONS.items()
    }
    assessment["evaluator"] = {
        "system": "claude_code",
        "model": model,
        "tool_calls": len(steps),
    }
    assessment["cost"] = claude_stage_cost(
        "quality_evaluation",
        terminal,
        len(steps),
    )
    return assessment, steps


def markdown(assessment):
    downstream = assessment["downstream_assessment"]
    lines = [
        f"# Localization quality — {assessment['candidate_id']}",
        "",
        f"- Weighted score: **{assessment['overall_score']:.2f}/100**",
        f"- Can proceed: **{downstream['can_proceed']}**",
        f"- Evaluator tool calls: {assessment['evaluator']['tool_calls']}",
        "",
        "## Dimensions",
        "",
        "| Dimension | Weight | Score |",
        "| --- | ---: | ---: |",
    ]
    for name, spec in DIMENSIONS.items():
        score = assessment["dimensions"][name]["score"]
        lines.append(
            f"| {name} | {int(spec['weight'] * 100)}% | {score:.1f}/10 |"
        )

    lines += ["", "## Rationale", ""]
    for name in DIMENSIONS:
        item = assessment["dimensions"][name]
        lines += [f"### {name}", "", item["reason"], ""]

    lines += ["## Strengths", ""]
    strengths = assessment.get("strengths") or []
    lines += [f"- {item}" for item in strengths] or ["- None identified"]

    lines += ["", "## Important omissions", ""]
    omissions = assessment.get("important_omissions") or []
    if omissions:
        for item in omissions:
            location = item.get("path") or "unspecified"
            if item.get("range"):
                location += f":{item['range']}"
            lines.append(f"- {location} — {item.get('reason', '')}")
    else:
        lines.append("- None identified")

    lines += ["", "## Redundancies", ""]
    redundancies = assessment.get("redundancies") or []
    if redundancies:
        for item in redundancies:
            location = item.get("path") or "unspecified"
            if item.get("range"):
                location += f":{item['range']}"
            lines.append(f"- {location} — {item.get('reason', '')}")
    else:
        lines.append("- None identified")

    lines += [
        "",
        "## Downstream assessment",
        "",
        downstream.get("reason", ""),
        "",
        f"Recommended next step: {downstream.get('recommended_next_step', '')}",
        "",
        "## Summary",
        "",
        assessment.get("summary", ""),
        "",
    ]
    return "\n".join(lines)


def combined_report(left, right, left_label, right_label):
    left_dims = left["dimensions"]
    right_dims = right["dimensions"]
    lines = [
        "# Localization quality evaluation report",
        "",
        "> Both candidates were evaluated in separate fresh Claude Code sessions "
        "using the same rubric. Each evaluator saw only one anonymized result "
        "plus the same repository revision. Scores are evaluator judgments, not "
        "ground-truth accuracy measurements.",
        "",
        "## Candidate mapping",
        "",
        f"- {left['candidate_id']} = {left_label}",
        f"- {right['candidate_id']} = {right_label}",
        "",
        "## Overall",
        "",
        "| Candidate | System | Weighted score | Can proceed |",
        "| --- | --- | ---: | --- |",
        (
            f"| {left['candidate_id']} | {left_label} | "
            f"{left['overall_score']:.2f}/100 | "
            f"{left['downstream_assessment']['can_proceed']} |"
        ),
        (
            f"| {right['candidate_id']} | {right_label} | "
            f"{right['overall_score']:.2f}/100 | "
            f"{right['downstream_assessment']['can_proceed']} |"
        ),
        "",
        "## Dimension scores",
        "",
        "| Dimension | Weight | Candidate A | Candidate B |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, spec in DIMENSIONS.items():
        lines.append(
            f"| {name} | {int(spec['weight'] * 100)}% | "
            f"{left_dims[name]['score']:.1f} | "
            f"{right_dims[name]['score']:.1f} |"
        )

    lines += [
        "",
        "## Candidate A summary",
        "",
        left.get("summary", ""),
        "",
        "## Candidate B summary",
        "",
        right.get("summary", ""),
        "",
        "## Candidate A downstream assessment",
        "",
        left["downstream_assessment"].get("reason", ""),
        "",
        "## Candidate B downstream assessment",
        "",
        right["downstream_assessment"].get("reason", ""),
        "",
        "## Interpretation limits",
        "",
        "- The evaluator is Claude Code, so model-specific evaluator bias remains possible.",
        "- Producer identity, cost, and confidence were removed before evaluation, but writing/content patterns may still leak provenance.",
        "- The two sessions are independent and may inspect different repository regions.",
        "- Scores should be treated as structured review evidence, not absolute truth.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--candidate-id", required=True)
    prepare.add_argument("--output-candidate", required=True)
    prepare.add_argument("--output-prompt", required=True)

    finish = sub.add_parser("finalize")
    finish.add_argument("--candidate", required=True)
    finish.add_argument("--raw-jsonl", required=True)
    finish.add_argument("--subject-root", required=True)
    finish.add_argument("--model", required=True)
    finish.add_argument("--output-json", required=True)
    finish.add_argument("--output-markdown", required=True)

    report = sub.add_parser("report")
    report.add_argument("--candidate-a", required=True)
    report.add_argument("--candidate-b", required=True)
    report.add_argument("--output-json", required=True)
    report.add_argument("--output-markdown", required=True)
    report.add_argument("--candidate-a-label", default="System One")
    report.add_argument("--candidate-b-label", default="Claude Code")

    args = parser.parse_args(argv)

    if args.command == "prepare":
        candidate = anonymize(load(args.input), args.candidate_id)
        Path(args.output_candidate).write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        Path(args.output_prompt).write_text(
            prompt(candidate),
            encoding="utf-8",
        )
        return 0

    if args.command == "finalize":
        candidate = load(args.candidate)
        assessment, _ = finalize(
            candidate,
            args.raw_jsonl,
            args.subject_root,
            args.model,
        )
        Path(args.output_json).write_text(
            json.dumps(assessment, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        Path(args.output_markdown).write_text(
            markdown(assessment),
            encoding="utf-8",
        )
        return 0

    left = load(args.candidate_a)
    right = load(args.candidate_b)
    payload = {
        "schema_version": 1,
        "kind": "code-localization-quality-evaluation-report",
        "candidate_mapping": {
            "candidate-a": args.candidate_a_label,
            "candidate-b": args.candidate_b_label,
        },
        "candidate_a": left,
        "candidate_b": right,
    }
    Path(args.output_json).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.output_markdown).write_text(
        combined_report(
            left,
            right,
            args.candidate_a_label,
            args.candidate_b_label,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
