# Research Log

This directory is the canonical research history for **System One Code Explorer**.

The repository is intentionally in a research phase. Implementation is expected
to change quickly and may be replaced entirely. The durable artifact is the
research path: what problem was studied, what hypothesis was tested, what the
experiment showed, what was rejected, and what should be tested next.

## Working rule

Every meaningful research iteration should leave a record here before or with
the implementation change.

Each record should answer:

1. **Question** — what are we trying to learn?
2. **Hypothesis** — what do we believe before the experiment?
3. **Design** — what state/action/model/runtime design is being tested?
4. **Controlled setup** — what is held fixed?
5. **Evidence** — what data or traces were collected?
6. **Result** — what happened?
7. **Interpretation** — what does the result mean?
8. **Rejected ideas** — what should we stop carrying forward?
9. **Next direction** — what variable should be isolated next?

Raw benchmark details may live under `docs/experiments/`, but every experiment
that changes our understanding should be linked from a research record.

## Research path

| ID | Research | Status | Main conclusion |
| --- | --- | --- | --- |
| R01 | [Range runtime baseline](2026-09-24-r01-range-runtime-baseline.md) | historical | System One can drive bounded code reads, but geometry and evidence shaping dominate quality. |
| R02 | [Adaptive relevance frontier](2026-09-24-r02-adaptive-relevance-frontier.md) | superseded | Coarse-to-fine frontier search is useful as an experiment, but region scores are the wrong Phase0 state abstraction. |
| R03 | [Full-read System 2 reference field](2026-09-24-r03-full-read-system2-reference.md) | active benchmark | A fixed CC full-read relevance field gives us a distribution-level target instead of only final evidence overlap. |
| R04 | [Choice policy and evidence closure](2026-09-24-r04-choice-and-evidence-closure.md) | retained partially | Choice is appropriate for policy selection; isolated fine-fragment keep/drop is not. |
| R05 | [Sparse Phase0 sensing](2026-09-24-r05-sparse-phase0.md) | superseded | Sparse reads are correct, but collapsing them into four coarse region scores destroys the global relevance shape. |
| R06 | [Whole-file probability frontier](2026-09-24-r06-whole-file-probability-frontier.md) | baseline | Phase0 should reconstruct a file-length relevance distribution from sparse observations. |
| R07 | [Posterior reconstruction](2026-09-24-r07-posterior-reconstruction.md) | completed | Path-independent posterior reconstruction recovers much more of the local System One signal than sequential propagation. |
| R08 | [Online posterior feedback and holdout generalization](2026-09-24-r08-online-posterior-generalization.md) | completed | Single-fixture relevance gains did not generalize to search; support-derived uncertainty collapsed in sparse unread regions and degraded probe selection. |
| R09 | [Uncertainty calibration and search policy](2026-09-24-r09-uncertainty-calibration-search-policy.md) | current | Keep multi-scale relevance fixed, decouple exploration uncertainty from adaptive-kernel support, and validate search on fresh holdouts. |
| R10 | [Phase0 to final evidence quality](2026-09-25-r10-final-evidence-quality.md) | completed baseline | Phase0 already yields concentrated concrete evidence, but the fixed top-score selector still retains meaningful false positives. |
| R11 | [System One relevance prompt calibration](2026-09-25-r11-system-one-prompt-calibration.md) | current parallel — Phase C | Hard negatives exposed 64-line→8-line label leakage; Phase C uses a full-read teacher to score exact micro-targets before comparing System One prompts. |

## Current research architecture

```text
durable sparse observations
        |
        v
PosteriorEstimator
        |
        +--> relevance[N]
        |
        +--> interpolation support
        |
ObservationGeometry
        |
        +--> coverage / exploration uncertainty[N]
        |
        v
System One Choice over diverse legal probes
        |
        v
new observations
        |
        +--------------------------+
                                   |
                                   v
                            posterior recompute

evaluation:
  every checkpoint -> fixed System 2 full-read relevance field
```

## Repository workflow

During the research phase:

- research changes may be committed directly to `main`;
- pull requests are not required for research iterations;
- unstable APIs and implementation churn are acceptable;
- `docs/research/` is the durable record of decisions and learning;
- benchmark fixtures that define a research conclusion should be copied into
  this repository when practical, rather than depend indefinitely on external
  workflow artifacts;
- external benchmark/reference provenance should still be pinned by repository,
  revision, workflow run, and model/runtime configuration.

| R16 | [Frontier obligation geometry](2026-09-25-r16-frontier-obligation-geometry.md) | completed diagnosis | Prominence recovers secondary modes, but wide basins are too broad; narrow persistent multiscale seeds are the promoted mechanism candidate. |
| R17 | [Hybrid obligations end-to-end](2026-09-25-r17-hybrid-obligations-end-to-end.md) | completed diagnosis | Narrow persistent secondary peaks can become retained evidence, especially on sequential Phase0, but add false-positive/cost overhead and need fresh validation. |
