# ADR-0003: Trigger interruption and reflexes on event edges

- **Status:** Accepted and implemented in `Test_Arena`
- **Recorded:** 2026-08-29, retrospectively

## Context

Perception runs repeatedly. Dispatching interruption or motion from a sustained
state on every tick would spam reactions, compound displacement, and corrupt
latency counts.

## Decision

Threat confirmation, activity interruption, and reflex dispatch occur on
explicit state edges. The behavior coordinator interrupts the current activity
synchronously before it commands the reflex. The `(episode ID, confirmation
timestamp)` identifies interruption delivery, while the reflex independently
rejects duplicate commands for the episode. A later reaction requires recovery
and rearming; a held threat cannot generate repeated steps.

## Consequences

- Each threat episode has at most one interruption and one initial reflex.
- Activity state and motion ordering are testable independently.
- Cooldowns and no-repeat variation can be added without weakening edge
  ownership.
- Telemetry counts events rather than repeated state samples.

See [`ARCH.md`](../../ARCH.md) and the deterministic fixture history in
[`DETERMINISTIC_V1.md`](../history/DETERMINISTIC_V1.md).
