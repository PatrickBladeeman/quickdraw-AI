# quickdraw-AI — Tracked Project Context and Progress

## Authority and synchronization role

`CONTEXT.md` is the primary authoritative memory and requirements document for the project and local working session. `PROJECT_CONTEXT.md` is its tracked, sanitized backup of public project information and the repository's tracked progress record.

This file must remain synchronized with `CONTEXT.md` for public project scope, features, research framing, architecture and control flow, technical decisions and tuning, repository status and known defects, task and milestone progress, evaluation requirements, and non-goals. It intentionally excludes personal information, local-session details, private workflow material, credentials, and other internal-only context; those omissions are not synchronization drift.

When synchronized public information differs, `CONTEXT.md` controls and both documents must be realigned. For public repository readers who do not have the local `CONTEXT.md`, this file is the complete tracked reference for public project state. `ARCH.md` provides detailed code boundaries, `TASKS.md` provides the ordered execution plan, and `README.md` provides the short public introduction.

## Conflict-resolved decisions

- The project is an FPS AI behavior laboratory, not a survival or extraction game.
- A structured aiming stimulus flows through perception; direct camera-hit confirmation is debug-only.
- FOV values are total cone widths and comparisons use half-angles.
- Suspicion uses actual perception-tick elapsed time.
- Threat confirmation, interruption, and reflex dispatch occur on state edges and do not repeat every tick.
- `Flinch_StepBack` is the first measurable placeholder; `RaiseHands_High` comes later.
- Stable serialized seeds replace runtime name hashing.
- Command dispatch and observed visible motion are separate latency events.
- The first recovery controller is a finite-state machine.
- LLM, TTS, memory enrichment, GOAP, and broader tactics are deferred until the local loop is functional and measured.

## Mission

Build a small Unity FPS behavior laboratory that demonstrates how an NPC can preserve human-time responsiveness during urgent interactions while slower tactical or generative systems remain off the urgent path.

This is independent systems/HCI/applied-AI work. It is not a survival game, an extraction shooter, or core machine-learning research.

## Current downsized scope

The player needs only:

- WASD movement and mouse look.
- Optional sprint and jump.
- Right-mouse aiming with smooth FOV reduction.
- A public read-only `IsAiming` state.
- A center-screen aim direction or structured threat stimulus.

The player does not currently need a visible gun, shooting, damage, health, ammo, reloads, recoil, inventory, or weapon switching.

The first NPC needs only:

- One ongoing activity, initially patrol or inspect.
- Soft field-of-view perception with line of sight.
- Suspicion and turn-in-place orientation.
- Explicit interruption of its current activity.
- One visibly measurable placeholder reflex.
- One simple tactical recovery state.
- Detailed event and timing instrumentation.

The signature interaction is:

```text
NPC performs a basic activity
→ player enters peripheral awareness
→ NPC notices, hesitates, and turns
→ player remains in an aiming state
→ NPC confirms the threat
→ NPC interrupts its activity
→ NPC begins a visible reflex
→ NPC enters a simple recovery state
→ NPC later resumes or abandons the activity
```

## Canonical control flow

```text
Player.IsAiming
→ structured aim-threat stimulus
→ SoftFOVPerception evaluates distance, total-FOV half-angle, and line of sight
→ perception state edge: Idle → Suspicious → Orienting → ThreatConfirmed
→ current activity is interrupted once
→ ReflexSelector chooses and commands a local reaction once
→ visible-onset observer records the first measurable motion
→ local state machine chooses recovery
→ optional slow systems may influence later decisions
```

A camera ray may directly confirm a threat only behind an explicit debug bypass. It must not be the default or permanent gameplay path.

## Layer responsibilities

### Perception and stimulus

- The controller exposes `IsAiming`; it does not directly force an NPC reaction.
- A structured stimulus carries source, origin, direction, timestamp, maximum distance, and aiming state.
- Perception checks distance and angle before performing line of sight.
- `coreFOV = 90°` and `peripheralFOV = 140°` are total cone widths. Comparisons use half-angles of `45°` and `70°`.
- Perception ticks at approximately 12 Hz and uses measured tick elapsed time, not render-frame `Time.deltaTime`, for suspicion gain and decay.
- Peripheral suspicion builds over roughly 0.45 seconds with enter/exit thresholds of 0.5 and 0.3.
- Body orientation may update every rendered frame at roughly 300 degrees per second.
- Threat confirmation is an event edge, not a condition that retriggers every tick.

### Activity and interruption

- The NPC starts with one simple, inspectable activity.
- Threat confirmation stops movement or interaction before the reflex begins.
- The system records what was interrupted, why, when, and whether it was suspended or cancelled.
- The old activity must not immediately restart while the threat remains active.
- Repeated perception samples must not repeatedly interrupt the same activity.

### Reflex

- The reflex path is local, synchronous, and substantially under one frame of code execution.
- It performs no network calls, disk I/O, waits, or coroutine delay before visible feedback.
- The first reaction is `Flinch_StepBack` because root rotation or displacement provides an obvious measurable onset without requiring humanoid animation assets.
- `RaiseHands_High` is a later second reaction after a suitable animation or rig exists.
- Variation uses a serialized stable seed or profile identifier, never `gameObject.name.GetHashCode()`.
- Cooldowns and state edges prevent repeated reactions.
- Collision-aware motion should replace raw root teleportation; a small direct transform delta is acceptable only as a clearly labeled early placeholder.

### Tactical recovery

- The first recovery implementation is a small explicit state machine, not GOAP or a behavior-tree framework.
- Initial outcomes may be `RemainThreatened`, `Comply`, `FleeToMarker`, `Recover`, and `ResumeActivity`.
- Tactical work must not delay perception, interruption, or reflex dispatch.

