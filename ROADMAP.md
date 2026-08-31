# quickdraw-AI — Research Roadmap

This file owns major milestone ordering and remaining scope. It is not an
authorization document and does not repeat the registered numeric experiment
contract. See [`TASK.md`](TASK.md) for current authorization and
[`RESEARCH.md`](RESEARCH.md) for frozen values.

Status terms are deliberately distinct: planned, implemented, verified,
committed, pushed, experimentally validated, and effectiveness demonstrated
must not be collapsed.

## Completed foundation

### Deterministic Tasks 1–8

Status: complete, verified, committed, and pushed.

The `Test_Arena` control-and-measurement substrate implements player control,
patrol, structured perception, event-edge interruption, one deterministic
placeholder reflex, observed visible onset, and buffered structured telemetry.

Evidence: [`docs/evidence/DETERMINISTIC-R0-R2.md`](docs/evidence/DETERMINISTIC-R0-R2.md).

### R0 — Deterministic checkpoint

Status: complete, verified, committed, and pushed.

The deterministic substrate was revalidated before research dependencies were
introduced.

### R1 — Contracts and reproducible ML infrastructure

Status: R1A, R1B, R1C, revised R1E, and R1F complete and pushed. R1D is
superseded and retired.

The communicator, CPU transport reference, Python 3.11 compatibility lane, and
narrow fixed-policy CPU/ROCm comparison are established. CPU remains the
historical reference; ROCm acceptance is limited to the registered inference
fixture and does not establish training support.

### R2 — Unity Basic benchmark

Status: R2A complete, verified, committed, and pushed.

The canonical slot-based environment and random/scripted LLAPI baselines are
implemented and repeatable. It is the control environment for R3.

## R3 — Branching Double DQN

Status: implementation and acceptance infrastructure complete through R3N;
the full R3 learning and evaluation goal is not complete.

Completed boundaries:

- R3A: pure-Python replay/network/target/loss foundation.
- R3B: deterministic optimizer and schedule.
- R3C: high-level trainer/trajectory experiment superseded and removed.
- R3D: direct LLAPI collection and truncation-mask transport.
- R3E: fixed seeded epsilon-greedy collection below warmup.
- R3F/R3G: scheduled optimizer updates 1 and 2 on Unity experience.
- R3H: first live updated-weight masked-greedy handoff.
- R3I/R3J: stateless production epsilon schedule and bounded live integration.
- R3K/R3M: scheduled optimizer updates 3 and 4.
- R3L: diagnostic update-3 greedy handoff.
- R3N: lossless, memory-bounded replay representation with frozen-trace
  regression.
- R3O: bounded scheduled optimizer update 5 at transition 10,016.
- R3P: deterministic Python-only checkpoint round-trip on the registered
  synthetic workload.

Evidence: [`docs/evidence/README.md`](docs/evidence/README.md).

Remaining R3 work, in dependency order:

1. Extend durable checkpoint/resume beyond the registered synthetic Python
   boundary toward the live trajectory and add learned-policy export parity
   without weakening deterministic replay or schedule contracts.
2. Run the five registered Basic training seeds and retain complete lineage,
   curves, manifests, and hashes.
3. Evaluate held-out Basic success and random-policy improvement.
4. Run and report the joint-action Double DQN factorization control.

The first target synchronization is scheduled by optimizer-update count; it
has not occurred. A roadmap item is not permission to start it or to choose the
next SSNT.

## Deferred post-R3 variant — Gradual-motion Basic

Status: planned only after the canonical slot-based R3 acceptance gates pass.

Create a separately versioned environment that retains the same discrete
movement/combat branches but holds lateral intent across fixed physics steps.
Do not mutate R2A in place, call the branch continuous, or reuse a slot-trained
checkpoint as confirmatory evidence without separate training and held-out
evaluation.

## R4 — Strategic combat and goal-conditioned policy

Status: planned; not implemented.

Implement the controlled strategic scene, shared mechanics, scripted opponent,
resource decisions, telegraphed shots, categorical goals, deterministic
teacher, and goal-conditioned policy. Register the still-undefined strategic
potential-shaping terms before training. Exact mechanics and fairness rules are
owned by [`RESEARCH.md`](RESEARCH.md).

## R5 — Deterministic research reflex

Status: planned; not implemented.

Add the narrowly bounded `EvadeTelegraphedShot` movement preemption and prove it
is collision-safe, duplicate-safe, observable, and independent of policy and
LLM timing.

## R6 — Asynchronous local strategic director

Status: planned; not implemented.

Implement the provider-neutral snapshot/result boundary, deterministic mock,
rule director, and pinned local Qwen3/`llama.cpp` director. Complete failure and
delay isolation before any effectiveness claim.

## R7 — Registered factorial evaluation

Status: planned; not run.

Run the paired reflex-by-LLM factorial and same-information rule-director
controls using the frozen design, greedy checkpoints, held-out scenarios, and
hierarchical bootstrap. Report negative, null, and rejected hypotheses without
post-hoc threshold changes.

## R8 — Reproducible research artifact

Status: planned.

Curate configurations, schemas, scripts, aggregate results, figures, checksums,
commands, and limitations. Keep raw runs and large models in the ignored
artifact boundary. Every published claim must trace to a run manifest and an
analysis command.

## Current authorization

R3P is completed and accepted in the working tree; no next SSNT is currently
authorized. See [`TASK.md`](TASK.md) for the completed boundary and
[`STATE.md`](STATE.md) for current truth.
