# Adaptive Relevance Frontier v1 — Research Experiment

Date: 2026-09-24

## Research question

Can the adaptive-zoom idea be reformulated around a continuously updated relevance frontier, so that System One uses repeated observations to refine high-value / uncertain intervals instead of mechanically walking a fixed binary zoom tree?

The key hypothesis is:

> A file should be represented as a dynamic relevance field over intervals. New observations change interval scores. The harness should create new read actions from missing coarse frontier coverage, parent/child score gradients, high relevance, and score volatility. Final evidence should be resolved from a finer action space after the frontier has evolved.

The 0..1 value is intentionally called **relevance potential**, not a probability mass. Scores for sibling intervals are not required to sum to one.

## Implementation

New runtime:

`src/system_one_relevance_frontier.py`

Canonical producer algorithm:

`adaptive_relevance_frontier_search_v1`

Frozen implementation commit:

`ce1b802150950d40124d58ea3a824d4e7b896209`

The implementation adds four mechanisms that were absent from adaptive zoom v0.

### 1. Dynamic coarse frontier

Initial region count scales with file size rather than always creating 16 regions:

- <=160 lines: 1 region
- <=600: 2
- <=1500: 3
- <=3500: 4
- larger: 6

This removes most of the fixed startup tax of v0.

### 2. Re-scored frontier

After each read round, every currently observed frontier leaf is scored again by System One using the newly expanded observation state.

Each node keeps:

```text
score_history
score_delta
volatility
parent_score
observed / missing
```

This allows relevance to change when evidence is discovered elsewhere.

### 3. Observation-driven action generation

The harness can disclose:

- `missing_frontier`
- `refine_high`
- `resolve_gradient`
- `volatility_revisit`
- `stochastic_revisit`

At most three source probes execute in one round, and a file runs for at most ten rounds.

### 4. Fine final Choice

After navigation, high-relevance observed probes are partitioned into roughly 32-line final candidates.

System One receives the whole candidate set and answers an explicit `keep | drop` Choice for each fine-grained range.

The final localization result contains only candidates retained by that Choice stage.

## Controlled experiment

Actions run:

`35949459683`

Subject:

`BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`

Task:

`Help me optimize the websocket connection implementation`

System One:

`jev-latest`

Blind evaluator:

Claude Code harness with `deepseek-flash`.

The experiment runs Phase 1 exactly once and gives the exact same 18 candidate files to:

1. the current independent range runtime;
2. adaptive relevance frontier v1.

This controls for stochastic Phase-1 file selection.

## Navigation cost

Shared Phase 1:

- model calls: 2
- input tokens: 84,068
- output tokens: 10,768
- elapsed: 1.227s
- selected files: 18

| Metric | Range runtime | Frontier v1 |
| --- | ---: | ---: |
| Counterfactual total elapsed | **25.765s** | 28.375s |
| Phase-2 elapsed | **24.538s** | 27.148s |
| Model calls incl. shared Phase 1 | **92** | 93 |
| Input tokens incl. shared Phase 1 | **719,575** | 1,041,096 |
| Output tokens incl. shared Phase 1 | **17,392** | 24,624 |
| Reads / probes | **88** | 174 |
| Valuable files | 12 | **14** |
| Final evidence regions | **43** | 76 |

Relative to range, v1 used:

- 1.10x elapsed time;
- 1.01x model calls;
- 1.45x input tokens;
- 1.42x output tokens;
- 1.98x source probes;
- 1.77x retained evidence regions.

This is a large improvement over adaptive zoom v0's execution shape: v1 batches frontier re-scoring so model-call count and latency are now close to range runtime even though it performs more source probes.

## Frontier coverage versus source coverage

The experiment deliberately records two different notions of coverage.

### Frontier coverage

Fraction of the file represented by **observed frontier leaves**.

Unweighted mean across files:

**97.0%**

Line-weighted across the whole 16,312-line candidate corpus:

**85.8%**

### Source coverage

Fraction of actual source lines read by probes.

