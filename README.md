# System One Code Explore

Researching whether a **System One model, when placed inside a constrained
harness, can replace or approximate System Two code search/localization well
enough to find the files and concrete source evidence required by an engineering
task — at materially lower latency and cost**.

This repository is not primarily a code-search product. It is an experimental
repository for discovering a reusable **System One code-localization pattern**.

## Research goal

Given a repository and a natural-language engineering task:

```text
Repository + Task
        |
        v
 System One Harness
        |
        +--> Which files are relevant?
        |
        +--> Which exact source spans are evidence?
        |
        v
 Localization Result
```

The central question is:

> Can a fast System One model, operating over progressively disclosed,
> harness-controlled state and action spaces, locate task-relevant files and
> task-relevant code evidence with quality close enough to a stronger System
> Two reference, while using fewer tokens, fewer model calls, and less wall
> time?

The project is therefore about **localization**, not code generation.

Downstream coding, planning, fixing, and review are intentionally outside the
primary benchmark. Their quality may be used later as blind downstream
validation of the evidence produced here.

## Two problem domains

System One code localization currently has two first-class problem domains.

### 1. File discovery

Find the repository files that deserve inspection.

The V1 mechanism is now converged:

```text
repository
    -> mechanically enumerate supported file metadata
    -> independent System One Noul score per file
    -> absolute high-confidence selection
       + top-1% relative recall guard
    -> RelevantFile[]
```

Semantic directory pruning is explicitly rejected: relevance of a deep file is
not monotonic in shallow parent-directory metadata.

On the frozen six-case convergence suite, V1 recovered 12/12 primary targets
across two repeats. Current cost on the 1,096-file nession fixture is about 18
model calls / 212k input tokens / 6.6s model wall time per task; reducing that
physical cost without changing logical all-file coverage is now an optimization
problem rather than a new search architecture.

See [File discovery](docs/domains/file-discovery.md) and
[File Discovery V1](docs/domains/file-discovery-v1.md).

### 2. Evidence localization inside a file

Given a candidate file, find the literal source spans that can serve as
evidence for the task.

```text
candidate file
    |
    v
sparse observations / probability frontier
    |
    v
coverage obligations
    |
    v
evidence anchors
    |
    v
directional semantic closure
    |
    v
EvidenceSpan[]
```

Questions include:

- how to reconstruct a useful whole-file relevance state from sparse reads;
- how to turn that field into durable coverage obligations;
- how to avoid both premature stopping and whole-file reading;
- how to recover secondary modes, shoulders, or under-observed relevant areas;
- how to turn a relevant 32-line hit into a semantically complete function,
  branch, state transition, or local behavior;
- how to separate navigation value from final evidence value;
- how to reduce closure calls, repeated context, tokens, and tail latency.

See [Evidence localization](docs/domains/evidence-localization.md).

## System One / System Two comparison

System Two is used as a **reference and benchmark**, not as unquestionable
ground truth.

The current reference protocol lets a stronger model inspect the complete
target scope before assigning relevance to overlapping source ranges. System
One then has to recover useful localization while seeing only progressively
disclosed state.

```text
                     +-------------------------+
Repository + Task -->| System Two full-read    |
                     | reference localization  |
                     +------------+------------+
                                  |
                                  | reference field / evidence
                                  v
                     +------------+------------+
Repository + Task -->| System One harness      |
                     | sparse / progressive    |
                     +------------+------------+
                                  |
                                  v
                         compare quality + cost
```

We deliberately do **not** optimize only for overlap with the reference.
Relevant evidence can be non-unique, and System Two itself can be noisy.
Reference metrics are paired with case-level inspection and, where useful,
blind downstream validation.

See [Benchmark contract](docs/benchmark.md).

## What counts as success

A System One pattern is interesting only if it occupies a useful
**quality–cost Pareto frontier**.

Quality metrics include:

- relevant-file recall and precision;
- hidden high-relevance region recall;
- high-line recall and precision;
- retained evidence relevance;
- relevance-mass recall;
- semantic completeness of retained evidence;
- missed independent relevance modes.

Cost metrics include:

- model calls;
- input/output tokens;
- model wall time;
- source lines read;
- repository metadata inspected;
- cache hits/misses;
- p50/p95 tail cost where repeated runs exist.

A method that gains recall by reading most of the repository is not a win.
A method that is cheap because it stops before finding independent evidence is
also not a win.

## Current working model

The strongest architectural conclusions so far are structural rather than a
single final algorithm:

1. **The harness owns mechanics.** State, legal actions, effects, budgets,
   durability, caching, and stopping invariants belong outside the model.
2. **System One supplies bounded semantic judgments.** It should choose among
   or score concrete actions instead of running an unconstrained ReAct loop.
