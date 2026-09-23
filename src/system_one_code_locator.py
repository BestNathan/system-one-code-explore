#!/usr/bin/env python3
"""System One two-phase progressive code-localization research demo."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from localization_result import build_system_one_result

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 522, 523, 524, 529}
MAX_REQUEST_ATTEMPTS = 5
IGNORE = {".git", ".idea", ".vscode", ".venv", "node_modules", "target", "dist", "build", "__pycache__"}
SUFFIXES = {".py", ".rs", ".go", ".java", ".ts", ".tsx", ".js", ".jsx", ".vue", ".proto", ".sql", ".sh", ".yaml", ".yml", ".toml", ".md"}

DEFAULT_DIRECTORY_THRESHOLD = 0.50
DEFAULT_FILE_THRESHOLD = 0.65

DEFAULT_READER_FILE_ACTIVATION_THRESHOLD = 0.65
DEFAULT_READER_WINDOW_LINES = 140
DEFAULT_READER_SOFT_READS = 4
DEFAULT_READER_HARD_READS = 8
DEFAULT_READER_ACTION_THRESHOLD = 0.40
DEFAULT_OBSERVATION_THRESHOLD = 0.65
MAX_RELEVANT_REGIONS = 3
MAX_ACTIONS_PER_FILE = 8


class Trace:
    def __init__(self, path):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("")

    def emit(self, event, **data):
        if not self.path:
            return
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **data}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def empty_usage():
    return {"model_calls": 0, "input_tokens": 0, "output_tokens": 0}


def merge_usage(total, current):
    for key in total:
        total[key] += int(current.get(key, 0) or 0)


def sanitize_source(value):
    if not isinstance(value, str):
        return value
    patterns = [
        (r'"(?:\\.|[^"\\])*"', '"<string>"'),
        (r"'(?:\\.|[^'\\])*'", "'<string>'"),
    ]
    for pattern, replacement in patterns:
        value = re.sub(pattern, replacement, value)
    return value


def reader_model_state(state):
    return {
        "goal": state["goal"],
        "phase": "global_progressive_reader",
        "round": state["round"],
        "thresholds": state.get("thresholds", {}),
        "budget": state.get("budget", {}),
        "files": [
            {
                "path": item["path"],
                "phase1_score": item["phase1_score"],
                "stat": item["stat"],
                "coverage": item["coverage"],
                "read_count": item.get("read_count", 0),
                "activation_count": item.get("activation_count", 0),
                "last_activation_score": item.get("last_activation_score"),
                "stopped": item["stopped"],
                "stop_reason": item.get("stop_reason"),
            }
            for item in state["files"]
        ],
        "observations": [
            {
                "id": item["id"],
                "path": item["path"],
                "start_line": item["start_line"],
                "end_line": item["end_line"],
                "content": sanitize_source(item["content"]),
                "relevance": item.get("relevance"),
                "action_probability": item.get("action_probability"),
            }
            for item in state["observations"]
        ],
        "policy": (
            "Read observations are part of state. Use prior content and coverage "
            "to choose the next information-gathering action."
        ),
    }


class SystemOneDecider:
    def __init__(self, key, trace, endpoint=API_URL, model=MODEL):
        self.key = key
        self.trace = trace
        self.endpoint = endpoint
        self.model = model

    def request(self, payload):
        body = json.dumps(payload).encode()
        for attempt in range(MAX_REQUEST_ATTEMPTS):
            request = urllib.request.Request(
                self.endpoint,
                data=body,
                method="POST",
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                retryable = exc.code in TRANSIENT_HTTP_STATUS
                if not retryable or attempt == MAX_REQUEST_ATTEMPTS - 1:
                    raise RuntimeError(f"TypeSafe HTTP {exc.code}: {detail[:2000]}") from exc
                delay = 2 ** attempt
                self.trace.emit("system_one_retry", status=exc.code, attempt=attempt + 1, delay_seconds=delay)
                time.sleep(delay)
            except urllib.error.URLError as exc:
                if attempt == MAX_REQUEST_ATTEMPTS - 1:
                    raise RuntimeError(f"TypeSafe transport error: {exc}") from exc
                delay = 2 ** attempt
                self.trace.emit("system_one_retry", status="transport", attempt=attempt + 1, delay_seconds=delay)
                time.sleep(delay)

    def send(self, stage, state, questions):
        payload = {"state": state, "model": self.model, "questions": questions}
        self.trace.emit(
            "system_one_request",
            stage=stage,
            request_bytes=len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            question_count=len(questions),
            request=payload,
        )
        started = time.perf_counter()
        response = self.request(payload)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        raw_usage = response.get("usage", {})
        self.trace.emit(
            "system_one_response",
            stage=stage,
            latency_ms=latency_ms,
            model=response.get("model"),
            usage=raw_usage,
            answers=response.get("answers", {}),
        )
        return response, {
            "model_calls": 1,
            "input_tokens": int(raw_usage.get("input_tokens", 0) or 0),
            "output_tokens": int(raw_usage.get("output_tokens", 0) or 0),
        }

    def score_candidates(self, query, stage, candidates):
        if not candidates:
            return [], empty_usage()
        questions = {}
        for index, candidate in enumerate(candidates):
            questions[f"candidate_{index}"] = {
                "type": "noul",
                "instructions": {
                    "task": query,
                    "candidate": candidate["payload"],
                    "question": (
                        "Would retaining this candidate materially help locate "
                        "source code relevant to the task?"
                    ),
                },
                "criteria": {
                    "true": "Likely to contain or directly lead to implementation evidence.",
                    "false": "Unlikely to help locate the requested implementation.",
                },
            }
        response, usage = self.send(
            stage,
            {"goal": query, "phase": "file_locator", "candidate_count": len(candidates)},
            questions,
        )
        answers = response.get("answers", {})
        scored = []
        for index, candidate in enumerate(candidates):
            answer = answers.get(f"candidate_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(f"unexpected candidate answer: {answer!r}")
            scored.append({**candidate, "score": float(answer["noul"])})
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        return scored, usage

    score = score_candidates

    def score_reader_files(self, query, state, file_states):
        """Score every eligible file in one global scheduling request."""
        if not file_states:
            return [], empty_usage()

        questions = {}
        for index, file_state in enumerate(file_states):
            latest = (
                file_state["observations"][-1]
                if file_state.get("observations")
                else None
            )
            questions[f"file_{index}"] = {
                "type": "noul",
                "instructions": {
                    "task": query,
                    "file": {
                        "path": file_state["path"],
                        "phase1_score": file_state["phase1_score"],
                        "stat": file_state["stat"],
                        "coverage": file_state["coverage"],
                        "read_count": file_state.get("read_count", 0),
                        "latest_observation_relevance": (
                            latest.get("relevance") if latest else None
                        ),
                    },
                    "question": (
                        "Given the complete current reader state, should this file "
                        "receive a read action now? Score whether reading it in the "
                        "next step is likely to add useful information for the task."
                    ),
                },
                "criteria": {
                    "true": (
                        "Reading this file now is a useful next information-gathering "
                        "step relative to the other available files and observations."
                    ),
                    "false": (
                        "This file should be deferred or stopped for now because other "
                        "files/actions are more useful or enough evidence already exists."
                    ),
                },
            }

        response, usage = self.send(
            "reader_file_priority",
            reader_model_state(state),
            questions,
        )
        answers = response.get("answers", {})
        scored = []
        for index, file_state in enumerate(file_states):
            answer = answers.get(f"file_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected reader-file answer: {answer!r}"
                )
            scored.append({
                "path": file_state["path"],
                "score": float(answer["noul"]),
            })
        return scored, usage

    def choose_read_actions(self, query, state, action_sets):
        """One Choice question per file, all files decided in one request."""
        if not action_sets:
            return [], empty_usage()

        questions = {}
        lookup = {}
        for file_index, item in enumerate(action_sets):
            question_id = f"file_{file_index}"
            criteria = {}
            option_lookup = {}
            read_index = 0
            for action in item["actions"]:
                if action["kind"] == "stop_file":
                    option = "stop"
                    criteria[option] = {
                        "action": "stop reading this file",
                        "reason": "Current evidence is sufficient or another read is not justified.",
                    }
                else:
                    option = f"read_{read_index}"
                    read_index += 1
                    criteria[option] = {
                        "action": "read_file",
                        "path": action["path"],
                        "start_line": action["start_line"],
                        "end_line": action["end_line"],
                        "reason_available": action["reason"],
                    }
                option_lookup[option] = action

            questions[question_id] = {
                "type": "choice",
                "instructions": {
                    "task": query,
                    "file": item["path"],
                    "question": (
                        "Choose the single next action most likely to increase useful "
                        "information about the task. Use observations already in state. "
                        "Choose stop when another read is not justified."
                    ),
                },
                "criteria": criteria,
            }
            lookup[question_id] = option_lookup

        response, usage = self.send("reader_action", reader_model_state(state), questions)
        answers = response.get("answers", {})
        decisions = []
        for question_id, option_lookup in lookup.items():
            answer = answers.get(question_id, {})
            if answer.get("type") != "choice":
                raise RuntimeError(f"unexpected read-action answer: {answer!r}")
            choice = answer["choice"]
            action = option_lookup.get(choice)
            if action is None:
                raise RuntimeError(f"unknown choice {choice!r} for {question_id}")
            probabilities = answer.get("probabilities", {})
            decisions.append({
                "path": action["path"],
                "action": action,
                "choice": choice,
                "probability": float(probabilities.get(choice, 0.0) or 0.0),
                "confidence": float(answer.get("confidence", 0.0) or 0.0),
                "probabilities": probabilities,
            })
        return decisions, usage

    def score_observations(self, query, state, observation_ids):
        """Observations are in state before this relevance request is made."""
        if not observation_ids:
            return {}, empty_usage()

        questions = {}
        for index, observation_id in enumerate(observation_ids):
            questions[f"observation_{index}"] = {
                "type": "noul",
                "instructions": {
                    "observation_id": observation_id,
                    "question": (
                        "In state.observations, find the observation whose id equals "
                        "observation_id. Does that observed source content materially "
                        "help answer the task?"
                    ),
                },
                "criteria": {
                    "true": "Contains relevant implementation evidence, behavior, dependencies, or strong clues.",
                    "false": "Does not materially help answer the task.",
                },
            }

        response, usage = self.send(
            "observation_relevance",
            reader_model_state(state),
            questions,
        )
        answers = response.get("answers", {})
        scores = {}
        for index, observation_id in enumerate(observation_ids):
            answer = answers.get(f"observation_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(f"unexpected observation answer: {answer!r}")
            scores[observation_id] = float(answer["noul"])
        return scores, usage


class OfflineDecider:
    """Deterministic fixture decider; not a model-quality simulation."""

    model = "offline-lexical-fixture"

    def __init__(self, trace):
        self.trace = trace

    def lexical_score(self, query, value):
        tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", query.lower()))
        if "websocket" in tokens:
            tokens |= {"ws", "socket", "connect", "connection", "reconnect"}
        text = value.lower()
        hits = sum(token in text for token in tokens if len(token) >= 2)
        return 0.05 if hits == 0 else 0.68 if hits == 1 else 0.84 if hits == 2 else 0.96

    def score_candidates(self, query, stage, candidates):
        scored = [
            {**candidate, "score": self.lexical_score(query, json.dumps(candidate["payload"]))}
            for candidate in candidates
        ]
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        self.trace.emit(
            "offline_scores",
            stage=stage,
            scores=[{"id": item["id"], "score": item["score"]} for item in scored],
        )
        return scored, empty_usage()

    score = score_candidates

    def score_reader_files(self, query, state, file_states):
        scored = []
        for file_state in file_states:
            observations = file_state.get("observations", [])
            value = file_state["path"]
            if observations:
                value += "\n" + "\n".join(
                    item.get("content", "") for item in observations[-2:]
                )
            scored.append({
                "path": file_state["path"],
                "score": self.lexical_score(query, value),
            })
        self.trace.emit("offline_reader_file_scores", scores=scored)
        return scored, empty_usage()

    def choose_read_actions(self, query, state, action_sets):
        decisions = []
        for item in action_sets:
            reads = [action for action in item["actions"] if action["kind"] != "stop_file"]
            action = reads[0] if reads else item["actions"][-1]
            probability = 0.95 if reads else 1.0
            decisions.append({
                "path": item["path"],
                "action": action,
                "choice": "offline",
                "probability": probability,
                "confidence": probability,
                "probabilities": {},
            })
        self.trace.emit("offline_read_actions", decisions=decisions)
        return decisions, empty_usage()

    def score_observations(self, query, state, observation_ids):
        by_id = {item["id"]: item for item in state["observations"]}
        scores = {
            observation_id: self.lexical_score(query, by_id[observation_id]["content"])
            for observation_id in observation_ids
        }
        self.trace.emit("offline_observation_scores", scores=scores)
        return scores, empty_usage()


def directories(root):
    root = Path(root).resolve()
    out = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(item for item in dirs if item not in IGNORE and not item.startswith("."))
        path = Path(current)
        if path == root:
            continue
        rel = path.relative_to(root).as_posix()
        out.append({
            "id": rel,
            "payload": {
                "path": rel,
                "name": path.name,
                "child_directories": dirs[:24],
                "direct_files": sorted(name for name in names if not name.startswith("."))[:40],
            },
        })
    return out


def files(root, selected_dirs):
    """Only direct files: stage-one directory pruning must not be undone."""
    root = Path(root).resolve()
    found = {}
    for directory in selected_dirs:
        base = root / directory["payload"]["path"]
        try:
            entries = sorted(base.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for path in entries:
            if not path.is_file():
                continue
            if path.name.startswith(".") or path.suffix.lower() not in SUFFIXES:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            found[rel] = {
                "id": rel,
                "payload": {
                    "path": rel,
                    "directory": directory["payload"]["path"],
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": size,
                },
            }
    return [found[key] for key in sorted(found)]


def source_stat(root, file):
    """Metadata for action generation. File body is not exposed to the model."""
    path = Path(root).resolve() / file["payload"]["path"]
    try:
        size_bytes = path.stat().st_size
        with path.open("rb") as handle:
            line_count = sum(1 for _ in handle)
    except OSError:
        return None
    return {
        "size_bytes": size_bytes,
        "line_count": line_count,
        "extension": file["payload"]["extension"],
    }


def merge_ranges(ranges):
    normalized = sorted(
        (max(1, int(start)), max(1, int(end)))
        for start, end in ranges
        if int(end) >= int(start)
    )
    merged = []
    for start, end in normalized:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def range_is_covered(start, end, coverage):
    return any(start >= left and end <= right for left, right in coverage)


def unread_gaps(line_count, coverage):
    if line_count <= 0:
        return []
    gaps = []
    cursor = 1
    for start, end in merge_ranges(coverage):
        if cursor < start:
            gaps.append((cursor, start - 1))
        cursor = max(cursor, end + 1)
    if cursor <= line_count:
        gaps.append((cursor, line_count))
    return gaps


def relevant_regions(file_state, observation_threshold):
    """Merge adjacent high-relevance observations into bounded semantic hotspots."""
    relevant = [
        (index, item)
        for index, item in enumerate(file_state["observations"])
        if (
            item.get("relevance") is not None
            and item["relevance"] >= observation_threshold
        )
    ]
    relevant.sort(key=lambda pair: (pair[1]["start_line"], pair[1]["end_line"]))

    regions = []
    for index, item in relevant:
        start = item["start_line"]
        end = item["end_line"]
        score = item["relevance"]
        if regions and start <= regions[-1]["end_line"] + 1:
            region = regions[-1]
            region["end_line"] = max(region["end_line"], end)
            region["max_relevance"] = max(region["max_relevance"], score)
            region["observation_count"] += 1
            region["latest_observation_index"] = max(
                region["latest_observation_index"],
                index,
            )
            region["observation_ids"].append(item["id"])
        else:
            regions.append({
                "start_line": start,
                "end_line": end,
                "max_relevance": score,
                "observation_count": 1,
                "latest_observation_index": index,
                "observation_ids": [item["id"]],
            })

    regions.sort(
        key=lambda region: (
            -region["max_relevance"],
            -region["latest_observation_index"],
            region["start_line"],
        )
    )
    return regions[:MAX_RELEVANT_REGIONS]


def make_read_action(path, start, end, reason):
    return {
        "kind": "read_range",
        "path": path,
        "start_line": start,
        "end_line": end,
        "reason": reason,
    }


def generate_read_actions(
    file_state,
    window_lines,
    observation_threshold=DEFAULT_OBSERVATION_THRESHOLD,
):
    """Generate a small dynamic action space from stat, coverage, and scores."""
    path = file_state["path"]
    line_count = file_state["stat"]["line_count"]
    coverage = merge_ranges(file_state["coverage"])
    if line_count <= 0:
        return [{"kind": "stop_file", "path": path, "reason": "empty file"}]

    actions = []

    def append(start, end, reason):
        start = max(1, start)
        end = min(line_count, end)
        if start > end or range_is_covered(start, end, coverage):
            return
        if any(
            item.get("start_line") == start and item.get("end_line") == end
            for item in actions
        ):
            return
        actions.append(make_read_action(path, start, end, reason))

    if not coverage:
        append(1, min(line_count, window_lines), "initial head probe")
        if line_count > window_lines:
            middle_start = max(1, (line_count // 2) - (window_lines // 2))
            append(middle_start, middle_start + window_lines - 1, "initial middle probe")
        if line_count > window_lines * 2:
            append(max(1, line_count - window_lines + 1), line_count, "initial tail probe")
    else:
        regions = relevant_regions(
            file_state,
            observation_threshold,
        )

        for region_index, region in enumerate(regions):
            label = (
                f"relevant region {region_index + 1} "
                f"{region['start_line']}-{region['end_line']} "
                f"(score={region['max_relevance']:.3f})"
            )
            append(
                region["end_line"] + 1,
                region["end_line"] + window_lines,
                f"continue after {label}",
            )
            append(
                region["start_line"] - window_lines,
                region["start_line"] - 1,
                f"expand before {label}",
            )

        gaps = unread_gaps(line_count, coverage)
        if gaps:
            gap_start, gap_end = max(gaps, key=lambda item: item[1] - item[0])
            if gap_end - gap_start + 1 <= window_lines:
                append(gap_start, gap_end, "cover the largest unread gap")
            else:
                midpoint = (gap_start + gap_end) // 2
                start = max(gap_start, midpoint - (window_lines // 2))
                append(start, min(gap_end, start + window_lines - 1), "probe the largest unread gap")

    actions = actions[: MAX_ACTIONS_PER_FILE - 1]
    actions.append({"kind": "stop_file", "path": path, "reason": "stop reading this file"})
    return actions


def read_range(root, action):
    path = Path(root).resolve() / action["path"]
    source = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, action["start_line"])
    end = min(len(source), action["end_line"])
    return {
        "path": action["path"],
        "start_line": start,
        "end_line": end,
        "content": "\n".join(
            f"{line_number}: {source[line_number - 1]}"
            for line_number in range(start, end + 1)
        ),
    }


def new_reader_state(
    query,
    files_in_state,
    root,
    action_threshold,
    observation_threshold,
    activation_threshold,
    soft_reads,
    hard_reads,
):
    state_files = []
    for file in files_in_state:
        stat = source_stat(root, file)
        if stat is None:
            continue
        state_files.append({
            "path": file["payload"]["path"],
            "phase1_score": file["score"],
            "stat": stat,
            "coverage": [],
            "observations": [],
            "read_count": 0,
            "activation_count": 0,
            "last_activation_score": None,
            "stopped": False,
            "stop_reason": None,
        })
    return {
        "goal": query,
        "round": 0,
        "thresholds": {
            "reader_file_activation": activation_threshold,
            "reader_action": action_threshold,
            "observation": observation_threshold,
        },
        "budget": {
            "soft_reads_per_file": soft_reads,
            "hard_reads_per_file": hard_reads,
        },
        "files": state_files,
        "observations": [],
    }


def append_observation(state, file_state, observation, action_probability):
    observation_id = (
        f"{observation['path']}:{observation['start_line']}-"
        f"{observation['end_line']}#{len(state['observations']) + 1}"
    )
    item = {
        "id": observation_id,
        **observation,
        "action_probability": action_probability,
        "relevance": None,
    }
    state["observations"].append(item)
    file_state["observations"].append(item)
    file_state["coverage"] = [
        list(value)
        for value in merge_ranges([
            *file_state["coverage"],
            (observation["start_line"], observation["end_line"]),
        ])
    ]
    return item


def evidence_snippets(reader_states, threshold):
    snippets = []
    for state in reader_states:
        for observation in state["observations"]:
            score = observation.get("relevance")
            if score is None or score < threshold:
                continue
            snippets.append({
                "path": observation["path"],
                "start_line": observation["start_line"],
                "end_line": observation["end_line"],
                "score": score,
                "action_probability": observation["action_probability"],
                "content": observation["content"],
            })
    snippets.sort(key=lambda item: (-item["score"], item["path"], item["start_line"]))
    return snippets


def progressive_read(
    root,
    query,
    decider,
    files_to_read,
    trace,
    *,
    file_activation_threshold,
    window_lines,
    soft_reads,
    hard_reads,
    action_threshold,
    observation_threshold,
):
    usage = empty_usage()
    decisions_made = 0
    file_priority_decisions = 0
    file_activations = 0
    reads_executed = 0
    soft_budget_extensions = 0
    files_stopped_by_soft_budget = 0
    hard_budget_hits = 0
    scheduler_rounds = 0
    unique_files_read = set()

    state = new_reader_state(
        query,
        files_to_read,
        root,
        action_threshold,
        observation_threshold,
        file_activation_threshold,
        soft_reads,
        hard_reads,
    )

    trace.emit(
        "reader_state_started",
        files=[
            {
                "path": item["path"],
                "phase1_score": item["phase1_score"],
                "stat": item["stat"],
            }
            for item in state["files"]
        ],
        file_count=len(state["files"]),
    )

    # No harness-defined batches. Every eligible file remains in one shared
    # state and System One decides which subset should receive reads next.
    max_scheduler_rounds = max(1, len(state["files"]) * hard_reads)
    for round_index in range(max_scheduler_rounds):
        state["round"] = round_index + 1
        scheduler_rounds += 1

        eligible_files = [
            item
            for item in state["files"]
            if not item["stopped"] and item["read_count"] < hard_reads
        ]
        if not eligible_files:
            trace.emit(
                "reader_scheduler_stop",
                round=state["round"],
                reason="no_eligible_files",
            )
            break

        file_scores, current_usage = decider.score_reader_files(
            query,
            state,
            eligible_files,
        )
        merge_usage(usage, current_usage)
        file_priority_decisions += len(file_scores)

        by_path = {item["path"]: item for item in state["files"]}
        for item in file_scores:
            by_path[item["path"]]["last_activation_score"] = item["score"]

        selected_paths = [
            item["path"]
            for item in file_scores
            if item["score"] >= file_activation_threshold
        ]
        trace.emit(
            "reader_file_frontier",
            round=state["round"],
            threshold=file_activation_threshold,
            scores=file_scores,
            selected_paths=selected_paths,
            eligible_count=len(eligible_files),
            selected_count=len(selected_paths),
        )

        if not selected_paths:
            trace.emit(
                "reader_scheduler_stop",
                round=state["round"],
                reason="no_file_above_activation_threshold",
            )
            break

        action_sets = []
        for path in selected_paths:
            file_state = by_path[path]
            file_state["activation_count"] += 1
            regions = relevant_regions(
                file_state,
                observation_threshold,
            )
            action_sets.append({
                "path": path,
                "relevant_regions": regions,
                "actions": generate_read_actions(
                    file_state,
                    window_lines,
                    observation_threshold,
                ),
            })
        file_activations += len(action_sets)

        trace.emit(
            "read_action_frontier",
            round=state["round"],
            file_count=len(action_sets),
            action_sets=action_sets,
        )
        decisions, current_usage = decider.choose_read_actions(
            query,
            state,
            action_sets,
        )
        merge_usage(usage, current_usage)
        decisions_made += len(decisions)

        new_observations = []
        state_changed = False

        for decision in decisions:
            file_state = by_path[decision["path"]]
            action = decision["action"]
            probability = decision["probability"]

            trace.emit(
                "read_action_decision",
                round=state["round"],
                path=decision["path"],
                action=action,
                probability=probability,
                confidence=decision["confidence"],
                probabilities=decision["probabilities"],
                threshold=action_threshold,
            )

            if action["kind"] == "stop_file":
                file_state["stopped"] = True
                file_state["stop_reason"] = "model_stop"
                state_changed = True
                continue

            if probability < action_threshold:
                file_state["stopped"] = True
                file_state["stop_reason"] = "action_below_threshold"
                state_changed = True
                trace.emit(
                    "read_action_rejected",
                    path=decision["path"],
                    probability=probability,
                    threshold=action_threshold,
                )
                continue

            observation = read_range(root, action)
            item = append_observation(
                state,
                file_state,
                observation,
                probability,
            )
            file_state["read_count"] += 1
            new_observations.append(item)
            reads_executed += 1
            unique_files_read.add(file_state["path"])
            state_changed = True
            trace.emit(
                "file_observed",
                round=state["round"],
                observation=item,
                file_read_count=file_state["read_count"],
            )

        if new_observations:
            # New content is in state before relevance is scored.
            scores, current_usage = decider.score_observations(
                query,
                state,
                [item["id"] for item in new_observations],
            )
            merge_usage(usage, current_usage)

            observation_by_path = {}
            for item in new_observations:
                item["relevance"] = scores[item["id"]]
                observation_by_path[item["path"]] = item
                trace.emit(
                    "observation_scored",
                    observation_id=item["id"],
                    path=item["path"],
                    start_line=item["start_line"],
                    end_line=item["end_line"],
                    relevance=item["relevance"],
                    evidence=item["relevance"] >= observation_threshold,
                    threshold=observation_threshold,
                )

            # Read budgets are owned by files, not scheduler rounds.
            for path, item in observation_by_path.items():
                file_state = by_path[path]
                if file_state["read_count"] >= hard_reads:
                    file_state["stopped"] = True
                    file_state["stop_reason"] = "hard_read_budget_reached"
                    hard_budget_hits += 1
                    trace.emit(
                        "reader_file_hard_budget_reached",
                        round=state["round"],
                        path=path,
                        read_count=file_state["read_count"],
                        hard_reads=hard_reads,
                    )
                elif file_state["read_count"] >= soft_reads:
                    if item["relevance"] >= observation_threshold:
                        soft_budget_extensions += 1
                        trace.emit(
                            "reader_file_budget_extended",
                            round=state["round"],
                            path=path,
                            read_count=file_state["read_count"],
                            soft_reads=soft_reads,
                            hard_reads=hard_reads,
                            observation_id=item["id"],
                            relevance=item["relevance"],
                        )
                    else:
                        file_state["stopped"] = True
                        file_state["stop_reason"] = (
                            "soft_budget_no_high_signal"
                        )
                        files_stopped_by_soft_budget += 1
                        trace.emit(
                            "reader_file_soft_budget_stop",
                            round=state["round"],
                            path=path,
                            read_count=file_state["read_count"],
                            soft_reads=soft_reads,
                            hard_reads=hard_reads,
                            relevance=item["relevance"],
                        )

        if not state_changed:
            trace.emit(
                "reader_scheduler_stop",
                round=state["round"],
                reason="no_state_change",
            )
            break

    trace.emit(
        "reader_state_completed",
        rounds=state["round"],
        observations=len(state["observations"]),
        evidence=sum(
            1
            for item in state["observations"]
            if (
                item.get("relevance") is not None
                and item["relevance"] >= observation_threshold
            )
        ),
        files_read=len(unique_files_read),
    )

    return [state], evidence_snippets([state], observation_threshold), {
        **usage,
        "reader_scheduler_rounds": scheduler_rounds,
        "reader_file_priority_decisions": file_priority_decisions,
        "reader_file_activations": file_activations,
        "reader_decisions": decisions_made,
        "reads_executed": reads_executed,
        "unique_files_read": len(unique_files_read),
        "soft_budget_extensions": soft_budget_extensions,
        "files_stopped_by_soft_budget": files_stopped_by_soft_budget,
        "hard_budget_hits": hard_budget_hits,
    }


def run(
    root,
    query,
    decider,
    trace,
    directory_threshold=DEFAULT_DIRECTORY_THRESHOLD,
    file_threshold=DEFAULT_FILE_THRESHOLD,
    reader_file_activation_threshold=DEFAULT_READER_FILE_ACTIVATION_THRESHOLD,
    reader_window_lines=DEFAULT_READER_WINDOW_LINES,
    reader_soft_reads=DEFAULT_READER_SOFT_READS,
    reader_hard_reads=DEFAULT_READER_HARD_READS,
    reader_action_threshold=DEFAULT_READER_ACTION_THRESHOLD,
    observation_threshold=DEFAULT_OBSERVATION_THRESHOLD,
):
    started = time.perf_counter()
    usage = empty_usage()

    trace.emit(
        "search_started",
        root=str(Path(root).resolve()),
        query=query,
        model=decider.model,
        architecture="two_phase_global_file_scheduler_progressive_reader",
        thresholds={
            "directory": directory_threshold,
            "file": file_threshold,
            "reader_file_activation": reader_file_activation_threshold,
            "reader_action": reader_action_threshold,
            "observation": observation_threshold,
        },
        reader={
            "window_lines": reader_window_lines,
            "soft_reads_per_file": reader_soft_reads,
            "hard_reads_per_file": reader_hard_reads,
            "scheduling": "global_file_frontier",
        },
    )

    # Phase 1: locate plausible files without exposing their source bodies.
    directory_candidates = directories(root)
    scored_directories, current_usage = decider.score_candidates(query, "directory", directory_candidates)
    merge_usage(usage, current_usage)
    selected_directories = [
        item for item in scored_directories
        if item["score"] >= directory_threshold
    ]
    trace.emit(
        "phase1_directory_selected",
        exposed=len(directory_candidates),
        selected=len(selected_directories),
        threshold=directory_threshold,
        candidates=selected_directories,
    )

    file_candidates = files(root, selected_directories)
    scored_files, current_usage = decider.score_candidates(query, "file", file_candidates)
    merge_usage(usage, current_usage)
    selected_files = [
        item for item in scored_files
        if item["score"] >= file_threshold
    ]
    trace.emit(
        "phase1_completed",
        exposed=len(file_candidates),
        selected=len(selected_files),
        threshold=file_threshold,
        files=selected_files,
    )

    # Phase 2: stat -> dynamic actions -> Choice -> read -> observation -> Noul.
    reader_states, snippets, reader_metrics = progressive_read(
        root,
        query,
        decider,
        selected_files,
        trace,
        file_activation_threshold=reader_file_activation_threshold,
        window_lines=reader_window_lines,
        soft_reads=reader_soft_reads,
        hard_reads=reader_hard_reads,
        action_threshold=reader_action_threshold,
        observation_threshold=observation_threshold,
    )
    merge_usage(usage, reader_metrics)

    result = {
        "query": query,
        "root": str(Path(root).resolve()),
        "model": decider.model,
        "architecture": "two_phase_global_file_scheduler_progressive_reader",
        "thresholds": {
            "directory": directory_threshold,
            "file": file_threshold,
            "reader_file_activation": reader_file_activation_threshold,
            "reader_action": reader_action_threshold,
            "observation": observation_threshold,
        },
        "directories": selected_directories,
        "files": selected_files,
        "reader_states": reader_states,
        "snippets": snippets,
        "metrics": {
            **usage,
            "directories_exposed": len(directory_candidates),
            "directories_selected": len(selected_directories),
            "files_exposed": len(file_candidates),
            "files_selected": len(selected_files),
            "reader_file_activation_threshold": reader_file_activation_threshold,
            "reader_window_lines": reader_window_lines,
            "reader_soft_reads": reader_soft_reads,
            "reader_hard_reads": reader_hard_reads,
            "reader_scheduler_rounds": reader_metrics["reader_scheduler_rounds"],
            "reader_file_priority_decisions": reader_metrics["reader_file_priority_decisions"],
            "reader_file_activations": reader_metrics["reader_file_activations"],
            "reader_decisions": reader_metrics["reader_decisions"],
            "reads_executed": reader_metrics["reads_executed"],
            "unique_files_read": reader_metrics["unique_files_read"],
            "soft_budget_extensions": reader_metrics["soft_budget_extensions"],
            "files_stopped_by_soft_budget": reader_metrics["files_stopped_by_soft_budget"],
            "hard_budget_hits": reader_metrics["hard_budget_hits"],
            "observations": sum(len(state["observations"]) for state in reader_states),
            "evidence_observations": len(snippets),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }
    result["localization_result"] = build_system_one_result(
        result,
        decider.model,
    )
    trace.emit("search_completed", result=result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("query")
    parser.add_argument("--directory-threshold", type=float, default=DEFAULT_DIRECTORY_THRESHOLD)
    parser.add_argument("--file-threshold", type=float, default=DEFAULT_FILE_THRESHOLD)
    parser.add_argument(
        "--reader-file-activation-threshold",
        type=float,
        default=DEFAULT_READER_FILE_ACTIVATION_THRESHOLD,
    )
    parser.add_argument("--reader-window-lines", type=int, default=DEFAULT_READER_WINDOW_LINES)
    parser.add_argument("--reader-soft-reads", type=int, default=DEFAULT_READER_SOFT_READS)
    parser.add_argument("--reader-hard-reads", type=int, default=DEFAULT_READER_HARD_READS)
    # Legacy arguments are accepted but intentionally ignored: Phase 2 no
    # longer uses a Phase-1 top-k cap or harness-defined file batches.
    parser.add_argument("--phase1-max-files", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--reader-file-batch-size", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--reader-max-rounds",
        dest="reader_soft_reads",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--reader-soft-rounds",
        dest="reader_soft_reads",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--reader-hard-rounds",
        dest="reader_hard_reads",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--reader-action-threshold", type=float, default=DEFAULT_READER_ACTION_THRESHOLD)
    parser.add_argument("--observation-threshold", type=float, default=DEFAULT_OBSERVATION_THRESHOLD)
    parser.add_argument("--offline-decider", action="store_true")
    parser.add_argument("--trace-file")
    parser.add_argument("--output-json")
    parser.add_argument("--output-localization-json")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--typesafe-endpoint", default=os.getenv("TYPESAFE_API_URL", API_URL))
    parser.add_argument("--model", default=os.getenv("TYPESAFE_MODEL", MODEL))
    args = parser.parse_args(argv)

    for name in (
        "reader_window_lines",
        "reader_soft_reads",
        "reader_hard_reads",
    ):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be >= 1")
    if args.reader_hard_reads < args.reader_soft_reads:
        parser.error("--reader-hard-reads must be >= --reader-soft-reads")

    trace = Trace(args.trace_file)
    if args.offline_decider:
        decider = OfflineDecider(trace)
    else:
        key = os.getenv("TYPESAFE_API_KEY", "")
        if not key:
            print("TYPESAFE_API_KEY is required unless --offline-decider is used.", file=sys.stderr)
            return 2
        decider = SystemOneDecider(key, trace, args.typesafe_endpoint, args.model)

    result = run(
        args.root,
        args.query,
        decider,
        trace,
        directory_threshold=args.directory_threshold,
        file_threshold=args.file_threshold,
        reader_file_activation_threshold=args.reader_file_activation_threshold,
        reader_window_lines=args.reader_window_lines,
        reader_soft_reads=args.reader_soft_reads,
        reader_hard_reads=args.reader_hard_reads,
        reader_action_threshold=args.reader_action_threshold,
        observation_threshold=args.observation_threshold,
    )

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
    if args.output_localization_json:
        Path(args.output_localization_json).write_text(
            json.dumps(
                result["localization_result"],
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(payload)
    else:
        print("potential files:")
        for item in result["files"]:
            print(f"  {item['score']:.3f} {item['id']}")
        print("evidence:")
        for item in result["snippets"]:
            print(
                f"  {item['score']:.3f} {item['path']}:"
                f"{item['start_line']}-{item['end_line']}\n{item['content']}"
            )
        print("metrics:", json.dumps(result["metrics"], ensure_ascii=False))

    return 0 if result["files"] and result["snippets"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
