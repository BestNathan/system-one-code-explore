# Issue 13 — Progressive Repository State Machine

Issue: [#13](https://github.com/BestNathan/system-one-code-explore/issues/13)

## Experiment Goal

Test whether progressive repository disclosure with durable unresolved directories can reduce System One-visible state while preserving all nine frozen primary targets. Low-scoring ancestors must not be deleted or marked resolved.

## Experiment Design

Compare two uncapped arms on the same nine task/revision pairs: (A) semantic weighted path retrieval followed by independent System One file scoring; (C) a progressive state machine that begins with root children, expands directories whose relevance or uncertainty is at least 0.55, and promotes files scoring at least 0.65. Each expansion exposes one directory level. Lower-scoring directories remain `deferred_unresolved`. The controls use the compact V4 prompt, four concurrent requests, and batches of up to 64 candidates. No source bodies, fixed top-k, file cap, or hard ancestor pruning are allowed. Parameters and cases are frozen in [`data/design.json`](data/design.json) and [`data/cases.json`](data/cases.json). The primary gate is 9/9 recall, zero irreversible ancestor pruning, and fewer model-visible nodes than the flat/path arm; report p50/p95 and worst-case cost. This is a single-repeat diagnostic suite, not a generalization claim.

## Experiment Process

The design was registered and run on `main`. Validation and all three repository jobs passed in [experiment Workflow 36253022973](https://github.com/BestNathan/system-one-code-explore/actions/runs/36253022973). Its report job initially failed because aggregate mode incorrectly required a repository argument. [Aggregation Workflow 36253471860](https://github.com/BestNathan/system-one-code-explore/actions/runs/36253471860) reused the three uploaded repository artifacts; no model calls were repeated. Progressive-state checkpoints were written after each complete wave. All 18 arm-level call manifests are complete and retained in the source Workflow artifacts for 90 days. The final experiment status is complete; the acceptance gate failed.

## Experiment Data

- Frozen task labels and repository revisions: [`data/cases.json`](data/cases.json).
- Frozen thresholds, model profile, concurrency, and constraints: [`data/design.json`](data/design.json).
- Frozen arm-level metrics and p50/p95 state sizes: [`data/summary.json`](data/summary.json).
- Workflow metadata and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json).
- Per-task raw calls, retries, outcomes, and SHA-256 manifests are retained in the repository-specific Workflow artifacts for 90 days. The aggregate summary and report are retained in artifact `issue13-aggregate-36253471860` for 90 days. Every artifact is inventoried in `workflow/metadata.json`.

## Experiment Results

The progressive arm recovered 6/9 primary targets, below the flat/path baseline's 8/9. It reduced file decisions in Nession (33 vs. 47 mean) and Codex (806 vs. 1,400), but directory decisions erased much of the total-state reduction: Nession averaged 58 visible nodes versus 47, while Codex averaged 1,025 versus 1,400 and missed the approval target under a deferred `codex-rs/core/src/tools` frontier. Nession also missed two targets beneath deferred frontiers.

OpenClaw failed the scale gate. The flat/path baseline averaged 4,632 scored files; progressive disclosure averaged 7,414 file decisions plus 303 directory decisions, for 7,716 visible nodes. Its input-token mean rose from 796k to 1.37m. Although it recovered all three OpenClaw targets, it scored more files and consumed more tokens. Across all nine cases, state size had p50 994, p95 9,366, and maximum 9,366 nodes.

No ancestor was irreversibly pruned by implementation. However, unresolved directories remained at scheduler exhaustion, and three targets were missed behind those deferred frontiers. Keeping a node deferred prevents permanent deletion, but does not guarantee recall if the run stops without revisiting it. This policy therefore fails the 9/9 recall and large-repository reduction gates and should not replace the path baseline. Treat the comparison as a one-repeat diagnostic: semantic decisions were not shared between arms, so batch-dependent model noise remains a limitation.

Next research should turn path-retrieval hits and other grounded evidence into explicit durable expansion obligations, with deferred ancestors revisited when an obligation lies below them. Measure directory decisions and total model-visible state against the path baseline before tuning thresholds.
