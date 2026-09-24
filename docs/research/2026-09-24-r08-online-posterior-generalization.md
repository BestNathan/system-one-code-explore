# R08 — Online Posterior Feedback and Holdout Generalization

## Status

Completed. Phase C holdout search-effect validation did not confirm the Phase B single-fixture search advantage.

Phase A implementation is complete on `main`: the online runtime now accepts a
pluggable posterior estimator and recomputes the complete frontier from durable
observations.

Phase B is now complete. After `TYPESAFE_API_KEY` was configured in this
repository, workflow run `35978076501` was rerun successfully.

The workflow remains manual-only because it is a credentialed research
experiment and should not consume model calls on every normal `main` commit.

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

Completed on workflow run `35978076501`.

On the existing websocket benchmark both arms used:

- same source revision;
- same query;
- 32 x 8-line read budget;
- same mixed/spatially-diverse action-generation rules;
- same Choice batching rules;
- same `jev-latest` model;
- same CC full-read reference.

Only the online posterior estimator differed.

Final result:

| estimator | MAE ↓ | Pearson ↑ | Spearman ↑ | JS ↓ | input tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| sequential | 0.2520 | 0.4962 | 0.4336 | 0.1017 | 163,275 |
| multi-scale | **0.1995** | **0.7280** | **0.6877** | **0.0696** | 176,053 |

At the same 256 source-line budget, multi-scale improves:

- MAE by about 20.8%;
- Pearson by +0.232 absolute;
- Spearman by +0.254 absolute;
- JS divergence by about 31.6%.

The online trajectories diverge substantially: only 9 of 32 exact probe ranges
are shared (Jaccard ≈ 0.164). This demonstrates that the posterior changes the
active sampling path rather than merely redrawing the final field.

From 8 probes onward, multi-scale has higher Pearson at every recorded
checkpoint in this run. At 4 probes sequential is still slightly stronger,
consistent with the R07 finding that geometry-adaptive posteriors need a
minimum observation density.

Pinned evidence:

- `fixtures/research/r08-online-sequential-trajectory.json`
- `fixtures/research/r08-online-multiscale-trajectory.json`
- `docs/experiments/r08-online-posterior-ab-2026-09-24.md`

Conclusion:

> the R07 posterior improvement survives the online feedback loop and changes
> System One's exploration path in a beneficial direction on this fixture.

## Synthetic estimator-bias sanity check

Before real holdouts are available, a model-free sanity benchmark was added:

- `src/posterior_synthetic_benchmark.py`
- `docs/experiments/r08-posterior-synthetic-sanity-2026-09-24.md`

Five 1024-line truth fields were tested with the same deterministic 32-probe
stratified geometry:

- broad smooth peak;
- separated multi-peak;
- plateau;
- narrow spike;
- two separated steps.

The exact synthetic truth supplies probe scores, so this isolates posterior
geometry without model noise.

The sequential baseline performed poorly on multi-modal and discontinuous
fields, while frozen adaptive Gaussian estimators remained strong. For example:

```text
multi-peak Pearson:
  sequential = 0.098
  k2         = 0.989

two-step Pearson:
  sequential = 0.080
  k2         = 0.916

narrow-spike Pearson:
  sequential = -0.025
  k2         = 0.880
```

This is not real-code generalization evidence and must not replace Phase C.
It does strengthen the conclusion that sequential mutation has a structural
reconstruction weakness rather than only a websocket-specific weakness.

No estimator parameters were changed as a result.

## Phase C — Holdout generalization

**Completed.**

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

## Phase C pre-registration — holdout search effect

Before generating any new holdout reference, the first Phase C suite is frozen
in `docs/experiments/r08-holdout-search-effect-2026-09-24.md`.

This round evaluates three previously unused real-code file/task pairs, repeats
both online estimator arms twice, normalizes the source-read budget to about
8.5% of each file, and adds probe-order search metrics. The primary question is
now stricter than posterior fit:

> does a better probability frontier cause System One to find high-value source
> earlier and recover more relevance mass under the same sparse-read budget?

No R07 estimator parameters or current action-generation rules may be changed
after the holdout references are generated.


## Phase C result — field fit did not generalize to search

The pre-registered holdout suite completed on online run `35991332346`.
References were generated on executor run `35990577401` and then pinned under
`fixtures/research/`.

Across three holdouts x two repeats, the frozen multi-scale estimator improved
mean Pearson only because one holdout was reference-degenerate, while the
search metrics moved in the opposite direction:

- final high-line recall: 0.0977 sequential vs 0.0741 multi-scale;
- high-recall AUC/probe: 0.0431 vs 0.0321;
- weighted-recall AUC/probe: 0.0458 vs 0.0413;
- useful-probe rate: 0.5605 vs 0.4824;
- multi-scale won high-recall AUC on 0/3 holdouts.

The two discriminative holdouts both reproduced the same negative search
direction in both repeats.

Raw/aggregate details are in:

- `docs/experiments/r08-holdout-search-effect-2026-09-24.md`;
- `fixtures/research/r08-holdout-search-effect-summary.json`.

### Structural diagnosis

The failure is an uncertainty-semantics error.

The multi-scale relevance estimator uses adaptive Gaussian bandwidth. Its
current "uncertainty" is derived from Gaussian support. Because bandwidth grows
in sparse areas, support can remain high far from every observation. The
resulting uncertainty is therefore not epistemic coverage uncertainty.

On the reconnect holdout:

- sequential corr(uncertainty, nearest-observation distance): about +0.879;
- multi-scale: about -0.408;
- 99.1% of unread high-relevance lines ended with multi-scale uncertainty <=
  0.10.

On full-stack the corresponding values are +0.879 vs -0.167 and 78.3%.

That field is then consumed directly by the `uncertainty` action family, so
the posterior can improve relevance interpolation while simultaneously making
the search policy worse.

## R08 conclusion

The Phase B statement must be narrowed:

> multi-scale posterior reconstruction improved the websocket fixture's
> reconstructed relevance field and changed its trajectory.

It is **not** established that the current multi-scale
relevance+uncertainty posterior improves search generally.

R08 therefore closes with a negative generalization result and one concrete
architectural requirement:

> relevance posterior and exploration uncertainty must be modeled as separate
> state.

R09 will change only uncertainty semantics while keeping the multi-scale
relevance reconstruction fixed, and will validate search behavior on fresh
holdouts.
