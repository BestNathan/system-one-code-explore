# Experiment Log

Each experiment has one directory containing its report, committed data, and GitHub Actions evidence. The report always records the experiment goal, plan, process, data, and result. Historical research created before this layout remains indexed in [`docs/research/`](../docs/research/README.md).

| Date | Experiment | Status | Workflow | Main result |
| --- | --- | --- | --- | --- |
| 2026-09-26 | [File Discovery scaling V1](2026-09-26-file-discovery-scaling-v1/) | completed | [36155715068](https://github.com/BestNathan/system-one-code-explore/actions/runs/36155715068) | Four concurrent requests improved full-scoring latency by 3.44–4.02×; lexical retrieval was cheapest but recalled 7/9 targets. |
| 2026-09-26 | [Semantic routing V2](2026-09-26-file-discovery-semantic-routing-v2/) | completed | [36213648492](https://github.com/BestNathan/system-one-code-explore/actions/runs/36213648492) | Semantic path aliases restored 9/9 candidate recall; directory routing remained too expensive. |
| 2026-09-26 | [Stable selection replay](2026-09-26-file-discovery-stable-selection-replay/) | completed | [36214118855](https://github.com/BestNathan/system-one-code-explore/actions/runs/36214118855) | A zero-model replay restored 9/9 final recall, but the repository-wide 1% guard still retained hundreds of OpenClaw files. |
| 2026-09-26 | [Concept-weighted retrieval and provenance rescue V3](2026-09-26-concept-weighted-retrieval-provenance-rescue/) | completed | [36229213515](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229213515) | Weighted retrieval recalled 8/9 targets and raised OpenClaw candidates by 78%; CamelCase normalization is the diagnosed failure. |
| 2026-09-26 | [CamelCase concept normalization V4](2026-09-26-camel-case-concept-normalization-v4/) | completed | [36229721717](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229721717) | CamelCase correction restored 9/9 recall; OpenClaw remained at 4,632 weighted files, so the scale gate failed. |

For a new experiment, create `research/YYYY-MM-DD-<experiment-name>/` before running it. Store the report in `README.md`, committed results in `data/`, and the Workflow run, jobs, and artifact inventory in `workflow/metadata.json`. Update this table and the root README after interpreting the result.
