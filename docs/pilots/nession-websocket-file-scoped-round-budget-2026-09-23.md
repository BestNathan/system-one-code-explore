# Nession WebSocket file-scoped round budget — 2026-09-23

## Purpose

The preceding soft/hard budget run proved that a relevant observation discovered at round four can earn a follow-up round, but continuation was granted at batch scope. One promising file could therefore keep unrelated sibling files active.

This experiment narrows only that behavior: each file must earn its own post-soft-limit continuation.

## Run

- GitHub Actions run: 35833457198
- subject: BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664
- model: jev-latest

## Policy

~~~text
normal rounds: 1..4

at / after round 4:
  for each active file:
    new observation relevance >= 0.65?
      yes -> keep that file active for one more round
      no  -> stop that file with soft_budget_no_high_signal

batch continues while at least one file remains active
hard cap = 8 rounds
~~~

Multi-file Choice remains unchanged during each active round. The change only affects which files are allowed into the next round.

## Aggregate result

~~~text
directories exposed            = 380
directories selected           = 41
files exposed                  = 160
files selected                 = 16

reader batches                 = 4
reader decisions               = 58
reads executed                 = 46
observations                   = 46
evidence observations          = 34

batch extension rounds         = 7
file extension grants          = 10
files stopped by soft budget   = 4
batches extended               = 3
hard-budget hits               = 0

model calls                    = 42
input tokens                   = 621,102
output tokens                  = 13,865
elapsed                        = 11.32s
~~~

The model's Phase-1 scores and later exploration choices drift between runs, so aggregate call/token differences must not be interpreted as a controlled cost comparison. The file-level trace transitions are the primary evidence.

## Target sibling-overextension case

In the batch-scoped run, `crates/nession-agent/src/connection/server_client.rs` kept its batch alive and `crates/nession-cli/src/client/connection.rs` received two extra reads whose relevance was 0.38 and 0.22.

In this file-scoped run, the CLI connection path was:

~~~text
round 1: 1-140       relevance 0.88
round 2: 141-280     relevance 0.83
round 3: 281-420     relevance 0.77
round 4: 421-560     relevance 0.64

0.64 < 0.65
-> reader_file_soft_budget_stop
-> no round 5
-> no round 6
~~~

The sibling `server_client.rs` independently earned continuation:

~~~text
round 4: 421-560     relevance 0.82
round 5: 561-700     relevance 0.81
round 6: 701-840     relevance 0.70
round 7: 841-980     relevance 0.25
-> stop
~~~

This demonstrates the intended distinction:

~~~text
batch = concurrent decision context
file  = continuation / budget ownership
~~~

## Original motivating case still works

`crates/nession-server/src/server/handler.rs` still receives the extra round that motivated the soft-budget design:

~~~text
round 4: 3449-3588  relevance 0.72
-> file earns round 5

round 5 frontier includes neighbors of the new hotspot
selected 3309-3448
relevance 0.33
-> stop
~~~

So file-scoped continuation removes sibling over-expansion without reintroducing the fixed-four-round failure.

## Comparison of budget designs

~~~text
fixed round budget:
  every file stops after round 4

batch-scoped soft budget:
  any high-signal file keeps the whole active batch alive

file-scoped soft budget:
  each file independently earns the next round
  batch continues only for remaining eligible files
~~~

The file-scoped version is the new baseline.

## Remaining research

1. calibrate Phase-1 file threshold around 0.60 / 0.625 / 0.65;
2. compare per-file Choice with a true batch-level global read budget;
3. study chosen probability, confidence, margin, and entropy as execution gates;
4. compact old ReaderState observations to reduce repeated input tokens;
5. add an explicit sufficiency / done decision separate from relevance.
