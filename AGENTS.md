# Repository Guidelines

## Project Structure

- `src/`: file discovery, evidence localization, benchmark, and evaluation code.
- `tests/`: unit and regression tests.
- `fixtures/`: frozen inputs, repository samples, and reusable reference data.
- `research/`: current and future experiment records, with one directory per experiment.
- `docs/research/`: historical records created before the current experiment layout.
- `.github/workflows/`: test, experiment, aggregation, and artifact-upload entry points.
- `README.md`: project entry point and chronological experiment tracker.

## Constraints

- The entire repository must be written in English. This includes source code, comments, generated output, documentation, configuration, fixtures, filenames, commit messages, and experiment artifacts committed to Git.
- Develop, commit, and run experiments directly on `main`. Do not create experiment branches or experiment worktrees.
- Run all project tests, experiments, benchmarks, and project scripts only through GitHub Actions. Local activity is limited to editing files, inspecting Git state, and reading existing data.
- Before an experiment, create `research/YYYY-MM-DD-<experiment-name>/` and freeze its tasks, repository revisions, model, parameters, controls, metrics, and stopping criteria.
- Every experiment directory must contain `README.md` with these level-two headings: `Experiment Goal`, `Experiment Design`, `Experiment Process`, `Experiment Data`, and `Experiment Results`. Record failed, canceled, and null-result experiments in the same format.
- Store committable frozen inputs, aggregates, and key results under `data/`. Keep large raw results in GitHub Actions artifacts; do not rely on manually copied metrics alone.
- `workflow/metadata.json` must record the Workflow URL, run ID, commit SHA, status, jobs, and artifact inventory. The report must name each artifact, explain its purpose, and state its retention period.
- Preserve every physical model request, full raw response, retry, terminal error, and cache-reuse link as immutable JSONL in the Workflow artifacts. Assign each physical call a unique `call_id` and deterministic request hash. Generate and commit or archive a manifest containing record counts, completeness status, byte sizes, and SHA-256 checksums. Never record credentials or authorization headers.
- Follow this sequence: preregister the design, push to `main`, run the Workflow, inspect jobs and artifacts, freeze data and conclusions, update the experiment directory plus both research indexes, then validate the final commit through GitHub Actions.
- Do not use a hard candidate-count cap as an algorithmic optimization. Report recall, scored files, directory decisions, tokens, calls, latency, and failures, and reduce scale through the algorithm itself.
