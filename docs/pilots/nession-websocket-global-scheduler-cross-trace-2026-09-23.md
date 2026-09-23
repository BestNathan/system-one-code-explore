# Nession WebSocket global file scheduler + Claude cross-trace — 2026-09-23

## Purpose

This run records two independent localization trajectories for the same repository revision and the same user task. Claude Code is not treated as ground truth and System One is not optimized to reproduce Claude's final file set.

The research question for System One is narrower:

> Does a fixed harness-defined file order/batch constrain the model unnecessarily? Can all Phase-1 retained files become one shared Phase-2 state and let System One decide which files should be read next?

## Run

- GitHub Actions run: `35839323377`
- Subject: `BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664`
- Task: `Help me optimize the websocket connection implementation`
- System One: `jev-latest`
- Claude Code: `@anthropic-ai/claude-code@2.1.278` using `ds` model `deepseek-flash`

## Architecture change

The previous reader used a harness-defined top-k and fixed file batches:

~~~text
Phase 1
  -> top 16 files
  -> batch 0 (4 files)
  -> batch 1 (4 files)
  -> ...
~~~

The new reader does not contain either decision:

~~~text
Phase 1
  -> every file above the Phase-1 file threshold
  -> one ReaderState containing all retained files

global scheduler epoch:
  -> Noul score every eligible file in one request
  -> select every file above the independent activation threshold
  -> Choice read action for the selected files
  -> execute reads
  -> observations enter state
  -> Noul observation relevance
  -> rescore the global file frontier
~~~

An unselected file is deferred, not deleted. It remains in ReaderState and can become active in a later epoch after other observations change the state.

Read budgets are file-owned (`soft_reads=4`, `hard_reads=8`), while scheduler epochs are only global decision steps.

## System One trajectory

Phase 1 retained 18 files. There is no top-16 truncation:

~~~text
0.90 crates/nession-server/src/server/websocket.rs
0.89 crates/nession-agent/src/server/websocket.rs
0.88 web/src/platform/socket/WebSocketService.ts
0.84 web/src/shared/hooks/useWebSocket.ts
0.81 web/src/app/useAppConnection.ts
0.79 web/src/platform/terminal-runtime/ConnectionManager.ts
0.78 crates/nession-cli/src/client/connection.rs
0.77 crates/nession-agent/src/connection/server_client.rs
0.76 web/src/platform/attach/relayServerConnection.ts
0.75 web/src/app/useRealtimeUpdates.ts
0.74 web/src/platform/socket/index.ts
0.72 crates/nession-agent/src/connection/mod.rs
0.69 crates/nession-server/src/server/web_client_registry.rs
0.68 web/src/platform/terminal-runtime/transport/TerminalTransport.ts
0.67 web/src/app/useVisibilityReconnect.ts
0.66 crates/nession-server/src/server/handler.rs
0.66 web/src/platform/attach/state/transport.ts
0.66 web/src/product/terminal/state/transport.ts
~~~

### Scheduler epoch 1

System One rescored all 18 files in the shared state. Only three exceeded the Phase-2 activation threshold (0.65):

~~~text
0.86 crates/nession-server/src/server/websocket.rs
0.81 web/src/platform/socket/WebSocketService.ts
0.78 crates/nession-agent/src/server/websocket.rs

next highest:
0.63 useAppConnection.ts
0.62 useWebSocket.ts
0.59 server_client.rs
...
~~~

The harness therefore read only those three files. It did not read the next files merely because they were next in Phase-1 score order.

All three chose the initial head probe (`1-140`) and produced high-relevance observations:

~~~text
server websocket      0.88
agent websocket       0.88
WebSocketService      0.91
~~~

### Scheduler epoch 2

The complete file frontier was rescored. The same three files remained above threshold and continued to `141-280`:

~~~text
server websocket      activation 0.72 -> observation 0.75
agent websocket       activation 0.79 -> observation 0.68
WebSocketService      activation 0.79 -> observation 0.83
~~~

### Scheduler epoch 3

Only two files remained above activation threshold:

~~~text
WebSocketService      0.69
agent websocket       0.65
server websocket      0.62  <- deferred
~~~

The selected files read `281-420` and scored 0.80 / 0.72.

### Scheduler epoch 4

No file scored at or above 0.65:

~~~text
server websocket      0.62
WebSocketService      0.62
agent websocket       0.61
web_client_registry   0.52
useAppConnection      0.50
...
~~~

The global scheduler stopped with reason `no_file_above_activation_threshold`.

## System One aggregate

~~~text
Phase-1 retained files          18
scheduler epochs                4
file-priority decisions        72
file activations                8
read-action decisions           8
reads executed                  8
unique files read               3
evidence observations           8
model calls                    12
input tokens              195,977
output tokens              12,464
elapsed                     3.78s
~~~

This is substantially narrower than the previous fixed-batch reader, but the experiment does not claim that narrower is inherently more accurate.

## Claude Code execution trajectory

The workflow now saves both:

- `claude.raw.jsonl`: the complete Claude Code `stream-json` event stream;
- `execution-path.json`: normalized ordered tool calls with input arguments and result metadata;
- `execution-summary.md`: human-readable ordered tool path;
- `reference.json`: Claude's final localization record.

Claude used 42 tool calls in 43 turns:

~~~text
Read  24
Grep   2
Bash  16
Glob   0
duration 79.8s
~~~

The path shows a classic System-2 repository exploration pattern rather than a fixed file sequence. High-level progression:

1. Inspect repository / Cargo structure.
2. Grep globally for websocket-related identifiers.
3. Read server websocket.
4. Inspect function outlines in agent/server and server/client code.
5. Read `server_client.rs` and the agent websocket hotspot.
6. Read CLI connection code.
7. Read `WebSocketService.ts` and `ConnectionManager.ts`.
8. Search `new WebSocket(` call sites.
9. Inspect session-runtime and attach directories.
10. Read `SessionRuntime.ts`, `AddressAttachPolicy.ts`, app reconnect hooks, and relay connection code.
11. Read `MessageRouter.ts` after following web socket relationships.
12. Search and read server handler / broker / registry paths.
13. Return to additional agent/server websocket and connection ranges.
14. Inspect `types.ts` and more session-runtime / handler regions.

This trajectory is preserved for comparison because the sequence of observations and searches is often more informative than Claude's final file list.

## Cross-trace record

The comparison artifact still records file/range overlap, but those values are descriptive only. Claude's final set is neither ground truth nor a target score for System One.

In this run System One intentionally concentrated on three files, while Claude continued a much broader 42-tool exploration. That divergence is itself useful experimental evidence.

## New design question

The global scheduler currently uses the file-activation threshold for two different purposes:

1. choose which files should be read now;
2. implicitly decide that exploration is finished when no file exceeds the threshold.

These are not necessarily the same semantic decision.

A future experiment should consider separating:

~~~text
FilePriority(path) -> should this file be read now?

TaskSufficiency(state) -> is the current evidence sufficient to stop exploring?
~~~

This should be studied independently rather than changing the activation threshold because Claude explored more files.

## Conclusion

The fixed batch/top-k policy is no longer part of the baseline. Phase 1 produces the complete threshold-retained initial state; Phase 2 is globally scheduled by System One. Claude Code is retained as an independent execution trace so that different search strategies can be inspected side by side without assuming either trajectory is the correct answer.
