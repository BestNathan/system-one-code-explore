# R15 — Frontier Obligations + Directional Semantic Closure

## Status

Next research iteration after R13/R14 diagnosis.

## Core conclusion from R13/R14

Three concepts must not be collapsed:

1. **coverage obligation** — which parts of the Phase0 frontier must be
   materially inspected;
2. **semantic closure** — whether the local code unit intersected by a seed has
   been read far enough before/after;
3. **final utility** — whether the closed local code unit is useful for the
   task.

R13 let System One re-decide coverage and merged evidence before closure. That
over-read and created giant mixed regions.

R14 made closure anchor-local, which fixed runaway region size, but still used:

- model-controlled representative coverage;
- a scalar completeness score;
- pre-closure utility as a gate.

The canonical R14 results show those choices are still wrong:

- hidden-reference premature stop remained 100%;
- directional before/after scores could both be low while scalar completeness
  remained low;
- useful hidden-reference fragments were sometimes dropped as low utility
  before their local unit had been closed.

R15 changes the runtime invariants rather than tuning thresholds.

## 1. Coverage becomes a Harness obligation

System One no longer decides whether a high-value Phase0 region deserves
coverage.

The Harness derives a finite set of **frontier obligations** directly from the
probability field.

### Relative, not absolute, frontier geometry

Absolute Phase0 calibration differs across posterior implementations. A fixed
threshold such as 0.65 can produce no obligation for a useful but
under-calibrated field.

Therefore R15 should derive obligations from the shape/rank of the field:

1. aggregate line relevance into the same equal evidence tiles;
2. compute within-file tile relevance ranks/quantiles;
3. identify contiguous high-rank runs / local modes;
4. collapse a flat high plateau into one obligation rather than one obligation
   per tile;
5. retain separated modes as separate obligations.

The first implementation should prefer simple deterministic geometry over
another model call.

Example:

```text
tile relevance
.10 .12 .80 .83 .81 .20 .18 .76 .79 .15
          └──── obligation A ────┘
                              └ obligation B ┘
```

A broad flat catalog-like plateau becomes one representative obligation, not a
command to read the whole file.

### Obligation state

```text
FrontierObligation {
  id
  tile_ids
  representative_candidates
  attempted_seed_ids
  anchors
  status: unresolved | satisfied | exhausted
}
```

The runtime cannot stop while a high-value obligation remains unresolved.

This makes objective 1 a state invariant, not a prompt preference.

## 2. A seed creates an anchor

For each unresolved obligation, choose one representative unread tile.

Initial baseline can simply choose the highest Phase0-relevance tile in the
obligation. Later work can compare System One selection among equal candidates.

Reading a seed creates:

```text
EvidenceAnchor {
  obligation_id
  seed_range
  current_range
  expansion_history
  closure_status
  final_utility
}
```

Anchors are independent until final output.

## 3. Remove scalar completeness from control flow

R14 demonstrated that a scalar question:

> Is this fragment complete?

can disagree with the actionable directional questions.

Example from canonical reconnect:

```text
need_before ~= 0.43
need_after  ~= 0.31
scalar completeness ~= 0.58
```

The model is saying no adjacent direction is worth reading, while still
refusing to give a high abstract completeness score.

For runtime purposes, directional continuation is the thing that matters.

R15 therefore makes semantic closure:

```text
closed(anchor) =
    need_before < expansion_threshold
AND need_after  < expansion_threshold
```

Scalar completeness may remain as a diagnostic only.

## 4. Directional questions

### Need before

> The anchor intersects one local semantic unit relevant to the task. Based on
> the currently visible contiguous source, how likely is the immediately
> preceding tile required to recover the beginning, setup, enclosing branch,
> function header, or other context necessary to understand THIS SAME local
> unit? Do not expand merely to discover another related construct.

### Need after

> The anchor intersects one local semantic unit relevant to the task. Based on
> the currently visible contiguous source, how likely is the immediately
> following tile required to see the continuation, body, branch outcome,
> state transition, error path, or follow-up necessary to understand THIS SAME
> local unit? Do not expand merely to discover another related construct.

Both are independent Noul probabilities.

No global "is the answer sufficient?" wording appears in closure.

## 5. Utility is evaluated after closure

A truncated fragment can look unhelpful precisely because the meaningful
behavior is outside the current tile.

Therefore R15 must not discard an anchor because pre-closure utility is low.

Flow:

```text
seed
  |
  v
directional closure
  |
  v
closed local unit
  |
  v
final utility Noul
```

Final utility question:

> Now that the anchor-specific local semantic unit is closed, how likely does
> this complete unit contain material evidence needed to solve the task?

If utility is high, the obligation is satisfied and the anchor enters final
evidence.

If utility is low, the anchor is a false-positive representative. The
obligation is still unresolved and may try another representative seed from
the same frontier region.

This distinction is critical:

```text
low-utility anchor != low-value frontier obligation
```

## 6. Stop semantics

There is no global Stop Noul.

The file phase ends when every frontier obligation is either:

- **satisfied**: at least one closed useful anchor represents the obligation;
- **exhausted**: all representative candidates were tried without useful
  evidence.

This makes stopping auditable and deterministic.

A later stage can separately ask whether evidence is sufficient to answer the
task. That is not the same as whether localization/coverage is complete.

## 7. Expected benefits

### Against R12

Evidence feedback cannot collapse all remaining high-value frontier regions,
because unresolved obligations remain in state.

### Against R13

Broad high plateaus create representative obligations rather than reading every
tile.

### Against R14

Anchor closure cannot be blocked by low pre-closure utility, and cannot remain
"unresolved" merely because an abstract completeness probability stays below a
threshold after both directional expansion needs are already low.

## 8. Evaluation

### Coverage

- obligation count;
- satisfied/exhausted obligation count;
- hidden CC relevance of each obligation's chosen anchor;
- high-line recall;
- hidden high-value regions not represented by any obligation.

### Closure

- tiles expanded before/after per anchor;
- anchor span distribution;
- rate of directional closure;
- closure safety-cap rate;
- hidden System2 audit of whether a closed anchor still truncates the relevant
  local semantic unit.

### Utility

- final utility after closure;
- precision of retained anchors;
- false-positive seed rate;
- attempts required per obligation.

### Cost

- source fraction;
- model calls/tokens;
- source lines per satisfied obligation.

## 9. Research guardrail

R15 can reuse R08/R13/R14 cases for mechanism debugging, but threshold/geometry
choices selected from those results must later be frozen and validated on fresh
files/goals before any generalization claim.
