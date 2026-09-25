# File Discovery V1 — Deterministic Research Convergence

## Status

**Converged mechanism baseline.**

This document closes the open-ended File Discovery design exploration and defines the one V1 architecture that future work should validate, optimize, or falsify.

Do not open new file-discovery architectures unless V1 fails a frozen benchmark for a structural reason.

## Research question

> Can System One recover the task-relevant file set from repository structure and metadata, under progressive disclosure, without reading source bodies and without asking System Two to search the whole repository?

## What the historical experiments already establish

The early nession websocket pilots provide enough mechanism evidence to reject several designs.

### Rejected

1. **Flatten the whole tree into the model prompt.** It scales context with repository size.
2. **Recursively walk selected directories again.** It reintroduces descendants that a previous directory decision already rejected.
3. **Per-line/source scoring during file discovery.** File discovery should end before source localization begins.
4. **Transport batching as semantic progress.** The original implementation reached 598 calls / 5.77M input tokens because candidate batching and per-file line scoring multiplied calls without adding new semantic state.
5. **Fixed top-k files.** Multi-file tasks are multi-hit; top-k is a Harness-imposed semantic cap.
6. **Fixed file batches/order.** Batch order is transport, not task semantics.
7. **Use one activation threshold as both scheduling and global stop.** 'Read now' and 'all relevant files have been covered' are different questions.
8. **Continuously rescore unchanged nodes.** If a node's semantic input has not changed, repeated scoring adds model variance and cost rather than information.

### Retained

1. Directory and file relevance are naturally **independent Noul judgments** because several nodes can be relevant simultaneously.
2. Directory pruning must expose **direct children only**.
3. Source bodies remain hidden during File Discovery.
4. The Harness owns traversal, visibility, budgets, caching, and termination.
5. System One supplies bounded semantic relevance judgments.
6. File false positives are not free: each promoted file can trigger an expensive Evidence Localization runtime.

Historical cost evidence:

- early all-tree / per-line implementation: 598 calls, 5.77M input tokens;
- stabilized three-stage metadata baseline: directory 380 -> 91 and file 272 -> 82 with three total model calls for the full three-stage run, 168,697 input tokens overall;
- later global reader pilot: Phase1 retained 18 files, only three were actually read; the end-to-end run used 12 calls / 195,977 input tokens, demonstrating that fixed top-k/batch ordering was unnecessary.

These numbers are mechanism evidence only; they are not a modern File Discovery quality benchmark.

## V1 scope

V1 answers exactly one question:

> Which files should be handed to Evidence Localization?

V1 is **metadata-only**.

It does not:

- inspect source contents;
- perform range reads;
- follow callers/callees/imports discovered from source;
- schedule evidence reads;
- decide whether enough final code evidence exists.

Those belong to Evidence Localization or a future cross-file expansion stage.

## V1 repository state

```text
FileDiscoveryState {
  task
  root
  disclosed_nodes
  unresolved_directories
  directory_scores
  file_scores
  promoted_files
  usage
}
```

Node states are mechanical:

```text
undisclosed
disclosed
expanded        # directory
pruned          # directory below expand threshold
promoted        # file above file threshold
rejected        # file below file threshold
```

There is no semantic global Stop action.

## Repository view

The Harness may build a cheap filesystem index internally, but the model sees only progressively disclosed node metadata.

Directory payload:

```text
path
name
direct child directory names
direct file names
```

File payload:

```text
path
filename
extension
size_bytes
```

No source body, AST, symbol graph, embeddings, or LSP semantics are part of V1.

## State transition

Start by expanding the repository root mechanically.

For every newly disclosed node, ask System One exactly once:

### Directory Noul

> How likely is this directory/subtree to contain or directly lead to source files materially relevant to the task?

### File Noul

> How likely is this file itself to contain material source evidence relevant to the task?

Scores do not compete or sum to one.

Transition:

```text
root
  -> disclose direct children
  -> independently score each child once

directory score >= directory_threshold
  -> expand directory
  -> disclose its direct children

directory score < directory_threshold
  -> prune subtree

file score >= file_threshold
  -> promote RelevantFile

file score < file_threshold
  -> reject file

repeat until no expandable directory remains
```

Termination is therefore deterministic:

