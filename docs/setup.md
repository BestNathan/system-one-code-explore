# Repository Setup

The source code and workflows are migrated, but GitHub does not migrate repository secrets, variables, or environments between repositories.

## CI

The normal `CI` workflow requires no secrets and runs:

```bash
python3 -m unittest discover -s tests -v
```

## Cross-trace workflow

`.github/workflows/cross-trace.yml` expects two GitHub Actions environments.

### `typesafe`

Required:

- secret or variable `TYPESAFE_API_KEY`

Optional variables:

- `TYPESAFE_MODEL` — defaults to `jev-latest`
- `TYPESAFE_API_URL` — defaults to `https://api.typesafe.ai/v1/systemone`

### `ds`

Required:

- secret `ANTHROPIC_API_KEY`
- variable `CLAUDE_MODEL` — use an explicit model identifier, not a moving alias

Optional variable:

- `ANTHROPIC_BASE_URL` — defaults to `https://api.anthropic.com`

The validated benchmark in the migrated research used Claude Code as the System 2 harness with `deepseek-flash` configured through the Anthropic-compatible endpoint.

## Manual benchmark

The cross-trace workflow is intentionally `workflow_dispatch` only. It accepts:

- `subject_repository`
- `subject_ref`
- `query`

Both System One and System 2 resolve and operate on the same immutable subject commit before comparison and blind quality evaluation.

## Repository metadata

The desired description and GitHub topics are recorded in [../REPOSITORY_METADATA.md](../REPOSITORY_METADATA.md).
