# Problem Domain — File Discovery

## Goal

Given a repository and an engineering task, identify the files that deserve source-level inspection.

The desired output is conceptually:

```text
RelevantFile {
  path
  relevance_state
  provenance
  unresolved_dependencies
}
```

File discovery should stop at a state-space boundary. It should not require reading the full body of every candidate file.

## Why this is a separate problem

If file discovery is poor, evidence localization pays for it downstream:

- irrelevant files multiply in-file model calls;
- omitted relevant files cannot be recovered by a perfect range locator;
- repository-scale cost becomes dominated by false-positive candidates.

Therefore relevant-file coverage is an upstream invariant, not just a ranking metric.

## Research question

> Can System One progressively discover relevant files from repository structure, metadata, and grounded observations without asking System Two to reason over the whole repository?

## Intended state machine

```text
RepositoryState
    -> bounded visible directories/files
    -> System One bounded judgments
    -> inspect directory / promote file / follow grounded relation
    -> observation
    -> RepositoryState
```

The harness owns tree traversal legality, visible metadata, pagination/batching, budgets, durability, duplicate suppression, and cache identity.

System One supplies bounded semantic judgments such as which visible node is worth expanding or promoting.

## Progressive disclosure rules

Avoid:

- putting the whole repository tree in every prompt;
- recursively expanding all descendants of a selected directory;
- fixed semantic ordering through arbitrary file batches;
- reading file bodies merely to decide whether a file deserves inspection.

Prefer:

- direct children after directory expansion;
- metadata before source;
- observation-created `FollowFile`, `FollowImport`, `InspectCaller`, `InspectCallee`, or `FollowTest` actions;
- durable unresolved file-level coverage state.

## Current status

This domain now has a mechanically converged V1 architecture.

Historical work plus the V1 convergence gate established a stronger conclusion:

- semantic directory pruning is not recall-safe because relevant descendants can sit under low-scoring generic parents;
- the Harness should mechanically enumerate supported file metadata;
- System One should independently score files, not directories;
- high-confidence absolute selection is augmented by a small relative recall guard;
- source bodies remain outside File Discovery.

Canonical V1:

```text
all supported file metadata
  -> independent Noul score per file
  -> score >= 0.65 OR top-1% relative guard
  -> RelevantFile[]
```

On the frozen six-case primary-target suite, two repeats recovered all 12/12 targets. Average cost was 18 model calls, ~212k input tokens, and 6.6s model wall time per task on a 1,096-file repository.

See [File Discovery V1 convergence](file-discovery-v1.md).

What remains missing is a broader repository-level reference benchmark with complete primary/supporting labels.

## Benchmark requirements

A proper file-discovery corpus should include repositories with multiple relevant files, misleading names, test/implementation splits, generated/vendor files, configuration-driven behavior, and same-symbol names in unrelated modules.

The reference should distinguish primary files, supporting files, and incidental mentions.

Metrics must include relevant-file recall/precision, irrelevant files promoted, metadata items seen, calls/tokens/time, and induced downstream evidence-localization cost.

## Research directions

### Repository relevance/uncertainty state

Explore a durable repository-level probability state rather than independent one-shot file scores.

### Observation-driven relations

Relations should become legal actions only when grounded by observations. The harness exposes the relation; System One decides whether following it is useful.

### File-level coverage obligations

Finding one useful file must not imply that every independent relevant-file mode has been covered.

### Cost-aware scheduling

Every promoted file may start an expensive evidence-localization runtime, so file discovery should optimize expected end-to-end quality per call/token, not file relevance in isolation.

## Boundary with evidence localization

File discovery answers: **which files deserve inspection?**

Evidence localization answers: **inside this file, which literal source spans are task evidence?**

The model may be shared, but state, legal actions, benchmarks, and stopping invariants should remain distinct.