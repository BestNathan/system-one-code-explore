# R11 — System One Relevance Prompt Calibration

## Status

Current parallel research iteration.

## Question

A full-read System 2 evaluator can already score the complete file for a concrete coding goal. R11 asks whether that field can supervise a better local System One relevance prompt.

The desired output is a calibrated scalar signal: genuinely useful local code should receive high probability, while incidental or merely nearby code should stay low.

## Benchmark construction

For each benchmark case:

1. freeze a repository revision and a concrete coding goal;
2. generate the existing overlapping 64/32 full-read System 2 field;
3. project the field to source lines;
4. sample 8-line TARGET blocks from high, medium, and low regions;
5. provide 24 lines of surrounding context on each side;
6. ask System One to score the TARGET only.

The surrounding code exists only to resolve symbols and control flow. It is not the item being scored.

## Discovery files

R11 intentionally avoids the fresh R09 holdouts.

- crates/nession-server/src/server/command_broker.rs
  - reconnect ownership, pending request routing, timeout/disconnect cleanup;
- crates/nession-agent/src/extension.rs
  - descriptor validation, route conflicts, manifest construction, dispatch;
- crates/nession-git/src/agent.rs
  - working-directory security boundary, typed request decoding, dispatch and errors.

## Prompt family

Phase A compares five semantics:

- generic task relevance;
- material evidence;
- counterfactual answer impact;
- minimal evidence keep/drop;
- direct mechanism match.

Every prompt sees exactly the same targets and surrounding source.

## Metrics

Primary:

- high-vs-rest ROC AUC;
- mean high minus mean low probability;
- precision among the top K predictions, where K equals the number of high-reference targets.

Secondary:

- Pearson and Spearman against continuous CC score;
- Brier score for the high-reference label;
- token/model-call cost.

## Guardrail

This three-file set is prompt discovery data only.

A prompt that wins here becomes a candidate, not a production conclusion. Promotion into Phase0 requires freezing the prompt and testing it on an unseen validation set.

R09 holdouts must not be used to select the R11 prompt.


## Phase A result

Workflow run `36026215590` completed successfully.

On the broad-goal discovery set, `generic_relevance` had the strongest
aggregate high-vs-rest AUC (0.7225), Pearson (0.3789), Spearman (0.4026), and
Brier score (0.2258). More elaborate evidence/counterfactual wording did not
improve calibration.

However, all three cases contained zero low-reference examples below 0.35.
Therefore Phase A is not sufficient to select a production prompt.

## Phase B — hard-negative calibration

Phase B keeps the same files but narrows each goal to one concrete mechanism.
The purpose is to create same-file hard negatives rather than easy
cross-domain negatives.

The prompt family remains frozen. Phase B may select a prompt candidate, but a
generalization claim still requires unseen files/goals.
