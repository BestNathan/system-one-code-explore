# R19 — Counterfactual-Safe Geometry A/B

## Status

Current research iteration.

## Why R19 exists

R18 fresh holdouts exposed an experimental-design flaw.

Two geometry arms can generate identical obligations and identical seeds, yet
independent System One calls can differ by a few probability points. A hard
runtime threshold can convert that small judgment variance into different
source reads and final evidence.

Observed R18 example:

```text
same Phase0 field
same obligations
same seed 289-320
same visible source

q75 arm:    need_before = 0.59
hybrid arm: need_before = 0.60
threshold:                0.60
```

The hybrid arm expanded one extra tile and produced a raw retained-recall
"win" despite adding zero secondary obligations.

That comparison is not counterfactually valid.

## R19 invariant

When two policies reach the same **semantic System One request**, they must
receive exactly the same System One response.

Only a genuine policy/state divergence may create a new model judgment.

## Shared semantic decision cache

Baseline and candidate execute inside the same job and share one cache.

Cache key:

```text
hash(
  stage,
  canonical semantic state,
  canonical questions
)
```

Volatile runtime identities are stripped:

- `anchor_id`;
- `obligation_id`.

They do not change the source, goal, range, or decision semantics and must not
prevent cache reuse.

The semantic key still contains:

- goal;
- file;
- obligation range;
- seed range;
- current anchor range;
- literal source;
- adjacent candidate range;
- question wording and criteria.

## Usage accounting

A cache miss:

- performs a real System One call;
- stores response + usage;
- increments physical usage.

A cache hit:

- returns the exact stored response;
- returns the stored usage to the caller so the policy's **logical standalone
  cost** remains comparable;
- increments cache-hit count but not physical usage.

Therefore R19 reports both:

- logical per-policy calls/tokens;
- physical model calls used to execute the paired counterfactual test.

## Sanity invariant

When hybrid geometry adds zero secondary obligations, q75 and hybrid must
produce identical:

- directional closure decisions;
- materialized source ranges;
- retained final regions;
- retained benchmark metrics.

Any violation is an R19 harness bug.

## Frozen data

Reuse R18's already frozen fresh inputs from workflow `36082601509`:

- three fresh references;
- six fresh Phase0 trajectories;
- two estimators;
- two repeats.

No reference or Phase0 call is regenerated.

## Frozen policies

Baseline:

`q75_components`

Candidate:

`q75_plus_multiscale_seed`

All R15/R17 closure/runtime thresholds remain unchanged.

## Primary result

For each of 12 Phase0 trajectories, compute candidate minus baseline only after
shared-decision control.

Primary metrics:

- retained high recall;
- retained relevance-mass recall;
- retained hidden-reference relevance;
- retained high precision;
- hidden high-reference regions without obligation;
- materialized source fraction;
- logical calls/tokens;
- physical cache misses/hits.

## Interpretation

R19 is the first causally interpretable A/B for obligation geometry.

If the hybrid gains disappear, R17/R18 apparent improvements were dominated by
decision noise or diagnostic reuse.

If retained gains remain only on states introduced by secondary obligations,
that is attributable evidence for the geometry mechanism.
