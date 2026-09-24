# R08 Synthetic Posterior Sanity Check — 2026-09-24

## Purpose

The first R08 online A/B cannot run yet because the new repository's
`typesafe` environment does not currently expose `TYPESAFE_API_KEY`.

Rather than tune further on the websocket CC reference, this sanity check asks a
different question:

> Are the R07 path-independent estimators only good because the websocket
> reference happens to have one convenient shape?

This is **not** a replacement for real holdout code evaluation. It tests only
the spatial inductive bias of the estimators.

## Setup

Construct five known 1024-line relevance fields:

1. one broad smooth peak;
2. three separated peaks;
3. a hard plateau;
4. a narrow spike;
5. two separated step regions.

Use the same deterministic 32-position stratified geometry for every field.

Each 8-line probe receives the exact mean relevance of the synthetic truth at
that block. Therefore there is no model noise: this isolates reconstruction
behavior.

Implementation:

- `src/posterior_synthetic_benchmark.py`

## Final 32-sample results

| field | sequential Pearson | k2 Pearson | k3 Pearson | multi-scale Pearson |
| --- | ---: | ---: | ---: | ---: |
| single broad | 0.681 | **0.999** | 0.998 | 0.998 |
| multi peak | 0.098 | **0.989** | 0.979 | 0.982 |
| plateau | 0.600 | **0.957** | 0.952 | 0.954 |
| narrow spike | -0.025 | **0.880** | 0.809 | 0.850 |
| two steps | 0.080 | **0.916** | 0.904 | 0.908 |

MAE shows the same direction. For example:

- multi-peak: sequential `0.282`, k2 `0.059`;
- plateau: sequential `0.151`, k2 `0.070`;
- two steps: sequential `0.267`, k2 `0.088`.

## Interpretation

The sequential exponential posterior has a structural weakness beyond the
websocket fixture. Mutation order and repeated local decay do not reliably
reconstruct multi-peak or discontinuous spatial fields.

Geometry-adaptive reconstruction remains strong across smooth, discontinuous,
multi-modal, and narrow-peak synthetic shapes.

On these clean synthetic fields, `adaptive_gaussian_k2` is consistently the
strongest or near strongest candidate. This does **not** supersede the R07
multi-scale result, because real System One observations contain scoring noise
and non-spatial code semantics.

## Decision

The holdout plan remains unchanged:

- freeze the existing estimator definitions;
- do not tune k or bandwidth from this synthetic experiment;
- run online A/B once the new repository has TypeSafe credentials;
- then evaluate the frozen candidates on real holdout code/reference fields.

The synthetic result strengthens one architectural conclusion:

> posterior reconstruction must be a replaceable component; sequential
> mutation should remain a baseline, not the core state-transition primitive.
