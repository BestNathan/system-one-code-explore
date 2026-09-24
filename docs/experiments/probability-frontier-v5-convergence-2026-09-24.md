# Probability Frontier v5 convergence — 2026-09-24

## Goal

Evaluate Phase0 as a whole-file distribution reconstruction problem:

```text
sparse System One observations
        ->
P(relevance)[1..line_count]
        ->
approach the validated CC full-read relevance field
```

Subject:

- repository: `BestNathan/nession`
- revision: `7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- file: `crates/nession-agent/src/server/websocket.rs`
- line count: 3030
- query: `Help me optimize the websocket connection implementation`

Reference:

- Claude Code runtime through the `ds` environment
- routed model: `deepseek-flash`
- validated 94-window full-read field
- reference workflow run: `35959563085`

## v5 implementation

Phase0 now exposes file-length fields rather than coarse regions:

```text
relevance[3030]
uncertainty[3030]
observed[3030]
```

The System One view uses one q16 digit per line for relevance and uncertainty.

Probe actions mix:

- stratified random exploration;
- high uncertainty;
- relevance gradients;
- relevance-peak neighborhoods.

Choice is consumed as a probability distribution. Multiple probes above the
probability threshold can execute in one epoch.

The convergence benchmark forces a 32-probe budget and snapshots the frontier
after every individual probe. Checkpoints are read from one trajectory, so
4/8/12/16/24/32 are directly comparable.

## First run and action-space bug

Run `35964776462` exposed a probe-diversity defect. Later batches contained
nearly duplicate ranges such as:

```text
2071-2078
2070-2077
2069-2076
```

The action generator also filled the pool with random + uncertainty candidates
before gradient/peak families could reliably enter.

This run is retained as diagnostic evidence but is not the corrected v5
baseline.

## Corrected v5 baseline

Run: `35965124785`

The corrected generator reserves action-family quotas and enforces a minimum
source-space separation between candidate probes.

| probes | unique source lines | MAE ↓ | RMSE ↓ | Pearson ↑ | Spearman ↑ | JS ↓ | Wasserstein ↓ | mean uncertainty ↓ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 32 | 0.2771 | 0.3092 | 0.3896 | 0.4299 | 0.1126 | 0.1411 | 0.9039 |
| 8 | 64 | 0.2789 | 0.3108 | 0.2835 | 0.3049 | 0.1150 | 0.1420 | 0.8290 |
| 12 | 96 | 0.2620 | 0.2957 | 0.4576 | 0.3685 | 0.1076 | 0.1377 | 0.7434 |
| 16 | 128 | 0.2495 | 0.2829 | 0.5689 | 0.4984 | 0.1006 | 0.1304 | 0.6845 |
| 24 | 192 | 0.2411 | 0.2731 | 0.5066 | 0.4794 | 0.0999 | 0.1144 | 0.5795 |
| 32 | 256 | 0.2298 | 0.2578 | 0.5403 | 0.4782 | 0.0948 | 0.1146 | 0.4799 |

Runtime at 32 probes:

- model calls: 15
- input tokens: 141,627
- output tokens: 1,736
- source read: 256 / 3030 lines = 8.45%

## What the experiment says

### 1. The global distance improves, but the shape does not converge smoothly

MAE, RMSE and JS improve overall as more observations arrive.

Pearson/Spearman are not monotonic. In particular, the ranking shape can get
worse even while average absolute error improves.

Therefore "lower uncertainty" currently does not imply "better calibrated
frontier."

### 2. Local System One relevance scoring is stronger than the reconstructed field

Across the 32 corrected probes, compare each Jev micro-block relevance score
with the CC line-field value at the same source location:

- local-score Pearson: approximately 0.755
- local-score MAE: approximately 0.168

That is materially stronger than the final reconstructed whole-file field:

- whole-field Pearson: 0.540
- whole-field MAE: 0.230

The dominant loss is therefore currently in the posterior/reconstruction step,
not primarily in the local micro-block scorer.

### 3. The current posterior update is heuristic

v5 currently applies sequential exponential local updates around each observed
micro-block.

That estimator is:

- order dependent;
- sensitive to the propagation radius;
- able to become more confident without improving rank correlation;
- not recomputed globally from the complete observation set.

The next experiment should change only the posterior estimator while keeping
the corrected mixed/diverse probe policy fixed.

## Next controlled experiment

Compare posterior estimators over the **same probe observations**:

```text
A. current sequential exponential update
B. path-independent kernel regression from all samples
C. multi-scale kernel posterior
D. optional learned/System-One distribution update
```

Do not tune estimator hyperparameters against the test CC field and then report
that same run as benchmark performance.

For each estimator preserve the same convergence metrics and probe budget.

A useful diagnostic performed on the recorded observations shows that a
path-independent kernel estimator can recover substantially more of the CC
field than the current sequential update. That diagnostic used the reference
field to inspect bandwidth behavior, so it is evidence for the direction only,
not a valid benchmark result.

## Current conclusion

The v5 architecture validates the probability-frontier framing:

- a few-thousand-position whole-file frontier is practical to expose;
- Choice can drive a multi-probe batch;
- randomized/diverse probing is reproducible;
- 8.45% source reading already changes the global field materially.

The next bottleneck is now isolated:

> convert sparse, reasonably accurate local relevance observations into a
> stable whole-file probability frontier without destroying uncertainty or
> distribution shape.
