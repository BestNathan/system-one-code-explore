# R11C Exact Micro-Target Prompt Calibration — 2026-09-25

## Why R11C exists

R11B successfully created same-file hard negatives by narrowing the coding goal,
but exposed a target-granularity mismatch.

The existing full-read reference scores overlapping 64-line windows. Projecting
a high window score onto every contained line makes an 8-line TARGET appear
high even when the actual relevant mechanism is elsewhere in that window.

R11C fixes the teacher, not the student prompt.

## Exact teacher design

For each narrow-goal case:

- target width: 8 lines;
- target stride: 8 lines (non-overlapping exhaustive coverage);
- System 2 sees the COMPLETE file;
- System 2 sees every exact TARGET id/range;
- it scores each exact TARGET itself;
- nearby relevance must not smear into the target.

The teacher output is a full-read micro-target relevance reference.

## Student design

System One sees:

- the same goal;
- the exact 8-line TARGET;
- 24 source lines before;
- 24 source lines after.

It must score the TARGET only.

## Prompt family

Carry forward the five R11 prompts and add one benchmark-correction candidate:

- generic relevance;
- material evidence;
- counterfactual answer impact;
- minimal evidence keep;
- mechanism match;
- direct target relevance.

The new direct-target prompt explicitly says that nearby code, shared symbols,
file theme, or an adjacent relevant function do not make TARGET itself relevant.

## Cases

Reuse the six narrow-goal R11B cases. This is still calibration data, not final
generalization data.

## Metrics

- high-vs-rest ROC AUC;
- high-low probability separation;
- precision@high-count;
- Pearson/Spearman versus exact teacher score;
- Brier score;
- high/mid/low mean probabilities.

## Decision rule

R11C may select a prompt candidate only.

The selected prompt must be frozen and tested later on unseen files/goals
before it is promoted into Phase0.


## Exhaustive-coverage correction

An initial execution used 8-line targets with stride 16. That left half of the
source uncovered and, on the sparse `extension_runtime_dispatch` goal, could
miss the exact dispatch implementation between sampled blocks.

That execution is superseded.

The canonical R11C design uses **8-line targets with stride 8**, tiling the
entire file without gaps. This matches the intended "score all code fragments"
benchmark and prevents sparse mechanisms from disappearing due to sampling
alignment.
