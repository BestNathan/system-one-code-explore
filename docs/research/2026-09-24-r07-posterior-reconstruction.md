# R07 — Posterior Reconstruction

## Status

Completed on the first controlled fixture. The estimator definitions are now
frozen for holdout evaluation; do not tune them further on the websocket CC
reference.

## Question

Given a fixed set of sparse micro-block observations whose local System One
relevance scores are reasonably aligned with the CC reference, what estimator
best reconstructs the whole-file relevance frontier?

## Controlled setup

Held fixed:

- `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`;
- websocket optimization query;
- 3030-line websocket file;
- 32 recorded 8-line probes;
- probe order and action kinds;
- all local Jev relevance scores;
- validated CC full-read relevance field.

Only the deterministic posterior estimator changed.

Pinned fixtures:

- `fixtures/research/r07-websocket-v5b-trajectory.json`
- `fixtures/research/r07-websocket-cc-reference.json`

Implementation:

- `src/posterior_reconstruction.py`
- `src/posterior_reconstruction_benchmark.py`

Raw report:

- `docs/experiments/r07-posterior-reconstruction-2026-09-24.md`

## Result

Local Jev sample scoring is already reasonably strong:

```text
local score -> CC local relevance
Pearson ≈ 0.755
MAE     ≈ 0.171
```

The historical sequential posterior loses much of this information:

```text
32 probes:
Pearson  = 0.540
Spearman = 0.478
MAE      = 0.230
```

A path-independent multi-scale Gaussian posterior on the same observations
reconstructs:

```text
32 probes:
Pearson  = 0.798
Spearman = 0.785
MAE      = 0.177
```

Relative to the sequential baseline:

- MAE decreases about 23%;
- RMSE decreases about 23%;
- Pearson increases by 0.257 absolute;
- Spearman increases by 0.307 absolute;
- JS divergence decreases about 39%.

No extra source reads or model calls are used.

## Interpretation

The primary v5 information-loss layer was not local System One relevance
judgment. It was the sequential heuristic that propagated sparse observations
into a whole-file field.

A posterior should therefore be treated as a first-class replaceable component:

```text
observations
      |
      v
PosteriorEstimator
      |
      +--> relevance[N]
      +--> uncertainty[N]
```

The estimator must be recomputable from durable observations rather than depend
on mutation order.

## Important limitation

This experiment uses one file and one CC reference to compare estimator
families.

Therefore multi-scale Gaussian is the current **candidate**, not a universal
winner. Its definitions are now frozen before holdout evaluation.

In particular, do not tune:

- k values;
- prior weight;
- minimum bandwidth;
- maximum bandwidth;
- local/broad blend ratio

against this same websocket reference and then present the tuned result as
generalization evidence.

## Rejected idea

Retire the assumption that a fixed sequential exponential update is an adequate
probability-frontier posterior.

Keep it only as a historical baseline.

## Next direction

R08: integrate the path-independent posterior into the online Phase0 feedback
loop and validate the frozen estimators on holdout files/tasks.
