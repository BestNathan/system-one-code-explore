# R11 System One Prompt Calibration Phase A Results — 2026-09-25

## Status

Phase A completed successfully on workflow run `36026215590`.

All three full-read CC references and all three System One prompt-calibration
jobs completed.

## Aggregate prompt result

| prompt | high-vs-rest AUC | precision@K | Pearson | Spearman | Brier ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| generic relevance | **0.7225** | **0.7000** | **0.3789** | **0.4026** | **0.2258** |
| mechanism match | 0.6774 | **0.7000** | 0.2728 | 0.2830 | 0.2466 |
| material evidence | 0.6705 | 0.6667 | 0.2861 | 0.3127 | 0.2492 |
| minimal evidence keep | 0.6607 | 0.6333 | 0.3032 | 0.3026 | 0.2433 |
| counterfactual answer impact | 0.5872 | 0.6333 | 0.1220 | 0.1775 | 0.2794 |

On this discovery set, the simplest prompt wins:

> How relevant is the TARGET code block to the user's goal?

The more elaborate evidence/counterfactual semantics do not automatically make
System One better calibrated.

## Important dataset failure

This is **not** yet a valid prompt-selection conclusion.

All three broad goal/file pairs produced no true low-reference examples below
0.35. The sampled targets are only high and medium relevance.

That means Phase A mostly tests:

> can the prompt separate very relevant code from still-relevant surrounding code?

It does not test the more important Phase0 failure mode:

> can the prompt aggressively suppress code that looks topically adjacent but
> is actually irrelevant?

The absence of negatives happened because each goal described a broad set of
responsibilities already concentrated inside its chosen file.

## Per-file signal

Generic relevance is strong on two files:

- extension registry: AUC ≈ **0.83**, Pearson ≈ **0.679**, precision@K ≈ **0.80**;
- git agent security: AUC ≈ **0.8875**, Pearson ≈ **0.628**, precision@K ≈ **0.90**.

Command broker is different. None of the prompts separate its high and mid
regions well; mechanism-match is best there at only ≈ **0.4722** AUC.

That case warns against overfitting to the aggregate.

## Phase A conclusion

Do not replace the current Phase0 scoring prompt yet.

The current evidence supports only a weaker statement:

> concise direct relevance wording is at least as good as, and on this
> positive-heavy discovery set generally better than, more complicated
> evidence/counterfactual instructions.

## Phase B requirement

Construct a hard-negative calibration set with narrower goals.

For the same or additional files, targets must include code that:

- shares names/types with the goal but implements a different concern;
- is near relevant code but does not materially answer the goal;
- is generic lifecycle/logging/error plumbing;
- is test/fixture scaffolding unrelated to the specific mechanism.

Phase B is dataset repair / prompt calibration, not a generalization test.
After a candidate prompt is selected on a dataset with real negatives, a final
prompt must still be frozen and tested on completely unseen files/goals.
