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
