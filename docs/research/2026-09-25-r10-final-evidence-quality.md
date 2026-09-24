# R10 — Phase0 to Final Evidence Quality

## Status

Current parallel research iteration.

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
