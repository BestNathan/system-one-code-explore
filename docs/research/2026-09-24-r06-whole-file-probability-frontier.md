# R06 — Whole-file Probability Frontier

**Implementation lineage:** PR #10 is the merged whole-file probability-frontier implementation; it also carried forward the still-valid tests and research artifacts from PRs #5, #6, and #8.

## Question

Can sparse System One observations reconstruct the complete relevance
distribution that a full-read System 2 evaluator sees?

## Hypothesis

Phase0 should maintain one relevance and uncertainty value per source line, let
System One see the full distribution shape, and actively choose sparse
micro-probes that improve that distribution.

## State

For a file with `N` lines:

```text
ProbabilityFrontier {
  relevance[N]
  uncertainty[N]
  observed[N]
  samples[]
}
```

The model view quantizes relevance and uncertainty to one hexadecimal digit per
line. A 3030-line file therefore remains cheap enough to expose as a whole
shape rather than a small set of summaries.

## Probe policy

The corrected v5 action pool mixes:

- stratified random exploration;
- high uncertainty;
- high relevance gradient;
- neighborhoods around current relevance peaks.

Candidate positions are spatially separated.

Choice is used as a distribution rather than only an argmax. Multiple probes
may execute in one epoch when their Choice probability clears the configured
threshold.

## Controlled benchmark

Reference:

- fixed CC full-read field from R03.

Corrected v5 run:

- workflow run `35965124785`;
- 32 probes;
- 8 lines per probe;
- 256 unique source lines read;
- 8.45% of the 3030-line file;
- 15 model calls;
- 141,627 input tokens.

Convergence:

| probes | MAE ↓ | Pearson ↑ | Spearman ↑ | JS ↓ |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 0.2771 | 0.3896 | 0.4299 | 0.1126 |
| 8 | 0.2789 | 0.2835 | 0.3049 | 0.1150 |
| 12 | 0.2620 | 0.4576 | 0.3685 | 0.1076 |
| 16 | 0.2495 | 0.5689 | 0.4984 | 0.1006 |
| 24 | 0.2411 | 0.5066 | 0.4794 | 0.0999 |
| 32 | 0.2298 | 0.5403 | 0.4782 | 0.0948 |

Raw report:

- `docs/experiments/probability-frontier-v5-convergence-2026-09-24.md`

## Critical diagnosis

The local 8-line System One scores are significantly better than the final
reconstructed field.

Across the corrected probes:

- local score vs CC local relevance Pearson ≈ 0.755;
- local score MAE ≈ 0.168.

The reconstructed whole-file field ends at:

- Pearson = 0.540;
- MAE = 0.230.

Therefore the dominant loss is currently:

```text
sparse observations
      ->
whole-file posterior reconstruction
```

not primarily:

```text
source micro-block
      ->
System One relevance score
```

## Rejected idea

Do not assume that monotonically decreasing uncertainty means the frontier is
becoming more correct. The current estimator becomes more confident while rank
correlation can fall.

## Next direction

Hold the probe observations/policy fixed and isolate the posterior estimator.
