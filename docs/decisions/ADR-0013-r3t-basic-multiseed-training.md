# ADR-0013: Register the R3T Basic multi-seed training boundary

## Status

Accepted for R3T on 2026-09-10.

## Context

The Basic Branching Double DQN implementation has verified collection, replay,
optimization, checkpoint, and deterministic CPU runtime boundaries through R3S.
R3T needs to run the five already registered policy-initialization seeds while
keeping each run independent and preserving enough lineage for later, separate
held-out evaluation. Training duration, checkpoint selection, stopping, and
learning-curve sampling were intentionally not registered by the prior
research contract.

## Decision

R3T uses one fresh run for each of policy seeds `51001` through `51005`. Every
run uses the registered Basic scenario seed `31001`, resets the scheduled CPU
exploration generator with the registered exploration seed `61001`, and starts
with fresh online/target networks, replay, optimizer, and selector state. The
existing controller seed is explicitly recorded as both policy-initialization
and replay-sampling seed because that is the established controller boundary;
the mapping is a table, not a derivation.

Each run stops after exactly `49,996` completed transitions and `10,000`
optimizer updates. The final update performs the first registered hard target
synchronization, and the worker stops at that clean boundary before selecting a
post-boundary live action. This is the smallest shared-gate boundary that
includes a target synchronization and does not require an unregistered second
synchronization or an unrestricted trainer path. It is a finite lineage gate,
not an effectiveness or convergence experiment.

Checkpoints are written after optimizer updates `2,500`, `5,000`, `7,500`, and
`10,000`. The checkpoint at update `10,000` is selected by position in the
predeclared schedule; return, success, loss, Q-values, and any other observed
outcome cannot influence selection. Each checkpoint uses the unchanged versioned
checkpoint writer and contains the network, optimizer, replay, selector/RNG,
counters, settings, and integrity bindings.

The learning curve samples every `100` optimizer updates, for `100` samples per
run. It records the existing loss and TD metrics, sampled replay indices, finite
per-branch Q summaries, a checkpoint-equivalent state hash, and diagnostic update
timing. Mean episode-prefix return is computed over completed Unity episodes
plus the current active episode prefix when a sample lands before reset; success
is target-hit terminals divided by that same observed-episode denominator, with
an incomplete active prefix contributing zero. Timing and process identifiers
are diagnostic and excluded from canonical artifact equality.

## Consequences

- The campaign has one thin, contract-bound entry point that composes the
  existing update gate and checkpoint implementation rather than creating a
  second trainer.
- Five seed-specific traces, metrics, manifests, checkpoints, logs, and rejected
  attempts remain under the ignored R3T artifact root.
- A fresh Python restore process must reproduce each selected checkpoint's
  state, counters, settings, replay, selector state, and hashes.
- The result may report finite training completion and lineage only. Held-out
  evaluation, Basic success thresholds, random-policy improvement, convergence,
  generalization, sample efficiency, final policy choice, and joint-action
  comparison remain separate registrations.

## Rejected alternatives

- Reusing the R3S checkpoint or transferring weights between seeds would break
  independent-seed lineage.
- Choosing a checkpoint from the best return/loss or inspecting held-out
  outcomes would make selection post hoc.
- Adding a generic duration argument or open-ended trainer would weaken the
  registered stopping boundary and duplicate the existing production path.

The machine-readable values and schemas are owned by
[`bdq-r3t-basic-multiseed-contract-v1.json`](../../Research/trainer/bdq-r3t-basic-multiseed-contract-v1.json)
and its matching schemas.
