# Project Structure

## Goal

Keep fast experimental change without allowing historical Rxx implementations to become the permanent architecture.

The repository separates durable concepts, active experimental implementations, evaluation/reference code, and historical experiment records.

## Current physical layout

`src/` and `tests/` are still mostly flat because historical workflows import modules by filename. Do not mass-move them just for aesthetics; that would damage reproducibility and create noisy changes unrelated to the research question.

## Target logical layout

```text
system-one-code-explore/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── benchmark.md
│   ├── project-structure.md
│   ├── research-path.md
│   ├── domains/
│   │   ├── file-discovery.md
│   │   └── evidence-localization.md
│   ├── research/       # canonical chronological learning
│   ├── experiments/    # frozen protocols and results
│   └── pilots/         # early exploratory traces
├── src/
│   ├── contracts/              # future stable data contracts
│   ├── file_discovery/         # repository-level search policies
│   ├── evidence_localization/  # in-file sensing/frontier/closure
│   ├── evaluation/             # references, metrics, A/B controls
│   └── experiments/            # experiment-specific adapters
├── tests/
│   ├── contracts/
│   ├── file_discovery/
│   ├── evidence_localization/
│   ├── evaluation/
│   └── regression/
├── fixtures/
│   ├── repository/
│   └── research/
└── .github/workflows/
```

This is a migration target, not a request to rewrite the repository in one commit.

## Stable contracts to extract first

### Task

```text
Task { goal, repository, revision }
```

### Usage

```text
Usage {
  model_calls
  input_tokens
  output_tokens
  model_wall_time_ms
  source_lines_read
  metadata_items_seen
  cache_hits
  cache_misses
}
```

### File discovery

```text
RelevantFile { path, relevance_state, provenance }
```

### Evidence localization

```text
EvidenceAnchor { path, seed_range, current_range, closure_history }
EvidenceSpan   { path, start_line, end_line, utility, role, provenance }
```

### Final result

```text
LocalizationResult { task, files[], evidence[], usage, trace_reference }
```

These contracts should remain comparable even when algorithms are replaced.

## Domain ownership

### `file_discovery/`

Owns repository/tree state, progressive directory/file disclosure, file relevance/uncertainty, file coverage obligations, relation-following actions, and repository-level stopping.

It does not own source-range closure or line-level evidence shaping.

### `evidence_localization/`

Owns sparse probes, file-local observations, posterior reconstruction, uncertainty, in-file obligations, evidence anchors, directional closure, and post-closure utility.

It does not decide the repository-wide candidate file set.

### `evaluation/`

Owns System Two reference generation, projection/metrics, cost accounting, shared semantic-decision cache, and aggregate reports.

Hidden labels must never influence candidate generation.

### `experiments/`

Owns only frozen experiment glue: parameters, baseline/candidate assembly, and artifact serialization. Logic reused across experiments should move into a domain module.

## Current module classification

Evidence localization examples:
- `system_one_probability_frontier.py`
- `posterior_reconstruction.py`
- `frontier_obligation_runtime.py`
- `frontier_obligation_geometry.py`
- `anchor_semantic_closure.py`

Evaluation/reference examples:
- `full_read_relevance_baseline.py`
- `compare_to_full_read_baseline.py`
- `localization_quality_evaluation.py`
- benchmark scripts

Historical predecessors such as `system_one_range_runtime.py` should remain reproducible until their experiment line is intentionally retired.

## Migration order

1. Documentation and contracts.
2. Common Usage/trace accounting.
3. Evidence-localization package behind compatibility imports.
4. New canonical file-discovery package.
5. Central evaluation package and counterfactual decision cache.

## Rule for new experiments

A new Rxx experiment should prefer a new policy behind an existing interface over inventing a new project-level runtime/result type.

The repository should become easier to compare as research grows, not harder.