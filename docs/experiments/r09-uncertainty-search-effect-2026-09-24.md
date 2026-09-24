# R09 Uncertainty-Guard Search Experiment — 2026-09-24

## Status

Pre-registered before any R09 holdout reference is generated.

## Question

Does separating exploration uncertainty from adaptive relevance-kernel support
improve sparse code search under the same read budget?

## Arms

- historical context: `sequential_exponential`;
- current R08 design: `multi_scale_gaussian`;
- R09 treatment: `multi_scale_gaussian_coverage_guard`.

The R09 treatment changes uncertainty only. For identical observations its
relevance vector must be exactly equal to the current multi-scale estimator.

## Fresh holdouts

| ID | File | Search task |
| --- | --- | --- |
| fs_read_safety | `crates/nession-agent/src/fs/ops.rs` | sandbox-safe file.read, chunking limits, offset/limit, MIME/binary, has_more |
| tmux_lifecycle_safety | `crates/nession-agent/src/tmux/manager.rs` | create/list/kill, socket isolation, env cleanup, timeouts/errors |
| terminal_attach_lifecycle | `web/src/platform/terminal-runtime/controller/TerminalController.ts` | attach/reparent, transport rewiring/cleanup, input lifecycle, resize, detach/dispose/reconnect |

No full-read reference for these cases has been generated at pre-registration
time.

## Frozen policy

- subject: `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`;
- sample width: 8 lines;
- source budget: `max(8, min(32, round(line_count * 0.085 / 8)))`;
- candidate actions: 16;
- max Choice batch: 4;
- default Choice threshold;
- `respect_stop=false`;
- two repeats per holdout;
- same System One model for every arm.

## Frozen uncertainty guard

```text
coverage_u(d) = 1 - 0.97 * exp(-d / 48)

guarded_u = max(multi_scale_support_u, coverage_u)
```

Distance is measured to the nearest actually observed source range.

The 48-line scale comes from the pre-existing sequential baseline and is not
fitted to R08.

## Evaluation

Use the same probe-order search metrics introduced in R08:

- first high/core hit;
- high-line recall AUC/probe;
- weighted relevance recall AUC/probe;
- final high-line recall;
- useful-probe rate;
- probe truth relevance;
- trajectory divergence;
- field-fit metrics and token cost.

Primary comparison is guarded vs plain multi-scale. Sequential is contextual.

## Interpretation

R08 files are diagnosis-only. R09 search claims must come from these fresh
holdouts. No holdout may be replaced after its reference is seen merely because
its relevance geometry is inconvenient; any degenerate case must remain
reported explicitly.
