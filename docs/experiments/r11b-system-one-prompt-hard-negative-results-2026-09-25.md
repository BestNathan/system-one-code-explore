# R11B Hard-Negative Prompt Calibration Results — 2026-09-25

## Status

Completed on workflow run `36027079823`.

Phase B successfully repaired the Phase A dataset geometry, but also revealed a
more fundamental reference-label problem. The prompt metrics in this report are
therefore **diagnostic only** and must not be used to promote a production
prompt.

## Hard-negative geometry

Narrow same-file goals worked:

| case | sampled high | sampled mid | sampled low |
| --- | ---: | ---: | ---: |
| broker stale-generation ownership | 10 | 10 | 1 |
| broker pending timeout/cleanup | 10 | 10 | 4 |
| extension duplicate routes | 10 | 10 | 8 |
| extension runtime dispatch | 6 | 8 | 10 |
| git cwd security | 10 | 10 | 8 |
| git typed decode | 10 | 10 | 0 |

Five of six cases contain real same-file low negatives. The remaining
`git_typed_decode` case is retained as a positive-heavy control.

## Prompt metrics under the projected reference

| prompt | AUC | precision@K | Pearson | Spearman | high mean | low mean | high-low |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| generic relevance | **0.7664** | **0.6222** | **0.5618** | **0.6444** | **0.4314** | 0.0787 | **0.3412** |
| material evidence | 0.7380 | 0.5944 | 0.4841 | 0.5907 | 0.3852 | 0.0835 | 0.2831 |
| minimal evidence keep | 0.7387 | 0.5500 | 0.4726 | 0.5988 | 0.3469 | 0.0935 | 0.2473 |
| mechanism match | 0.7241 | 0.5778 | 0.4866 | 0.5778 | 0.3879 | **0.0696** | 0.3039 |
| counterfactual impact | 0.6794 | 0.5167 | 0.4215 | 0.5066 | 0.3766 | 0.1366 | 0.2399 |

The concise generic prompt is still strongest in aggregate. Mechanism-match is
the most aggressive low-negative suppressor.

## Reference failure discovered

The current calibration script projects the overlapping 64-line CC reference
field onto individual 8-line TARGET blocks.

That is too coarse.

The clearest example is `extension_runtime_dispatch`.

The full-read CC reference gives the broad region around lines 225–312 very
high relevance because the 64-line windows contain the actual `dispatch()`
implementation around the later part of that region.

After line projection, targets such as 225–232 inherit reference ≈ 0.96 even
though those exact lines are duplicate-route validation, not runtime dispatch.
System One generic relevance scores that exact target only ≈ 0.06.

Source inspection supports the System One judgment:

- lines 225–248 are duplicate core-wire collision handling;
- the actual `dispatch()` method appears later, around the 270s.

So some apparent System One errors are actually teacher-label leakage caused by
window projection.

This explains why `extension_runtime_dispatch` is nearly impossible for every
prompt: the high labels do not consistently correspond to the 8-line target
being scored.

## Revised calibration design

R11C must create **micro-target teacher labels directly**.

The full-read System 2 teacher should see:

1. the complete file;
2. the exact coding goal;
3. the complete list of 8-line TARGET ranges;

and return one relevance probability for each exact TARGET while having full
file context.

Then System One receives only:

- the same goal;
- the exact TARGET;
- bounded local context around it.

This yields the intended comparison:

```text
System 2:
  full file + exact TARGET identity
        -> micro-target relevance label

System One:
  local neighborhood + exact TARGET
        -> predicted relevance

compare
```

The broad 64/32 field remains useful for Phase0/search evaluation and for
candidate stratification, but it must not be treated as fine-grained ground
truth for 8-line prompt calibration.

## Conclusion

Two useful findings survive Phase B:

1. same-file narrow goals are the right way to construct hard negatives;
2. simple/direct relevance wording is a strong prompt candidate.

But prompt selection is not yet complete because the teacher labels need to
match the target granularity. R11C fixes the benchmark before doing further
prompt tuning.
