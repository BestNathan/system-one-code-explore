# Roadmap

## Research objective

Build a general **System One Code Exploration Runtime** in which the harness owns state, legal actions, effects, budgets, and durability while a fast model supplies bounded policy decisions.

## Completed research path

- **R01 — Range runtime baseline:** bounded adaptive reads and stopping behavior.
- **R02 — Adaptive relevance frontier:** useful experiment, but coarse region scores were the wrong state abstraction.
- **R03 — Full-read System 2 reference:** fixed distribution-level evaluation target.
- **R04 — Choice and evidence closure:** Choice works as a policy distribution; isolated fragment keep/drop does not.
- **R05 — Sparse Phase0:** sparse sensing is viable; collapsing samples into a few coarse scores is not.
- **R06 — Whole-file probability frontier:** represent relevance and uncertainty at file length.
- **R07 — Posterior reconstruction:** separate durable observations from a replaceable, path-independent posterior estimator.
- **R08 Phase A/B — Online posterior feedback:** posterior choice changes the online sampling path and improves the websocket fixture.

Canonical details live in `docs/research/README.md`.

## Current milestone — R08 Phase C holdout generalization

Estimator parameters are frozen before holdout references are inspected.

Evaluate multiple files/tasks with materially different relevance geometry:

- localized implementation hotspot;
- separated multi-peak implementation;
- long mostly irrelevant tail/test region;
- distant relevant regions in the same file.

For each holdout:

1. create a fresh full-read System 2 reference;
2. run the same frozen estimator variants;
3. compare convergence curves and source-read budgets;
4. report per-file and aggregate metrics;
5. record failures instead of retuning against the same holdout set.

Exit criteria:

- improved average MAE/RMSE;
- improved ranking/correlation on most holdouts rather than one fixture;
- no systematic uncertainty collapse;
- fewer probes to reach a target frontier quality;
- deterministic reconstruction for a fixed observation set.

## After R08

If the posterior generalizes, promote it from a research candidate into the default frontier component and then resume broader exploration-runtime work. If it fails, open a new research iteration with an explicit train/validation split rather than tuning against R08 holdouts.

Longer-term runtime milestones remain:

### Observation-driven cross-file actions

Progressively disclose grounded actions such as `FollowFile`, `FollowSymbol`, `InspectCaller`, and `InspectCallee` from observations rather than eagerly building a complete semantic graph.

### Evidence shaping

Separate navigation from final evidence presentation: shrink useful observations, classify primary/supporting context, and measure precision, redundancy, and downstream actionability.

### Context and cost efficiency

Reduce repeated state transmission with deltas, stable observation references, cache-friendly prefixes, compact histories, and bounded batching. Track monetary cost as well as latency and tokens.

### Durable scheduler

Move exploration behind a scheduler/effect abstraction supporting pause/resume, event logging, replay, explicit resource budgets, bounded concurrency, priority, and forkable branches.

### System One / System 2 hybrid

Use System One for fast decisions inside disclosed state spaces and System 2 only when the runtime must create or reshape the state/action space.

## Evaluation discipline

Every algorithm change should record:

1. frozen subject revision and verbatim task;
2. model/runtime configuration;
3. source-read and model-call budgets;
4. frontier convergence and uncertainty behavior;
5. fixed-reference metrics where applicable;
6. blind downstream-quality impact where applicable;
7. omissions and failure modes;
8. repeated-run variance;
9. whether parameters were frozen before evaluation.

Do not treat Claude overlap alone as ground truth, and do not retune a candidate on the same holdout evidence used to claim generalization.