### Optional asynchronous enrichment

LLM integration is deferred until the complete local loop is functional and measured. Later, an asynchronous worker may generate cached barks, summarize memory, or nudge future biases. The NPC must behave correctly when that worker is absent.

## Timing and telemetry

Do not collapse the whole interaction into one vague latency value. Record distinct stages:

- stimulus start → perception notice;
- notice → suspicion threshold;
- threshold → orientation start;
- orientation → threat confirmation;
- confirmation → activity interruption;
- confirmation → reflex command;
- command → first observed visible motion;
- confirmation → first observed visible motion;
- threat end → recovery or activity resumption.

The primary responsiveness target is:

- median confirmed-threat → visible-motion latency under 150 ms;
- p95 under 250 ms.

Peripheral hesitation and turn time are intentional and must be reported separately.

Calling `Animator.SetTrigger`, assigning a rig weight, or recording a same-method timestamp is internal dispatch, not proof of visible onset. Visible onset requires an observed signal such as root displacement, bone rotation, rig weight crossing a threshold, or animation-state progress.

Logging requirements:

- Use `Time.realtimeSinceStartup` for event timestamps.
- Use explicit serializable DTOs, Newtonsoft JSON, or a custom writer; Unity `JsonUtility` with anonymous objects is invalid.
- Do not serialize or write files directly in the reflex hot path.
- Queue structured events in memory and flush outside the urgent path.
- Reset static logger state safely when Domain Reload is disabled.

## Technical baseline

- Unity: `6000.0.57f1`.
- Intended render pipeline: URP.
- Input: Unity Input System using `Keyboard.current` and `Mouse.current`; no Input Actions asset is required for the first controller. Active Input Handling may be `Input System Package (New)` or `Both`.
- Current relevant packages include Input System, ProBuilder, Animation Rigging, Newtonsoft JSON, AI Navigation, and URP.
- Starter Assets are not required and must not become a dependency.
- VSync should be off and Incremental GC on.
- Enter Play Mode should use Domain Reload off and Scene Reload on, with static lifecycle safeguards.

### Current repository baseline

The repository is still a pre-MVP scaffold:

- `Test_Arena` now contains the required `Player → CameraPivot → Main Camera` hierarchy, a configured `CharacterController`, a light, floor, and ceiling, but not yet the complete arena fixture.
- `SimpleFPSController` is an attachable custom Input System controller with WASD movement, mouse look, gravity, sprint, jump, cursor toggling, RMB aim, smooth FOV, and public read-only `IsAiming` state.
- Three focused Unity Play Mode tests verify the Task 2 component contract, scene configuration, and input-driven behavior; the tests pass, and a Windows standalone build also succeeds in Unity `6000.0.57f1`.
- Perception, reflex, logger, and overlay scripts exist as unwired scaffolds.
- NPC activity, interruption coordination, recovery state, and trustworthy visible-onset telemetry do not yet exist.
- Tracked URP renderer and pipeline assets now resolve in Graphics and both Quality levels; `Test_Arena` passed batch-mode pipeline and material validation in Unity `6000.0.57f1`.
- `Test_Arena` is the sole enabled Build Settings scene; the package lock and editor settings are tracked; VSync is off, Incremental GC is on, Active Input Handling is `Both`, and Enter Play Mode disables Domain Reload while retaining Scene Reload.

The next implementation task is `TASKS.md` section 3: complete the minimal test arena.

## Arena

`Assets/_Project/Scenes/Test_Arena.unity` is a controlled greybox testbed. Its eventual minimum contents are:

- floor, ceiling, and four walls;
- one full-height occluder and one low block;
- player spawn and NPC spawn;
- two patrol markers;
- one interaction marker;
- a `Systems` object for diagnostics and logging.

Do not add production art, a large map, complex NavMesh layout, combat encounters, loot, or decorative props that do not support a named test.

## Current definition of done

The first complete local milestone requires:

1. A working custom FPS controller with `IsAiming`.
2. One NPC performing an ongoing activity.
3. Correct total-FOV cone math, line of sight, tick delta, suspicion, and orientation.
4. One-shot activity interruption on confirmed threat.
5. A visibly measurable `Flinch_StepBack` placeholder.
6. Separate command and observed-motion telemetry.
7. A simple recovery or resume transition.
8. Repeatable frontal, peripheral, occluded, interrupted-activity, and threat-release tests.

LLMs, generated speech, structured long-term memory, multiple reaction families, automated experiments, and a polished report come only after this milestone.

## Hard non-goals

Do not implement without an explicit scope change:

- inventory, hunger, thirst, crafting, loot, or an extraction economy;
- firearms, shooting, ammo, reloads, damage, or full combat;
- multiplayer or networking;
- reinforcement learning or LLM training;
- large behavior-tree or GOAP frameworks;
- production art, procedural worlds, group AI, speech recognition, or high-quality TTS.

## Work discipline

- Follow the ordered tasks in `TASKS.md` one narrow task at a time.
- Inspect the actual repository before assuming a documented component exists.
- Keep implementation changes under `Assets/_Project/**` unless a task explicitly requires packages or ProjectSettings.
- Let Unity compile and verify behavior in Play Mode after each implementation task.
- Prefer state correctness, reproducible evidence, and clear instrumentation over visual polish.

## Additional tuning and compatibility references

These values are retained as design references rather than claims of completed functionality.

### Suggested first-person controller tuning

- `moveSpeed = 5`
- `sprintMultiplier = 1.4`
- `mouseSensitivity = 1.8`
- `mouseSensitivityAim = 1.2`
- `normalFOV = 70`
- `aimFOV = 55`
- `fovLerp = 12`
- `gravity = -9.81`
- `jumpHeight = 1.1`

