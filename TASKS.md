# quickdraw-AI — Ordered Execution Plan

## Authority

`CONTEXT.md` is the primary authority. `PROJECT_CONTEXT.md` is its tracked, sanitized backup of public project information and the tracked progress record. This file is the ordered implementation checklist derived from their synchronized public project scope. If an older task, code comment, or another document conflicts with `CONTEXT.md`, stop and reconcile the documentation before implementation.

The current objective is a small FPS AI behavior laboratory, not a survival or extraction game. Work on one numbered task at a time and verify it before continuing.

## Ground rules

- Keep gameplay implementation under `Assets/_Project/**` unless a task explicitly requires package or ProjectSettings changes.
- Do not add inventory, weapons, shooting, damage, survival mechanics, networking, or LLM integration during the local vertical slice.
- Do not place disk I/O, networking, waits, or serialization in the reflex dispatch path.
- Use `Time.realtimeSinceStartup` for pipeline event timestamps.
- Treat documented FOV values as total cone widths and compare against their half-angles.
- Use actual perception-tick elapsed time for suspicion gain and decay.
- Use event edges and episode identifiers to prevent repeated interruption and reflex spam.
- Keep internal dispatch timing separate from observed visible-motion timing.
- Use a serialized stable seed or profile identifier, never a runtime name hash.
- Let Unity compile and run the relevant manual acceptance test after each task.

## 0. Documentation alignment

- [x] Consolidate prior project notes into one authoritative local memory document.
- [x] Create `PROJECT_CONTEXT.md` as the tracked, sanitized backup and progress record, containing the complete public project requirements without personal or internal session information.
- [x] Define the prerequisite synchronization check between `CONTEXT.md` and `PROJECT_CONTEXT.md` for public project information.
- [x] Align `CONTEXT.md`, `PROJECT_CONTEXT.md`, `ARCH.md`, `TASKS.md`, and `README.md` with the downsized scope.
- [x] Remove the permanent direct-raycast path, false visible-latency definition, unstable seed guidance, and premature LLM/GOAP sequencing from current instructions.

Acceptance:

- The project documents describe the same canonical flow and task order.
- `CONTEXT.md` and `PROJECT_CONTEXT.md` agree on all public project scope, features, technical details, repository status, and progress.
- Any direct camera-hit confirmation is explicitly debug-only.
- The first local milestone ends with interruption, visible reflex, observed onset, and recovery.

## 1. Stabilize the Unity baseline

Goal: make the existing greybox a reliable place to begin implementation.

### 1A. Repair URP configuration — completed

- [x] Create or restore tracked URP renderer and pipeline assets.
- [x] Assign valid assets in Graphics and each active Quality level.
- [x] Open `Test_Arena.unity` and confirm there are no missing-pipeline errors or pink materials.
- [x] Do not change gameplay scripts or scene behavior in this subtask.

Acceptance:

- [x] Every configured render-pipeline GUID resolves to a tracked asset.
- [x] `Test_Arena` opens cleanly in Unity 6000.0.57f1.

### 1B. Repair reproducibility settings — completed

- [x] Put `Test_Arena.unity` in Build Settings and remove the missing `Assets/Scenes/SampleScene.unity` entry.
- [x] Confirm VSync is off, Incremental GC is on, and Active Input Handling supports the Input System.
- [x] Configure Enter Play Mode with Domain Reload off and Scene Reload on.
- [x] Reconcile `.gitignore` with `PROJECT_CONTEXT.md` so `Packages/packages-lock.json` and required reproducibility settings can be tracked intentionally.

Acceptance:

- [x] A fresh checkout resolves the same packages and opens the correct scene.
- [x] The documented editor settings are tracked.

## 2. Implement the minimal player controller — completed

Goal: move, look, and expose a trustworthy aiming state without Starter Assets.

Files:

- `Assets/_Project/Code/Core/SimpleFPSController.cs`
- `Assets/_Project/Scenes/Test_Arena.unity`

Steps:

- [x] Replace the empty class with a `MonoBehaviour` using `CharacterController`.
- [x] Read `Keyboard.current` and `Mouse.current` directly.
- [x] Add WASD, mouse look, gravity, cursor lock, RMB aim, and smooth FOV change.
- [x] Add optional sprint and jump only if they do not delay acceptance.
- [x] Expose `public bool IsAiming { get; private set; }`.
- [x] Create the `Player → CameraPivot → Main Camera` hierarchy and assign references.

Acceptance:

- [x] Project compiles without Starter Assets.
- [x] WASD and mouse look work.
- [x] RMB changes FOV and `IsAiming` accurately follows input.
- [x] Escape releases or toggles the cursor predictably.

Verification:

