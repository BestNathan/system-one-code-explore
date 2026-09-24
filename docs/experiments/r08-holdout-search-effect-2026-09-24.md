# R08 Holdout Search-Effect Experiment — 2026-09-24

## Status

Completed. The holdouts and online-policy parameters below were pre-registered before generating any holdout reference.

This experiment extends R08 Phase C from posterior-field fit to **search
behavior**. No estimator parameter, action-generation rule, Choice threshold,
or holdout definition may be changed after inspecting the references/results
from this round.

## Fixed subject

- repository: `BestNathan/nession`
- revision: `7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
- System One model: repository `typesafe` environment's pinned model
- reference model: repository `ds` environment's pinned explicit model

## Holdouts

These files/tasks were selected from source structure before reference
generation and were not used by the R07 websocket posterior fit.

### H1 — reconnect lifecycle

File:

`crates/nession-agent/src/connection/server_client.rs`

Task:

> Help me improve the agent-to-server reconnect lifecycle: exponential backoff,
> registration after reconnect, connected/sync-needed state transitions, and
> behavior of queued outbound messages while disconnected.

Intent: long source file with lifecycle behavior expected to be spread across
multiple regions.

### H2 — protocol catalog consistency

File:

`crates/nession-protocol-codegen/src/catalog.rs`

Task:

> Help me make protocol contract generation safer: locate the catalog code that
> defines unit identity and wire/request/response mappings and the checks that
> prevent missing, duplicate, or non-self-contained generated contracts.

Intent: catalog declarations plus validation/tests are expected to form a
multi-peak relevance shape.

### H3 — full-stack command lifecycle

File:

`crates/nession-server/tests/integration/full_stack.rs`

Task:

> I am debugging the server's agent command lifecycle. Locate the
> integration-test code that exercises agent registration, command
> request/response routing, disconnect or reconnect behavior, and cleanup of
> pending work.

Intent: large integration-test file with many unrelated sections and relevant
tests expected in separated regions.

## Frozen online policy

Compare only:

- `sequential_exponential`
- `multi_scale_gaussian`

Keep fixed:

- sample width: 8 lines;
- max action candidates: 16;
- max Choice batch: 4;
- default Choice probability threshold;
- `respect_stop=false` so both arms consume the same fixed budget;
- mixed stratified-random / uncertainty / gradient / peak action generation;
- posterior definitions from R07 unchanged.

Probe budget is normalized by file length:

`max(8, min(32, round(line_count * 0.085 / 8)))`

This targets roughly the same 8.5% source-line budget as the R08 websocket run
while keeping a minimum number of decisions for smaller holdouts.

Each estimator is repeated twice per holdout. Candidate geometry remains
deterministically seeded; repeats measure model-policy/scoring variability.

## Reference

For each holdout, generate one fresh full-read System 2 relevance field using
the existing 64-line / 32-line-stride reference protocol.

The reference is evaluation data, not ground truth and not an input to the
online policy.

## Metrics

Retain the existing posterior-fit metrics:

- MAE / RMSE;
- Pearson / Spearman;
- Jensen-Shannon distance;
- high-relevance recall of the reconstructed field.

Add search-oriented metrics over the **actual probe order**:

- first probe touching a high-relevance line;
- first probe touching a core line;
- probes to 50% / 80% high-line recall;
- final high-line recall at the fixed source budget;
- final relevance-mass recall;
- useful-probe rate;
- mean reference relevance of selected probes;
- high-line-recall AUC per probe;
- relevance-mass-recall AUC per probe;
- exact trajectory Jaccard between estimator arms;
- model calls, input tokens, output tokens, and elapsed time.

The AUC-per-probe metrics are the primary search-effect measures because they
reward finding useful regions early, not only eventually.

## Interpretation guardrail

A positive result requires improvement across multiple holdouts and should not
be claimed from aggregate field correlation alone.

If results suggest changing posterior parameters, action quotas, or thresholds,
that change starts a new research iteration with a new evaluation split.


## Execution provenance

References were generated once and then pinned into this repository:

- reference executor: `BestNathan/narness-engineering` workflow run `35990577401`;
- online paired search run: `BestNathan/system-one-code-explore` workflow run `35991332346`;
- durable machine-readable summary:
  `fixtures/research/r08-holdout-search-effect-summary.json`;
- pinned references:
  - `fixtures/research/r08-holdout-reconnect_lifecycle-reference.json`;
  - `fixtures/research/r08-holdout-protocol_catalog_consistency-reference.json`;
  - `fixtures/research/r08-holdout-full_stack_command_lifecycle-reference.json`.

The reference executor used the existing `ds` environment and
`deepseek-flash` through Claude Code. Once normalized, the references were
copied into `fixtures/research/`; the online experiment consumed only those
frozen fixtures.

## Aggregate result

Six paired online runs completed: three holdouts x two repeats. Each paired run
executed the same fixed source-read budget for
`sequential_exponential` and `multi_scale_gaussian`.

| metric | sequential | multi-scale | delta |
| --- | ---: | ---: | ---: |
| mean Pearson | 0.0815 | 0.2150 | +0.1334 |
| mean MAE | 0.2113 | 0.2096 | -0.0017 |
| final high-line recall | **0.0977** | 0.0741 | -0.0236 |
| high-recall AUC / probe | **0.0431** | 0.0321 | -0.0110 |
| weighted-recall AUC / probe | **0.0458** | 0.0413 | -0.0046 |
| useful-probe rate | **0.5605** | 0.4824 | -0.0781 |
| mean input tokens | **81,316.5** | 90,020.2 | +8,703.7 |

Multi-scale wins across the three holdouts:

- high-recall AUC: **0 / 3**;
- weighted-recall AUC: **1 / 3**;
- final high-line recall: **0 / 3**;
- Pearson: 1 / 3;
- MAE: 1 / 3.

The primary search-effect hypothesis is therefore **not supported**.

### Discriminative holdouts

On `reconnect_lifecycle`:

| metric | sequential | multi-scale |
| --- | ---: | ---: |
| Pearson | **0.4873** | 0.4311 |
| MAE | **0.2698** | 0.2858 |
| final high recall | **0.1166** | 0.0865 |
| high-recall AUC / probe | **0.0504** | 0.0354 |
| weighted-recall AUC / probe | **0.0469** | 0.0353 |
| useful-probe rate | **0.4167** | 0.3000 |

Both repeats have the same search direction: sequential has higher high-recall
AUC and useful-probe rate.

On `full_stack_command_lifecycle`:

| metric | sequential | multi-scale |
| --- | ---: | ---: |
| Pearson | **0.2300** | 0.2124 |
| MAE | **0.1931** | 0.2269 |
| final high recall | **0.0906** | 0.0500 |
| high-recall AUC / probe | **0.0335** | 0.0156 |
| weighted-recall AUC / probe | **0.0452** | 0.0426 |
| useful-probe rate | **0.2647** | 0.1471 |

One repeat is especially important: multi-scale produced a better local
sample-score/reference correlation than sequential, yet still produced worse
search recall. This separates **local relevance judgment** from the
**exploration-policy state**.

### Pre-registered degenerate holdout

The `protocol_catalog_consistency` full-read reference scored all 52 canonical
windows at >= 0.70 and marked every window as core. We did not replace the case
after seeing this result.

Consequences:

- every source probe is a "useful" high-relevance probe;
- final high-line recall is effectively source coverage;
- high-recall search metrics cannot discriminate the policies.

The case remains in the aggregate because removing it post hoc would violate
the pre-registration. It is explicitly treated as a reference-degenerate
control rather than evidence of search superiority.

## Failure diagnosis: uncertainty collapse

The strongest signal is not the relevance field. It is the semantics of the
multi-scale uncertainty field.

Across the two discriminative holdouts:

| diagnostic | sequential | multi-scale |
| --- | ---: | ---: |
| reconnect mean uncertainty | 0.4523 | **0.0737** |
| reconnect corr(uncertainty, distance-to-nearest-observation) | **+0.8793** | **-0.4083** |
| reconnect missed-high lines with uncertainty <= 0.10 | 0% | **99.1%** |
| full-stack mean uncertainty | 0.4489 | **0.0946** |
| full-stack corr(uncertainty, distance-to-nearest-observation) | **+0.8787** | **-0.1674** |
| full-stack missed-high lines with uncertainty <= 0.10 | 0% | **78.3%** |

The uncertainty-driven probes show the same failure:

- reconnect uncertainty-probe high-hit rate:
  sequential 27.3%, multi-scale 15.4%;
- full-stack uncertainty-probe high-hit rate:
  sequential 31.3%, multi-scale 0%.

The current adaptive Gaussian estimator derives bandwidth from distance to the
k-th nearest observation and then derives uncertainty from Gaussian support.
In sparse regions the bandwidth grows with observation distance. Normalized
distance therefore stays small enough that distant observations still produce
large support.

This creates the wrong epistemic behavior:

```text
far from observations
        ->
larger adaptive bandwidth
        ->
apparently strong support
        ->
low "uncertainty"
```

The online action generator then treats that support-derived value as epistemic
uncertainty and deprioritizes exactly the sparse regions that should remain
uncertain.

## Conclusion

R07 and R08 Phase B demonstrated that a path-independent multi-scale estimator
can reconstruct a relevance field better on a fixed trajectory / single online
fixture.

R08 Phase C shows that this does **not** imply better search.

The current design incorrectly couples two distinct quantities:

```text
P(relevance | observations)
epistemic uncertainty / need-to-observe
```

The next iteration must keep these concepts separate. R09 will hold the
multi-scale relevance reconstruction fixed and change only the exploration
uncertainty semantics. The three R08 holdouts become a diagnosis set only; no
R09 generalization claim may be made from them.
