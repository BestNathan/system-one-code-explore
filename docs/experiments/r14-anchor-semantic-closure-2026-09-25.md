# R14 Anchor-Centered Semantic Closure — 2026-09-25

## Pre-registration

R14 is a mechanism follow-up to R13 and reuses the same R08 Phase0 trajectories for diagnosis. It is not a fresh generalization set.

Frozen source:

- Phase0/reference run: `36004833542`;
- three R08 tasks;
- two repeats;
- sequential and multi-scale posterior arms.

Frozen policy:

- 32-line global actions;
- independent representative-frontier coverage Noul;
- independent intrinsic task-utility Noul;
- each acquired tile becomes its own anchor;
- anchor-local utility/completeness/before/after Noul;
- completeness >= 0.70 closes an anchor;
- useful incomplete anchors expand before/after at >= 0.60;
- false-positive/low-utility anchors do not expand;
- maximum 12 tiles per anchor is safety-only;
- anchors remain independent during closure;
- final output may merge overlapping/adjacent anchor ranges only after closure.

Primary comparison is against the R13 merged-region closure behavior.

Key question:

> Does binding completeness to an evidence anchor prevent runaway expansion while still turning truncated hits into complete local semantic units?
