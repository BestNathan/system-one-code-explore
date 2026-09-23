# Pilot Run: Nession WebSocket Localization

> Date: 2026-09-23  
> Workflow run: 35817921653  
> Subject: `BestNathan/nession@f6a08b41c946574cc14343c4c3bb808bc402e49f`  
> Model: `jev-latest`

## Query

> Help me optimize the websocket connection implementation

## Parameters

```text
directory threshold = 0.35
file threshold      = 0.50
line threshold      = 0.70
batch size          = 48
```

## Outcome

The real System One workflow completed successfully and produced a full research artifact.

The highest-scoring files were strongly aligned with the requested implementation:

| Score | File |
|---:|---|
| 0.93 | `crates/nession-server/src/server/websocket.rs` |
| 0.92 | `crates/nession-agent/src/server/websocket.rs` |
| 0.91 | `web/src/platform/socket/WebSocketService.ts` |
| 0.88 | `web/src/shared/hooks/useWebSocket.ts` |
| 0.86 | `crates/nession-cli/src/client/connection.rs` |
| 0.86 | `web/src/app/useAppConnection.ts` |
| 0.86 | `web/src/platform/terminal-runtime/ConnectionManager.ts` |
| 0.84 | `web/src/platform/attach/relayServerConnection.ts` |

The top snippets also landed on concrete WebSocket lifecycle behavior, including:

- server-side ping/heartbeat handling;
- WebSocket accept/split and connection setup;
- reconnect and visibility-reconnect behavior;
- client/agent WebSocket message loops;
- connection-management code.

This is evidence that repeated System One relevance judgments can recover semantically useful implementation surfaces without a ReAct browsing loop.

## Cost and search-space behavior

The same run also exposed a major weakness in the first prototype:

```text
directories exposed  = 382
directories selected = 88

files exposed         = 1040
files selected        = 92

lines exposed         = 25,189
lines selected        = 1,308

snippets              = 370

model calls           = 601
  directory            = 8
  file                 = 22
  line                 = 571

input tokens          = 5,808,879
  directory            = 67,063
  file                 = 165,449
  line                 = 5,576,367
output tokens         = 502,109
elapsed               = 125.7 s
```

The result quality was promising, but the search policy was too permissive. Line expansion alone accounted for 571 of 601 model calls and about 96% of input tokens.

The main problem is not System One latency itself. The harness exposes too much state before applying a sufficiently strong budget.

In particular:

1. the prototype enumerates the whole directory tree before semantic pruning;
2. a low directory threshold retains many overlapping parent/child directories;
3. file discovery under those directories exposes a very large union of files;
4. every retained file is then expanded into line candidates.

This creates multiplicative fan-out:

```text
weak early pruning
  -> many directories
  -> many files
  -> many lines
  -> many System One questions
```

The pilot therefore supports the original hypothesis that early-stage recall matters, but also shows that threshold-only retention is not enough.

## Transport-boundary finding

An earlier attempt reached a Cloudflare 403 while scoring source lines.

The blocked batch contained security-test code such as a path-traversal fixture:

```text
../etc/passwd
```

The API key and endpoint were valid: the Kubernetes System One experiment completed successfully in the same job.

The fix was to separate **raw evidence** from the **model transport projection**:

```text
raw source candidate
  -> preserved in local trace

model projection
  -> normalize string literal values
  -> preserve identifiers / types / control flow
  -> send to System One
```

This allowed the real code-localization run to complete while keeping the original source in the research artifact.

This suggests a broader harness principle:

> External model transport is itself an execution boundary. The runtime may need a safe semantic projection of observed state instead of blindly forwarding raw environment bytes.

## Updated working hypothesis

The pilot suggests that the next version should move from threshold-only breadth-first filtering toward a bounded semantic search policy.

A stronger policy is:

```text
current frontier
  -> System One score
  -> retain above threshold
  -> guarantee a minimum beam
  -> enforce a maximum expansion budget
  -> expand only retained states
```

For repository localization, the likely next hierarchy is:

```text
root
  -> immediate child directories
  -> recursively selected directories
  -> files
  -> symbols / blocks
  -> lines
```

This is preferable to globally enumerating every directory before the first judgment.

## Next experiment

The next comparison should hold the query and subject revision constant and compare:

### Baseline A — current prototype

```text
whole-tree directories
-> threshold
-> files
-> threshold
-> lines
```

### Candidate B — recursive semantic beam

```text
root children
-> score
-> threshold + top-k
-> expand selected children
-> repeat
-> files
-> symbols
-> lines
```

Measure:

- relevant-file recall;
- model calls;
- input/output tokens;
- elapsed time;
- candidates exposed at each level;
- stage where any expected file is first pruned;
- final snippet quality.

The goal is not merely to make the current search cheaper. It is to test whether **progressive state disclosure plus a bounded semantic frontier** is the right primitive for System One code navigation.
