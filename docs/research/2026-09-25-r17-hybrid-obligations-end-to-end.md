# R17 — Hybrid Frontier Obligations End-to-End

## Status

Current research iteration.

## Question

R16 found that a narrow persistent multiscale secondary-peak obligation can
recover some high-value Phase0 modes missed by the R15 q75 geometry at small
candidate-span cost.

Does that geometric improvement survive the full R15 pipeline?

## Controlled variable

Only obligation generation changes.

### Baseline

R15:

```text
q75 connected components
  -> representative seed
  -> directional closure
  -> post-closure utility
```

### R17 candidate

```text
q75 connected components
  +
persistent multiscale secondary peak seeds
  -> representative seed
  -> SAME directional closure
  -> SAME post-closure utility
```

Everything after obligation generation is frozen.

## Hybrid geometry

- 32-line tiles;
- q75 primary connected components unchanged;
- multiscale prominence radii 0/1/2/4;
- relative prominence threshold 0.10;
- peak persistence at two or more scales, or global maximum;
- cluster distance two tiles;
- secondary mode ignored when its basin overlaps an existing q75 component;
- secondary peak must be >= file median relevance;
- secondary obligation is exactly one 32-line peak tile.

## Runtime frozen from R15

- directional closure only;
- expansion threshold 0.60;
- no scalar completeness gate;
- final utility only after directional closure;
- final utility threshold 0.65;
- max 12 tiles per anchor is safety-only;
- low-utility seed does not invalidate a primary obligation.

For a one-tile secondary obligation, a low-utility closed anchor exhausts that
secondary obligation.

## Dataset

Mechanism diagnosis uses the same two discriminative R08 holdouts as R15:

- reconnect lifecycle;
- full-stack command lifecycle;
- two repeats;
- sequential and multi-scale Phase0 arms.

The catalog control is not rerun end-to-end because R16 already established its
geometry behavior and it is reference-degenerate.

## Primary comparison

Compare R17 directly with the pinned R15 aggregate:

- satisfied/exhausted obligations;
- retained anchor count;
- materialized source fraction;
- retained source fraction;
- retained hidden CC relevance;
- retained high precision;
- retained high recall;
- retained relevance-mass recall;
- model calls/tokens;
- closure safety caps.

## Key case

Full-stack sequential repeat 1 is the most informative mechanism case.

R16 adds secondary obligation `801-832`, which overlaps hidden high-reference
command-lifecycle code but was absent from q75.

R17 asks whether:

```text
secondary peak
 -> anchor
 -> directional closure
 -> post-closure utility
 -> retained command evidence
```

actually occurs.

## Guardrail

R17 reuses diagnostic data already inspected in R15/R16. A positive result is a
mechanism result only. The hybrid geometry must later be frozen on fresh
files/goals before being promoted as a general default.


## Canonical result

Canonical workflow: `36082094094`.

All eight end-to-end runs succeeded.

### Aggregate versus R15

#### Sequential Phase0

| metric | R15 q75 | R17 hybrid |
| --- | ---: | ---: |
| obligations | 3.25 | 4.75 |
| retained anchors | 1.00 | 1.25 |
| materialized source | 36.8% | 44.8% |
| retained source | 6.4% | 8.1% |
| retained CC relevance | 0.434 | **0.618** |
| retained high precision | 0.50 | **0.60** |
| retained high recall | 19.2% | **19.8%** |
| retained relevance-mass recall | 13.8% | **15.0%** |
| hidden high regions without obligation | 2.50 | **2.25** |
| model calls | 61.0 | 67.0 |
| input tokens | 209k | 229k |

The hybrid improves final evidence quality on sequential fields, but the recall
gain is modest relative to the additional materialization/model cost.

#### Multi-scale Phase0

Final retained-evidence metrics are unchanged:

- retained source fraction: 14.36%;
- retained CC relevance: 0.7908;
- high precision: 0.75;
- high recall: 0.2542;
- relevance-mass recall: 0.1845.

The hybrid only increases work:

- obligations 2.00 -> 2.75;
- materialized source 27.1% -> 30.4%;
- model calls 41.75 -> 46.5;
- input tokens 175k -> 198k.

This is expected: multi-scale Phase0 already exposed the useful full-stack
command mode through q75.

### Mechanism success: full-stack sequential repeat 1

R15 retained no final evidence for this case.

R16 identified a persistent secondary peak at `801-832`, below q75 but above
the within-file median.

R17 makes that peak a one-tile obligation:

```text
801-832
  -> directional closure
  -> 769-928
  -> final utility = 0.66
  -> retained
```

The secondary obligation itself has hidden CC mean relevance 0.78.

The final retained region:

- 160 lines;
- hidden CC mean relevance 0.696;
- high-line recall 0.125.

This proves that the R16 geometry signal can survive the full R15 runtime and
become concrete final evidence.

### Boundary: full-stack sequential repeat 2

The hybrid does not recover the command core.

Its only added secondary peak is `1313-1344`, hidden CC mean 0.60, and it is
correctly rejected after closure.

No final evidence is retained.

The useful command-core region in this trajectory does not form a stable
relevance mode. This is a genuine Phase0 false-negative boundary:

> obligation geometry cannot recover a region that is absent from the
> relevance topology it receives.

### Cost / false-positive tradeoff

The hybrid also adds low-value secondary modes on reconnect.

For example, some secondary obligations have hidden CC relevance around 0.05
and are eventually exhausted. Post-closure utility prevents them from entering
final evidence, but they still consume source reads and System One calls.

Therefore R17 does not justify unconditionally replacing q75 with the hybrid.

## R17 conclusion

Carry forward:

- persistent multiscale secondary peaks are a valid source of narrow
  supplemental obligations;
- they can recover end-to-end evidence that q75 misses;
- post-closure utility successfully filters many false-positive secondary
  obligations.

Do not conclude:

- that every detected secondary peak should become an obligation;
- that the hybrid is already the default geometry;
- that geometry can solve genuine Phase0 false negatives.

The correct next step is fresh generalization:

1. freeze all R17 geometry/runtime parameters;
2. select new files/goals before generating hidden references;
3. compare R15 q75 and R17 hybrid end-to-end;
4. separately report benefit on sequential and multi-scale Phase0;
5. test whether the extra cost is justified by retained-evidence gains.

Pinned aggregate:

- `fixtures/research/r17-hybrid-obligations-aggregate.json`.
