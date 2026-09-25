# File Discovery V1 — Deterministic Research Convergence

## Status

**Mechanically converged V1. Canonical validation gate passed.**

This document closes open-ended File Discovery architecture exploration. Future work may calibrate, optimize, or falsify this V1, but should not invent new traversal semantics unless V1 fails for a structural reason.

## Research question

> Can System One identify task-relevant files from repository file metadata alone, at materially lower cost than System Two repository exploration, while preserving the files needed by downstream Evidence Localization?

## Final V1 conclusion

File Discovery is **not a semantic directory-traversal problem**.

It is a multi-label file classification problem over a mechanically enumerated repository file set.

```text
Repository
   -> Harness mechanically enumerates supported file metadata
   -> System One independently Noul-scores every file once
   -> threshold selects RelevantFile[]
   -> Evidence Localization handles source
```

Directory paths remain useful metadata and transport structure, but directories do not semantically prune descendants.

## Why directory pruning is rejected

The convergence gates produced the same failure repeatedly for the fs symlink/delete task.

Target:

`crates/nession-agent/src/fs/sandbox.rs`

### Gate 1 — semantic pruning from the repository root

Two repeats both recovered 5/6 primary files.

`crates` scored only 0.41 / 0.38 and the entire target subtree was pruned.

### Gate 2 — mechanically expand only top-level directories

The same failure moved down one namespace layer.

`crates/nession-agent` scored 0.22 in both repeats.

### Gate 3 — mechanically collapse directories with no direct implementation files

The same failure moved to:

`crates/nession-agent/src` -> 0.40 / 0.44

even though its child names included the genuinely relevant `fs` directory.

This establishes a structural property:

> High relevance of a descendant file does not imply high relevance of shallow parent-directory metadata.

Directory relevance is therefore not safely monotonic and cannot be used as a hard pruning invariant.

Lowering the directory threshold only moves the false-negative boundary and makes correctness depend on repository naming depth.

## Historical designs formally rejected

1. Whole-tree semantic directory scoring as a pruning stage.
2. Recursive re-walking of selected directories.
3. Per-line/source scoring during File Discovery.
4. Fixed top-k file caps.
5. Fixed file batches as semantic ordering.
6. Repeated rescoring of unchanged files.
7. A model-controlled global Stop for file discovery.
8. Any architecture where a parent directory rejection can make a relevant file permanently unreachable.

Historical cost evidence also rejects combining file discovery with line-level reading: the original implementation reached 598 calls and 5.77M input tokens largely because candidate batching and per-file line scoring multiplied semantic calls.

## V1 scope

V1 answers exactly:

> Which files should be handed to Evidence Localization?

V1 does not read source bodies, reason about line ranges, follow callers/callees, or decide whether final code evidence is sufficient.

## Repository view

The Harness recursively enumerates supported files using deterministic ignore and extension rules.

System One sees only:

```text
path
filename
extension
size_bytes
```

No source body, AST, symbol graph, embedding, LSP result, or hidden semantic summary is part of V1.

## Decision primitive

For each file, independently ask Noul:

> How likely is this file itself to contain material source evidence relevant to the task?

Files do not compete and probabilities do not sum to one.

This is intentionally multi-hit: several files can all be relevant.

## State transition

```text
mechanically enumerate all supported files
        |
        v
score every file exactly once
        |
        +--> score >= file_threshold -> RelevantFile
        |
        +--> score <  file_threshold -> rejected
        |
        v
all file metadata scored
        |
        v
terminate
```

There is no directory threshold, top-k, or semantic global Stop.

## Batching and caching

Transport batching is allowed only as an execution detail.

A file score is cacheable by:

```text
hash(task + canonical file metadata + prompt version + model)
```

Changing batch size must not change the logical candidate set or selection semantics.

When two policies reuse an identical file scoring request, counterfactual A/B must share the same cached System One response.

## Threshold

The initial canonical gate freezes:

`file_threshold = 0.65`

This is a baseline operating point, not a universally optimal threshold.

Because all file scores exist independently of traversal, future threshold calibration is cheap and deterministic: replay 0.50/0.55/0.60/0.65/0.70 against the same score field without new model calls.

Threshold research therefore becomes a quality-cost Pareto analysis rather than a new architecture.

## Output

```text
RelevantFile {
  path
  score
  parent_directory
}
```

All files above threshold are passed downstream. There is no top-k truncation.

## Failure attribution

V1 has only two meaningful miss classes.

### File rejected

The target file was enumerated and scored below threshold.

This is a calibration/model-quality failure and can be studied from the same score field.

### Unsupported/not enumerated

The file is absent because of deterministic ignore/extension policy.

This is a Harness coverage bug or unsupported-file-type policy issue.

`ancestor_pruned` is impossible by construction.

## Canonical primary-target benchmark

The first gate uses six already frozen tasks on:

`BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`

Targets:

