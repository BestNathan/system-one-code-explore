# R10 Final Evidence Quality — 2026-09-25

## Pre-registration

R10 consumes canonical R08 run 36004833542 without rerunning Phase0.

Final evidence is fixed to:

- top Phase0-scored observed probes;
- non-overlapping 32-line context windows;
- at most six snippets;
- at most 192 source lines.

Compare sequential_exponential and multi_scale_gaussian.

Evaluation uses the matching canonical full-read System 2 reference from the same R08 workflow run.

Primary outputs:

- reference precision of final snippets;
- high-line recall;
- relevance-mass recall;
- same-budget oracle gap;
- literal source snippets.

No evidence-selector prompt is tuned in this iteration.
