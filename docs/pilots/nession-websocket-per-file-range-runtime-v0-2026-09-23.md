# Nession WebSocket — Per-file Range Runtime v0 — 2026-09-23

## Motivation

TypeSafe System One constrains each request to a bounded context. In particular,
the model state plus the longest question must remain within the state context
budget.

That makes one shared Phase-2 state containing every candidate file and every
observation an awkward abstraction.

More importantly, code localization does not require Phase-2 files to reason
about each other. Once Phase 1 has selected plausible files, each file can
answer the same independent question:

> Which ranges in this file materially help localize content relevant to the goal?

The v0 runtime therefore removes the global file scheduler.

## Architecture

~~~text
Phase 1
  repository metadata
    -> directory Noul
    -> direct-file Noul
    -> PotentialFile[]

Phase 2
  PotentialFile A -> FileRuntime A
  PotentialFile B -> FileRuntime B
  PotentialFile C -> FileRuntime C
  ...

Each FileRuntime:
  FileState
    -> generate range-only ActionSpace
    -> System One Noul score for every action
    -> deterministic selector
    -> execute selected ReadRange actions
    -> append raw observations
    -> new FileState
    -> repeat
~~~

File runtimes do not share observations or navigation decisions.

The only semantic input shared across files is the user goal.

## FileState

~~~text
FileState
  path
  phase1_score
  line_count
  size_bytes
  extension

  epoch
  coverage[]
  observations[]
  last_selected_ranges[]
  read_count
  termination
  action_history[]
~~~

The durable FileState retains all observations.

The System One DecisionView is a bounded projection containing only:

~~~text
goal
file metadata
coverage
read_count
epoch
recent raw observations within a mechanical character budget
~~~

No AST, LSP, symbols, imports, keywords, semantic chunks, or source parsing are
used.

## Action-space generation

The Harness only understands range geometry.

### Unread file

~~~text
ReadRange(head)
ReadRange(middle)
ReadRange(tail)
StopFile
~~~

### Partially-read file

Around ranges selected in the previous epoch:

~~~text
ReadRange(expand_before)
ReadRange(expand_after)
~~~

For global exploration inside the same file:

~~~text
ReadRange(jump)
~~~

Jump targets are the midpoint windows of the largest unread gaps.

The Harness never reads the target content while generating actions.

All read actions use the same effect:

~~~text
ReadRange(path, start_line, end_line)
~~~

Navigation labels such as `seed_head`, `expand_after`, and `jump` are only
descriptions of how the grounded range was generated.

## Selector

Current threshold:

~~~text
parallel_action_threshold = 0.65
~~~

The threshold controls concurrency only.

~~~text
if StopFile >= threshold
   and StopFile >= best ReadRange:
    stop this FileRuntime

else:
    execute every non-overlapping ReadRange >= threshold

if no ReadRange >= threshold:
    execute the highest-scored ReadRange
~~~

A low action score never causes Harness termination.

If multiple above-threshold ranges overlap, the selector greedily retains the
higher-scored non-overlapping actions. This is a deterministic effect-conflict
rule rather than semantic pruning.

## Stop semantics

`StopFile` is an explicit model action.

Its scoring question tells System One to raise the score when current
observations are sufficient for judging this file and further reads are
unlikely to materially improve localization.

The Harness does not infer stop from low read scores.

Mechanical terminal reasons remain distinct:

~~~text
model_stop
action_space_exhausted
budget_exhausted
error / cancelled
~~~

## Result scoring

Navigation and result classification are separated.

After a FileRuntime terminates, every observed range is independently scored
for evidence relevance. These scores do not affect the navigation loop or
stopping behavior.

Evidence scoring is transport-batched so that many observations do not exceed
the request context limit.

## Real run

GitHub Actions run:

~~~text
35857120750
~~~

Subject:

~~~text
BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664
~~~

Task:

~~~text
Help me optimize the websocket connection implementation
~~~

Model:

~~~text
jev-latest
~~~

Configuration:

~~~text
directory threshold       0.50
file threshold            0.65
parallel action threshold 0.65
result evidence threshold 0.65
window                    140 lines
max jumps                 2
max file epochs           32
~~~

Aggregate:

~~~text
Phase-1 selected files     17
FileRuntime instances      17

model_stop                  0
action_space_exhausted     16
budget_exhausted            1

reads executed            138
valuable files             11
evidence regions           46

model calls               145
input tokens        1,316,145
output tokens          19,858
elapsed               33.243 s
~~~

The per-file architecture completed without the previous shared-state context
overflow.

## Coverage behavior

Sixteen files reached 100% coverage and terminated because there were no unread
ranges left.

The only safety-budget termination was:

~~~text
crates/nession-server/src/server/handler.rs
line count  6617
reads         50
epochs        32
coverage    94.2%
termination budget_exhausted
~~~

Representative runtimes:

~~~text
server/websocket.rs
  767 lines
  8 reads
  5 epochs
  100% coverage

WebSocketService.ts
  542 lines
  5 reads
  3 epochs
  100% coverage

agent/server/websocket.rs
  3030 lines
  31 reads
  19 epochs
  100% coverage

server_client.rs
  2858 lines
  21 reads
  10 epochs
  100% coverage
~~~

## Action behavior

Across all file runtimes:

~~~text
parallel_above_threshold  42 epochs
fallback_top1             41 epochs
action_space_exhausted    16 epochs
~~~

Selected read navigation:

~~~text
jump           77
expand_after   21
expand_before  11
seed_head      17
seed_middle     6
seed_tail       6
~~~

This validates the intended threshold semantics:

- high-confidence actions can execute concurrently;
- when nothing reaches the threshold, exploration still advances through top-1;
- low scores do not trigger Harness stop.

## Example: server websocket

