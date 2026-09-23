#!/usr/bin/env python3
"""Canonical structured output for code-localization experiments."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path


SCHEMA_VERSION = 1
KIND = "code-localization-result"
DRAFT_KIND = "code-localization-draft"
CONFIDENCE_KIND = "code-localization-confidence-assessment"
ROLES = {"relevant", "primary", "supporting", "context", "unknown"}


def subject_identity(repository, revision):
    if not repository or not revision:
        return None
    return {
        "repository": str(repository),
        "revision": str(revision),
    }


def attach_subject(result, subject):
    if subject is not None:
        result["subject"] = {
            "repository": str(subject["repository"]),
            "revision": str(subject["revision"]),
        }
    return result


def confidence_label(score):
    if score is None:
        return "unknown"
    score = float(score)
    if score >= 0.80:
        return "high"
    if score >= 0.60:
        return "medium"
    return "low"


def confidence(score, kind, basis=None):
    if score is None:
        return None
    value = max(0.0, min(1.0, float(score)))
    out = {
        "score": round(value, 6),
        "label": confidence_label(value),
        "type": kind,
    }
    if basis:
        out["basis"] = basis
    return out


def materialize_range(root, path, start_line, end_line):
    source = (Path(root) / path).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    start = max(1, int(start_line))
    end = min(len(source), int(end_line))
    if start > end:
        return ""
    return "\n".join(
        f"{line_number}: {source[line_number - 1]}"
        for line_number in range(start, end + 1)
    )


def normalize_tokens(usage):
    usage = usage or {}
    details = usage.get("output_tokens_details") or {}
    return {
        "input": int(usage.get("input_tokens", 0) or 0),
        "output": int(usage.get("output_tokens", 0) or 0),
        "cache_read_input": int(
            usage.get("cache_read_input_tokens", 0) or 0
        ),
        "cache_creation_input": int(
            usage.get("cache_creation_input_tokens", 0) or 0
        ),
        "thinking": int(details.get("thinking_tokens", 0) or 0),
    }


def add_tokens(total, current):
    for key in total:
        total[key] += int(current.get(key, 0) or 0)


def provider_cost_usd(model_usage):
    total = 0.0
    found = False
    for item in (model_usage or {}).values():
        if not isinstance(item, dict):
            continue
        value = item.get("costUSD")
        if value is None:
            continue
        total += float(value)
        found = True
    return round(total, 12) if found else None


def claude_stage_cost(name, terminal, tool_calls=0):
    return {
        "name": name,
        "elapsed_ms": int(terminal.get("duration_ms", 0) or 0),
        "api_elapsed_ms": int(terminal.get("duration_api_ms", 0) or 0),
        "model_calls": None,
        "turns": int(terminal.get("num_turns", 0) or 0),
        "tool_calls": int(tool_calls or 0),
        "tokens": normalize_tokens(terminal.get("usage")),
        "provider_cost_usd": provider_cost_usd(
            terminal.get("modelUsage")
        ),
    }


def aggregate_cost(stages, elapsed_semantics):
    tokens = {
        "input": 0,
        "output": 0,
        "cache_read_input": 0,
        "cache_creation_input": 0,
        "thinking": 0,
    }
    elapsed_ms = 0
    api_elapsed_ms = 0
    turns = 0
    tool_calls = 0
    model_calls = 0
    model_calls_known = True
    provider_cost = 0.0
    provider_cost_known = False

    for stage in stages:
        elapsed_ms += int(stage.get("elapsed_ms", 0) or 0)
        api_elapsed_ms += int(stage.get("api_elapsed_ms", 0) or 0)
        turns += int(stage.get("turns", 0) or 0)
        tool_calls += int(stage.get("tool_calls", 0) or 0)
        if stage.get("model_calls") is None:
            model_calls_known = False
        else:
            model_calls += int(stage.get("model_calls", 0) or 0)
        add_tokens(tokens, stage.get("tokens") or {})
        if stage.get("provider_cost_usd") is not None:
            provider_cost += float(stage["provider_cost_usd"])
            provider_cost_known = True

    return {
        "elapsed_ms": elapsed_ms,
        "api_elapsed_ms": api_elapsed_ms or None,
        "elapsed_semantics": elapsed_semantics,
        "model_calls": model_calls if model_calls_known else None,
        "turns": turns or None,
        "tool_calls": tool_calls or 0,
        "tokens": tokens,
        "provider_cost_usd": (
            round(provider_cost, 12)
            if provider_cost_known
            else None
        ),
        "stages": stages,
    }


def system_one_cost(engine_result):
    metrics = engine_result.get("metrics") or {}
    stage = {
        "name": "localization",
        "elapsed_ms": int(metrics.get("elapsed_ms", 0) or 0),
        "api_elapsed_ms": None,
        "model_calls": int(metrics.get("model_calls", 0) or 0),
        "turns": None,
        "tool_calls": 0,
        "tokens": {
            "input": int(metrics.get("input_tokens", 0) or 0),
            "output": int(metrics.get("output_tokens", 0) or 0),
            "cache_read_input": 0,
            "cache_creation_input": 0,
            "thinking": 0,
        },
        "provider_cost_usd": None,
        "operations": {
            "reads_executed": int(
                metrics.get("reads_executed", 0) or 0
            ),
            "scheduler_rounds": int(
                metrics.get("reader_scheduler_rounds", 0) or 0
            ),
        },
    }
    return aggregate_cost(
        [stage],
        "end-to-end System One localization harness runtime",
    )


def validate_cost(cost):
    if not isinstance(cost, dict):
        raise ValueError("localization result requires cost")
    tokens = cost.get("tokens")
    if not isinstance(tokens, dict):
        raise ValueError("localization result cost requires tokens")
    for name in (
        "input",
        "output",
        "cache_read_input",
        "cache_creation_input",
        "thinking",
    ):
        value = tokens.get(name)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid cost token field: {name}")
    elapsed = cost.get("elapsed_ms")
    if not isinstance(elapsed, int) or elapsed < 0:
        raise ValueError("invalid cost.elapsed_ms")
    if not isinstance(cost.get("stages"), list):
        raise ValueError("localization result cost requires stages[]")


def validate(result):
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported localization result schema_version")
    if result.get("kind") != KIND:
        raise ValueError("invalid localization result kind")
    if not isinstance(result.get("task"), str) or not result["task"]:
        raise ValueError("localization result requires task")
    producer = result.get("producer")
    if not isinstance(producer, dict) or not producer.get("system"):
        raise ValueError("localization result requires producer.system")
    subject = result.get("subject")
    if subject is not None:
        if not isinstance(subject, dict):
            raise ValueError("localization result subject must be an object")
        if not subject.get("repository") or not subject.get("revision"):
            raise ValueError(
                "localization result subject requires repository and revision"
            )
    validate_cost(result.get("cost"))
    files = result.get("files")
    if not isinstance(files, list):
        raise ValueError("localization result requires files[]")

    seen = set()
    for item in files:
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("localization file requires path")
        if path in seen:
            raise ValueError(f"duplicate localization file: {path}")
        seen.add(path)
        if item.get("role", "unknown") not in ROLES:
            raise ValueError(
                f"invalid role for {path}: {item.get('role')}"
            )
        if not isinstance(item.get("evidence"), list):
            raise ValueError(
                f"localization file requires evidence[]: {path}"
            )
        for evidence in item["evidence"]:
            start = evidence.get("start_line")
            end = evidence.get("end_line")
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError(
                    f"evidence requires integer line range: {path}"
                )
            if start < 1 or end < start:
                raise ValueError(
                    f"invalid evidence range: {path}:{start}-{end}"
                )
    return result


def validate_draft(draft):
    if draft.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported localization draft schema_version")
    if draft.get("kind") != DRAFT_KIND:
        raise ValueError("invalid localization draft kind")
    if "confidence" in draft:
        raise ValueError(
            "localization session must not emit confidence"
        )
    if not isinstance(draft.get("task"), str) or not draft["task"]:
        raise ValueError("localization draft requires task")
    if not isinstance(draft.get("files"), list):
        raise ValueError("localization draft requires files[]")

    seen = set()
    for item in draft["files"]:
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("localization draft file requires path")
        if path in seen:
            raise ValueError(f"duplicate localization draft file: {path}")
        seen.add(path)
        if "confidence" in item:
            raise ValueError(
                f"localization session emitted file confidence: {path}"
            )
        if item.get("role", "unknown") not in ROLES:
            raise ValueError(f"invalid role for {path}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            raise ValueError(f"draft requires evidence[]: {path}")
        for region in evidence:
            if "confidence" in region:
                raise ValueError(
                    "localization session emitted evidence confidence: "
                    f"{path}"
                )
            start = region.get("start_line")
            end = region.get("end_line")
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError(
                    f"draft evidence requires integer range: {path}"
                )
            if start < 1 or end < start:
                raise ValueError(
                    f"invalid draft range: {path}:{start}-{end}"
                )
    return draft


def normalize_claude_draft(raw, subject_root, model=None):
    """Validate localization-only output and materialize cited source."""
    draft = deepcopy(raw)
    draft.setdefault("schema_version", SCHEMA_VERSION)
    draft.setdefault("kind", DRAFT_KIND)
    producer = draft.setdefault("producer", {})
    producer["system"] = "claude_code"
    if model:
        producer["model"] = model

    for file_item in draft.get("files", []):
        file_item.setdefault("role", "unknown")
        for index, evidence in enumerate(
            file_item.get("evidence", []),
            1,
        ):
            evidence.setdefault(
                "id",
                f"{file_item['path']}#evidence-{index}",
            )
            evidence["content"] = materialize_range(
                subject_root,
                file_item["path"],
                evidence["start_line"],
                evidence["end_line"],
            )
    return validate_draft(draft)


def validate_confidence_assessment(assessment, draft):
    if assessment.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "unsupported confidence assessment schema_version"
        )
    if assessment.get("kind") != CONFIDENCE_KIND:
        raise ValueError("invalid confidence assessment kind")
    if assessment.get("task") != draft.get("task"):
        raise ValueError("confidence assessment task changed")

    overall = assessment.get("overall")
    if not isinstance(overall, dict):
        raise ValueError("confidence assessment requires overall")
    float(overall["score"])

    draft_files = draft.get("files", [])
    assessed_files = assessment.get("files")
    if not isinstance(assessed_files, list):
        raise ValueError("confidence assessment requires files[]")
    if len(draft_files) != len(assessed_files):
        raise ValueError(
            "confidence assessment changed file count"
        )

    for draft_file, assessed_file in zip(
        draft_files,
        assessed_files,
    ):
        if assessed_file.get("path") != draft_file.get("path"):
            raise ValueError(
                "confidence assessment changed file order/path"
            )
        float(assessed_file["score"])
        draft_evidence = draft_file.get("evidence", [])
        assessed_evidence = assessed_file.get("evidence")
        if not isinstance(assessed_evidence, list):
            raise ValueError(
                f"confidence assessment missing evidence: "
                f"{draft_file['path']}"
            )
        if len(draft_evidence) != len(assessed_evidence):
            raise ValueError(
                "confidence assessment changed evidence count: "
                f"{draft_file['path']}"
            )
        for draft_region, assessed_region in zip(
            draft_evidence,
            assessed_evidence,
        ):
            if (
                int(assessed_region.get("start_line", -1))
                != int(draft_region["start_line"])
                or int(assessed_region.get("end_line", -1))
                != int(draft_region["end_line"])
            ):
                raise ValueError(
                    "confidence assessment changed evidence range: "
                    f"{draft_file['path']}"
                )
            float(assessed_region["score"])
    return assessment


def build_claude_result(
    draft,
    assessment,
    model,
    localization_stage,
    confidence_stage,
    subject=None,
):
    validate_draft(draft)
    validate_confidence_assessment(assessment, draft)

    files = []
    for draft_file, assessed_file in zip(
        draft["files"],
        assessment["files"],
    ):
        evidence = []
        for draft_region, assessed_region in zip(
            draft_file["evidence"],
            assessed_file["evidence"],
        ):
            evidence.append({
                **draft_region,
                "confidence": confidence(
                    assessed_region["score"],
                    "model_self_assessment",
                    assessed_region.get("reason")
                    or "fresh-session evidence confidence assessment",
                ),
            })

        files.append({
            **draft_file,
            "confidence": confidence(
                assessed_file["score"],
                "model_self_assessment",
                assessed_file.get("reason")
                or "fresh-session file confidence assessment",
            ),
            "evidence": evidence,
        })

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "task": draft["task"],
        "producer": {
            "system": "claude_code",
            "model": model,
            "confidence_semantics": (
                "File/evidence confidence is assigned by a second, "
                "fresh Claude Code session after localization is complete. "
                "The assessment session cannot alter files or ranges."
            ),
        },
        "summary": draft.get("summary", ""),
        "confidence": confidence(
            assessment["overall"]["score"],
            "model_self_assessment",
            assessment["overall"].get("reason")
            or "fresh-session overall confidence assessment",
        ),
        "cost": aggregate_cost(
            [localization_stage, confidence_stage],
            "sum of two independent Claude Code session durations",
        ),
        "files": files,
    }
    attach_subject(result, subject)
    return validate(result)


def build_system_one_result(engine_result, model=None):
    state_files = {}
    for state in engine_result.get("reader_states", []):
        for item in state.get("files", []):
            state_files[item["path"]] = item

    by_path = {}
    for snippet in engine_result.get("snippets", []):
        by_path.setdefault(snippet["path"], []).append(snippet)

    files = []
    for path, snippets in by_path.items():
        snippets = sorted(
            snippets,
            key=lambda item: (
                -float(item["score"]),
                item["start_line"],
            ),
        )
        file_state = state_files.get(path, {})
        max_score = max(float(item["score"]) for item in snippets)
        evidence = []
        for index, item in enumerate(
            sorted(snippets, key=lambda row: row["start_line"]),
            1,
        ):
            evidence.append({
                "id": f"{path}#evidence-{index}",
                "start_line": int(item["start_line"]),
                "end_line": int(item["end_line"]),
                "confidence": confidence(
                    item["score"],
                    "noul_relevance",
                    "System One observation relevance score",
                ),
                "reason": (
                    "Observed source range retained because its "
                    "relevance score met the evidence threshold."
                ),
                "content": item.get("content", ""),
                "provenance": {
                    "action_probability": item.get(
                        "action_probability"
                    ),
                },
            })

        files.append({
            "path": path,
            "role": "relevant",
            "confidence": confidence(
                max_score,
                "derived_max_evidence_relevance",
                "maximum retained observation relevance for this file",
            ),
            "reason": (
                "System One retained at least one observed source "
                "range from this file as relevant evidence."
            ),
            "evidence": evidence,
            "provenance": {
                "phase1_score": file_state.get("phase1_score"),
                "last_activation_score": file_state.get(
                    "last_activation_score"
                ),
                "activation_count": file_state.get(
                    "activation_count",
                    0,
                ),
                "read_count": file_state.get("read_count", 0),
                "stop_reason": file_state.get("stop_reason"),
            },
        })

    files.sort(
        key=lambda item: (
            -item["confidence"]["score"],
            item["path"],
        )
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "task": engine_result.get("query", ""),
        "producer": {
            "system": "system_one",
            "model": model or engine_result.get("model"),
            "confidence_semantics": (
                "Evidence confidence is System One Noul relevance. "
                "File confidence is the maximum retained evidence "
                "relevance."
            ),
        },
        "summary": {
            "valuable_files": len(files),
            "evidence_regions": sum(
                len(item["evidence"]) for item in files
            ),
            "note": (
                "Only retained evidence is listed. Phase-1 candidates "
                "and deferred/stopped files remain available in the "
                "execution result."
            ),
        },
        "confidence": None,
        "cost": system_one_cost(engine_result),
        "files": files,
    }
    attach_subject(result, engine_result.get("subject"))
    return validate(result)


def build_system_one_range_result(engine_result, model=None):
    """Build the canonical result from the independent per-file range runtime."""
    files = []
    for item in engine_result.get("result_files", []):
        path = item["path"]
        evidence = []
        for index, region in enumerate(item.get("evidence", []), 1):
            evidence.append({
                "id": f"{path}#evidence-{index}",
                "start_line": int(region["start_line"]),
                "end_line": int(region["end_line"]),
                "confidence": confidence(
                    region["score"],
                    "noul_relevance",
                    "post-navigation System One evidence relevance",
                ),
                "reason": (
                    "Observed range retained by the per-file range runtime "
                    "because its post-navigation relevance met the evidence "
                    "threshold."
                ),
                "content": region.get("content", ""),
                "provenance": {
                    "navigation": region.get("navigation"),
                    "selected_action_score": region.get(
                        "selected_action_score"
                    ),
                },
            })

        files.append({
            "path": path,
            "role": "relevant",
            "confidence": confidence(
                item["score"],
                "derived_max_evidence_relevance",
                "maximum retained evidence relevance for this file",
            ),
            "reason": (
                "The independent FileRuntime retained at least one "
                "representative evidence range from this file."
            ),
            "evidence": evidence,
            "provenance": {
                "phase1_score": item.get("phase1_score"),
                "termination": item.get("termination"),
                "read_count": item.get("read_count", 0),
                "coverage": item.get("coverage", []),
            },
        })

    files.sort(
        key=lambda item: (
            -item["confidence"]["score"],
            item["path"],
        )
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "task": engine_result.get("query", ""),
        "producer": {
            "system": "system_one",
            "model": model or engine_result.get("model"),
            "confidence_semantics": (
                "Evidence confidence is post-navigation System One Noul "
                "relevance. File confidence is the maximum retained "
                "evidence relevance."
            ),
            "algorithm": "independent_file_range_runtime",
        },
        "summary": {
            "valuable_files": len(files),
            "evidence_regions": sum(
                len(item["evidence"]) for item in files
            ),
            "file_runtimes": (
                engine_result.get("metrics") or {}
            ).get("file_runtimes"),
        },
        "confidence": None,
        "cost": system_one_cost(engine_result),
        "files": files,
    }
    attach_subject(result, engine_result.get("subject"))
    return validate(result)
