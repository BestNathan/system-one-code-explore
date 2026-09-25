# Research Summary

## Project objective

System One Code Explore studies whether a constrained System One harness can perform code localization well enough to replace or approximate System Two for:

1. finding the files relevant to an engineering task;
2. finding concrete, semantically usable evidence spans inside those files;

while reducing model calls, tokens, wall time, and unnecessary source exposure.

System Two is a stronger reference and possible escalation path, not ground truth.

## Current problem model

```text
Repository + Task
    -> File Discovery
    -> RelevantFile[]
    -> Evidence Localization
       -> sparse observations
       -> relevance / uncertainty state
       -> coverage obligations
       -> evidence anchors
       -> directional semantic closure
       -> post-closure utility
    -> EvidenceSpan[]
```

File discovery and evidence localization are separate problem domains with separate state/action spaces and benchmarks.

## Strongest retained findings

- System One works best as a bounded policy/value function inside a Harness, not as an unconstrained ReAct loop.
- Progressive disclosure is essential; repository trees, full files, and action spaces should not be eagerly injected.
- Sparse observations are a better basis than a few coarse region scores.
- Whole-file relevance/posterior state is useful, but relevance and epistemic uncertainty must be separated.
- Coverage must be durable state: finding some useful evidence must not erase another unresolved relevant region.
- Fixed top-N evidence is an artificial constraint.
- Relevant fragments must be closed around an anchor/local semantic unit; merged-region closure can run away.
- Directional `need_before` / `need_after` is a better runtime control signal than one scalar completeness score.
- Final utility should be judged after semantic closure.
- Obligation geometry can recover some missed secondary modes, but cannot recover a genuine Phase0 false negative.
- False-positive obligations are expensive because they multiply seed attempts and closure calls.
- Identical semantic states must share System One decisions in causal policy A/B tests.
- Quality must always be reported together with calls, tokens, wall time, and source-read cost.

## Current methodological frontier

R18 showed that independent model variance can create fake policy wins around hard thresholds even when two policies have identical geometry and source state.

R19 therefore focuses on counterfactual-safe evaluation through a shared semantic-decision cache. Logical standalone policy cost and physical cached execution cost are reported separately.

## Current engineering priorities

### Evidence localization

- finish counterfactual-safe policy comparison;
- reduce closure calls through batching;
- reduce tokens through boundary-window context;
- stop Phase0 based on frontier/obligation stability;
- improve genuine Phase0 false-negative recovery.

### File discovery

- build a current repository-level System Two/reference benchmark;
- define relevant-file coverage/precision metrics;
- build a canonical progressive-disclosure runtime;
- make file-level false positives visible as downstream localization cost.

## Benchmark stance

The current benchmark corpus is intentionally small and version-pinned. R08/R15-R17 cases are mechanism data; R18 cases are fresh holdouts. Broader repositories, languages, and task classes are still required before generalization claims.

See:

- `../README.md`
- `benchmark.md`
- `research-path.md`
- `domains/file-discovery.md`
- `domains/evidence-localization.md`
- `research/README.md`