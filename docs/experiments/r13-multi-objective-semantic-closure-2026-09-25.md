# R13 Multi-Objective Evidence + Semantic Closure — 2026-09-25

## Pre-registration

Frozen source inputs:

- Phase0/reference run: `36004833542`;
- subject:
  `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`;
- R08 three single-file tasks;
- two repeats;
- sequential and multi-scale Phase0 arms.

Frozen R13 policy:

- 32-line non-overlapping global actions;
- independent Noul `frontier_coverage`;
- independent Noul `task_utility`;
- read an unread tile when coverage >= 0.65 OR utility >= 0.65;
- merge adjacent materialized tiles;
- score literal materialized regions for utility and semantic completeness;
- a useful region with completeness < 0.70 can request its immediate preceding
  and/or following unread tile;
- execute each directional expansion with Noul >= 0.60;
- merge and reassess after expansion;
- normal stop requires no global acquisition and no semantic expansion;
- 12 rounds is safety-only.

Primary comparison baselines:

- R10 fixed-six evidence;
- R12 independent marginal-evidence Noul.

Primary questions:

1. Does independent frontier coverage prevent R12's post-evidence collapse?
2. How often does semantic closure expand a selected fragment?
3. Do final evidence regions become more complete without destroying precision?
4. Does added source cost buy recall/coverage rather than redundant context?

The hidden CC reference is used only for post-run evaluation.
