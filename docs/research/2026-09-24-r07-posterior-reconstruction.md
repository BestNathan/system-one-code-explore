# R07 — Posterior Reconstruction

## Status

Next controlled research direction.

## Question

Given a fixed set of sparse micro-block observations whose local System One
relevance scores are already reasonably aligned with the CC reference, what
estimator best reconstructs the whole-file relevance frontier?

## Why this is the next variable

R06 isolated a clear gap:

```text
local sample scorer:
  Pearson ≈ 0.755
  MAE ≈ 0.168

current whole-file reconstruction:
  Pearson = 0.540
  MAE = 0.230
```

The current v5 update applies sequential exponential propagation around each
observation. It is heuristic and path dependent.

## Hypothesis

A path-independent estimator that recomputes the whole field from all current
observations should preserve more of the local scoring signal.

## Controlled experiment

Keep fixed:

- frozen subject revision;
- query;
- CC full-read reference field;
- probe width;
- corrected mixed/spatially-diverse probe policy;
- recorded sparse observations and local System One scores.

Change only the posterior estimator.

Candidate estimators:

1. **Sequential exponential update** — current baseline.
2. **Kernel regression** — reconstruct every line from all observations.
3. **Multi-scale kernel posterior** — combine local and broad spatial kernels.
4. **Uncertainty-aware kernel posterior** — keep relevance and epistemic
   uncertainty separate.
5. **System One field update** — optionally ask the model to update or select
   among candidate frontier transforms after deterministic estimators are
   understood.

## Evaluation

At every probe checkpoint compare the reconstructed line-level field with the
same CC reference:

- MAE;
- RMSE;
- Pearson;
- Spearman;
- top-K relevance recall;
- high-relevance recall;
- Jensen-Shannon divergence;
- Wasserstein position distance;
- uncertainty calibration;
- compute/token cost.

The important output is the convergence curve, not one final score.

## Experimental discipline

Do not choose kernel bandwidth or other estimator hyperparameters using the
same CC reference and then report that tuned result as unbiased benchmark
performance.

If the reference is used to explore hyperparameters, record that run explicitly
as diagnostic only.

## Success criterion

Find a reconstruction method where additional accurate observations generally
improve the global relevance shape, rather than merely reduce uncertainty.

A strong result would close a meaningful fraction of the gap between local
sample-score correlation (~0.755) and current whole-field correlation (0.540)
without increasing source-read budget.
