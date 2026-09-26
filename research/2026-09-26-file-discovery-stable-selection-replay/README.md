# File Discovery: Stable Relative-Guard Replay

## Experiment Goal

Determine whether the top-1% relative guard should use the reduced candidate count or the mechanically enumerated original repository population.

## Experiment Design

Replay existing file scores with the guard population fixed to the original repository file count. Limit the protected count to the number of candidates actually scored. This preserves V1 selection semantics without making new model calls.

## Experiment Process

The source was [Workflow 36213648492](https://github.com/BestNathan/system-one-code-explore/actions/runs/36213648492); [replay Workflow 36214118855](https://github.com/BestNathan/system-one-code-explore/actions/runs/36214118855) downloaded its artifacts, applied old and stable population semantics, and uploaded per-task comparisons. The replay made zero System One calls.

The repository contains the [fixed summary](data/summary.json) and [source/replay Workflow metadata](workflow/metadata.json).

| Artifact | Purpose | Retention |
| --- | --- | --- |
| `fd-stable-selection-replay-36214118855` | Per-task rankings and aggregate replay for four policies | 90 days, through 2026-12-25 |

Moving the frozen configuration to `main` produced a second zero-model [validation replay 36220565302](https://github.com/BestNathan/system-one-code-explore/actions/runs/36220565302). It succeeded and uploaded `fd-stable-selection-replay-36220565302`, retained for 90 days through 2026-12-25. It is validation of the migrated Workflow rather than a separate experiment; see its [metadata](workflow/main-replay-36220565302.json).

## Experiment Data

| Policy | Cases | Original recall | Stable-population recall | Mean selected files |
| --- | ---: | ---: | ---: | ---: |
| semantic lexical | 9 | 88.9% | 100% | 182.9 |
| hierarchy V2 | 9 | 88.9% | 100% | 186.9 |
| adaptive V2 quality | 9 | 88.9% | 100% | 189.3 |
| adaptive V2 cold | 9 | 88.9% | 100% | 184.7 |

All four policies recovered `crates/nession-agent/src/fs/sandbox.rs`. Nession's 1,096 files produce 11 protected positions instead of one. Codex receives 63 positions and OpenClaw 438; score ties can select slightly more.

Stable population semantics provide a valid V1-compatible comparison, but they are unsuitable as the production policy. Semantic lexical retrieval still selected roughly 442–456 OpenClaw files per task because the repository-wide 1% fallback dominates downstream cost.

## Experiment Results

1. V1-compatible research comparisons must calculate the relative guard from the original repository population.
2. Stable selection restored 9/9 primary recall but did not make hierarchical or adaptive routing cost-effective.
3. Semantic lexical discovery remains the candidate-generation baseline.
4. Production selection needs provenance-aware low-score rescue rather than a permanent repository-wide 1% fallback.
5. Rescue rules must first be diagnosed on the existing tasks, then frozen and evaluated on fresh tasks from all three repositories.
