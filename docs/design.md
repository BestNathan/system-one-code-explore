# Two-Phase Code Localization with System One

## Research question

Can a fast System One model localize code by operating over a bounded, progressively disclosed state/action space without requiring an open-ended ReAct loop or a harness-defined traversal order?

Running task:

> Help me optimize the websocket connection implementation.

## Core principle

The harness should own validity and bounds, but should avoid making semantic navigation decisions that the model itself can make.

The current abstraction is:

~~~text
State
  -> ActionSpaceGenerator
  -> DecisionPrimitive
  -> Effect
  -> Observation
  -> State transition
~~~

The state/action space is progressively disclosed by real observations.

## Why earlier variants were rejected

### Transport batching

Splitting one large candidate set into batches of HTTP requests does not create semantic progress. The original pilot reached 598 model calls because transport batching and per-file line scoring scaled with candidate count.

### Recursive file expansion

Once the directory stage has enumerated every repository directory, selected directories must expose direct files only. Recursively walking selected directories reintroduces descendants that the previous decision already rejected.

### Lines / fixed regions / flat symbols

Pre-expanding file bodies into line, chunk, region, outline, or all-symbol candidate sets exposes too much interior state before the model has decided to inspect it. Source content should appear as an observation produced by an information-gathering action.

### Fixed file batches

A fixed batch adds another harness semantic decision:

~~~text
these four files first
then these four files
then these four files
~~~

Nothing in the task establishes that this ordering is meaningful. The current baseline therefore has no harness-defined file batches.

## Phase 1 — File Locator

~~~text
repository metadata
  -> directory Noul
  -> direct-file metadata
  -> file Noul
  -> PotentialFile[]
~~~

No source body is exposed in Phase 1.

Current defaults:

~~~text
directory threshold = 0.50
file threshold      = 0.65
~~~

There is no Phase-1 max-files cap. Every file above the file threshold becomes part of the Phase-2 initial state.

Phase 1 is therefore a coarse state-space boundary, not a ranking that dictates read order.

## Phase 2 — Independent File Range Runtime

The current Phase-2 baseline intentionally avoids a shared multi-file state.

Two observations drive this design:

1. System One requests have a bounded state context.
2. Once Phase 1 has selected plausible files, one file does not need another
   file's raw observations to decide which ranges inside itself should be read.

Therefore:

~~~text
PotentialFile[]
  -> FileRuntime(file A)
  -> FileRuntime(file B)
  -> FileRuntime(file C)
  -> ...
~~~

The user goal is shared. Runtime state is not.

## FileRuntime state

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

A FileRuntime owns complete durable state for exactly one file.

The model request receives a bounded DecisionView rather than the entire
durable object:

~~~text
goal

file
  path
  phase1_score
  line_count
  coverage
  read_count
  epoch

recent raw observations
  bounded mechanically by context size
~~~

The projection does not summarize or interpret text. Older observations may be
omitted from the request by a mechanical recency/size policy while remaining
in durable FileState.

## Content-agnostic action space

The v0 Harness does not parse source contents at all.

It has no language-specific concepts:

~~~text
no AST
no LSP
no symbols
no imports
no keyword extraction
no semantic chunking
~~~

This means Rust, TypeScript, Markdown, YAML, SQL, logs, and plain text use the
same runtime.

The only effect primitive is:

~~~text
ReadRange(path, start_line, end_line)
~~~

plus the control action:

~~~text
StopFile
~~~

Navigation labels only describe how a grounded range was generated.

### Unread file

~~~text
seed_head
seed_middle
seed_tail
StopFile
~~~

### Partially-read file

The Harness uses coverage geometry and previous selected ranges to generate:

~~~text
expand_before
expand_after
jump
StopFile
~~~

`expand_before/after` are adjacent to ranges selected in the previous epoch.

`jump` is a midpoint window from one of the largest unread gaps.

No text is inspected when these actions are generated.

## Decision primitives and action selection

Phase 2 contains two different decision semantics and therefore uses two
different primitives in the same request:

~~~text
StopFile / ContinueFile
  -> Choice
  -> control-flow sufficiency

ReadRange(...)
  -> Noul
  -> expected information-gathering utility
~~~

This distinction matters. Earlier experiments independently Noul-scored both
StopFile and ReadRange and then compared the numeric scores. Prompt changes
alone did not make early stopping reliable because stop sufficiency and read
utility are not the same quantity.

Current ReadRange threshold:

~~~text
parallel_action_threshold = 0.65
~~~

Selection policy:

~~~text
if Choice == StopFile:
    terminate with model_stop

if Choice == ContinueFile:
    select all ReadRange actions >= threshold
    remove overlapping effects by keeping higher-scored ranges

