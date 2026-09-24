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
- **R08 — Online posterior feedback and holdout search:** a better relevance posterior changed the online path, but its support-derived uncertainty failed holdout search generalization.

Canonical details live in `docs/research/README.md`.

## Current milestone — R09 uncertainty calibration and search policy

R08 identified a structural separation that the runtime must make explicit:

```text
relevance interpolation
    !=
epistemic need-to-observe
```

R09 keeps the multi-scale relevance reconstruction unchanged and introduces a
conservative observation-distance lower bound for exploration uncertainty.

The first R09 round is pre-registered on three fresh holdouts:

- agent filesystem read/chunking safety;
- tmux lifecycle and cleanup safety;
- web terminal attach/reconnect lifecycle.

Primary success criteria are search-oriented:

- higher high-relevance recall AUC per probe;
- higher relevance-mass recall AUC per probe;
- better fixed-budget high-line recall;
- improved useful-probe rate;
- no uncertainty collapse in distant unread regions.

R08 holdouts are diagnosis-only and cannot be used as R09 generalization
evidence.

## After R09

If the uncertainty guard generalizes on fresh holdouts, promote the split
relevance/uncertainty state model into the default probability frontier. If it
does not, preserve the R09 data and open a new iteration rather than tuning on
the same validation references.

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
