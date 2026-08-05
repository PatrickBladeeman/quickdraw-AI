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

### 1A. Repair URP configuration — next recommended task

- Create or restore tracked URP renderer and pipeline assets.
- Assign valid assets in Graphics and each active Quality level.
- Open `Test_Arena.unity` and confirm there are no missing-pipeline errors or pink materials.
- Do not change gameplay scripts or scene behavior in this subtask.

Acceptance:

- Every configured render-pipeline GUID resolves to a tracked asset.
- `Test_Arena` opens cleanly in Unity 6000.0.57f1.

### 1B. Repair reproducibility settings

- Put `Test_Arena.unity` in Build Settings and remove the missing `Assets/Scenes/SampleScene.unity` entry.
- Confirm VSync is off, Incremental GC is on, and Active Input Handling supports the Input System.
- Configure Enter Play Mode with Domain Reload off and Scene Reload on.
- Reconcile `.gitignore` with `PROJECT_CONTEXT.md` so `Packages/packages-lock.json` and required reproducibility settings can be tracked intentionally.

Acceptance:

- A fresh checkout resolves the same packages and opens the correct scene.
- The documented editor settings are either tracked or explicitly documented as a required local step.

## 2. Implement the minimal player controller

Goal: move, look, and expose a trustworthy aiming state without Starter Assets.

Files:

- `Assets/_Project/Code/Core/SimpleFPSController.cs`
- `Assets/_Project/Scenes/Test_Arena.unity`

Steps:

- Replace the empty class with a `MonoBehaviour` using `CharacterController`.
- Read `Keyboard.current` and `Mouse.current` directly.
- Add WASD, mouse look, gravity, cursor lock, RMB aim, and smooth FOV change.
- Add optional sprint and jump only if they do not delay acceptance.
- Expose `public bool IsAiming { get; private set; }`.
- Create the `Player → CameraPivot → Main Camera` hierarchy and assign references.

Acceptance:

- Project compiles without Starter Assets.
- WASD and mouse look work.
- RMB changes FOV and `IsAiming` accurately follows input.
- Escape releases or toggles the cursor predictably.

## 3. Complete the minimal test arena

Goal: give each initial test a controlled spatial fixture.

Steps:

- Keep the existing floor and ceiling.
- Add four walls, one full-height divider, and one low block.
- Add player and NPC spawn markers.
- Add two patrol markers and one interaction marker.
- Add a `Systems` object for diagnostics and logging when those components are ready.
- Create an `NPC` layer.

Acceptance:

- The room supports direct, peripheral, and occluded sight lines.
- Every added object supports a named test; there is no decorative scope creep.

## 4. Add one ongoing NPC activity

Goal: establish meaningful behavior that can later be interrupted.

Recommended first activity: patrol between two markers. A simple inspect activity is also acceptable if it is easier to make deterministic.

Steps:

- Create one capsule NPC on the `NPC` layer.
- Implement explicit start, tick, interrupt, resume, and cancel behavior without a general AI framework.
- Track activity name, start time, current target/progress, and running state.
- Add reset behavior for repeatable manual tests.

Acceptance:

- The NPC performs the activity repeatedly and deterministically.
- Interrupt and resume can be invoked manually without leaving motion or state stuck.

## 5. Add structured aiming stimulus

Goal: expose aiming geometry without directly controlling NPC behavior.

Steps:

- Define a small `AimThreatStimulus` containing source identity, origin, direction, timestamp, maximum distance, and aiming state.
- Publish or expose the current stimulus from the player/camera.
- Do not call `ReflexSelector` from the controller or emitter.
- If isolated reflex testing needs a direct center-camera hit, protect it with a serialized `bypassPerceptionForDebug` flag that defaults to false.

Acceptance:

- Starting and ending RMB aim creates clear stimulus edges.
- With the debug bypass disabled, aiming alone cannot directly force a reflex.

## 6. Correct soft perception and orientation

Goal: turn the structured stimulus into gradual awareness and one-shot threat confirmation.

Files:

- `Assets/_Project/Code/AI/Perception/SoftFOVPerception.cs`

Steps:

- Represent explicit perception state or equivalent unambiguous state edges.
- Treat `coreFOV = 90°` and `peripheralFOV = 140°` as total widths.
- Check maximum distance, then angle, then line of sight.
- Tick near 12 Hz and use measured elapsed tick time for suspicion.
- Use enter/exit thresholds of 0.5 and 0.3.
- Turn the body near 300 degrees per second while orienting.
- Confirm only while the aiming stimulus remains valid and yaw difference is below approximately 3 degrees.
- Emit confirmation once per threat episode and require recovery before rearming.
- Add debug visualization for cones, line of sight, and current state if it can remain allocation-light.

Acceptance:

- Frontal stimulus confirms quickly.
- Peripheral stimulus builds suspicion and turns before confirming.
- An occluder prevents visual confirmation.
- Losing the stimulus decays or cancels awareness correctly.
- Holding aim does not generate repeated confirmations.

## 7. Interrupt activity and command one reflex

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