3. **Progressive disclosure matters.** Do not eagerly inject the repository,
   full files, symbols, or all possible actions into context.
4. **Relevance and epistemic uncertainty are different state variables.**
5. **Coverage is durable state.** Finding some useful evidence must not erase
   unresolved high-value regions.
6. **Evidence closure is anchor-local and directional.** Ask whether more source
   is needed before/after the same local construct; do not rely on one abstract
   completeness score.
7. **Final utility is evaluated after local closure.** A truncated fragment can
   look useless because the important continuation is not visible yet.
8. **Identical semantic states must share decisions in policy A/B tests.**
   Independent model noise must not be mistaken for policy improvement.
9. **Cost is a first-class outcome.** Calls, tokens, source reads, and latency
   are measured alongside localization quality.

## Benchmark data

The canonical benchmark corpus is intentionally small and version-pinned while
the research mechanics are still changing.

Current data families:

- **R08 mechanism/holdout set** — three tasks on the frozen
  `BestNathan/nession@7ac9b6e0c2bb43c52f83e7dd706c0c0dc0d7a1df`
  revision. These established the probability-frontier and obligation
  experiments.
- **R18 fresh holdout set** — three additional files/tasks chosen before hidden
  System Two references were generated. These are used to test whether a
  mechanism survives beyond diagnostic cases.
- **Pinned reference/aggregate fixtures** under `fixtures/research/` — durable
  results required to reproduce research conclusions.

The benchmark is not yet broad enough to claim general code-search
generalization. Expanding it across repositories, languages, file sizes, and
task classes is a project milestone, not an already solved problem.

See [Benchmark contract](docs/benchmark.md).

## Research path

The research history is intentionally preserved, but experiment IDs are not
the architecture.

The path so far can be read as four stages:

```text
Stage A — bounded System One exploration
R01-R05
  range runtime -> progressive disclosure -> sparse observations

Stage B — reconstruct useful global state
R06-R09
  probability frontier -> posterior reconstruction -> uncertainty separation

Stage C — turn probability state into evidence
R10-R17
  evidence quality -> dynamic acquisition -> coverage obligations
  -> anchor-local directional closure -> obligation geometry

Stage D — validate causally and on fresh tasks
R18-R19
  fresh holdouts -> discover A/B decision-noise problem
  -> shared semantic-decision cache / counterfactual-safe comparison
```

Historical work remains in [docs/research/README.md](docs/research/README.md).
New experiments and their execution evidence are tracked in
[research/README.md](research/README.md).

See [Research path](docs/research-path.md) for the problem-oriented view.

## Experiment progress

