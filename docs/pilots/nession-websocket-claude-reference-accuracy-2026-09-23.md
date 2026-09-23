# Nession WebSocket localization accuracy against Claude Code reference — 2026-09-23

> Methodology note: Claude Code is an independent System-2 execution record, not ground truth and not an optimization target for System One. The agreement/recall numbers below are retained as descriptive observations from this historical run only.

## Purpose

Behavioral traces show that the progressive reader can make coherent state transitions, but that does not establish that the returned files and source ranges are correct. This experiment therefore compares the System One locator with an independent System 2 repository investigation performed by Claude Code using the configured `ds` environment.

Claude Code is a reference baseline, not ground truth. Agreement metrics are useful for identifying likely misses and noise, but a multi-task human-reviewed gold set is still required for absolute accuracy claims.

## Experimental controls

- GitHub Actions run: 35834529068
- Subject: `BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664`
- Verbatim task given to both systems: `Help me optimize the websocket connection implementation`
- System One model: `jev-latest`
- Claude Code client: `@anthropic-ai/claude-code@2.1.278`
- Claude Code provider/model from `ds`: `deepseek-flash`
- Claude tools: Read, Glob, Grep and read-only Bash only
- Claude could not edit files, use web search, inspect GitHub issues, or use git history

Both jobs resolved the subject revision once and checked out the same exact SHA.

## Runtime comparison

~~~text
System One progressive reader
  elapsed             12.71s
  semantic model calls    47
  input tokens        585,542
  output tokens        13,926

Claude Code + ds
  duration             67.19s
  turns                    34
  input tokens          77,006
  cache-read tokens  1,105,152
  output tokens         11,398
  reported cost         $1.222556
~~~

Token accounting is provider/runtime-specific and is not directly comparable. Runtime shows the intended qualitative tradeoff: the System One harness finished about 5.3x faster in this single run.

## Claude reference set

Claude identified 18 files:

~~~text
primary     5
supporting  9
context     4
~~~

Primary files:

1. `web/src/platform/socket/WebSocketService.ts`
2. `crates/nession-agent/src/connection/server_client.rs`
3. `crates/nession-agent/src/server/websocket.rs`
4. `crates/nession-server/src/server/websocket.rs`
5. `web/src/platform/socket/MessageRouter.ts`

## File-level agreement

~~~text
System One Phase-1 files       16
System One final evidence files 12

Claude reference files hit by Phase 1   11/18 = 61.1%
Claude reference files in final evidence 9/18 = 50.0%

Claude primary hit by Phase 1             4/5 = 80.0%
Claude primary in final evidence          4/5 = 80.0%

Evidence precision proxy vs Claude        9/12 = 75.0%
~~~

The precision number is deliberately called a proxy: the three System-One-only files may contain useful evidence that Claude omitted.

System-One-only evidence files were:

- `crates/nession-server/src/server/web_client_registry.rs`
- `web/src/app/useRealtimeUpdates.ts`
- `web/src/product/terminal/server.ts`

## Evidence-region accuracy

File overlap alone is too weak because a reader may open the correct large file but miss the relevant implementation region. Claude therefore returned explicit evidence line ranges.

Against those ranges, System One achieved:

~~~text
all Claude evidence regions
  overlap          24/39 = 61.5%
  line coverage          = 76.8%

primary evidence regions
  overlap          16/20 = 80.0%
  line coverage          = 85.8%

supporting evidence regions
  overlap           8/15 = 53.3%
  line coverage          = 65.4%

context evidence regions
  overlap            0/4 = 0%
~~~

The zero context-region recall is not necessarily undesirable: the final evidence threshold intentionally removes several wrapper/context files after reading them.

## Important primary miss: MessageRouter.ts

Claude classifies `web/src/platform/socket/MessageRouter.ts` as primary because it owns request correlation, request timeouts, incoming response dispatch, and failing pending requests when the socket is lost.

System One Phase 1 exposed the file but scored it:

~~~text
MessageRouter.ts
score = 0.64
rank  = 21