if no ReadRange reaches threshold:
    execute the highest-scored ReadRange
~~~

The threshold controls concurrent exploration width only. It is not a
termination threshold.

## Stop strategy

There is no Harness rule such as:

~~~text
best read score < threshold
  -> stop
~~~

`StopFile` is an explicit Choice result from System One.

Its current meaning is:

> Current observations contain enough representative evidence to finalize this
> file-level localization result. Full-file coverage and exhaustive discovery
> of every relevant range are not required.

The model is told to continue only when another range can resolve a material
uncertainty or qualitatively improve the final result.

Mechanical terminal conditions are recorded separately:

~~~text
model_stop
action_space_exhausted
budget_exhausted
error
cancelled
~~~

`action_space_exhausted` means every line range has been covered. It is not
reported as model confidence.

A safety epoch budget may still exist to bound experiments, but
`budget_exhausted` is likewise not a semantic stop.

## Loop

The core runtime is deliberately small:

~~~text
FileState
  -> generate range actions
  -> System One scores actions
  -> deterministic selection
  -> execute ReadRange effects
  -> append raw observations
  -> new FileState
  -> repeat
~~~

Equivalent pseudocode:

~~~python
state = initial_file_state(file)

while True:
    actions = generate_actions(state)
    scores = system_one.score(goal, decision_view(state), actions)
    selected = select(scores, parallel_threshold)

    if selected == StopFile:
        break

    observations = execute(selected)
    state = reduce(state, selected, observations)
~~~

No observation relevance score is used to decide whether future actions exist.

## Post-loop result scoring

Navigation and final evidence classification are separate.

After FileRuntime termination, each observed range is Noul-scored for result
relevance.

Those post-loop scores:

~~~text
do determine final evidence
do NOT affect navigation
do NOT affect StopFile
do NOT prune the action space
~~~

Evidence questions are transport-batched to remain within request context
limits.

## Phase-2 coordination

The current prototype executes FileRuntime instances sequentially for easy
trace inspection.

This is not a semantic requirement.

Because FileRuntime A and FileRuntime B share only the immutable goal, the
coordinator can later run them concurrently without changing the state-machine
model.

## Real per-file runtime trace

Run `35857120750`:

~~~text
subject:
BestNathan/nession@b76fe4921a63023a69ce91399328ab53d3526664

goal:
Help me optimize the websocket connection implementation
~~~

Phase 1 selected 17 files.

All 17 entered independent FileRuntime instances.

Aggregate:

~~~text
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

The 16 `action_space_exhausted` files all reached 100% coverage.

The only safety-budget case was:

~~~text
server/handler.rs
6617 lines
50 reads
32 epochs
94.2% coverage
~~~

Action selection across all FileRuntime epochs:

~~~text
parallel_above_threshold  42
fallback_top1             41
action_space_exhausted    16
~~~

Selected read actions:

~~~text
jump           77
expand_after   21
expand_before  11
seed_head      17
seed_middle     6
seed_tail       6
~~~

This confirms the core policy:

- the parallel threshold controls concurrency;
- low scores still advance through top-1;
- no low-score Harness stop exists;
- file-local state stays within the bounded request model.

The main unresolved behavior is `StopFile`: no file chose an early
`model_stop`. The current model is conservative and generally explores until
the file is exhausted.

The next stop experiment should change only StopFile semantics/prompting. It
should explicitly state that full-file coverage is not required once enough
evidence exists to judge the file.

See:

~~~text
pilots/nession-websocket-per-file-range-runtime-v0-2026-09-23.md
~~~

## Historical global-scheduler experiment

The previous baseline placed all Phase-1 files into one shared ReaderState and
used a global file-activation request before local reads.

That experiment demonstrated that fixed batches were unnecessary, but it is no
longer the current Phase-2 architecture.

Its main findings remain useful historical evidence:

- global scheduling reduced reads aggressively;
- activation thresholds could accidentally become an implicit stop rule;
- one shared state grows poorly as observations accumulate;
- request-context limits make a multi-file raw-observation state undesirable.

The per-file runtime keeps the useful idea of model-directed range exploration
while removing cross-file Phase-2 scheduling.

## Claude Code cross-trace methodology

Claude Code + `ds` is recorded as a separate System-2 trajectory, not ground truth and not an optimization target.

The manual workflow:

~~~text
.github/workflows/system-one-code-locator-accuracy.yml
~~~

uses the historical filename but now records a cross-trace.

Claude is intentionally split into two fresh sessions:

~~~text
Session A — localization
  repository tools enabled
  decides files / roles / reasons / evidence ranges
  confidence is forbidden

