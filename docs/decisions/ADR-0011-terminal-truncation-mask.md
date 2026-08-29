# ADR-0011: Transport final masks for bootstrapped truncations

- **Status:** Accepted and implemented for Basic LLAPI collection
- **Recorded:** 2026-08-29, retrospectively

## Context

A true terminal transition does not bootstrap, so its next-action mask is
irrelevant. A decision-limit truncation does bootstrap from its final state and
therefore needs the legal next-action mask. ML-Agents delivers that interrupted
state through `TerminalSteps`, where the normal next `DecisionStep` mask is not
available.

## Decision

Immediately before `EpisodeInterrupted()`, Unity publishes one strict
`quickdraw.basic-truncation-mask.v1` side-channel message containing the final
position and environment-authored unavailable-action masks. Python binds it to
the expected run, episode, agent, and sequence and uses it only for the matching
truncated transition.

Ordinary continuations take masks from the next `DecisionStep`. True terminals
use an explicit all-available sentinel because the target multiplier is zero.
Python never infers legality from privileged scene state.

## Consequences

- Terminal and truncation semantics remain mathematically distinct.
- Missing, duplicate, stale, or mismatched final-mask messages fail closed.
- The transport fixture can validate bootstrapping without exposing Unity
  objects to the trainer.

See [`Research/basic/README.md`](../../Research/basic/README.md) and
[`Research/trainer/bdq-llapi-contract-v1.json`](../../Research/trainer/bdq-llapi-contract-v1.json).
