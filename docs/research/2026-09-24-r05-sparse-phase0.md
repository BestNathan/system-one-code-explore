# R05 — Sparse Phase0 Sensing

## Question

Can Phase0 avoid scanning large files while still building enough state for
later refinement?

## Hypothesis

Phase0 should read only tiny 5–10 line samples whose total budget is largely
independent of file length.

## Design

v4 replaced large coarse samples with 8-line micro-probes:

- a tiny bootstrap;
- geometry-only candidate positions;
- Choice-selected subsequent probes;
- a small fixed read budget.

Raw report:

- `docs/experiments/relevance-frontier-v4-sparse-phase0-2026-09-24.md`

A controlled run sampled only 64 lines from the 3030-line websocket file.

## Result

Sparse sensing itself was viable, but the representation was wrong.

The implementation still collapsed the file into four coarse region scores.
That meant a weak 8-line sample could incorrectly depress hundreds of unseen
lines.

This violated the actual Phase0 goal.

## Rejected idea

Do not let Phase0 output:

```text
region 1 -> score
region 2 -> score
region 3 -> score
region 4 -> score
```

The whole-file shape matters, and a few thousand probability values are cheap
enough to expose directly.

## Next direction

Make the Phase0 product a file-length relevance probability frontier with a
separate uncertainty frontier.
