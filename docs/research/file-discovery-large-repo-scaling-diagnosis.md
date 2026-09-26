# Large-Repository File Discovery Scaling Diagnosis

## Status

Mechanism diagnosis after the Nession / OpenClaw / Codex large-repository benchmark.

Follow-up: [algorithmic reduction and concurrent requests](../../research/2026-09-26-file-discovery-scaling-v1/plan.md)
revises the next research direction: no cumulative file/directory count caps or
fixed candidate quotas. Study natural reduction through retrieval and adaptive
routing, plus independent-request concurrency, on Nession, Codex, and OpenClaw.
The numeric ranges and budget-driven refinement below are historical proposals,
superseded by the follow-up; they are not validated results or active limits.

## 1. Why Codex System2 cost appeared higher than OpenClaw

The difference is not explained by repository file count. System2 searches source selectively.

Raw Claude Code usage:

| case family | mean turns | fresh input | cache-read input | output | runtime `costUSD` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex | 66.3 | 102.8k | 3.02M | 15.4k | $2.410 |
| OpenClaw | 50.3 | 73.9k | 1.30M | 11.0k | $1.296 |

Codex required more iterative search/read turns and about 2.3x as many cache-read input tokens. That is the primary reason its runtime-reported cost was higher.

## 2. Claude Code `costUSD` is not a trustworthy DeepSeek bill

The raw result names the field `total_cost_usd` / `modelUsage.costUSD`, so its declared unit is USD.

However the same model-usage record reports:

```text
provider = firstParty
model = deepseek-flash
costBasis = unknown
```

and the number does not match current official DeepSeek Flash pricing.

The benchmark ran at about 07:48 UTC on Friday, inside DeepSeek's 06:00-10:00 UTC weekday peak window.

Official peak DeepSeek Flash prices at the frozen snapshot:

```text
cache-hit input  = $0.006 / 1M tokens
cache-miss input = $0.30  / 1M tokens
output           = $1.20  / 1M tokens
```

Recomputed from the raw token usage:

| family | mean official list-price estimate | mean Claude runtime `costUSD` |
| --- | ---: | ---: |
| Codex | ~$0.0674 | $2.410 |
| OpenClaw | ~$0.0432 | $1.296 |

The runtime number is therefore retained only as `runtime_reported_cost_usd` diagnostics. Cross-model cost conclusions must use the provider pricing snapshot plus raw cache-hit/cache-miss/output usage.

## 3. The OpenClaw 43k candidate count is effectively almost the whole repository

Frozen OpenClaw tree:

```text
total blobs:              49,683
current suffix-eligible:  44,146
```

So the current File Discovery filter admits roughly 89% of all repository blobs.

Eligible extension breakdown is dominated by:

```text
.ts    40,884
.md     1,953
.yaml     623
.sh       276
.yml      174
...
```

At least 18,770 TypeScript files match test/fixture/spec patterns.

Top-level eligible counts include:

```text
src         22,975
extensions  10,623
ui           4,359
test         1,646
docs         1,328
packages     1,218
```

Therefore 43k is not an acceptable final System One file-classification candidate set. Extension filtering alone is not candidate shaping.

## 4. Candidate Shaping V2

The logical guarantee remains:

> A relevant file must remain reachable independently of shallow parent-directory relevance.

But logical reachability does not require physically sending every file to Jev.

Target invariant:

```text
final file-level System One candidates: 128-512
preferred operating point: ~256
```

### Stage A — deterministic global path retrieval

Build a zero-model path/stem inverted index over every repository file.

Retrieve a small global rescue set using task/path lexical and fuzzy signals. This lane never depends on parent-directory pruning.

Initial target: ~64-128 files.

### Stage B — semantic module cards

Do not score shallow directory names such as `crates` or `nession-agent`.

Partition the repository into bounded semantic cards, e.g. 64-128 descendant files per card. Each card carries compressed descendant evidence:

```text
prefix
descendant count
subdirectory/stem token sketch
representative file paths
extension/language distribution
```

A card for `extensions/memory-core` therefore exposes actual descendant terms such as memory/search/embedding/manager rather than only the parent name.

System One independently scores these cards. Selected cards are recursively refined until their combined leaf-file set fits the final file budget.

### Stage C — structural neighborhood rescue

For strong deterministic/module hits, include bounded siblings and directly related local files so implementation splits are not lost.

### Stage D — final file-level Jev

Union and deduplicate the lanes, then run the existing independent file-level Noul only on the final ~128-512 candidates.

At 256 files and the current 64-question transport batch this is only four final file-scoring requests rather than 684 on OpenClaw.

### No silent hard cap

If the candidate set cannot be reduced below the budget while preserving unresolved high-value module mass:

1. recursively refine the unresolved cards; or
2. escalate the unresolved portion to System2.

Do not arbitrarily truncate to top-256.

## Expected scaling effect

Using the current OpenClaw baseline as a rough linear reference:

```text
43,748 files -> 8.48M input tokens / 684 requests
256 files    -> ~50k file-level input tokens / 4 requests
```

Routing/card overhead is additional, but the goal is still an order-of-magnitude reduction in total cost and latency.

## Research decision

File Discovery V1 remains the correctness baseline for reachability and independent file relevance.

Large-repository production execution should move to Candidate Shaping V2:

```text
all-file deterministic index
  -> global path rescue
  + semantic module-card refinement
  + bounded structural neighbors
  -> <= ~256-512 candidate files
  -> final Jev file scoring
  -> unresolved overflow => refine or System2 escalation
```

This preserves the lesson that shallow directory relevance is not monotonic while preventing repository size from linearly determining Jev token/call cost.
