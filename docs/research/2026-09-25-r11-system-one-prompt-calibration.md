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
