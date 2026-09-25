# Roadmap

## Project objective

Determine whether a constrained System One harness can replace or approximate System Two for code localization: first finding the relevant files, then finding concrete source evidence inside those files, while materially reducing calls, tokens, and latency.

The project has two primary problem domains:

1. **File discovery** — repository -> relevant files.
2. **Evidence localization** — candidate file -> concrete, semantically complete evidence spans.

Benchmark methodology and cost/runtime are cross-cutting.

## Milestone 1 — Converged research contracts

Status: current convergence step.

- stable Task / Usage / RelevantFile / EvidenceAnchor / EvidenceSpan / LocalizationResult concepts;
- one benchmark contract for quality + cost;
- chronological Rxx history separated from the conceptual architecture;
- counterfactual-safe policy comparison for identical semantic states.

## Milestone 2 — Canonical evidence-localization runtime

Retain the strongest current invariants:

- sparse observations and replaceable posterior reconstruction;
- separate relevance and epistemic uncertainty;
- durable coverage obligations;
- anchor-local directional closure;
- final utility after closure;
- shared semantic-decision cache for A/B.

Before calling this domain stable, reduce cost tails:

- batch directional closure across anchors;
- use boundary-window context rather than resending the full growing anchor;
- add adaptive Phase0 stopping based on frontier/obligation stability;
- report p50/max calls, tokens, and wall time in every canonical run.

## Milestone 3 — File Discovery V1

Status: **mechanism converged**.

Canonical V1 mechanically enumerates supported file metadata and independently
Noul-scores every file. Semantic directory pruning, top-k truncation, and model
global Stop are rejected.

The frozen six-case gate recovered 12/12 primary targets across two repeats with
a score>=0.65 plus top-1% relative recall guard.

Current work is no longer architecture discovery. It is:

- reduce the ~18 calls / ~212k input tokens per 1,096-file task without changing
  logical all-file coverage;
- build complete primary/supporting/incidental file references;
- validate on multiple repositories/languages and true multi-file tasks;
- study deterministic/cached pre-indexing only if it is recall-safe.

## Milestone 4 — End-to-end localization

Compose:

```text
File Discovery
    -> RelevantFile[]
    -> Evidence Localization per file
    -> EvidenceSpan[]
    -> LocalizationResult
```

End-to-end evaluation must include the cost induced by file false positives. A file-discovery policy is not cheap if it promotes many files into expensive evidence localization.

## Milestone 5 — Broader generalization

Expand beyond one repository:

- multiple repositories;
- multiple languages;
- small and very large files;
- feature work, bug investigation, refactoring, protocol tracing, tests, configuration, and cross-layer tasks.

Freeze candidates before hidden evaluation and keep diagnostic versus fresh-generalization evidence separate.

## Milestone 6 — System One / System Two escalation

The long-term result does not need to be 'System One only'.

Study an escalation policy:

```text
System One handles cheap bounded localization
        |
        +--> confident / covered -> finish
        |
        +--> unresolved / high-risk -> System Two escalation
```

The objective is to identify which localization work can move reliably to System One and when a stronger model is economically justified.

## Current research priorities

1. Finish R19 counterfactual-safe comparison methodology.
2. Standardize Usage and wall-time accounting across all experiments.
3. Optimize evidence-localization calls/tokens without changing semantics.
4. Optimize and broaden the converged File Discovery V1 benchmark.
5. Compose File Discovery V1 with Evidence Localization, then expand end-to-end datasets.

## Evaluation rule

Every promoted method must report both quality and cost. Do not promote a method solely because it improves recall if it materially worsens calls, tokens, latency, or source exposure without a justified tradeoff.

See:

- `docs/benchmark.md`
- `docs/project-structure.md`
- `docs/domains/file-discovery.md`
- `docs/domains/evidence-localization.md`
- `docs/research-path.md`