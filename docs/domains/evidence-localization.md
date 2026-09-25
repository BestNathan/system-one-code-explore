# Problem Domain — Evidence Localization

## Goal

Given one candidate file and an engineering task, identify concrete source spans that can serve as evidence for that task.

Conceptually:

```text
EvidenceSpan {
  path
  start_line
  end_line
  role
  utility
  provenance
}
```

The result must expose enough contiguous source to understand the relevant local behavior, not merely a keyword, function name, or half of a branch.

## Research question

> Can System One recover task-relevant, semantically usable source evidence from sparse observations without requiring System Two to read the whole file?

## Current four-layer model

### 1. Sparse sensing / Phase0

Read small source probes and preserve them as durable observations. The harness owns legal probe geometry; System One performs bounded local relevance/policy judgments.

### 2. Whole-file state reconstruction

Reconstruct file-length fields such as:

```text
relevance[N]
uncertainty[N]
observed[N]
```

A major conclusion is that relevance interpolation and epistemic need-to-observe are different quantities. A smooth posterior can still be unjustifiably confident in unread space.

### 3. Coverage obligations

Convert the probability state into durable obligations for unresolved high-value regions.

Key invariant:

> Finding some useful evidence must not silently delete another independent unresolved relevance region.

R15 established hard obligations. R16/R17 explored q75 components, prominence, narrow secondary peaks, and their cost/precision tradeoffs.

Geometry cannot recover a genuine Phase0 false negative if the relevance topology never exposes that region.

### 4. Anchor-local semantic closure

A selected seed becomes an evidence anchor. Closure is directional:

```text
need_before(anchor)
need_after(anchor)
```

The anchor expands only to complete the same local construct: function body, branch, match arm, loop, state transition, error path, or required local setup/follow-up.

Final task utility is judged after directional closure.

## Why relevance is not enough

A 32-line fragment can be highly relevant and still be invalid final evidence because the function body, `if` branch, transition outcome, or error behavior continues outside the range.

Evidence localization therefore separates:

1. coverage of high-value regions;
2. task relevance/utility;
3. semantic completeness of the retained local construct.

These must not be collapsed into one probability.

## Strongest retained invariants

- source reads are observations, not eager context;
- posterior reconstruction is replaceable and recomputable from durable observations;
- relevance and epistemic uncertainty are separate;
- coverage is durable Harness state;
- Choice is relative policy semantics, not independent read-worthiness;
- independent Noul is appropriate when multiple actions may all be useful;
- closure is anchor-local and directional;
- utility comes after closure;
- navigation observations and final evidence are separate;
- identical semantic states share decisions in counterfactual A/B tests;
- cost is measured alongside quality.

## Main open problems

### Phase0 false negatives

Some important regions are not global peaks or even local peaks. Candidate signals include unresolved relevance mass, uncertainty, observation distance, posterior disagreement, slopes/shoulders, and spatial novelty.

### Closure cost

R15-style closure has expensive tails when false-positive obligations try many seeds and each seed requires several directional rounds.

Promising optimizations:

- batch closure decisions across independent anchors;
- transmit boundary windows instead of the full growing anchor every round;
- cache semantic states;
- adaptively stop Phase0 when frontier/obligation state stabilizes;
- prioritize obligations by expected quality gain per call/token.

### Evidence roles

Final spans should eventually distinguish primary implementation evidence, supporting context, tests, contracts/configuration, and edge/counter evidence.

## Evaluation

Quality: high-region recall, high-line recall/precision, retained relevance, relevance-mass recall, missed independent modes, semantic truncation, redundancy.

Cost: model calls, input/output tokens, wall time, source lines read, closure depth, seed attempts, cache hits/misses.

See [Benchmark contract](../benchmark.md).

## Historical mapping

- R01–R05: bounded range exploration and sparse sensing.
- R06–R09: probability frontier, posterior reconstruction, uncertainty.
- R10–R14: evidence selection and semantic closure.
- R15–R17: obligations and obligation geometry.
- R18–R19: fresh validation and counterfactual-safe comparison.

The Rxx sequence is research history. The four-layer model above is the problem-oriented architecture.