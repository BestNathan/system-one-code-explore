# Architecture

## Scope

The project studies code localization with System One under a Harness that owns state, legal actions, effects, progressive disclosure, durability, budgets, caching, and evaluation.

The architecture has two independent localization domains.

```text
Repository + Task
      |
      v
+--------------------+
| File Discovery     |
| repository-level   |
+---------+----------+
          | RelevantFile[]
          v
+--------------------+
| Evidence           |
| Localization       |
| file-level         |
+---------+----------+
          | EvidenceSpan[]
          v
 LocalizationResult
```

System Two is used for stronger reference/evaluation and optional future escalation. It is not assumed to be ground truth.

## Domain 1 — File discovery

State contains progressively disclosed repository structure and metadata.

The Harness owns traversal legality and visible actions. System One decides among bounded semantic actions such as expanding a directory, promoting a file, or following a grounded relation.

Output is a set of relevant files plus provenance and unresolved state.

## Domain 2 — Evidence localization

Within one file:

```text
sparse observations
    -> posterior relevance / uncertainty
    -> durable coverage obligations
    -> representative seed
    -> evidence anchor
    -> need_before / need_after closure
    -> post-closure utility
    -> retained EvidenceSpan
```

## Core invariants

### Harness owns mechanics

The Harness owns:

- state transitions;
- legal action generation;
- effects;
- source/repository access;
- budgets and safety caps;
- durability/replay;
- cache identity;
- cost accounting.

It should not silently replace model semantics with hidden AST/LSP reasoning unless that is the explicit experiment variable.

### System One owns bounded semantic judgments

System One is used as a fast policy/value function over concrete disclosed choices, not as an unconstrained ReAct agent.

### Progressive disclosure

Repository trees, full files, symbol graphs, and action spaces should not be injected eagerly. New state/actions should be revealed by real observations.

### Relevance != uncertainty

File/source relevance and epistemic need-to-observe are different state variables.

### Coverage is durable

Finding some useful evidence must not erase unresolved independent file/source regions.

### Navigation != final evidence

A read can be useful to navigate and still be excluded from the final evidence set.

### Closure is local and directional

Evidence completion is tied to one anchor/local construct. Runtime control uses `need_before` and `need_after`, not one abstract completeness score.

### Utility comes after closure

A truncated fragment must not be rejected solely because its meaningful continuation is not visible yet.

### Counterfactual A/B shares semantic decisions

If two policies produce the same semantic request, they must receive the same cached System One response during causal policy comparison.

### Cost is part of behavior

Calls, tokens, wall time, source reads, and cache behavior are first-class outputs.

## Durable interfaces

The target stable interfaces are documented in `docs/project-structure.md`: Task, Usage, RelevantFile, EvidenceAnchor, EvidenceSpan, and LocalizationResult.

Experimental Rxx runtimes may be replaced behind those concepts.

## Evaluation

See `docs/benchmark.md` for the quality-cost contract and System Two reference methodology.

## Historical note

Earlier architecture documents and modules used a two-phase directory/file Noul stage followed by independent range runtimes. Those experiments remain valuable historical evidence, but they are not the current conceptual architecture.