# quickdraw-AI — Current Authorized Task

Last updated: 2026-09-04

This file is the canonical answer to **what work is authorized right now**.
It excludes completed-task history and speculative later work.

## Task

### R3Q — Live-derived trainer checkpoint gate

Extend the existing R3P Python checkpoint mechanism to the trainer state
produced by the unchanged R3O live collection path at its clean boundary:
10,016 completed transitions, optimizer update 5 complete, zero target
synchronizations, no pending decision, and no post-update action selected.

Save that live-derived state, restore it in a fresh CPU Python process without
Unity, and prove exact state and next-replay-sample parity with the saver.

Status: **implemented and verified in the working tree on 2026-09-04; not
committed or pushed by instruction**.

## Implementation boundary

- Reuse `quickdraw_bdq.checkpoint`, `quickdraw_bdq.update_gate`, and
  `quickdraw_bdq.acceptance`; do not clone their generic control flow into an
  R3Q-specific runner or test.
- Bind the new claim to the frozen R3O contract and accepted live boundary
  without modifying R3O, R3P, their schemas, or their evidence.
- Use one fresh live saver process and one fresh Python-only restorer process.
- Keep the checkpoint and raw results under `Artifacts/Experiments/`; track
  only the minimal contract, tests, schema additions if genuinely required,
  and curated evidence.

## Acceptance criteria

- The saver exactly reproduces the registered R3O boundary, including network
  hashes, optimizer/replay state and accounting, counters, seeds, selector RNG
  state, and an empty pending-decision set.
- The fresh restorer loads without Unity and matches the saved boundary
  field-for-field before exposing restored objects.
- The saver and restorer produce the identical next replay sample without
  changing the registered sampling algorithm or RNG consumption.
- Existing checkpoint corruption/incompatibility rejection remains fail-closed
  without duplicating already-covered impossible-state checks.
- Focused R3Q tests, the complete trainer suite, and frozen R3O/R3P regressions
  pass with no weakened assertion, tolerance, or provenance binding.

## Constraints

Do not select or execute an action after update 5, collect transition 10,017,
run optimizer update 6, synchronize the target network, resume the Unity
process, start extended training, export a model, or make an effectiveness
claim. Do not change C# behavior, registered research values, or frozen
historical artifacts. Do not commit or push without explicit authorization.
