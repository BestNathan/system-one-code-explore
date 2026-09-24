# Research Summary

## Current result

The project has moved beyond the original adaptive range locator into a sparse-observation probability-frontier runtime.

The current architecture keeps durable micro-probe observations, reconstructs a file-length relevance/uncertainty posterior from those observations, and lets System One Choice select among a bounded set of legal probes. Posterior reconstruction is now a first-class replaceable component rather than an implicit sequence of local mutations.

## What R07 established

R07 held the websocket observations and probe order fixed and changed only the posterior estimator. The historical sequential posterior lost a large part of the local relevance signal; a path-independent multi-scale Gaussian reconstruction recovered substantially more of it without additional source reads or model calls.

The important conclusion is architectural: **posterior reconstruction, not local System One scoring, was the dominant information-loss layer on that controlled fixture**.

See `docs/research/2026-09-24-r07-posterior-reconstruction.md`.

## What R08 established

R08 integrated the posterior into the online feedback loop, so the reconstructed frontier can change which probes System One selects next.

On the same frozen websocket task and the same 32 × 8-line source-read budget, the multi-scale arm improved the final reference-field metrics over the sequential arm and produced a substantially different probe trajectory. This shows that the posterior affects exploration policy, not only the final visualization.

The project is now in **R08 Phase C: holdout generalization**. Estimator parameters are frozen before fresh files/tasks and full-read references are evaluated.

See `docs/research/2026-09-24-r08-online-posterior-generalization.md`.

## Historical baseline

The earlier range runtime remains a useful historical control. It established that System One can act as a fast policy over bounded reads and terminate without a free-form ReAct loop. Later frontier experiments superseded its state representation as the active Phase0 design.

The older latency/quality benchmark, Stop reconciliation work, and blind evaluation remain valid historical evidence; they are not the current algorithm.

## Research thesis

> System One models are most useful as fast policies inside a harness that owns state, legal actions, effects, progressive disclosure, and durable observations.

The current question is narrower and testable: can a frozen sparse-observation posterior generalize across different code files and relevance shapes without using holdout references for tuning?

Canonical history: `docs/research/README.md`.
