# Sparse Phase0 v4: micro-sampling before adaptive frontier search

## Problem corrected

The previous v3 Phase0 used head/middle/tail samples for every depth-0 coarse
region. That created a useful controlled experiment, but it is the wrong
runtime contract for large files:

- Phase0 cost still grows with the number of coarse regions.
- A 112-line sample is already too large to be called sensing.
- Marking a coarse leaf as "observed" after a large sample encourages the
  harness to confuse region coverage with evidence.
- Broad source chunks can make System One judge a mixed block rather than the
  local signal we actually want.

Phase0 must be sparse sensing, not a coarse scan.

## v4 contract

Default Phase0 budget:

- micro sample width: 8 source lines
- fixed bootstrap: head / middle / tail
- maximum Phase0 probes: 8
- maximum source-line budget: about 64 lines
- candidate probe actions per Choice epoch: up to 10
- cost does not scale with file length

The bootstrap is only enough to give the policy a few observations. After that,
the harness generates legal micro-probe positions from:

1. the largest unread gaps, sampled at several interior positions;
2. immediate neighborhoods around already-read snippets.

System One Choice selects exactly one next position, or stops Phase0. The
candidate source is not read until the action is selected.

This gives the runtime the following loop:

```text
Phase0
  3 tiny bootstrap probes
        |
        v
  sparse observations
        |
        v
  generate legal 8-line probe positions
        |
        v
  Choice(next probe | StopPhase0)
        |
        +---- stop -----------------------+
        |                                 |
        v                                 |
  read exactly one tiny block             |
        |                                 |
        +---------- repeat ---------------+
                                          |
                                          v
                         provisional relevance field
                         from sampled evidence only

Phase1
  Choice(frontier action | StopFrontier)
        |
        v
  focused read (larger than Phase0)
        |
        v
  Noul value refresh

Phase2
  group-aware evidence closure
```

## Important semantics

A Phase0 sample does **not** mean its coarse region is fully observed.

v4 therefore reports:

- `phase0.sampled_source_lines`
- `phase0.sampled_source_coverage`
- `phase0.observed_leaf_count`
- `frontier_coverage` as an observed-leaf ratio only
- `source_coverage` as actual unique source lines read across the whole run

The primary Phase0 efficiency metric is sampled source coverage, not leaf
coverage.

## Why the model chooses positions instead of content

The harness owns the action space. It proposes legal positions using geometry
only. The model sees:

- the task;
- the file length;
- already-read tiny snippets;
- candidate ranges and why the harness exposed them.

The model then chooses which position is worth paying to read next.

This keeps the state/action split explicit:

```text
Harness: where may I look next?
System One: which legal look has the highest information value?
Harness: execute exactly that read.
```

The runtime never pre-reads all candidate positions and asks the model to rank
them afterward.

## Controlled parameters for the next run

For the frozen websocket subject:

- Phase0 sample lines: 8
- Phase0 maximum probes: 8
- Phase0 candidate actions: 10
- Phase1 probe lines: 64
- Phase1 Choice action set: up to 6 + Stop
- Phase1 maximum rounds: 12
- Final evidence: v3 group-aware closure

The full-read System 2 reference remains intentionally separate. It is a
ground-truth-style evaluator, not part of System One exploration.
