# Concept-Weighted Retrieval and Provenance Rescue V3

## Experiment Goal

Test whether counting high-signal aliases as one concept reduces file scoring while retaining all nine frozen primary targets, and whether file-level path provenance can replace the repository-wide 1% selection fallback. The operational target is a stable order-of-magnitude reduction in files sent for scoring on the largest repository, without imposing a fixed candidate limit.

## Experiment Design

Compare three arms on the same nine tasks and pinned Nession, Codex, and OpenClaw revisions: broad semantic lexical retrieval with a stable repository-population guard; concept-weighted retrieval with that same guard; and concept-weighted retrieval with provenance rescue. Concept retrieval counts each narrow alias group once, weights concepts by inverse path frequency and segment position, and admits a candidate when at least two distinct concepts match, one concept occurs in at most 2% of enumerated paths, or a filename match has a weighted score of at least 2.0. No result-count cap is used. Provenance rescue keeps the 0.65 absolute score threshold and rescues a score of at least 0.50 only when a rare matched path concept or filename concept supports it. The two weighted arms share identical file-score batches, so selection differences do not incur additional model calls. All arms use four independent concurrent requests through the shared System One client.

Primary metrics are candidate recall, final primary recall, scored-file count, selected-file count, reduction factor, directory decisions, physical and logical calls, tokens, cost, and wall time. Require 9/9 primary candidate recall before interpreting reduction; report task-level failures and misses. These nine diagnostic cases are not a fresh generalization set, and primary labels do not cover every supporting file.

## Experiment Process

The implementation tests first failed in GitHub Actions run [36228816265](https://github.com/BestNathan/system-one-code-explore/actions/runs/36228816265), confirming that the broad `filesystem` alias generated generic `file` and `system` evidence. A second red run is recorded after the full behavior tests are pushed. The preregistered experiment will run only through the `File Discovery — Algorithm Scaling Experiment` Workflow on `main` after code and frozen inputs are committed. The Workflow validates the full test suite before any paid calls, then archives call-level request and response records, manifests, per-task metrics, and aggregate reports.

## Experiment Data

- Frozen configuration: [`data/scaling-experiment.json`](data/scaling-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Shared System One transport: [`src/system_one_client.py`](../../../src/system_one_client.py)
- Workflow run, jobs, and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Each repository artifact contains task inputs, score traces, raw calls, call manifests, run JSON, metrics, and report output. Artifacts are retained for 90 days.

## Experiment Results

Pending the preregistered Workflow. The result will report per-repository candidate and final recall, reduction, model cost, directory decisions, failures, and whether the selection rescue can replace the repository-wide guard. No claim will be made from candidate-count reduction alone.
