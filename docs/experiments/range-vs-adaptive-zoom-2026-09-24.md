# Range Runtime vs Adaptive Semantic Zoom — Controlled A/B

Date: 2026-09-24

## Question

Does the current adaptive semantic zoom algorithm improve code-localization quality or navigation efficiency compared with the independent per-file range runtime?

## Frozen experiment

- Subject: `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- Task: `Help me optimize the websocket connection implementation`
- Harness: `BestNathan/system-one-code-explore@42da60815e7f1a7c05cce41d8c85d26488ed39e7`
- System One model: `jev-latest`
- Blind evaluator harness: Claude Code
- Blind evaluator model: `deepseek-flash`
- Controlled Actions run: `35942536032`

A preliminary independent run (`35942028473`) allowed each algorithm to execute its own Phase 1 and selected slightly different file sets. Because that difference could confound quality, the controlled run performs Phase 1 exactly once and feeds the same 17 candidate files into both Phase-2 algorithms.

## Algorithms

### Range runtime

- 140-line reads.
- Seed head / middle / tail.
- Expand before / after the previous selected ranges.
- Geometry-only jumps into the largest unread gaps.
- System One chooses StopFile / ContinueFile and scores concrete ReadRange utility.
- Stop/read contradictions are explicitly reconciled.

### Adaptive semantic zoom v0

- Split each file into 16 initial coarse regions.
- Read a 32-line midpoint probe from every coarse region.
- System One produces a probability distribution over the visible frontier.
- Retain a beam up to width 3 / probability mass 0.80.
- Add one geometry-only exploration slot.
- Split selected regions and recursively probe their children.
- Converge when the probability frontier is fine/stable, otherwise stop at eight rounds.

## Controlled cost

Shared Phase 1:

- candidates: 17
- model calls: 2
- input tokens: 82,628
- output tokens: 10,568
- elapsed: 2.301s

| Metric | Range runtime | Adaptive zoom |
| --- | ---: | ---: |
| Counterfactual total elapsed | **43.737s** | 83.192s |
| Phase-2 elapsed | **41.435s** | 80.890s |
| Model calls incl. shared Phase 1 | **83** | 187 |
| Input tokens incl. shared Phase 1 | **616,598** | 1,052,237 |
| Output tokens incl. shared Phase 1 | **16,753** | 34,227 |
| Reads / probes | **88** | 433 |
| Valuable files | 10 | **11** |
| Evidence regions | **38** | 206 |

Relative to range, adaptive zoom used approximately:

- 1.90x total elapsed time;
- 2.25x model calls;
- 1.71x input tokens;
- 2.04x output tokens;
- 4.92x source probes;
- 5.42x retained evidence regions.

No provider-dollar comparison is available because System One provider cost was not recorded.

## Termination

Range runtime:

- model_stop: 6 files;
- action_space_exhausted: 11 files;
- budget_exhausted: 0 files.

Adaptive zoom:

- probability_frontier_converged: 11 files;
- round_budget_exhausted: 6 files.

The zoom algorithm therefore still has a substantial tail in which the frontier never satisfies its convergence rule before the eight-round budget.

## Large-file behavior

| File | Range reads / coverage | Zoom probes / coverage |
| --- | ---: | ---: |
| `server/handler.rs` | 25 / 50.8% | 78 / 29.5% |
| agent `server/websocket.rs` | 16 / 73.9% | 52 / 45.6% |
| `connection/server_client.rs` | 16 / 78.1% | 52 / 44.4% |
| server `server/websocket.rs` | 5 / 89.3% | 38 / 89.2% |
| CLI `client/connection.rs` | 7 / 92.9% | 44 / 94.1% |

The most important structural result is that more probes do not mean more distinct source coverage. Recursive midpoint probes overlap parent/child neighborhoods, so zoom may issue three to five times as many reads while covering fewer unique lines.

Small files also pay a fixed initial-probe tax: many files that range can consume in one or two reads receive 10–16 initial zoom probes.

## Localization overlap

Canonical result comparison:

- shared valuable files: 10;
- union valuable files: 11;
- file Jaccard: 90.9%;
- range-only files: 0;
- adaptive-only: `web/src/platform/attach/relayServerConnection.ts`.

Evidence overlap:

- 97.4% of range evidence regions overlap adaptive evidence;
- 60.6% of range evidence lines overlap adaptive evidence;
- 74.8% of adaptive evidence regions overlap range evidence;
- 71.8% of adaptive evidence lines overlap range evidence.

Adaptive zoom therefore covers nearly every region range finds, but produces a much larger evidence surface around and between those regions.

## Blind downstream-quality evaluation

Each candidate was evaluated in a separate fresh Claude Code session against the same frozen repository. The evaluator saw only one anonymized candidate and the common rubric.

| Dimension | Weight | Range | Adaptive zoom |
| --- | ---: | ---: | ---: |
| Completeness | 25% | 6.0 | 6.0 |
| Relevance precision | 15% | **6.5** | 4.5 |
| Evidence grounding | 15% | **8.0** | 7.5 |
| Redundancy efficiency | 10% | **4.0** | 3.0 |
| Downstream actionability | 20% | **5.5** | 5.0 |
| Organization / prioritization | 5% | **4.0** | 2.5 |
| Risk / uncertainty coverage | 10% | 3.5 | **4.0** |
| **Weighted score** | 100% | **57.25** | 51.25 |
| Can proceed | — | yes | yes |

The important point is not the absolute score — evaluator judgments are stochastic and are not ground truth. The controlled comparison shows that zoom did **not** improve completeness despite its much larger navigation budget.

### Shared omissions

Both algorithms still miss the dependencies that motivated the next research stage:

- `web/src/platform/socket/MessageRouter.ts`;
- `crates/nession-server/src/server/command_broker.rs`;
- `crates/nession-server/src/server/client_registry.rs`;
- `web/src/shared/lib/addressSelection.ts`;
- important test and configuration surfaces.

This confirms that spending more range-navigation budget inside the Phase-1 file set does not solve the cross-file state-space-discovery problem.

### Adaptive-specific quality problem

The evaluator repeatedly identified overlapping sliding evidence:

- multiple overlapping windows over `handler.rs`;
- multiple overlapping windows over agent `websocket.rs`;
- near-whole-file `WebSocketService.ts` represented as many probes;
- unrelated handler and file-operation regions retained as evidence.

The current evidence scorer independently evaluates every observation, including parent/child zoom probes that cover substantially the same source. It has no dominance / leaf-only / overlap-pruning rule.

## Interpretation

### Range runtime remains the baseline

Adaptive zoom v0 should not replace the current range runtime.

The range runtime is:

- materially cheaper;
- easier to stop;
- less redundant;
- at least as complete in this controlled experiment;
- more suitable as the baseline for M1 cross-file state discovery.

### What is still valuable in adaptive zoom

The failed replacement does not invalidate the underlying zoom idea.

The useful primitives are:

1. probability distributions over a bounded frontier;
2. beam selection instead of a single winner;
3. coarse-to-fine refinement around uncertain hotspots;
4. an explicit exploration slot outside the current probability beam.

These should be reused as **local actions inside the range runtime**, rather than applied eagerly to every candidate file.

A better architecture is:

```text
Range Runtime
    |
    +-- ReadRange
    +-- JumpGap
    +-- FollowFile
    |
    +-- ZoomRegion   <-- optional, only when a large/ambiguous region deserves it
            |
            +-- small local beam
            +-- leaf probes only
            +-- stop on marginal information gain
