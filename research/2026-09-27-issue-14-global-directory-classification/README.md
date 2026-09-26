# Issue 14 — Global Directory Classification

Issue: [#14](https://github.com/BestNathan/system-one-code-explore/issues/14)

## Experiment Goal

Test whether classifying all directory paths globally and then scoring only selected directories' direct files can reduce File Discovery cost while preserving primary-target recall. No parent score may make a child directory invisible.

## Experiment Design

Compare two arms on the same nine frozen tasks and repository revisions: (A) uncapped semantic weighted path retrieval followed by independent file scoring; (C) enumerate the full directory population, score it in fixed transport batches, select directories at Noul 0.65, and score only deduplicated direct files under selected directories at the same frozen 0.65 threshold. Phase 1 metadata is path, basename, depth, direct-file count, and direct-directory count. The full directory population is fixed before the first model call; no later batch depends on earlier scores. Phase 2 never descends recursively. Use `compact_state_v4`, `jev-latest`, four workers, batch size 64, and a 48,000-byte candidate payload limit. No source bodies, top-k, or hard candidate caps. Issue #13 remains a historical tree-search result and is not rerun as a third paid arm. Parameters and tasks are frozen in [`data/design.json`](data/design.json) and [`data/cases.json`](data/cases.json).

The primary gates are 100% target candidate recall, final recall no worse than arm A, every target directory independently visible in Phase 1, and OpenClaw Phase 2 file candidates materially below arm A. Report per-phase calls/tokens, directory and file batch distributions, and p50/p95/max end-to-end cost. One repeat is diagnostic only.

## Experiment Process

The design was registered and executed on `main`. [Workflow 36255811807](https://github.com/BestNathan/system-one-code-explore/actions/runs/36255811807) completed successfully: validation, all three repository jobs, and aggregation passed. The aggregate artifact and all repository-level raw-call artifacts are retained for 90 days. All 18 arm-level call manifests are complete and cover 493 physical model calls. No local experiment or model call was run.

## Experiment Data

- Frozen tasks and target labels: [`data/cases.json`](data/cases.json).
- Frozen thresholds, model, revisions, and transport settings: [`data/design.json`](data/design.json).
- Aggregated task and cost data: [`data/summary.json`](data/summary.json).
- Workflow/job status and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json).
- Repository-specific raw-call, result, and batch artifacts are retained for 90 days. Aggregate artifact `issue14-aggregate-36255811807` is retained for 90 days; exact artifact names appear in `workflow/metadata.json`.

## Experiment Results

The global-directory arm recovered **5/9** targets at both candidate and final stages. The path baseline had **9/9 candidate recall** and **8/9 final recall**, so the global-directory design fails both recall gates. Every directory path was scored independently, so the four misses were low own-directory scores rather than ancestor gating: all three Codex target directories scored below 0.65 (0.29 for `codex-rs/core/src/tools`, 0.41 and 0.46 for `codex-rs/core/src`), and the Nession filesystem directory scored 0.46. The baseline had already exposed that Nession file, but its file score was 0.56, below the shared 0.65 file threshold.

OpenClaw shows the compression benefit in isolation. Its 1,907-directory population was scored once for each task. The selected directories exposed an average of **865 direct files** per task, versus 4,632 path-baseline file candidates and 43,748 repository files. That is an 81% reduction from the current path candidate set and about a 50× reduction from the full file population. Counting both phases, model-visible nodes averaged 2,772 versus 4,632, input tokens averaged 554k versus 796k, and physical calls averaged 44 versus 73. All three OpenClaw targets were selected and promoted.

The compression did not transfer across the frozen suite. Codex scored 938 directories per task but selected only 4–6, leaving all three target files unexposed; Nession exposed only 4 files per task on average and missed the filesystem target directory. The all-arm end-to-end distribution was p50/p95 1,005/7,918 model-visible nodes and 17/124 physical calls; both directory and file batch sizes were 64 at p50, p95, and maximum.

This exact path-and-count directory representation is **not viable as a general replacement** for path retrieval: overall candidate recall fell to 5/9. It does show that direct-file scoring can become small on OpenClaw when relevant directory paths are selected. The likely missing signal is direct-file naming: the frozen directory payload had only the path, basename, depth, and file/directory counts. The next experiment should add deterministic direct-filename token frequencies and rare-name evidence without truncating directories at a fixed file count; keep every directory globally visible and test whether this recovers the low-scoring Codex/Nession directories without giving back OpenClaw's Phase 2 reduction. Issue #13 remains a separate failed recursive-tree-search result; its outcome does not falsify this two-stage mechanism.
