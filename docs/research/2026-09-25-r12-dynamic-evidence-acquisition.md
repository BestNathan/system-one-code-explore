# R12 — Probability-Frontier-Guided Dynamic Evidence Acquisition

## Status

Current research iteration.

The initial single-Choice design was rejected before becoming canonical.
R12 now uses independent Noul action scores and reads every remaining action
whose marginal-evidence probability clears a fixed threshold.

## Why R12 exists

R10 proved that completed Phase0 trajectories already contain useful code
evidence, but its selector was deliberately artificial:

- rank observed micro-probes;
- expand them to 32 lines;
- keep exactly six.

That is a useful diagnostic baseline, not a final evidence runtime.

The number of useful code ranges should emerge from the task, the Phase0
probability frontier, and evidence already materialized.

## Core state machine

```text
completed Phase0 probability frontier
        |
        v
partition whole file into equal 32-line ReadRange actions
        |
        v
score EVERY remaining action with independent Noul
        |
        v
read ALL actions whose Noul >= threshold
        |
        v
add literal source to accumulated evidence
        |
        v
remove those actions from the action space
        |
        +------------------------------+
                                       |
                                       v
                         rescore every remaining action
                                       |
                                       v
                        no score >= threshold -> stop
```

There is no target snippet count.

A round can materialize zero, one, or many ranges.

## Why Noul, not Choice

A Choice result is categorical:

```text
P(a1) + P(a2) + ... + P(an) + P(stop) = 1
```

Its probabilities describe competition between alternatives. With many useful
actions they are forced to split a unit mass, so the value of one action
depends on how many other actions exist.

That is the wrong semantics for R12.

R12 needs an independent question for each action:

```text
Noul(tile_i) =
P(
  reading tile_i NOW adds new material evidence
  | Phase0 frontier, evidence already selected
)
```

These scores do not sum to one. Multiple ranges can all receive high
probability in the same round.

For example:

```text
tile_03 = 0.91
tile_08 = 0.84
tile_17 = 0.79
tile_22 = 0.76
```

All four should be read together if the threshold is 0.65.

## Rejected R12-A design

The first implementation used one Choice across all ranges plus Stop and read
only the single best range each round.

That design is retained only as a rejected research branch in the history. It
does not match the intended semantics because:

1. valuable actions compete for normalized probability mass;
2. a file with ten simultaneously valuable ranges still exposes only one
   winner;
3. repeated single-read rounds create unnecessary model calls;
4. "all remaining actions are low probability" is not meaningful for a
   categorical distribution.

The canonical R12 implementation is Noul multi-select.

## Equal action space

Initial action width is frozen to 32 source lines:

- non-overlapping;
- complete coverage of the file;
- final tile may be shorter.

Before a range is read, the action exposes only Phase0-derived state:

- range;
- mean Phase0 relevance;
- max Phase0 relevance;
- mean Phase0 uncertainty;
- Phase0 observed fraction.

The source text itself remains hidden until that ReadRange executes.

This preserves progressive disclosure.

## Evidence feedback

After all above-threshold ranges from one round are read, their literal source
is added to the next scoring state.

Every remaining tile is then rescored for **marginal evidence value**, not
static task relevance.

A previously attractive unread tile can therefore fall below threshold when
the new evidence already establishes the same fact.

This is the main reason R12 must iterate rather than threshold the Phase0 field
once.

## Scoring request

For each remaining action System One receives an independent Noul question:

> How likely is reading this exact source range now to add new material
> evidence needed for the goal, beyond evidence already materialized?

High probability means the range is likely to add a distinct useful mechanism,
state transition, dependency/contract, constraint, edge case, or
implementation fact.

Low probability means it is likely irrelevant, redundant, incidental, or
merely confirmatory.

The implementation batches Noul questions for transport efficiency, but the
semantics remain independent per action.

## Frozen baseline parameters

First canonical R12 run:

- tile width: 32 lines;
- Noul threshold: 0.65;
- Noul transport batch size: 16 actions;
- read all actions at or above threshold;
- rescore after every materialization round;
- stop when no remaining action clears threshold;
- 16 rounds is a safety cap only.

The 0.65 threshold is inherited from the repository's existing evidence
threshold and is not fitted against R10 data.

Any run ending at the safety cap is a policy failure, not a valid stop.

## Controlled experiment

Reuse the canonical R08 Phase0 trajectories and CC references:

- source workflow: `36004833542`;
- subject:
  `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`;
- three single-file tasks;
- two Phase0 repeats;
- sequential and multi-scale posterior arms.

This makes R10 fixed-six evidence the direct baseline.

## Metrics

### Evidence quality

- dynamically selected tile count;
- selected source lines and source fraction;
- mean hidden CC relevance;
- high-line precision;
- high-line recall;
- weighted relevance-mass recall;
- same-action-space oracle at the same selected tile count;
- relevance recall per source fraction.

### Termination quality

At the first all-below-threshold round, inspect every remaining tile using the
hidden CC field:

- best remaining tile mean relevance;
- best remaining high-line fraction;
- number of remaining tiles with mean CC relevance >= 0.70;
- premature-stop rate.

This is **stop regret**.

If the Noul policy stops while strong hidden-reference tiles remain, the
threshold/scoring semantics are not yet good enough.

### Batch behavior

Because R12 can read many actions per round, also record:

- number selected per round;
- probability distribution of selected versus rejected actions;
- overlap/redundancy among same-round selected evidence;
- how scores change after evidence feedback;
- number of rescoring rounds.

### Cost

- System One calls;
- input/output tokens;
- selected source fraction;
- evidence quality per token/read line.

## Success criteria

Compared with the R10 fixed-six baseline, R12 is promising if:

1. selected count varies naturally by task;
2. precision stays comparable while recall/relevance mass increases where more
   evidence is required;
3. easy tasks can stop after few tiles;
4. same-budget oracle gap narrows;
5. premature-stop rate is low;
6. safety-cap rate is near zero;
7. later rounds select fewer/weaker marginal actions as evidence becomes
   sufficient.

## Later isolated variables

Only after the baseline is characterized:

- 16 / 32 / 64-line action granularity;
- Noul threshold;
- static threshold versus calibrated threshold;
- score all remaining actions versus Phase0-prefiltered action subsets;
- literal evidence versus compact evidence summaries;
- intra-round redundancy control;
- feeding Phase1 observations back into the Phase0 posterior.

R12 first tests whether independent Noul multi-select is the right phase shape.