The controller uses the corrected design: use the Unity Input System directly, expose `IsAiming`, and do not depend on Starter Assets.

### Corrected reaction tuning reference

`Flinch_StepBack` is the first placeholder reaction:

- step-back distance: approximately `0.1–0.6 m`, constrained by collision and environment;
- flinch direction: approximately `±30°`;
- no artificial start delay.

`RaiseHands_High` is a later reaction after a real animation or rig exists:

- hand height reference: approximately `0.70–0.95`;
- step-back reference: approximately `0.10–0.40 m`.

Multiple reactions later use cooldowns, no-repeat behavior, environment constraints, and a serialized stable style seed. The original name-hash guidance is superseded.

### Log location reference

The intended Windows Editor output remains under:

`C:\Users\<user>\AppData\LocalLow\<CompanyName>\<ProductName>\`

Use a session-unique JSONL filename or identifier. Logging implementation must follow the corrected buffering, DTO serialization, and visible-onset requirements below.

### Superseded requirements

Earlier plans described a permanent `ThreatRaycaster`, same-frame animation-command latency, `RaiseHands_High` as the first reaction, name-hash randomness, early Utility/GOAP work, and an early LLM worker. Those plans are superseded and must not be implemented as current requirements.

## Project history and decision record

Earlier ideas remain documented for research provenance. The current operational scope and explicit corrections above control implementation.

### 2. Original idea

The original concept was a survival or extraction-shooter-style FPS with agentic NPCs that could:

- react to the environment,
- respond to player actions,
- fight,
- gather resources,
- manage hunger and thirst,
- use inventory,
- make plans,
- speak through generated dialogue,
- remember previous interactions,
- and change long-term strategy.

The project was inspired by public AI-NPC demonstrations and industry experiments involving:

- conversational NPCs,
- generated dialogue,
- persistent character memory,
- contextual reactions,
- and game characters with broader goals than traditional scripted dialogue trees.

The initial working thesis concept was similar to:

> Procedural generation of narratives and combat policies through constrained natural-language agents.

That was too broad.

The better research focus became:

> How can a real-time game preserve fast, believable NPC reactions while using slower generative reasoning for context, dialogue, strategy, and memory?

The clearest example is:

- the player points a gun at an NPC,
- the NPC must react in human time,
- but an LLM request may take hundreds of milliseconds or several seconds,
- and TTS may add more delay.

A naïve system that waits for the LLM before reacting will fail.

The project therefore focuses on a **hybrid latency-bounded architecture**.

---

### 3. Honest evaluation of the idea

The current evaluation is:

- The project is a good idea.
- It is clearly AI-adjacent.
- It is not core ML research.
- It fits systems, HCI, interactive AI, and game AI.
- It is weaker if it becomes only a polished game demo.
- It is stronger if it produces measurable architecture and experiments.

The project should not try to prove:

- a new language model,
- a new training technique,
- state-of-the-art combat AI,
- or a complete commercial game.

The strongest contribution is:

1. separating urgent reactions from slow reasoning,
2. measuring the complete interaction pipeline,
3. showing interruption and recovery,
4. demonstrating variation without waiting for an LLM,
5. and showing that asynchronous reasoning does not damage urgent responsiveness.

---

### 4. Current downsized scope

#### 4.1 Why the project was downsized

The original survival/extraction design included too many systems:

- inventory,
- hunger,
- thirst,
- weapons,
- reloading,
- crafting,
- resource gathering,
- extraction,
- combat,
- animation libraries,
- dialogue,
- long-term memory,
- tactical planning,
- and LLM integration.

With roughly two months and limited daily time, this would likely produce an unfinished game and weak research evidence.

Inventory and survival systems were therefore removed from the current scope.

This is the correct decision.

#### 4.2 Current project definition

The project should currently be treated as:

> An FPS-based AI behavior laboratory for testing perception, interruption, urgent reactions, and basic tactical recovery.

The player needs only:

- WASD movement,
- mouse look,
- optional sprint,
- right-mouse aiming,
- a center-screen aim direction or threat stimulus,
- and possibly a crosshair.

The player does not currently need:

- a visible weapon,
- shooting,
- ammo,
- reload,
- recoil,
- damage,
- inventory,
- health,
- or weapon switching.

The NPC needs only:

- idle or patrol behavior,
- one simple environment interaction,
- soft field-of-view perception,
- suspicion,
- turn-in-place,
- task interruption,
- one or two visible reflexes,
- and a simple post-reflex state.

The signature interaction should be:

```text
NPC performs a basic activity
→ player enters peripheral awareness
→ NPC hesitates and turns
→ player aims
→ NPC interrupts its current task
→ NPC reacts immediately
→ NPC chooses a simple follow-up
→ NPC later resumes or revises its behavior
```

This chain is the core project.

---

### 5. Research framing

#### 5.1 Recommended working title

Possible paper title:

> Latency-Bounded Hybrid NPCs for Real-Time FPS Interactions

Other acceptable research-style titles:

- Human-Time Reactions for Generative NPCs
- A Layered Architecture for Responsive Agentic NPCs
- Separating Reflex and Deliberation in Real-Time Interactive Agents
- Latency-Aware Agentic NPCs in a Unity FPS Testbed

The repository can remain named `quickdraw-AI` even though the long-term architecture includes more than reflexes.

#### 5.2 Core research question

> How can a real-time NPC preserve human-time responsiveness during urgent interactions while still using slower asynchronous reasoning for tactical context, dialogue, memory, and longer-term adaptation?

#### 5.3 Core hypothesis

A layered architecture can preserve perceived responsiveness if:

- urgent perception and reflexes are local,
- slower reasoning never blocks the urgent path,
- immediate visual or audio acknowledgment begins before generated output arrives,
- slow systems update future biases rather than controlling the current frame,
- and the entire pipeline is instrumented.

#### 5.4 Intended contribution

A realistic contribution is:

1. A layered NPC architecture with explicit latency budgets.
2. A soft-perception pipeline that separates notice, confirmation, and reflex.
3. A task-interruption mechanism.
4. Procedural reaction variation without live LLM inference.
5. End-to-end telemetry for perceived reaction timing.
6. Optional asynchronous generative enrichment that leaves reflex timing unchanged.

This is systems/HCI/applied-AI work, not core ML.

---

### 6. Architecture overview

The architecture contains three conceptual layers.

#### 6.1 Reflex layer

The reflex layer handles urgent reactions.

Properties:

- local,
- fast,
- deterministic or utility-weighted,
- no network calls,
- no disk I/O,
- no LLM dependency,
- no waits,
- no coroutine delay before initial visible feedback.

Responsibilities:

- receive confirmed threat events,
- interrupt current behavior,
- choose a reaction family,
- begin visible motion,
- optionally play immediate nonverbal audio,
- log event and timing information,
- expose the selected reaction to the tactical layer.

Examples:

- flinch,
- freeze,
- step backward,
- raise hands,
- crouch,
- drop an object,
- turn the head toward the threat.

The reflex path should execute in substantially less than one frame. The user-facing latency budget refers to visible reaction, not code execution.

#### 6.2 Tactical or reflection layer

This layer handles short-horizon follow-up.

Responsibilities:

- comply,
- flee,
- investigate,
- remain frozen,
- seek basic cover,
- resume the interrupted task,
- abandon the interrupted task,
- and update reaction weights.

Inputs may include:

- distance to player,
- whether the player is aiming,
- line of sight,
- available exits,
- current task,
- fear,
- trust,
- personality,
- whether the NPC is cornered,
- and persistent memory.

This layer does not require ML.

The first version can use:

- a finite-state machine,
- a utility selector,
- or a very lightweight planner.

A state machine is preferred initially because it is easier to debug and instrument.

#### 6.3 Deliberative or LLM layer

This layer is optional until the local system works.

Possible later responsibilities:

- generate bark variants,
- generate contextual dialogue,
- summarize encounters into structured memory,
- update slow personality or tactical biases,
- suggest longer-term goals,
- or produce natural-language explanations.

It must never:

- block the reflex layer,
- directly manipulate animation every frame,
- control frame-by-frame movement,
- be required for perception,
- or be required for basic gameplay.

If the LLM worker is unavailable, the NPC should still function.

---

### 7. Canonical event flow

The intended final flow is:

```text
Player enters aiming state
→ a structured threat stimulus exists
→ NPC perception evaluates angle, visibility, and awareness
→ NPC notices or accumulates suspicion
→ NPC turns toward the source
→ threat is confirmed
→ current task is interrupted
→ reflex reaction starts
→ tactical layer chooses follow-up
→ optional async LLM output arrives later
```

Do not permanently implement:

```text
camera ray hits NPC
→ directly force flinch
```

That direct path is acceptable only as a debug mode for testing the reflex layer.

---

### 8. Soft field of view

#### 8.1 Goal

Perception should feel gradual rather than binary.

Expected behavior:

- Player directly in front: fast recognition.
- Player in peripheral vision: hesitation and orientation.
- Player outside visual field: no visual response.
- Player behind an occluder: no visual response.
- Player behind the NPC: no immediate response unless another sense exists.

#### 8.2 Suggested cone values

The initial design used:

- core FOV: 90 degrees,
- peripheral FOV: 140 degrees.

Important: the implementation must define whether these are total widths or half-angles.

Recommended convention:

```text
Core total FOV: 90°
Core half-angle: 45°

