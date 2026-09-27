# Issue 14 — Global Directory Classification

- Workflow: https://github.com/BestNathan/system-one-code-explore/actions/runs/36298796510
- Repository: `aggregate`
- Directory candidates are globally enumerated before Phase 1; no directory score gates another directory.
- Phase 2 enumerates direct files only. No source bodies, top-k, or hard candidate caps are used.

| Case | Arm | Status | Candidate recall | Final recall | Total files | All dirs | Selected dirs | Phase 2 files | Promoted | Visible nodes | P1 calls | P1 in/out tokens | P2 calls | P2 in/out tokens | Total calls | Wall s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| codex_approval_routing | flat_path | success | 100% | 100% | 6277 | 0 | 0 | 928 | 75 | 928 | 0 | 0/0 | 15 | 165743/17542 | 15 | 1.9 |
| codex_approval_routing | global_directory | success | 0% | 0% | 6277 | 938 | 9 | 116 | 29 | 1054 | 15 | 277293/17732 | 2 | 22091/2192 | 17 | 1.5 |
| codex_mcp_tool_approval | flat_path | success | 100% | 100% | 6277 | 0 | 0 | 2414 | 106 | 2414 | 0 | 0/0 | 38 | 444623/45638 | 38 | 3.1 |
| codex_mcp_tool_approval | global_directory | success | 0% | 0% | 6277 | 938 | 5 | 72 | 7 | 1010 | 15 | 272528/17732 | 2 | 14192/1358 | 17 | 1.4 |
| codex_thread_resume_persistence | flat_path | success | 100% | 100% | 6277 | 0 | 0 | 858 | 87 | 858 | 0 | 0/0 | 14 | 155416/16218 | 14 | 1.7 |
| codex_thread_resume_persistence | global_directory | success | 0% | 0% | 6277 | 938 | 7 | 124 | 33 | 1062 | 15 | 276340/17732 | 2 | 22876/2344 | 17 | 1.5 |
| nession_backend_reconnect_lifecycle | flat_path | success | 100% | 100% | 1096 | 0 | 0 | 100 | 10 | 100 | 0 | 0/0 | 2 | 18361/1888 | 2 | 0.4 |
| nession_backend_reconnect_lifecycle | global_directory | success | 100% | 100% | 1096 | 381 | 1 | 2 | 2 | 383 | 6 | 184649/7203 | 1 | 894/40 | 7 | 0.8 |
| nession_filesystem_symlink_delete_safety | flat_path | success | 100% | 0% | 1096 | 0 | 0 | 15 | 1 | 15 | 0 | 0/0 | 1 | 3072/279 | 1 | 0.2 |
| nession_filesystem_symlink_delete_safety | global_directory | success | 0% | 0% | 1096 | 381 | 0 | 0 | 0 | 381 | 6 | 186584/7203 | 0 | 0/0 | 6 | 0.8 |
| nession_frontend_request_correlation | flat_path | success | 100% | 100% | 1096 | 0 | 0 | 27 | 3 | 27 | 0 | 0/0 | 1 | 5137/507 | 1 | 0.2 |
| nession_frontend_request_correlation | global_directory | success | 100% | 100% | 1096 | 381 | 1 | 5 | 2 | 386 | 6 | 186584/7203 | 1 | 1348/94 | 7 | 0.8 |
| openclaw_gateway_ws_dispatch | flat_path | success | 100% | 100% | 43748 | 0 | 0 | 7918 | 257 | 7918 | 0 | 0/0 | 124 | 1367934/149698 | 124 | 12.4 |
| openclaw_gateway_ws_dispatch | global_directory | success | 100% | 100% | 43748 | 1907 | 6 | 292 | 52 | 2199 | 30 | 559100/36053 | 5 | 54748/5518 | 35 | 3.7 |
| openclaw_skill_source_precedence | flat_path | success | 100% | 100% | 43748 | 0 | 0 | 4587 | 79 | 4587 | 0 | 0/0 | 72 | 784913/86721 | 72 | 8.9 |
| openclaw_skill_source_precedence | global_directory | success | 100% | 100% | 43748 | 1907 | 3 | 148 | 27 | 2055 | 30 | 561037/36053 | 3 | 26312/2794 | 33 | 3.4 |
| openclaw_memory_hybrid_search | flat_path | success | 100% | 100% | 43748 | 0 | 0 | 1391 | 62 | 1391 | 0 | 0/0 | 22 | 236520/26297 | 22 | 5.0 |
| openclaw_memory_hybrid_search | global_directory | success | 100% | 100% | 43748 | 1907 | 7 | 287 | 44 | 2194 | 30 | 547478/36053 | 5 | 53306/5423 | 35 | 3.6 |

## Target Routing

