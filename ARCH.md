# quickdraw-AI — Architecture and Code Contracts

## Authority and status

`CONTEXT.md` is the primary authoritative memory and requirements document. `PROJECT_CONTEXT.md` is its tracked, sanitized backup of public project information and the tracked progress record. This file translates their synchronized public project context into current architecture and code boundaries. It describes the intended first complete local system, not functionality that should be assumed to exist already.

## System overview

```text
Player controller
  └─ IsAiming + camera pose
       ↓
Structured aim-threat stimulus
       ↓
Soft perception
  ├─ distance and total-FOV half-angle checks
  ├─ line of sight
  ├─ suspicion with real tick delta
  └─ orientation and one-shot threat confirmation
       ↓
NPC behavior coordinator
  ├─ interrupt current activity
  ├─ dispatch local reflex
  └─ enter tactical recovery state
       ↓
Reflex execution
  ├─ select stable, cooldown-safe variant
  ├─ command visible placeholder motion immediately
  └─ emit dispatch event
       ↓
Visible-onset observer
  └─ detect first actual motion and emit measured latency

Optional later:
cached barks / structured memory / slow bias updates
  └─ affect future choices only
```

The default flow never maps a camera hit directly to a reflex. An explicit debug-only bypass may confirm a threat for isolated reflex testing.

## Modules and dependency direction

- `QuickDraw.Core` — player controller and development overlay.
- `QuickDraw.AI.Stimuli` — structured aiming stimulus or emitter.
- `QuickDraw.AI.Perception` — soft FOV, suspicion, visibility, and orientation.
- `QuickDraw.AI.Activity` — the current interruptible NPC activity.
- `QuickDraw.AI.Reflex` — reaction selection and immediate motion command.
- `QuickDraw.AI.Behavior` — explicit high-level state and recovery coordination.
- `QuickDraw.Logging` — structured event buffering, serialization, and summaries.
- `QuickDraw.AI.Memory` — optional later structured memory.

Dependency rules:

- Core does not know about individual NPCs.
- Stimuli describe the player state; they do not select reactions.
- Perception confirms threats but does not implement activities or tactical recovery.
- The behavior coordinator owns interruption and state edges.
- Reflex never calls logging file I/O, networking, tactical planning, or an LLM.
- Optional slow systems publish data that future local decisions may read.

Assembly definitions are optional later and should not delay the first vertical slice.

## Component contracts

### `SimpleFPSController`

Purpose: minimal first-person movement and an observable aiming state.

Expected behavior:

- Inherits `MonoBehaviour` and requires a `CharacterController`.
- Uses the Unity Input System directly through `Keyboard.current` and `Mouse.current`.
- Supports WASD, mouse look, gravity, cursor locking, RMB aim, smooth FOV change, and optional sprint/jump.
- Exposes `public bool IsAiming { get; private set; }`.
- Does not reference Starter Assets or NPC code.

### Aim-threat stimulus

The implemented structured value contains:

```csharp
public struct AimThreatStimulus
{
    public int SourceId;
    public Vector3 Origin;
    public Vector3 Direction;
    public float Timestamp;
    public float MaxDistance;
    public bool IsAiming;
}
```

`AimThreatEmitter` is attached to the player beside `SimpleFPSController`. It samples the configured player camera in `LateUpdate`, exposes the current snapshot, and raises one `AimStarted` or `AimEnded` event per aiming-state transition. It does not reference NPC behavior, perception, or reflex selection; perception remains the only path from stimulus data to threat confirmation.

The emitter exposes current aiming state and geometry without forcing a target reaction.

An optional serialized `bypassPerceptionForDebug` flag may allow a center-camera hit to invoke confirmed threat during isolated testing. It defaults to false and is not used for final evaluation.

### `SoftFOVPerception`

Purpose: model gradual visual awareness and produce a single confirmed-threat edge.

Implemented references and tunables:

- `eye`, player or stimulus source, and `occludersMask`;
- maximum visual distance;
- total core FOV `90°` and total peripheral FOV `140°`;
- suspicion build time `0.45 s`, decay rate `0.8`, and enter/exit thresholds `0.5/0.3`;
- perception tick rate near `12 Hz`;
- body turn speed near `300°/s` and facing threshold near `3°`.

