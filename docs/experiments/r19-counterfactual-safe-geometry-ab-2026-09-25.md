# R19 Counterfactual-Safe Geometry A/B — 2026-09-25

## Pre-registration

Reuse all R18 reference and Phase0 artifacts from workflow `36082601509`.

For each fresh case / repeat / posterior estimator:

1. run q75 baseline first;
2. run q75 + persistent multiscale secondary seeds second;
3. share one semantic System One decision cache across both runs;
4. strip only volatile `anchor_id` and `obligation_id` from cache keys;
5. cache hits return the exact stored response;
6. logical policy usage remains the original request usage;
7. physical cache usage is reported separately.

Hard assertion:

> If the hybrid generates zero secondary obligations, final materialized and
> retained evidence must be identical to baseline.

No algorithm parameter changes from R18.
