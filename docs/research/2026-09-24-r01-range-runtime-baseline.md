# R01 — Range Runtime Baseline

## Question

Can a fast System One model drive code localization when the harness owns the
state machine, legal read actions, budgets, and effects?

## Hypothesis

A System One model does not need a ReAct loop if the harness presents a bounded
action space and keeps the durable exploration state.

## Design

The initial runtime used per-file geometric actions:

- head / middle / tail reads;
- expansion before or after previously useful ranges;
- midpoint reads over unread gaps;
- explicit stop.

System One used Choice/Noul decisions while the harness executed reads and
tracked coverage.

## Evidence

The end-to-end benchmark on the frozen nession revision showed that the runtime
could produce usable localization evidence, but used many reads and missed
important cross-file/state-space expansions.

See:

- `docs/research-summary.md`
- `docs/system-one-localization-algorithms.md`

## Result

The experiment established the basic harness thesis:

> State and legal effects belong to the runtime; the fast model can act as a
> local policy/value function.

However, simply improving stop behavior was not enough. The dominant quality
gap moved to state-space discovery and evidence shaping.

## Rejected idea

Do not treat better stop logic as the main path to System One code exploration.

## Next direction

Replace flat range navigation with an adaptive relevance representation that
can decide where to spend future reads.