Rules:

1. Reject by distance first.
2. Convert total FOV fields to half-angles before comparison.
3. Perform line of sight only for plausible angles and distances.
4. Update suspicion with measured elapsed perception-tick time.
5. Expose notice, threshold, and orientation transitions through state edges.
6. Confirm a threat only while the relevant aiming stimulus remains valid.
7. Emit threat confirmation once per episode.
8. Require a recovery/cooldown transition before a new episode can confirm.

Implemented states:

```text
Idle → Noticed → Suspicious → Orienting → ThreatConfirmed → Cooldown/Recovery
```

The implementation combines `Noticed` with `Suspicious`, exposes `StateChanged`, and emits `ThreatConfirmed` with the perception component as the event source. A camera ray intersecting the NPC `CharacterController` bounds qualifies the stimulus as relevant, but distance, cone, line-of-sight, suspicion, orientation, and one-shot rearming rules still control confirmation. Once confirmed, a renewed valid aim in the same unrearmed episode may continue steering the NPC without incrementing the episode or emitting another confirmation; invalid aim does not steer it. The component has no activity or reflex dependency.

`Test_Arena` provides a child `PerceptionEye` for sight checks and a small non-colliding `FacingMarker` so orientation is visible during playtests. In Play Mode, renderer-local material property blocks tint both the NPC capsule and facing marker green, yellow, orange, red, or cyan for `Idle`, `Suspicious`, `Orienting`, `ThreatConfirmed`, or `Recovering`; the shared arena material is never modified. Selected-object gizmos remain supplemental diagnostics for core/peripheral boundaries, the current source line, and eye position, with a matching state sphere above the capsule bounds.

### Interruptible activity

The first activity may be patrol between two markers or inspect at one marker. A lightweight explicit component is preferred over a general framework.

Minimum observable state:

- activity name and start time;
- running and interruptible flags;
- current target or progress;
- interruption reason and timestamp;
- suspended versus cancelled outcome;
- resume timestamp, if any.

Threat confirmation must stop activity motion before dispatching the reflex. It must not resume while the threat remains active.

### NPC behavior coordinator

Purpose: own high-level state edges and sequencing.

Suggested initial states:

```text
Activity
→ ThreatConfirmed
→ Reflex
→ RemainThreatened or Comply or FleeToMarker
→ Recover
→ ResumeActivity or Idle
```

This first implementation is a finite-state machine. A utility selector may later choose among a few recovery outcomes, but GOAP and behavior-tree frameworks are unnecessary.

### `ReflexSelector`

Purpose: choose a local reaction and command an immediate visible placeholder.

Initial reaction:

- `Flinch_StepBack` with collision-conscious root rotation or displacement.
- Parameters may include step distance, direction, and intensity.

Later reaction:

- `RaiseHands_High` after an animation or rig provides a real pose.

Rules:

- Accept a confirmed-threat timestamp and episode identifier.
- Ignore duplicate dispatch for the same episode.
- Use a serialized stable style seed or profile GUID.
- Apply cooldown and no-repeat rules when multiple variants exist.
- Perform no waits, coroutines, network calls, or disk I/O before the motion command.
- Emit an internal `reflex_commanded` event separately from observed motion.
- Do not label `Animator.SetTrigger` time as visible onset.

### Visible-onset observer

Purpose: identify when the commanded reaction becomes visibly measurable.

Acceptable signals include:

- root position or rotation exceeds a defined threshold;
- a tracked bone rotates beyond a threshold;
- a rig weight crosses a threshold;
- the Animator enters the target state and advances;
- an animation event explicitly marks first motion.

The observer emits `visible_motion_started` once per reaction episode. The primary SLA is calculated from `threat_confirmed` to this event.

### `JsonlLogger`

Purpose: preserve ordered structured evidence without urgent-path file I/O.

Rules:

- Use explicit DTOs, Newtonsoft JSON, or a custom writer.
- Do not pass anonymous objects to `JsonUtility`.
- Enqueue structured records in memory; serialize and flush outside the urgent path.
- Avoid per-event string construction in reflex dispatch where practical.
- Flush periodically and on quit; tolerate failures without affecting behavior.
- Reset singleton/static state safely when Domain Reload is disabled.
- Use a session-unique file name or session identifier.

