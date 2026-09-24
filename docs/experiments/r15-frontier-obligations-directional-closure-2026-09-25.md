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
