"""Metadata-only discovery experiments. No file, directory or top-k count cap."""
from __future__ import annotations

import math
import re
import time
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from file_discovery_profiles import ProfiledFileDiscoveryDecider


STOP = set("a an the and or to of for in on with without from by as is are be "
           "i am need want find file files code source materially implement implements "
           "implementation debugging debug reviewing review understand how which "
           "that this these those it its into before after used use using caller callers".split())

SEMANTIC_ALIASES = {
    "filesystem": {"fs", "file", "system"},
    "websocket": {"ws", "web", "socket"},
    "javascript": {"js"},
    "typescript": {"ts"},
    "configuration": {"config"},
    "authentication": {"auth"},
    "authorization": {"authz"},
    "database": {"db"},
}


def tokens(text):
    parts = re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", text)
    return {p.lower()[:-1] if p.lower().endswith("s") and len(p) > 4 else p.lower()
            for p in parts if len(p) >= 3 and p.lower() not in STOP}


def semantic_tokens(text):
    """Expand common code-path abbreviations symmetrically."""
    base = tokens(text)
    # Short path abbreviations are intentionally retained for this vocabulary.
    raw = {p.lower() for p in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", text) if p}
    expanded = set(base)
    for canonical, aliases in SEMANTIC_ALIASES.items():
        if canonical in raw or raw & aliases:
            expanded.add(canonical)
            expanded.update(aliases)
    return expanded


class AdaptiveDecider(ProfiledFileDiscoveryDecider):
    def score_candidates(self, query, stage, candidates):
        if stage != "route":
            return super().score_candidates(query, stage, candidates)
        questions = {}
        for i, c in enumerate(candidates):
            for name, question in (
                ("relevance", "Does this module contain ANY primary implementation or necessary supporting file for the task? Judge existence, not average relevance of its descendants."),
                ("uncertainty", "Is there a concrete plausible task-relevant descendant that this compressed summary could hide, making further inspection useful? Generic absence of source is not itself a reason to expand every module."),
            ):
                questions[f"{name}_{i}"] = {
                    "type": "noul", "instructions": {"module": c["payload"], "question": question},
                    "criteria": {"true": "Evidence supports exploring this module.",
                                 "false": "No material task-specific reason to explore this module."},
                }
        response, usage = self.send("adaptive_route_v1", {
            "goal": query, "phase": "module_routing", "source_visible": False,
            "contract": "Independent multi-hit routing. Generic ancestor names are weak evidence. Read descendant terms and paths. Do not rank modules against each other. Tests/docs matter only if necessary for the task.",
        }, questions)
        answers = response.get("answers", {})
        result = []
        for i, c in enumerate(candidates):
            values = []
            for name in ("relevance", "uncertainty"):
                answer = answers.get(f"{name}_{i}", {})
                if answer.get("type") != "noul":
                    raise ValueError(f"missing/invalid routing answer {name}_{i}")
                values.append(float(answer["noul"]))
            result.append(dict(c, score=values[0], uncertainty=values[1]))
        return result, usage


def lexical_matches(candidates, query):
    terms = tokens(query)
    matched = {c["path"]: tokens(c["path"]) & terms for c in candidates}
    frequencies = Counter(t for terms_here in matched.values() for t in terms_here)
    return {path for path, hits in matched.items()
            if hits and (len(terms) == 1 or len(hits) >= 2
                         or any(frequencies[t] / max(1, len(candidates)) <= 0.02 for t in hits))}


def semantic_lexical_matches(candidates, query):
    terms = semantic_tokens(query)
    matched = {c["path"]: semantic_tokens(c["path"]) & terms for c in candidates}
    frequencies = Counter(t for terms_here in matched.values() for t in terms_here)
    return {path for path, hits in matched.items()
            if hits and (len(terms) == 1 or len(hits) >= 2
                         or any(frequencies[t] / max(1, len(candidates)) <= 0.02 for t in hits))}


def build_tree(candidates, fanout=32):
    """Virtual grouping is a representation width; every child is retained."""
    raw = {"dirs": {}, "files": [], "prefix": "."}
    for c in candidates:
        node = raw
        prefix = []
        for part in PurePosixPath(c["path"]).parts[:-1]:
            prefix.append(part)
            node = node["dirs"].setdefault(part, {"dirs": {}, "files": [], "prefix": "/".join(prefix)})
        node["files"].append(c["path"])

    def group(prefix, children, files):
        files = sorted(files)
        children = list(children)
        if len(files) > fanout:
            children.extend(group(f"{prefix}::files:{i}", [], files[i:i + fanout])
                            for i in range(0, len(files), fanout))
            files = []
        level = 0
        while len(children) > fanout:
            children = [group(f"{prefix}::groups:{level}:{i}", children[i:i + fanout], [])
                        for i in range(0, len(children), fanout)]
            level += 1
        members = sorted(files + [p for child in children for p in child["members"]])
        return {"id": f"module:{prefix}", "prefix": prefix, "files": files,
                "children": children, "members": members}

    def finish(node):
        children = [finish(c) for _, c in sorted(node["dirs"].items())]
        if not node["files"] and len(children) == 1:
            return children[0]
        return group(node["prefix"], children, node["files"])
    return finish(raw)


def module_card(node, query, *, semantic=False):
    paths = node["members"]
    tokenize = semantic_tokens if semantic else tokens
    terms = tokenize(query)
    frequencies = Counter(t for p in paths for t in sorted(tokenize(p)))
    matches = [p for p in paths if tokenize(p) & terms]
    # Compact samples are summary content, never a restriction on reachable files.
    step = max(1, len(paths) // 8)
    samples = paths[::step][:8]
    return {"id": node["id"], "kind": "module", "payload": {
        "prefix": node["prefix"], "descendant_files": len(paths),
        "child_modules": len(node["children"]),
        "common_descendant_tokens": sorted(frequencies, key=lambda t: (-frequencies[t], t))[:24],
        "task_matched_tokens": sorted(terms & frequencies.keys()),
        "matching_path_count": len(matches), "matching_path_examples": matches[:8],
        "representative_paths": samples, "summary_is_lossy": len(paths) > len(samples),
    }}


def discover(candidates, query, scorer, *, policy="hybrid", route_threshold=0.5,
             uncertainty_threshold=0.5, file_threshold=0.65):
    if policy not in {"all", "lexical", "hierarchy", "hybrid",
                      "semantic_lexical", "hierarchy_v2", "adaptive_v2"}:
        raise ValueError("unknown policy")
    started = time.perf_counter()
    by_path = {c["path"]: c for c in candidates}
    reasons = defaultdict(set)
    routes, deferred = [], []
    if policy == "all":
        for p in by_path:
            reasons[p].add("all_file_baseline")
    if policy in {"lexical", "hybrid"}:
        for p in lexical_matches(candidates, query):
            reasons[p].add("global_path_retrieval")
    if policy in {"semantic_lexical", "adaptive_v2"}:
        for p in semantic_lexical_matches(candidates, query):
            reasons[p].add("semantic_path_retrieval")
    indexing_ms = 0.0
    hierarchical = policy in {"hierarchy", "hybrid", "hierarchy_v2", "adaptive_v2"}
    v2 = policy in {"hierarchy_v2", "adaptive_v2"}
    if hierarchical and candidates:
        tick = time.perf_counter()
        root = build_tree(candidates)
        indexing_ms = (time.perf_counter() - tick) * 1000
        # V2 removes the lossy repository-root summary as a single pruning gate.
        # Virtual grouping already guarantees a bounded first wave without
        # removing any child from the logical tree.
        pending = (list(root["children"]) or [root]) if v2 else [root]
        while pending:
            nodes = {n["id"]: n for n in pending}
            scored = scorer.score("route", [module_card(n, query, semantic=v2) for n in pending])
            pending = []
            for item in scored:
                node = nodes[item["id"]]
                expand = item["score"] >= route_threshold or item["uncertainty"] >= uncertainty_threshold
                routes.append({"id": item["id"], "score": item["score"],
                               "uncertainty": item["uncertainty"], "expanded": expand,
                               "descendant_files": len(node["members"])})
                if expand:
                    pending.extend(node["children"])
                    for p in node["files"]:
                        reasons[p].add("semantic_module")
                else:
                    deferred.append({"id": node["id"], "files": node["members"]})
    file_scores = {}
    siblings = defaultdict(list)
    for p in by_path:
        siblings[str(PurePosixPath(p).parent)].append(p)
    waves = 0
    while True:
        pending_files = sorted(set(reasons) - file_scores.keys())
        if not pending_files:
            break
        waves += 1
        scored = scorer.score("file", [by_path[p] for p in pending_files])
        for item in scored:
            file_scores[item["path"]] = float(item["score"])
        if policy == "hybrid":
            for item in scored:
                if item["score"] >= file_threshold:
                    for p in siblings[str(PurePosixPath(item["path"]).parent)]:
                        reasons[p].add("high_confidence_sibling")
    # Exactly the existing V1 final selection policy, including tie preservation.
    ordered = sorted(file_scores, key=lambda p: (-file_scores[p], p))
    fallback_count = max(1, math.ceil(len(ordered) * 0.01)) if ordered else 0
    cutoff = file_scores[ordered[fallback_count - 1]] if fallback_count else None
    selected = [{"path": p, "score": file_scores[p], "discovery_reasons": sorted(reasons[p])}
                for p in ordered if file_scores[p] >= file_threshold or file_scores[p] >= cutoff]
    return {"policy": policy, "enumerated_file_count": len(candidates),
            "scored_file_count": len(file_scores), "file_scores": file_scores,
            "relevant_files": selected, "route_scored_count": len(routes),
            "route_decisions": routes, "deferred_module_count": len(deferred),
            "deferred_modules": deferred,
            "discovery_reasons": {p: sorted(r) for p, r in reasons.items()},
            "index_build_ms": indexing_ms, "file_waves": waves,
            "termination": "discovered_frontier_exhausted",
            "coverage_complete": policy == "all" or len(file_scores) == len(candidates),
            "candidate_count_cap": None,
            "wall_time_ms": (time.perf_counter() - started) * 1000}
