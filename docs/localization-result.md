# Canonical Code Localization Result

The code-locator experiments use one execution-independent result contract:

~~~text
localization-result.json
~~~

Execution traces remain separate artifacts.

## Separation of concerns

The contract deliberately separates three concerns:

~~~text
ExecutionTrace
  = how a system searched, read, and decided

LocalizationDraft
  = which files and source ranges the system finally selected

LocalizationResult
  = the immutable draft + confidence analysis + cost metrics
~~~

For System One, confidence is already part of the localization mechanism because Noul relevance scores are produced during reading.

For Claude Code, localization and confidence are intentionally separated into two fresh sessions:

~~~text
Session A
  repository search + reads
  -> final files / ranges / reasons
  -> NO confidence calculation

Session B
  new Claude Code session
  input = immutable Session-A draft + materialized evidence source
  tools = disabled
  -> confidence only
  -> cannot add/remove/change files or ranges
~~~

The final Claude result is assembled programmatically. If Session B changes a file path, order, evidence count, or evidence range, the workflow fails.

## Canonical schema

~~~json
{
  "schema_version": 1,
  "kind": "code-localization-result",
  "task": "Help me optimize the websocket connection implementation",
  "subject": {
    "repository": "BestNathan/nession",
    "revision": "<immutable commit sha>"
  },
  "producer": {
    "system": "system_one",
    "model": "jev-latest",
    "confidence_semantics": "..."
  },
  "summary": {},
  "confidence": null,
  "cost": {
    "elapsed_ms": 3780,
    "api_elapsed_ms": null,
    "elapsed_semantics": "end-to-end System One localization harness runtime",
    "model_calls": 12,
    "turns": null,
    "tool_calls": 0,
    "tokens": {
      "input": 195977,
      "output": 12464,
      "cache_read_input": 0,
      "cache_creation_input": 0,
      "thinking": 0
    },
    "provider_cost_usd": null,
    "stages": [
      {
        "name": "localization",
        "elapsed_ms": 3780,
        "model_calls": 12,
        "turns": null,
        "tool_calls": 0,
        "tokens": {},
        "provider_cost_usd": null
      }
    ]
  },
  "files": [
    {
      "path": "web/src/platform/socket/WebSocketService.ts",
      "role": "relevant",
      "confidence": {
        "score": 0.91,
        "label": "high",
        "type": "derived_max_evidence_relevance",
        "basis": "maximum retained observation relevance for this file"
      },
      "reason": "why this file is considered valuable",
      "evidence": [
        {
          "id": "web/src/platform/socket/WebSocketService.ts#evidence-1",
          "start_line": 1,
          "end_line": 140,
          "confidence": {
            "score": 0.91,
            "label": "high",
            "type": "noul_relevance",
            "basis": "System One observation relevance score"
          },
          "reason": "why this source range is considered valuable",
          "content": "1: ...\n2: ..."
        }
      ],
      "provenance": {}
    }
  ]
}
~~~

## files[]

This list contains the producer's final valuable files, not every file it inspected.

For System One, a file enters the final list when at least one observed range is retained above the observation threshold.

For Claude Code, Session A decides the final file list. Session B cannot alter it.

## role

~~~text
relevant
primary
supporting
context
unknown
~~~

System One currently emits `relevant`.

Claude Session A may emit `primary`, `supporting`, or `context`.

Role mismatch is descriptive and is not automatically an error.

## evidence[]

Each evidence record identifies a source range the producer considers valuable:

~~~text
path + start_line + end_line
reason
content
confidence
~~~

The result contains the actual source text for the range.

System One already possesses that text from the read observation.

For Claude, Session A selects the path/range, then the normalizer materializes the exact source from the pinned repository revision before Session B assesses confidence.

## Confidence semantics

Confidence is always structured:

~~~json
{
  "score": 0.91,
  "label": "high",
  "type": "noul_relevance",
  "basis": "..."
}
~~~

Labels are presentation helpers:

~~~text
high    >= 0.80
medium  >= 0.60
low     <  0.60
~~~

Current confidence types:

~~~text
noul_relevance
derived_max_evidence_relevance
model_self_assessment
~~~

These values are not assumed to be calibrated to each other.

For Claude specifically, every `model_self_assessment` value is produced by Session B, not by the repository-search session.

## Cost metrics

Cost is part of the canonical result because result quality and search cost need to be compared together.

Common fields:

~~~text
elapsed_ms
api_elapsed_ms
model_calls
turns
tool_calls

tokens.input
tokens.output
tokens.cache_read_input
tokens.cache_creation_input
tokens.thinking

provider_cost_usd
stages[]
~~~

Not every provider exposes every field. Missing values remain null rather than being inferred.

### System One

System One currently records one stage:

~~~text
localization
~~~

Its cost contains total harness elapsed time, System One model-call count, input/output tokens, and local read-operation counts in stage provenance.

### Claude Code

Claude records two independent stages:

~~~text
localization
confidence_assessment
~~~

The final cost is the sum of both sessions.

The localization stage includes repository tool calls.

The confidence stage must have:

~~~text
tool_calls = 0
~~~

and is rejected if it attempts to use repository tools.

Claude token accounting also preserves cache-read/cache-creation tokens and provider-reported USD cost when available.

## Claude artifacts

The Claude cross-trace artifact contains:

~~~text
localization-prompt.txt
localization.raw.jsonl
localization-draft.json
localization-manifest.json

execution-path.json
execution-summary.md

confidence-prompt.txt
confidence.raw.jsonl
confidence-manifest.json
confidence-summary.md

localization-result.json
manifest.json
~~~

This keeps the original search path, immutable localization output, independent confidence assessment, and final merged result separately inspectable.

## Comparison contract

Future comparisons consume only two canonical `localization-result.json` files.

For cross-system experiments, both results must carry the same canonical
`subject.repository` and immutable `subject.revision`. The comparator fails
closed when subject identity is missing or the revisions differ; line/range
overlap across different revisions is not considered meaningful.

The generic comparator records symmetric observations:

~~~text
cost metrics for both sides

shared files
left-only files
right-only files
file-set Jaccard

role differences
file confidence pairs

evidence-region overlap in both directions
evidence-line overlap in both directions
missed regions in both directions
~~~

Neither side is treated as ground truth.

Absolute accuracy requires an independently reviewed gold set.


## Two-session real validation

Run `35846265667` validates the split end to end on the Nession websocket task.

Claude localization session:

~~~text
final files       13
evidence regions  42
confidence keys    0

elapsed          67,864 ms
turns                 32
tool calls            31
input tokens      51,398
output tokens     11,575
cache-read       554,368
provider cost   $0.823549
~~~

Claude confidence session:

~~~text
new independent session
repository tool calls    0
files changed            0
evidence ranges changed  0

elapsed          24,424 ms
turns                  1
input tokens      32,119
output tokens      5,616
provider cost   $0.300995
~~~

Combined Claude result cost:

~~~text
elapsed          92,288 ms
turns                 33
tool calls            31
input tokens      83,517
output tokens     17,191
cache-read       554,368
provider cost   $1.124544
~~~

The final overall confidence was 0.84, but that value exists only in the second-session assessment. The localization draft remains confidence-free.

The same run's System One result carried:

~~~text
elapsed           3,770 ms
model calls            15
reads                  10
scheduler rounds        5
input tokens      249,871
output tokens      13,009
~~~

These values are cost records, not a winner/loser judgment. Provider token semantics differ, especially around cache accounting.