- Four focused Unity Play Mode tests pass for the component/API contract, configured scene hierarchy, movement/look/sprint/jump/aim/FOV/cursor behavior, full unobstructed jump height, and immediate recovery from overhead collision.
- A Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 3. Complete the minimal test arena — completed

Goal: give each initial test a controlled spatial fixture.

Steps:

- [x] Keep the existing floor and use an open-top arena for clear lighting and playtest visibility.
- [x] Add four walls, one full-height divider, and one low block.
- [x] Add player and NPC spawn markers.
- [x] Add two patrol markers and one interaction marker.
- [x] Add a `Systems` object for diagnostics and logging when those components are ready.
- [x] Create an `NPC` layer.

Acceptance:

- [x] The room supports direct, peripheral, and occluded sight lines.
- [x] Every added object supports a named test; there is no decorative scope creep.

Verification:

- Two focused arena Play Mode tests verify the 16-by-16-unit open-top fixture, exact hierarchy, collision fixtures, shared valid material, marker-only transforms, empty `Systems` container, enclosing walls, and direct/peripheral/occluded sightlines.
- The complete Play Mode suite passes ten tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 4. Add one ongoing NPC activity — completed

Goal: establish meaningful behavior that can later be interrupted.

Recommended first activity: patrol between two markers. A simple inspect activity is also acceptable if it is easier to make deterministic.

Steps:

- [x] Create one capsule NPC on the `NPC` layer.
- [x] Implement explicit start, tick, interrupt, resume, and cancel behavior without a general AI framework.
- [x] Track activity name, start time, current target/progress, and running state.
- [x] Add reset behavior for repeatable manual tests.

Acceptance:

- [x] The NPC performs the activity repeatedly and deterministically.
- [x] Interrupt and resume can be invoked manually without leaving motion or state stuck.

Verification:

- Four focused Play Mode tests verify the configured capsule NPC, collision-aware wall blocking, deterministic repeated patrol, observable activity state, and consistent interrupt/resume/cancel/reset transitions.
- The complete Play Mode suite passes ten tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 5. Add structured aiming stimulus — complete

Goal: expose aiming geometry without directly controlling NPC behavior.

Steps:

- [x] Define a small `AimThreatStimulus` containing source identity, origin, direction, timestamp, maximum distance, and aiming state.
- [x] Publish the current camera-backed stimulus and explicit aim-start/aim-end edges from the player.
- [x] Keep the controller and emitter independent from `ReflexSelector` and NPC behavior.
- [x] Omit the optional direct center-camera debug bypass because isolated reflex testing does not need it at this stage.

Acceptance:

- [x] Starting and ending RMB aim creates clear stimulus edges.
- [x] Aiming alone cannot directly force a reflex.

Verification:

- Two focused Play Mode tests verify the six-field stimulus contract, camera-derived snapshots, serialized player wiring, single RMB start/end edges, and the absence of direct NPC/reflex effects.
- The complete Play Mode suite passes twelve tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 6. Correct soft perception and orientation — complete

Goal: turn the structured stimulus into gradual awareness and one-shot threat confirmation.

Files:

- `Assets/_Project/Code/AI/Perception/SoftFOVPerception.cs`

Steps:

- [x] Represent explicit perception state and unambiguous state edges.
- [x] Treat `coreFOV = 90°` and `peripheralFOV = 140°` as total widths.
- [x] Check maximum distance, then angle, then line of sight.
- [x] Tick near 12 Hz and use measured elapsed tick time for suspicion.
- [x] Use enter/exit thresholds of 0.5 and 0.3.
- [x] Turn the body near 300 degrees per second while orienting.
- [x] Confirm only while the aiming stimulus remains valid and yaw difference is below approximately 3 degrees.
- [x] Emit confirmation once per threat episode and require recovery before rearming.
- [x] Continue tracking a renewed valid aim during an unrearmed confirmed episode without emitting another confirmation.
- [x] Add allocation-light debug visualization for cones, line of sight, current state, eye position, and facing direction; expose state colors directly in the Game view through renderer-local capsule and facing-marker colors, with the supplemental gizmo sphere above the NPC bounds.

Acceptance:

- [x] Frontal stimulus confirms quickly.
- [x] Peripheral stimulus builds suspicion and turns before confirming.
- [x] An occluder prevents visual confirmation.
- [x] Losing the stimulus decays or cancels awareness correctly.
- [x] Holding aim does not generate repeated confirmations.

Verification:

- Ten focused Play Mode tests verify scene wiring, frontal and peripheral perception, measured suspicion timing, 300-degree-per-second orientation, distance and total-FOV half-angle rejection, occlusion, release/recovery/rearm, renewed-aim tracking without duplicate confirmation, invalid-aim tracking rejection, held-aim one-shot behavior, real-frame scheduling, state-gizmo clearance, and runtime state colors on both NPC renderers.
- The complete Play Mode suite passes twenty-two tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 7. Interrupt activity and command one reflex — next recommended task

