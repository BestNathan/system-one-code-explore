# R12 — Probability-Frontier-Guided Dynamic Evidence Acquisition

## Status

Current research iteration.

## Why R12 exists

R10 proved that completed Phase0 trajectories already contain useful code
evidence, but its selector was deliberately artificial:

- sort observed micro-probes by score;
- expand them to 32 lines;
- keep exactly six.

That was useful as a diagnostic, but it is not a plausible final evidence
runtime. The number of useful snippets should depend on the task and on what
has already been read.

R12 replaces the fixed-count selector with a second System One state machine.

## Question

Given a completed Phase0 probability frontier, can System One dynamically read
full code ranges until the remaining action space no longer contains evidence
worth acquiring?

## State transition

```text
completed Phase0 probability frontier
        |
        v
partition whole file into equal evidence tiles
        |
        v
remaining ReadRange actions + Stop
        |
        v
System One Choice
        |
        +--> Stop
        |
        +--> Read one tile
                 |
                 v
          add literal source to evidence
                 |
                 v
          remove tile from action space
                 |
                 +--------------------+
                                      |
                                      v
                               Choice again
```

The action space therefore shrinks monotonically.

There is no target evidence count.

## Why Stop must be an explicit Choice action

A categorical Choice distribution without Stop is purely relative. If there are
N remaining actions, at least one action must receive probability near or above
1/N even when every action is bad.

Therefore "all actions have low probability" is not well-defined without an
anchor.

R12 includes a `stop` action whose meaning is:

> the evidence already read is sufficient and no remaining range is likely to
> add a distinct material fact worth its read cost.

A round stops when either:

1. `P(stop) >= max P(read_i)`; or
2. the best read action is not meaningfully above the categorical uniform
   prior.

The second criterion reuses the existing Phase0 threshold multiplier:

```text
best_read_lift = P(best_read) / (1 / (remaining_actions + 1))

continue only if best_read_lift >= 1.1
```

The value 1.1 is inherited from the current Phase0 Choice batch policy and is
not tuned against R10/R12 references.

## Equal action space

Initial R12 action width:

- 32 source lines per action;
- non-overlapping;
- covers the complete file;
- the final tile may be shorter.

For a 3,000-line file this yields roughly 94 actions.

Every action exposes only Phase0-derived metadata before it is read:

- mean relevance;
- max relevance;
- mean uncertainty;
- Phase0 observed fraction;
- source range.

Source text is disclosed only after System One chooses the action.

This preserves the intended progressive-disclosure property.

## Evidence feedback

After a tile is read, its literal source is added to the next Choice state.

The next decision therefore asks for **marginal evidence value**, not independent
topical relevance. A range should become less attractive when its facts are
already covered by selected evidence.

Phase0 itself is frozen during R12. Reading an evidence tile does not mutate the
Phase0 posterior. This keeps the two phases separable:

- Phase0 estimates where evidence may exist;
- R12 decides which full ranges are actually worth materializing.

## Controlled experiment

The first R12 experiment reuses the canonical R08 Phase0 trajectories and CC
references:

- Phase0/reference workflow: `36004833542`;
- subject:
  `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`;
- three R08 single-file tasks;
- two Phase0 repeats;
- `sequential_exponential` and `multi_scale_gaussian`.

This directly compares R12 against the R10 fixed-six baseline without rerunning
Phase0.

## Metrics

### Evidence quality

- number of dynamically selected tiles;
- selected source lines / source fraction;
- mean CC relevance;
- high-line precision;
- high-line recall;
- weighted relevance-mass recall;
- same-action-space oracle at the same selected tile count;
- relevance recall per source fraction.

### Termination quality

The most important new diagnostic is **stop regret**.

At termination, evaluate every unselected tile with the hidden CC reference:

- best remaining tile mean relevance;
- best remaining tile high-line fraction;
- number of remaining tiles whose mean relevance is >= 0.70;
- premature-stop flag.

A selector that returns clean evidence but stops while an obviously valuable
tile remains has not solved the phase.

### Cost

- Choice rounds;
- System One calls;
- input/output tokens;
- termination reason;
- safety-cap rate.

## Safety cap

The implementation has a 32-round cap only to prevent a broken policy from
creating an unbounded workflow.

It is not considered a valid termination mechanism. Any run ending at
`safety_cap` is evidence that the stopping policy failed.

## Success criteria

R12 is promising if, compared with R10 fixed-six evidence:

1. evidence precision is not materially worse;
2. variable evidence count improves recall/relevance mass when the task needs
   more evidence;
3. simple tasks naturally stop with fewer ranges;
4. same-budget oracle gap narrows;
5. premature-stop and safety-cap rates are low;
6. selected ranges show declining marginal reference value near termination.

## Next research variables

Do not tune all of these at once.

If the baseline works, later iterations can isolate:

- 16 / 32 / 64-line action granularity;
- stop-anchor wording;
- 1.1 uniform-lift threshold;
- one-read-per-round versus above-threshold batches;
- compact summaries versus literal accumulated evidence;
- Phase0 posterior updates from Phase1 reads.

R12 first establishes whether this phase shape is viable at all.
