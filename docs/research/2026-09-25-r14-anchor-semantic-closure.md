# R14 — Anchor-Centered Semantic Closure

## Status

Current follow-up to R13.

## Why R14 exists

R13 separated frontier coverage, task utility, and semantic completeness, but
its first discriminative runs exposed a new failure mode:

- adjacent acquired tiles were merged before completeness was judged;
- the merged region could contain several unrelated functions/tests/branches;
- System One then kept reporting low completeness;
- closure repeatedly expanded one side, producing 700–1000+ line regions.

Representative R13 examples:

- reconnect/sequential expanded one merged region to lines 1–1024 while final
  completeness stayed around 0.16;
- full-stack/multi expanded a merged region to 385–1120 while completeness
  stayed around 0.28.

The completeness question was therefore attached to the wrong object.

## Core idea

Every initially materialized high-value tile becomes an independent semantic
anchor.

Completeness is judged relative to the local semantic unit originally revealed
by that anchor, not relative to a merged evidence region.

An anchor may expand immediately before or after itself, but only to close the
same local construct.

Examples:

- complete the function body whose signature the anchor revealed;
- complete the if/else branch whose condition/body was truncated;
- complete the match arm/state transition/error path;
- include locally necessary setup or follow-up.

It must not expand merely because another related function exists nearby.

## Runtime

```text
Phase0 frontier
      |
      v
representative acquisition
      |
      +--> tile A -> anchor A
      +--> tile B -> anchor B
      +--> tile C -> anchor C
                    ...
each anchor independently:
      |
      v
utility(anchor)
completeness(anchor)
need_before(anchor)
need_after(anchor)
      |
      +--> complete -> stop anchor
      |
      +--> low utility -> stop anchor
      |
      +--> incomplete -> expand only this anchor
                          |
                          v
                       reassess
      |
      v
final output only:
merge overlapping/adjacent completed anchor ranges
```

## Representative frontier coverage

R13 also showed that asking whether a tile is simply a high-value frontier
region can over-read a broad high plateau. The degenerate catalog case
materialized the whole file.

R14 changes the coverage question to:

> Is this a DISTINCT unresolved high-value frontier region that still needs
> representative source coverage?

A tile should score lower when nearby already-materialized tiles adequately
represent the same smooth frontier plateau.

This is spatial redundancy, not answer sufficiency.

## Independence of objectives

R14 keeps these concepts separate:

1. representative frontier coverage;
2. intrinsic task utility;
3. anchor-local semantic completeness.

Finding enough evidence for an answer must not automatically suppress coverage.
Likewise high relevance must not imply semantic completeness.

## Initial frozen parameters

- global tile width: 32 lines;
- representative coverage threshold: 0.65;
- task utility threshold: 0.65;
- anchor completeness threshold: 0.70;
- before/after expansion threshold: 0.60;
- max 12 tiles per anchor is safety-only;
- max 10 global rounds is safety-only.

## Evaluation

Primary evidence metrics remain:

- mean hidden CC relevance;
- high-line precision/recall;
- relevance-mass recall;
- Phase0 high-frontier coverage.

Anchor-specific diagnostics:

- anchor count;
- complete / low-utility / unresolved-incomplete anchors;
- closure expansion tiles;
- mean and max anchor span;
- anchor growth ratio relative to the 32-line seed;
- final System One completeness;
- closure safety-cap rate.

The most important R14 criterion is:

> semantic closure should increase local completeness without creating giant
> runaway regions.

A later hidden System2 audit is still required before treating System One's
self-reported completeness as ground truth.


## Canonical diagnostic result

Canonical workflow: `36041935061`.

R14 was intentionally evaluated only on the two discriminative holdouts
(reconnect and full-stack), excluding the known degenerate catalog case.

Anchor-centered closure substantially reduced runaway expansion:

| metric | sequential | multi-scale |
| --- | ---: | ---: |
| source fraction | 8.8% | 2.5% |
| high-line precision | 0.671 | 0.500 |
| high-line recall | 0.230 | 0.075 |
| mean anchor span | 37 lines | 33 lines |
| max anchor span | 80 lines | 56 lines |
| mean anchor growth | 1.16x | 1.04x |

So binding closure to anchors fixed the giant-region pathology.

However it overcorrected. Hidden-reference premature-stop rate returned to
100%. Representative cases show two new issues.

### Standalone completeness is internally inconsistent

For reconnect/sequential, one anchor expanded from a 32-line seed to six tiles.
Directional expansion probability eventually fell below threshold:

- need-before about 0.43;
- need-after about 0.31.

Yet the standalone completeness score remained only about 0.58.

This means "is the fragment complete?" is less operationally reliable than the
two directional questions "do I still need source before/after?".

### Utility must not gate closure before the fragment is complete

In full-stack/sequential, selected source averaged hidden CC relevance about
0.84, yet post-read System One utility fell below 0.65 and anchors were marked
low-utility before closure could finish.

A truncated fragment can look low-utility precisely because the code needed to
understand it is outside the current range. Therefore utility before closure is
not a safe stopping gate.

### R14 conclusion

R14 establishes two stronger design rules:

1. semantic closure must be anchor-local;
2. closure should be driven by directional continuation needs, not a separate
   scalar completeness score.

The next runtime should also move coverage out of model discretion: high-value
Phase0 frontier regions should create explicit coverage obligations, while
System One decides representative source and local closure.

Pinned aggregate:
`fixtures/research/r14-anchor-semantic-closure-aggregate.json`.
