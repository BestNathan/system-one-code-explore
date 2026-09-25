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
