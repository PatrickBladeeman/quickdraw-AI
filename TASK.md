# quickdraw-AI — Current Authorized Task

Last updated: 2026-08-31

This file is the canonical answer to **what work is authorized right now**.
It excludes completed-task history and speculative later work.

## Task

Implement **R3P — deterministic Python trainer checkpoint round-trip**.

Status: **completed, verified, committed, and pushed on 2026-08-31** in
`0d78c783897225395ed44304fb6b0124a4620582`.

## Outcome

A versioned, fail-closed checkpoint boundary now exists for the Python BDQ
trainer. The checkpoint preserves the online and target networks, Adam
optimizer state, optimizer and target-synchronization counters, the
completed-transition count, replay contents with ring cursor, accounting, and
sampling RNG state, the scheduled-selector RNG stream, and the
package/runtime/settings/seeds/contract identity, sealed by a SHA-256 over
the canonical encoded state.

Three independent fresh CPU Python processes proved the round-trip without
Unity: an uninterrupted reference, a saver, and a restored process. All three
agreed exactly on the registered synthetic boundary at decision count 36
(network hashes, counters, replay contents, cursor, and accounting), on the
next replay sample, and on the bounded next optimizer result at decision
count 40. Saving refuses any boundary with a pending LLAPI decision, and
loading rejects corrupt, schema-incomplete, and incompatible checkpoints
before any restored object is returned.

All acceptance criteria passed, including focused R3P tests, the full trainer
and Python research suites, contract/checkpoint/result schema validation,
bytecode compilation, dependency checks, and the three-fresh-process
boundary.

- Exact evidence, hashes, and limitations:
  [`docs/evidence/R3P.md`](docs/evidence/R3P.md)
- Contract: [`Research/trainer/bdq-checkpoint-contract-v1.json`](Research/trainer/bdq-checkpoint-contract-v1.json)
- Module: [`Research/trainer/quickdraw_bdq/checkpoint.py`](Research/trainer/quickdraw_bdq/checkpoint.py)
- Runner: [`Research/trainer/run_bdq_checkpoint_roundtrip_smoke.py`](Research/trainer/run_bdq_checkpoint_roundtrip_smoke.py)
- Current truth: [`STATE.md`](STATE.md)

## Boundary

R3P does not open a Unity rollout, live LLAPI collection, transition 10,017 on
the R3O trajectory, optimizer update 6 on that trajectory, an action with
update-5 weights, target synchronization, extended training, final checkpoint
selection, ONNX export or exported-inference parity, ROCm training,
multi-environment collection, or any effectiveness claim.

No next task is authorized. The next SSNT requires an explicit task update.
