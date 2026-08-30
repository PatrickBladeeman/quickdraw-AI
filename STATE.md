# quickdraw-AI — Current State

Last verified: 2026-08-29

This file is the canonical answer to **what is true right now**. It records
implementation and verification status, not the registered experiment design
or detailed acceptance evidence.

- Registered design: [`RESEARCH.md`](RESEARCH.md)
- Software architecture: [`ARCH.md`](ARCH.md)
- Current authorization: [`TASK.md`](TASK.md)
- Detailed evidence: [`docs/evidence/`](docs/evidence/README.md)
- Future ordering: [`ROADMAP.md`](ROADMAP.md)

## Repository checkpoint

- Branch: `main`.
- `HEAD`, the configured upstream, and `origin/main` all resolve to
  `abd240f9551bfc077e38672f06e7071d5480bc44`
  (`documentation clean up pt 2`).
- The hierarchical documentation migration and its QA cleanup are committed
  and pushed in `563c726fb3e782bd3bece11c0ce38dbcf3a8feed` and
  `abd240f9551bfc077e38672f06e7071d5480bc44`.
- The verified research implementation frontier remains
  `ca66335ce4e413ce7c4c35827d71154a254b850e`
  (`R3N: lossless replay storage optimization`); the two later commits are
  documentation-only.
- R3N is committed and pushed. Earlier wording that placed the frontier at an
  uncommitted R3M was stale and was resolved from Git state.

## Current research phase

The project is in **R3 — Branching Double DQN implementation and acceptance
infrastructure**.

The implemented live learning boundary is deliberately small: four scheduled
batch-64 optimizer updates have run on one deterministic Unity-derived prefix,
ending at transition 10,012. This is not an extended training run and has not
produced a trained or useful policy.

## Implemented and verified

### Deterministic substrate and R0

- The `Test_Arena` regression fixture implements the minimal player controller,
  deterministic patrol, structured aim stimulus, soft perception, one-shot
  interruption, collision-aware `Flinch_StepBack`, observed visible-motion
  onset, and buffered typed JSONL telemetry.
- Deterministic Tasks 1–8 and the R0 checkpoint are complete.
- Detailed evidence: [`docs/evidence/DETERMINISTIC-R0-R2.md`](docs/evidence/DETERMINISTIC-R0-R2.md).

### R1 — Reproducible ML infrastructure

- Unity ML-Agents 4.0.0 and its locked Inference Engine dependency are
  installed.
- The isolated communicator fixture, deterministic 10,000-decision CPU
  transport reference, Python 3.11.13 compatibility overlay, and fixed-policy
  CPU-versus-ROCm gate are complete.
- ROCm is accepted only for the registered batch-size-one fixed-policy
  inference fixture. ROCm training and larger learned-model performance remain
  unproven.
- Detailed evidence: [`docs/evidence/DETERMINISTIC-R0-R2.md`](docs/evidence/DETERMINISTIC-R0-R2.md).

### R2 — Basic environment

- `Research_Basic` implements the registered slot-based visual benchmark:
  deterministic reset, actual uncompressed float32 HWC `[84,84,4]`
  observation, typed two-branch actions, action masks, shared center-camera
  hitscan, additive reward, true terminal, and decision-limit truncation.
- Random and scripted LLAPI baselines repeat exactly across fresh processes.
- The slot-based environment remains the canonical R3 control. Gradual motion
  is a separately versioned future variant.
- Detailed evidence: [`docs/evidence/DETERMINISTIC-R0-R2.md`](docs/evidence/DETERMINISTIC-R0-R2.md).

### R3 — BDQ boundary through R3N

- R3A/R3B implement and test replay semantics, the registered visual dueling
  branch network, legal masking, Double-DQN targets, averaged branch Huber
  loss, Adam optimization, update scheduling, and hard-target synchronization
  logic.
- R3D replaced the retired high-level trainer experiment with direct synchronous
  ML-Agents LLAPI collection and authoritative final masks for truncations.
- R3E–R3M established deterministic collection, the registered epsilon
  schedule, live action handoffs, and scheduled optimizer updates 1–4.
- The R3M production path ends at transition 10,012 with four optimizer
  updates, zero target synchronizations, the target network still equal to its
  initial snapshot, and no pending decision.
- R3N implements lossless content-addressed float32 frame storage and columnar
  replay metadata under a fail-closed 4 GiB accounting ceiling while preserving
  the frozen R3M trace and optimizer results exactly.
- Detailed evidence: [`docs/evidence/README.md`](docs/evidence/README.md), with
  one record per R3D–R3N milestone.

## Not implemented or not demonstrated

- Optimizer update 5 or an extended Unity epsilon-decay/training rollout.
- The first scheduled hard target-network synchronization.
- Training to convergence across the five registered policy seeds.
- Checkpoint/resume lifecycle, final checkpoint selection, or ONNX export for
  the learned BDQ policy.
- Held-out learned-policy evaluation, the Basic BDQ acceptance result, or the
  joint-action Double DQN comparison.
- The separately versioned gradual-motion Basic variant.
- Multi-environment collection or `Research_Strategic`.
- Strategic health, damage, cover, ammunition, reload, pickups, opponent, or
  telegraph mechanics.
- The research `EvadeTelegraphedShot` reflex.
- The provider-neutral director boundary, Qwen3/`llama.cpp` runtime, rule
  director, failure/delay injection, or strategic directives.
- The paired factorial runner, bootstrap analysis, or research report.

No current smoke or regression result demonstrates policy effectiveness,
sample efficiency, the registered hypotheses, or general ROCm training
support.

## Active constraints and risks

- Do not describe the four bounded optimizer updates as an extended training
  session or a trained-policy result.
- Do not treat the unchanged target network as a defect: the registered hard
  synchronization boundary has not been reached.
- Strategic reward-shaping potentials and coefficients remain intentionally
  unregistered until R4; they must be fixed before strategic training rather
  than invented during implementation.
- R3O is defined as the next bounded SSNT, but its implementation requires a
  separate explicit go-ahead. Defining it does not open an extended training
  rollout, update 6, a post-update action, or target synchronization.
- Local context and handoff archives are intentionally ignored. Their absence
  from a fresh checkout is not public-documentation drift.

## Current boundary

R3O is the defined next task: reproduce the accepted R3N/R3M production prefix,
extend it by exactly four transitions, and stop immediately after scheduled
optimizer update 5 at transition 10,016. The current request authorizes the
task definition only, not implementation. See [`TASK.md`](TASK.md).
