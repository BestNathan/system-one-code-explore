# R03 — Full-read System 2 Reference Field

## Question

How can we evaluate whether sparse System One exploration has reconstructed the
relevant parts of the *whole file*, rather than merely compare final evidence
sets?

## Hypothesis

A System 2 evaluator that reads the complete file and scores a canonical set of
overlapping windows can serve as a stable reference relevance field.

## Design

The reference pipeline:

1. freezes repository, revision, file and query;
2. constructs canonical 64-line windows with stride 32;
3. gives the complete source to Claude Code;
4. asks it to score every canonical window;
5. strictly validates that every returned range preserves canonical geometry.

For the current benchmark, Claude Code runs through the `ds` environment and
its configured DeepSeek Anthropic-compatible route.

Raw report:

- `docs/experiments/full-read-claude-baseline-2026-09-24.md`

Validated reference run:

- narness workflow run `35959563085`
- subject: `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- file: `crates/nession-agent/src/server/websocket.rs`
- 3030 lines
- 94 canonical windows

## Result

The full-read field changed the research target from:

```text
Did the sparse runtime find some useful ranges?
```

to:

```text
How close is the sparse runtime's relevance distribution
to the full-read relevance distribution?
```

Strict validation proved necessary because model output can drift from the
requested canonical geometry.

## Retained principle

Reference generation and System One exploration must remain separate.

The full-read evaluator is a measurement instrument, not part of the System One
runtime.

## Next direction

Measure convergence of the Phase0 probability field against this fixed
reference after every additional sparse observation.
