# Architecture

## Model

The current runtime is a hierarchical adaptive range search with a System One policy.

```text
Repository
   ↓
Phase 1 directory/file scoring
   ↓
Candidate files
   ↓
Independent FileRuntime(s)
   ↓
┌────────────────────────────────────────────┐
│ FileState                                  │
│  coverage                                  │
│  observations                              │
│  last_selected_ranges                      │
│  action_history                            │
└────────────────────────────────────────────┘
   ↓
Harness generates legal actions from geometry
   ↓
System One
   ├─ Choice: StopFile / ContinueFile
   └─ Noul: utility(ReadRange)
   ↓
Conflict reconciliation when required
   ↓
Read effect
   ↓
Observation
   ↺
   ↓ stop
Post-navigation evidence scoring
   ↓
Canonical localization result
```

## Invariants

### Harness owns mechanics

The harness may reason about:

- paths;
- line counts;
- ranges;
- coverage;
- unread gaps;
- action history;
- budgets;
- effect validity.

It should not silently perform source-level semantic interpretation to compensate for the model.

### System One owns semantic local decisions

The model judges:

- whether current observations are sufficient;
- expected utility of concrete reads;
- relevance of observed evidence.

### Stop is not a numeric threshold rule

The parallel threshold controls which reads may execute concurrently. It is not a hidden stop rule.

If control and concrete utility disagree, the model explicitly resolves the contradiction.

### Navigation and evidence are separate

A range may be worth reading for exploration but not worth retaining in the final result.

Post-navigation evidence scoring must not retroactively alter the executed navigation trace.

## Current limitation

The current state graph only expands along line ranges inside files chosen by Phase 1.

The next architecture introduces observation-driven effects that can create new FileRuntimes, beginning with `FollowFile`.
