# File Discovery Scaling Implementation Plan

**Goal:** Run uncapped file-discovery algorithm and concurrency comparisons on the three frozen repositories, entirely in GitHub Actions, and preserve the results in a research report.

**Architecture:** Keep V1 unchanged. Add a reusable concurrent scorer, a metadata-only adaptive discovery policy, and an experiment runner that separates hidden evaluation labels from runtime inputs. Reuse the existing TypeSafe API and pricing snapshot.

**Tech stack:** Python standard library, unittest, GitHub Actions, existing Noul model API.

## 1. Remote red/green validation

- [x] Add `tests/test_file_discovery_scaling.py` covering concurrency, failure propagation, deterministic merge, cache identity, routing uncertainty, global rescue, and candidate populations above 2,000.
- [x] Push the test-only commit to the research branch. CI [36154615282](https://github.com/BestNathan/system-one-code-explore/actions/runs/36154615282) failed on the missing feature as expected.
- [x] Implement `src/file_discovery_scoring.py` and `src/file_discovery_adaptive.py`; core CI [36154997859](https://github.com/BestNathan/system-one-code-explore/actions/runs/36154997859) passed all 133 tests. Additional report/accounting regressions were verified failing before their implementation.

Scoring interface: `BatchScorer(query, decider, workers=4, batch_size=64, cache=None).score(stage, candidates)`. Responses retain candidate IDs; incomplete/non-finite responses fail rather than becoming low scores. Shared cache identities include ordered batch payloads, stage and model/profile identity.

Discovery interface: `discover(candidates, query, scorer, policy)` with policies `all`, `lexical`, `hierarchy`, `hybrid`. All candidates remain mechanically indexed. Logical selection has no count cap or per-channel quota. Independent batches run concurrently; policy transitions wait for the full wave.

## 2. Experimental policy

- [ ] Build compressed metadata trees from directory relationships; virtual intermediate groups make very broad directories traversable without discarding children.
- [ ] Route using separate descendant-relevance and missing-information Noul answers. Expand if either crosses its preregistered threshold; record deferred subtrees.
- [ ] Lexical rescue uses informative query/path token overlap; no fixed top-k. Hybrid unions lexical and hierarchy paths, then follows same-directory neighbors of high-confidence files until no new files appear.
- [ ] Use the same file decider and final V1 absolute/relative selection rule in every arm. Retain per-path scores and candidate provenance.
- [ ] Explicitly record heuristic stopping, potential routing omissions and cold index time. This first experiment does not claim calibrated uncertainty or complete supporting-file recall.

## 3. Workflow and reports

- [ ] Add `src/file_discovery_scaling_benchmark.py` to run/evaluate the frozen cases, checkpoint every arm, continue after individual failures, and emit JSON plus Markdown.
- [ ] Add `.github/workflows/file-discovery-scaling.yml`, branch-scoped automatic start when the experiment config changes, with the existing owner/environment controls, CI gating and artifact upload on failure.
- [ ] Freeze `fixtures/file-discovery/scaling-experiment.json`: first repeat, nine cases, `all/c1`, `all/c4`, `lexical/c4`, `hierarchy/c4`, `hybrid/c4`, plus an independent cold `hybrid/c4` latency arm. Baseline V1 file prompts, route/uncertainty thresholds 0.5, file threshold 0.65, all frozen before seeing results. Run jobs sequentially to isolate credential-level concurrency.
- [ ] Report original inputs, candidate recall before file scoring, final primary recall, file/card counts, token/call usage, costs, request latency sum versus wall time, failures, retries, and unresolved subtrees. Reuse the frozen System2 reference only as historical context, not a new paid arm.
- [ ] Download Workflow reports, review failure traces and summarize findings in `docs/research/`; link artifacts and commit IDs. A first-repeat diagnostic is not a stability/generalization claim. Use results to choose further repeats rather than blindly rerunning all expensive baselines.

## 4. Review and completion

- [ ] Request independent code review, fix important issues, and verify final CI remotely.
- [ ] Commit research artifacts and update the research index without retriggering paid runs.

No local Python, tests, benchmark, or model requests are permitted. Local operations are limited to editing, reading, Git and GitHub orchestration.