- codex_approval_routing / flat_path / `codex-rs/core/src/tools/approvals.rs`: directory selection: not applicable; file scored: True; score: 0.87; promoted: True
- codex_approval_routing / global_directory / `codex-rs/core/src/tools/approvals.rs`: directory selected: False; file scored: False; score: None; promoted: False
- codex_mcp_tool_approval / flat_path / `codex-rs/core/src/mcp_tool_call.rs`: directory selection: not applicable; file scored: True; score: 0.86; promoted: True
- codex_mcp_tool_approval / global_directory / `codex-rs/core/src/mcp_tool_call.rs`: directory selected: False; file scored: False; score: None; promoted: False
- codex_thread_resume_persistence / flat_path / `codex-rs/core/src/thread_manager.rs`: directory selection: not applicable; file scored: True; score: 0.86; promoted: True
- codex_thread_resume_persistence / global_directory / `codex-rs/core/src/thread_manager.rs`: directory selected: False; file scored: False; score: None; promoted: False
- nession_backend_reconnect_lifecycle / flat_path / `crates/nession-agent/src/connection/server_client.rs`: directory selection: not applicable; file scored: True; score: 0.82; promoted: True
- nession_backend_reconnect_lifecycle / global_directory / `crates/nession-agent/src/connection/server_client.rs`: directory selected: True; file scored: True; score: 0.83; promoted: True
- nession_filesystem_symlink_delete_safety / flat_path / `crates/nession-agent/src/fs/sandbox.rs`: directory selection: not applicable; file scored: True; score: 0.55; promoted: False
- nession_filesystem_symlink_delete_safety / global_directory / `crates/nession-agent/src/fs/sandbox.rs`: directory selected: False; file scored: False; score: None; promoted: False
- nession_frontend_request_correlation / flat_path / `web/src/platform/socket/MessageRouter.ts`: directory selection: not applicable; file scored: True; score: 0.8; promoted: True
- nession_frontend_request_correlation / global_directory / `web/src/platform/socket/MessageRouter.ts`: directory selected: True; file scored: True; score: 0.8; promoted: True
- openclaw_gateway_ws_dispatch / flat_path / `src/gateway/server/ws-connection/message-handler.ts`: directory selection: not applicable; file scored: True; score: 0.89; promoted: True
- openclaw_gateway_ws_dispatch / global_directory / `src/gateway/server/ws-connection/message-handler.ts`: directory selected: True; file scored: True; score: 0.88; promoted: True
- openclaw_skill_source_precedence / flat_path / `src/skills/loading/workspace-skill-sources.ts`: directory selection: not applicable; file scored: True; score: 0.87; promoted: True
- openclaw_skill_source_precedence / global_directory / `src/skills/loading/workspace-skill-sources.ts`: directory selected: True; file scored: True; score: 0.88; promoted: True
- openclaw_memory_hybrid_search / flat_path / `extensions/memory-core/src/memory/manager-search-orchestration.ts`: directory selection: not applicable; file scored: True; score: 0.89; promoted: True
- openclaw_memory_hybrid_search / global_directory / `extensions/memory-core/src/memory/manager-search-orchestration.ts`: directory selected: True; file scored: True; score: 0.89; promoted: True
- codex_approval_routing / global_directory: codex-rs/core/src/tools/approvals.rs (target_directory_not_selected)
- codex_mcp_tool_approval / global_directory: codex-rs/core/src/mcp_tool_call.rs (target_directory_not_selected)
- codex_thread_resume_persistence / global_directory: codex-rs/core/src/thread_manager.rs (target_directory_not_selected)
- nession_filesystem_symlink_delete_safety / flat_path: crates/nession-agent/src/fs/sandbox.rs (file_score_rejected)
- nession_filesystem_symlink_delete_safety / global_directory: crates/nession-agent/src/fs/sandbox.rs (target_directory_not_selected)

## Interpretation Notes

- Phase 1 batches are fixed from the complete directory population; later batches do not depend on earlier scores.
- Results compare full policies with independent model calls; no counterfactual cache is shared between arms.
- The nine targets are diagnostic primary labels, not complete supporting-file ground truth.

## End-to-End Cost Distribution

| Metric | p50 | p95 | Max |
| --- | ---: | ---: | ---: |
| model_visible_nodes | 1010 | 7918 | 7918 |
| physical_calls | 17 | 124 | 124 |
| input_tokens | 236520 | 1367934 | 1367934 |
| output_tokens | 19090 | 149698 | 149698 |
| phase_1_directory_candidates | 0 | 1907 | 1907 |
| phase_2_file_candidates | 124 | 7918 | 7918 |

## Physical Batch-Size Distribution

| Phase | p50 | p95 | Max |
| --- | ---: | ---: | ---: |
| directory | 64 | 64 | 64 |
| file | 64 | 64 | 64 |

## Repository and Arm Summary

| Repository | Arm | Tasks | Mean candidate recall | Mean final recall | Mean Phase 1 dirs | Mean Phase 2 files | Mean visible nodes | Mean input tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BestNathan/nession | flat_path | 3/3 | 100.0% | 66.7% | 0.0 | 47.3 | 47.3 | 8857 |
| BestNathan/nession | global_directory | 3/3 | 66.7% | 66.7% | 381.0 | 2.3 | 383.3 | 186686 |
| openai/codex | flat_path | 3/3 | 100.0% | 100.0% | 0.0 | 1400.0 | 1400.0 | 255261 |
| openai/codex | global_directory | 3/3 | 0.0% | 0.0% | 938.0 | 104.0 | 1042.0 | 295107 |
| openclaw/openclaw | flat_path | 3/3 | 100.0% | 100.0% | 0.0 | 4632.0 | 4632.0 | 796456 |
| openclaw/openclaw | global_directory | 3/3 | 100.0% | 100.0% | 1907.0 | 242.3 | 2149.3 | 600660 |
