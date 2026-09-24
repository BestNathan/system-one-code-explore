# R13 — Multi-Objective Evidence Acquisition with Semantic Closure

## Status

Current research iteration.

## Motivation

R12 fixed the action semantics by replacing categorical Choice with independent
Noul scores, but it still compressed several different objectives into one
question:

> does reading this tile now add new material evidence?

The canonical R12 run showed a characteristic failure:

1. first-round selections were often excellent;
2. after those fragments were materialized, all remaining marginal-evidence
   scores collapsed;
3. the runtime stopped even though the hidden full-file reference still
   contained high-value regions.

This suggests the model was allowed to equate "I already have useful evidence"
with "the file is sufficiently covered".

A second problem is fragment completeness. A 32-line tile can contain a highly
relevant function signature, if-branch, match arm, state transition, or call
site while cutting off the rest of the semantic unit. Such a fragment can be
both relevant and useful while still being insufficient evidence.

R13 separates these concerns.

## Three independent objectives

### 1. Frontier coverage

Question:

> Does this unread range represent an important unresolved high-value part of
> the Phase0 probability frontier that should be materially inspected?

This score must not collapse simply because useful evidence was found
elsewhere.

### 2. Task utility

Question:

> Is this range likely to contain source that materially helps solve the task?

This is still a Phase0-prior judgment before source is disclosed.

### 3. Semantic completeness

After source is materialized, ask:

> Is the visible relevant fragment complete enough to understand the code unit
> or behavior it reveals?

Relevance and completeness are explicitly different.

Examples of incomplete evidence:

- only a function signature is visible but its body continues outside the
  range;
- an if-condition is visible but the branch body or else path is cut off;
- only one half of a match arm/state transition is visible;
- an error path begins but its consequence is outside the range;
- a call site is visible but the locally necessary setup or follow-up is
  truncated;
- the visible fragment mentions the relevant symbol but does not expose the
  behavior that makes it relevant.

## Runtime

```text
Phase0 relevance frontier
        |
        v
equal 32-line unread actions
        |
        v
+-------------------------------+
| independent Noul objectives   |
|                               |
| frontier_coverage(tile)       |
| task_utility(tile)            |
+-------------------------------+
        |
        v
read every tile where
coverage >= threshold
OR utility >= threshold
        |
        v
merge adjacent materialized tiles into evidence regions
        |
        v
for each useful region:
    System One utility(fragment)
    System One completeness(fragment)
    System One need_before(fragment)
    System One need_after(fragment)
        |
        v
if useful AND incomplete:
    read qualifying adjacent tile(s)
        |
        v
merge + reassess
        |
        v
repeat global acquisition and closure
        |
        v
stop only when:
- no remaining tile has coverage/utility obligation, AND
- no useful materialized region requests semantic expansion
```

There is no fixed snippet count.

## Why this should resist the R12 collapse

R12 used one marginal-evidence question. Once evidence existed, the model could
legitimately decide that unread ranges were redundant.

R13 makes frontier coverage independent:

> even if the current answer feels sufficient, an unresolved high-value
> frontier region can still require inspection.

This separates "answer sufficiency" from "coverage obligation".

Semantic closure is also independent:

> a fragment can be highly useful and still require adjacent source because it
> is structurally or semantically truncated.

## Action generation

The harness remains syntax-agnostic.

It does not parse Rust, identify functions, or infer AST boundaries.

For semantic closure it only offers immediate unread adjacency:

- `expand_before`;
- `expand_after`.

System One decides whether either direction is required.

Repeated closure rounds can therefore grow a region from:

```text
32 lines
 -> 64 lines
 -> 96 lines
 -> ...
```

until the relevant semantic unit is sufficiently visible.

This preserves the research question: can System One discover semantic
boundaries from source and local state rather than receiving parser-generated
function boundaries?

## Initial thresholds

For the first run:

- tile width: 32 lines;
- frontier coverage threshold: 0.65;
- task utility threshold: 0.65;
- completeness threshold: 0.70;
- adjacent expansion threshold: 0.60;
- maximum rounds: 12 safety cap.

These values are initial frozen parameters, not fitted against R13 outcomes.

## Evaluation

### Frontier objective

- Phase0 high-frontier coverage;
- hidden CC high-line recall;
- best hidden high-value range left unread.

### Utility objective

- mean CC relevance of materialized source;
- high-line precision;
- weighted relevance-mass recall.

### Completeness objective

- number of closure expansion tiles;
- final contiguous evidence-region count;
- final region lengths;
- final System One completeness score;
- number of final regions still below completeness threshold.

System One completeness is not sufficient as ground truth. A later hidden
System2 audit must check whether final regions that System One calls complete
are actually complete when viewed with larger/full-file context.

### Cost

- materialized source lines;
- model calls/tokens;
- closure expansion cost;
- rounds.

## Hypotheses

H1: separating frontier coverage from marginal evidence reduces the R12
second-round collapse.

H2: semantic closure turns high-value but truncated 32-line hits into fewer,
larger, more interpretable evidence regions.

H3: closure increases source cost but improves downstream usefulness more than
simply lowering the global acquisition threshold.

H4: if high-frontier coverage still collapses, the problem is upstream
calibration of Phase0 or the coverage prompt, not semantic closure.
