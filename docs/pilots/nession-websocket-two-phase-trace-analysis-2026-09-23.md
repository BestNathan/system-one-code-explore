# Nession WebSocket two-phase reader trace analysis — 2026-09-23

## Scope

This note analyzes the decision path from the real TypeSafe baseline run 35828994234 for the task:

> Help me optimize the websocket connection implementation.

The purpose is to verify whether the two-phase harness produces meaningful semantic state transitions and to identify the next harness defect before changing any research variable.

## Baseline configuration

~~~text
Phase 1
directory threshold = 0.50
file threshold      = 0.65
max files           = 16

Phase 2
file batch size       = 4
read window           = 140 lines
max rounds / batch    = 4
read action threshold = 0.40
observation threshold = 0.65
~~~

## Aggregate path

~~~text
380 directories
  -> Noul >= 0.50
40 directories
  -> 159 direct files
  -> Noul >= 0.65
17 files above threshold
  -> top-16 budget
16 PotentialFiles

Phase 2
4 batches
48 file-level action decisions
38 executed reads
38 observations
27 evidence observations
~~~

Model usage:

~~~text
Directory calls             1
File calls                  1
Reader Action calls        14
Observation scoring calls  13
Total                      29

Input tokens          340,395
Output tokens          13,205
Elapsed                  7.20s
~~~

The 29 calls correspond to semantic interaction depth rather than transport batching: Phase 1 uses two localization requests and Phase 2 alternates batched Choice and batched observation-Noul requests.

## Phase-1 findings

Raising the directory threshold to 0.50 compressed the directory frontier from 380 to 40 while preserving the expected websocket/server/connection areas.

The file threshold at 0.65 is more aggressive. A notable boundary case is `web/src/.../useVisibilityReconnect.ts`, which scored 0.64 and was pruned even though its name suggests plausible relevance. This makes 0.60 / 0.625 / 0.65 useful values for a controlled threshold study.

Phase 1 also has an independent top-k budget. Seventeen files passed the 0.65 threshold, but only sixteen entered the reader. Threshold pruning and hard frontier budget must therefore be measured separately.

## Three observed reader behaviors

### Exploit a high-relevance local region

`web/src/platform/socket/WebSocketService.ts` followed a clean local expansion path:

~~~text
1-140    relevance 0.89
  -> 141-280    0.77
  -> 281-420    0.79
  -> 421-542    0.86
~~~

Each high-relevance observation generated a valid continuation action, and System One repeatedly selected it. This is the intended progressive-reader behavior.

### Stop after evidence corrects a Phase-1 hypothesis

`web/src/shared/hooks/useWebSocket.ts` entered Phase 2 with a strong Phase-1 file score (0.84), but its only observed range scored 0.44. The next Choice selected StopFile.

Similar early stops occurred for low-value wrapper/index files such as `socket/index.ts` and `connection/mod.rs`.

This demonstrates a useful separation of responsibilities:

~~~text
Phase 1: this file looks worth investigating
Phase 2: after reading it, the implementation evidence is weak -> stop
~~~

### Explore elsewhere after local relevance falls

`crates/nession-agent/src/server/websocket.rs` showed exploration after a local drop:

~~~text
1-140       0.87
141-280     0.60   <- below evidence threshold
1585-1724   0.74   <- probe largest unread gap; new hotspot
2307-2446   0.22
~~~

After the 0.60 observation, the harness stopped local expansion and offered an unexplored-gap probe. System One found a second relevant region at 1585-1724. This is evidence that observation scores can switch the reader from exploitation to exploration.

## Core defect discovered: strongest-hotspot collapse

The current ActionSpaceGenerator only expands around the single strongest relevant observation/region.

In `crates/nession-agent/src/server/websocket.rs`, the trace contained two separated relevant regions:

~~~text
hotspot A: 1-140       relevance 0.87
hotspot B: 1585-1724   relevance 0.74
~~~

After hotspot B was discovered, the next frontier should have included reads immediately before and after 1585-1724. It did not. The implementation continued to treat hotspot A as the strongest anchor; its adjacent ranges were already covered, so the only useful action left was another largest-gap probe.

This is a harness action-space defect, not a System One decision error. The model cannot select an action that the harness does not expose.

## Next change: RelevantRegion[]

Replace the single strongest anchor with a bounded set of connected high-relevance regions:

~~~text
high-score observations
  -> merge overlapping / adjacent observations
  -> RelevantRegion[]
       start_line
       end_line
       max_relevance
       observation_count
  -> rank regions
  -> generate before/after actions for each retained region
  -> add one exploration-gap action
  -> StopFile
~~~

The action frontier must remain bounded. The initial implementation should retain at most three relevant regions per file and generate at most two neighbor actions per region, plus one exploration action and StopFile.

This preserves multiple semantic hotspots without returning to a flat whole-file frontier.

## Other findings intentionally deferred

### Hard round budget

`server/handler.rs` found a new relevant region on round 4 and then stopped because the fixed max-round budget was exhausted. A later study should compare soft and hard read budgets or explicit sufficiency decisions.

### Batch semantics

Four files are decided in one request, but the current schema still asks one Choice question per file. It does not impose a global read budget across the batch. A future experiment may compare per-file Choice with batch-level resource allocation.

### Action confidence

The 0.40 chosen-action threshold did not reject any selected read in this run. Some reads had low Choice confidence despite a winning probability above threshold. Probability, confidence, margin, and entropy should be evaluated separately.

### State accumulation cost

Observation-relevance requests consumed more input tokens than Phase 1 because previous raw observations remain in ReaderState across rounds. State compaction is now a distinct cost-optimization research direction, but it should not be mixed into the multi-hotspot change.

## Baseline conclusion

The run demonstrates the intended loop:

~~~text
Action
  -> Observation
  -> Observation score
  -> changed state
  -> changed action frontier
~~~

The next implementation change is narrowly scoped: preserve multiple disconnected high-relevance regions when constructing the next read-action frontier. Thresholds, batch size, read window, and round budget should remain unchanged so the next real run isolates this one harness variable.

## Implementation result

The multi-hotspot change described above was implemented and validated in real TypeSafe run 35831659317.

The motivating `crates/nession-agent/src/server/websocket.rs` trace changed from:

~~~text
second hotspot 1585-1724
  -> no local neighbor actions
  -> unrelated gap probe
~~~

to:

~~~text
second hotspot 1585-1724
  -> before 1445-1584
  -> after 1725-1864
  -> exploration gap
  -> stop
~~~

System One selected the before-hotspot action at probability 0.62, and the resulting observation scored 0.78 relevance.

This directly closes the strongest-hotspot action-space defect identified by this analysis. The controlled follow-up is documented in [nession-websocket-multi-hotspot-reader-2026-09-23.md](nession-websocket-multi-hotspot-reader-2026-09-23.md).
