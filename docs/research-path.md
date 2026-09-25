# Research Path

This is the problem-oriented view of the research. The chronological source of truth remains `docs/research/README.md`.

## Project thesis

The project investigates whether a fast System One model can perform high-quality code localization when a harness owns state, legal actions, effects, progressive disclosure, durability, budgets, caching, and evaluation.

System Two is the stronger reference and possible escalation path. The research target is to discover which localization decisions can reliably move to System One.

## Track A — Bounded exploration (R01–R05)

Questions:
- Can System One drive code reads without an open-ended ReAct loop?
- How should range actions be generated?
- Should state be coarse ranges or sparse observations?
- How should Choice and Noul semantics differ?

Retained conclusions:
- bounded System One decisions are viable;
- eager/fixed traversal is harmful;
- sparse observations are better state than a few coarse region scores;
- Choice and independent read utility are different semantics.

## Track B — Global file-local state (R06–R09)

Questions:
- How can sparse observations describe the whole file?
- Can relevance be reconstructed as a file-length field?
- How should uncertainty behave far from observations?

Retained conclusions:
- use a file-length probability/relevance frontier;
- keep raw observations durable and posterior reconstruction replaceable;
- multi-scale/path-independent reconstruction can outperform sequential propagation;
- relevance support is not epistemic uncertainty;
- unread areas require an explicit exploration-uncertainty treatment.

## Track C — From frontier to evidence (R10–R14)

Questions:
- Which observations become final evidence?
- Should evidence count be fixed?
- How should a relevant but truncated fragment expand?
- What should determine stopping?

Retained conclusions:
- fixed top-N evidence is artificial;
- multiple high-value actions need independent Noul semantics;
- one marginal score cannot safely represent coverage, utility, and completeness;
- merged-region completeness can run away;
- closure must be anchor-local;
- before/after continuation is more actionable than scalar completeness;
- utility belongs after closure.

## Track D — Coverage obligations and geometry (R15–R17)

Questions:
- How do independent relevance regions remain durable?
- How should a probability field create obligations?
- Can secondary relevance modes recover q75 false negatives?

Retained conclusions:
- coverage obligations belong to the harness;
- q75 connected components are a useful simple baseline;
- lowering thresholds buys recall with source/cost inflation;
- prominence can expose some secondary modes;
- wide basins are too broad;
- narrow persistent secondary peaks can recover some missed evidence;
- extra obligations create downstream call/token cost;
- geometry cannot recover a genuine Phase0 false negative.

## Track E — Fresh validation and causal comparison (R18–R19)

R18 froze a promoted geometry and moved to fresh files/goals. Raw A/B results exposed a methodological bug: identical geometry and source state could receive 0.59 vs 0.60 from independent System One calls, crossing a hard threshold and creating a fake policy win.

Retained conclusion:

> Identical semantic states must share the same System One decision in counterfactual policy comparison.

R19 introduces a shared semantic-decision cache and separates logical standalone usage from physical cached usage.

## Track F — Cost efficiency

Cost is now a first-class research dimension.

Observed patterns:
- better Phase0 state can lower total cost by preventing false obligations;
- merged contexts reduce call count but can explode tokens;
- anchor-local closure reduces context size but may increase calls;
- false-positive obligations create expensive seed/closure tails;
- deterministic geometry is almost free compared with model decisions.

Current optimization directions:
- batch directional closure across anchors;
- send boundary windows instead of full growing anchors;
- cache semantic states;
- stop Phase0 based on frontier/obligation stability;
- prioritize work by expected quality gain per call/token.

## Enduring problem domains

All future experiments should be primarily assigned to one of:

1. [File discovery](domains/file-discovery.md)
2. [Evidence localization](domains/evidence-localization.md)

Cross-cutting work belongs to benchmark/evaluation, cost/runtime, or counterfactual methodology.

The Rxx sequence is the research history, not the conceptual architecture.