Peripheral total FOV: 140°
Peripheral half-angle: 70°
```

Code should either:

- store half-angles explicitly,
- or divide total FOV fields by two before comparing to the angle from forward.

Earlier scaffold pseudocode compared `angle <= 90`, which would create a 180-degree total cone. That should be corrected.

#### 8.3 Suspicion

Peripheral perception should build suspicion over approximately:

- 0.25 to 0.6 seconds,
- default around 0.45 seconds.

Suggested hysteresis:

- enter suspicious behavior at `0.5`,
- leave suspicious behavior below `0.3`.

This prevents rapid toggling near the cone boundary.

#### 8.4 Perception tick

Run perception around:

- 10–20 Hz,
- default around 12 Hz.

Do not use a full line-of-sight raycast for every NPC every render frame.

Suggested process:

1. Check distance.
2. Check angle.
3. Only perform line of sight if angle and distance are plausible.
4. Update suspicion with the actual elapsed perception-tick time.

Important known bug:

Earlier scaffold code called perception at 12 Hz but added suspicion using render-frame `Time.deltaTime`. This produces incorrect accumulation.

Use:

- measured elapsed time since the previous perception tick,
- or `1 / tickRateHz` when the scheduler is stable.

#### 8.5 Turn behavior

When suspicious:

- begin head/gaze orientation if available,
- rotate the body toward the player,
- confirm threat when yaw difference is below a threshold.

Suggested defaults:

- body turn rate: 240–360 degrees per second,
- default: 300 degrees per second,
- confirmation threshold: 3 degrees.

#### 8.6 Perception state machine

Recommended explicit states:

```text
Idle
→ Noticed
→ Suspicious
→ Orienting
→ ThreatConfirmed
→ Cooldown or Recovery
```

A simpler version may combine `Noticed` and `Suspicious`, but explicit states make instrumentation easier.

Potential transitions:

```text
Idle
  → Suspicious:
      player is within peripheral cone and visible

Suspicious
  → Orienting:
      suspicion crosses threshold

