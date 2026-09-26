# Large-Repository File Discovery: Algorithmic Reduction and Concurrent Requests

## Status and Goal

The first diagnostic round is complete; see the [result report](README.md) and [Workflow 36155715068](https://github.com/BestNathan/system-one-code-explore/actions/runs/36155715068).

Following the [large-repository scaling diagnosis](../../docs/research/file-discovery-large-repo-scaling-diagnosis.md), this experiment studied how to reduce file and directory scoring while preserving relevant-file recall, and how to execute independent System One requests concurrently.

The design imposed no cumulative file or directory cap, fixed top-k, or channel quota. Counts had to emerge from task relevance, retrieval evidence, and exploration state. An order-of-magnitude reduction, 2,000 files, and earlier 128–512-file targets were observations rather than truncation or pass criteria.

All tests, indexing, and experiments ran through GitHub Actions. Request size, concurrency, and retries could control transport but could not discard logical candidates.

## Existing Evidence

- V1 scored file batches sequentially even though batches had no score dependency.
- `compact_state_v4` already separated shared instructions from batch content.
- The prior OpenClaw V1 run scored 43,748 files per task through 684 requests, used about 8.48 million input tokens, and took 332.6 seconds.
- Full scoring was known to be costly, but no routing strategy had demonstrated stable recall with an order-of-magnitude reduction.

## Compared Policies

| Policy | Isolated question | Main risk |
| --- | --- | --- |
| Full V1 plus concurrency | How much independent waiting time can be removed? | File and token counts remain unchanged |
| Global metadata retrieval plus file scoring | How many model decisions can path evidence avoid? | Weak naming and cross-module files may be missed |
| Retrieval plus adaptive hierarchy and rescue | Can file and directory decisions both fall? | Summaries may hide rare descendants or stop early |

## Algorithm Design

### Global metadata retrieval

Build a revision-keyed index of paths, filename terms, directory relations, and descendant summaries. Preserve all matches that satisfy evidence rules. Wide matches should be summarized by module rather than truncated.

### Adaptive module summaries

Use descendant terms, representative paths, child composition, and counts. Ask separately whether relevant descendants may exist and whether the summary is sufficient. Expand mixed, uncertain, or relevant modules. A low-scoring parent must not permanently hide descendants reachable through another retrieval path.

### Evidence-driven continuation

Record new clues, unresolved coverage, deferred modules, uncertainty, and candidate changes after every wave. Stop only when the exploration queue is exhausted. This is a heuristic stop, not proof of complete coverage.

### Independent scoring and reuse

Score discovered files independently and cache identical semantic batches. Preserve candidate provenance and routing decisions so failures can be classified as retrieval omission, routing omission, early stopping, or file-score rejection.

## Concurrency Design

- Compare worker counts 1, 2, 4, and 8 with fixed candidates, prompts, and batches.
- Bound in-flight requests with a queue; never discard logical candidates when the transport window fills.
- Merge results by stable ID and advance exploration only after a complete wave.
- Retry timeouts, 429 responses, and server errors with bounded backoff while preserving failure accounting.
- Report summed request time, queue time, scoring wall time, and end-to-end time.

## Frozen Three-Repository Suite

| Repository | Revision | Tasks |
| --- | --- | --- |
| `BestNathan/nession` | `7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df` | reconnect lifecycle, symlink deletion safety, frontend request correlation |
| `openai/codex` | `d7b07d45517a793acfba4cbf8de697d723cceb46` | command approval, MCP call approval, thread create/resume/persistence |
| `openclaw/openclaw` | `932abb0a841b522ebaa5b81921119a61b6a80b21` | Gateway dispatch, skill-source precedence, hybrid memory retrieval |

The original nine tasks were diagnostic cases. Any generalization claim requires new tasks frozen before their labels or results are inspected.

## Evaluation and Reporting

- Require all primary targets from the original nine tasks; report primary and supporting-file recall separately for new tasks.
- Report total repository files versus actually scored files without enforcing a 2,000-file threshold.
- Report directory decisions, duplicates, files, tokens, calls, cost, rate limits, errors, and end-to-end latency.
- Break results down by repository and task and retain the worst cases.
- Record quality/cost tradeoffs, failure mechanisms, and the next isolated variable.
- Store every experiment in its own root `research/` directory. Keep traces, provenance, stopping evidence, and raw usage in Workflow artifacts even when a run fails.
