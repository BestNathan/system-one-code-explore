# R02 — Adaptive Relevance Frontier

## Question

Can a coarse-to-fine relevance frontier guide code reads more efficiently than
the original range runtime?

## Hypothesis

A tree of source intervals with relevance scores can progressively refine areas
that look useful while avoiding low-value regions.

## Design

The relevance-frontier experiments introduced:

- coarse interval leaves;
- relevance-potential scores;
- refine-high actions;
- missing-frontier exploration;
- gradient resolution;
- volatility revisits;
- stochastic revisits.

The harness controlled interval geometry; System One scored or selected legal
actions.

Raw reports:

- `docs/experiments/range-vs-adaptive-zoom-2026-09-24.md`
- `docs/experiments/relevance-frontier-v1-2026-09-24.md`

## Result

The frontier representation made exploration behavior explicit and measurable,
but exposed two problems:

1. action budgets could starve unobserved coarse regions;
2. a region-level score mixed together relevance, uncertainty, and coverage.

The experiments also showed that token cost was increasingly dominated by
retransmitting state rather than by model-call count alone.

## Rejected idea

A small set of coarse region scores is **not** an adequate Phase0 product.

Region trees may remain useful internally for action generation, but they
should not define the semantic state that Phase0 is trying to reconstruct.

## Next direction

Separate broad sensing from focused refinement, and establish an independent
full-read reference field for evaluating the entire relevance landscape.
