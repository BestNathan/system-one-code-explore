# Leave-One-Task-Out Weighted Threshold V7

## Experiment Goal

Check whether a weighted threshold calibrated from other tasks in the same repository can preserve primary targets on a held-out task while keeping OpenClaw below 2,000 candidates on average.

## Experiment Design

For each repository, hold out each of its three frozen tasks in turn. Set the threshold to the minimum weighted score among the primary targets in the other two tasks from that repository. Apply that threshold to every concept-matching path in the held-out task and record candidate count and primary recall. This prevents the held-out task's labels from setting its own threshold. Require 9/9 primary recall and fewer than 2,000 mean held-out candidates in OpenClaw. No hard candidate cap, top-k policy, System One call, or directory model decision is used.

The suite has only three diagnostic tasks per repository, so this check measures transfer across the existing task types; it does not replace fresh-task generalization.

## Experiment Process

V6 found that repository-shared thresholds calibrated on all task labels retained 3/3 OpenClaw targets at 802 candidates per task. Because those same labels set the threshold, V6 is an optimistic bound. Workflow [36231288979](https://github.com/BestNathan/system-one-code-explore/actions/runs/36231288979) left each task out and calibrated only on the other two tasks in the same repository. All three repository jobs and the aggregate completed successfully; no model calls were made.

## Experiment Data

- Frozen cross-validation rule: [`data/threshold-validation-experiment.json`](data/threshold-validation-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Aggregate held-out predictions: [`data/summary.json`](data/summary.json)
- Workflow, jobs, and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Repository artifacts contain each held-out threshold, candidate count, primary recall, and misses. The aggregate artifact is retained for 90 days. No raw model-call data is expected because there are no calls.

## Experiment Results

Leave-one-task-out recall was 2/3 in each repository. OpenClaw averaged 455 candidates but missed `src/gateway/server/ws-connection/message-handler.ts`: its held-out threshold was 18.9608, above that file's 13.1513 score. This confirms the 802-candidate V6 result depended on seeing the same tasks' labels. A fixed repository threshold is too high for lower-score task types and does not provide stable recall. Keep broad semantic retrieval as the current baseline; investigate query-adaptive uncertainty rescue on fresh tasks before considering weighted scores for production.
