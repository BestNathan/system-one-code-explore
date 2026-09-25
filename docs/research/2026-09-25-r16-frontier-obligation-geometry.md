# R16 — Frontier Obligation Geometry

## Status

Current research iteration.

## Question

R15 made coverage obligations durable Harness state and separated them from
directional semantic closure. The remaining failure is geometric:

> How should a Phase0 relevance field be converted into a small set of
> coverage obligations that preserves independent high-value modes without
> degenerating into whole-file coverage?

R15 used connected components of the top 25% tile relevance. That rule is
simple and deterministic, but it misses secondary modes below the global q75
threshold.

R16 isolates this variable. It does not rerun Phase0 and does not call System
One. Every candidate geometry sees exactly the same frozen Phase0 fields.

## Frozen inputs

Canonical source run:

- R08 Phase0/reference workflow: `36004833542`;
- subject revision:
  `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`;
- three existing holdouts;
- two repeats;
- sequential and multi-scale posterior fields.

The three cases include the known catalog-degenerate control because geometry
must explicitly show how it behaves on a broad flat relevance plateau.

## Tile representation

The file is partitioned into the same non-overlapping 32-line tiles used by
R15.

Each geometry receives only Phase0 tile mean relevance. Hidden CC relevance is
used only after obligations have been generated.

## Candidate geometries

### A. q75 connected components — R15 baseline

- compute within-file q75 tile relevance;
- keep every tile at or above q75;
- merge contiguous kept tiles.

This is the exact R15 obligation geometry.

### B. q60 connected components — sensitivity control

Same algorithm with q60.

This is not proposed as the final solution. It measures the cost of fixing
missed modes by simply lowering the global relevance threshold.

Expected behavior:

- higher hidden recall;
- much larger source coverage;
- more degeneration on flat/broad fields.

### C. local prominence basins

Treat the one-dimensional tile relevance vector as a signal.

1. find local maxima, collapsing flat peak plateaus;
2. compute one-dimensional peak prominence relative to surrounding valleys;
3. retain peaks whose prominence is at least 10% of the file's relevance
   dynamic range;
4. always retain the global maximum;
5. form an obligation basin around each retained peak down to half-prominence;
6. merge overlapping basins.

Prominence asks whether a location is a distinct mode relative to its local
surroundings, not whether it exceeds a global relevance threshold.

This should preserve a secondary local mode such as a 0.45 peak even when q75
is 0.49, provided the surrounding valley is materially lower.

For a nearly flat field where the dynamic range is negligible, emit one broad
plateau obligation instead of one obligation per tile.

### D. multi-scale persistent prominence

Repeat prominence detection after deterministic box smoothing at tile radii:

- 0;
- 1;
- 2;
- 4.

Peak candidates from different scales are clustered when their centers are
within two tiles.

Keep clusters that:

- appear at two or more scales; or
- contain the global maximum.

The obligation range is the union of the candidate basins in that persistent
cluster. Overlapping final ranges are merged.

This tests whether broad but real modes are easier to recover from a smoothed
field than from raw local maxima.

### E. relevance-mass + spatial-diversity coverage

This is a non-peak control.

1. subtract the file minimum from each tile score to obtain nonnegative
   relevance mass;
2. repeatedly choose the highest remaining mass tile;
3. selecting a tile represents mass within +/-2 tiles;
4. continue until at least 70% of positive relevance mass is represented or a
   deterministic cap of `ceil(log2(tile_count + 1))` representatives is hit;
5. each representative produces a five-tile-or-smaller local obligation.

This tests whether a simple mass/diversity strategy covers useful secondary
regions without reasoning about prominence.

## Hidden evaluation

Geometry is evaluated before any R15 closure or final-utility model call.

Primary metrics:

- **CC high-region recall**: fraction of contiguous hidden CC >=0.70 regions
  overlapped by at least one obligation;
- **CC high-line coverage**: fraction of hidden high lines covered by obligation
  ranges;
- **obligation precision**: fraction of obligations that overlap any hidden high
  line;
- **source coverage**: fraction of file lines inside obligation ranges;
- **mean hidden relevance** inside obligation ranges;
- obligation count.

A good geometry must improve hidden-region recall without buying the result by
covering most of the file.

## Interpretation guardrail

This is mechanism diagnosis on existing R08/R15 data.

CC labels must not be used to choose or tune geometry parameters after the
results are visible. Any promoted geometry must be frozen and validated on new
files/goals before a generalization claim.

## Promotion criterion

R16 should not select a single winner from one scalar score.

A geometry is a candidate for R17 end-to-end use if it lies on a useful Pareto
frontier:

- materially better high-region recall than q75;
- without q60-like source-coverage inflation;
- stable across sequential and multi-scale Phase0 fields;
- sane behavior on the flat catalog control.


## Phase A result

Canonical workflow: `36081359100`.

Overall geometry-only results across 12 frozen Phase0 fields:

| method | obligations | candidate source span | hidden high-region recall | high-line coverage | obligation precision | hidden relevance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| q75 components | 2.67 | **26.2%** | 62.2% | 39.5% | 83.1% | **0.736** |
| q60 components | 3.50 | 41.9% | 75.6% | 53.1% | 79.2% | 0.680 |
| local prominence | 3.67 | 50.6% | **83.3%** | 58.7% | 76.8% | 0.648 |
| multi-scale prominence | 2.83 | 57.1% | **83.3%** | **63.6%** | 82.8% | 0.644 |
| mass diverse | **2.25** | 41.0% | 69.4% | 53.4% | **83.8%** | 0.726 |

The important estimator-specific result is on sequential Phase0:

- q75 high-region recall: 57.8%;
- local prominence: 85.6%;
- multi-scale prominence: 85.6%.

So local prominence does recover secondary modes that q75 misses.

However converting the complete half-prominence basin directly into an
obligation range is too broad. Local prominence candidate span rises to ~50%
of the file and multi-scale to ~59% on sequential fields.

This does **not** mean R15 would necessarily read half the file: obligations
are candidate domains, and R15 materializes representative seeds. But broad
candidate domains cause expensive exhaustion when an obligation is a false
positive.

The useful signal from Phase A is therefore peak discovery, not basin width.

## Phase B pre-registration

Phase B separates **mode detection** from **candidate width**.

Two hybrid geometries are added:

### q75 + local-prominence seed

1. keep the original q75 connected components unchanged;
2. detect local-prominence candidates with the already frozen 10% relative
   prominence rule;
3. ignore a prominence candidate whose basin overlaps an existing q75
   component, because q75 already represents that mode;
4. require a secondary peak to be at or above the file median tile relevance;
5. for each remaining secondary mode, add exactly the peak's 32-line tile as a
   new obligation candidate.

### q75 + multi-scale-prominence seed

Same rule, but secondary candidates come from persistent multi-scale peak
clusters.

The median guard is a Phase0-only robust-height floor. It prevents an isolated
local maximum in the bottom half of the file relevance distribution from
becoming an obligation solely because its surrounding valley is even lower.

Phase B remains mechanism diagnosis on the same data and is not a fresh
generalization test.

Primary question:

> Can prominence add the secondary modes missed by q75 while preserving the
> narrow source/candidate footprint and precision of the q75 baseline?