current threshold = 0.65
current cap       = 16
~~~

It therefore failed both the confidence cutoff and the frontier budget.

This is especially important because the information needed to recover the miss already existed in a high-confidence observation. `WebSocketService.ts` was a top System One file and its first observed window (`1-140`) contains:

~~~text
import { MessageRouterImpl } from './MessageRouter';
import type { ... } from './types';
~~~

The current Phase 2 reader cannot turn those newly observed dependencies into new file actions, so a Phase-1 miss is permanent.

## Other reference misses

Near the current boundary:

~~~text
SessionRuntime.ts          score .64  rank 20  supporting
useVisibilityReconnect.ts  score .67  rank 17  context
types.ts                   score .59  rank 29  supporting
~~~

`useVisibilityReconnect.ts` is a pure hard-cap miss: it passes the 0.65 threshold but loses the top-16 cutoff.

Some indirect dependencies score far below any practical Phase-1 threshold:

~~~text
command_broker.rs          score .37  rank 75  supporting
probe.rs                   score .31  rank 93  context
AddressAttachPolicy.ts     score .16  rank 130 supporting
~~~

This demonstrates that lowering the Phase-1 threshold alone cannot recover the full dependency graph without re-expanding the state space dramatically.

## Same-score threshold/cap replay

The exact Phase-1 score snapshot from this run was replayed against the Claude reference set, avoiding model-score drift:

~~~text
threshold / cap       files   all ref   primary   supporting
.65 / 16                16     11/18      4/5       5/9
.65 / 20                19     12/18      4/5       5/9
.64 / 24                21     14/18      5/5       6/9
.59 / 32                30     15/18      5/5       7/9
~~~

`0.64 + cap >= 21` would recover all five Claude primary files in this task, but changing the default based on one query would overfit the experiment. A multi-task reference/gold set should drive threshold calibration.

## Range-level misses inside selected files

Phase 2 also has misses independent of Phase 1.

Examples:

- `crates/nession-agent/src/server/websocket.rs` was selected and explored around lines 1305-1724, but Claude also identified the attach/subscriber fan-out at 625-724; System One never observed that region.
- `crates/nession-server/src/server/handler.rs` was selected, but Claude's relay-begin evidence at 1455-1478 was not observed; System One instead read the head and a later hotspot around 3449-3588.

So accuracy is not only a Phase-1 problem. Dynamic exploration still needs a better way to follow semantic dependencies and references.

## Architectural conclusion

The strongest result is asymmetric:

> When System One reaches the correct primary file, its local evidence coverage is strong. The dominant accuracy failure is that the initial file frontier is static and Phase 2 cannot add newly discovered files.

This suggests preserving a relatively high-confidence Phase 1 and extending Phase 2 with dynamically disclosed cross-file actions derived from observations.

Candidate actions include:

~~~text
InspectDependency(path discovered in import/use/mod statement)
FindReferences(identifier discovered in relevant content)
InspectDefinition(identifier)
SwitchToDiscoveredFile(path)
~~~

For the current task, the progression could become:

~~~text
WebSocketService.ts:1-140
  -> observation discovers ./MessageRouter and ./types
  -> new grounded file actions
  -> System One chooses InspectDependency(MessageRouter.ts)
  -> MessageRouter content enters state
  -> observation relevance decides whether to retain / expand it
~~~

This is more consistent with progressive state-space disclosure than lowering Phase-1 thresholds until every transitive dependency is present up front.

## Benchmark infrastructure

The repository now contains:

- `.github/workflows/system-one-code-locator-accuracy.yml` — manual dual-run accuracy workflow using `typesafe` and `ds` environments.
- `research/code-locator/src/compare_claude_reference.py` — file and evidence-region comparison.
- `research/code-locator/tests/test_compare_claude_reference.py` — comparison metric regression tests.

Future runs should preserve both agents' execution trajectories across multiple real localization tasks. Any absolute accuracy claim requires an independent human-reviewed gold set; Claude agreement alone should not drive System One thresholds or architecture.
