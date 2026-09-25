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
