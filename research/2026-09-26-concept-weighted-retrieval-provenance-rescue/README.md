# Concept-Weighted Retrieval and Provenance Rescue V3

## Experiment Goal

Test whether deduplicating high-signal aliases and weighting path evidence reduces scoring while preserving primary targets, and whether file provenance can replace the repository-wide 1% selection guard. The scale target was an order-of-magnitude reduction on the largest repository without any fixed candidate limit.

## Experiment Design

Three arms ran on nine frozen tasks from pinned Nession, Codex, and OpenClaw revisions: broad semantic lexical retrieval plus the stable repository-population guard; concept-weighted retrieval with the same guard; and concept-weighted retrieval with provenance rescue. The weighted arm counted narrow alias groups once, used inverse path frequency and filename/directory position weights, and admitted paths by two distinct concepts, one concept in at most 2% of repository paths, or filename weighted score of at least 2.0. Provenance rescue retained the 0.65 absolute threshold and selected scores at or above 0.50 when a rare matched concept or filename concept supported them. No file or directory candidate cap was used. All arms used four concurrent independent System One calls; weighted selection arms reused identical score batches.

Success required 9/9 primary candidate recall before reduction could be accepted. We tracked final primary recall, scored and selected files, directory decisions, calls, tokens, cost, latency, failures, and raw request provenance. These tasks are diagnostic; primary labels do not include every supporting file and one run cannot establish stability.

## Experiment Process

The test-first changes failed in GitHub Actions runs [36228816265](https://github.com/BestNathan/system-one-code-explore/actions/runs/36228816265) and [36228892830](https://github.com/BestNathan/system-one-code-explore/actions/runs/36228892830), exposing broad alias inflation and the missing concept-aware behavior. Commit `e86e927c2a5d9fb281bd3d3925bb13761de25832` then passed 152 tests in GitHub Actions. The paid experiment ran on `main` in [Workflow 36229213515](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229213515); all 27 task/arm units succeeded across the three repositories.

The weighted OpenClaw Gateway miss came from splitting PascalCase `WebSocket` into `web` and `socket` before alias normalization. Provenance rescue cannot recover a file that retrieval never scores. This implementation is rejected for large repositories; the next experiment isolates CamelCase normalization as a correction.

## Experiment Data

- Frozen configuration: [`data/scaling-experiment.json`](data/scaling-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Aggregate metrics: [`data/summary.json`](data/summary.json)
- Workflow, job, and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Per-task scores, complete raw requests and responses, retry/error records, call manifests, and detailed reports are preserved in the linked Workflow artifacts. All four artifacts are retained through 2026-12-25 (90 days).

## Experiment Results

| Repository | Arm | Candidate recall | Mean scored files | Mean input tokens | Mean selected files |
| --- | --- | ---: | ---: | ---: | ---: |
| Nession | Broad semantic + stable guard | 3/3 | 258 | 49,750 | 11 |
| Nession | Weighted + stable guard | 3/3 | 51 | 9,962 | 13 |
| Nession | Weighted + provenance rescue | 3/3 | 51 | 9,962 | 9 |
| Codex | Broad semantic + stable guard | 3/3 | 1,358 | 260,792 | 89 |
| Codex | Weighted + stable guard | 3/3 | 1,400 | 269,023 | 89 |
| Codex | Weighted + provenance rescue | 3/3 | 1,400 | 269,023 | 146 |
| OpenClaw | Broad semantic + stable guard | 3/3 | 2,655 | 520,432 | 446 |
| OpenClaw | Weighted + stable guard | 2/3 | 4,729 | 931,420 | 456 |
| OpenClaw | Weighted + provenance rescue | 2/3 | 4,729 | 931,420 | 278 |

All three arms made zero model directory decisions because metadata retrieval operated on paths directly. Overall, broad semantic retrieval scored a mean 1,424 files and used 276,991 input tokens per task; weighted retrieval scored 2,060 files and used 403,469 tokens. The weighted arms missed `src/gateway/server/ws-connection/message-handler.ts` in both selection policies. Provenance rescue reduced selected files in Nession and OpenClaw, but increased them in Codex and could not compensate for candidate omissions. V3 therefore failed the 9/9 recall gate and did not establish a scalable replacement for the current mechanism.
