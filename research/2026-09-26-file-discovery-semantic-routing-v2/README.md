# File Discovery V2: Semantic Path Rescue and Root-Safe Routing

## Experiment Goal

Test whether deterministic path-semantic normalization repairs the `filesystem/fs` and `websocket/ws` misses, and whether routing from top-level module cards reduces both file and directory decisions. Candidate counts remained uncapped.

## Experiment Design

1. Expand common code abbreviations symmetrically in queries and paths while retaining every evidence-qualified match.
2. Begin hierarchical routing at top-level or virtual module cards so one root summary cannot prune the entire repository.
3. Remove the ineffective same-directory expansion from V1.

## Experiment Process

[Workflow 36213648492](https://github.com/BestNathan/system-one-code-explore/actions/runs/36213648492) ran commit `919aa70b13756105446c7914e6fe626796cd7a4d`. All 36 units succeeded with model response version `jev-1.13.0`, with no retries or 429 responses. The full-scoring baseline came from the [V1 experiment](../2026-09-26-file-discovery-scaling-v1/), avoiding another paid baseline run. These nine tasks were already used for diagnosis and do not establish fresh-task generalization.

The repository contains the [fixed summary](data/summary.json) and [Workflow, job, and artifact metadata](workflow/metadata.json).

| Artifact | Purpose | Retention |
| --- | --- | --- |
| `fd-scaling-nession` | Nession V2 task results, traces, and usage | 30 days, through 2026-10-26 |
| `fd-scaling-codex` | Codex V2 task results, traces, and usage | 30 days, through 2026-10-26 |
| `fd-scaling-openclaw` | OpenClaw V2 task results, traces, and usage | 30 days, through 2026-10-26 |
| `fd-scaling-report-36213648492` | Aggregate JSON and Markdown for all 36 units | 90 days, through 2026-12-25 |

## Experiment Data

| Repository | Policy | Candidate recall | Final recall | Mean scored files | Mean directory decisions | Mean input tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Nession | semantic lexical | 3/3 | 2/3 | 258.3 | 0 | 49,750 |
| Nession | hierarchy V2 | 3/3 | 2/3 | 179.3 | 108.3 | 120,198 |
| Nession | adaptive V2 cold | 3/3 | 2/3 | 357.0 | 107.3 | 153,827 |
| Codex | semantic lexical | 3/3 | 3/3 | 1,357.7 | 0 | 260,792 |
| Codex | hierarchy V2 | 3/3 | 3/3 | 2,604.0 | 532.7 | 992,869 |
| Codex | adaptive V2 cold | 3/3 | 3/3 | 2,833.7 | 509.0 | 1,013,652 |
| OpenClaw | semantic lexical | 3/3 | 3/3 | 2,654.7 | 0 | 520,432 |
| OpenClaw | hierarchy V2 | 3/3 | 3/3 | 7,773.0 | 1,425.3 | 2,707,812 |
| OpenClaw | adaptive V2 cold | 3/3 | 3/3 | 8,732.7 | 1,430.3 | 2,899,232 |

Semantic aliases restored both V1 misses and reached 9/9 candidate recall. Some tasks expanded substantially: the Nession frontend case grew from 21 to 657 files, while the OpenClaw Gateway case grew from 3,994 to 4,984.

The remaining final-selection miss was `crates/nession-agent/src/fs/sandbox.rs`, scored at 0.53. Full V1 scoring protected it through a repository-wide top-1% guard. Candidate reduction incorrectly recomputed that 1% from only 71 scored candidates, shrinking the protected population from about 11 files to one.

## Experiment Results

1. Semantic lexical retrieval became the next baseline: it achieved 9/9 candidate recall without directory-model decisions.
2. The worst task still scored 4,984 candidates, so the algorithm had not reached a stable order-of-magnitude reduction.
3. Root-safe hierarchy removed root-summary omission but increased directory cost and was rejected.
4. Adaptive union increased cost without recall improvement and was rejected.
5. The next step was a zero-model replay using the original enumerated repository population for the relative guard.
