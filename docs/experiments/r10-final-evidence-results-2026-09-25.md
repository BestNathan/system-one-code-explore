# R10 Final Evidence Quality Results — 2026-09-25

## Status

Completed for the first fixed evidence policy.

Canonical workflow run: `36026211113`.

R10 did not rerun Phase0. It consumed the canonical R08 trajectories from run
`36004833542` and converted the highest-scored observed probes into at most six
non-overlapping 32-line snippets.

## Aggregate result

Across 3 tasks × 2 repeats:

| metric | sequential | multi-scale |
| --- | ---: | ---: |
| mean CC reference relevance | **0.6825** | 0.6441 |
| high-line precision | **0.6658** | 0.5946 |
| high-line recall | **0.1289** | 0.1086 |
| weighted relevance recall | **0.1122** | 0.1054 |
| mean relevance / oracle | **74.1%** | 70.0% |
| high-recall / oracle | **66.6%** | 59.5% |

The catalog task is reference-degenerate because essentially the whole file is
high/core. Excluding that case, the two discriminative holdouts show:

| metric | sequential | multi-scale |
| --- | ---: | ---: |
| mean CC reference relevance | **0.6237** | 0.5544 |
| high-line precision | **0.4987** | 0.3919 |
| high-line recall | **0.1362** | 0.1057 |
| weighted relevance recall | **0.1115** | 0.0998 |

So the simple final-evidence policy substantially concentrates useful code
relative to uniform source coverage, but still leaves a large amount of
medium/irrelevant material.

## Concrete evidence examples

For the reconnect task, multi-scale repeat 1 selected a particularly strong
snippet around lines 138–169. It contains:

- the `ServerClientHandle`;
- the queued `outbox`;
- the `sync_needed` atomic;
- the `connected` atomic;
- the comments documenting reconnect/resync behavior;
- `mark_sync_needed` / `take_sync_needed`.

Its 32-line CC reference mean is about **0.90**, with all 32 lines classified
high relevance.

The same final bundle also contains supporting reconnect tests around
1661–1692 and the `ServerClient` reconnect lifecycle documentation around
76–107.

But the same run also selects two clear false positives:

- around 1851–1882, CC reference mean ≈ **0.056**;
- around 2266–2297, CC reference mean ≈ **0.189**.

So the actual product is already recognizable as useful code evidence, not
random snippets, but the top-score list still needs a stronger final evidence
filter.

Sequential repeat 1 is more concentrated: four of its six reconnect snippets
have CC mean around **0.89–0.90**, while two are clear lower-value selections.

## Interpretation

The important distinction is:

```text
raw sparse search coverage
       ↓
actual observed micro-blocks
       ↓
top-score + local-context evidence
       ↓
much denser downstream evidence
```

Phase0 does not need to recover every high-relevance line to be useful. A small
number of correctly placed probes can seed excellent 32-line evidence windows.

However, current final evidence quality is not yet good enough to treat the
highest Phase0 scores as the final answer without another selection/closure
stage.

R10 therefore suggests two independent improvements:

1. R09 should improve where Phase0 explores;
2. a later evidence stage should remove false-positive / redundant snippets and
   optionally expand/follow genuinely strong snippets.

The next downstream benchmark should feed only the selected snippet bundle to a
fixed System 2 solver and compare the resulting answer/edit with a full-file
solver.
