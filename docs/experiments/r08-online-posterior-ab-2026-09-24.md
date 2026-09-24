# R08 Online Posterior A/B — 2026-09-24

## Question

R07 showed that path-independent posterior reconstruction is much better when
replaying a fixed probe trajectory.

This experiment asks whether the advantage survives the **online feedback
loop**, where the posterior changes the state shown to System One and therefore
changes future probe choices.

## Controlled setup

Both runs use:

- subject: `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- file: `crates/nession-agent/src/server/websocket.rs`
- query: `Help me optimize the websocket connection implementation`
- model: `jev-latest`
- 8-line probes
- 32-probe budget
- same mixed/spatially-diverse action generator
- same Choice batching rules
- same CC full-read reference

Only the online posterior estimator differs:

- `sequential_exponential`
- `multi_scale_gaussian`

Workflow run:

- `35978076501`
- successful rerun after `TYPESAFE_API_KEY` was configured in this repository

Compact trajectories are pinned in:

- `fixtures/research/r08-online-sequential-trajectory.json`
- `fixtures/research/r08-online-multiscale-trajectory.json`

## Final result

| estimator | source lines | MAE ↓ | RMSE ↓ | Pearson ↑ | Spearman ↑ | JS ↓ | calls | input tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sequential | 256 | 0.2520 | 0.2829 | 0.4962 | 0.4336 | 0.1017 | 17 | 163,275 |
| multi-scale | 256 | **0.1995** | **0.2240** | **0.7280** | **0.6877** | **0.0696** | 17 | 176,053 |

Multi-scale therefore improves, at the same source-read budget:

- MAE by about **20.8%**
- RMSE by about **20.8%**
- Pearson by **+0.232 absolute**
- Spearman by **+0.254 absolute**
- JS divergence by about **31.6%**

Model-call count is unchanged. Input tokens increase by about **7.8%** because
the multi-scale frontier exposed to later Choice calls differs from the
sequential state.

## Convergence

| probes | sequential Pearson | multi-scale Pearson |
| ---: | ---: | ---: |
| 4 | **0.3783** | 0.3313 |
| 8 | 0.2519 | **0.6490** |
| 12 | 0.4684 | **0.7065** |
| 16 | 0.4372 | **0.6312** |
| 24 | 0.3869 | **0.6446** |
| 32 | 0.4962 | **0.7280** |

The multi-scale posterior is initially slightly worse at 4 probes, which
matches the R07 observation that geometry-adaptive reconstruction needs enough
spatial support.

From 8 probes onward it is consistently stronger in this online run.

## Feedback-loop effect

The estimator does not merely redraw the same trajectory.

Only **9 of 32** exact probe ranges are shared between the two online runs
(Jaccard ≈ **0.164**). About 19/32 sequential probes have a multi-scale probe
within 16 source lines.

So the posterior materially changes the policy state and therefore the
exploration path.

Examples unique to the multi-scale trajectory include gradient probes around:

- 400–407
- 437–444

and a different collection of broad/random/uncertainty probes.

This matters because the final improvement is not just an offline interpolation
artifact: the better posterior changes which source is observed next and still
ends closer to the CC full-read relevance field.

## Cost

Runtime in this single run:

- sequential: ~7.75 s
- multi-scale: ~9.55 s

Multi-scale is about 1.23x slower end-to-end and uses 1.078x input tokens.

The extra deterministic posterior computation itself is small; most of the
token increase comes from changed online state/trajectory and should be treated
as part of the active-policy effect.

## Conclusion

R08 Phase B supports the R07 architectural decision:

> posterior reconstruction is not merely an evaluation-layer improvement; it
> changes the online active-sampling policy in a beneficial direction.

The result is still one real-code fixture. It does not establish generalization.

## Next step

Proceed to R08 Phase C:

- freeze the current estimator definitions;
- generate fresh CC full-read references for holdout files/tasks;
- run the same sequential vs frozen path-independent variants;
- report per-file and aggregate convergence without tuning on the holdouts.