```

## Why adaptive zoom v0 is expensive

### 1. Eager 16-region probing

Every candidate file begins by probing up to 16 regions even when the whole file can be consumed cheaply in one or two range reads.

### 2. Parent/child probe overlap

A region is probed, split, and its children are probed again. Distinct source coverage grows much more slowly than probe count.

### 3. Every observation becomes an evidence candidate

Post-navigation scoring sees all ancestor and descendant probes. It therefore tends to retain repeated views of the same code.

### 4. Convergence is not marginal-utility stopping

The zoom loop stops on frontier geometry/probability stability. Six of 17 controlled files reached the round budget. Range runtime now uses explicit Stop/Read reconciliation and had zero budget exhaustion.

## Recommended next experiments

Do not tune beam width or probability mass first. The structural costs dominate those parameters.

The next zoom experiment should change the algorithm:

1. **Lazy initial probing**
   - scale coarse probes by file size;
   - use 1–3 probes for small files;
   - avoid 16-probe startup cost.

2. **Leaf-only evidence**
   - do not retain both an ancestor probe and overlapping descendants;
   - perform overlap/dominance pruning before evidence scoring.

3. **Distinct-coverage accounting**
   - optimize information gained per newly observed line, not raw probe count.

4. **Model-driven stop**
   - add explicit StopZoom / ContinueZoom control;
   - reconcile it with the utility of the best concrete refinement, analogous to range runtime.

5. **Use zoom as a primitive, not the file runtime**
   - expose `ZoomRegion` only for large ambiguous gaps or hotspots;
   - preserve range runtime as the default navigation policy.

6. **Prioritize M1 FollowFile**
   - both algorithms miss the same cross-file dependencies;
   - another intra-file search algorithm cannot repair a missing action-space dimension.

## Conclusion

The controlled result rejects the current hypothesis that adaptive semantic zoom v0 is a better default code-localization runtime than range search.

It spends substantially more computation to produce substantially more evidence, but that additional evidence is mostly overlapping or low-priority. The blind evaluator found no completeness gain and rated the final result lower overall.

The research value of adaptive zoom is therefore not as a replacement runtime. Its useful concepts should be decomposed into optional exploration primitives inside the cheaper range-based state machine.
