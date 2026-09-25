"""File Discovery System One prompt/state profiles."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from system_one_code_locator import SystemOneDecider, empty_usage


PROFILES = (
    "baseline_v1",
    "instruction_v2",
    "enriched_state_v3",
)


def tokenize_path(path):
    tokens = []
    for segment in Path(path).parts:
        stem = Path(segment).stem
        tokens.extend(
            token.lower()
            for token in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", stem)
            if token
        )
    return tokens


def repository_metadata_context(candidates):
    extensions = Counter(
        item["payload"].get("extension") or "<none>"
        for item in candidates
    )
    top_level = Counter(
        Path(item["path"]).parts[0]
        for item in candidates
        if Path(item["path"]).parts
    )
    return {
        "file_count": len(candidates),
        "top_level_roots": [
            {"name": name, "files": count}
            for name, count in top_level.most_common(24)
        ],
        "extension_counts": [
            {"extension": ext, "files": count}
            for ext, count in extensions.most_common(24)
        ],
    }


def enriched_candidate_payload(candidate):
    payload = dict(candidate["payload"])
    path = payload["path"]
    parts = list(Path(path).parts)
    payload["path_segments"] = parts
    payload["semantic_tokens"] = tokenize_path(path)
    payload["parent_segments"] = parts[:-1]
    payload["file_stem"] = Path(path).stem
    return payload


class ProfiledFileDiscoveryDecider(SystemOneDecider):
    def __init__(
        self,
        key,
        trace,
        *,
        profile,
        repository_context=None,
        endpoint,
        model,
    ):
        super().__init__(key, trace, endpoint, model)
        if profile not in PROFILES:
            raise ValueError(f"unknown file discovery profile: {profile}")
        self.profile = profile
        self.repository_context = repository_context or {}

    def score_candidates(self, query, stage, candidates):
        if self.profile == "baseline_v1":
            return super().score_candidates(query, stage, candidates)
        if not candidates:
            return [], empty_usage()

        questions = {}
        for index, candidate in enumerate(candidates):
            payload = (
                enriched_candidate_payload(candidate)
                if self.profile == "enriched_state_v3"
                else candidate["payload"]
            )
            questions[f"candidate_{index}"] = {
                "type": "noul",
                "instructions": {
                    "task": query,
                    "file": payload,
                    "decision_contract": [
                        "Judge this exact file independently; multiple files may all be relevant.",
                        "Estimate whether this file itself is likely to contain primary implementation evidence or directly necessary supporting implementation for the task.",
                        "Use the full repository-relative path compositionally: specific leaf directories and filenames are stronger evidence than generic container names.",
                        "Do not require exact task keywords when architecture conventions strongly imply the responsibility.",
                        "Do not lower a file merely because another candidate may be better; this is independent multi-label relevance, not ranking or Choice.",
                        "Tests, protocol/contracts, configuration, and adapters count only when the task materially depends on them.",
                    ],
                    "question": (
                        "How likely is this exact file to contain material "
                        "source evidence needed to investigate the task?"
                    ),
                },
                "criteria": {
                    "true": (
                        "The file is likely to directly implement the requested "
                        "behavior or provide a necessary supporting implementation "
                        "surface for understanding it."
                    ),
                    "false": (
                        "The file is unlikely to contain material implementation "
                        "evidence for this task; a name/path coincidence alone is "
                        "not enough."
                    ),
                },
            }

        state = {
            "goal": query,
            "phase": "file_discovery",
            "profile": self.profile,
            "candidate_count": len(candidates),
            "semantic_contract": {
                "multi_hit": True,
                "source_visible": False,
                "independent_probabilities": True,
            },
        }
        if self.profile == "enriched_state_v3":
            state["repository_metadata"] = self.repository_context

        response, usage = self.send(
            f"file_discovery_{self.profile}",
            state,
            questions,
        )
        answers = response.get("answers", {})
        scored = []
        for index, candidate in enumerate(candidates):
            answer = answers.get(f"candidate_{index}", {})
            if answer.get("type") != "noul":
                raise RuntimeError(
                    f"unexpected candidate answer: {answer!r}"
                )
            scored.append({
                **candidate,
                "score": float(answer["noul"]),
            })
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        return scored, usage

    score = score_candidates
