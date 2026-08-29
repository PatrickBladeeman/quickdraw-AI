# ADR-0004: Separate command time from visible-motion time

- **Status:** Accepted and implemented in `Test_Arena`
- **Recorded:** 2026-08-29, retrospectively

## Context

Calling a movement method or setting an animation trigger does not establish
when a player could observe motion. Treating dispatch as visible response would
systematically understate latency.

## Decision

Record `reflex_commanded` and `visible_motion_started` as distinct one-shot
events. `VisibleMotionObserver` captures the pre-command root pose and observes
the actual pose in `LateUpdate`. A position delta of at least `0.01 m` or a
rotation delta of at least `1°` marks onset. Cross-stage timestamps use
`Time.realtimeSinceStartup`.

Report command-to-visible and confirmed-threat-to-visible latency separately.
For the deterministic fixture, the retained regression targets are p50 below
`150 ms` and p95 below `250 ms` from confirmed threat to observed motion.

## Consequences

- A command-only smoke cannot support a visible-latency claim.
- Animation or rig implementations must provide an observable onset signal.
- Timing telemetry needs stable episode IDs and ordered events.

See [`ARCH.md`](../../ARCH.md) for the timing and event contracts.
