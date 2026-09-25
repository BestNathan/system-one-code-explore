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


## Canonical result

Canonical workflow: `36082601509`.

All fresh references, six Phase0 trajectories, 24 evidence arms, and aggregate
completed successfully.

### Fresh reference shapes

- `fs_symlink_delete_semantics`: 408 lines, relevance 0.40-0.95, mean 0.85;
  broad relevance field.
- `tmux_env_session_lifecycle`: 701 lines, relevance 0.08-1.00, mean 0.58;
  strongly discriminative.
- `manifest_union_wire_routing`: 423 lines, relevance 0.50-0.96, mean 0.705;
  moderately broad.

### Raw paired aggregate

If the two independently executed evidence arms are compared naively, the
hybrid appears slightly better:

- retained high-recall mean delta: +0.0142;
- retained relevance-mass recall delta: +0.0138;
- retained precision delta: 0;
- materialized source delta: +0.0257;
- hidden high regions without obligation: -0.0833.

However this raw comparison is **not causally valid**.

### Attribution failure discovered by R18

Both retained-evidence "wins" occur on fs/multi-scale repeat 1 and repeat 2.

In both cases:

- q75 and hybrid generate exactly the same two obligations;
- the hybrid adds **zero** secondary obligations;
- seed order is identical.

Yet independent System One closure calls differ near the hard directional
threshold.

Representative repeat 1:

```text
same obligation: 257-320
same seed:       289-320

baseline need_before = 0.59
hybrid   need_before = 0.60
threshold           = 0.60
```

The hybrid arm therefore reads one extra 32-line tile and ends with a larger
retained region, despite there being no geometry difference at all.

This is model/judgment variance crossing a hard runtime threshold, not a hybrid
geometry benefit.

Therefore the two raw retained wins must be removed from causal attribution.

### Actual fresh secondary-obligation case

Only one fresh paired case adds a secondary obligation that changes coverage:

`manifest_union_wire_routing / sequential / repeat 2`.

Hybrid adds:

```text
secondary obligation: 353-384
hidden CC mean:        0.70
directional closure:   353-416
final utility:         0.61
status:                rejected_low_utility
```

Effects versus q75:

- hidden high regions without obligation: 1 -> 0;
- retained evidence: unchanged;
- materialized source: +15.1 percentage points;
- model calls: +3;
- input tokens: +5862.

So the fresh holdout does **not** show an attributable retained-evidence gain
from the hybrid geometry.

It does show that the hybrid can improve coverage state, but post-closure
utility correctly prevents that secondary region from entering final evidence.

### R18 conclusion

R18 does not validate R17 as a default geometry.

More importantly, R18 identifies a flaw in the policy-comparison harness:

> two policies that reach the same semantic state must not receive independent
> System One judgments when their downstream behavior is being compared
> counterfactually.

Independent calls can differ by a few probability points. With hard thresholds,
a 0.59/0.60 difference can create a fake policy win.

The next experiment must use a shared semantic-decision cache:

1. canonicalize each System One closure/utility request by semantic content,
   stripping volatile anchor/obligation ids;
2. baseline and candidate share the same cached response for an identical
   request;
3. only genuinely divergent states cause additional model calls;
4. preserve original usage as logical standalone cost while separately
   recording physical cache hits/misses;
5. assert that when the hybrid generates zero secondary obligations, baseline
   and hybrid final evidence is identical.

Only after that experiment can the R18 fresh holdouts provide causal evidence
about geometry.

Pinned result:

- `fixtures/research/r18-fresh-hybrid-generalization-aggregate.json`.
