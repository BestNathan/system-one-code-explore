# Issue 13 — Progressive Repository State Machine

Issue: [#13](https://github.com/BestNathan/system-one-code-explore/issues/13)

## Experiment Goal

Test whether progressive repository disclosure with durable unresolved directories can reduce System One-visible state while preserving all nine frozen primary targets. Low-scoring ancestors must not be deleted or marked resolved.

## Experiment Design

Compare two uncapped arms on the same nine task/revision pairs: (A) semantic weighted path retrieval followed by independent System One file scoring; (C) a progressive state machine that begins with root children, expands directories whose relevance or uncertainty is at least 0.55, and promotes files scoring at least 0.65. Each expansion exposes one directory level. Lower-scoring directories remain `deferred_unresolved`. The controls use the compact V4 prompt, four concurrent requests, and batches of up to 64 candidates. No source bodies, fixed top-k, file cap, or hard ancestor pruning are allowed. Parameters and cases are frozen in [`data/design.json`](data/design.json) and [`data/cases.json`](data/cases.json). The primary gate is 9/9 recall, zero irreversible ancestor pruning, and fewer model-visible nodes than the flat/path arm; report p50/p95 and worst-case cost. This is a single-repeat diagnostic suite, not a generalization claim.

## Experiment Process

The design was registered before execution on `main`. GitHub Actions will run tests, verify the three pinned revisions, execute both arms, and upload raw request/response/retry/error JSONL plus checksums. Progressive-state checkpoints are written after each complete wave so failures preserve the last known deferred frontier. Workflow-only execution is required. The report must distinguish scheduler exhaustion from semantic completion and preserve failures or missing jobs. Current status: preregistered; Workflow run pending.

## Experiment Data

- Frozen task labels and repository revisions: [`data/cases.json`](data/cases.json).
- Frozen thresholds, model profile, concurrency, and constraints: [`data/design.json`](data/design.json).
- Workflow metadata and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json), to be populated from the aggregate Workflow artifact.
- Per-task raw calls, results, and SHA-256 manifests are retained in the repository-specific Workflow artifacts for 90 days. The aggregate summary and report are retained for 90 days. Every artifact is inventoried in `workflow/metadata.json` after the run.

## Experiment Results

Pending GitHub Actions execution. No result is claimed before the Workflow artifacts are inspected.
