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


## Phase B result

Workflow run `36027079823` created useful same-file hard negatives, but the
64-line reference projection is too coarse for 8-line student targets.

The decisive counterexample is `extension_runtime_dispatch`: broad CC windows
around lines 225–312 score highly because they contain the real dispatch path
later in the window, but exact targets near 225–248 are duplicate-route
validation. System One scores those exact targets low, which is semantically
reasonable even though the projected label says high.

Therefore the R11B prompt ranking is diagnostic only.

## Phase C — exact micro-target teacher

R11C keeps the narrow-goal hard-negative design but asks the full-read System 2
teacher to score every exact 8-line target directly.

This aligns teacher and student granularity:

```text
full-file System 2 + target identity -> exact micro-target label
local-context System One + same target -> predicted probability
```

The broad 64/32 field remains appropriate for Phase0/search evaluation but is
no longer used as fine-grained prompt-calibration ground truth.

R11C also adds `direct_target_relevance`, a concise prompt that preserves the
generic relevance formulation while explicitly denying relevance credit from
nearby code, shared symbols, or file-level theme.


## Phase A result

Completed in workflow run `36026215590`.

Discovery-set aggregate:

| prompt | ROC AUC | top-K precision | Pearson | Spearman | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| generic relevance | **0.7225** | **0.7000** | **0.3789** | **0.4026** | **0.2258** |
| mechanism match | 0.6774 | **0.7000** | 0.2728 | 0.2830 | 0.2466 |
| material evidence | 0.6705 | 0.6667 | 0.2861 | 0.3127 | 0.2492 |
| minimal evidence keep | 0.6607 | 0.6333 | 0.3032 | 0.3026 | 0.2433 |
| counterfactual answer impact | 0.5872 | 0.6333 | 0.1220 | 0.1775 | 0.2794 |

The simplest prompt — direct task relevance — is the strongest Phase A candidate.

However the fixed absolute sampling buckets exposed a benchmark flaw: all three full-read references produced high and medium examples but no examples below the fixed `0.35` low threshold. Phase A therefore measures high-vs-mid separation, not true high-vs-low calibration.

Per-case generic-relevance AUC:

- command broker ownership: **0.45**;
- extension registry integrity: **0.83**;
- git agent security: **0.8875**.

This variance is important. The aggregate winner is not yet robust across goals.

### Next step

Phase B should:

1. freeze `generic_relevance` as the current candidate;
2. replace fixed score buckets with within-file CC quantiles so every benchmark contributes positive, ambiguous, and negative targets;
3. use fresh files/goals not present in Phase A or R09;
4. compare small wording variants around the winning simple semantics rather than increasingly elaborate evidence language;
5. require consistent per-file AUC/precision before promoting a prompt into Phase0.

Pinned aggregate: `fixtures/research/r11-prompt-calibration-aggregate.json`.
