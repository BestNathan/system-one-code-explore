# Nession WebSocket multi-hotspot progressive reader — 2026-09-23

## Purpose

This run validates one narrow change to the two-phase progressive reader: replace a single strongest relevance anchor with a bounded set of disconnected high-relevance regions.

All primary reader settings were held constant:

~~~text
directory threshold      = 0.50
file threshold           = 0.65
max files                = 16
file batch size          = 4
read window              = 140 lines
max rounds / batch       = 4
reader action threshold  = 0.40
observation threshold    = 0.65
~~~

Implementation change:

~~~text
high-relevance observations
  -> merge adjacent observations
  -> RelevantRegion[]
  -> keep at most 3 regions
  -> before / after actions per region
  -> one exploration-gap action
  -> StopFile
~~~

The per-file frontier remains bounded to eight total actions.

## Runs

Single-hotspot baseline:

- GitHub Actions run: 35828994234
- harness behavior: expand only around the strongest high-relevance region

Multi-hotspot run:

- GitHub Actions run: 35831659317
- subject: BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664
- model: jev-latest

## Target trace comparison

The motivating file was `crates/nession-agent/src/server/websocket.rs`.

### Before

~~~text
1-140       relevance 0.87
141-280     relevance 0.60
1585-1724   relevance 0.74   <- second hotspot discovered

next frontier:
  probe 2307-2446
  stop

selected 2307-2446 -> relevance 0.22
~~~

The second hotspot could not grow because the generator continued to anchor on the stronger 1-140 region. The model never received an action adjacent to 1585-1724.

### After

~~~text
1-140       relevance 0.87
141-280     relevance 0.54
1585-1724   relevance 0.70   <- second hotspot discovered

RelevantRegion[]:
  region 1 = 1-140       score 0.87
  region 2 = 1585-1724   score 0.70

next frontier includes:
  1725-1864  continue after region 2
  1445-1584  expand before region 2
  2307-2446  exploration gap
  stop

System One selected:
  1445-1584
  chosen probability = 0.62

observation relevance:
  0.78
~~~

This is the exact behavior the change was intended to unlock: a newly discovered secondary hotspot can now create its own local action frontier.

## Aggregate comparison

~~~text
                         single-hotspot   multi-hotspot
directories selected          40              39
files exposed                159             159
files selected                16              16
model calls                   29              29
reader decisions              48              49
reads executed                38              39
evidence observations         27              30
input tokens             340,395         355,200
output tokens             13,205          13,295
elapsed                     7.20s            9.24s
~~~

The two runs are not a perfectly deterministic A/B test because the model's Noul scores varied slightly between runs, including Phase-1 directory/file scores. The aggregate deltas therefore must not be attributed solely to multi-hotspot expansion.

The targeted trace transition is stronger evidence: under the new harness, once the second high-relevance region existed, the required neighboring actions were present and System One selected one of them, producing another high-relevance observation.

## Interpretation

The result supports a more precise reader invariant:

> Every retained disconnected high-relevance region should remain capable of expanding until its neighboring action space is exhausted or the runtime budget stops it.

This is preferable to a single global strongest anchor because source files can contain several semantically relevant implementation areas separated by unrelated code.

The harness still owns bounding:

- at most three RelevantRegion values per file;
- at most two neighbor actions per region;
- at most one exploration-gap action;
- one StopFile action;
- fixed round and file-batch budgets.

Thus multi-hotspot preservation improves local state disclosure without returning to full-file flattening.

## Follow-up research

The next issues remain intentionally separate:

1. soft versus hard round budgets when a new hotspot is discovered at the final round;
2. Phase-1 threshold calibration around the 0.60-0.65 file range;
3. batch-level read-budget allocation instead of one independent Choice per active file;
4. action confidence / probability-margin policies;
5. ReaderState compaction to reduce repeated raw-observation tokens.
