# System One Localization Algorithms

This topic captures two experimental alternatives to the current per-file range-runtime baseline.

Both algorithms remain language-agnostic. Neither depends on AST, LSP, symbol extraction, imports, or semantic parsing.

## Algorithm A — Explore-Guided Evidence Filtering

### Goal

Keep the existing FileRuntime mechanics unchanged while changing the semantic question asked of System One.

The baseline asks whether a read is useful for localization. Algorithm A asks a stricter question:

> Will this read add NEW MATERIAL EVIDENCE needed by the downstream task?

Topical relevance is not enough.

### Runtime

The state machine and action-space generator are unchanged:

```text
FileState
  -> head/middle/tail | expand | jump | StopFile
  -> Stop/Continue Choice
  -> ReadRange Noul utility
  -> effects
  -> observations
  -> repeat
```

Only decision semantics change.

### Material evidence

High-value evidence should add a distinct fact about one or more of:

```text
implementation details
control flow
state transitions
dependencies and contracts
edge cases
invariants and constraints
```

Evidence should score lower when it is:

```text
merely topically related
another example of an already established fact
wrapper/plumbing with no new behavior
logging/debug/status code with no new material fact
confirmatory rather than additive
```

### Stop semantics

Stop when the current observations already form a minimal but sufficient representative evidence set.

Continue only to close a concrete material evidence gap.

### Final filtering

Observed ranges are re-scored after navigation with the same evidence-first rubric. The final result therefore attempts to minimize redundancy instead of retaining every relevant range.

### Implementation

```text
research/code-locator/src/system_one_evidence_guided_runtime.py
```

## Algorithm B — Adaptive Semantic Zoom Search

### Goal

Replace sequential coverage-oriented navigation with coarse-to-fine, multi-hotspot range refinement.

The file is first sampled across its whole length. System One then allocates refinement budget to the most promising regions while the Harness reserves a small exploration budget for other large unexplored regions.

### Initial stratified probes

Default prototype:

```text
coarse regions = 16
probe size      = 32 lines
```

The file is divided into 16 contiguous strata. A midpoint probe is read from each region.

No content analysis is used to create the strata.

### Region competition

At every round, System One receives the current region frontier and probe observations and answers one Choice question:

> Which region most deserves finer-grained inspection next?

The returned Choice probabilities are used as a distribution over the whole frontier.

### Beam zoom

Default prototype:

```text
beam width = 3
target cumulative probability mass = 0.80
```

Regions are sorted by Choice probability.

The exploitation beam keeps up to three regions, stopping early once cumulative probability reaches 0.80.

This preserves multiple simultaneous hotspots instead of winner-take-all refinement.

### Exploration budget

Default:

```text
exploration slots = 1
```

In addition to the probability beam, one region outside the beam is selected mechanically for exploration.

The exploration selector does not inspect content. It prefers the largest still-coarse range outside the beam.

With a three-region exploitation beam plus one exploration region, the intended budget is approximately:

```text
75% exploit
25% explore
```

### Refinement

A selected range larger than the target resolution is split in half.

Each child receives a midpoint probe.

```text
parent range
   -> left child probe
   -> right child probe
```

This repeats independently across multiple hotspots.

Default final target:

```text
target region size = 40 lines
```

### Convergence

The current v0 stops refinement when the probability frontier has converged:

```text
no region with probability >= 0.05
remains larger than 40 lines

AND

the dominant root-region set has remained stable
for at least 2 rounds
```

There is also an 8-round safety budget.

These are experimental Harness convergence rules for Algorithm B, not part of the baseline FileRuntime StopFile policy.

### Final evidence

All actual probes are grounded source observations.

After zooming ends, probes are independently Noul-scored for material evidence. Only evidence above the result threshold survives.

### Implementation

```text
research/code-locator/src/system_one_adaptive_zoom.py
```

## Comparison intent

The two algorithms test different hypotheses:

```text
Algorithm A
  same search mechanics
  better semantic objective
  question:
    can evidence-aware prompting reduce redundant reads/results?

Algorithm B
  different search mechanics
  coarse-to-fine probability-guided search
  question:
    can multi-resolution zoom find sparse hotspots without full traversal?
```

They should not be merged into one algorithm before measuring them independently.

## Manual experiment workflow

```text
.github/workflows/system-one-localization-algorithms.yml
```

The workflow runs both algorithms against the same repository, revision, task, and System One model, producing separate artifacts:

```text
system-one-evidence-guided-<run>
system-one-adaptive-zoom-<run>
```

Each artifact contains:

```text
subject-sha.txt
trace.jsonl
result.json
summary.md
```

Useful comparison dimensions include:

```text
model calls
input/output tokens
elapsed time
reads or probes
file count
evidence-region count
evidence redundancy
evidence coverage
downstream usefulness
```

The last three dimensions should be assessed by an independent evaluator rather than by treating either algorithm as ground truth.


## Real validation — 2026-09-23

Both algorithms were validated against the same subject revision and task:

~~~text
BestNathan/nession@97b9d2b49c5137064e910fc180aabc01cfb1021f

Help me optimize the websocket connection implementation
~~~

### Algorithm A

Run:

~~~text
35882424922
~~~

Observed metrics:

~~~text
Phase-1 files        17
reads               135

model stops           1
space exhausted      15
budget exhausted      1

valuable files        8
evidence regions     32

model calls         164
input tokens   1,830,611
output tokens      20,532
elapsed           40.840s
~~~

The evidence-first rubric materially reduced the FINAL retained evidence set,
but it did not yet reduce navigation cost. Large files still tended to explore
until coverage exhaustion.

This supports a useful separation:

~~~text
Evidence filtering quality
  !=
Search efficiency
~~~

Algorithm A currently improves the former more than the latter.

### Algorithm B

Run:

~~~text
35881894374
~~~

Observed metrics:

~~~text
Phase-1 files           17
probe observations     417

frontier converged      12
round budget exhausted   5

valuable files          11
evidence regions       194

model calls            184
input tokens     1,019,712
output tokens        33,605
elapsed             43.360s
~~~

Adaptive Zoom successfully exercised the intended coarse-to-fine loop: most
files terminated through probability-frontier convergence rather than complete
file traversal.

However, v0 currently overproduces probe observations and final evidence. The
next B iteration should separate:

~~~text
search probes
  = temporary observations used for routing refinement

final evidence
  = a much smaller distilled subset returned downstream
~~~

### Early comparison

These runs are stochastic System One observations, not a controlled accuracy
test, but they expose complementary behavior:

~~~text
A:
  coverage-style search
  aggressive evidence filtering
  small final result
  navigation cost still high

B:
  probability-guided multi-resolution search
  avoids exhaustive line coverage
  many more small probes
  final evidence still too broad
~~~

The two algorithms should therefore remain separate experiments for now.