Unweighted mean across files:

**92.7%**

Line-weighted across the whole candidate corpus:

**59.7%**

The difference is important.

For the large files, the runtime establishes a relevance frontier over substantially more of the file than it literally reads.

Examples:

| File | Frontier coverage | Actual source coverage |
| --- | ---: | ---: |
| server `handler.rs` | 81.3% | 31.3% |
| agent `server/websocket.rs` | 75.0% | 67.4% |
| agent `server_client.rs` | 90.7% | 70.1% |

This is closer to the intended research objective than adaptive zoom v0: maintain a broad belief/frontier state while using sparse observations to refine selected regions.

Small files still dominate the unweighted coverage metric because one probe often reads the whole file, so the line-weighted numbers are the more informative aggregate.

## Action-space behavior

Across the 18 files, v1 executed 174 actions:

| Action | Count |
| --- | ---: |
| `missing_frontier` | 94 |
| `refine_high` | 54 |
| `volatility_revisit` | 10 |
| `stochastic_revisit` | 10 |
| `resolve_gradient` | 6 |

The gradient and volatility mechanisms therefore executed in real model traces; they are not dead code.

### Concrete parent/child gradient example

In `crates/nession-cli/src/client/connection.rs`:

```text
parent 490-652       relevance = 0.76

known child 572-652
  score history      = 0.58 -> 0.37 -> 0.33

difference from parent = 0.18
```

The runtime generated:

```text
resolve_gradient(490-571)
```

The missing sibling then scored approximately:

```text
490-571 = 0.75
```

This is the exact behavior the relevance-frontier hypothesis predicts: a high parent combined with a materially lower known child makes the missing sibling a high-information action.

Other observed gradient resolutions included:

- agent websocket parent `949-1137 = 0.75`, known child `949-1043` falling to `0.36`, causing `1044-1137` to be probed;
- `server_client.rs` parent `2145-2501 = 0.53`, known child `2145-2323 = 0.21`, causing `2324-2501` to be probed;
- server `handler.rs` parent `5740-6886` rising to `0.66`, known child `5740-6313 = 0.19`, causing the missing sibling to be probed.

### Concrete volatility behavior

The same region can change score as observations elsewhere accumulate.

Examples:

```text
agent websocket.rs 1896-2273
0.24 -> 0.23 -> 0.23 -> 0.20 -> 0.30 -> 0.48

server_client.rs 716-1430
0.30 -> 0.27 -> 0.22 -> 0.37

handler.rs 5740-6886
0.35 -> 0.33 -> 0.35 -> 0.35 -> 0.38 -> 0.45 -> 0.66
```

These score movements triggered `volatility_revisit` refinement actions.

This validates the central mechanism: relevance is not frozen at the first read.

## Known intra-file gap recovered

One of the recurring failures of the range runtime was:

`crates/nession-agent/src/connection/server_client.rs:421-538`

The range result in this controlled run again omitted the reconnect-delay application and `connect_once` registration/handshake area.

Frontier v1 retained:

```text
419-448
449-478
479-508
509-537
```

with frontier relevance around `0.81` / `0.65`.

This is strong evidence that the relevance-frontier mechanism can repair an **intra-file localization failure** that geometric range expansion does not reliably recover.

## Canonical result overlap

- Range valuable files: 12
- Frontier v1 valuable files: 14
- Shared: 12
- Union: 14
- File Jaccard: 85.7%
- Range-only: none
- Frontier-only:
  - `web/src/platform/attach/relayServerConnection.ts`
  - `web/src/shared/hooks/useWebSocket.ts`

Evidence overlap:

- 58.1% of range regions overlap frontier evidence;
- 33.0% of range evidence lines overlap frontier evidence;
- 88.2% of frontier regions overlap range evidence;
- 85.5% of frontier evidence lines overlap range evidence.

The asymmetric overlap reflects different output granularity: range often retains large 140-line or whole-file blocks, while frontier finalization emits many approximately 32-line regions.

