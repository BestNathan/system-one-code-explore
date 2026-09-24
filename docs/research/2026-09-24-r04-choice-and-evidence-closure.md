# R04 — Choice Policy and Evidence Closure

## Question

How should System One be used for action selection and final evidence
resolution?

## Hypothesis

Choice is more natural than a scalar Noul score for selecting among
harness-generated legal actions, because the model should reason over the
available action set rather than independently judge isolated actions.

## Design

The experiments changed the adaptive runtime to:

- expose several legal actions plus stop;
- use Choice for policy selection;
- refresh value estimates after execution;
- group fine evidence fragments by their source observation before final
  keep/drop resolution.

Raw report:

- `docs/experiments/relevance-frontier-v3-phase0-choice-closure-2026-09-24.md`

## Result

Two durable conclusions survived later redesigns.

### Choice is a policy distribution

Using only `answer.choice` as an argmax discards useful information. Later v5
research consumes the complete Choice probability distribution and may execute
multiple probes above a threshold.

### Evidence fragments need closure

A contiguous useful observation can become several individually weak fragments.
Judging those fragments independently can drop the entire useful region.

Grouping related fragments before final resolution prevents this failure mode.

## Rejected idea

Do not use independent fine-fragment keep/drop as the only evidence-closure
mechanism.

## Next direction

Use Choice probabilities to drive a batch of sparse probes over a whole-file
probability frontier.