Goal: make confirmed threat visibly interrupt the ongoing activity exactly once.

Files:

- `Assets/_Project/Code/AI/Reflex/ReflexSelector.cs`
- A small behavior coordinator or equivalent explicit state owner.

Steps:

- On the threat-confirmed edge, interrupt the current activity first.
- Record activity, reason, timestamp, and suspended/cancelled outcome.
- Implement `Flinch_StepBack` as the first placeholder reaction.
- Use collision-conscious rotation/displacement where practical; label any raw transform delta as temporary.
- Add a serialized stable style seed.
- Guard against duplicate dispatch for the same episode.
- Emit `reflex_commanded`; do not claim this is visible onset.

Acceptance:

- Patrol or inspect motion stops before the reflex command.
- The placeholder motion is obvious in the Game view.
- A held threat causes one interruption and one reflex, not repeated steps.
- No coroutine delay, file I/O, networking, or LLM call occurs before the command.

## 8. Implement trustworthy structured telemetry

Goal: measure the complete interaction pipeline, including actual visible onset.

Files:

- `Assets/_Project/Code/Logging/JsonlLogger.cs`
- Explicit log DTOs or equivalent event records.
- A visible-onset observer associated with the placeholder reaction.

Steps:

- Replace anonymous-object `JsonUtility` calls with explicit DTOs, Newtonsoft JSON, or a custom writer.
- Queue events in memory and flush outside urgent dispatch.
- Reset singleton/static state safely with Domain Reload off.
- Emit stimulus, notice, suspicion threshold, turn, confirmation, interruption, reflex command, visible onset, recovery, and resume events.
- Detect visible onset from a measured transform, bone, rig, or Animator signal.
- Calculate stage-specific descriptive statistics.

Acceptance:

- JSONL records contain their intended fields rather than `{}`.
- `reflex_commanded` and `visible_motion_started` are separate events.
- Confirmed-threat → visible-motion latency is calculated from observed events.
- Logging failure cannot block or break NPC behavior.

## 9. Add simple tactical recovery

Goal: complete the local interaction loop after the reflex.

Steps:

- Use a finite-state machine for `RemainThreatened`, one follow-up such as `Comply` or `FleeToMarker`, `Recover`, and `ResumeActivity`.
- Keep the NPC threatened while the aiming stimulus remains active.
- Define a stable threat-release and recovery delay condition.
- Resume or abandon the interrupted activity deliberately; do not restart it every frame.
- Emit state-change and resume/cancel events.

Acceptance:

- The NPC does not resume while the player remains aimed at it.
- Releasing the threat leads to one deterministic recovery outcome.
- The activity resumes or remains cancelled according to explicit state.

## 10. Validate the first local vertical slice

Run repeatable manual scenarios:

1. Direct frontal threat.
2. Peripheral notice and orientation.
3. Occluded player with no visual response.
4. Patrol or inspect activity interrupted once.
5. Threat release followed by recovery or resume.

Collect at least 20–30 confirmed-threat trials after visible-onset telemetry is trustworthy.

Acceptance:

- Confirmed-threat → visible-motion p50 is under 150 ms and p95 is under 250 ms.
- Peripheral suspicion and orientation are reported separately.
- Profiler inspection shows reflex selection/command is substantially under 1 ms and performs no file I/O or network work.
- Resetting the scenario produces comparable starting conditions.

## 11. Reaction variation

Only after the local vertical slice passes:

- Add `RaiseHands_High` when a suitable animation or rig exists.
- Add cooldown and no-repeat behavior across reaction families.
- Add stable per-NPC personality values or profile assets.
- Add environment constraints such as walls behind the NPC.
- Demonstrate divergence between two NPCs.

## 12. Experiment harness and evaluation

After behavior is stable:

- Add named scenario presets and repeatable resets.
- Export stage-specific summaries and plots.
- Compare direct, peripheral, and occluded conditions.
- Record standalone Windows-build results in addition to Editor measurements.
- Add an optional 30 FPS versus 60 FPS comparison or small user study only if time permits.

## 13. Later optional work

Prioritize structured memory before live generative features:

- threat/spared counts, trust, and fear;
- future local bias changes;
- cached asynchronous bark generation;
- structured encounter summaries;
- optional slow tactical weight nudges.

An LLM worker must remain optional, asynchronous, and irrelevant to the current reflex latency distribution.

## Commit hygiene

- Commit Unity assets with their `.meta` files.
- Keep generated Unity and IDE files out of Git.
- Do not commit paid or unredistributable assets.
- Review `git status` before and after every task.
- Commit only after Unity compilation and the task’s acceptance test succeed.
