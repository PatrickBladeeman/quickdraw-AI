# quickdraw-AI — Current Authorized Task

Last updated: 2026-08-29

This file is the canonical answer to **what work is authorized right now**.
It intentionally excludes completed-task history and speculative later work.

## Task

Define **R3O — bounded scheduled optimizer update 5** as the next smallest,
safe task after R3N.

Status: **defined; implementation has not started and requires a separate
explicit user go-ahead**.

## Objective

Prove that the unchanged R3N production LLAPI, replay, scheduled selector, and
optimizer path can advance one additional eligible boundary without reset or
drift: exactly four new Unity-derived transitions after the accepted 10,012-
transition prefix, followed by optimizer update 5 at transition 10,016.

Each fresh worker must reproduce the entire seeded trajectory from transition
zero. “Continue” means that selector, replay, network, optimizer, and RNG state
remain uninterrupted within that worker; it does not mean resuming from an
untracked process or checkpoint artifact.

This is one bounded integration gate, not extended training or policy-
effectiveness evidence.

## Frozen basis

- Research implementation frontier: pushed R3N commit
  `ca66335ce4e413ce7c4c35827d71154a254b850e`.
- R3M fourth-update contract SHA-256:
  `0a6f209d93ef6d522a53f24807d4ce48e6e820a344905e9762583bbe13a72dbb`.
- R3N replay-storage contract SHA-256:
  `ece35b60208adbb9ca0d36f8d61b3be652aae4a94ffdb7d2bcafc9ace58e16a9`.
- Registered runtime, replay, optimizer, target, epsilon, and seed values remain
  owned by [`RESEARCH.md`](RESEARCH.md) and may not change for this gate.
- The accepted prefix, losses, TD errors, weight hashes, trace hashes, replay
  sample-index hashes, failures, and limitations remain owned by
  [`docs/evidence/R3M.md`](docs/evidence/R3M.md) and
  [`docs/evidence/R3N.md`](docs/evidence/R3N.md).

## Allowed implementation scope after explicit approval

- Add a versioned R3O fifth-update contract and matching contract/result
  schemas.
- Add the smallest dedicated runner and focused tests needed to validate the
  new boundary, reusing the existing production package rather than creating a
  parallel trainer.
- Run two independent fresh CPU workers with normal graphics and the registered
  scenario, policy, and exploration seeds.
- Select actions at completed-transition counts 10,012 through 10,015 using the
  registered scheduled epsilon-greedy selector.
- Complete transition 10,016, perform exactly optimizer update 5, and stop
  before selecting another action.
- Preserve R3N's exact lossless replay representation, sampling stream,
  accounting rules, and fail-closed 4 GiB ceiling.
- Record accepted and rejected evidence without modifying earlier milestone
  records or tracking raw generated artifacts.
- Update current-state, roadmap, trainer-runbook, and evidence navigation only
  after the corresponding claims have actually passed.

## Explicit non-goals

- No optimizer update 6 or longer epsilon-decay/training rollout.
- No action selection using update-5 weights and no post-update handoff claim.
- No target-network synchronization; the registered 10,000-update boundary is
  not approached.
- No checkpoint/resume, final-checkpoint selection, ONNX export, ROCm training,
  multi-environment collection, or throughput benchmark.
- No held-out evaluation, useful-policy, convergence, sample-efficiency, or
  effectiveness claim.
- No Unity environment, observation, action, reward, episode, mask, scene,
  package, dependency, or runtime-version change.
- No gradual-motion, strategic combat, reflex, local LLM, or factorial work.
- No weakening of exact-prefix, determinism, schema, hash, or failure gates
  after observing a result.

## Acceptance criteria

1. The versioned R3O contract validates against its schema and binds the exact
   R3M and R3N contract hashes above.
2. Each worker exactly reproduces the accepted 10,012-transition prefix,
   including transitions, action stream, optimizer updates 1–4, replay sample
   indices, online hashes, and unchanged target hash.
3. Exactly four additional legal actions are selected at counts 10,012–10,015
   by the same seeded scheduled selector; epsilon values are derived from the
   registered formula without resetting or consuming a different RNG stream.
4. Completing transition 10,016 triggers update 5 exactly once. Its loss and
   mean absolute TD error are finite, and the online-network hash changes from
   the update-4 hash.
5. The target-network hash remains the initial frozen hash, target-sync count
   remains zero, and no target parameter receives a gradient.
6. The runner stops immediately after update 5 with 10,016 replay transitions,
   five optimizer updates, no selected post-update action, and no pending
   decision.
7. Two independent fresh workers produce object-equal and byte-equal validated
   traces. Partial, failed, batch-mode, headless, or prefix-divergent runs do
   not count.
8. R3N replay reconstruction, sampling, reclamation, accounting, and memory-
   ceiling invariants remain unchanged and pass their regression checks.
9. Focused R3O tests, the full trainer and Python research suites, schema and
   contract validation, bytecode compilation, pinned-dependency checks, the
   normal-graphics player build, and the live two-worker boundary pass. Unity
   EditMode tests are required if Unity files change; otherwise the task must
   confirm that no Unity file changed.
10. The final diff and repository status contain only approved R3O files and
    documentation. Evidence distinguishes the bounded integration result from
    training or effectiveness.

## Completion and failure handling

R3O is complete only when every acceptance criterion has direct evidence. A
failed or divergent worker remains negative evidence; reruns need fresh output
directories and may not weaken the frozen boundary. If the task discovers that
a Unity, dependency, research-contract, or broader trainer change is required,
stop and request expanded authorization rather than editing around it.

## Relevant context

- Procedure: [`AGENTS.md`](AGENTS.md)
- Current truth: [`STATE.md`](STATE.md)
- Registered BDQ contract: [`RESEARCH.md`](RESEARCH.md#branching-double-dqn-contract)
- Python BDQ architecture: [`ARCH.md`](ARCH.md#python-bdq-boundary--implemented-through-bounded-acceptance)
- Ordering: [`ROADMAP.md`](ROADMAP.md#r3--branching-double-dqn)
- R3M evidence: [`docs/evidence/R3M.md`](docs/evidence/R3M.md)
- R3N evidence: [`docs/evidence/R3N.md`](docs/evidence/R3N.md)
- Replay rationale: [`docs/decisions/ADR-0012-lossless-bounded-replay.md`](docs/decisions/ADR-0012-lossless-bounded-replay.md)
- Trainer runbook: [`Research/trainer/README.md`](Research/trainer/README.md)