| Date | Experiment | Status | Workflow | Result |
| --- | --- | --- | --- | --- |
| 2026-09-26 | [File Discovery scaling V1](research/2026-09-26-file-discovery-scaling-v1/) | completed | [36155715068](https://github.com/BestNathan/system-one-code-explore/actions/runs/36155715068) | Four-way request concurrency delivered 3.44–4.02× speedup; lexical discovery recalled 7/9 primary targets. |
| 2026-09-26 | [Semantic routing V2](research/2026-09-26-file-discovery-semantic-routing-v2/) | completed | [36213648492](https://github.com/BestNathan/system-one-code-explore/actions/runs/36213648492) | Semantic aliases reached 9/9 candidate recall; hierarchy and adaptive routing were rejected for directory/token cost. |
| 2026-09-26 | [Stable selection replay](research/2026-09-26-file-discovery-stable-selection-replay/) | completed | [36214118855](https://github.com/BestNathan/system-one-code-explore/actions/runs/36214118855) | Stable population semantics restored 9/9 final recall without model calls; OpenClaw selectivity remains unresolved. |
| 2026-09-26 | [Concept-weighted retrieval and provenance rescue V3](research/2026-09-26-concept-weighted-retrieval-provenance-rescue/) | completed | [36229213515](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229213515) | Weighted retrieval missed the OpenClaw WebSocket target and increased mean large-repository candidates from 2,655 to 4,729; rejected pending CamelCase correction. |
| 2026-09-26 | [CamelCase concept normalization V4](research/2026-09-26-camel-case-concept-normalization-v4/) | completed | [36229721717](https://github.com/BestNathan/system-one-code-explore/actions/runs/36229721717) | Restored 9/9 recall, but OpenClaw averaged 4,632 weighted candidates and 913k input tokens; scale gate failed. |
| 2026-09-26 | [Uncapped weighted path score frontier V5](research/2026-09-26-uncapped-weighted-path-score-frontier-v5/) | completed | [36230341725](https://github.com/BestNathan/system-one-code-explore/actions/runs/36230341725) | No tested score threshold met both gates: threshold 6 retained 9/9 at 4,181 OpenClaw files; threshold 10 fell to 6/9 at 1,933 files. |
| 2026-09-26 | [Exact primary-safe weighted frontier V6](research/2026-09-26-exact-primary-safe-weighted-frontier-v6/) | completed | [36230858823](https://github.com/BestNathan/system-one-code-explore/actions/runs/36230858823) | Label-calibrated OpenClaw threshold retained all three targets at 802 candidates/task; follow-up must test held-out transfer. |
| 2026-09-26 | [Leave-one-task-out weighted threshold V7](research/2026-09-26-leave-one-task-out-weighted-threshold-v7/) | completed | [36231288979](https://github.com/BestNathan/system-one-code-explore/actions/runs/36231288979) | Thresholds transferred poorly: 2/3 recall in each repository; OpenClaw averaged 455 candidates but missed its lower-score Gateway target. |
| 2026-09-26 | [Issue 13: Progressive repository state machine](research/2026-09-26-issue-13-progressive-repository-state-machine/) | completed, gate failed | [Experiment 36253022973](https://github.com/BestNathan/system-one-code-explore/actions/runs/36253022973) · [aggregation 36253788131](https://github.com/BestNathan/system-one-code-explore/actions/runs/36253788131) | Progressive recall was 6/9 vs. 8/9 for path retrieval; OpenClaw model-visible state rose 67% to 7,716 nodes. Deferred state prevented hard pruning but still hid three targets at scheduler stop. |
| 2026-09-27 | [Issue 14: Global directory classification](research/2026-09-27-issue-14-global-directory-classification/) | completed, recall gate failed | [36255811807](https://github.com/BestNathan/system-one-code-explore/actions/runs/36255811807) | Overall candidate recall was 5/9 vs. 9/9 for path retrieval. OpenClaw fell to 865 mean Phase 2 files and 2,772 total visible nodes, but low directory scores hid all three Codex targets. |

The [experiment log](research/README.md) links the complete goal, plan, process,
data, result, Workflow jobs, and artifact inventory for every new experiment.

## Target project structure

The repository is converging toward this logical structure:

```text
system-one-code-explore/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── benchmark.md
│   ├── project-structure.md
│   ├── research-path.md
│   ├── domains/
│   │   ├── file-discovery.md
│   │   └── evidence-localization.md
│   ├── research/          # historical research records
│   ├── experiments/       # experiment protocols/results
│   └── pilots/            # early exploratory traces
├── src/
│   ├── ...                # current research implementations; still flat
│   └──                    # migrate by domain only after interfaces stabilize
├── tests/
├── fixtures/
│   ├── repository/        # synthetic/local fixtures
│   └── research/          # pinned references and canonical aggregates
├── research/              # one auditable directory per new experiment
└── .github/workflows/     # reproducible experiment runners
```

The current `src/` is intentionally **not** mass-moved yet. Many workflows and
historical tests import the flat modules directly. The target module split is
defined in [Project structure](docs/project-structure.md); migration should
happen behind stable interfaces instead of breaking historical reproducibility.

## Canonical interfaces

The project should converge on a small number of durable artifacts independent
of any particular Rxx implementation:

```text
Task
RepositoryView

FileDiscoveryState
RelevantFile

FileEvidenceState
EvidenceAnchor
EvidenceSpan

LocalizationResult

Usage
  model_calls
  input_tokens
  output_tokens
  model_wall_time_ms
  source_lines_read
  metadata_items_seen
  cache_hits
  cache_misses
```

Experimental algorithms may be replaced. These concepts should remain stable
enough to compare algorithms across generations.

## Research discipline

Every meaningful experiment must state:

1. the question and hypothesis;
2. the frozen task, repository revision, model, and runtime parameters;
3. the controlled variable;
4. the System Two reference protocol, if used;
5. quality metrics;
6. calls, tokens, wall time, and source-read cost;
7. repeated-run variance or shared-decision controls where relevant;
8. whether parameters were frozen before hidden references/results were seen;
9. the result, failure mode, and next variable to isolate.

Do not:

- call a reference model ground truth;
- retune on the same hidden reference and then claim generalization;
- compare two policies with independent model judgments for identical semantic
  states;
- report recall without its source/model cost;
- treat a wide candidate basin as equivalent to source actually materialized.

## Running tests

```bash
python3 -m unittest discover -s tests -v
```

## Where to start

For the purpose and benchmark:

- [Benchmark contract](docs/benchmark.md)
- [File discovery](docs/domains/file-discovery.md)
- [Evidence localization](docs/domains/evidence-localization.md)

For architecture and repository organization:

- [Project structure](docs/project-structure.md)
- [Roadmap](ROADMAP.md)

For the full experimental record:

- [Research path](docs/research-path.md)
- [Current experiment log](research/README.md)
- [Historical research log](docs/research/README.md)
