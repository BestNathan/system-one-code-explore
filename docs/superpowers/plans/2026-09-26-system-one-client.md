# Shared System One Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every physical System One model call through one reusable client without changing research prompts or algorithm parsing.

**Architecture:** Add `src/system_one_client.py` as the only HTTP, retry, raw-record, and usage-normalization boundary. Keep `SystemOneDecider` as an algorithm compatibility adapter that delegates to the client, so all existing decider subclasses migrate without prompt changes.

**Tech Stack:** Python standard library, unittest, GitHub Actions.

---

### Task 1: Specify the shared boundary

**Files:**
- Modify: `tests/test_system_one_code_locator.py`
- Modify: `tests/test_file_discovery_scaling.py`

- [ ] Require a reusable `SystemOneClient.call(stage, state, questions)` API.
- [ ] Require `SystemOneDecider` to own and delegate to the shared client.
- [ ] Require `system_one_client.py` to be the only production module importing the HTTP transport.
- [ ] Push the test-only commit and confirm GitHub Actions fails for the missing client.

### Task 2: Extract transport and preserve behavior

**Files:**
- Create: `src/system_one_client.py`
- Modify: `src/system_one_code_locator.py`
- Modify: `tests/test_system_one_code_locator.py`

- [ ] Move payload construction, request hashing, call IDs, retries, HTTP transport, raw response/error records, and usage normalization into `SystemOneClient`.
- [ ] Delegate `SystemOneDecider.request` and `SystemOneDecider.send` to the client while preserving subclass overrides used by offline tests and research caches.
- [ ] Move transport monkeypatches in legacy tests to the new module.
- [ ] Push and confirm the complete GitHub Actions suite passes.

### Task 3: Enforce the shared client

**Files:**
- Modify: `AGENTS.md`

- [ ] Require all future online research to call System One through `SystemOneClient` or its compatibility adapter.
- [ ] Verify English-only content, clean Git state, and synchronization with `origin/main`.
