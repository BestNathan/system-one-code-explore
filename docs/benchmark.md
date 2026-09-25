# Benchmark Contract

## Purpose

Compare System One localization with a stronger System Two reference on the same repository/task, while treating quality and cost as co-equal outcomes.

System Two is a **reference**, not ground truth. Relevant code is often non-unique and the reference model can also be noisy.

## Benchmark unit

Every case freezes: repository, revision, verbatim task, target scope, model/runtime configuration, reference protocol, and candidate parameters before hidden evaluation.

## Current reference protocol

For in-file evidence localization, the reference model sees the complete target file and scores overlapping source windows. The established protocol uses 64-line windows with 32-line stride.

For file discovery, a strong repository-level reference is still missing. Building it is a first-class project milestone rather than treating historical Phase-1 scores as a finished benchmark.

## Current datasets

- **Mechanism set:** R08/R15-R17 cases on `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`: reconnect lifecycle, protocol catalog consistency, full-stack command lifecycle.
- **Fresh holdout set:** R18 adds fs symlink/delete semantics, tmux environment/session lifecycle, and manifest union/wire routing. These were selected before hidden references were generated.
- **Pinned results:** canonical references, trajectories, and aggregates live under `fixtures/research/`.

The corpus is still too small and too concentrated in one repository to claim general code-search generalization.

## Quality metrics

### File discovery

- relevant-file recall and precision;
- primary/supporting files missed;
- irrelevant files promoted;
- files/metadata inspected before useful files are found.

### Evidence localization

- hidden high-region recall;
- high-line recall and precision;
- retained mean reference relevance;
- relevance-mass recall;
- missed independent relevance modes;
- semantic truncation/completeness;
- redundancy between final evidence spans.

Navigation/materialization and final retained evidence are evaluated separately.

## Cost metrics

Every model-using benchmark must report:

```text
model_calls
input_tokens
output_tokens
model_wall_time_ms
source_lines_read
metadata_items_seen
cache_hits
cache_misses
```

Where possible, attribute cost by phase: file discovery, Phase0 sensing, obligation generation, semantic closure, and final utility.

Repeated runs should report mean and tail behavior. If the sample is too small for a meaningful p95, report the maximum.

Useful efficiency views include recall per 100k tokens, recall per model call, retained relevance mass per 100k tokens, and useful evidence per model second.

## Pareto rule

A method does not win merely because recall is higher. It must be judged on the quality-cost Pareto frontier.

- Reading most of a file to gain a little recall is not automatically better.
- Stopping cheaply while missing independent evidence is not better.
- A more accurate Phase0 can be cheaper end-to-end if it prevents false obligations and closure work.

## Experimental controls

### Freeze before hidden evaluation

Do not tune parameters or task wording after inspecting the hidden reference and then claim generalization.

### Shared semantic decisions

R18 exposed a causal A/B flaw: identical semantic states can receive slightly different independent System One probabilities, and a hard threshold can turn that noise into a fake policy win.

For policy A/B tests, identical semantic requests must receive the same cached System One response. Report logical standalone cost separately from physical cached execution cost.

### Mechanism vs generalization

Repeatedly inspected cases answer whether a mechanism works. Fresh frozen holdouts answer whether it generalizes. Keep those claims separate.

## Durable artifacts

- `fixtures/research/`: pinned references, trajectories, aggregates.
- `docs/experiments/`: frozen protocols and detailed results.
- `docs/research/`: interpretation and decisions.

Workflow artifacts are execution evidence, but conclusions should not depend on ephemeral artifacts alone.