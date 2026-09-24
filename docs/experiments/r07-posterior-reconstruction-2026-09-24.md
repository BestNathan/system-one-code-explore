# R07 Posterior Reconstruction Experiment — 2026-09-24

## Controlled variable

This experiment replays the **same 32 recorded System One probes and local
relevance scores** through several posterior estimators.

Nothing else changes:

- same frozen nession file;
- same query;
- same 8-line probes;
- same probe order;
- same Jev local scores;
- same validated CC full-read reference.

Therefore differences in the result come from only:

```text
sparse observations -> whole-file probability frontier
```

## Fixtures

The research inputs are now pinned inside this repository:

- `fixtures/research/r07-websocket-v5b-trajectory.json`
- `fixtures/research/r07-websocket-cc-reference.json`

This removes the R07 benchmark's runtime dependency on the older
`narness-engineering` workflow artifacts.

## Estimators

### Sequential exponential

The v5 baseline. Each observation mutates the current frontier and propagates
locally with an exponential decay.

Properties:

- path dependent;
- fixed propagation scale;
- uncertainty changes incrementally.

### Adaptive Gaussian k=2 / k=3 / k=4

Recompute the complete frontier from all observations.

For every source line, bandwidth is determined from observation geometry:

```text
bandwidth(line)
  = clamp(
      distance to k-th nearest observed sample,
      4 * probe_width,
      file_length / 12
    )
```

No CC reference value participates in reconstruction.

### Multi-scale Gaussian

Blend:

- local adaptive Gaussian `k=2`;
- broad adaptive Gaussian `k=4`.

The local field receives twice the confidence weight. This preserves sharper
observed structure while allowing the broader field to fill sparse areas.

## Local scorer check

Before studying reconstruction, compare the raw Jev score for each observed
8-line block with the CC relevance field at that location.

Across all 32 probes:

- Pearson: **0.7550**
- MAE: **0.1709**

This confirms that a large part of the remaining error is downstream of local
System One scoring.

## Convergence results

### Sequential exponential baseline

| probes | MAE ↓ | Pearson ↑ | Spearman ↑ |
| ---: | ---: | ---: | ---: |
| 4 | 0.2771 | 0.3896 | 0.4299 |
| 8 | 0.2789 | 0.2835 | 0.3049 |
| 12 | 0.2620 | 0.4576 | 0.3685 |
| 16 | 0.2495 | 0.5689 | 0.4984 |
| 24 | 0.2411 | 0.5066 | 0.4794 |
| 32 | 0.2298 | 0.5403 | 0.4782 |

### Adaptive Gaussian k=2

| probes | MAE ↓ | Pearson ↑ | Spearman ↑ |
| ---: | ---: | ---: | ---: |
| 4 | 0.2929 | 0.2916 | 0.3806 |
| 8 | 0.2835 | 0.2014 | 0.2935 |
| 12 | 0.2279 | 0.6226 | 0.4959 |
| 16 | 0.1919 | 0.7798 | 0.7535 |
| 24 | 0.1901 | 0.7706 | 0.7441 |
| 32 | **0.1777** | 0.7956 | 0.7079 |

### Adaptive Gaussian k=3

| probes | MAE ↓ | Pearson ↑ | Spearman ↑ |
| ---: | ---: | ---: | ---: |
| 4 | 0.2929 | 0.2916 | 0.3805 |
| 8 | 0.2913 | 0.0867 | 0.2875 |
| 12 | 0.2395 | 0.5696 | 0.5525 |
| 16 | 0.1925 | 0.7739 | **0.8152** |
| 24 | 0.1898 | 0.7572 | **0.8176** |
| 32 | 0.1799 | 0.7687 | **0.8028** |

### Multi-scale Gaussian

| probes | MAE ↓ | Pearson ↑ | Spearman ↑ |
| ---: | ---: | ---: | ---: |
| 4 | 0.2929 | 0.2916 | 0.3806 |
| 8 | 0.2875 | 0.1575 | 0.2978 |
| 12 | 0.2347 | 0.6011 | 0.5213 |
| 16 | 0.1934 | 0.7771 | 0.7944 |
| 24 | 0.1899 | 0.7697 | 0.7973 |
| 32 | **0.1769** | **0.7977** | **0.7849** |

At the 32-probe checkpoint, multi-scale versus the sequential baseline:

- MAE: `0.2298 -> 0.1769` (**23.0% lower**)
- RMSE: `0.2578 -> 0.1976` (**23.4% lower**)
- Pearson: `0.5403 -> 0.7977` (**+0.2574 absolute**)
- Spearman: `0.4782 -> 0.7849` (**+0.3067 absolute**)
- JS divergence: `0.0948 -> 0.0578` (**about 39% lower**)

No additional source line or model call is required. The change is entirely in
the deterministic posterior reconstruction.

## Interpretation

### The posterior was the dominant v5 information-loss layer

The raw local observations already contain much more useful signal than the
sequential frontier preserved.

The path-independent estimators recover a substantial part of that signal.

### More observations are not automatically useful at very small sample counts

At 4–8 probes, adaptive kernels can be worse than the sequential baseline
because sparse geometry forces very broad interpolation.

The gain becomes clear around 12–16 probes.

This implies that posterior choice may itself need to depend on observation
density rather than use one estimator at every stage.

### There is no single universal winner yet

On this one fixture:

- k=2 is strongest on final Pearson / absolute error;
- k=3 is strongest on rank shape at several checkpoints;
- multi-scale gives the strongest final balance.

This is **not enough evidence** to declare multi-scale universally best.

The same CC reference was used to compare these candidates, so the next stage
must evaluate frozen estimator definitions on holdout files/tasks.

## Decision

Retire sequential exponential propagation as the only posterior model.

Keep it as a baseline, and add path-independent reconstruction as a first-class
runtime abstraction.

## Next research question

Can the improved posterior still help when it participates in the **online
feedback loop** that generates future probes, and does the result generalize to
new files/tasks that were not used to compare these estimators?