## Timing model

Use `Time.realtimeSinceStartup` consistently for cross-stage event timestamps.

Required measurements:

```text
stimulus_start → perception_notice
perception_notice → suspicion_threshold
suspicion_threshold → turn_started
turn_started → threat_confirmed
threat_confirmed → activity_interrupted
threat_confirmed → reflex_commanded
reflex_commanded → visible_motion_started
threat_confirmed → visible_motion_started
threat_ended → recovered_or_resumed
```

Targets:

- Reflex selection and command execution: substantially under 1 ms when profiled.
- Confirmed threat to visible motion: p50 under 150 ms and p95 under 250 ms.
- Peripheral suspicion and orientation: intentionally separate from the reflex SLA.

Do not enforce an artificial delay to make reactions appear human. Variation should come from reaction parameters and later tactical choices, not from blocking initial acknowledgment.

## Event schema

Representative records:

```json
{"t":"activity_started","ts":2.000,"npcId":"NPC_01","activity":"Patrol"}
{"t":"aim_stimulus_started","ts":5.000,"sourceId":"Player"}
{"t":"perception_notice","ts":5.050,"npcId":"NPC_01","angleDeg":62.4,"hasLos":true}
{"t":"suspicion_threshold","ts":5.420,"npcId":"NPC_01","value":0.5}
{"t":"turn_started","ts":5.421,"npcId":"NPC_01"}
{"t":"threat_confirmed","ts":5.650,"npcId":"NPC_01","episodeId":3}
{"t":"activity_interrupted","ts":5.651,"npcId":"NPC_01","activity":"Patrol","reason":"Threat"}
{"t":"reflex_commanded","ts":5.653,"npcId":"NPC_01","variant":"Flinch_StepBack"}
{"t":"visible_motion_started","ts":5.690,"npcId":"NPC_01","signal":"root_delta","confirmation_to_visible_ms":40}
{"t":"tactical_state_changed","ts":5.800,"npcId":"NPC_01","state":"RemainThreatened"}
```

Session summaries should include counts and descriptive statistics for each defined stage, including min, max, mean, p50, p95, and optional standard deviation. A single reflex summary is insufficient for the final evaluation.

## Arena responsibilities

`Test_Arena` is a test fixture. Each object must support a named scenario:

- open lane for direct frontal threat;
- visual edge for peripheral notice;
- full-height divider for occlusion;
- two patrol markers for ongoing activity;
- interaction marker for interruption;
- low block or exit marker for later recovery choices.

Required initial scenarios:

1. Direct frontal threat.
2. Peripheral notice and orientation.
3. Occluded player with no false detection.
4. Patrol interrupted once.
5. Threat release followed by controlled recovery or resume.

## Expected first file map

Names marked “possible” are not fixed contracts.

```text
Assets/_Project/
  Code/
    Core/
      SimpleFPSController.cs
      DevOverlay.cs
    AI/
      Stimuli/
        AimThreatStimulus.cs
        AimThreatEmitter.cs
      Perception/
        SoftFOVPerception.cs
      Activity/
        PatrolActivity.cs
      Behavior/
        NpcBehaviorController.cs         (possible)
      Reflex/
        ThreatEvents.cs
        ReflexSelector.cs
        VisibleMotionObserver.cs         (possible)
    Logging/
      JsonlLogger.cs
      LogEvents.cs                       (possible DTOs)
  Scenes/
    Test_Arena.unity
```

There is no required `ThreatRaycaster.cs` in the canonical runtime architecture.

## Failure modes to test explicitly

- Total FOV is accidentally treated as a half-angle.
- Suspicion uses render-frame delta inside a lower-frequency tick.
- Occlusion masks are empty or include the target incorrectly.
- Threat confirmation or reflex dispatch repeats every tick.
- Patrol movement continues during surrender or flinch.
- Activity resumes while aiming remains active.
- A direct debug bypass remains enabled in an evaluation build.
- Raw root movement passes through a wall.
- Name hashing changes style behavior across sessions.
- Dispatch timestamp is reported as visible motion.
- Logging serialization allocates or writes from the urgent path.
- Static singleton state survives incorrectly with Domain Reload disabled.
