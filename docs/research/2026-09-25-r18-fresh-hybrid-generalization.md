# R18 — Fresh Holdout Generalization for Hybrid Frontier Obligations

## Status

Fresh validation iteration.

## Question

R17 showed on previously inspected mechanism cases that narrow persistent
multiscale secondary peaks can recover a missed relevance mode and survive the
full evidence pipeline.

R18 asks whether that benefit generalizes to **new files and new goals** chosen
before any hidden full-read reference is generated.

## Frozen subject

`BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`

## Fresh holdouts

These files/goals were not used in R08, R11, R15, R16, or R17.

### 1. fs_symlink_delete_semantics

File:

`crates/nession-agent/src/fs/sandbox.rs`

Goal:

> I am reviewing file-operation path semantics around deleting symlinks and
> creating non-existent paths. Locate the code that decides when the final
> symlink component is followed versus preserved, how parent symlinks and
> non-existent ancestors are resolved, how duplicated root-name paths fall
> back, and the tests that prevent a delete from operating on a symlink target.

### 2. tmux_env_session_lifecycle

File:

`crates/nession-agent/src/tmux/manager.rs`

Goal:

> I want to harden tmux session creation and teardown. Locate the code that
> filters inherited TERM/LANG/LC_ALL/TMUX environment, applies caller
> overrides, creates sessions with fixed geometry and timeouts, and cleans up
> session environment scripts when a session is killed.

### 3. manifest_union_wire_routing

File:

`crates/nession-protocol/src/kernel/manifest.rs`

Goal:

> I need to verify protocol-manifest composition and routing semantics. Locate
> the code that omits retired units, unions duplicate protocol IDs across
> versions and wire types deterministically, keeps older manifests without wire
> projections safe, and resolves a wire message type back to the protocol unit
> that carries it.

## Frozen Phase0

Use the exact R08 online Phase0 protocol:

- 8-line probes;
- 8.5% target source coverage;
- minimum 8 / maximum 32 probes;
- max 16 candidate actions;
- max Choice batch 4;
- `respect_stop=false`;
- compare `sequential_exponential` and `multi_scale_gaussian`;
- two repeats per file.

No R18 result may change Phase0 parameters.

## Frozen evidence runtimes

Every completed Phase0 field is consumed twice.

### Baseline

`q75_components`

Exactly the R15 obligation geometry.

### Candidate

`q75_plus_multiscale_seed`

Exactly the R17 promoted geometry:

- q75 primary connected components;
- prominence smoothing radii 0/1/2/4;
- relative prominence >= 0.10;
- persistence >=2 scales or global maximum;
- cluster distance two tiles;
- ignore secondary modes already represented by q75;
- secondary peak must be >= within-file median relevance;
- added secondary obligation width is one 32-line tile.

## Frozen closure/runtime

Both geometry arms use the same downstream runtime:

- 32-line evidence tiles;
- directional `need_before` / `need_after`;
- expansion threshold 0.60;
- no scalar completeness gate;
- final utility only after directional closure;
- final utility threshold 0.65;
- maximum 12 tiles per anchor is safety-only;
- low-utility seed causes the obligation to try its next representative.

## Hidden reference

Generate a fresh full-read System2 field for each holdout using the established
64-line / 32-line-stride protocol.

The references are generated **after this pre-registration** and are used only
for evaluation.

## Primary comparison

For each posterior estimator compare candidate minus baseline on:

- retained high-line recall;
- retained relevance-mass recall;
- retained hidden-reference relevance;
- retained high precision;
- hidden high-reference regions without any obligation;
- materialized source fraction;
- model calls and input tokens;
- closure safety-cap count.

Also record case-level wins/losses rather than relying only on averages.

## Promotion rule

R18 does not require the hybrid to win every case.

It is a stronger default candidate only if fresh holdouts show that secondary
obligations recover additional retained evidence often enough to justify their
extra source/model cost, without a systematic precision collapse.

If the candidate helps only sequential Phase0 but not multi-scale, preserve
that distinction rather than promoting one global geometry.

## Guardrail

No geometry, threshold, task wording, or holdout membership may be changed
after reference/results are inspected.
