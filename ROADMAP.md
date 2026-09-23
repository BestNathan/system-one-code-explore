# Roadmap

## Research objective

Evolve the current adaptive range locator into a general **System One Code Exploration Runtime** based on progressive state-space disclosure.

## M0 — Extract and freeze the validated baseline

Status: completed in the bootstrap tree.

- preserve the per-file range runtime;
- preserve Stop/Read reconciliation;
- preserve canonical result identity;
- preserve the Claude Code-style cross-trace;
- preserve blind downstream-quality evaluation;
- keep historical pilots as evidence, not as production architecture.

## M1 — Observation-driven cross-file actions

Primary target.

Introduce a runtime-level effect such as:

```text
FollowFile(path, reason, discovered_from)
```

Design constraints:

- the harness validates that the path exists but does not interpret source semantics;
- a System One observation may propose or score a newly disclosed file action;
- a scheduler owns the active set of FileRuntimes;
- each discovered file records provenance from the observation that exposed it;
- branching must be bounded by explicit global and per-runtime budgets.

Target experiment: recover known misses such as `MessageRouter.ts` without lowering the global Phase 1 file threshold.

## M2 — Evidence shaping

Replace retained fixed-size observation windows with a post-navigation evidence-shaping stage.

Research:

- shrink a useful 140-line observation to representative subranges;
- generate task-specific reasons;
- classify files as primary / supporting / context;
- measure precision, redundancy, and downstream actionability separately.

Success criterion: raise blind quality without increasing navigation cost materially.

## M3 — Progressive graph actions

Generalize the action vocabulary:

- `FollowFile`
- `FollowSymbol`
- `InspectCaller`
- `InspectCallee`
- `InspectStateHolder`

The harness should progressively expose actions from grounded observations rather than eagerly constructing a complete semantic graph.

## M4 — Context and cost efficiency

The current System One runtime is latency-efficient but input-token heavy.

Investigate:

- state deltas instead of full repeated DecisionView payloads;
- stable observation references;
- prefix/cache reuse;
- compact exploration histories;
- observation summarization that remains replayable;
- model-call batching without collapsing independent decisions.

Track provider monetary cost in addition to latency and tokens.

## M5 — Durable scheduler

Move FileRuntime execution behind a scheduler/effect abstraction.

Desired properties:

- pause/resume;
- durable event log;
- replay;
- per-task resource budgets;
- bounded concurrency;
- priority scheduling;
- forkable exploration branches.

## M6 — System One / System 2 hybrid

Use the two model classes for different jobs:

- System One: fast action selection inside a disclosed state space;
- System 2: create or reshape state/action spaces when the runtime cannot progress.

The research goal is to minimize System 2 involvement while preserving completeness.

## Evaluation discipline

Every algorithm change should be evaluated on:

1. frozen subject revision;
2. verbatim task;
3. navigation cost;
4. termination behavior;
5. symmetric overlap;
6. blind downstream-quality score;
7. omissions and failure modes;
8. repeated-run variance.

Do not use Claude overlap alone as ground truth.
