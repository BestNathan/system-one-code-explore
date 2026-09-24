# R08 — Online Posterior Feedback and Holdout Generalization

## Status

Current research direction.

Phase A implementation is complete on `main`: the online runtime now accepts a
pluggable posterior estimator and recomputes the complete frontier from durable
observations.

Phase B workflow is implemented at
`.github/workflows/r08-online-posterior-ab.yml`, but the first run
(`35978076501`) stopped before model execution because the new repository's
`typesafe` environment does not currently expose `TYPESAFE_API_KEY`.

This is an experiment-environment blocker, not an algorithm result. The
workflow is manual-only until that credential exists in this repository, so
normal research commits do not produce expected red Actions runs.

## Question

R07 showed that a path-independent posterior can reconstruct the fixed
websocket relevance field much better from the same observations.

Two questions remain:

1. Does that advantage survive when the posterior participates online and
   therefore changes which probes System One chooses next?
2. Does the frozen estimator generalize to files/tasks not used during R07?

## Hypothesis

A better calibrated relevance/uncertainty frontier should improve the probe
policy itself because future Choice decisions see a more faithful global
distribution.

However, the feedback loop can also amplify estimator bias:

```text
posterior
   -> action pool / Choice
   -> new observations
   -> posterior
   -> ...
```

Therefore offline replay improvement is necessary but not sufficient.

## Phase A — Online integration

Refactor Phase0 to depend on a posterior interface rather than directly mutate
the frontier:

```text
PosteriorEstimator.reconstruct(
    observations,
    line_count
) -> {
    relevance[N],
    uncertainty[N]
}
```

Support at least:

- `sequential_exponential` baseline;
- `adaptive_gaussian_k2`;
- `adaptive_gaussian_k3`;
- `multi_scale_gaussian`.

After every individual observed micro-block, recompute the whole frontier from
durable observations. A Choice-selected batch is still chosen from one
pre-batch state, but each resulting observation is persisted independently.

Implemented in:

- `src/posterior_reconstruction.py`
- `src/system_one_probability_frontier.py`

The historical `update_probability_frontier` remains only for compatibility
and regression comparison. The online runtime uses
`append_probability_sample + rebuild_probability_frontier`.

A regression test proves that the pluggable
`sequential_exponential` estimator reproduces the old mutation behavior for
the same ordered samples.

Do not change the current mixed/spatially-diverse action generator in this
phase.

## Phase B — Same-task online A/B

On the existing websocket benchmark:

- same source revision;
- same query;
- same read budget;
- same action-generation rules;
- same System One model;
- estimator is the only intended algorithmic change.

Because the posterior changes Choice state, trajectories are expected to
diverge. Compare convergence and read efficiency rather than expecting matched
probe locations.

## Phase C — Holdout generalization

Freeze all R07 estimator parameters before generating new references.

Select multiple holdout files/tasks that exhibit different relevance shapes,
for example:

- one localized implementation hotspot;
- one multi-peak cross-cutting implementation;
- one long file with mostly irrelevant tail/tests;
- one file where relevant logic is spread across several distant regions.

For each holdout:

1. create a fresh full-read System 2 reference;
2. run the same fixed estimator variants;
3. compare convergence curves;
4. report aggregate as well as per-file metrics.

## Success criteria

A candidate posterior should:

- improve average holdout MAE/RMSE;
- improve correlation/ranking on most holdouts, not only one;
- avoid systematic uncertainty collapse;
- reduce the number of probes needed to reach a target frontier quality;
- remain deterministic for a fixed observation set.

## Guardrail

Do not use holdout CC references to change estimator parameters during the same
evaluation round.

If a parameter is changed after inspecting holdout results, start a new
research iteration with a new train/validation split and record that decision.