> **frontier exhausted under the frozen directory expansion policy**.

The model does not decide global completion.

## Batching and caching

Transport batching may group independent Noul questions, but batch boundaries must not change semantics.

A node score is cacheable by:

```text
hash(task + canonical node metadata + prompt version + model)
```

If the semantic request is unchanged, the node must not be rescored in the same run.

This both reduces cost and removes model-noise-driven traversal differences.

## V1 thresholds

The initial validation baseline freezes the historical values:

```text
directory_threshold = 0.50
file_threshold      = 0.65
```

These values are **baseline parameters, not proven optima**.

Threshold calibration is allowed only through a frozen File Discovery benchmark. Do not invent new traversal semantics merely because one threshold misses a file.

Because file discovery is recall-sensitive, threshold studies should prefer a Pareto curve over one magic value.

## Output

```text
RelevantFile {
  path
  score
  provenance: {
    parent_directory
    directory_path_scores
  }
}
```

All promoted files are passed to Evidence Localization. V1 has no top-k truncation.

## Failure attribution

A missed primary file should be classified before changing the algorithm.

### Ancestor-pruned miss

An ancestor directory scored below the directory threshold, so the file was never disclosed.

Interpretation: directory recall/calibration failure.

### File-rejected miss

The file was disclosed but scored below the file threshold.

Interpretation: file relevance/calibration failure.

### Unsupported-view miss

Required evidence cannot be inferred from path/metadata alone.

Interpretation: V1 metadata-only boundary; consider a future grounded cross-file expansion mechanism rather than hiding source semantics inside the locator.

## Minimal canonical benchmark

The first gate reuses six already frozen evidence-localization tasks and asks only whether File Discovery recovers their known primary target files.

This is intentionally a **primary-target recovery benchmark**, not a complete multi-file relevance gold set.

Cases:

1. reconnect lifecycle -> `crates/nession-agent/src/connection/server_client.rs`
2. protocol catalog consistency -> `crates/nession-protocol-codegen/src/catalog.rs`
3. full-stack command lifecycle -> `crates/nession-server/tests/integration/full_stack.rs`
4. fs symlink/delete semantics -> `crates/nession-agent/src/fs/sandbox.rs`
5. tmux environment/session lifecycle -> `crates/nession-agent/src/tmux/manager.rs`
6. manifest union/wire routing -> `crates/nession-protocol/src/kernel/manifest.rs`

All use frozen `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`.

Primary metrics:

- primary target recall;
- selected file count;
- scored directory/file count;
- metadata nodes disclosed;
- model calls/tokens/wall time;
- failure attribution for every miss.

Because supporting-file labels are incomplete, **do not claim precision from this benchmark**. Selected-file count is a cost/selectivity measure only.

## V1 acceptance gate

Mechanism V1 is considered usable for composition with Evidence Localization when, on the frozen primary-target benchmark:

1. all primary target files are recovered in the canonical run;
2. no result depends on fixed top-k or model global Stop;
3. every selected/rejected node has one auditable score and ancestry path;
4. all model/source costs are reported;
5. reruns use semantic caching or shared decisions when policies are compared.

If target recall is below 100%, diagnose ancestor-pruned vs file-rejected vs unsupported-view before changing structure.

## What is now closed

The following are no longer open architecture questions for V1:

- flat vs hierarchical repository traversal -> **hierarchical direct-child disclosure**;
- Choice vs Noul for sibling relevance -> **independent Noul**;
- top-k vs multi-hit -> **no top-k**;
- fixed batch order -> **transport-only batching**;
- source body in File Discovery -> **not allowed**;
- repeated rescoring -> **cache unchanged semantic states**;
- global semantic Stop -> **not used; frontier exhaustion terminates**.

## What remains legitimately open

Only three research questions remain inside this domain:

1. **Calibration:** what directory/file thresholds occupy the best recall-cost Pareto frontier?
2. **Benchmark breadth:** does V1 generalize to multi-file tasks, misleading names, and other repositories/languages?
3. **Cross-file expansion:** when metadata is insufficient, what grounded observation from Evidence Localization may create new File Discovery actions without collapsing the two domains?

Everything else should be treated as implementation optimization, not a new File Discovery architecture.