# Large-Repository File Discovery: State / Prompt / System2 Benchmark

## Goal

Extend the converged File Discovery V1 mechanism from one medium repository to two substantially larger, independently designed codebases, while isolating whether System One quality/cost changes come from instructions or state representation.

Repositories are frozen:

- `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- `openclaw/openclaw@932abb0a841b522ebaa5b81921119a61b6a80b21`
- `openai/codex@d7b07d45517a793acfba4cbf8de697d723cceb46`

Each repository contributes three tasks from different subsystems or engineering intents.

## System One profiles

### A — `baseline_v1`

Current canonical V1:

- file metadata: path, filename, extension, size;
- generic independent Noul question;
- no repository-level semantic state.

### B — `instruction_v2`

State is intentionally unchanged from A.

Only the decision contract changes:

- judge the exact file, not its directory;
- independent multi-hit relevance, never relative ranking;
- primary implementation and directly necessary supporting implementation count;
- use full path compositionally;
- generic container names are weak evidence, specific leaf directory/filename semantics are stronger;
- do not require exact task-keyword overlap when architecture conventions imply ownership;
- do not retain tests/config/contracts from name coincidence alone.

This arm measures **instruction effect**.

### C — `enriched_state_v3`

Uses B's instructions and adds deterministic, source-free state:

- path segments;
- tokenized path/stem semantics;
- parent segments;
- repository file count;
- top-level file distribution;
- extension/language distribution.

This arm measures the incremental value and cost of **state representation**.

No arm can read source.

## Selection policy

All three profiles use exactly the same downstream selection rule:

```text
score >= 0.65
OR
top-1% relative recall guard
```

Therefore changes in recall/selectivity before System2 comparison come only from System One score fields, not different selection policies.

## System2 arm

One independent System2 run per task, shared by all three System One profile comparisons.

System2 may use `Read`, `Glob`, and `Grep` against source. It cannot edit, use Bash, web/network context, git history, MCP, or subagents.

System2 is not treated as ground truth. Both systems are evaluated against the same frozen primary target file(s). File-set overlap is descriptive.

## Frozen tasks

### Nession

1. reconnect lifecycle;
2. symlink/delete filesystem safety;
3. frontend request correlation.

### OpenClaw

1. Gateway WebSocket handshake/RPC dispatch;
2. workspace skill source discovery/precedence;
3. built-in memory hybrid retrieval orchestration.

### Codex

1. command approval/reviewer routing;
2. MCP tool invocation/approval;
3. thread create/resume/persistence wiring.

Full wording and primary paths are pinned in `fixtures/file-discovery/system1-vs-system2-cases.json`.

## Metrics

Primary quality:

- primary target recall;
- selected file count.

System One cost:

- enumerated file count;
- model calls;
- input/output tokens;
- model wall time;
- Jev USD at the pinned pricing snapshot.

System2 cost:

- tool calls;
- turns;
- input/cache/output usage reported by the runtime;
- wall time;
- provider-reported USD cost.

Profile comparison:

- A -> B isolates instruction effect;
- B -> C isolates state effect;
- all comparisons report delta recall/selectivity/calls/tokens/time/cost.

## Research questions

1. Does all-file metadata scoring maintain primary recall as repository size grows?
2. Does stronger instruction reduce false-positive file selection without hurting recall?
3. Does enriched deterministic state recover ambiguous primary files that path-only instructions miss?
4. Is any quality gain worth the extra prompt tokens?
5. At what repository size does all-file scoring become a cost bottleneck even if Jev remains cheaper/faster than System2?

## Workflow

`.github/workflows/file-discovery-system1-vs-system2.yml` auto-triggers on changes to the benchmark/runtime/profile/workflow files.

The workflow still hard-gates paid execution with `github.actor == BestNathan`. Pushes from other actors may create the workflow shell, but cannot enter System One or System2 paid jobs.

Result docs and pinned aggregate files are intentionally not trigger paths, so recording conclusions does not rerun the paid benchmark.