## Blind downstream-quality evaluation

Both results were anonymized and evaluated in separate fresh sessions against the same frozen repository.

| Dimension | Weight | Range | Frontier v1 |
| --- | ---: | ---: | ---: |
| Completeness | 25% | 7.0 | 7.0 |
| Relevance precision | 15% | **8.5** | 7.5 |
| Evidence grounding | 15% | 8.5 | 8.5 |
| Redundancy efficiency | 10% | 6.0 | 6.0 |
| Downstream actionability | 20% | 6.0 | **7.0** |
| Organization / prioritization | 5% | 3.0 | 3.0 |
| Risk / uncertainty coverage | 10% | 4.0 | 4.0 |
| **Weighted score** | 100% | 66.50 | **67.00** |
| Can proceed | — | yes | yes |

The 0.5-point total difference is much smaller than evaluator variance and should **not** be interpreted as a statistically meaningful win.

The useful signal is dimensional:

- Frontier preserved completeness and grounding.
- Frontier improved downstream actionability in this evaluation.
- Frontier lost relevance precision because it retained more peripheral / redundant evidence.

## What improved compared with adaptive zoom v0

A previous controlled adaptive-zoom-v0 run used the same task and frozen subject but a separately sampled Phase-1 set, so the comparison below is directional rather than a strict A/B.

| Metric | Adaptive zoom v0 | Frontier v1 |
| --- | ---: | ---: |
| Elapsed | 83.2s | **28.4s** |
| Model calls | 187 | **93** |
| Reads / probes | 433 | **174** |
| Input tokens | 1.052M | 1.041M |
| Output tokens | 34.2k | **24.6k** |
| Evidence regions | 206 | **76** |

The architecture change substantially reduces probe explosion and model-call count.

However input tokens barely improve.

Why?

v1 re-sends a relatively rich frontier plus visible observations when it re-scores observed leaves. Fewer, larger stateful requests replace many smaller v0 requests.

Average input per model call is roughly:

- range: 7.8k
- v0 zoom: 5.6k
- frontier v1: 11.2k

So v1's next cost bottleneck is **frontier state transmission**, not request count.

## Failure modes discovered

### 1. No file terminated via `frontier_stable`

Termination:

- `frontier_exhausted`: 15 files
- `round_budget_exhausted`: 3 files
- `frontier_stable`: 0 files

The stability mechanism is therefore not yet doing useful work.

The three large files that reached ten rounds were:

- `crates/nession-agent/src/server/websocket.rs`
- `crates/nession-agent/src/connection/server_client.rs`
- `crates/nession-server/src/server/handler.rs`

### 2. Generic missing-child exploration is too aggressive

The current v1 planner gives every newly created but unread child a generic `missing_frontier` action.

That means:

```text
high parent
  -> split
  -> read one child
  -> the other child is automatically "missing"
  -> eventually read it too
```

This partially defeats the intended gradient logic and explains why source coverage becomes high.

The intended behavior should instead be:

```text
initial coarse regions:
  missing => must sample

refined child regions:
  missing sibling => disclose only when:
    parent/child gradient is high
    OR uncertainty/volatility is high
    OR stochastic exploration selects it
```

This is the clearest algorithmic change for v1.1.

### 3. Final Choice is still insufficiently selective

The final stage generated 175 fine candidates and retained 76: about 43%.

The evaluator still found:

- effectively whole-file WebSocketService evidence;
- whole-file ConnectionManager / terminal-server evidence;
- six adjacent chunks over the agent attach fan-out;
- a trivial `useWebSocket.ts` context accessor.

Binary `keep | drop` decisions are independent enough that they do not impose a global evidence budget.

A better finalizer should use a **budgeted global Choice loop**:

```text
Choose next best evidence region
or
StopEvidence
```

with a small maximum number of retained regions per file / globally.

### 4. Cross-file discovery remains unsolved

Both Range and Frontier v1 still omit:

