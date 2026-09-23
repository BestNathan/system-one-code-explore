# Research Summary

## Current result

The validated System One code locator demonstrates that a fast System One model can act as a policy over a bounded, progressively disclosed action space instead of running a ReAct loop.

On the frozen Nession WebSocket task, the successful end-to-end run completed in 22.743 seconds and received 71/100 from a blind downstream-quality evaluator. The Claude Code-style System 2 reference completed in 96.347 seconds and received 83/100. Both were judged usable for downstream engineering work.

System One covered 69.9% of the lines retained by the System 2 reference while following a substantially different exploration path.

## Cost interpretation

The present advantage is clearly latency, not yet proven monetary cost.

System One used many shallow decisions: 96 calls and 724,127 input tokens in the successful run. The System 2 reference used 40 turns, 38 tool calls, 75,469 non-cache input tokens, and 624,384 cache-read input tokens.

Future work must reduce repeated state/context transmission and record actual System One provider cost.

## Stop reconciliation

The earlier range runtime often continued after all concrete read utilities had collapsed, because it executed an unconditional best remaining read. Large files therefore approached full coverage.

The current runtime treats disagreement between the control decision and concrete read utility as an explicit second decision.

After this change, repeated runs on the same frozen task/revision used 94, 86, and 96 reads. Large files terminated through `model_stop` rather than budget exhaustion.

## Blind evaluation

The blind evaluator scores:

- completeness;
- relevance precision;
- evidence grounding;
- redundancy efficiency;
- downstream actionability;
- organization/prioritization;
- risk/uncertainty coverage.

It is allowed to inspect the frozen source repository. Candidates are anonymized so the evaluator is not asked which system it prefers.

The evaluator identified the major remaining gap as cross-file discovery and evidence organization, not inability to stop.

## Research thesis

The emerging thesis is:

> System One models are most useful as fast policies inside a harness that owns state, legal actions, effects, and progressive disclosure.

The next test is whether observation-driven state expansion can recover cross-file causal structure without turning the model back into a free-form ReAct agent.
