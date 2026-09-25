# R16 Frontier Obligation Geometry — 2026-09-25

## Pre-registration

No new System One calls are made.

Frozen data:

- Phase0/reference workflow: `36004833542`;
- three existing R08 cases;
- two repeats;
- sequential and multi-scale fields;
- 32-line tiles.

Frozen geometry methods:

1. `q75_components`;
2. `q60_components`;
3. `local_prominence` with relative prominence >= 0.10 and half-prominence
   basins;
4. `multiscale_prominence` over smoothing radii 0/1/2/4, persistence >=2,
   peak clustering distance 2 tiles;
5. `mass_diverse` with +/-2-tile represented neighborhoods, 70% positive-mass
   target, and `ceil(log2(N+1))` representative cap.

Primary hidden metrics:

- high-region recall;
- high-line coverage;
- obligation precision;
- source coverage;
- mean hidden relevance;
- obligation count.

Parameters above are frozen before hidden-reference results are generated.


## Phase B pre-registration

After Phase A, basin span is no longer interpreted as the amount of source that
must be materialized. Phase B tests narrow hybrid obligations:

- keep q75 components;
- add only secondary prominence peaks not already represented by a q75 basin;
- secondary peak must be >= the file median tile relevance;
- added secondary obligation width is exactly one 32-line tile;
- compare local-prominence and multi-scale-persistent peak sources.

No hidden CC labels participate in hybrid generation.
