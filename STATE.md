# quickdraw-AI — Current State

Last checked against repository: 2026-09-10.
Research acceptance remains the recorded R3S result of 2026-09-09; R3T was
accepted on 2026-09-10 as a bounded five-seed Basic training and lineage gate.
Neither acceptance establishes policy effectiveness or convergence.

## Repository checkpoint

- Branch: `main`; committed implementation frontier:
  `61ba19ebe9fab3c888fc67c88cdeb30a6333e86c` (R3S).
- The R3T implementation, contract, schemas, evidence, and documentation
  consolidation are uncommitted. The pre-existing untracked `tmp/` directory
  is outside this cleanup.
- Verify Git status at task start; this checkpoint is not a live worktree ledger.
  Earlier checkpoints and maintenance provenance are in
  [history](docs/history/MAINTENANCE_2026-09.md).

## Current research phase

**R3 — Branching Double DQN.** The implementation and bounded acceptance
infrastructure are complete through R3T. R3T accepted finite five-seed Basic
training and complete lineage; effectiveness evaluation remains separate. The
scientific design is in
[RESEARCH.md](RESEARCH.md); future ordering is in [ROADMAP.md](ROADMAP.md).

## Implemented capabilities

- **R0–R2:** deterministic `Test_Arena` control/perception/reflex/visible-onset
  telemetry, reproducible Unity/Python transport, and slot-based
  `Research_Basic` with repeatable random/scripted LLAPI baselines are verified.
  [Foundation evidence](docs/evidence/DETERMINISTIC-R0-R2.md) retains exact
  versions, observations/actions, backend qualification, and results.
- **BDQ:** direct synchronous LLAPI collection, authoritative truncation masks,
  visual dueling branches, legal Double-DQN targets, averaged Huber loss,
  Adam updates, seeded epsilon selection, and hard target synchronization.
- **Replay/persistence:** lossless content-addressed float32 frames and columnar
  metadata with fail-closed storage accounting; versioned trainer checkpoints
  preserve networks, optimizer, replay, selector/RNG, counters, and identity.
  Python-only restore and live-derived checkpoint parity are accepted.
- **Execution:** shared capability modules support bounded historical entry
  points; collection loops and validators retain their distinct contracts.
  Module ownership and compatibility boundaries are in [ARCH.md](ARCH.md).
- **R3T:** the registered five-seed Basic campaign contract, result schemas,
  thin runner, update telemetry, provenance checks, checkpoint lineage, and
  fresh Python restore path are implemented, focused-tested, and accepted.
  Each seed completed `49,996` transitions, `10,000` optimizer updates, one
  target synchronization, four checkpoints, and fresh-Python restore parity.
  The accepted result and exact hashes are owned by [R3T evidence](docs/evidence/R3T.md);
  two earlier rejected attempts remain retained under the ignored artifact
  tree.
- The [evidence index](docs/evidence/README.md) supplies each acceptance record;
  the [roadmap](ROADMAP.md#r3--branching-double-dqn) supplies milestone ordering.

## Current accepted frontier

- R3R accepted deterministic one-seed continuation through the first hard
  target synchronization, with independent-worker and fresh-restorer parity.
  It uses fresh complete player copies, not resume of a frozen historical
  Unity process. [R3R evidence](docs/evidence/R3R.md).
- R3S accepted two run-owned live Unity-process handoffs across fresh trainer
  restores. Each completes exactly one post-sync action and stops at transition
  **49,997**, with **10,000 optimizer updates and one synchronization**, before
  another action. It also accepts ONNX/CPU inference parity for the accepted
  R3R online network. [R3S evidence](docs/evidence/R3S.md) owns exact hashes,
  parity error/tolerance, commands, corpus, rejected attempts, and verification.
- These gates establish deterministic continuation, live-process continuity,
  and exported-inference software parity. They do not establish a useful policy,
  convergence, generalization, sample efficiency, or the registered hypotheses.
- R3T accepted five independent Basic training runs with complete ordered
  lineage and fresh-Python checkpoint parity. The result explicitly does not
  claim a useful policy, convergence, generalization, sample efficiency, or
  held-out performance.

## Not implemented / not demonstrated

- Held-out learned-policy evaluation, Basic effectiveness acceptance, or the
  joint-action Double-DQN factorization comparison.
- Optimizer update 10,001, a second target synchronization, or extended live
  resumption beyond the R3S gate.
- Resume of the original frozen historical Unity trajectory. R3S continuity
  applies only to each attempt's run-owned player.
- Multi-environment collection or the separately versioned gradual-motion
  Basic variant.
- `Research_Strategic` combat mechanics, research `EvadeTelegraphedShot`,
  director boundary, rule/local Qwen3 director, failure/delay injection,
  paired factorial evaluation, bootstrap analysis, or research report.
- General ROCm inference or training support. Its accepted scope is only the
  registered batch-size-one fixed-policy fixture.

## Active constraints / risks

- Basic remains the slot-based R3 control. R3T starts fresh per seed; the
  accepted R3S checkpoint is not a multi-seed training starting point.
- R3T training duration, checkpoint selection, stopping, seed mapping, and
  metric definitions are registered in [ADR-0013](docs/decisions/ADR-0013-r3t-basic-multiseed-training.md)
  and [RESEARCH.md](RESEARCH.md#r3t-basic-multi-seed-training-registration),
  with accepted hashes in [R3T evidence](docs/evidence/R3T.md).
  Strategic shaping potentials/coefficients remain unresolved until R4.
- Frozen player directories must not receive profiling output; use complete
  run-owned copies. The prior timing-log exception is retained in
  [maintenance history](docs/history/MAINTENANCE_2026-09.md).
- Evidence records describe their dated acceptance checkpoints; historical
  “uncommitted” labels there do not describe today's Git state.
- Local context and handoffs are intentionally ignored; their absence from a
  checkout is not public-documentation drift.

## Authorization

There is no active implementation authorization after the completed R3T task.
Any new work requires a new explicit objective in [TASK.md](TASK.md).
