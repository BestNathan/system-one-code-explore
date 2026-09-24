# Phase0 + Choice + Evidence Closure v3

## Controlled run

Subject:
BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df

File:
crates/nession-agent/src/server/websocket.rs

Task:
Help me optimize the websocket connection implementation

Parameters:

- Phase0: 4 coarse regions, 112-line head/middle/tail samples
- Phase1: 10 rounds
- Choice action set: up to 6 legal exploration actions plus Stop
- Value refresh: Noul after every executed action
- Final closure: group fine fragments from the same observation before Choice
- final window: 32 lines
- max candidates: 24

## Result

| Metric | Range | Phase0 + Choice + closure |
| --- | ---: | ---: |
| model calls | 13 | 22 |
| input tokens | 130,877 | 362,835 |
| output tokens | 1,154 | 2,035 |
| reads | 17 | 22 |
| elapsed | 5.26s | 10.65s |
| source coverage | 78.55% | 69.80% |
| evidence regions | 7 | 5 |
| termination | model_stop | round_budget_exhausted |

Frontier coverage reached 100% after the Phase0 coarse bootstrap and adaptive
refinement. The 100% figure is current frontier-leaf coverage; Phase0 itself
also records explicit coarse coverage = 100%.

Action distribution:

- refine_high: 4
- missing_frontier: 2
- resolve_gradient: 3
- volatility_revisit: 1

Final evidence:

- Range: 1-140, 281-420, 582-721, 722-861, 862-1001, 1305-1444, 1445-1584
- Frontier v3: 513-624, 892-1003, 1176-1287, 1328-1422, 1423-1516

The frontier evidence covered 65.14% of the Range evidence line mass, while
Range covered 34.90% of the Frontier evidence line mass. Neither is ground
truth.

## What changed

### Phase0

The first Phase0 implementation read one midpoint probe per coarse region.
That was too weak as an independent initial field: the probe could miss a
relevant function inside a large coarse region.

v3 therefore samples head, middle, and tail of every depth-0 region before
scoring the region. This produces 12 initial reads for the four coarse regions
and a much more explicit initial relevance distribution.

### Choice policy

The first Choice experiment accidentally exposed only one exploration action
plus Stop. That did not test the intended policy semantics.

v2/v3 expose up to six harness-generated legal actions plus Stop. Choice now
selects the next action from a real action space containing refine, missing
frontier, gradient, volatility, and stop actions.

### Evidence closure

v2 demonstrated a concrete failure: the observed 1271-1382 span was split into
four fine candidates and every fragment was independently dropped, even though
the complete observed span was relevant enough to have been explored.

v3 groups contiguous fine fragments from the same observation and asks Choice
to retain/drop the complete group. This preserves evidence continuity.

## Interpretation

The experiment supports the architecture:

Phase0 = establish a coarse relevance field.

Phase1 = Choice policy over harness-generated actions.

Value refresh = Noul relevance estimation after actions.

Phase2 = group-aware evidence closure.

It does not yet establish that this architecture beats the Range runtime. The
main remaining cost is context transmission: 22 calls consumed 2.77x the input
tokens of Range. The next optimization should therefore reduce state
retransmission without collapsing the explicit policy/value separation.

## Next

1. Complete the full-read Claude reference field baseline.
2. Project Range and v3 onto that reference field.
3. Add closure/continuity metrics.
4. Complete the blind Claude quality evaluation.
5. Replace full-state retransmission with compact frontier deltas.
6. Add true information-gain StopFrontier instead of the hard round budget.