1. reconnect lifecycle -> `crates/nession-agent/src/connection/server_client.rs`
2. protocol catalog consistency -> `crates/nession-protocol-codegen/src/catalog.rs`
3. full-stack command lifecycle -> `crates/nession-server/tests/integration/full_stack.rs`
4. fs symlink/delete semantics -> `crates/nession-agent/src/fs/sandbox.rs`
5. tmux environment/session lifecycle -> `crates/nession-agent/src/tmux/manager.rs`
6. manifest union/wire routing -> `crates/nession-protocol/src/kernel/manifest.rs`

The suite runs twice.

This is a **primary-target recovery benchmark**, not a complete multi-file relevance gold set, so selected-file count is a selectivity/cost measure rather than true precision.

Metrics:

- primary target recall;
- target score;
- selected file count;
- enumerated file count;
- model calls;
- input/output tokens;
- model wall time;
- deterministic miss classification.

## Acceptance gate

V1 is considered mechanically converged when:

1. every primary target is enumerated;
2. every target is recovered in both canonical repeats at the frozen 0.65 threshold, or any miss is shown to be only threshold calibration rather than structural reachability;
3. no result depends on directory pruning, top-k, or model global Stop;
4. every file has one auditable score;
5. quality and cost are reported together.

If a target scores below 0.65, the next allowed experiment is an offline threshold Pareto replay on the same score field, not a new traversal architecture.

## What is now closed

- directory semantics -> **not used for hard pruning**;
- hierarchical vs flat semantic locator -> **flat file-level semantic scoring over mechanically enumerated metadata**;
- Choice vs Noul -> **independent Noul**;
- top-k -> **none**;
- fixed semantic batches -> **none; batching is transport-only**;
- source body visibility -> **none**;
- repeated rescoring -> **none for unchanged semantic state**;
- global model Stop -> **none; terminate after the finite file set is scored**.

## Remaining legitimate research

Only these questions remain inside File Discovery:

1. threshold calibration on a larger frozen benchmark;
2. benchmark breadth across repositories/languages and true multi-file tasks;
3. whether cheap deterministic pre-indexing or caching can reduce scoring cost without changing the logical all-file coverage;
4. future cross-file expansion created by grounded Evidence Localization observations.

These are calibration, efficiency, and composition questions—not new File Discovery architecture questions.

## Canonical convergence result

Canonical workflow: `36104786728`.

Frozen subject:

`BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`

Six primary-target cases x two repeats:

```text
12 / 12 target runs recovered
primary recall = 100%
ancestor-pruned failures = impossible by construction
other failures = 0
```

Average per task:

| metric | value |
| --- | ---: |
| repository files scored | 1,096 |
| selected files | 16.5 |
| max selected files | 35 |
| System One calls | 18 |
| input tokens | 212,584 |
| model wall time | 6.61 s |

The current transport batch size is 64, so 1,096 file questions require 18
physical requests. This is an efficiency parameter, not a semantic one.

### Why the relative guard is retained

The all-file scorer exposed the previous failure clearly:

`crates/nession-agent/src/fs/sandbox.rs`

was always reachable and ranked very highly, but its absolute score was only
0.46-0.47.

Across the diagnostic score fields, all six primary targets ranked within the
top 9 of 1,096 files in both repeats.

Selection replay on the exact same score fields:

| selection rule | primary recall | mean selected files | max selected |
| --- | ---: | ---: | ---: |
| strict score >= 0.65 | 83.3% | 12.7 | 35 |
| strict score >= 0.45 | 100% | 47.4 | 116 |
| score >= 0.65 OR top-1% relative guard | **100%** | **16.5** | **35** |

Therefore the project does **not** globally lower the probability threshold to
repair one under-calibrated task. It keeps high-confidence multi-hit selection
and adds a small rank-based recall guard.

The guard is additive, not a top-k cap: every file above the absolute threshold
is retained even when there are more than 1% of the repository.

### Cost conclusion

V1 is dramatically cleaner than the original 598-call / 5.77M-token
file+line locator, but it is not yet cost-optimal.

Current full file-metadata scoring costs about 212k input tokens / 18 calls per
task on this 1,096-file repository.

This cost is now isolated and deterministic. Future optimizations may reduce
physical calls/tokens through:

- larger transport batches;
- semantic score caching;
- cheap deterministic indexing;
- reusable repository metadata encodings;
- eventually a recall-safe prefilter proven against a broader benchmark.

Such optimizations must preserve the logical all-file coverage contract.

## Final research decision

For the first problem domain, the architecture is now considered **closed at
V1**:

```text
mechanically enumerate files
        ->
independent System One file scores
        ->
absolute high-confidence selection
+ small relative recall guard
        ->
RelevantFile[]
```

Do not return to semantic directory pruning unless new evidence demonstrates a
recall-safe monotonic directory representation.

The next File Discovery work is no longer architecture exploration. It is:

1. reduce the 18-call / 212k-token execution cost without changing the logical
   score field;
2. validate the frozen V1 on fresh multi-file tasks and additional
   repositories/languages;
3. build complete primary/supporting file references so precision can be
   measured honestly;
4. compose V1 with Evidence Localization and measure end-to-end cost.
