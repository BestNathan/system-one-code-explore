# Exact Primary-Safe Weighted Frontier V6

## Experiment Goal

Compute the exact minimum candidate count that any single weighted-score threshold can achieve while retaining every frozen primary target, then determine whether the OpenClaw mean can fall below 2,000 without a candidate cap.

## Experiment Design

For each of the nine frozen tasks across the same pinned Nession, Codex, and OpenClaw revisions, calculate weighted evidence for every concept-matching path. Set that task's threshold to the lowest weighted score among its primary target files and count every path at or above that threshold. This is the smallest candidate set any scalar threshold can produce while preserving all labeled primary targets: any lower threshold can only add paths; any higher threshold drops a lowest-score target. If any target has no concept evidence, mark the task as unrecoverable by this score rule. Aggregate exact counts and thresholds by repository. The operational gate is an OpenClaw mean below 2,000 at 100% primary recall.

This is a deterministic metadata-only upper-bound analysis, not a production threshold recommendation. Primary labels are incomplete for supporting files and do not establish generalization.

## Experiment Process

The eleven-point grid in [V5](../2026-09-26-uncapped-weighted-path-score-frontier-v5/) found 9/9 recall at threshold 6 with 4,181 mean OpenClaw candidates; threshold 10 reduced that mean below 2,000 but retained only 6/9 targets. This run removes grid spacing as a source of uncertainty by computing the exact recall-safe threshold per task. GitHub Actions runs all repository analysis and stores the result; there are no System One calls or directory model decisions.

## Experiment Data

- Frozen pass criteria: [`data/primary-safe-frontier-experiment.json`](data/primary-safe-frontier-experiment.json)
- Frozen tasks and revisions: [`data/cases.json`](data/cases.json)
- Workflow jobs and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Per-repository artifacts contain exact safe thresholds, primary feature scores, candidate counts, and misses. Artifacts are retained for 90 days. No model-call raw data is expected because no calls are made.

## Experiment Results

Pending the GitHub Actions run. The key result is whether the exact primary-safe candidate minimum meets the OpenClaw scale gate; this establishes whether a single scalar weighted score can satisfy both constraints on the frozen labels.