Orienting
  → ThreatConfirmed:
      NPC faces source and aiming stimulus remains valid

Suspicious or Orienting
  → Idle:
      line of sight is lost and suspicion decays below exit threshold
```

---

### 9. Threat stimulus design

#### 9.1 Player aiming state

The custom FPS controller should expose:

```csharp
public bool IsAiming { get; private set; }
```

RMB changes this state.

The player does not need a real gun yet.

#### 9.2 Threat stimulus

A future structured stimulus could contain:

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

Possible target-specific information:

- ray intersects the NPC,
- distance,
- angle from NPC forward,
- occlusion,
- source identity.

#### 9.3 Direct debug mode

A debug mode can allow:

```text
RMB + camera ray hits NPC
→ directly invoke confirmed threat
```

This is useful for testing:

- reflex selection,
- interruption,
- animation,
- and logging.

It should be controlled by an explicit flag such as:

```csharp
[SerializeField] private bool bypassPerceptionForDebug;
```

Default final behavior should not bypass perception.

---

### 10. Task interruption

Interruption is one of the most important project behaviors.

A generic LLM NPC that can talk but cannot interrupt an animation or task is not convincing.

The initial NPC should perform a simple task such as:

- patrol between two points,
- inspect a table,
- walk toward a marker,
- look at a console,
- or interact with a placeholder object.

When a threat is confirmed:

```text
Current task
→ interrupt request
→ movement or interaction stops
→ previous task state is saved or abandoned
→ reflex begins
→ tactical recovery decides whether to resume
```

Track:

- current task,
- task start time,
- task priority,
- whether it is interruptible,
- interruption reason,
- interruption timestamp,
- whether it was suspended or cancelled,
- and when it resumes.

Potential initial task interface:

```csharp
public interface IInterruptibleActivity
{
    bool IsRunning { get; }
    bool CanInterrupt { get; }

    void Begin();
    void Tick(float deltaTime);
    void Interrupt(ActivityInterruptReason reason);
    void Resume();
    void Cancel();
}
```

This may be over-engineered for the first implementation. A simple patrol component with explicit methods is acceptable.

Important failure cases:

- NavMeshAgent continues moving during surrender.
- Old animation keeps playing.
- NPC resumes patrol while the player is still aiming.
- An interrupted interaction immediately restarts every frame.
- Reflex repeatedly re-interrupts the same task.

---

### 11. Reaction design and variation

#### 11.1 Minimum reactions

Start with one reaction that is visibly measurable.

Recommended first reaction:

- `Flinch_StepBack`

Reason:

- it can be represented using root rotation or displacement,
- does not require a polished humanoid hand rig,
- provides an obvious visible onset.

Second reaction:

- `RaiseHands_High`

This requires either:

- a humanoid animation,
- hand IK,
- or a clear placeholder pose.

#### 11.2 Variation mechanisms

The fast layer can produce variation without an LLM.

Use:

- stable per-NPC seed,
- personality values,
- environment constraints,
- parameter variation,
- cooldowns,
- and no-repeat masks.

Possible personality values:

```text
fearfulness
aggression
pride
impulsivity
discipline
trust
```

Possible reaction parameters:

```text
step-back distance
flinch direction
hand height
turn speed
reaction intensity
gaze target
crouch depth
```

#### 11.3 Stable randomness

Do not rely on:

```csharp
gameObject.name.GetHashCode()
```

for cross-session deterministic behavior.

Use:

- serialized integer seed,
- GUID,
- stable custom hash,
- or NPC profile asset.

Example:

```csharp
[SerializeField] private int styleSeed = 1001;
```

#### 11.4 No-repeat mask

Prevent the same NPC from selecting the same reaction repeatedly inside a short window.

Example:

```text
last reaction = Flinch
cooldown = 2 seconds
next selection biases away from Flinch
```

#### 11.5 Environment-aware constraints

Examples:

- wall behind NPC limits backward displacement,
- cover on left biases leftward movement,
- narrow corridor disables wide lateral step,
- held object may need to be dropped,
- player proximity affects whether the NPC can flee.

---

### 12. Player controller

#### 12.1 Decision

Use a custom Unity `CharacterController`-based FPS controller.

Do not depend on the Starter Assets package for the current MVP.

This decision was made because:

- the required feature set is tiny,
- Starter Assets import caused URP and missing prefab errors,
- integrating a larger package would consume time,
- and the controller is not the research contribution.

#### 12.2 Required hierarchy

```text
Player
├── CharacterController
├── SimpleFPSController
└── CameraPivot
    └── Main Camera
