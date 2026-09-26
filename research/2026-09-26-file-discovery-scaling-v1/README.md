# File Discovery Algorithm Scaling and Concurrency: First Three-Repository Results

## Experiment Goal

1. Determine whether concurrent independent System One file batches reduce latency without changing logical input.
2. Test whether global path retrieval and hierarchical routing naturally reduce file scoring while retaining primary targets.
3. Measure whether fewer file decisions merely shift cost into directory decisions and prompt tokens.

## Experiment Design

- `all_c1_cold` and `all_c4_cold`: identical full candidate sets with one versus four workers.
- `lexical_c4_quality`: deterministic query-to-path evidence.
- `hierarchy_c4_quality`: recursive routing over compressed descendant terms and representative paths.
- `hybrid_c4_quality` and `hybrid_c4_cold`: lexical plus hierarchy candidates and same-directory expansion.

Quality arms shared only identical request batches. Candidate-set changes alter batching, so this was not a strict paired per-file causal comparison. The first round had one repeat.

## Experiment Process

[Workflow 36155715068](https://github.com/BestNathan/system-one-code-explore/actions/runs/36155715068) ran commit `ebe7e0748c78704a061f177a2746efde21657ae9`. All 54 units succeeded with model response version `jev-1.13.0`. The frozen suite contained three tasks each for Nession, Codex, and OpenClaw. Primary labels were used only after execution.

The committed evidence includes the [fixed summary](data/summary.json) and [Workflow, job, and artifact metadata](workflow/metadata.json).

| Artifact | Purpose | Retention |
| --- | --- | --- |
| `fd-scaling-nession` | Nession task results, traces, and usage | 30 days, through 2026-10-25 |
| `fd-scaling-codex` | Codex task results, traces, and usage | 30 days, through 2026-10-25 |
| `fd-scaling-openclaw` | OpenClaw task results, traces, and usage | 30 days, through 2026-10-25 |
| `fd-scaling-report-36155715068` | Aggregate JSON and Markdown for all 54 units | 90 days, through 2026-12-24 |

Moving the historical commits to `main` triggered duplicate [run 36220565316](https://github.com/BestNathan/system-one-code-explore/actions/runs/36220565316). It was canceled immediately: Codex and OpenClaw did not execute, and Nession was canceled about 13 seconds into its experiment step. The run is excluded from all results; its state and partial artifacts are preserved in [migration-run metadata](workflow/migration-triggered-run-36220565316.json).

## Experiment Data

Full scoring retained 9/9 primary targets with unchanged logical input tokens.

| Repository | Files | Serial mean | Four-worker mean | Speedup |
| --- | ---: | ---: | ---: | ---: |
| Nession | 1,096 | 3.90s | 1.13s | 3.44× |
| Codex | 6,277 | 31.65s | 7.88s | 4.02× |
| OpenClaw | 43,748 | 156.92s | 40.01s | 3.92× |

There were 74 retry events across 25 of 54 units and no 429 retries.

| Repository | Policy | Primary recall | Scored files | Directory decisions | Logical input tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| Nession | lexical | 2/3 | 26.7 | 0 | 5,251 |
| Nession | hierarchy | 2/3 | 97.7 | 65.7 | 69,333 |
| Nession | hybrid cold | 2/3 | 129.0 | 72.0 | 82,236 |
| Codex | lexical | 3/3 | 1,357.7 | 0 | 260,792 |
| Codex | hierarchy | 3/3 | 2,663.0 | 534.7 | 1,004,540 |
| Codex | hybrid cold | 3/3 | 3,203.3 | 531.3 | 1,105,123 |
| OpenClaw | lexical | 2/3 | 2,324.7 | 0 | 456,164 |
| OpenClaw | hierarchy | 3/3 | 7,072.0 | 1,398.0 | 2,529,199 |
| OpenClaw | hybrid cold | 3/3 | 14,512.7 | 1,377.3 | 3,965,194 |

Lexical retrieval missed `crates/nession-agent/src/fs/sandbox.rs` because it did not align `filesystem` with `fs`, and missed `src/gateway/server/ws-connection/message-handler.ts` because it did not align `websocket` with `ws`. Hierarchical routing recovered the OpenClaw target but stopped the Nession filesystem task at the root summary. Same-directory expansion did not repair these failures and greatly enlarged OpenClaw candidates.

## Experiment Results

1. Four concurrent independent batches produced near-ideal speedup without rate limiting.
2. Lexical retrieval delivered large natural reductions but insufficient recall.
3. Hierarchical summaries repaired one lexical miss while adding too many directory decisions.
4. Same-directory expansion was rejected.
5. The next experiment should add symmetric path-semantic normalization and remove root-level single-point pruning, while continuing to report file count, directory count, tokens, calls, latency, and failures.
