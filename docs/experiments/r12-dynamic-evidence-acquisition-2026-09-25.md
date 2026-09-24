# R12 Dynamic Evidence Acquisition — 2026-09-25

## Pre-registration

R12 replaces R10's fixed-six selector with a dynamic Choice state machine.

Frozen inputs:

- Phase0/reference run: `36004833542`;
- three R08 tasks;
- two Phase0 repeats;
- sequential and multi-scale posterior arms.

Frozen R12 policy:

- 32-line non-overlapping full-file actions;
- one source read per Choice round;
- read action removed after execution;
- literal selected evidence returned to the next Choice state;
- explicit `stop` action;
- stop if `P(stop) >= P(best read)`;
- also stop if best-read lift over uniform prior is below 1.1;
- 32 rounds is safety-only, not a valid normal stopping target.

Primary claim is not "select more" or "select fewer". It is:

> select exactly as much evidence as the remaining marginal value justifies.

Evaluation uses the hidden canonical CC field only after the R12 trajectory has
finished.

Primary outputs:

- dynamically selected range count;
- precision / recall / relevance-mass recall;
- same-tile-budget oracle ratio;
- stop regret / premature-stop rate;
- safety-cap rate;
- model/token cost.
