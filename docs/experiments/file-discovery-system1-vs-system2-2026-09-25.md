# File Discovery — System One vs System2

## Question

Can the converged metadata-only System One File Discovery V1 recover the primary task files with materially lower latency and dollar cost than a normal System2 coding-agent repository investigation?

## Controlled subject

- repository: `BestNathan/nession`
- revision: `7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- identical verbatim task per arm

## System One arm

File Discovery V1:

- mechanically enumerate all supported file metadata;
- no source body;
- independent Jev Noul score per file;
- select `score >= 0.65` OR top-1% relative recall guard;
- no directory semantic pruning;
- no top-k;
- terminate when every file has one score.

Cost is calculated using the pinned TypeSafe pricing snapshot.

## System2 arm

Claude Code performs an independent repository investigation:

- pinned Claude Code client;
- explicit configured model;
- high effort;
- tools: `Read`, `Glob`, `Grep` only;
- no Bash, edits, web, git history, issues, MCP, subagents, or external context;
- source reading is allowed;
- final output is a ranked `primary|supporting|context` file set.

System2 is not ground truth. Both arms are evaluated against the same frozen primary-target file(s). File-set overlap is descriptive only.

## Frozen tasks

### 1. Backend reconnect lifecycle

Direction: backend networking/state lifecycle. Language: Rust.

Primary target: `crates/nession-agent/src/connection/server_client.rs`.

### 2. Filesystem symlink/delete safety

Direction: filesystem correctness/safety. Language: Rust.

Primary target: `crates/nession-agent/src/fs/sandbox.rs`.

### 3. Frontend request correlation

Direction: frontend realtime messaging. Language: TypeScript.

Primary target: `web/src/platform/socket/MessageRouter.ts`.

Tasks are frozen in `fixtures/file-discovery/system1-vs-system2-cases.json`.

## Metrics

Per arm:

- primary target recall;
- selected file count;
- input/output token usage;
- model/tool calls;
- model/runtime wall time;
- USD cost.

Descriptive cross-arm metrics:

- file-set intersection;
- Jaccard overlap;
- files unique to each method;
- System2/System1 cost ratio;
- System2/System1 latency ratio.

## Workflow security

Canonical workflow: `.github/workflows/file-discovery-system1-vs-system2.yml`.

It has only `workflow_dispatch` as a trigger.

An explicit authorization job requires `github.actor == BestNathan` before any paid System One/System2 jobs execute.

GitHub repository permissions still control who can see/click the dispatch action; the workflow guard prevents any other actor from entering paid benchmark jobs.