```

Optional later:

```text
Main Camera
└── ThreatStimulusEmitter
```

#### 12.3 Suggested transforms

```text
Player position: (0, 1, -4)
CameraPivot local position: (0, 0.65, 0)
Main Camera local position: (0, 0, 0)
```

#### 12.4 CharacterController values

```text
Center: (0, 1, 0)
Height: 2
Radius: 0.4
Step Offset: 0.3
Slope Limit: 45
```

#### 12.5 Controller features

- WASD.
- Mouse look.
- Gravity.
- Optional sprint.
- Optional jump.
- RMB aiming.
- Smooth FOV reduction.
- Cursor lock.
- Escape toggles cursor lock.
- `IsAiming` public read-only state.

#### 12.6 Input system

The current proposed controller uses:

```csharp
using UnityEngine.InputSystem;
```

and directly reads:

```csharp
Keyboard.current
Mouse.current
```

It does not require an Input Actions asset.

Required package:

- Input System.

Project setting:

```text
Edit
→ Project Settings
→ Player
→ Active Input Handling
→ Input System Package (New)
```

`Both` is also acceptable.

#### 12.7 Current file ambiguity

The repository may already contain:

- `SimpleFPSController.cs`,
- possibly an older legacy-input version,
- possibly the newer Input System version.

Inspect the actual file before changing it.

Acceptance:

- project compiles,
- player moves,
- mouse look works,
- RMB changes FOV and `IsAiming`,
- no Starter Assets dependency exists.

---

### 13. Animation strategy

#### 13.1 First prototype

Do not block development on animation assets.

Acceptable placeholders:

- rotate root,
- move root slightly,
- change capsule scale,
- change material,
- move a child transform,
- or display a debug pose indicator.

The first goal is state correctness and timing.

#### 13.2 Later animation minimum

Eventually implement:

- turn-in-place,
- flinch,
- hands-up or partial compliance,
- optional head-look.

Use Animation Rigging later for:

- head tracking,
- hand targets,
- spine rotation,
- procedural pose variation.

Do not make motion matching, Final IK, or a large animation library required.

---

### 14. Arena design

The arena is a controlled testbed, not a game level.

#### 14.1 Current scene

Expected scene:

`Assets/_Project/Scenes/Test_Arena.unity`

The scene currently contains only:

- floor,
- ceiling.

Do not assume walls, NPCs, or player objects exist without inspection.

#### 14.2 Minimal map elements

Build:

- floor,
- ceiling,
- four walls,
- one occluding wall or divider,
- one waist-high block,
- one simple interaction object,
- two patrol markers,
- player spawn,
- NPC spawn.

Example:

```text
┌───────────────────────────────────┐
│ Patrol B        Full-height wall  │
│                                   │
│        Interaction marker         │
│                                   │
│ Low block          NPC spawn      │
│                                   │
│ Player spawn       Patrol A       │
└───────────────────────────────────┘
```

Each object has a purpose:

- open area: direct frontal test,
- divider: line-of-sight test,
- edge: peripheral test,
- patrol points: ongoing activity,
- interaction marker: interruption,
- block: later cover context.

#### 14.3 Do not add yet

- realistic art,
- large maps,
- outdoor terrain,
- stairs,
- elevated platforms,
- extraction zones,
- loot rooms,
- complex NavMesh,
- detailed lighting,
- or many props.

---

### 15. AI test scenarios

The test suite should grow in this order.

#### 15.1 Direct frontal threat

Setup:

- NPC faces player.
- Player aims.

Test:

- threat confirmation,
- interruption,
- reflex onset,
- cooldown.

#### 15.2 Peripheral notice

Setup:

- player enters edge of visual cone.

Test:

- suspicion,
- orientation,
- hesitation,
- confirmation.

#### 15.3 Occluded player

Setup:

- wall between player and NPC.

Test:

- no false visual detection.

#### 15.4 Interrupted patrol

Setup:

- NPC walks between two points.
- player aims.

Test:

- movement stops,
- current state is recorded,
- reaction starts,
- recovery is correct.

#### 15.5 Resume after threat

Setup:

- threat ends.

Test:

- NPC waits for a recovery condition,
- then resumes or abandons task.

#### 15.6 Open route versus cornered

Later:

- one configuration gives a flee route,
- another blocks it.

Test:

- flee versus comply.

#### 15.7 Structured memory

Later:

- same NPC is threatened or spared twice.

Test:

- fear/trust values change,
- future follow-up changes.

#### 15.8 Multi-NPC divergence

Later:

- two NPCs have different seeds and personalities.

Test:

- avoid cloned reactions.

---

### 16. Instrumentation

Observability is a central project strength.

#### 16.1 Why it matters

The project must show:

- when a stimulus began,
- when the NPC noticed,
- when suspicion crossed threshold,
- when orientation started,
- when threat was confirmed,
- when current behavior was interrupted,
- when a reaction was selected,
- when a visible change began,
- and what tactical state followed.

#### 16.2 Suggested event stream

```json
{"t":"session_start","ts":1.234,"unity":"6000.0.57f1"}
{"t":"scene_loaded","ts":1.500,"scene":"Test_Arena"}
{"t":"activity_started","ts":2.000,"npcId":"NPC_01","activity":"Patrol"}
{"t":"aim_stimulus_started","ts":5.000,"sourceId":"Player","targetId":"NPC_01"}
{"t":"perception_notice","ts":5.050,"npcId":"NPC_01","angleDeg":62.4,"hasLos":true}
{"t":"suspicion_started","ts":5.050,"npcId":"NPC_01"}
{"t":"suspicion_threshold","ts":5.420,"npcId":"NPC_01","value":0.5}
{"t":"turn_started","ts":5.421,"npcId":"NPC_01"}
{"t":"threat_confirmed","ts":5.650,"npcId":"NPC_01"}
{"t":"activity_interrupted","ts":5.651,"npcId":"NPC_01","activity":"Patrol","reason":"Threat"}
{"t":"reflex_selected","ts":5.652,"npcId":"NPC_01","variant":"Flinch_StepBack"}
{"t":"reflex_commanded","ts":5.653,"npcId":"NPC_01"}
{"t":"visible_motion_started","ts":5.690,"npcId":"NPC_01","signal":"root_delta"}
{"t":"tactical_state_changed","ts":5.800,"npcId":"NPC_01","state":"Comply"}
```

#### 16.3 Separate timing stages

Do not report one vague “reaction latency.”

Measure:

- stimulus-to-notice,
- notice-to-suspicion-threshold,
- suspicion-to-facing,
- facing-to-threat-confirmation,
- confirmation-to-reflex-command,
- command-to-visible-motion,
- confirmation-to-visible-motion,
- task-interruption latency.

#### 16.4 Visible onset

Earlier code measured:

```text
event timestamp
→ same-frame Animator.SetTrigger timestamp
```

That is not a valid measurement of visible reaction.

Better signals:

- root moved beyond a threshold,
- head bone rotated beyond a threshold,
- rig weight exceeded a threshold,
- Animator state entered and normalized time advanced,
- animation event marked visible motion.

Keep both:

- internal dispatch latency,
- visible onset latency.

#### 16.5 Logger implementation warning

The original scaffold used `JsonUtility.ToJson` with anonymous objects.

Unity `JsonUtility` is not suitable for arbitrary anonymous objects and may serialize them incorrectly or as empty objects.

Fix using one of:

1. Newtonsoft JSON.
2. Explicit serializable DTO classes.
3. A custom JSON writer.

Newtonsoft is acceptable if installed.

#### 16.6 Buffering

Do not write files from the reflex path.

Use:

- in-memory queue,
- periodic flush,
- flush on quit,
- optional background writer later.

#### 16.7 Summary metrics

Compute:

- count,
- min,
- max,
- mean,
- p50,
- p95,
- optional p99,
- and standard deviation.

---

### 17. Performance targets

#### 17.1 Reflex execution

Reflex selection and dispatch should be much less than 150 ms.

Target:

- under 1 ms of code execution,
- no network,
- no disk I/O,
- no blocking,
- ideally zero GC allocation.

#### 17.2 Perceived reaction

Target discussed:

- median visible reaction under 150 ms,
- p95 under 250 ms.

Apply this target to:

> confirmed threat → first visible response

Do not include deliberate peripheral suspicion time in the reflex metric.

#### 17.3 Perception timing

Peripheral hesitation is intentional.

Report separately:

- time spent suspicious,
- time spent turning,
- and reflex onset after confirmation.

#### 17.4 Frame conditions

Early development:

- Editor,
- VSync off,
- profiler checks.

Final evaluation:

- standalone Windows build,
- possibly 60 FPS cap,
- optional 30 FPS comparison.

---

### 18. Unity setup

#### 18.1 Editor

Chosen version:

`Unity 6000.0.57f1`

#### 18.2 Render pipeline

The project may have started as 3D Core.

Starter Assets were imported and produced:

```text
Universal Render Pipeline Asset was not found.
```

They also received a missing nested prefab error for `UI_EventSystem`.

Current resolution: URP is configured with tracked renderer and pipeline assets under `Assets/_Project/Settings/`. Graphics and both Quality levels reference the tracked pipeline asset, and `Test_Arena` opens without missing-pipeline, missing-material, or error-shader failures in Unity `6000.0.57f1` batch validation.

The project can use:

- URP,
- or Built-in for the early prototype.

Do not spend excessive time on URP unless current assets require it.

Inspect:

- `Packages/manifest.json`
- `ProjectSettings/GraphicsSettings.asset`
- `ProjectSettings/QualitySettings.asset`
- URP asset files under `Assets`
- `Assets/Starter Assets`

The Starter Assets package is not a required dependency and may be removable.

#### 18.3 Packages

Likely or intended packages:

- Input System
- ProBuilder
- Animation Rigging
- Newtonsoft JSON

Optional:

- Cinemachine

Not needed:

- FPS template
- large controller framework
- behavior-tree package
- GOAP package
- ML-Agents

#### 18.4 Settings previously discussed

- VSync: Don't Sync.
- Incremental GC: On.
- Enter Play Mode Options:
  - Domain Reload Off for fast iteration,
  - Scene Reload On.
- Visible Meta Files.
- Force Text asset serialization.
- Auto Refresh on.

Current resolution: `Test_Arena` is the sole enabled Build Settings scene, `Packages/packages-lock.json` and `ProjectSettings/EditorSettings.asset` are tracked, VSync is off for both Quality levels, Incremental GC is on, Active Input Handling is `Both`, and Enter Play Mode disables Domain Reload while keeping Scene Reload enabled.

Important:

Domain Reload Off can cause stale static singleton fields. Logger singletons must reset safely.

---

### 19. Repository

#### 19.2 Expected files

```text
Assets/
  _Project/
    Code/
      Core/
      AI/
        Perception/
        Reflex/
        Tactical/
      Logging/
    Prefabs/
    Scenes/
    ScriptableObjects/
    Audio/
