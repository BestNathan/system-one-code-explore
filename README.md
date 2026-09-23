# System One Code Explorer

A research runtime for using **System One models as fast policies over progressively disclosed code-exploration state and action spaces**.

This repository continues the code-localization research originally developed in `BestNathan/narness-engineering`. The project is intentionally broader than a locator: the goal is to evolve from adaptive line-range search into a reusable **System One code exploration runtime**.

## Core idea

System One is not treated as a small ReAct agent. The harness owns state, action-space construction, effects, budgets, traces, and lifecycle. The model performs fast local decisions:

```text
State
  ↓
Harness builds a bounded ActionSpace
  ↓
System One policy / utility decisions
  ↓
Effect
  ↓
Observation
  ↓
State transition
  ↺
```

The current implementation uses two phases:

1. **Repository filtering** — score directories and files to select candidate files.
2. **Independent FileRuntime exploration** — generate geometric `ReadRange` and `StopFile` actions, let System One choose stop/continue and score concrete reads, then update coverage and observations.

Navigation and final evidence scoring are intentionally separated.

## Current algorithm

For an unread file, the harness exposes head / middle / tail probes. After observations exist, it exposes:

- `expand_before` and `expand_after` around ranges selected in the previous epoch;
- midpoint probes over the largest unread gaps;
- `StopFile`.

System One answers:

- a **Choice**: `StopFile` or `ContinueFile`;
- **Noul utility scores** for concrete `ReadRange` actions.

When the control decision contradicts the best concrete read, a second explicit reconciliation Choice resolves:

- stop + high-utility read;
- continue + no high-utility read.

This removed the previous unconditional low-score `fallback_top1` tail that tended to scan large files almost exhaustively.

## Latest end-to-end benchmark

Task:

`Help me optimize the websocket connection implementation`

Frozen subject:

`BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`

Successful cross-trace run: `35890516881`.

| Metric | System One | Claude Code-style System 2 |
| --- | ---: | ---: |
| Runtime | 22.743s | 96.347s |
| Model calls / turns | 96 calls | 40 turns |
| Reads / tool calls | 96 reads | 38 tool calls |
| Input tokens | 724,127 | 75,469 |
| Cache-read input | — | 624,384 |
| Output tokens | 17,427 | 21,045 |
| Blind quality | 71/100 | 83/100 |
| Evaluator can proceed | yes | yes |

The System 2 side used Claude Code as the harness with `deepseek-flash` as the configured model in that run.

Overlap on the same frozen source revision:

- shared files: 8;
- union files: 17;
- file Jaccard: 47.1%;
- Claude evidence covered by System One: **66.7% of regions / 69.9% of lines**.

Three repeated System One runs on the same frozen task/revision after Stop reconciliation used 94, 86, and 96 reads respectively, showing stable convergence rather than one lucky stop.

## What the benchmark says

The current runtime is already useful: the blind evaluator marked the System One result `can_proceed=true`. The main gap is no longer stopping. It is **state-space expansion and evidence shaping**.

The evaluator specifically exposed missing cross-file dependencies such as `MessageRouter.ts`, `command_broker.rs`, and `client_registry.rs`, even when observations contained clues pointing toward them.

The next architectural step is therefore:

```text
Observation
   ↓
discover new state / dependency
   ↓
progressively disclose new actions
   ↓
ReadRange(...)
FollowFile(...)
FollowSymbol(...)
InspectCaller(...)
InspectCallee(...)
```

## Repository layout

- `src/system_one_range_runtime.py` — current per-file adaptive range runtime.
- `src/system_one_code_locator.py` — shared System One API and earlier locator primitives.
- `src/localization_result.py` — canonical localization result contract.
- `src/localization_quality_evaluation.py` — blind downstream-quality evaluator.
- `src/compare_localization_results.py` — symmetric file/range comparison.
- `src/claude_*.py` — System 2 reference tracing and confidence normalization.
- `tests/` — deterministic regression tests.
- `fixtures/` — offline fixture repository.
- `docs/` — design notes and historical pilot reports.
- `ROADMAP.md` — next research milestones.

## Running offline tests

```bash
python3 -m unittest discover -s tests -v
```

## Running the System One range runtime

```bash
export TYPESAFE_API_KEY=...
export TYPESAFE_API_URL=https://api.typesafe.ai/v1/systemone

python3 src/system_one_range_runtime.py \
  /path/to/repository \
  "Help me optimize the websocket connection implementation" \
  --window-lines 140 \
  --parallel-threshold 0.65 \
  --evidence-threshold 0.65 \
  --max-jumps 2 \
  --max-file-epochs 32
```

## Research direction

The long-term question is not whether a System One model can read code. It is:

> How strong can a harness become when it progressively discloses state and legal actions, while a fast System One model only chooses how to advance the state machine?

See [ROADMAP.md](ROADMAP.md) and [docs/research-summary.md](docs/research-summary.md).
