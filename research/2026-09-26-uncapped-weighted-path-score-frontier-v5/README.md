# Uncapped Weighted Path Score Frontier V5

## Experiment Goal

Find whether any preregistered metadata score threshold can retain all nine frozen primary targets while reducing the mean OpenClaw candidate set below 2,000 files. This experiment replays every matching path without model calls and applies no fixed candidate count or top-k rule.

## Experiment Design

Run eleven thresholds (`0, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20`) over the complete weighted path score for the same nine tasks and three pinned repository revisions used in V4. Include paths that matched a task concept but failed V4's current eligibility rules so the frontier includes previously discarded evidence. Compute candidate count and frozen primary-target recall only after building the deterministic path scores. Report the per-task frontier, overall recall, OpenClaw mean, the maximum candidate count, and whether any threshold meets both gates. This is a diagnostic threshold analysis; using frozen targets to evaluate a frontier does not establish fresh-task generalization.

The run must make zero System One calls and zero directory model decisions. Thresholds express metadata evidence strength, never a candidate-count cap. The report includes missing primary files at each threshold.

## Experiment Process

V3 increased OpenClaw mean scoring from 2,655 to 4,729 files and missed a Gateway target. V4 fixed the PascalCase normalization and restored all nine primary targets, but weighted retrieval still scored 4,632 OpenClaw files. This frontier study checks whether a metadata-only score threshold can reduce that cost before another paid scoring experiment. The GitHub Actions Workflow validates the test suite, checks out the same pinned repositories, computes the full threshold frontier, aggregates the results, and retains artifacts for 90 days.

## Experiment Data

- Frozen thresholds and pass criteria: [`data/frontier-experiment.json`](data/frontier-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Workflow jobs, aggregate artifact, and retention inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Per-repository artifacts contain each task's threshold counts, primary recall, and misses. No raw model-call files are expected because the experiment is offline and makes no calls.

## Experiment Results

Pending the GitHub Actions run. The principal result is the Pareto frontier of candidate count versus primary recall; the experiment passes its operational gate only if at least one threshold reaches 9/9 recall and fewer than 2,000 mean OpenClaw candidates.
