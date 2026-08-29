# ADR-0002: Route aim threat through structured perception

- **Status:** Accepted and implemented in `Test_Arena`
- **Recorded:** 2026-08-29, retrospectively

## Context

A center-camera raycast can confirm geometry cheaply, but mapping that hit
directly to a reaction bypasses distance, field of view, occlusion, suspicion,
orientation, and state-transition behavior. It would make the perception layer
decorative and weaken the experiment.

## Decision

`AimThreatEmitter` publishes a structured `AimThreatStimulus` containing source,
origin, direction, timestamp, maximum distance, and aiming state. Perception is
the normal route from that stimulus to threat confirmation. It applies distance,
total-cone half-angle, line-of-sight, measured suspicion-tick time, orientation,
and rearming rules.

A direct center-camera confirmation may exist only as an explicit debug bypass.
It defaults off and is excluded from evaluation.

## Consequences

- Stimulus production remains independent from NPC behavior and reflex choice.
- Frontal, peripheral, and occluded scenarios exercise the same causal path.
- Tests must prove that aiming alone cannot directly force a reflex.

See the implemented component contracts in [`ARCH.md`](../../ARCH.md).
