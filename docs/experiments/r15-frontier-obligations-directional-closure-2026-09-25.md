# R15 Frontier Obligations + Directional Closure — 2026-09-25

## Design pre-registration

R15 changes runtime structure rather than tuning R14 thresholds.

Planned invariant:

- Phase0 geometry creates explicit frontier obligations;
- obligations are relative/rank-based so under-calibrated posterior arms still
  produce coverage targets;
- one representative seed is tried per unresolved obligation;
- seed anchors close using only independent need-before / need-after Noul;
- no scalar completeness score controls expansion;
- no pre-closure utility score can kill an anchor;
- final utility is evaluated only after directional closure;
- low final utility means try another representative in the same obligation;
- the phase ends only when every obligation is satisfied or exhausted.

R13/R14 cases may be reused for mechanism diagnosis only.

Primary success criterion:

> compared with R14, reduce hidden-reference premature coverage failure without
> recreating R13's giant merged-region expansion.


## Canonical execution

Workflow run: `36077460697`.

All eight discriminative jobs succeeded:

- reconnect lifecycle x 2 repeats x 2 Phase0 posterior arms;
- full-stack command lifecycle x 2 repeats x 2 Phase0 posterior arms.

The experiment confirms the structural R15 invariants:

- obligations cannot disappear because evidence already feels sufficient;
- anchors close through need-before / need-after only;
- utility is evaluated only after closure;
- low-utility seeds cause another representative attempt rather than deleting
  the obligation.

Primary remaining failure is Phase0-to-obligation geometry. On full-stack
sequential, hidden command-core regions never enter an obligation because
their Phase0 scores are below the global q75 threshold. Multi-scale exposes
those regions and R15 then retains useful evidence.

Canonical pinned outputs:

- `fixtures/research/r15-frontier-obligations-aggregate.json`;
- `fixtures/research/r15-phase0-obligation-coverage-diagnostic.json`.
