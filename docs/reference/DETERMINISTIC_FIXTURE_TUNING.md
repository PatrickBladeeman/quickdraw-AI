# Deterministic fixture tuning reference

This file distinguishes retained design suggestions from implemented and tested
`Test_Arena` values. It is not a request to retune the fixture.

## Suggested controller values

These values were retained from the original first-person controller design:

| Setting | Reference value |
| --- | --- |
| `moveSpeed` | `5` |
| `sprintMultiplier` | `1.4` |
| `mouseSensitivity` | `1.8` |
| `mouseSensitivityAim` | `1.2` |
| `normalFOV` | `70` |
| `aimFOV` | `55` |
| `fovLerp` | `12` |
| `gravity` | `-9.81` |
| `jumpHeight` | `1.1` |

Upward `CharacterController` collision should clear positive vertical velocity
immediately. The accepted controller uses the Unity Input System directly,
exposes `IsAiming`, and has no Starter Assets dependency.

Verify serialized values in the scene and implementation before treating the
table as current runtime truth.

## Implemented perception values

| Setting | Implemented value |
| --- | --- |
| Core FOV | total `90°` |
| Peripheral FOV | total `140°` |
| Suspicion build time | `0.45 s` |
| Suspicion decay rate | `0.8` |
| Enter/exit threshold | `0.5 / 0.3` |
| Perception cadence | approximately `12 Hz` |
| Body turn speed | approximately `300°/s` |
| Facing threshold | approximately `3°` |

FOV values are total cone widths and comparisons use half-angles. Suspicion uses
measured perception-tick elapsed time rather than render-frame delta.

## Reflex values

The broad retained `Flinch_StepBack` design range is approximately `0.1–0.6 m`
with a yaw variation near `±30°` and no artificial start delay. The implemented
`NPC_01` fixture uses:

- serialized style seed `1001`;
- step distance `0.35 ± 0.05 m`;
- yaw offset within `±30°`;
- collision-constrained `CharacterController.Move`.

`RaiseHands_High` remains a later animation reference only. Its historical
reference ranges are hand height `0.70–0.95` and step back `0.10–0.40 m`; it is
not implemented behavior.

## Visible onset and timing

`VisibleMotionObserver` marks actual onset when the post-command root changes by
at least `0.01 m` or `1°`. Command and visible onset remain separate events.

The deterministic regression targets are:

- reflex selection/command substantially below `1 ms` when profiled;
- confirmed threat to visible motion p50 below `150 ms`;
- confirmed threat to visible motion p95 below `250 ms`.

These are fixture targets, not evidence of a measured distribution. Consult the
milestone evidence before making a performance claim.

## Telemetry location

Unity's Windows persistent-data convention places Editor/player output under:

```text
C:\Users\<user>\AppData\LocalLow\<CompanyName>\<ProductName>\
```

Use a session-unique JSONL filename or identifier. Event handlers enqueue typed
records; serialization and file I/O occur later. The logger must retain buffered
data on a failed write, expose the error, and reset static state safely when
Domain Reload is off.

See [`ARCH.md`](../../ARCH.md) for current contracts and
[`DETERMINISTIC_V1.md`](../history/DETERMINISTIC_V1.md) for provenance.