- `web/src/platform/socket/MessageRouter.ts`
- `crates/nession-server/src/server/command_broker.rs`

The Frontier evaluator also called out:

- the server heartbeat sweeper;
- config heartbeat definitions;
- tests and type definitions.

This confirms the architectural boundary:

> Relevance Frontier improves intra-file belief refinement. It cannot discover a file that is absent from the legal action space.

That remains the job of M1 `FollowFile` / progressive repository-state discovery.

## Research judgment

The experiment supports the **core relevance-frontier hypothesis**, but not the current v1 policy as a finished replacement for range runtime.

What is validated:

1. **Re-scoring after new observations matters.**
   Real score histories move materially as context accumulates.

2. **Parent/child score gradients create useful actions.**
   The mechanism produced the intended missing-sibling probes in real code.

3. **Frontier search can recover an intra-file region that range misses.**
   The `server_client.rs:421-538` gap is the strongest example.

4. **The v0 fixed binary zoom topology was the wrong implementation.**
   Relevance Frontier v1 cuts its latency, calls, probes, and evidence volume substantially.

5. **A broad relevance frontier can be maintained with less than full source reading on large files.**
   Across all candidate lines, v1 had about 85.8% observed-frontier coverage while literally reading about 59.7% of source lines.

What is not yet validated:

1. Frontier v1 is not clearly higher quality than range; the blind score is effectively tied.
2. It still uses 45% more input tokens than range.
3. It reads about twice as many source probes.
4. The stopping rule never reaches `frontier_stable`.
5. Final evidence remains too verbose.
6. It does not solve cross-file omissions.

## Proposed v1.1

Do not change the central idea. Tighten the policy around it.

### A. Separate coarse missing frontier from refined missing children

Only depth-0 coarse regions are mandatory exploration.

A missing child should become legal only through:

- parent/child gradient;
- high uncertainty / volatility;
- high-relevance refinement;
- stochastic exploration.

Expected result: preserve broad file-level frontier coverage while reducing source coverage and probe count.

### B. Incremental frontier re-scoring

Do not re-send the whole frontier state every round.

Re-score:

- newly observed leaves;
- ancestors / siblings affected by a refinement;
- top high-relevance leaves;
- high-volatility leaves.

Use stable observation IDs and state deltas where possible.

Expected result: reduce the current ~11.2k input tokens/model-call.

### C. Explicit marginal-information stop

Add:

```text
StopFrontier
vs
BestRemainingFrontierAction
```

using the same conflict-reconciliation principle that fixed range runtime.

Expected result: large files terminate on low information gain rather than round 10.

### D. Budgeted global evidence resolver

Replace independent binary keep/drop with:

```text
Choice:
  Candidate A
  Candidate B
  ...
  StopEvidence
```

repeated under a small evidence budget.

Expected result: improve precision, redundancy efficiency, and organization.

### E. Compose with FollowFile

A frontier observation should be allowed to disclose repository actions:

```text
ReadRange
  -> Observation
  -> relevance frontier update
  -> FollowFile(MessageRouter.ts)
```

The two mechanisms operate at different dimensions of the same runtime:

- Relevance Frontier: progressively disclose **where inside a file** to inspect.
- FollowFile: progressively disclose **which file/state** becomes reachable next.

## Conclusion

Adaptive Relevance Frontier v1 is a meaningful improvement over the original adaptive zoom design.

It demonstrates the behavior the hypothesis required: relevance changes with new observations, score gradients disclose missing siblings, volatile regions can be revisited, and a known range-runtime intra-file miss was recovered.

The experiment does **not** justify replacing Range Runtime yet. Its strongest current interpretation is:

> Relevance Frontier is a promising intra-file policy that has reached roughly range-level latency and blind quality, while providing richer belief-state behavior. The next work is to make the frontier selective — especially after the coarse level — and then compose it with cross-file `FollowFile` actions.

The research direction remains valid; the remaining problem is now much more specific: **reduce frontier-state cost and prevent refinement from degenerating into near-exhaustive child coverage.**