Packages/
ProjectSettings/
README.md
PROJECT_CONTEXT.md
ARCH.md
TASKS.md
.codexignore
.gitignore
.gitattributes
CITATION.cff
ASSETS_LICENSE.md
LICENSE
.env.example
```

#### 19.3 Track

Track:

- source code,
- `.meta`,
- folder `.meta`,
- scenes,
- prefabs,
- packages manifest,
- packages lock,
- ProjectSettings,
- documentation.

#### 19.4 Ignore

Ignore:

- Library
- Temp
- Logs
- Obj
- obj
- Build
- Builds
- UserSettings
- .idea
- .vs
- generated `.csproj`
- generated `.sln`

#### 19.5 Public-asset rule

Do not commit:

- paid assets,
- proprietary or otherwise non-redistributable third-party assets,
- unredistributable animations,
- licensed audio without permission.

---

#### 19.5 Text and line-ending policy

Use stable text normalization:

```gitattributes
* text=auto

*.cs text eol=lf
*.meta text eol=lf
*.unity text eol=lf
*.prefab text eol=lf
*.asset text eol=lf
*.md text eol=lf
*.json text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.cff text eol=lf
```

### 22. Known scaffold issues

The initial scaffold was a starting point, not trusted production code.

#### 22.1 JSON serialization

Anonymous objects plus `JsonUtility` may not serialize.

#### 22.2 Suspicion delta

The soft-FOV code may use render-frame delta inside a low-frequency tick.

#### 22.3 FOV values

The code may treat total FOV degrees as half-angle.

#### 22.4 Repeated reactions

The NPC may trigger the reflex repeatedly every time the perception loop observes the same state.

Use state edges and cooldowns.

#### 22.5 Direct bypass

`OnDirectThreatDetected()` may skip perception entirely.

Keep only as debug.

#### 22.6 Root teleport

Directly changing `transform.position` for step-back ignores collision.

Acceptable only as placeholder.

#### 22.7 Unstable seed

Name hash may be unstable.

#### 22.8 Child-collider caching

Threat raycast component caching may incorrectly compare child collider GameObjects.

#### 22.9 Hot-path allocations

Anonymous objects, strings, and serialization allocate.

Instrumentation should eventually be decoupled from the reflex path.

#### 22.10 Static singleton lifecycle

Domain Reload Off may leave stale logger singleton state.

#### 22.11 Scene assumptions

Do not assume required GameObjects are already in `Test_Arena`.

Inspect the scene.

#### 22.12 Starter Assets

The package may be partially imported and broken.

It should not be required.

---

### 23. Eight-week realistic plan

## Week 1 — Functional behavior test harness

Deliver:

- working FPS controller,
- basic room,
- one NPC,
- one ongoing NPC activity,
- soft FOV,
- turn-in-place,
- interruption,
- one placeholder reflex,
- basic logs.

Do not add LLM.

## Week 2 — Correct states and reaction variation

Deliver:

- explicit NPC state machine,
- reliable event-edge handling,
- cooldowns,
- second reaction,
- stable seed,
- no-repeat logic,
- visible onset instrumentation,
- simple reset flow.

## Week 3 — Basic tactical follow-up

Deliver:

- comply versus flee or remain threatened,
- one exit target,
- deterministic utility values,
- debug rationale,
- recovery and task-resumption logic.

## Week 4 — Structured memory or async dialogue

Preferred priority:

- structured memory first.

Implement:

- threat count,
- spared count,
- trust,
- fear,
- persistent values,
- future bias changes.

If ahead:

- async bark generation,
- cached subtitles,
- no live reflex dependency.

## Week 5 — Experiment harness

Deliver:

- named scenario presets,
- repeatable resets,
- fixed spawn positions,
- condition flags,
- automated or semi-automated repeated trials.

## Week 6 — Evaluation

Deliver:

- latency trials,
- profiler data,
- p50 and p95,
- condition comparison,
- recorded clips,
- optional small user study.

## Week 7 — Report

Deliver:

- 4–6 page technical report,
- architecture figure,
- state-machine figure,
- plots,
- methodology,
- limitations,
- README cleanup.

## Week 8 — Release

Deliver:

- external feedback,
- bug fixes,
- public release,
- short video,
- tagged version,
- optional Zenodo DOI,
- concise public project description.

---

### 24. Immediate five-day plan


## Day 1 — Audit and stabilize

- inspect project,
- inspect Console,
- verify packages,
- inspect current render pipeline,
- inspect Starter Assets,
- confirm controller code,
- confirm scene,
- make clean commit.

## Day 2 — Player controller

- create hierarchy,
- add CharacterController,
- attach controller,
- test movement and aim,
- fix cursor and gravity,
- commit.

## Day 3 — NPC activity

- create capsule NPC,
- create two patrol points,
- implement patrol,
- add basic state,
- verify repeatable movement,
- commit.

## Day 4 — Soft perception

- implement correct cone math,
- line of sight,
- real tick delta,
- suspicion,
- hysteresis,
- body turn,
- debug visualization,
- commit.

## Day 5 — Interruption and reflex

- create aim threat stimulus,
- interrupt patrol,
- trigger placeholder flinch,
- prevent repeated spam,
- instrument visible onset,
- run manual trials,
- commit.

This is ambitious. If behind, prioritize state correctness over polished dashboards.

---

### 25. Ideal final demo

A successful final demo should show:

1. NPC patrols between two points.
2. Player approaches from outside view.
3. NPC enters peripheral awareness.
4. NPC hesitates and rotates.
5. Player aims.
6. NPC stops patrol.
7. NPC visibly flinches immediately.
8. NPC chooses comply or flee.
9. Player disengages.
10. NPC recovers or resumes.
11. A later encounter changes because of memory.
12. Optional generated bark appears asynchronously.

The scene can remain greybox.

---

### 26. Ideal research artifacts

The project should produce:

- public GitHub repository,
- Unity demo,
- technical report,
- architecture diagram,
- state diagram,
- JSONL sample logs,
- analysis script or notebook,
- latency plots,
- short video,
- reproducibility instructions,
- honest limitations.

---

### 28. Hard non-goals

Do not implement unless explicitly requested:

- inventory,
- hunger,
- thirst,
- crafting,
- extraction economy,
- advanced weapon mechanics,
- reloads,
- ammo,
- full combat,
- multiplayer,
- networking,
- RL,
- LLM training,
- large behavior-tree frameworks,
- complex GOAP,
- production art,
- high-quality TTS,
- group AI,
- speech recognition,
- procedural worlds.

The project wins through:

- perception,
- interruption,
- responsiveness,
- layered control,
- observability,
- and evidence.

---

### 31. Final truth-first conclusion

This project is viable.

It will fail if it becomes a miniature extraction shooter.

It will succeed if it becomes a focused experimental system showing:

```text
ongoing behavior
→ perception under uncertainty
→ orientation
→ threat confirmation
→ interruption
→ immediate visible reflex
→ tactical recovery
→ optional asynchronous enrichment
```

The LLM is not needed to prove the first and most important contribution.

The local architecture must work first.

The most valuable project outcome is not a large game. It is a small, reproducible, well-instrumented demonstration that slow generative reasoning can coexist with fast real-time interaction without making the NPC feel unresponsive.
