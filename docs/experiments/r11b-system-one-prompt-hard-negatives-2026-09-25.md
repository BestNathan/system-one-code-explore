# R11B System One Prompt Calibration — Hard Negatives — 2026-09-25

## Why Phase B exists

R11 Phase A accidentally produced a positive-heavy dataset: all three broad
goal/file pairs had no true low-reference examples below 0.35.

Phase B repairs the benchmark geometry rather than changing prompts.

## Design

Keep the same three source files but define two narrow mechanisms per file.
This creates hard negatives inside the same file: code with the same types,
imports, domain vocabulary, and nearby context can still be irrelevant to the
specific target mechanism.

Cases:

- command broker: stale-generation ownership only;
- command broker: pending request timeout/cleanup only;
- extension registry: duplicate/conflicting routes only;
- extension registry: runtime dispatch only;
- git agent: session-derived cwd security only;
- git agent: typed decode/error mapping only.

The same five frozen Phase A prompt variants are evaluated.

No prompt text is changed after looking at these references.

## Goal

Find which prompt semantics give:

- strong high-vs-rest ranking;
- large high-vs-low probability separation;
- good top-K precision;
- low Brier error.

This is still prompt calibration, not final generalization. A winning prompt
must later be frozen and validated on unseen files.
