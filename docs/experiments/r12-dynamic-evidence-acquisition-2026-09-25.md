# R12 Dynamic Evidence Acquisition — 2026-09-25

## Pre-registration

R12 replaces R10's fixed-six selector with a dynamic Noul multi-select state
machine.

Frozen inputs:

- Phase0/reference run: `36004833542`;
- three R08 tasks;
- two Phase0 repeats;
- sequential and multi-scale posterior arms.

Frozen canonical R12 policy:

- 32-line non-overlapping full-file actions;
- every remaining action receives an independent Noul marginal-evidence score;
- Noul scoring may be transported in batches of 16 questions;
- every action with score >= 0.65 is read in the same round;
- all materialized ranges are removed from the action space;
- literal selected evidence is returned to the next scoring state;
- all remaining actions are rescored after each round;
- normal termination occurs when no remaining action reaches 0.65;
- 16 rounds is safety-only and is not a valid normal stopping target.

The 0.65 threshold is inherited from the existing evidence threshold and is not
selected using R10 results.

Primary claim:

> evidence count should emerge from independent marginal value, not from a
> fixed number of snippets and not from a normalized categorical Choice.

## Rejected pre-run design

An earlier R12 draft used one Choice distribution over all ranges plus Stop and
read only one range per round.

That draft is superseded before canonical interpretation because Choice
probabilities sum to one and therefore represent relative competition rather
than independent read-worthiness. Its workflow run, if present, is
non-canonical diagnostic history.

## Evaluation

Use the hidden canonical CC field only after the dynamic trajectory completes.

Primary outputs:

- dynamically selected range count;
- source fraction;
- precision / recall / relevance-mass recall;
- same-tile-budget oracle ratio;
- stop regret / premature-stop rate;
- selected count per round;
- score change after evidence feedback;
- safety-cap rate;
- model/token cost.

A good outcome is not "read many" or "read few"; it is:

> read every range whose current marginal evidence probability is high, then
> stop when all remaining ranges are low.
