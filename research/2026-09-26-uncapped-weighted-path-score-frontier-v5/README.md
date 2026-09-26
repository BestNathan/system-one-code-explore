# Uncapped Weighted Path Score Frontier V5

## Experiment Goal

Find whether any preregistered metadata score threshold can retain all nine frozen primary targets while reducing the mean OpenClaw candidate set below 2,000 files. This experiment replays every matching path without model calls and applies no fixed candidate count or top-k rule.

## Experiment Design

Run eleven thresholds (`0, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20`) over the complete weighted path score for the same nine tasks and three pinned repository revisions used in V4. Include paths that matched a task concept but failed V4's current eligibility rules so the frontier includes previously discarded evidence. Compute candidate count and frozen primary-target recall only after building the deterministic path scores. Report the per-task frontier, overall recall, OpenClaw mean, the maximum candidate count, and whether any threshold meets both gates. This is a diagnostic threshold analysis; using frozen targets to evaluate a frontier does not establish fresh-task generalization.

The run must make zero System One calls and zero directory model decisions. Thresholds express metadata evidence strength, never a candidate-count cap. The report includes missing primary files at each threshold.

## Experiment Process

V3 increased OpenClaw mean scoring from 2,655 to 4,729 files and missed a Gateway target. V4 fixed the PascalCase normalization and restored all nine primary targets, but weighted retrieval still scored 4,632 OpenClaw files. Workflow [36230341725](https://github.com/BestNathan/system-one-code-explore/actions/runs/36230341725) validated 154 tests and completed all three repositories with zero model calls and zero directory model decisions. Artifacts are retained for 90 days.

## Experiment Data

- Frozen thresholds and pass criteria: [`data/frontier-experiment.json`](data/frontier-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Aggregate threshold frontier: [`data/summary.json`](data/summary.json)
- Workflow jobs, aggregate artifact, and retention inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Per-repository artifacts contain each task's threshold counts, primary recall, and misses. No raw model-call files are expected because the experiment is offline and makes no calls.

## Experiment Results

No tested threshold met both gates. Threshold 6 retained all 9/9 primary targets but averaged 4,181 OpenClaw candidates. Threshold 8 reduced that mean to 2,451 but lost one target. Threshold 10 reached 1,933 candidates but retained only 6/9 targets. The available score thresholds therefore expose a sharp recall/cost tradeoff; the next experiment calculates the exact smallest candidate population any scalar score threshold can retain while preserving all known primary targets.
