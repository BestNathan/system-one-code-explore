# R09 — Decouple Relevance Posterior from Exploration Uncertainty

## Status

Current research iteration. Pre-registered after R08 Phase C and before
generating any R09 holdout reference.

## Why R09 exists

R08 produced two results that must be kept separate:

1. path-independent multi-scale Gaussian reconstruction can preserve relevance
   shape better than sequential mutation on some fixed trajectories;
2. the same estimator's support-derived `uncertainty` does not generalize as
   an online exploration signal.

On the discriminative R08 holdouts, multi-scale search recovered less
high-relevance source under the same read budget even when local scoring or
some field-fit metrics were competitive.

The structural failure was uncertainty collapse:

```text
sparse observation geometry
        |
        v
adaptive bandwidth grows
        |
        v
Gaussian support remains high
        |
        v
support uncertainty becomes low
        |
        v
search incorrectly believes unread space is known
```

Therefore R09 treats these as different state:

```text
relevance posterior
    !=
exploration uncertainty
```

## Hypothesis

Keep the R07/R08 multi-scale relevance reconstruction unchanged, but prevent
exploration uncertainty from becoming lower than direct observation geometry
allows.

For a source line, define `d` as distance to the nearest actually observed
source range:

```text
coverage_uncertainty(d)
  = 1 - 0.97 * exp(-d / 48)
```

This gives:

- uncertainty 0.03 inside an observed range;
- monotonically increasing uncertainty as distance from observations grows;
- uncertainty approaching 1.0 in distant unread space.

The scale `48` is not fitted from R08. It is inherited from the existing
historical `sequential_exponential(decay_lines=48)` baseline.

The guarded estimator is:

```text
relevance_guarded
  = relevance_multi_scale

uncertainty_guarded
  = max(
      uncertainty_multi_scale_support,
      coverage_uncertainty
    )
```

## Non-negotiable invariant

For the same durable observations:

> `guarded.relevance == multi_scale.relevance` element-for-element.

R09 is not another relevance-estimator tuning round. Only exploration
uncertainty semantics change.

## R08 diagnosis set

The three R08 holdouts may be used only to validate structural invariants:

- relevance remains unchanged;
- uncertainty no longer collapses in distant unread regions;
- uncertainty follows observation geometry rather than adaptive-kernel support.

They are **not** R09 generalization evidence and must not be used to choose the
coverage decay constant or other parameters.

## Fresh R09 validation set

Search effects will be evaluated on three files/tasks whose references have not
yet been generated.

### H4 — file read safety and chunking

File:

`crates/nession-agent/src/fs/ops.rs`

Task:

> Help me harden file.read: locate the code that enforces sandbox-safe path
> resolution, full-read versus chunked size limits, offset/limit semantics,
> MIME/binary handling, and has_more behavior.

### H5 — tmux lifecycle safety

File:

`crates/nession-agent/src/tmux/manager.rs`

Task:

> Help me make tmux session lifecycle cleanup safer: locate session
> create/list/kill behavior, socket isolation, inherited environment
> filtering/cleanup, command timeouts, and error handling.

### H6 — terminal attach/reconnect lifecycle

File:

`web/src/platform/terminal-runtime/controller/TerminalController.ts`

Task:

> Help me make terminal attach and reconnect lifecycle robust: locate
> attach/reparent logic, transport rewiring and callback cleanup, input-router
> lifecycle, resize handling, detach/dispose behavior, and reconnect state
> propagation.

These tasks were selected from source structure before any R09 full-read
reference was generated.

## Controlled online experiment

Primary A/B:

- `multi_scale_gaussian`;
- `multi_scale_gaussian_coverage_guard`.

Historical context arm:

- `sequential_exponential`.

Keep fixed across all arms:

- System One model and API;
- 8-line micro-probes;
- mixed random / uncertainty / gradient / peak action families;
- 16 candidate actions;
- Choice probability batching;
- max batch = 4;
- `respect_stop=false`;
- source-read budget normalized to about 8.5%:
  `max(8, min(32, round(line_count * 0.085 / 8)))`;
- two repeats per holdout.

## Primary metrics

The primary claim is about search, not only field reconstruction:

- high-relevance recall AUC per probe;
- weighted relevance-mass recall AUC per probe;
- fixed-budget final high-line recall;
- useful-probe rate;
- first high-relevance hit;
- uncertainty-probe high-hit rate.

Secondary diagnostics:

- Pearson / Spearman / MAE / JS of the reconstructed relevance field;
- mean uncertainty;
- correlation between uncertainty and distance to nearest observation;
- model calls and input tokens.

## Success criteria

The coverage guard is promising only if, on fresh holdouts:

1. guarded relevance remains the same estimator family by construction;
2. uncertainty no longer collapses in distant unread regions;
3. guarded search improves high-recall AUC on a majority of discriminative
   holdouts versus plain multi-scale;
4. the result is not driven only by a degenerate all-high reference;
5. cost remains within the same order of magnitude.

A single positive fixture is not enough.

## Guardrail

Do not tune `48`, the 0.03 observed floor, action quotas, Choice threshold, or
probe budget after inspecting R09 holdout references/results.

If those values need to change, close R09 and start a new iteration with a new
validation split.
