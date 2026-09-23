# Nession WebSocket two-phase progressive reader baseline — 2026-09-23

## Run

- GitHub Actions run: 35828994234
- Subject: BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664
- Query: Help me optimize the websocket connection implementation
- Model: jev-latest

## Configuration

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

## Result

~~~text
directories exposed  = 380
directories selected = 40
files exposed        = 159
files selected       = 16

reader batches       = 4
reader decisions     = 48
reads executed       = 38
observations         = 38
evidence observations= 27

model calls          = 29
input tokens         = 340,395
output tokens        = 13,205
elapsed              = 7.20s
~~~

## Selected Phase-1 files

~~~text
0.910 crates/nession-server/src/server/websocket.rs
0.890 crates/nession-agent/src/server/websocket.rs
0.880 web/src/platform/socket/WebSocketService.ts
0.840 web/src/shared/hooks/useWebSocket.ts
0.810 web/src/app/useAppConnection.ts
0.800 web/src/platform/terminal-runtime/ConnectionManager.ts
0.780 crates/nession-cli/src/client/connection.rs
0.770 crates/nession-agent/src/connection/server_client.rs
0.770 web/src/app/useRealtimeUpdates.ts
0.760 web/src/platform/attach/relayServerConnection.ts
0.740 web/src/platform/socket/index.ts
0.730 crates/nession-agent/src/connection/mod.rs
0.700 crates/nession-server/src/server/web_client_registry.rs
0.680 web/src/platform/terminal-runtime/transport/TerminalTransport.ts
0.670 crates/nession-server/src/server/handler.rs
0.670 web/src/platform/attach/state/transport.ts
~~~

## Evidence that progressive reading is working

The reader does not immediately load full files. It begins with stat-derived probes and then changes the action frontier using observation relevance.

Examples:

- server/websocket.rs: 1-140 scored 0.88, then 141-280 scored 0.73, so the next rounds continued 281-420 and 421-560.
- WebSocketService.ts: 1-140 scored 0.89 and 141-280 scored 0.77, so the reader kept expanding contiguously to 281-420 and 421-542.
- useWebSocket.ts: the only range scored 0.44, so the next round chose StopFile.
- socket/index.ts scored 0.33 and connection/mod.rs scored 0.34; both stopped after the initial probe.
- server/handler.rs stayed locally focused while observations remained above threshold, then moved to an unread-gap probe after a 0.59 observation fell below the 0.65 evidence threshold.

This demonstrates the intended transition:

~~~text
read action
  -> source observation
  -> observation score
  -> changed action frontier
~~~

## Interpretation

The original 598-call implementation scaled model calls with candidate count because it used transport batching and per-file line scoring. This baseline uses 29 calls for a semantically interactive process: two Phase-1 localization requests plus batched reader Choice / observation-relevance requests.

The 29 calls should not be treated as an optimization target by itself. The research question is whether each additional call corresponds to a useful state transition and whether the reader reaches high-quality evidence under a bounded read budget.

## Next controlled experiments

1. Sweep directory/file thresholds while keeping the reader fixed.
2. Sweep reader-action and observation thresholds independently.
3. Compare file batch sizes 1, 2, 4, and 8.
4. Compare current stat/range actions with richer observation-driven actions.
5. Evaluate against a small gold set of expected relevant files/ranges.

## Trace analysis

A full decision-path analysis is preserved in [nession-websocket-two-phase-trace-analysis-2026-09-23.md](nession-websocket-two-phase-trace-analysis-2026-09-23.md).

The main harness defect discovered by that analysis was strongest-hotspot collapse: a file could contain multiple disconnected high-relevance regions, while the action generator only expanded around the single highest-scoring one. The next baseline changes only that variable by retaining a bounded `RelevantRegion[]` frontier.
