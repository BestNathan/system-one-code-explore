# CamelCase Concept Normalization V4

## Experiment Goal

Determine whether preserving known compound concepts before CamelCase splitting restores the OpenClaw Gateway primary target and reduces concept-weighted file scoring in a 43,748-file repository. The operational pass gate is 9/9 primary candidate recall and fewer than 2,000 mean files scored on OpenClaw, with no fixed candidate cap.

## Experiment Design

Repeat the V3 three-arm comparison on the same nine frozen tasks and pinned Nession, Codex, and OpenClaw revisions: broad semantic lexical retrieval with the stable repository-population guard; concept-weighted retrieval with the same guard; and concept-weighted retrieval with provenance rescue. The only algorithm change from V3 is token normalization: recognize a complete known canonical concept or alias inside punctuation-delimited chunks before splitting unknown CamelCase names. This preserves `WebSocket` as one `websocket` concept while still splitting names such as `OpenClaw` into useful components. Alias vocabulary, path-frequency thresholds, position weights, score thresholds, concurrency, and cache behavior remain fixed.

Track candidate and final primary recall, scored and selected file counts, reduction, directory decisions, physical and logical calls, tokens, cost, latency, failures, and per-call raw provenance. Primary-target labels do not cover every supporting file; passing this diagnostic suite is not fresh-task generalization.

## Experiment Process

V3 failed its recall and scale gates in [Workflow 36229213515](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229213515): the weighted OpenClaw Gateway arm missed `src/gateway/server/ws-connection/message-handler.ts` and averaged 4,729 scored files. Test-first regression coverage then failed in CI run [36229609799](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229609799), showing `WebSocket` became separate `web` and `socket` concepts. The corrected implementation ran on `main` in [Workflow 36229721717](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229721717). All 27 units succeeded, and all 153 GitHub Actions tests passed before paid requests.

## Experiment Data

- Frozen configuration: [`data/scaling-experiment.json`](data/scaling-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Aggregate metrics: [`data/summary.json`](data/summary.json)
- Workflow, jobs, and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Each repository artifact contains per-task scores, raw model requests and responses, manifests, usage, errors/retries, and the report. Artifacts are retained for 90 days.

## Experiment Results

The correction restored the missing OpenClaw Gateway candidate; the weighted policy reached 9/9 primary recall across the nine diagnostic tasks. It failed the scale gate: OpenClaw weighted retrieval averaged 4,632 files and 912,681 input tokens, versus 2,655 files and 520,432 tokens for broad semantic retrieval. Weighted retrieval averaged 47 files on Nession, but 1,400 on Codex, so improvements did not transfer consistently across repository sizes. The order-of-magnitude target remains unmet. The next experiment will replay score thresholds across every enumerated path without model calls to measure the candidate-count/recall frontier before another paid scoring run.
