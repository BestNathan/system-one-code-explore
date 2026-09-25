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

## Milestone 3 — File-discovery benchmark and runtime

File discovery is currently the less mature problem domain.

Build a repository-level benchmark with:

- multiple relevant files per task;
- primary/supporting/incidental reference labels;
- misleading names and same-symbol distractors;
- test/implementation/configuration splits;
- repository-level System Two reference or carefully frozen human/reference sets.

Then build a canonical progressive-disclosure runtime with file-level relevance, uncertainty, and coverage obligations.

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
4. Start the canonical file-discovery benchmark/runtime.
5. Only then expand end-to-end datasets.

## Evaluation rule

Every promoted method must report both quality and cost. Do not promote a method solely because it improves recall if it materially worsens calls, tokens, latency, or source exposure without a justified tradeoff.

See:

- `docs/benchmark.md`
- `docs/project-structure.md`
- `docs/domains/file-discovery.md`
- `docs/domains/evidence-localization.md`
- `docs/research-path.md`