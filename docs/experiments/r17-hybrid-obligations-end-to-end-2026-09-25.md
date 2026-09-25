# R17 Hybrid Frontier Obligations — 2026-09-25

## Pre-registration

Source Phase0/reference run: `36004833542`.

Eight runs:

- reconnect + full-stack;
- repeat 1/2;
- sequential + multi-scale posterior.

Only change from R15:

`q75_components -> q75_plus_multiscale_seed`.

Frozen downstream runtime:

- expansion threshold 0.60;
- final utility threshold 0.65;
- max anchor tiles 12;
- same System One model/provider;
- same directional closure prompt;
- same post-closure utility prompt.

Success is not defined as "more obligations". The candidate is useful only if
the added secondary obligations improve retained task evidence or recover
previously missed high-value regions without disproportionate false-positive
anchors and model cost.


## Canonical result

Workflow: `36082094094`.

The promoted R16 hybrid successfully rescued the pre-registered mechanism case:
full-stack/sequential/repeat1 produced secondary obligation `801-832`, closed
to `769-928`, scored final utility 0.66, and was retained. R15 had retained no
evidence for the same case.

Aggregate effects:

- sequential retained relevance and precision improve, with modest recall gain;
- multi-scale retained metrics remain unchanged;
- materialized source, model calls, and tokens increase in both arms;
- full-stack sequential repeat2 remains unrecovered because the true core is
  not a stable Phase0 relevance mode.

Conclusion: freeze R17; next test is fresh holdout generalization, not further
parameter tuning on these cases.

Pinned result:
`fixtures/research/r17-hybrid-obligations-aggregate.json`.
