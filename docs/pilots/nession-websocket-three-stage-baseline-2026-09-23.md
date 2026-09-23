# Nession WebSocket Three-Stage Baseline — 2026-09-23

## Purpose

Establish a stable, reproducible System One Code Locator baseline before changing thresholds or the decision primitive.

The baseline intentionally keeps the original semantic thresholds unchanged:

```text
directory >= 0.35
file      >= 0.50
region    >= 0.70
```

The task is:

> Help me optimize the websocket connection implementation.

Subject repository:

```text
BestNathan/nession@67062f3e622b83360aed20fd8c4b3cb052a00404
```

Successful GitHub Actions run:

- https://github.com/BestNathan/narness-engineering/actions/runs/35824339286

## Stable request topology

The harness now performs exactly one System One request per semantic stage:

```text
repository
  -> all directories
  -> Noul request #1
  -> retained directories
  -> direct files only
  -> Noul request #2
  -> retained files
  -> compact 120-line regions
  -> Noul request #3
  -> grounded source snippets
```

Two invariants are important:

1. The file frontier never recursively walks a selected directory. Stage one already enumerates the complete directory tree, so stage two exposes only direct files of directories that survived stage one.
2. Repository size may increase the size of a decision frontier, but it must not increase the number of semantic System One round trips.

## Baseline result

| Stage | Exposed | Selected | Request bytes | Input tokens | Output tokens | Latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Directory | 380 | 91 | 239,202 | 64,730 | 7,494 | 704 ms |
| File | 272 | 82 | 165,700 | 43,788 | 5,334 | 378 ms |
| Region | 267 | 89 | 199,892 | 60,179 | 5,234 | 569 ms |

Aggregate:

```text
model_calls              = 3
input_tokens             = 168,697
output_tokens            = 18,062
elapsed_ms               = 1,822
physical_lines_considered= 26,280
region_span              = 120
snippets                 = 43
```

The highest-scoring files are semantically plausible for the task:

```text
0.920 crates/nession-agent/src/server/websocket.rs
0.920 crates/nession-server/src/server/websocket.rs
0.920 web/src/platform/socket/WebSocketService.ts
0.870 crates/nession-cli/src/client/connection.rs
0.870 web/src/shared/hooks/useWebSocket.ts
0.860 web/src/app/useAppConnection.ts
0.840 web/src/platform/terminal-runtime/ConnectionManager.ts
0.830 web/src/app/useRealtimeUpdates.ts
0.830 web/src/platform/attach/relayServerConnection.ts
0.820 crates/nession-agent/src/connection/server_client.rs
```

This is not yet a localization-accuracy claim. It is the first stable operational baseline whose state transitions, decision primitive, thresholds, and request topology are fixed enough for controlled experiments.

## Why the frontier changed

The initial implementation accidentally measured transport behavior rather than the intended architecture.

### Initial batched line implementation

```text
directories exposed = 382
files exposed       = 1,040
files selected      = 92
lines exposed       = 25,006
model calls         = 598
input tokens        = 5,766,575
```

The causes were:

- candidates were split into batches of 48;
- the line scorer was called once per selected file;
- selected directories were recursively walked again.

### Direct-file frontier with per-line candidates

After removing recursive file traversal:

```text
directory: 380 -> 89
file:      275 -> 80
line candidates: 23,051
line request: ~18.5 MB
```

The third request failed with rate limiting. A line plus overlapping local context was too expensive as a decision-state representation.

### Compact 60-line regions

The first region representation reduced the third frontier to:

```text
files selected = 77
regions        = 462
request bytes  = 370,529
```

TypeSafe returned `max_tokens_exceeded`.

### Bounded 120-line regions

Increasing the deterministic region span to 120 lines reduced the third frontier to 267 compact questions and produced the successful three-request baseline above.

The important lesson is not that 120 lines is optimal. It is that state representation and frontier construction are harness concerns. When a frontier is too large, the first response should be to improve the representation rather than silently multiply semantic model calls.

## Controlled research directions

### 1. Threshold versus state-space accuracy

Keep Noul and the three-stage topology fixed. Sweep one threshold at a time and measure:

- frontier size at every stage;
- request tokens and latency;
- relevant-file recall and precision against a gold set;
- relevant-range overlap;
- false-prune stage;
- run-to-run stability.

The central question is how much state can be removed before useful evidence is irreversibly pruned.

### 2. Noul versus Choice

Keep the repository revision, task set, frontier generator, and state budget fixed. Compare:

- independent Noul relevance judgments;
- Choice-based selection over the same frontier.

Measure:

- multi-hit recall;
- supporting-file retention;
- probability concentration on dominant candidates;
- stability;
- tokens and latency;
- final localization quality.

The working hypothesis is that Noul is naturally suited to multi-hit localization because several candidates can be simultaneously relevant, while Choice may be useful when the harness explicitly wants a bounded competing frontier.

## Baseline status

This run is the reference point for subsequent Code Locator experiments. New experiments should change one variable at a time and report their delta against this baseline.
