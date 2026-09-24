# R08 Holdout Search-Effect Experiment — 2026-09-24

## Status

Pre-registered before generating any holdout reference.

This experiment extends R08 Phase C from posterior-field fit to **search
behavior**. No estimator parameter, action-generation rule, Choice threshold,
or holdout definition may be changed after inspecting the references/results
from this round.

## Fixed subject

- repository: `BestNathan/nession`
- revision: `7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- System One model: repository `typesafe` environment's pinned model
- reference model: repository `ds` environment's pinned explicit model

## Holdouts

These files/tasks were selected from source structure before reference
generation and were not used by the R07 websocket posterior fit.

### H1 — reconnect lifecycle

File:

`crates/nession-agent/src/connection/server_client.rs`

Task:

> Help me improve the agent-to-server reconnect lifecycle: exponential backoff,
> registration after reconnect, connected/sync-needed state transitions, and
> behavior of queued outbound messages while disconnected.

Intent: long source file with lifecycle behavior expected to be spread across
multiple regions.

### H2 — protocol catalog consistency

File:

`crates/nession-protocol-codegen/src/catalog.rs`

Task:

> Help me make protocol contract generation safer: locate the catalog code that
> defines unit identity and wire/request/response mappings and the checks that
> prevent missing, duplicate, or non-self-contained generated contracts.

Intent: catalog declarations plus validation/tests are expected to form a
multi-peak relevance shape.

### H3 — full-stack command lifecycle

File:

`crates/nession-server/tests/integration/full_stack.rs`

Task:

> I am debugging the server's agent command lifecycle. Locate the
> integration-test code that exercises agent registration, command
> request/response routing, disconnect or reconnect behavior, and cleanup of
> pending work.

Intent: large integration-test file with many unrelated sections and relevant
tests expected in separated regions.

## Frozen online policy

Compare only:

- `sequential_exponential`
- `multi_scale_gaussian`

Keep fixed:

- sample width: 8 lines;
- max action candidates: 16;
- max Choice batch: 4;
- default Choice probability threshold;
- `respect_stop=false` so both arms consume the same fixed budget;
- mixed stratified-random / uncertainty / gradient / peak action generation;
- posterior definitions from R07 unchanged.

Probe budget is normalized by file length:

`max(8, min(32, round(line_count * 0.085 / 8)))`

This targets roughly the same 8.5% source-line budget as the R08 websocket run
while keeping a minimum number of decisions for smaller holdouts.

Each estimator is repeated twice per holdout. Candidate geometry remains
deterministically seeded; repeats measure model-policy/scoring variability.

## Reference

For each holdout, generate one fresh full-read System 2 relevance field using
the existing 64-line / 32-line-stride reference protocol.

The reference is evaluation data, not ground truth and not an input to the
online policy.

## Metrics

Retain the existing posterior-fit metrics:

- MAE / RMSE;
- Pearson / Spearman;
- Jensen-Shannon distance;
- high-relevance recall of the reconstructed field.

Add search-oriented metrics over the **actual probe order**:

- first probe touching a high-relevance line;
- first probe touching a core line;
- probes to 50% / 80% high-line recall;
- final high-line recall at the fixed source budget;
- final relevance-mass recall;
- useful-probe rate;
- mean reference relevance of selected probes;
- high-line-recall AUC per probe;
- relevance-mass-recall AUC per probe;
- exact trajectory Jaccard between estimator arms;
- model calls, input tokens, output tokens, and elapsed time.

The AUC-per-probe metrics are the primary search-effect measures because they
reward finding useful regions early, not only eventually.

## Interpretation guardrail

A positive result requires improvement across multiple holdouts and should not
be claimed from aggregate field correlation alone.

If results suggest changing posterior parameters, action quotas, or thresholds,
that change starts a new research iteration with a new evaluation split.
