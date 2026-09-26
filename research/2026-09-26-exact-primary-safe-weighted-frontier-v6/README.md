# Exact Primary-Safe Weighted Frontier V6

## Experiment Goal

Compute the exact minimum candidate count that any single weighted-score threshold can achieve while retaining every frozen primary target, then determine whether the OpenClaw mean can fall below 2,000 without a candidate cap.

## Experiment Design

For each of the nine frozen tasks across the same pinned Nession, Codex, and OpenClaw revisions, calculate weighted evidence for every concept-matching path. Set that task's threshold to the lowest weighted score among its primary target files and count every path at or above that threshold. This is the smallest candidate set any scalar threshold can produce while preserving all labeled primary targets: any lower threshold can only add paths; any higher threshold drops a lowest-score target. If any target has no concept evidence, mark the task as unrecoverable by this score rule. Aggregate exact counts and thresholds by repository. The operational gate is an OpenClaw mean below 2,000 at 100% primary recall.

This is a deterministic metadata-only upper-bound analysis, not a production threshold recommendation. Primary labels are incomplete for supporting files and do not establish generalization.

## Experiment Process

The eleven-point grid in [V5](../2026-09-26-uncapped-weighted-path-score-frontier-v5/) found 9/9 recall at threshold 6 with 4,181 mean OpenClaw candidates; threshold 10 reduced that mean below 2,000 but retained only 6/9 targets. Workflow [36230858823](https://github.com/BestNathan/system-one-code-explore/actions/runs/36230858823) computed the exact recall-safe thresholds on GitHub Actions. All three repositories completed, with zero System One calls and zero directory model decisions.

## Experiment Data

- Frozen pass criteria: [`data/primary-safe-frontier-experiment.json`](data/primary-safe-frontier-experiment.json)
- Frozen tasks and revisions: [`data/cases.json`](data/cases.json)
- Aggregate exact candidate minima: [`data/summary.json`](data/summary.json)
- Workflow jobs and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Per-repository artifacts contain exact safe thresholds, primary feature scores, candidate counts, and misses. Artifacts are retained for 90 days. No model-call raw data is expected because no calls are made.

## Experiment Results

The per-task oracle thresholds averaged 537 candidates in OpenClaw at 100% primary recall. A single threshold shared across the three OpenClaw tasks, calibrated from all three tasks' primary labels, averaged 802 candidates and retained 3/3 targets. The corresponding shared means were 571 for Codex and 34 for Nession. The method therefore clears the scale gate on the frozen labels, but its threshold used those labels and is only an optimistic calibration bound. A leave-one-task-out experiment will test whether thresholds learned from other tasks transfer to a held-out task.
