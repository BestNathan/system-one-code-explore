# R10 — Phase0 to Final Evidence Quality

## Status

Completed for the first fixed evidence-selection policy.

## Question

R08/R09 measure search and posterior quality, but a coding agent ultimately consumes concrete source evidence. R10 asks:

> After Phase0 stops, what exact code snippets are handed to downstream reasoning/editing, and are they useful?

R10 freezes Phase0 and evaluates only the downstream evidence product.

## Hypothesis

The highest-scored sparse observations may still form a compact useful evidence set once local context is restored, even when raw high-line search recall is modest.

The opposite failure is also possible: the probability field can look useful while the actually observed top probes are fragmented, redundant, or incidental.

## Controlled setup

Reuse canonical R08 Phase C workflow run 36004833542:

- subject: BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df;
- three real single-file tasks;
- two repeats;
- sequential and multi-scale Phase0 trajectories.

No Phase0 model calls are rerun.

## Downstream evidence policy v0

For every completed trajectory:

1. rank actually observed 8-line probes by System One score;
2. reject final evidence windows that overlap an already selected window;
3. restore 32 lines of local source context around each selected probe;
4. keep at most six snippets / 192 source lines.

No new model is used in the selector. This isolates how much useful evidence is already present in Phase0 observations.

## Metrics

Against the corresponding full-read CC field:

- mean reference relevance of selected evidence;
- high-line precision;
- high-line recall;
- weighted relevance-mass recall;
- same-budget oracle upper bound;
- ratio to oracle precision and recall.

The artifact also contains the literal final source snippets for qualitative inspection.

## Interpretation

R10 is parallel to R09, not a replacement.

If final evidence is precise but low recall, the next stage should expand/follow good evidence. If precision is poor, Phase0 search/scoring is still the dominant problem. If both are strong, the next experiment should feed only these snippets into a downstream System 2 task and measure answer/edit quality directly.


## Result

Workflow run `36026211113` completed all 12 evidence jobs and the aggregate.

Across all cases, sequential final evidence had mean CC relevance 0.6825 and
66.6% high-line precision; multi-scale had 0.6441 and 59.5%.

The catalog case is reference-degenerate. On the two discriminative holdouts,
sequential selected evidence averaged 0.6237 CC relevance with 49.9% high-line
precision, versus 0.5544 / 39.2% for multi-scale.

The literal snippets confirm that Phase0 frequently lands on excellent concrete
evidence, including reconnect state flags and lifecycle tests, but also retains
clear false positives. Therefore a downstream evidence-selection/closure stage
remains useful even after Phase0 search improves.

See `docs/experiments/r10-final-evidence-results-2026-09-25.md`.


## Result

Completed in workflow run `36026211113`.

Across 12 evidence artifacts (3 tasks x 2 repeats x 2 Phase0 estimators), each final evidence set was limited to six non-overlapping 32-line snippets / 192 source lines.

Aggregate:

| metric | sequential | multi-scale |
| --- | ---: | ---: |
| mean CC relevance | **0.6825** | 0.6441 |
| high-line precision | **0.6658** | 0.5946 |
| high-line recall | **0.1289** | 0.1086 |
| weighted relevance recall | **0.1122** | 0.1054 |
| same-budget oracle precision ratio | **0.7408** | 0.6998 |
| same-budget oracle high-recall ratio | **0.6658** | 0.5946 |

The evidence is meaningfully enriched relative to raw source coverage, but still substantially below the same-budget oracle. The main qualitative failure is that several high System One probe scores expand into locally plausible but reference-low snippets, consuming one of only six final evidence slots.

The strongest reconnect example makes the gap concrete. Sequential retained four high-reference windows around the actual connection/registration loop before spending two slots on weak regions; multi-scale retained four useful windows but also spent two slots on clearly low-reference regions.

Conclusion:

> current Phase0 observations are good enough to form a useful compact evidence set, but evidence selection quality is still dominated by false-positive local scores and incomplete search coverage.

This supports a next downstream stage that can re-rank/expand evidence, but it does not justify treating top Phase0 probes as final evidence without another selection step.

Pinned aggregate: `fixtures/research/r10-final-evidence-quality-aggregate.json`.
