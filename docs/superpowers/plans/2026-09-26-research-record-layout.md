# Research Record Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every experiment auditable from a dedicated root `research/` directory and establish `main` as the only experiment branch.

**Architecture:** Each experiment owns one directory containing a five-section report, frozen summary data, and GitHub Actions metadata. Repository-level documentation links these directories chronologically, while `AGENTS.md` defines the mandatory process for future experiments.

**Tech Stack:** Markdown, JSON, GitHub Actions, Git.

---

### Task 1: Define the repository experiment contract

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Create: `research/README.md`

- [ ] Document direct-to-`main`, GitHub-Actions-only execution, the required five report sections, and Workflow/artifact evidence.
- [ ] Add a chronological experiment tracker to the repository README.

### Task 2: Reorganize the three completed experiments

**Files:**
- Create: `research/2026-09-26-file-discovery-scaling-v1/`
- Create: `research/2026-09-26-file-discovery-semantic-routing-v2/`
- Create: `research/2026-09-26-file-discovery-stable-selection-replay/`
- Modify: `docs/research/README.md`

- [ ] Move each report into its experiment directory and normalize its required sections.
- [ ] Store the fixed summary under `data/summary.json` and Workflow run/job/artifact evidence under `workflow/metadata.json`.
- [ ] Move the first experiment's design documents into its directory and update all repository links.

### Task 3: Align automation and verify remotely

**Files:**
- Modify: `.github/workflows/file-discovery-scaling.yml`
- Modify: `.github/workflows/file-discovery-selection-replay.yml`

- [ ] Change experiment workflow branch triggers to `main` and align documentation paths.
- [ ] Commit and push directly to `main`.
- [ ] Verify the resulting commit only through GitHub Actions and record the run URL.