Session B — confidence assessment
  new session
  repository tools disabled
  receives the immutable Session-A draft plus materialized evidence source
  assigns overall / file / evidence confidence only
~~~

Session B cannot change file paths, ordering, evidence counts, or evidence ranges. The finalizer validates those invariants before producing the canonical result.

Artifacts include:

~~~text
localization.raw.jsonl
localization-draft.json
localization-manifest.json
execution-path.json
execution-summary.md

confidence.raw.jsonl
confidence-manifest.json
confidence-summary.md

localization-result.json
manifest.json
~~~

The localization raw stream preserves every repository-search event. The normalized execution path records ordered Read / Grep / Glob / Bash calls, inputs, errors, and result-size/preview metadata.

Run `35839323377` recorded:

~~~text
42 Claude tool calls
  24 Read
   2 Grep
  16 Bash
43 turns
79.8s
~~~

Its sequence progressed from repository inspection and broad websocket grep to server/agent websocket files, connection clients, web transport, session runtime, MessageRouter, handler/broker/registry paths, and additional targeted regions.

That trajectory can be compared with System One's much narrower global-scheduler trajectory without assuming that either final file set is the correct answer.

See:

~~~text
pilots/nession-websocket-global-scheduler-cross-trace-2026-09-23.md
~~~

## Historical findings retained

### Multi-hotspot

A single strongest relevance anchor prevented a second high-relevance region from expanding. The reader now retains several disconnected `RelevantRegion[]` anchors.

### Fixed round budget

A hard four-round loop could stop immediately after discovering a new hotspot. Read continuation became evidence-driven and file-scoped.

### Batch-scoped continuation

One high-signal file could previously keep low-value sibling files alive. Continuation ownership was moved to the file.

These findings remain historical inputs. The current v0 no longer uses a global scheduler, relevance-gated expansion, or file activation.

## Research studies

1. StopFile semantics: encourage sufficiency without Harness-driven stopping.
2. Range frontier geometry: seed / expand / jump density and redundancy.
3. Concurrent coordination of independent FileRuntime instances.
4. Mechanical DecisionView context budgeting for very large files.
5. Phase-1 threshold replay on frozen score snapshots.
6. Multi-task cross-traces using the per-file runtime baseline.
7. Human-reviewed gold datasets only when an absolute accuracy claim is required.

## Shared harness model

The code reader and Kubernetes System One experiment converge on the same abstraction:

~~~text
State
  -> grounded ActionSpace
  -> System One decision
  -> Effect
  -> Observation
  -> State transition
~~~

The harness provides valid bounded actions. The model decides which semantic direction to take.


## Canonical localization result

Execution strategy and final result are separate contracts.

~~~text
ExecutionTrace
  = how the system searched, decided, and observed

LocalizationResult
  = which files and source regions it ultimately considers valuable
~~~

Both System One and Claude Code now emit the same `code-localization-result` schema. The common comparison layer consumes this schema only; it does not depend on System One's internal ReaderState or Claude's tool protocol.

File and evidence confidence explicitly retain their semantics (`noul_relevance`, `derived_max_evidence_relevance`, or `model_self_assessment`) because these numbers are not assumed to be calibrated against each other.

See [localization-result.md](localization-result.md).


### Cost as part of the result

Localization quality and execution cost are both result dimensions. The canonical result therefore carries:

~~~text
elapsed_ms
api_elapsed_ms
model_calls
turns
tool_calls

tokens
  input
  output
  cache_read_input
  cache_creation_input
  thinking

provider_cost_usd
stages[]
~~~

System One currently has one localization stage. Claude has two independent stages, localization and confidence assessment, and the final cost is their sum. Missing provider metrics remain null rather than being estimated.


### Stop control experiment

Clean run `35864316780` validates the current Choice-based control decision.

~~~text
17 file runtimes
4 model_stop
12 action_space_exhausted
1 budget_exhausted

134 reads
130 model calls
1,272,639 input tokens
25.952 s
~~~

The four genuine model stops happened before coverage exhaustion:

~~~text
server/websocket.rs        91.3%
WebSocketService.ts        77.5%
CLI connection.rs          86.0%
web_client_registry.rs     99.3%
~~~

On the four common stopped files, the earlier exhaustive baseline used 24 reads
while this run used 17. Evidence-line overlap with the earlier run ranged from
0.775 to 1.000. Because System One scoring is stochastic, this is descriptive
rather than a controlled accuracy estimate.

The largest files still tend to continue until full coverage or the safety
budget. The next stopping research should expose explicit exploration cost or
diminishing-return state to the model, rather than reintroducing a
Harness-owned low-score stop heuristic.
