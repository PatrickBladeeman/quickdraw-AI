# quickdraw-AI — Current State

Last verified: 2026-09-07

This file is the canonical answer to **what is true right now**. It records
implementation and verification status, not the registered experiment design
or detailed acceptance evidence.

- Registered design: [`RESEARCH.md`](RESEARCH.md)
- Software architecture: [`ARCH.md`](ARCH.md)
- Current authorization: [`TASK.md`](TASK.md)
- Detailed evidence: [`docs/evidence/`](docs/evidence/README.md)
- Future ordering: [`ROADMAP.md`](ROADMAP.md)

## Repository checkpoint

- Task-start branch: `main`; HEAD and local `origin/main` both pointed to
  `549617b08b0d88199c0a97531350d9c61a2428ae`, the R3Q checkpoint implementation.
  The second implementation-consolidation changes are currently uncommitted.
- The hierarchical documentation migration and its QA cleanup are committed
  and pushed in `563c726fb3e782bd3bece11c0ce38dbcf3a8feed` and
  `abd240f9551bfc077e38672f06e7071d5480bc44`.
- The persistent read-only Kilo reconnaissance/review workflow is documented
  and pushed in `75bfb6427a1f17518e0b8487d7cdf8c31399f7d8`.
- The acceptance-harness consolidation and repository-wide bloat-control rule
  are committed and pushed in `4fa825b6c8ca45797abaaf6da85cde9357aa3657`.
- The verified research implementation frontier is committed R3Q, extending
  the R3P deterministic Python-only trainer checkpoint round-trip. The R3Q
  evidence record's uncommitted status describes its original verification
  date; this repository checkpoint supersedes that historical status.
- The verified live Unity frontier remains R3O at
  `028143fff494c6234fd17832dd41199aee5a6fad`: bounded scheduled optimizer
  update 5 at transition 10,016. R3P does not extend that live trajectory.

## Current research phase

The project is in **R3 — Branching Double DQN implementation and acceptance
infrastructure**.

The implemented live learning boundary is deliberately small: five scheduled
batch-64 optimizer updates have run on one deterministic Unity-derived prefix,
ending at transition 10,016. This is not an extended training run and has not
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

### R3 — BDQ boundary through R3Q

- R3A/R3B implement and test replay semantics, the registered visual dueling
  branch network, legal masking, Double-DQN targets, averaged branch Huber
  loss, Adam optimization, update scheduling, and hard-target synchronization
  logic.
- R3D replaced the retired high-level trainer experiment with direct synchronous
  ML-Agents LLAPI collection and authoritative final masks for truncations.
- R3E–R3M established deterministic collection, the registered epsilon
  schedule, live action handoffs, and scheduled optimizer updates 1–4.
- R3N implements lossless content-addressed float32 frame storage and columnar
  replay metadata under a fail-closed 4 GiB accounting ceiling while preserving
  the frozen R3M trace and optimizer results exactly.
- R3O extends the unchanged R3N production path by exactly four transitions
  and completes scheduled optimizer update 5 at transition 10,016. Each of two
  independent fresh workers reproduced the accepted 10,012-transition prefix
  byte-for-byte, and the runner stopped before any post-update action.
- R3P adds a versioned fail-closed Python checkpoint boundary. Three
  independent fresh CPU processes (uninterrupted reference, saver, restored)
  agreed exactly on the registered synthetic boundary at decision count 36
  and on the same next replay sample and bounded next optimizer result at
  decision count 40, loaded without Unity.
- R3Q extends the same checkpoint mechanism to the unchanged R3O live-derived
  state at transition 10,016. One fresh Unity-backed saver and one fresh CPU
  Python restorer agreed field-for-field on the checkpoint state and on the
  same next replay sample without Unity; the run stopped before any post-update
  action.
- Detailed evidence: [`docs/evidence/README.md`](docs/evidence/README.md), with
  one record per R3D–R3Q milestone.

## Not implemented or not demonstrated

- Optimizer update 6 or an extended Unity epsilon-decay/training rollout.
- The first scheduled hard target-network synchronization.
- Any action selected with update-5 weights.
- Training to convergence across the five registered policy seeds.
- Resume of the frozen Unity trajectory or final checkpoint selection. R3Q
  saves and restores a live-derived state in a fresh Python process without
  resuming Unity; ONNX export for the learned BDQ policy remains unproven.
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

- Do not describe the five bounded optimizer updates as an extended training
  session or a trained-policy result.
- Do not treat the unchanged target network as a defect: the registered hard
  synchronization boundary has not been reached.
- Strategic reward-shaping potentials and coefficients remain intentionally
  unregistered until R4; they must be fixed before strategic training rather
  than invented during implementation.
- R3O is implemented, committed, and pushed. Its acceptance does not open an
  extended training rollout, update 6, a post-update action, or target
  synchronization.
- R3P is implemented, accepted, committed, and pushed. Its acceptance is
  Python-only: it does not open a Unity rollout, resume of the frozen Unity
  trajectory, or any new environment interaction.
- R3Q is implemented, verified, and committed. It does not open transition 10,017,
  select an action after update 5, synchronize the target, resume Unity, or
  authorize extended training/export.
- Local context and handoff archives are intentionally ignored. Their absence
  from a fresh checkout is not public-documentation drift.

## Completed maintainability work

A conservative consolidation of the Python research acceptance harness is
implemented, verified, committed, and pushed at
`4fa825b6c8ca45797abaaf6da85cde9357aa3657`.
Generic acceptance utilities and the shared update-gate implementation
live in capability-oriented `quickdraw_bdq` modules while all historical
runner paths remain compatibility entry points.

The complete trainer suite and representative historical artifacts pass, the
independent read-only contract review found no blocking drift, and all frozen
contracts, schemas, evidence, and original production-core files remain
byte-identical. This work does not advance the R3 research frontier, change any
registered research value or accepted result, or authorize new Unity
collection.

The second implementation consolidation is complete and remains uncommitted.
It shares the eight trajectory entry flows, repeated contract/prefix validation,
scheduled-update test fixtures,
PlayMode reflection helpers, raw-file/runtime provenance, R3P process launch,
and Unity build/report handling. Historical commands and frozen research
formats remain intact; [`ARCH.md`](ARCH.md) owns the new module boundaries.
The three collection loops remain distinct because sharing their substantial
body would require new event-order tests and more control machinery.

The complete trainer suite passes 277 cases and the unchanged 41 PlayMode
cases pass. Both historical Unity build entry methods produced fresh players
from existing scenes. R3O traces/results and R3P/R3Q checkpoints/results match
the accepted raw bytes. All 21 explicit path/SHA contract
bindings pass. Of 273 task-start manifest entries, 272 match and one records
ML-Agents rewriting the historical player's unbound `Research_Basic_timers.json`
timing log. Its original hash and the failed strict audit are retained. On
2026-09-07 the user authorized completion without restoring that log; the
exception remains explicit in the complete manifest comparison. Two read-only
Kilo reviews covered the change; the first review's render-asset line-ending
finding was resolved, and the second found no substantive new issue.
Verification passes within the updated authorized scope.
[`TASK.md`](TASK.md) owns the authorized maintenance boundary.

## Current boundary

R3P is implemented, accepted, committed, and pushed at
`0d78c783897225395ed44304fb6b0124a4620582`. The live Unity boundary remains
R3O at 10,016 transitions with five optimizer updates, zero target
synchronizations, and no post-update action. R3Q is implemented and verified
at the committed repository checkpoint above: the
live-derived state was saved and restored in a fresh Python process without
Unity with exact next-sample parity. R3Q does not resume Unity or extend that
live boundary.
