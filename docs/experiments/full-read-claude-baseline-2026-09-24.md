# Full-Read Claude Relevance Field Baseline

## Purpose

This baseline answers a different question from the previous Claude-overlap
comparison:

> If a System 2 model has the entire file available, what relevance
> distribution does it assign to the file?

It is a reference field, not ground truth.

## Canonical grid

The first experiment uses overlapping windows:

- window: 64 lines
- stride: 32 lines
- overlap: 32 lines

For every window Claude sees the complete file before scoring. A range can be
highly relevant even when it is a fragment of a larger function.

Each range receives:

- relevance: 0..1
- role: core, supporting, context, incidental, irrelevant
- continuity: self_contained, requires_left, requires_right, requires_both
- reason: concise rationale

## Why this matters

The previous comparison measured System One against another exploration
strategy. That cannot tell us how much relevant material exists in the file.

This field lets us measure:

1. weighted relevance recall;
2. high-relevance window recall;
3. core-window recall;
4. evidence precision against the reference field;
5. source coverage;
6. continuity/closure coverage.

Blind downstream Claude evaluation remains separate and answers whether the final
localization result is actually useful.

## Invariants

- same task;
- same frozen repository revision;
- exact canonical range geometry;
- complete source supplied before scoring;
- every canonical range exactly once;
- baseline output is labeled reference, never ground truth.

## First target

Repository:
BestNathan/nession

Revision:
7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df

File:
crates/nession-agent/src/server/websocket.rs

Task:
Help me optimize the websocket connection implementation
