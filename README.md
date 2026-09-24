# System One Code Explorer

A research runtime for using **System One models as fast policies over progressively disclosed code-exploration state and action spaces**.

This repository continues the code-localization research originally developed in `BestNathan/narness-engineering`. The implementation is intentionally experimental; the durable artifact is the research path captured under `docs/research/`.

## Core idea

System One is not treated as a small ReAct agent. The harness owns state, legal actions, effects, budgets, traces, and lifecycle. The model performs fast local decisions inside that bounded state machine.

```text
State
  ↓
Harness builds a bounded ActionSpace
  ↓
System One policy / utility decisions
  ↓
Effect → Observation → State transition
  ↺
```

## Current research architecture

The active line of research is no longer the original head/middle/tail range runtime. Phase0 now treats code exploration as sparse sensing plus whole-file posterior reconstruction:

```text
durable sparse observations
        ↓
PosteriorEstimator
        ├── relevance[N]
        └── uncertainty[N]
        ↓
System One Choice over diverse legal probes
        ↓
new observations
        ↓
posterior recompute
```

Key properties:

- sparse micro-probes rather than coarse full-region reads;
- a file-length relevance and uncertainty frontier;
- Choice probabilities consumed as a policy distribution, including multi-probe batches;
- posterior reconstruction is replaceable and recomputable from durable observations;
- reference evaluation uses a fixed full-read System 2 relevance field rather than treating final overlap as ground truth.

## Current status

The canonical research log is `docs/research/README.md`. The current iteration is **R08 — Online Posterior Feedback and Holdout Generalization**.

R07 isolated posterior reconstruction from probe selection and showed that path-independent reconstruction preserved substantially more of the sparse local relevance signal than the historical sequential propagation baseline.

R08 then integrated the posterior into the online feedback loop. On the frozen websocket fixture, the multi-scale posterior improved the final frontier at the same 32 × 8-line read budget and materially changed the probe trajectory. The active phase is now holdout generalization with estimator parameters frozen before new references are inspected.

See:

- `docs/research/2026-09-24-r07-posterior-reconstruction.md`
- `docs/research/2026-09-24-r08-online-posterior-generalization.md`
- `docs/experiments/r08-online-posterior-ab-2026-09-24.md`

## Historical baseline

The earlier adaptive range runtime remains useful as a historical control and regression baseline. It established that a fast System One model can drive bounded code reads and terminate without a free-form ReAct loop, but later experiments showed that coarse region state and sequential frontier propagation lose too much information.

The old range-runtime benchmark and raw reports are intentionally retained under `docs/experiments/`; they should not be read as the current algorithm.

## Repository layout

- `src/system_one_probability_frontier.py` — online sparse-probe probability-frontier runtime.
- `src/posterior_reconstruction.py` — replaceable posterior estimators.
- `src/posterior_reconstruction_benchmark.py` — controlled estimator comparison.
- `src/posterior_synthetic_benchmark.py` — model-free estimator geometry sanity checks.
- `src/system_one_sparse_phase0.py` — retained sparse Phase0 predecessor.
- `src/system_one_relevance_frontier.py` — retained relevance-frontier predecessor.
- `src/system_one_range_runtime.py` — historical adaptive range baseline.
- `src/full_read_relevance_baseline.py` — full-read System 2 reference-field construction.
- `src/compare_to_full_read_baseline.py` — frontier/reference comparison.
- `tests/` — deterministic regression tests, including historical algorithm invariants.
- `fixtures/research/` — pinned research trajectories and references.
- `docs/research/` — canonical research history and decisions.
- `docs/experiments/` — raw experiment reports.
- `ROADMAP.md` — current and longer-term research milestones.

## Running offline tests

```bash
python3 -m unittest discover -s tests -v
```

## Research discipline

The long-term question is:

> How strong can a harness become when it progressively discloses state and legal actions, while a fast System One model only chooses how to advance the state machine?

During the research phase:

- implementation may change or be replaced entirely;
- rejected algorithms may remain as regression baselines;
- every meaningful iteration should preserve its question, controlled setup, evidence, result, rejected ideas, and next direction in `docs/research/`;
- raw workflow artifacts are not the durable source of truth; important evidence should be pinned in the repository when practical;
- holdout references must not be used to retune a frozen estimator during the same evaluation round.

See `docs/research/README.md`, `docs/research-summary.md`, and `ROADMAP.md`.

## Full-read System 2 reference baseline

`src/full_read_relevance_baseline.py` builds a canonical overlapping grid and prepares a prompt in which the reference model sees the complete target file before scoring every range. The resulting field is reference data, not ground truth.

`src/compare_to_full_read_baseline.py` projects a candidate frontier/localization result onto that field and reports distribution- and coverage-level metrics.

The intended evaluation stack is:

1. full-read System 2 reference field: what relevant content is visible with the complete file;
2. System One sparse exploration: how efficiently that field can be reconstructed;
3. blind downstream quality: whether selected evidence is useful for engineering work.

See `docs/experiments/full-read-claude-baseline-2026-09-24.md`.
