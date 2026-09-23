# Nession WebSocket evidence-driven round budget — 2026-09-23

## Purpose

This experiment changes one reader variable after the multi-hotspot baseline: replace the fixed four-round termination rule with a soft/hard round budget.

All other primary controls remain unchanged:

~~~text
directory threshold      = 0.50
file threshold           = 0.65
max files                = 16
file batch size          = 4
read window              = 140 lines
reader action threshold  = 0.40
observation threshold    = 0.65

soft rounds              = 4
hard rounds              = 8
~~~

At or beyond the soft limit, another round is granted only when the just-completed round produced at least one new observation above the observation threshold. The hard limit remains unconditional.

## Run

- GitHub Actions run: 35833091673
- subject: BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664
- model: jev-latest

## Aggregate result

~~~text
directories exposed      = 380
directories selected     = 36
files exposed            = 150
files selected           = 16

reader batches           = 4
reader decisions         = 60
reads executed           = 48
observations             = 48
evidence observations    = 33

soft-budget extensions   = 6
batches extended         = 3
hard-budget hits         = 0

model calls              = 41
input tokens             = 604,249
output tokens            = 13,770
elapsed                  = 12.21s
~~~

## Target trace: handler.rs

The motivating case was `crates/nession-server/src/server/handler.rs`. In the previous fixed-four-round baseline, round four discovered a new high-relevance hotspot and the loop terminated before the hotspot could generate a follow-up action.

This run produced:

~~~text
round 1: 1-140       relevance 0.81
round 2: 141-280     relevance 0.74
round 3: 281-420     relevance 0.60

round 4:
  action: probe 3449-3588
  chosen probability: 0.96
  relevance: 0.70

  -> reader_budget_extended

round 5 frontier:
  3589-3728  continue after hotspot
  3309-3448  expand before hotspot
  5033-5172  exploration gap
  stop

round 5 decision:
  3309-3448
  chosen probability: 0.43
  relevance: 0.29

  -> reader_soft_budget_stop
~~~

The soft budget therefore solved the exact failure mode: the new round-four hotspot was allowed to disclose its own local action frontier. The low relevance of the follow-up observation then stopped further expansion.

## Longer extension chains

Three of four batches crossed the soft limit.

Batch 0 extended through round 7. Relevant observations kept earning additional rounds at rounds 4, 5, and 6, then round 7 produced no new high-relevance observation and stopped.

Batch 1 extended through round 6. `server_client.rs` produced 0.84 at round 4 and 0.83 at round 5; round 6 fell below threshold and stopped.

Batch 3 is the `handler.rs` case above and extended only to round 5.

No batch reached the hard limit of eight.

## Cost comparison

Compared with the preceding multi-hotspot fixed-four-round run:

~~~text
                         fixed 4 rounds    soft 4 / hard 8
model calls                    29                 41
reads                          39                 48
evidence observations          30                 33
input tokens              355,200            604,249
output tokens              13,295             13,770
elapsed                      9.24s              12.21s
~~~

The runs contain normal model-score drift, so aggregate quality deltas are not causal measurements. The targeted `handler.rs` transition is the stronger validation of the budget mechanism.

## New defect: batch-level continuation over-expands sibling files

The current implementation grants an extra round to the entire active batch when any file produces a new high-relevance observation.

For example, batch 1 was kept alive by `crates/nession-agent/src/connection/server_client.rs`, but `crates/nession-cli/src/client/connection.rs` also received two extra reads:

~~~text
cli connection round 5: relevance 0.38
cli connection round 6: relevance 0.22

server_client round 5: relevance 0.83
server_client round 6: relevance 0.60
~~~

The sibling file did not earn those extra rounds itself. This is unnecessary IO and increases the already-visible ReaderState token accumulation cost.

## Next change

Move soft-budget continuation from batch scope to file scope:

~~~text
at/after soft round:
  for each active file:
    did this file produce a new high-relevance observation?
      yes -> keep file active
      no  -> stop/defer this file

batch continues while any file remains active
hard round cap still applies to the batch
~~~

This keeps the requested multi-file concurrent Choice behavior during normal rounds, while preventing one promising file from subsidizing unrelated extra reads in sibling files.