The 767-line server websocket file began with three concurrent seed reads:

~~~text
1-140      head    0.84
313-452    middle  0.78
628-767    tail    0.71
StopFile           0.07
~~~

Epoch 2 generated both local expansion and gap jumps. The selector removed
overlapping effects and executed:

~~~text
156-295    jump          0.83
453-592    expand_after  0.83
~~~

Subsequent gap probes completed the remaining coverage.

The file terminated with `action_space_exhausted`, not because a read fell
below a threshold.

## Example: agent websocket

The 3030-line agent websocket runtime demonstrates the intended explore /
expand behavior without text parsing.

Initial probes:

~~~text
1-140       head    0.81
1445-1584   middle  0.73
2891-3030   tail    0.66
~~~

The next epochs mixed:

~~~text
1305-1444   expand_before
1585-1724   expand_after
722-861     jump
2167-2306   jump
141-280     expand_after
...
~~~

When high-confidence actions disappeared, the runtime did not stop. It
continued with the highest-scored unread range until coverage was exhausted.

This also recovered evidence around the previously interesting 1305-1584
region without any symbol extraction or LSP.

## Stop finding

The strongest result of this run is that `StopFile` did not win early for any
of the 17 files.

For large files its score generally remained around 0.2-0.3 even after the
highest available read action fell below the parallel threshold.

Therefore the current semantics are conservative:

~~~text
uncertainty remains
  -> keep exploring

no high-confidence read
  -> top-1 exploration

eventually
  -> full traversal or safety budget
~~~

This is correct with respect to the v0 rule that the Harness must not stop
because of low confidence.

It is not yet efficient.

The next stop experiment should change only the wording/meaning of StopFile,
not reintroduce Harness thresholds as terminal conditions. In particular,
System One should be told explicitly that full-file coverage is not required:
once the observed evidence is sufficient to judge the file for the user goal,
it should raise StopFile even if unread ranges remain.

## Current conclusion

The 32k state constraint suggests a cleaner architecture rather than a
workaround:

~~~text
Phase 1 chooses the file domain.

Phase 2 does not schedule files globally.

Each file owns an independent bounded state machine:
  State
    -> geometry-only ActionSpace
    -> System One scores actions
    -> threshold controls concurrency
    -> Effects
    -> Observations
    -> State

StopFile is a model action, not a Harness heuristic.
~~~

This structure is language-agnostic and works equally for source code,
Markdown, YAML, SQL, logs, and plain text.


## StopFile control experiment

The initial v0 represented both ReadRange and StopFile as independently scored
Noul actions. This produced almost no early stopping. The core issue is that
the two decisions do not have the same semantics:

~~~text
ReadRange score
  = expected information-gathering utility

StopFile
  = control-flow sufficiency decision
~~~

Comparing those values directly biased the runtime toward continuing.

Several prompt-only experiments confirmed that wording alone was insufficient.
Even when StopFile was described as result sufficiency or marginal utility,
the model usually raised its stop score only near complete coverage.

### Revised primitive

StopFile is now a binary control decision using Choice:

~~~text
Choice:
  stop
  continue

Noul:
  one score per ReadRange
~~~

Both question types are sent in the same System One request and share the same
file-local DecisionView.

The runtime policy is:

~~~text
if Choice == stop:
    model_stop

if Choice == continue:
    execute all non-overlapping ReadRanges >= 0.65

if no ReadRange >= 0.65:
    execute top-1 ReadRange
~~~

The 0.65 threshold therefore controls ReadRange concurrency only. It is not a
StopFile threshold.

The StopFile prompt also makes the output objective explicit: localization
needs representative, useful evidence, not an exhaustive catalog of every
relevant range in the file.

### Clean real validation

Run:

~~~text
35864316780
~~~

completed with:

~~~text
Phase-1 files             17
FileRuntime instances     17

model_stop                 4
action_space_exhausted    12
budget_exhausted           1

reads                    134
valuable files            10
evidence regions          40

model calls              130
input tokens        1,272,639
output tokens          20,362
elapsed               25.952 s
~~~

The four genuine model stops all occurred while unread ranges remained:

~~~text
server/websocket.rs
  coverage 91.3%
  reads 5
  Stop choice at epoch 3
  P(stop) 0.50

WebSocketService.ts
  coverage 77.5%
  reads 3
  Stop choice at epoch 2
  P(stop) 0.62

CLI connection.rs
  coverage 86.0%
  reads 7
  Stop choice at epoch 4
  P(stop) 0.60

web_client_registry.rs
  coverage 99.3%
  reads 2
  Stop choice at epoch 2
  P(stop) 0.87
~~~

The runtime first checks whether any ReadRange remains. If none remains, it
terminates mechanically as action_space_exhausted without asking the model for
a redundant Stop/Continue decision.

### Evidence trade-off

The original per-file baseline run 35857120750 had no early model stops.

For the four common files that now stopped early:

~~~text
                                      reads      evidence-line Jaccard
server/websocket.rs                    8 -> 5          0.913
WebSocketService.ts                    5 -> 3          0.775
CLI connection.rs                      8 -> 7          0.878
web_client_registry.rs                 3 -> 2          1.000
~~~

These numbers compare two stochastic System One runs, so they are observations,
not a controlled accuracy measurement.

They still illustrate the intended trade-off clearly:

- stopping can avoid redundant tail exploration;
- stopping can also omit ranges that another run later retained as relevant;
- representative localization and exhaustive localization are different
  objectives.

The biggest unresolved files remain the multi-thousand-line agent websocket,
server_client, and handler. System One still chose continue until full coverage
or the safety budget for those files. Further stopping work should therefore
focus on explicit exploration cost / diminishing-return state rather than
reintroducing Harness-driven low-score termination.
