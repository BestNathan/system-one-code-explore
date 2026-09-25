# R18 Fresh Hybrid Holdout — 2026-09-25

## Pre-registration

Fresh frozen files/goals:

1. `crates/nession-agent/src/fs/sandbox.rs`
   - symlink delete/no-follow + non-existent path resolution;
2. `crates/nession-agent/src/tmux/manager.rs`
   - session environment isolation/create/kill cleanup lifecycle;
3. `crates/nession-protocol/src/kernel/manifest.rs`
   - manifest duplicate-id union/retired filtering/wire routing compatibility.

Two repeats, two Phase0 posterior estimators.

Every Phase0 trajectory is evaluated by both:

- `q75_components`;
- `q75_plus_multiscale_seed`.

All Phase0, geometry, closure, and utility parameters are frozen from
R08/R15/R17 before fresh references are generated.

Primary unit of evidence is the paired difference between the two geometry
arms on the exact same Phase0 trajectory.


## Canonical result

Workflow `36082601509` completed all 12 geometry pairs.

The naive paired aggregate showed small retained-evidence gains, but attribution
inspection invalidated them: both retained wins occurred where the hybrid added
zero secondary obligations and the two arms had identical geometry.

A representative identical-state closure call returned 0.59 in the baseline
and 0.60 in the hybrid at a 0.60 expansion threshold, producing a spurious
extra read.

The only fresh case with a real secondary obligation improved coverage but not
retained evidence and added cost.

R18 therefore becomes an experimental-design result:

> policy A/B must share System One decisions for identical semantic states.

Next: rerun these frozen fresh holdouts with a shared counterfactual decision
cache. No algorithm parameters change.

Pinned result:
`fixtures/research/r18-fresh-hybrid-generalization-aggregate.json`.
