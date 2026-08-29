# Deterministic vertical slice: Tasks 1–8

> **Historical scope record.** Tasks 1–8 are complete and remain implemented as
> the `Test_Arena` regression fixture, but this earlier vertical-slice plan does
> not control the current research roadmap.

## Purpose

The first version tested a narrow proposition: an NPC should continue an
observable activity, perceive a structured aiming threat, interrupt that
activity once, command an immediate collision-aware reaction, and report actual
visible onset without urgent-path file I/O.

It was explicitly a behavior and instrumentation substrate rather than a
trained-agent result.

## Completed task sequence

1. Stabilize Unity `6000.0.57f1`, URP, reproducibility settings, package locks,
   and the `Test_Arena` build.
2. Implement `SimpleFPSController` with `CharacterController`, direct Unity
   Input System access, movement, mouse look, gravity, cursor control, aiming,
   and an observable `IsAiming` property.
3. Build a `16 × 16`-unit open-top arena supporting direct, peripheral, and
   occluded sight lines plus patrol and interaction markers.
4. Implement deterministic, collision-aware `PatrolActivity` with explicit
   start, interrupt, resume, cancel, and reset behavior.
5. Emit structured camera-backed `AimThreatStimulus` start/end edges without a
   direct behavior or reflex dependency.
6. Implement `SoftFOVPerception` using total cone widths, measured perception
   tick time, line of sight, suspicion, orientation, one-shot confirmation, and
   rearming.
7. Interrupt patrol synchronously and command one deterministic
   `Flinch_StepBack` through a narrow coordinator and selector.
8. Observe actual root motion separately from command dispatch and record the
   ordered interaction through buffered typed JSONL telemetry.

## Corrected design that survived the slice

- Aiming is a structured stimulus that flows through perception. A direct
  center-camera hit is debug-only.
- Core and peripheral FOV settings are total cone widths; comparisons use their
  half-angles.
- Suspicion gain and decay use actual elapsed perception-tick time.
- Confirmation, interruption, and reflex dispatch occur on event edges rather
  than every tick.
- Serialized stable seeds replace runtime object-name hashing.
- Collision-aware `CharacterController.Move` replaces raw root teleportation.
- `reflex_commanded` and `visible_motion_started` are separate events.
- Event handlers enqueue typed records; serialization and disk writes happen
  outside urgent dispatch.
- Logger singleton state resets safely when Domain Reload is disabled.

## Frozen fixture values

- Core FOV: total `90°`.
- Peripheral FOV: total `140°`.
- Suspicion build time: `0.45 s`.
- Suspicion decay rate: `0.8`.
- Enter/exit thresholds: `0.5 / 0.3`.
- Perception tick: approximately `12 Hz`.
- Body turn speed: approximately `300°/s`.
- Facing threshold: approximately `3°`.
- `NPC_01` style seed: `1001`.
- Implemented step distance: `0.35 ± 0.05 m`.
- Implemented yaw range: `±30°`.
- Visible root thresholds: `0.01 m` position or `1°` rotation.
- Confirmed-threat-to-visible-motion regression targets: p50 below `150 ms`,
  p95 below `250 ms`.

## Accepted verification

The completed slice passed 41 Unity Play Mode tests and a Windows standalone
build. Its implementation was checkpointed in consecutive commits `ac1274e`
(`task 8 : Logging and telemetry`) and `b5532e1` (`task 8 continued`). Those
tests prove the software contracts, not a latency distribution or research
hypothesis.

## Continuing role

`Test_Arena` remains isolated from ML-Agents research scenes and is still the
regression fixture for perception, interruption, reflex ordering, visible onset,
and typed telemetry. The unimplemented tactical-recovery FSM is not required by
the current research architecture and must not be inferred from historical
sketches.

See [`ARCH.md`](../../ARCH.md) for current component boundaries and
[`docs/evidence`](../evidence/README.md) for milestone evidence.
