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

## Canonical result

Bootstrap execution: `36107671466`.

The final reusable workflow remains manual-only; this bootstrap run was used
only to obtain the initial canonical comparison.

Actual System2 configuration resolved by the `ds` environment:

```text
Claude Code client: @anthropic-ai/claude-code@2.1.278
model: deepseek-flash
tools: Read, Glob, Grep
effort: high
```

### Aggregate

| metric | System One V1 | System2 |
| --- | ---: | ---: |
| primary recall | **100%** | **100%** |
| mean selected files | 13.3 | 15.3 |
| model/tool calls | 18 model calls | 30.7 tool calls |
| mean wall time | **6.87 s** | 44.68 s |
| mean USD cost | **$0.00885** | $0.74021 |

Using the observed provider cost from the configured System2 environment:

```text
System2 / System One cost ratio ~= 83.6x
System2 / System One wall-time ratio ~= 6.5x
```

System One cost uses the pinned TypeSafe Jev list-price snapshot. System2 cost
uses Claude Code's provider-reported `modelUsage.costUSD`; the configured
provider reports `costBasis=unknown`, so this should be interpreted as the
observed environment cost, not a normalized public-list-price comparison.

### Per case

| case | S1 recall | S2 recall | S1 cost | S2 cost | S1 time | S2 time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| backend reconnect lifecycle | 100% | 100% | $0.00869 | $1.19471 | 7.16s | 58.93s |
| filesystem symlink/delete safety | 100% | 100% | $0.00893 | $0.56430 | 4.08s | 39.58s |
| frontend request correlation | 100% | 100% | $0.00893 | $0.46161 | 9.36s | 35.52s |

### Search-shape difference

The experiment compares two materially different ways of finding files.

System One:

```text
1,096 file metadata records
  -> independent parallelizable Noul decisions
  -> RelevantFile[]
```

System2:

```text
task
  -> Glob / Grep
  -> Read source
  -> update hypothesis
  -> more search / reads
  -> final file set
```

For the backend reconnect task, for example:

- System One: 18 Jev requests, 7.16s, $0.00869;
- System2: 37 repository tool calls / 38 turns, 58.93s, $1.19471.

Both recovered
`crates/nession-agent/src/connection/server_client.rs`.

The file sets do not strongly coincide (backend Jaccard = 0.20), which is
expected: only the frozen primary target is currently reference-labeled.
Supporting/context overlap remains descriptive.

## Conclusion

For the first problem domain, this initial comparison supports the V1 thesis:

> A System One model can recover the primary file for several materially
> different tasks without reading source, while using much less wall time and
> observed dollar cost than an iterative System2 repository investigation.

This is **not** yet a general superiority claim.

What remains:

1. complete primary/supporting/context references;
2. more repositories/languages/tasks;
3. repeated System2 runs to measure variance;
4. normalized public-price comparison when provider routing/model pricing is
   intentionally fixed;
5. optimize System One's current ~210k metadata-token input without reducing
   logical file coverage.

Canonical pinned result:

`fixtures/research/file-discovery-system1-vs-system2-canonical.json`.
