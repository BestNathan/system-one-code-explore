# R08 Holdout Search-Effect Results — 2026-09-24

## Status

Completed.

The credentialed rerun in the new repository succeeded after the `ds`
environment was configured.

Canonical run:

- workflow: `R08 holdout search effect`
- run: `36004833542`
- harness commit: `3b8a8a5273b6fe9ec91ea7e5753d91add46ec9df`
- subject: `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- 3 holdouts
- 2 repeats per holdout
- 6 paired sequential vs multi-scale online runs
- all reference, online, and aggregate jobs succeeded

The full-read references were generated inside
`BestNathan/system-one-code-explore` using the configured `ds` environment.
All three references passed canonical normalization on their first accepted
attempt in the final run.

Compact result data is pinned in:

- `fixtures/research/r08-holdout-search-effect-aggregate.json`
- `fixtures/research/r08-frontier-uncertainty-diagnostic.json`

## Main result

The holdouts separate **posterior reconstruction quality** from **active search
quality**.

| holdout | probes | seq Pearson | multi Pearson | seq high-recall AUC | multi high-recall AUC | seq final high recall | multi final high recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full-stack command lifecycle | 17 | 0.0359 | **0.3473** | **0.0538** | 0.0387 | **0.1250** | 0.0840 |
| protocol catalog consistency | 18 | -0.1639 | **0.0947** | 0.0453 | 0.0453 | 0.0858 | 0.0858 |
| reconnect lifecycle | 30 | 0.4577 | **0.5115** | **0.0597** | 0.0410 | **0.1307** | 0.0958 |

Across the three holdouts:

- multi-scale wins Pearson on **3/3**;
- multi-scale wins MAE on **2/3**;
- multi-scale wins high-recall AUC on **0/3**;
- multi-scale wins final high-line recall on **0/3**;
- multi-scale wins weighted-relevance AUC on only **1/3**.

Overall means:

| metric | sequential | multi-scale | multi-scale change |
| --- | ---: | ---: | ---: |
| Pearson | 0.1099 | **0.3178** | +0.2079 |
| MAE | 0.2189 | **0.2086** | -4.7% |
| final high-line recall | **0.1138** | 0.0885 | -22.2% |
| high-recall AUC / probe | **0.0529** | 0.0417 | -21.3% |
| weighted-relevance AUC / probe | **0.0470** | 0.0444 | -5.7% |
| useful-probe rate | **0.6680** | 0.5690 | -14.8% |
| mean input tokens | **85,702** | 92,235 | +7.6% |

So the R07/R08-B result remains true in a narrow sense:

> the multi-scale posterior can reconstruct the relevance field better.

But Phase C rejects the stronger assumption:

> a better reconstructed relevance field automatically produces a better
> sparse-search policy.

It does not on these holdouts.

## Repeat stability

The strongest negative result is `reconnect_lifecycle`.

Repeat 1:

- sequential high-recall AUC: 0.0581
- multi-scale high-recall AUC: 0.0456
- sequential final high recall: 0.1333
- multi-scale final high recall: 0.1000

Repeat 2:

- sequential high-recall AUC: 0.0614
- multi-scale high-recall AUC: 0.0364
- sequential final high recall: 0.1281
- multi-scale final high recall: 0.0917

The degradation therefore survives a second model run.

`full_stack_command_lifecycle` is noisier. Multi-scale is much worse in
repeat 1 and close to sequential in repeat 2, but the two-repeat aggregate
still favors sequential search recall while strongly favoring multi-scale
field correlation.

`protocol_catalog_consistency` is a deliberately retained degenerate
holdout: its full-read reference marks essentially the whole file as
high/core. Search recall therefore reduces almost exactly to source coverage.
It is useful as a sanity case but carries little discrimination for active
search.

## Trajectory divergence

The two estimators do not reach these results through the same probes.

Mean exact-range Jaccard by holdout:

- reconnect lifecycle: about 0.081
- protocol catalog consistency: about 0.143
- full-stack command lifecycle: about 0.261

The reconnect case is especially important: the posterior changes the policy
very strongly, and that changed policy is consistently worse at finding the
reference high-relevance regions.

## Mechanism: uncertainty collapse

The key diagnostic is not relevance interpolation. It is the meaning of
`uncertainty`.

At the final budget, only about **8.52%** of source lines have actually been
observed.

Across all six paired runs:

| uncertainty diagnostic | sequential | multi-scale |
| --- | ---: | ---: |
| mean uncertainty on unobserved lines after 4 probes | 0.862 | **0.368** |
| mean uncertainty on unobserved lines at final budget | 0.484 | **0.086** |
| mean uncertainty on observed lines at final budget | 0.192 | 0.081 |
| unobserved / observed uncertainty ratio | 2.53x | **1.05x** |

The multi-scale estimator therefore becomes globally confident very quickly.

This follows directly from the current estimator:

1. adaptive Gaussian bandwidth grows in sparse regions;
2. distant observations therefore contribute broad support;
3. uncertainty is computed from that support;
4. support is interpreted as confidence even when the source line itself has
   never been observed.

That uncertainty is useful as a **posterior interpolation confidence** signal,
but it is not a valid **search epistemic uncertainty / novelty** signal.

The current runtime uses the same field for both purposes:

```text
posterior support
    -> frontier.uncertainty
    -> uncertainty candidate generation
    -> Choice state
    -> next probes
```

By the end of the holdout runs, multi-scale assigns almost the same low
uncertainty to observed and unobserved source. The action generator therefore
loses the strongest indication of "where have I not actually looked yet?"

Sequential exponential reconstruction is a worse global field estimator, but
its conservative local decay accidentally preserves a much healthier
exploration signal. That explains why it can search better while correlating
worse with the final full-read field.

## Architectural conclusion

The frontier needs at least two distinct state variables:

```text
relevance_posterior(x)
    what relevance do current observations imply here?

epistemic_uncertainty(x)
    how little direct evidence do we have here?
```

They must not be derived from the same kernel-support number.

A future acquisition policy can consume both:

```text
state
  relevance_posterior
  epistemic_uncertainty / novelty
  observed_mask
  gradients / peaks
      |
      v
candidate generation + Choice
```

The multi-scale estimator can remain a candidate for
`relevance_posterior`; this experiment does **not** justify discarding it.
What fails is using its support-derived uncertainty as the exploration field.

## Next research iteration

Do not tune this on the same three holdouts.

Start a new R09 split and test the architectural separation:

1. freeze multi-scale relevance reconstruction;
2. derive epistemic uncertainty independently from observation geometry,
   for example nearest-observation distance / coverage novelty;
3. keep the same action quotas and Choice semantics initially;
4. compare:
   - sequential relevance + sequential uncertainty baseline;
   - multi-scale relevance + current support uncertainty;
   - multi-scale relevance + conservative epistemic uncertainty;
5. evaluate field fit and search-effect metrics separately again.

The success condition should require both:

- reconstruction quality does not materially regress;
- high-recall / weighted-recall AUC improves on the new holdout split.

This is now the primary hypothesis after R08 Phase C.
