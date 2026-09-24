# Relevance Frontier v1c — Single-file controlled experiment

Date: 2026-09-24

## Goal

Repeat the same task on one representative file rather than the whole repository:

- query: Help me optimize the websocket connection implementation
- subject: BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df
- file: crates/nession-agent/src/server/websocket.rs
- file size: 3,030 lines
- model: jev-latest

This file is more representative than the previous server/handler.rs trial because it is directly responsible for the agent WebSocket server and was independently retained by both System One and Claude in the earlier repository-level benchmark.

## Fresh parameter set

The new v1c preset is intentionally between v1 and the aggressive v1b trial:

{
  "max_rounds": 10,
  "max_actions_per_round": 2,
  "probe_lines": 112,
  "target_region_lines": 48,
  "final_window_lines": 32,
  "refine_threshold": 0.72,
  "candidate_threshold": 0.55,
  "gradient_threshold": 0.15,
  "volatility_threshold": 0.10,
  "stable_delta": 0.06,
  "stable_rounds": 2,
  "max_frontier_leaves": 24,
  "final_max_candidates": 24
}

Range reference remained:

{
  "window_lines": 140,
  "parallel_threshold": 0.65,
  "max_jumps": 2,
  "max_file_epochs": 32
}

Experiment workflow: 35952482145.

## Cost

| Metric | Range Runtime | Frontier v1c |
| --- | ---: | ---: |
| Elapsed | 5.43s | 6.13s |
| Model calls | 10 | 11 |
| Input tokens | 97,857 | 151,321 |
| Output tokens | 1,031 | 1,840 |
| Source reads | 16 | 20 |
| Source coverage | 73.9% | 48.5% |
| Frontier coverage | — | 81.3% |
| Evidence regions | 7 | 12 |
| Termination | model_stop | round_budget_exhausted |

Relative to Range, v1c used:

- 1.13x latency;
- 1.25x source probes;
- 1.55x input tokens;
- 1.78x output tokens.

The important result is the coverage separation:

> Frontier v1c established an 81.3% observed relevance frontier while literally reading only 48.5% of the file.

This is the strongest single-file evidence so far for the intended distinction between belief/frontier coverage and source coverage.

## Action behavior

20 probes were executed:

missing_frontier: 10
refine_high: 7
volatility_revisit: 2
resolve_gradient: 1

The runtime did not merely binary-zoom every round. High-score regions were refined, a volatile region was revisited, and a parent/child gradient produced a dedicated missing-sibling action.

However, there is a significant policy issue:

With only two actions allowed per round, the runtime did not finish sampling all initial coarse regions before beginning refinement. It moved from coarse regions c1..c4 into refinement while later coarse regions were still not directly observed.

This means max_actions_per_round=2 is currently too restrictive for a six-region initial frontier unless the action generator explicitly reserves capacity for undisclosed coarse regions.

## Evidence behavior

Range retained:

1-140
281-420
582-721
722-861
862-1001
1305-1444
1445-1584

Frontier v1c retained:

444-474
475-506
507-538
539-569
570-601
602-633
634-664
665-696
697-727
728-758
825-852
881-908

The two outputs are complementary rather than equivalent.

Frontier evidence overlaps:

- 23.8% of Range evidence lines;
- 62.8% of Frontier evidence lines are covered by Range.

The frontier found a fine-grained cluster around the P2P request/session/broadcast path and resize/subscriber handling, while Range also reached the connection lifecycle around:

- WebSocket upgrade;
- split sink/stream;
- incoming message loop;
- Ping/Pong;
- disconnect cleanup.

That latter connection-lifecycle area is important for the stated task and is a concrete omission in this v1c run.

## What this experiment validates

1. The frontier/source-coverage separation is real.

   81.3% frontier coverage with 48.5% source coverage is substantially different from mechanically reading most of the file.

2. Frontier refinement is producing meaningful non-geometric actions.

   refine_high, volatility_revisit, and resolve_gradient all executed in the real trace.

3. The runtime can produce more granular evidence with fewer source lines.

   Frontier emitted 12 fine regions versus Range's 7 larger ranges.

4. The remaining cost is state transmission, not model-call count.

   11 calls versus 10 is negligible; 151k versus 98k input tokens is the material overhead.

## What this experiment exposes

### 1. Coarse coverage needs a hard invariant

The intended algorithm says the first stage should establish a sparse view covering the whole file.

That should be a runtime invariant rather than a side effect of the generic action scorer.

For a six-region file:

round 1: c1 c2 c3
round 2: c4 c5 c6

or an equivalent scheduling policy should happen before deep refinement.

### 2. Frontier v1 still does not have a true information-gain stop

This run terminated by round_budget_exhausted, not frontier_stable.

So the ten-round cap is still acting as the practical stopping mechanism.

### 3. Final evidence can become too locally concentrated

The frontier correctly became selective, but it concentrated on one local region and failed to recover the later connection lifecycle section.

This is not a reason to abandon the frontier. It indicates that the frontier scheduler needs an explicit global missing-frontier reserve so local refinement cannot consume the entire exploration budget.

## Current interpretation

This run is a stronger validation of the research direction than the earlier whole-repository comparison.

The important property is not that Frontier beats Range on the blind score. The important property is:

broad relevance frontier
        ↓
sparse source observations
        ↓
progressive refinement
        ↓
fine-grained evidence

That behavior is now visible on a 3,030-line real WebSocket implementation.

The next experiment should therefore not increase model intelligence or simply increase the round budget.

It should modify the harness policy:

1. reserve coarse-frontier actions until all initial regions are sampled;
2. only then allow deep refinement to consume the action budget;
3. keep gradient/volatility actions as higher-value overrides;
4. add a global StopFrontier vs BestRemainingAction decision;
5. reduce state transmission to deltas.

## Blind CC evaluation

The blind quality job is running separately against the same frozen subject and query. Its score should be treated as downstream validation only; the navigation metrics above are already sufficient to evaluate the algorithmic behavior of v1c.

## Conclusion

v1c is a useful result.

It does not show that Frontier is already a better replacement for Range. It shows something more specific:

> A relevance frontier can cover most of a large file's search space while reading substantially less source, and the model can use changing relevance, refinement, volatility and gradient signals to decide where to spend the next reads.

The next optimization target is now clear: protect global coarse coverage from local refinement starvation, then make stopping information-gain driven.
