"""Metadata-only discovery experiments. No file, directory or top-k count cap."""
from __future__ import annotations

import math
import re
import time
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from file_discovery_profiles import ProfiledFileDiscoveryDecider
from file_discovery_selection import select_relevant


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

# Narrow high-signal aliases used by the concept-aware experiment. The broader
# V2 vocabulary above stays unchanged as the comparison baseline.
SEMANTIC_CONCEPT_ALIASES = {
    "filesystem": {"fs"},
    "websocket": {"ws"},
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


def semantic_concepts(text):
    """Return distinct task concepts without counting aliases as extra evidence."""
    aliases = {alias: canonical for canonical, values in SEMANTIC_CONCEPT_ALIASES.items()
               for alias in values}
    concepts = set()
    for chunk in re.split(r"[^A-Za-z0-9]+", text):
        if not chunk:
            continue
        whole = chunk.lower()
        if whole.endswith("s") and len(whole) > 4:
            whole = whole[:-1]
        if whole in aliases:
            concepts.add(aliases[whole])
            continue
        if whole in SEMANTIC_CONCEPT_ALIASES:
            concepts.add(whole)
            continue
        # Keep recognized compounds intact before splitting unknown CamelCase
        # names such as OpenClaw into their useful path components.
        parts = re.split(r"(?<=[a-z0-9])(?=[A-Z])", chunk)
        for part in parts:
            normalized = part.lower()
            if normalized.endswith("s") and len(normalized) > 4:
                normalized = normalized[:-1]
            if normalized in aliases:
                concepts.add(aliases[normalized])
            elif normalized in SEMANTIC_CONCEPT_ALIASES:
                concepts.add(normalized)
            elif len(normalized) >= 3 and normalized not in STOP:
                concepts.add(normalized)
    return concepts


def semantic_weighted_evidence(candidates, query, *, include_ineligible=False):
    """Build uncapped, concept-deduplicated path matches and provenance."""
    query_concepts = semantic_concepts(query)
    path_concepts = {c["path"]: semantic_concepts(c["path"]) for c in candidates}
    frequencies = Counter(concept for concepts in path_concepts.values() for concept in concepts)
    total = max(1, len(candidates))
    evidence = {}
    for candidate in candidates:
        path = candidate["path"]
        hits = path_concepts[path] & query_concepts
        if not hits:
            continue
        rare = sorted(concept for concept in hits if frequencies[concept] / total <= 0.02)
        parts = PurePosixPath(path).parts
        filename_concepts = sorted(semantic_concepts(parts[-1]) & hits) if parts else []
        segment_weights = []
        for concept in sorted(hits):
            positions = [i for i, part in enumerate(parts) if concept in semantic_concepts(part)]
            path_weight = max((2.0 if i == len(parts) - 1 else 1.5 if i == len(parts) - 2 else 1.0
                               for i in positions), default=0.0)
            idf = math.log((total + 1) / (frequencies[concept] + 1)) + 1.0
            segment_weights.append({"concept": concept, "document_frequency": frequencies[concept],
                                    "idf": idf, "path_weight": path_weight,
                                    "weighted_score": idf * path_weight})
        filename_score = max((item["weighted_score"] for item in segment_weights
                              if item["concept"] in filename_concepts), default=0.0)
        eligible = (len(query_concepts) <= 1 or len(hits) >= 2 or bool(rare)
                    or filename_score >= 2.0)
        if not eligible and not include_ineligible:
            continue
        evidence[path] = {
            "matched_concepts": sorted(hits), "rare_concepts": rare,
            "filename_concepts": filename_concepts, "segment_weights": segment_weights,
            "weighted_score": sum(item["weighted_score"] for item in segment_weights),
            "filename_weighted_score": filename_score, "eligible": eligible,
        }
    return evidence


def semantic_weighted_matches(candidates, query):
    return set(semantic_weighted_evidence(candidates, query))


def semantic_weighted_threshold_frontier(candidates, query, thresholds):
    """Replay uncapped score thresholds over all path concepts without model calls."""
    evidence = semantic_weighted_evidence(candidates, query, include_ineligible=True)
    rows = []
    for threshold in sorted({float(value) for value in thresholds}):
        rows.append({"threshold": threshold,
                     "paths": sorted(path for path, item in evidence.items()
                                     if item["weighted_score"] >= threshold)})
    return rows


def semantic_weighted_primary_safe_frontier(candidates, query, primary_paths):
    """Return the minimum score-threshold set that retains every labeled target."""
    evidence = semantic_weighted_evidence(candidates, query, include_ineligible=True)
    primary = sorted(set(primary_paths))
    primary_scores = {path: evidence[path]["weighted_score"]
                      for path in primary if path in evidence}
    missing = sorted(set(primary) - primary_scores.keys())
    if missing:
        threshold = None
        selected = set()
    else:
        threshold = min(primary_scores.values()) if primary_scores else None
        selected = {path for path, item in evidence.items()
                    if item["weighted_score"] >= threshold} if threshold is not None else set()
    recovered = set(primary) & selected
    return {
        "threshold": threshold,
        "candidate_count": len(selected),
        "candidate_paths": sorted(selected),
        "primary_scores": primary_scores,
        "primary_target_count": len(primary),
        "recovered_primary_count": len(recovered),
        "primary_recall": len(recovered) / len(primary) if primary else 1.0,
        "missing_primary": sorted(set(primary) - recovered),
        "score_by_path": {path: item["weighted_score"] for path, item in evidence.items()},
    }


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
             uncertainty_threshold=0.5, file_threshold=0.65,
             selection_policy="stable_population", rescue_threshold=0.50):
    if policy not in {"all", "lexical", "hierarchy", "hybrid",
                      "semantic_lexical", "hierarchy_v2", "adaptive_v2",
                      "semantic_weighted"}:
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
    evidence = {}
    if policy == "semantic_weighted":
        evidence = semantic_weighted_evidence(candidates, query)
        for p in evidence:
            reasons[p].add("concept_weighted_path_retrieval")
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
    selected, selection_metadata = select_relevant(
        file_scores, enumerated_file_count=len(candidates), file_threshold=file_threshold,
        policy=selection_policy, rescue_threshold=rescue_threshold, evidence=evidence)
    for item in selected:
        item["discovery_reasons"] = sorted(reasons[item["path"]])
    return {"policy": policy, "enumerated_file_count": len(candidates),
            "scored_file_count": len(file_scores), "file_scores": file_scores,
            "relevant_files": selected, "selection": selection_metadata,
            "retrieval_evidence": evidence, "route_scored_count": len(routes),
            "route_decisions": routes, "deferred_module_count": len(deferred),
            "deferred_modules": deferred,
            "discovery_reasons": {p: sorted(r) for p, r in reasons.items()},
            "index_build_ms": indexing_ms, "file_waves": waves,
            "termination": "discovered_frontier_exhausted",
            "coverage_complete": policy == "all" or len(file_scores) == len(candidates),
            "candidate_count_cap": None,
            "wall_time_ms": (time.perf_counter() - started) * 1000}
