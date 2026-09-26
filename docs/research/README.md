# Research Log

This directory is the canonical chronological history for **System One Code Explore**.

The project is intentionally experimental. Implementations may be replaced; the durable artifact is the research path: question, hypothesis, controlled setup, evidence, result, rejected ideas, and next direction.

For the problem-oriented view, read `../research-path.md` first.

## Project question

> Can a System One harness locate task-relevant files and concrete source evidence with quality close enough to a stronger System Two reference, while using materially fewer calls, tokens, and less wall time?

The research is organized conceptually around two problem domains:

1. file discovery;
2. evidence localization inside a file.

Rxx IDs are chronological experiments, not the architecture.

## Research path

| ID | Research | Status | Main conclusion |
| --- | --- | --- | --- |
| R01 | [Range runtime baseline](2026-09-24-r01-range-runtime-baseline.md) | historical | System One can drive bounded reads, but geometry and evidence shaping dominate quality. |
| R02 | [Adaptive relevance frontier](2026-09-24-r02-adaptive-relevance-frontier.md) | superseded | Coarse region scores are the wrong state abstraction. |
| R03 | [Full-read System 2 reference](2026-09-24-r03-full-read-system2-reference.md) | active benchmark | Use a stronger full-read relevance field as reference, not ground truth. |
| R04 | [Choice and evidence closure](2026-09-24-r04-choice-and-evidence-closure.md) | partially retained | Choice suits relative policy decisions; isolated fine-fragment keep/drop is insufficient. |
| R05 | [Sparse Phase0](2026-09-24-r05-sparse-phase0.md) | superseded | Sparse sensing is viable; collapsing it into a few coarse scores loses the global shape. |
| R06 | [Whole-file probability frontier](2026-09-24-r06-whole-file-probability-frontier.md) | retained baseline | Represent relevance/uncertainty over the whole file. |
| R07 | [Posterior reconstruction](2026-09-24-r07-posterior-reconstruction.md) | completed | Path-independent reconstruction preserves sparse local relevance better than sequential propagation. |
| R08 | [Online posterior generalization](2026-09-24-r08-online-posterior-generalization.md) | completed | Better posterior reconstruction changes the online path, but support-derived uncertainty can fail search generalization. |
| R09 | [Uncertainty calibration/search policy](2026-09-24-r09-uncertainty-calibration-search-policy.md) | completed diagnosis | Relevance interpolation and epistemic need-to-observe must be separated. |
| R10 | [Final evidence quality](2026-09-25-r10-final-evidence-quality.md) | completed baseline | Phase0 contains useful evidence, but fixed top-N evidence is artificial and retains false positives. |
| R11 | [System One prompt calibration](2026-09-25-r11-system-one-prompt-calibration.md) | completed calibration line | Prompt/calibration effects matter, but label construction and hard negatives must be controlled. |
| R12 | [Dynamic evidence acquisition](2026-09-25-r12-dynamic-evidence-acquisition.md) | completed diagnosis | Independent Noul multi-select removes fixed evidence count; one marginal-evidence score causes premature stopping. |
| R13 | [Multi-objective semantic closure](2026-09-25-r13-multi-objective-semantic-closure.md) | completed diagnosis | Separating coverage/utility/completeness improves recall, but merged-region closure runs away. |
| R14 | [Anchor-centered closure](2026-09-25-r14-anchor-semantic-closure.md) | completed diagnosis | Anchor-local closure fixes giant regions; scalar completeness and pre-closure utility are poor control signals. |
| R15 | [Frontier obligations + directional closure](2026-09-25-r15-frontier-obligations-directional-closure.md) | completed diagnosis | Coverage should be durable Harness state; close anchors with before/after and score utility after closure. |
| R16 | [Frontier obligation geometry](2026-09-25-r16-frontier-obligation-geometry.md) | completed diagnosis | Prominence finds some secondary modes; wide basins are too broad and narrow peaks recover only a subset of misses. |
| R17 | [Hybrid obligations end-to-end](2026-09-25-r17-hybrid-obligations-end-to-end.md) | completed mechanism test | Narrow persistent secondary peaks can become retained evidence, but add false-positive/cost overhead. |
| R18 | [Fresh hybrid generalization](2026-09-25-r18-fresh-hybrid-generalization.md) | completed fresh validation | Raw gains were confounded by independent System One decision noise; fresh secondary obligations did not show attributable retained-evidence gain. |
| R19 | [Counterfactual-safe geometry A/B](2026-09-25-r19-counterfactual-safe-geometry-ab.md) | current methodology | Identical semantic states must share cached System One decisions; separate logical policy cost from physical cached execution cost. |

## File Discovery scaling follow-up

- [Large-repository scaling diagnosis](file-discovery-large-repo-scaling-diagnosis.md) — observed all-file scoring and corrected System2 cost interpretation.
- [Algorithmic reduction and concurrent requests](2026-09-25-file-discovery-algorithm-scaling-plan.md) — uncapped research design for retrieval, adaptive routing, and independent-request concurrency.
- [Three-repository scaling results](2026-09-26-file-discovery-scaling-results.md) — four concurrent requests reduced full-scoring latency by 3.44–4.02×; lexical retrieval was cheapest but missed 2/9 targets, hierarchy retained 8/9 while adding substantial directory cost, and same-directory rescue was rejected.
- [Semantic path and root-safe routing V2](2026-09-26-file-discovery-semantic-routing-v2-results.md) — semantic aliases recovered 9/9 targets into the candidate set; final selection remained 8/9 because candidate reduction incorrectly shrank the relative recall guard. Hierarchy and adaptive union were rejected on directory/token cost.

## Current conceptual architecture

```text
Repository + Task
    |
    +--> File Discovery
    |       -> RelevantFile[]
    |
    +--> Evidence Localization per file
            -> sparse observations
            -> relevance / uncertainty state
            -> coverage obligations
            -> evidence anchors
            -> directional closure
            -> final EvidenceSpan[]
```

System Two remains the stronger reference and possible escalation path.

## Working rule

Every meaningful research iteration should record:

1. Question;
2. Hypothesis;
3. Design / controlled variable;
4. Frozen setup;
5. Quality metrics;
6. Calls, tokens, wall time, and source/metadata cost;
7. Evidence and repeated-run/counterfactual controls;
8. Result;
9. Interpretation and rejected ideas;
10. Next variable to isolate.

Raw benchmark details live under `docs/experiments/`; durable conclusions belong here. Important aggregate/reference artifacts should be pinned under `fixtures/research/` when practical.

## Methodological guardrails

- Do not call the System Two reference ground truth.
- Do not tune on a hidden reference and then claim generalization on it.
- Keep repeatedly inspected mechanism cases separate from fresh holdouts.
- In policy A/B, identical semantic states must share decisions.
- Report localization quality together with model/source cost.
- Preserve historical algorithms as regression evidence when removal would make prior results hard to reproduce.

## Repository workflow

Research changes may be committed directly to `main`; unstable implementation churn is acceptable. The durable interfaces and benchmark contract should become more stable over time even while experimental algorithms change.

See:

- `../benchmark.md`
- `../research-path.md`
- `../domains/file-discovery.md`
- `../domains/evidence-localization.md`
- `../../ROADMAP.md`
