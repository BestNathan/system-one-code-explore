# Issue 14 — Global Directory Classification

Issue: [#14](https://github.com/BestNathan/system-one-code-explore/issues/14)

## Experiment Goal

Test whether classifying all directory paths globally and then scoring only selected directories' direct files can reduce File Discovery cost while preserving primary-target recall. No parent score may make a child directory invisible.

## Experiment Design

Compare two arms on the same nine frozen tasks and repository revisions: (A) uncapped semantic weighted path retrieval followed by independent file scoring; (C) enumerate the full directory population, score it in fixed transport batches, select directories at Noul 0.65, and score only deduplicated direct files under selected directories at the same frozen 0.65 threshold. Phase 1 metadata is path, basename, depth, direct-file count, and direct-directory count. The full directory population is fixed before the first model call; no later batch depends on earlier scores. Phase 2 never descends recursively. Use `compact_state_v4`, `jev-latest`, four workers, batch size 64, and a 48,000-byte candidate payload limit. No source bodies, top-k, or hard candidate caps. Issue #13 remains a historical tree-search result and is not rerun as a third paid arm. Parameters and tasks are frozen in [`data/design.json`](data/design.json) and [`data/cases.json`](data/cases.json).

The primary gates are 100% target candidate recall, final recall no worse than arm A, every target directory independently visible in Phase 1, and OpenClaw Phase 2 file candidates materially below arm A. Report per-phase calls/tokens, directory and file batch distributions, and p50/p95/max end-to-end cost. One repeat is diagnostic only.

## Experiment Process

Preregister on `main`, run tests and all three frozen repositories through GitHub Actions, inspect each job and raw-call manifest, then freeze the aggregate and interpretation here. The runner deterministically enumerates the entire directory population before classification and logs separate Phase 1 and Phase 2 calls. Raw requests, responses, retries, terminal errors, and SHA-256 manifests are archived as Workflow artifacts. Workflow execution status: pending.

## Experiment Data

- Frozen tasks and target labels: [`data/cases.json`](data/cases.json).
- Frozen thresholds, model, revisions, and transport settings: [`data/design.json`](data/design.json).
- Aggregated task and cost data: [`data/summary.json`](data/summary.json), populated after Actions completes.
- Workflow/job status and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json), populated from the aggregate Workflow.
- Repository-specific raw-call, result, and batch artifacts are retained for 90 days. The aggregate report, summary, and metadata artifact are retained for 90 days; exact artifact names appear in `workflow/metadata.json`.

## Experiment Results

Pending GitHub Actions execution. Do not infer the result from Issue #13: this experiment scores the complete directory population independently and has a separate acceptance gate.
