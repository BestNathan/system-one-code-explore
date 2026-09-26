# CamelCase Concept Normalization V4

## Experiment Goal

Determine whether preserving known compound concepts before CamelCase splitting restores the OpenClaw Gateway primary target and reduces concept-weighted file scoring in a 43,748-file repository. The operational pass gate is 9/9 primary candidate recall and fewer than 2,000 mean files scored on OpenClaw, with no fixed candidate cap.

## Experiment Design

Repeat the V3 three-arm comparison on the same nine frozen tasks and pinned Nession, Codex, and OpenClaw revisions: broad semantic lexical retrieval with the stable repository-population guard; concept-weighted retrieval with the same guard; and concept-weighted retrieval with provenance rescue. The only algorithm change from V3 is token normalization: recognize a complete known canonical concept or alias inside punctuation-delimited chunks before splitting unknown CamelCase names. This preserves `WebSocket` as one `websocket` concept while still splitting names such as `OpenClaw` into useful components. Alias vocabulary, path-frequency thresholds, position weights, score thresholds, concurrency, and cache behavior remain fixed.

Track candidate and final primary recall, scored and selected file counts, reduction, directory decisions, physical and logical calls, tokens, cost, latency, failures, and per-call raw provenance. Primary-target labels do not cover every supporting file; passing this diagnostic suite is not fresh-task generalization.

## Experiment Process

V3 failed its recall and scale gates in [Workflow 36229213515](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229213515): the weighted OpenClaw Gateway arm missed `src/gateway/server/ws-connection/message-handler.ts` and averaged 4,729 scored files. Test-first regression coverage then failed in CI run [36229609799](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229609799), showing `WebSocket` became separate `web` and `socket` concepts. The corrected implementation and frozen V4 configuration will be committed on `main`; GitHub Actions validates all tests before model calls and archives complete traces and aggregates.

## Experiment Data

- Frozen configuration: [`data/scaling-experiment.json`](data/scaling-experiment.json)
- Frozen tasks and repository revisions: [`data/cases.json`](data/cases.json)
- Workflow, jobs, and artifact inventory: [`workflow/metadata.json`](workflow/metadata.json)
- Each repository artifact contains per-task scores, raw model requests and responses, manifests, usage, errors/retries, and the report. Artifacts are retained for 90 days.

## Experiment Results

Pending the V4 Workflow. A pass requires all 27 units to complete, the weighted policy to retain all nine primary candidates, and the weighted OpenClaw arm to average fewer than 2,000 scored files. Selection rescue is considered separately and cannot compensate for a retrieval-stage miss.
