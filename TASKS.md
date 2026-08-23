# quickdraw-AI — Ordered Execution Plan

## Authority

`CONTEXT.md` is the primary authority. `PROJECT_CONTEXT.md` is its tracked, sanitized backup of public project information and the tracked progress record. This file is the ordered implementation checklist derived from their synchronized public project scope. If an older task, code comment, or another document conflicts with `CONTEXT.md`, stop and reconcile the documentation before implementation.

The current objective is a small FPS AI behavior laboratory, not a survival or extraction game. Work on one numbered task at a time and verify it before continuing.

## Ground rules

- Keep gameplay implementation under `Assets/_Project/**` unless a task explicitly requires package or ProjectSettings changes.
- Preserve the existing `Test_Arena` deterministic fixture without adding inventory, weapons, shooting, damage, survival mechanics, networking, or LLM dependencies to that fixture. Named research scenes may add only the combat and model-integration mechanics explicitly required below.
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
- The complete Play Mode suite passes twenty-five tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 7. Interrupt activity and command one reflex — completed

Goal: make confirmed threat visibly interrupt the ongoing activity exactly once.

### 7A. One-shot activity interruption coordinator — completed

Files:

- `Assets/_Project/Code/AI/Behavior/NpcBehaviorController.cs`
- `Assets/_Project/Editor/NpcBehaviorControllerEditor.cs`

Steps:

- [x] Subscribe to the threat-confirmed edge without adding an activity dependency to perception.
- [x] Interrupt the current patrol activity synchronously.
- [x] Record activity name, reason, real-time timestamp, threat episode ID, and suspended/cancelled outcome.
- [x] Guard against duplicate delivery of the same confirmation.
- [x] Expose a post-interruption event for the reflex step.
- [x] Show the existing interruption count and metadata in a live, read-only custom Inspector.
- [x] Leave resume and recovery policy explicit and unimplemented.

Acceptance:

- [x] Patrol motion stops on confirmed threat.
- [x] A held threat or duplicate event causes one interruption.
- [x] A later rearmed episode can interrupt a deliberately resumed activity again.
- [x] Runtime interruption diagnostics are inspectable without making coordinator state editable or serialized.
- [x] Task 7A itself introduces no reflex, logging, recovery, networking, file I/O, or LLM dependency.

Verification:

- Three focused Play Mode tests verify scene/API isolation, interruption metadata and motion stop, duplicate suppression, and a later rearmed episode.
- The complete Play Mode suite passes twenty-five tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

### 7B. Command `Flinch_StepBack` — completed

Files:

- `Assets/_Project/Code/AI/Reflex/ReflexSelector.cs`
- `Assets/_Project/Code/AI/Behavior/NpcBehaviorController.cs`
- `Assets/_Project/Editor/ReflexSelectorEditor.cs`
- `Assets/_Project/Scenes/Test_Arena.unity`
- `Assets/_Project/Tests/PlayMode/ReflexSelectorAcceptanceTests.cs`

Steps:

- [x] Implement `Flinch_StepBack` as the first placeholder reaction.
- [x] Use collision-conscious rotation and `CharacterController.Move` displacement.
- [x] Add a serialized stable style seed and deterministic per-episode variation.
- [x] Command the reflex only from the coordinator's post-interruption path.
- [x] Guard against duplicate reflex dispatch for the same episode.
- [x] Emit `reflex_commanded`; do not claim this is visible onset.
- [x] Expose live command and collision diagnostics through a read-only custom Inspector.

Acceptance:

- [x] The already-interrupted patrol remains stopped before the reflex command.
- [x] The placeholder motion is obvious in the Game view.
- [x] A held threat causes one interruption and one reflex, not repeated steps.
- [x] A rearmed threat does not command another reflex unless activity was deliberately resumed and interrupted again.
- [x] Arena walls constrain the step-back displacement.
- [x] No coroutine delay, file I/O, networking, or LLM call occurs before the command.

Verification:

- Five focused `ReflexSelector` Play Mode tests verify the scene/API boundary, deterministic serialized style, interruption-before-command ordering, one-shot and paused-activity suppression, obvious displacement, and wall collision.
- Three coordinator tests also verify duplicate suppression and a later resumed/rearmed episode issuing a second interruption and reflex.
- The complete Play Mode suite passes thirty tests, and a Windows standalone player build succeeds in Unity `6000.0.57f1`.

## 8. Implement trustworthy structured telemetry — completed

Goal: measure the complete interaction pipeline, including actual visible onset.

### 8A. Observe actual visible onset — completed

Files:

- `Assets/_Project/Code/AI/Reflex/VisibleMotionObserver.cs`
- `Assets/_Project/Code/AI/Reflex/ReflexSelector.cs`
- `Assets/_Project/Editor/VisibleMotionObserverEditor.cs`
- `Assets/_Project/Scenes/Test_Arena.unity`
- `Assets/_Project/Tests/PlayMode/VisibleMotionObserverAcceptanceTests.cs`

Steps:

- [x] Capture the root position and rotation immediately before the reflex command changes them.
- [x] Arm observation from `reflex_commanded` without treating command dispatch as visible onset.
- [x] Detect the first root displacement of at least `0.01 m` or rotation of at least `1°` in `LateUpdate`.
- [x] Emit one `visible_motion_started` edge per threat episode with command-to-visible and confirmation-to-visible timings.
- [x] Expose live read-only onset diagnostics without adding logging or file I/O to the observer.

Acceptance:

- [x] `reflex_commanded` and `visible_motion_started` are separate one-shot events.
- [x] Sub-threshold changes do not count as visible motion.
- [x] Position-only and rotation-only placeholder motion can be observed.
- [x] Confirmed-threat → visible-motion latency is calculated from the observed edge.

Verification:

- Five focused Play Mode tests verify scene/API isolation, command/onset separation, threshold behavior, rotation-only observation, duplicate suppression, and later episodes.
- Before Task 8B, the complete Play Mode suite passed thirty-five tests.

### 8B. Record buffered typed JSONL telemetry — completed

Files:

- `Assets/_Project/Code/Logging/LogEvents.cs`
- `Assets/_Project/Code/Logging/JsonlLogger.cs`
- `Assets/_Project/Code/Logging/TelemetryRecorder.cs`
- `Assets/_Project/Editor/JsonlLoggerEditor.cs`
- `Assets/_Project/Scenes/Test_Arena.unity`
- `Assets/_Project/Tests/PlayMode/StructuredTelemetryAcceptanceTests.cs`

Steps:

- [x] Replace anonymous-object `JsonUtility` calls with explicit Newtonsoft-serialized event records.
- [x] Queue typed records in memory, then serialize and flush outside urgent dispatch.
- [x] Reset singleton/static state safely with Domain Reload off and use a session-unique JSONL path.
- [x] Observe stimulus, notice, suspicion threshold, turn, confirmation, interruption, reflex command, visible onset, threat release, and actual activity lifecycle edges.
- [x] Keep logging out of AI component dependencies; a scene-wired recorder owns event translation.
- [x] Calculate min, max, mean, p50, p95, and standard deviation for every sampled stage.
- [x] Contain serialization and disk-write failures without changing NPC behavior.

Acceptance:

- [x] JSONL records contain their intended fields rather than `{}`.
- [x] Event dispatch only enqueues typed records; serialization and file I/O occur later.
- [x] Command-to-visible and confirmed-threat-to-visible remain distinct latency samples.
- [x] A forced flush failure leaves buffered data available and does not block activity interruption or resume.
- [x] Task 8 records real threat-release and manual activity-resume edges without fabricating the Task 9 tactical recovery policy.

Verification:

- Six focused Play Mode tests verify the telemetry contract, populated valid JSON, deferred flushing, ordered end-to-end recording, descriptive statistics, Domain Reload safety, and write-failure containment.
- The complete Play Mode suite passes forty-one tests.
- A Windows standalone player build succeeds in Unity `6000.0.57f1`.

## Superseded future tasks

The former Tasks 9–13—a tactical-recovery FSM, completion of the old local slice, reaction-family variation, its original experiment harness, and optional dialogue/memory enrichment—were not implemented. They are superseded by the approved hierarchical deep-RL research program below. Tasks 1–8 and their verification remain valid and must be preserved.

## R0. Checkpoint the deterministic substrate — completed

Goal: establish a clean, independently reproducible Task 8 baseline before any research package, scene, combat, model, or LLM change.

Steps:

- [x] Re-run the complete 41-test Unity Play Mode suite against the current working tree.
- [x] Run the Windows standalone build in Unity `6000.0.57f1`.
- [x] Investigate and resolve only failures attributable to the existing Task 8 implementation.
- [x] Confirm `reflex_commanded` and `visible_motion_started` remain distinct and that telemetry file I/O remains outside urgent event handlers.
- [x] Confirm `CONTEXT.md` is ignored and `PROJECT_CONTEXT.md` contains the synchronized public research context.
- [x] Review the working tree and push Task 8 code, tests, scene wiring, and `.meta` files as an isolated Task 8 checkpoint series without adding research dependencies. The implementation is split across consecutive commits `ac1274e` and `b5532e1`.

Acceptance:

- [x] All 41 Play Mode tests pass from the checkpoint candidate.
- [x] The standalone Windows player builds successfully.
- [x] Task 8 telemetry remains populated, ordered, buffered, failure-tolerant, and Domain-Reload safe.
- [x] The latest commit after the checkpoint contains no ML-Agents, training environment, combat mechanic, or LLM integration.
- [x] The old tactical-recovery task remains unimplemented and is no longer the next task.

## R1. Establish research contracts and reproducible ML infrastructure

Goal: create a version-locked Unity/Python boundary and prove deterministic environment communication before implementing the full learned task.

Progress:

- [x] Add `com.unity.ml-agents` version `4.0.0`, compatible with Unity 6, and track the package-lock change.
- [x] Create a Python 3.10.12 environment specification with matching `mlagents`/`mlagents-envs`, PyTorch, numerical, plotting, and test dependencies pinned.
- [x] Record package versions, operating system, Unity version, Python version, CPU/GPU, driver, and trainer-plugin status in a machine-readable run-manifest schema/example.
- [x] Define stable episode, policy-training, opponent, and evaluation seeds. Never derive seeds from runtime object names or unstable hashes.
- [x] Define immutable observation, action, reward, terminal, truncation, and side-channel contracts.
- [x] Add a communicator/backend smoke environment before adding combat complexity.
- [x] Run a deterministic 10,000-step CPU reference trace and throughput measurement.
- [ ] Test an available supported AMD backend against the same trace. Accept it only if observations, actions, seeded returns, checkpoint reload, and exported inference agree within documented floating-point tolerance and measured steps per second improve; otherwise retain CPU.
- [x] Create an ignored project-local experiment-artifact root for raw JSONL, CSV, checkpoints, model files, and run manifests. Track schemas, scripts, and configurations, not large generated artifacts.

Acceptance:

- [x] A fresh documented Python environment connects to a standalone Unity environment and completes seeded reset/step/terminal cycles.
- [x] Repeating the same smoke seed produces the same initial observation, action legality, reward sequence, and terminal reason.
- [x] Package and environment versions are pinned rather than inferred from a developer machine.
- [ ] Backend selection is recorded as a measured decision, with CPU remaining the reference.
- [x] No learned model or LLM claim is made in this infrastructure task.

### R1A. Contract-and-dependency preflight — completed

Scope completed without installing a Unity package or adding runtime/gameplay code:

- [x] Verified from primary sources that Release 23 pairs `com.unity.ml-agents` `4.0.0` with `mlagents`/`mlagents-envs` `1.1.0` on Python 3.10.12.
- [x] Added and clean-installed the exact Windows CPU reference lock, including the reproducible bootstrap versions required by ML-Agents' `pkg_resources` import.
- [x] Added versioned machine-readable observation, action, reward, terminal, truncation, reset, seed, side-channel, and artifact contracts.
- [x] Added a Draft 2020-12 run-manifest schema plus a validated preflight example containing repository, software, hardware, backend, seed, contract-hash, and validation state.
- [x] Added and verified the ignored `Artifacts/Experiments/` root while keeping environment/config/schema sources tracked.
- [x] Confirmed the Unity package manifest/lock, scenes, gameplay, trainer, combat, and LLM code were untouched.

At its completion, R1A alone did not satisfy the Unity communicator, deterministic trace, throughput, or AMD parity acceptance gates. R1B subsequently satisfied only the communicator and repeatability gates documented below.

### R1B. Unity package and deterministic communicator smoke — completed

Scope completed without starting a research benchmark or trainer:

- [x] Installed and locked `com.unity.ml-agents` `4.0.0`; Unity resolved its declared `com.unity.ai.inference` `2.2.1` dependency without unrelated package changes.
- [x] Added an isolated `QuickDraw.Research.Environment` assembly, abstract seeded state machine, ML-Agents agent, strict custom side channel, and dedicated `Research_Smoke` scene.
- [x] Added a tracked smoke contract and Python 3.10.12 low-level API driver that validates behavior shapes, observations, action masks, actions, rewards, terminal/truncation semantics, side-channel ordering, contract hash, and run-manifest schema.
- [x] Completed two standalone runs with base seed `21001`; their canonical traces were structurally and numerically identical.
- [x] Completed one `smoke_goal` terminal episode and one `decision_limit` truncation with `interrupted=true` per run.
- [x] Passed five focused Edit Mode tests, all 41 existing Play Mode tests, the isolated smoke-player build, and the normal `Test_Arena` Windows build in Unity `6000.0.57f1`.
- [x] Kept all generated players, logs, traces, and run manifests under ignored `Artifacts/Experiments/`.
- [x] Added no `Research_Basic`, combat, trainer, replay, learned model, AMD acceleration, or LLM implementation and made no model-effectiveness claim.

R1B alone did not satisfy the 10,000-step CPU trace/throughput or AMD parity gates. R1C subsequently satisfied the CPU trace/throughput gate below; AMD parity remains separately approved work.

### R1C. Deterministic 10,000-decision CPU reference trace — completed

Scope completed by extending only the abstract communicator fixture:

- [x] Added a separate tracked CPU-reference contract with one base-seed-`21001`, 10,000-decision truncation; the original two-episode R1B smoke contract and default runner behavior remain unchanged.
- [x] Bounded accepted decision limits at 10,000 in both the pure episode state machine and coordinator validation, with a focused test proving decisions 1–9,999 remain active, decision 10,000 truncates, and 10,001 is rejected.
- [x] Timed only synchronous Python LLAPI action-to-Unity-step round trips with `time.perf_counter_ns`; player startup, exact trace comparison, and JSON serialization are excluded.
- [x] Completed two standalone CPU runs. Both contained exactly 10,000 transitions, ended with `decision_limit` and `interrupted=true`, and produced the same canonical trace SHA-256 `d5080b62ea3cc6c33a18567461f690a568339d2168f9d253ea3134b7c85572c5`.
- [x] Recorded 92.0502828 s / 108.636 decisions/s and 93.0801134 s / 107.434 decisions/s in schema-validated run manifests. These are communicator-transport measurements, not training or model-inference throughput.
- [x] Passed six focused Edit Mode tests, all 41 existing Play Mode tests, the isolated smoke-player build, the normal `Test_Arena` Windows build, and the unchanged R1B two-run exact-trace regression.
- [x] Kept generated players, logs, traces, and manifests ignored and added no AMD backend, `Research_Basic`, combat, trainer, replay, learned model, or LLM implementation.

R1C does not satisfy AMD/backend parity, checkpoint reload, model export, either learned benchmark, or any research-effectiveness gate. CPU remains the measured reference.

### R1D. AMD support exploration and parity-contract preflight — superseded

R1D investigated an exploratory Windows accelerator path and froze the later
all-or-nothing parity procedure without accepting a backend or modifying the CPU
reference. The current ROCm `7.14.0` matrix subsequently established exact RX
7900 XT / `gfx1100` / Windows 11 25H2 support. Revised R1E replaced the
exploratory candidate with ROCm, and the obsolete R1D executable probe, package
lock, contract, result schema, curated result, and focused tests were retired
during repository cleanup. The registered parity procedure was subsequently
executed by R1F.

### R1E. Python 3.11 / ROCm 7.14 / ML-Agents 1.1 compatibility — completed

Scope completed without training or executing the full AMD parity benchmark:

- [x] Registered the exact Windows 11 25H2, RX 7900 XT / `gfx1100`, Python 3.11.13, ROCm 7.14.0, PyTorch `2.12.0+rocm7.14.0`, and ML-Agents 1.1.0 target.
- [x] Proved why the published ML-Agents 1.1.0 metadata blocks Python 3.11: its Python upper bound is 3.10.12 and its `grpcio<=1.48.2` dependency has no CPython 3.11 Windows wheel.
- [x] Added a deterministic, metadata-only wheel overlay that retains every official ML-Agents runtime file byte-for-byte, widens the Python range only through 3.11, and uses the Release 23-compatible `grpcio==1.53.2` wheel. Official and overlay wheel hashes are frozen.
- [x] Disclosed and source-hashed the transitive `PettingZoo==1.15.0` Python-metadata exception without modifying its runtime source.
- [x] Added the isolated support lock, preparation pipeline, strict compatibility probe, Draft 2020-12 result schema, curated result, and six focused R1E tests.
- [x] Clean-installed two independent ignored Python 3.11.13 environments. Both had identical 71-distribution inventories and passed `pip check`, imports, and `mlagents-learn --help`.
- [x] Selected the exact RX 7900 XT as ROCm device 0 through ML-Agents and passed the fixed CPU-versus-ROCm float32 forward/backward probe: forward maximum absolute difference `4.76837158203125e-07`, both gradient differences `0.0`, all finite, registered tolerance `1e-5`.
- [x] Ran two Unity communicator traces from each independent environment. All four passed and shared canonical trace SHA-256 `5c5a5190f36e320a7bf05f85543681ba8f98e04aef1e71922d277f805ccf42b5`.
- [x] Recorded `conditional_go`, `backend_acceptance=not_accepted`, `cpu_reference_retained=true`, and `full_parity_executed=false`. No driver, Windows security, Unity runtime, or gameplay change was made.
- [x] Retired the superseded exploratory R1D files, removed stale cloud/manifest examples, removed the disposable reproduction environments after preserving their evidence, and retained the primary ROCm environment for R1F.

R1E did not establish training support, model-quality evidence, full correctness parity, or a ROCm throughput advantage; R1F evaluated the latter two claims separately.

### R1F. Fixed-policy CPU-versus-ROCm parity and throughput — completed

Scope completed without training or research-gameplay expansion:

- [x] Registered a distinct scenario seed (`21001`) and policy-initialization seed (`11001`), a real 1,000-decision warmup episode, and a separately timed 10,000-decision episode.
- [x] Generated one deterministic float32 4→32 ReLU policy with separate 3-logit and 2-logit heads, saved it once, independently reloaded it on CPU and ROCm, and exported it once to ONNX.
- [x] Ran the required alternating CPU-1, ROCm-1, CPU-2, ROCm-2 order in isolated Python 3.11.13 environments. Both environments passed `pip check`; ROCm selected the exact AMD Radeon RX 7900 XT.
- [x] Matched the registered R1C observation trace exactly and passed every action-mask, discrete-action, terminal/interrupted, seeded-return, checkpoint, finiteness, and ONNX action gate.
- [x] Recorded exact repeat logits on each backend. CPU-versus-ROCm and ONNX-versus-CPU maximum absolute differences were both `9.5367431640625e-07`, below the registered `1e-5` tolerance.
- [x] Recorded CPU throughput of 81.321 and 105.108 decisions/s (median 93.2145) and ROCm throughput of 96.430 and 100.213 decisions/s (median 98.3215), a ROCm/CPU median ratio of `1.0547876135150647`.
- [x] Applied the frozen no-partial-acceptance rule: every correctness gate passed and ROCm median throughput was strictly higher, so ROCm is accepted for this batch-size-one synchronous inference fixture.
- [x] Added the fixed-policy implementation, parity runner mode, evaluator, strict Draft 2020-12 result schema, curated result, reproducibility documentation, and four focused R1F tests. Generated checkpoint, ONNX, traces, manifests, environments, and diagnostic evidence remain ignored.

R1F does not prove training throughput, larger-model performance, learned-policy quality, `Research_Basic`, combat, or LLM behavior. R2A separately validates the environment contract below without using R1F as learned-policy evidence.

## R2. Implement the Unity Basic visual-control benchmark

Goal: create a small Unity hitscan analogue of the ViZDoom Basic Scenario that can validate visual Q-learning before strategic or LLM complexity.

### R2A. Deterministic environment-only slice — completed

- [x] Added an isolated long narrow primitive room with the capsule agent at the south end, a target in one of nine seeded north-end lateral slots, and a visible open-center reticle aligned to the only hitscan ray.
- [x] Implemented an actual uncompressed float32 HWC `[84,84,4]` sensor using Rec. 601 grayscale, oldest-to-newest stacking, and explicit post-reset four-channel fill with stale-stack failure containment.
- [x] Added stable semantic action enums, the shared typed action tuple, movement-before-shoot actuation, mechanically impossible boundary masks, 10 Hz decision gating, additive rewards, terminal hit, and 300-decision truncation.
- [x] Reset transforms, seeded target sampling, ammunition, cooldown, counters, cumulative reward, and visual state deterministically; fixed target sequences are locked in both C# and Python tests.
- [x] Added one common LLAPI runner for seeded random and visual-only scripted policies. Both export the same strict `quickdraw.basic-episode.v1` schema intended for later learned policies.
- [x] Passed the current 30 Edit Mode tests, all 41 existing Play Mode tests, seven Basic Python tests, the isolated Basic Windows build, and the normal `Test_Arena` Windows build.
- [x] Ran two fresh 12-episode standalone processes per policy. Random traces matched exactly, scripted traces matched exactly, and the scripted policy completed all 12 episodes with one aligned hit and no misses per episode.
- [x] Added a directional key light, lit high-contrast room materials, and a half-size unlit cyan reticle; froze those pixel-affecting values in the Basic contract and propagated its hash through R3A and R3B.
- [x] Recovered a deterministic episode and post-reset stack when the supported Domain-Reload-off workflow lets ML-Agents request an observation before its normal first reset; the focused regression reproduces the unprimed update path.

R2A contains no replay buffer, BDQ trainer, training run, learned weights, strategic combat expansion, or LLM runtime.

Scene and mechanics:

- Create a separate primitive-geometry research scene with a long narrow floor and enclosing walls.
- Spawn the capsule agent at the south end and one target at a seeded random lateral position near the north end.
- Give the agent one egocentric `84×84` grayscale camera observation with four-frame stacking.
- Use two concurrent discrete branches:
  - movement `[Stay, Left, Right]`;
  - combat `[Idle, Shoot]`.
- Use a fixed forward crosshair and one identical hitscan implementation. The learned policy moves laterally to align and never controls a mouse or privileged target snap in this benchmark.
- End the episode on a target hit or after 300 policy decisions.
- Apply reward `+1` for a hit, `-0.01` per decision, and `-0.02` for a missed shot.
- Reset agent transform, target position, ammunition, cooldowns, frame stack, counters, telemetry, and random state deterministically.
- Add random and scripted heuristic policies through the exact same action and actuator interfaces.

Acceptance:

- Observation shape, grayscale encoding, frame order, and stacking reset are stable and testable.
- Every one of the six joint action tuples produces the documented mechanical result.
- Fixed-seed target sequences and episode results repeat across resets and standalone runs.
- Invalid states, including a stale frame stack or an episode that continues after a hit, have focused tests.
- Random and scripted baselines export the same episode schema expected from learned policies.

## R3. Implement and validate Branching Double DQN

Goal: train a visual branched Q-policy with reproducible checkpoints and demonstrate that learning succeeds on Unity Basic.

### R3A. Pure-Python trainer foundation — completed

- [x] Added a strict `quickdraw.bdq-foundation.v1` contract and Draft 2020-12 schema bound to the exact R2A Basic contract hash and installed Python 3.11 / ML-Agents 1.1 / PyTorch CPU stack.
- [x] Added immutable validated replay transitions and a fixed-capacity seeded uniform ring buffer carrying observations, branch actions, rewards, next observations, current/next masks, terminal flags, and truncation flags.
- [x] Added the registered HWC-to-CHW three-convolution encoder, 512-unit representation, scalar value head, and mean-centered `[3,2]` advantage heads.
- [x] Added fail-closed branch masking, deterministic greedy/epsilon-greedy selection, and reversible row-major branch-to-six-joint-action mapping.
- [x] Added per-branch Double-DQN online selection/target evaluation, true-terminal masking, registered truncation bootstrapping, and mean Huber loss over batch and branches.
- [x] Passed 15 deterministic synthetic CPU tests covering contract/schema/runtime parity, the installed ML-Agents plugin seam, Unity action-name/index parity, replay validation/sampling, masks, exact network layers and shapes, gradients, hand-calculated targets, terminal/truncation behavior, loss reduction, and the full replay-to-backward composition.

R3A does not register a trainer entry point, launch Unity, collect experience,
run an optimizer or training loop, use ROCm, create checkpoints/exports, or make
a learned-policy claim.

### R3B. Registered trainer and deterministic optimizer smoke — completed

- [x] Added an installable `quickdraw-bdq-trainer` package with a real
  `mlagents.trainer_type` entry point, `QuickDrawBDQSettings`, and a
  factory-compatible `QuickDrawBDQTrainer`.
- [x] Kept policy creation, trajectory advancement, episode handling, model
  saving, and checkpoint loading fail-closed because Unity rollout is outside
  R3B.
- [x] Added seeded online/target initialization, Adam `1e-4`, replay warmup,
  one optimizer update every four decisions, and hard synchronization every
  10,000 optimizer updates with explicit decision/update/sync counters.
- [x] Preserved the exact production defaults while allowing smaller injectable
  scheduling values only for deterministic synthetic tests.
- [x] Passed 22 focused R3B CPU tests, all 37 trainer tests, and all 54 Python
  research tests. The proof covers
  official plugin discovery, settings structuring, `TrainerFactory`
  construction, exact initialization, no premature update, online-only weight
  change after optimization, a frozen target before its boundary, exact hard
  synchronization, a real batch-64 update, and tensor-for-tensor seeded replay.

Post-R3B repository and tooling checkpoint — completed:

- [x] Committed and pushed R3B plus the bounded R2A lighting/contrast,
  compact-reticle, missing-reset recovery, contract-hash, test, cleanup, and
  documentation maintenance as `500bc24` (`add optimizer implementation and
  unity cli`).
- [x] Installed Unity CLI `1.0.0-beta.5` as local tooling, registered and
  structurally verified Unity `6000.0.57f1`, and matched the legacy batch-mode
  result for one exact focused Edit Mode test: one selected, one passed, zero
  failed or skipped.
- [x] Kept the CLI outside the project dependency contract and left the
  experimental `com.unity.pipeline` package uninstalled. Treat raw Editor
  stderr as sensitive because it can include authentication command-line
  arguments.

R3B does not create an ML-Agents policy, consume Unity trajectories, run an
environment training session, execute ROCm, implement epsilon decay, save or
restore checkpoints, export ONNX, or claim learned-policy effectiveness.

### R3C. High-level trajectory experiment — superseded and removed

The local R3C experiment proved that ML-Agents' trainer controller could deliver
one terminal trajectory, but its `Trainer`/`Policy`/`Trajectory` lifecycle and
next-mask registry obscured the direct environment-step boundary. None of that
experimental scaffolding was committed. R3D removes
the trainer class, settings class, plugin entry point, trajectory adapter,
configuration YAML, runner, contracts, schemas, and focused trajectory tests.

### R3D. Direct LLAPI collection and truncation-mask transport — completed and pushed

- [x] Added strict `quickdraw.bdq-llapi.v1` and result schemas bound to the exact
  R2A, R3A, and R3B contracts plus the pinned Python 3.11 CPU runtime.
- [x] Replaced the registered ML-Agents trainer path with direct synchronous
  `UnityEnvironment` collection. One pending decision per agent is completed
  exactly once when that agent next appears in `DecisionSteps` or
  `TerminalSteps`.
- [x] Added exact behavior/observation/branch validation, mask-aware greedy
  online-network action selection, immutable replay completion, weight hashing,
  and strict failure on missing, duplicate, malformed, or unused masks.
- [x] Added a Unity-to-Python `quickdraw.basic-truncation-mask.v1` side channel.
  Immediately before decision-limit interruption, Unity supplies the final slot
  and authoritative current-state unavailable-action masks; Python never infers
  them from privileged scene state.
- [x] Preserved true-terminal non-bootstrapping and proved that the transported
  truncation mask controls Double-DQN online selection/target evaluation.
- [x] Removed the now-unneeded trainer, policy, trajectory, settings, plugin,
  YAML, next-mask registry, one-time runner, contracts, schemas, and tests.
  The package now has no `mlagents.trainer_type` entry point.
- [x] Passed all 39 focused trainer tests, all 56 Python research tests, 13
  focused Unity Basic episode tests, and the complete 31-test Edit Mode suite.
- [x] Built the saved Windows `Research_Basic` scene and ran two fresh direct
  Python/Unity processes. Each inserted exactly 302 transitions: a deterministic
  two-step greedy terminal episode and a 300-step truncation episode that moved
  to slot `-4` and delivered `[false,true,false]` as its final movement mask.
  Both traces were byte-identical; optimizer updates and target synchronizations
  remained zero, and online/target weight hashes did not change.

This direct-collection slice is committed and pushed as `a4b449d` (`R3D: llapi
implementation + truncation maski + pending decision`). It is not a training
session and makes no learned-policy claim.

### R3E. Seeded epsilon-greedy LLAPI collection below warmup — implemented and verified locally

- [x] Extended only the R3D direct collector with the registered starting
  epsilon `1.0`, fixed exploration seed `61001`, branch-wise uniform legal
  action sampling, and exactly 1,000 replay transitions across episode resets.
- [x] Remained below the 10,000-transition replay warmup so optimizer updates and
  target synchronizations both stay at zero and online/target hashes remain
  unchanged.
- [x] Required no unresolved pending decision at the cutoff and ran two fresh
  Python/player processes whose canonical traces are byte-identical.
- [x] Excluded epsilon decay, gradients, checkpointing, ROCm execution, ONNX,
  learned weights, effectiveness claims, and changes to the R2A environment.

The live gate completed 18 Unity episodes and crossed 18 reset boundaries per
process, exercised all six action tuples, handled one authoritative truncation
mask, and stopped after transition 1,000 with a completed nonterminal replay
transition and no pending action. All 47 trainer tests and all 64 Python
research tests pass. R3E is verified locally but is not committed or pushed.

Remaining trainer and network work:

- Use four stacked `84×84` grayscale frames.
- Shared encoder:
  - 32 filters, `8×8`, stride 4;
  - 64 filters, `4×4`, stride 2;
  - 64 filters, `3×3`, stride 1;
  - 512-unit shared representation.
- Use a scalar dueling value head and one mean-centered advantage head per action branch.
- Add epsilon-greedy Unity collection, checkpointing, resume, and inference
  export around the implemented replay, Double-DQN target, averaged branch
  Huber loss, and optimizer schedule. Add gradient clipping only if needed and
  documented.

Registered defaults:

- replay capacity 100,000;
- replay warmup 10,000 decisions;
- batch size 64;
- `gamma = 0.99`;
- Adam learning rate `1e-4`;
- optimizer update every four decisions;
- hard target synchronization every 10,000 optimizer updates;
- epsilon decay from `1.0` to `0.1`, followed by a `0.05` evaluation floor only during exploratory validation; final evaluation is greedy;
- five independent policy-training seeds.

Controls and diagnostics:

- Implement a joint-action Double DQN head for the Basic benchmark's six action tuples as a sanity comparison, not the primary final architecture.
- Record training return, success rate, learning-curve area, Huber loss, mean absolute TD error, epsilon, replay size, Q-value summaries, environment steps per second, inference time, checkpoint hash, and configuration hash.
- Unit-test branch-to-action mapping, Double-DQN target construction, terminal masking, replay sampling, target synchronization, checkpoint restore, and exported inference parity.

Acceptance:

- At least four of five BDQ training seeds reach at least 90% success over 500 held-out target-placement seeds.
- Each passing seed exceeds random-policy success by at least 30 percentage points.
- The BDQ-versus-joint-action result is reported even if BDQ performs worse; do not hide branch-factorization limitations.
- Every reported model is traceable to a seed, configuration, training curve, checkpoint, and hash.

### Deferred post-R3 scenario: gradual-motion Basic variant

Begin this scenario only after the canonical slot-based Basic benchmark satisfies
the R3 Q-learning acceptance gates. Do not change the implemented R2A contract
in place; retain it as the deterministic control environment.

- [ ] Keep the same discrete movement `[Stay, Left, Right]` and combat `[Idle, Shoot]` branches so continuous motion is not confused with a continuous action space.
- [ ] Replace one-slot teleportation only in the new variant with a held lateral movement intent integrated on every fixed physics step. `Left` and `Right` use the negative and positive agent-right axis; forward motion is outside this scenario.
- [ ] Freeze a separately versioned contract covering movement speed, fixed timestep, decision period, action persistence, continuous bounds, raycast alignment, reset behavior, and terminal/truncation semantics.
- [ ] Train and evaluate a separate checkpoint with the same accepted Q-learning architecture, then compare success, sample efficiency, return, and throughput against the canonical discrete benchmark.
- [ ] Label any zero-shot transfer of a slot-trained checkpoint into gradual motion as exploratory; do not treat it as a substitute for training and held-out evaluation under the new dynamics.

## R4. Implement the strategic combat benchmark and goal-conditioned policy

Goal: create a controlled combat decision problem with enough resource and positioning tradeoffs for reflex and strategic-director evaluation.

Shared mechanics:

- Use three concurrent action branches:
  - movement `[Stay, Forward, Backward, Left, Right]`;
  - combat `[Idle, Shoot]`;
  - utility `[Idle, Reload, Interact]`.
- Use 100 health, 20 hitscan damage, a six-round magazine, 18 reserve rounds, a 0.25-second shot cooldown, a 1.5-second reload, and a 30-second episode timeout.
- Add named cover, health/ammunition pickups, collision-aware movement, line of sight, and a bounded interaction radius.
- Add one seeded scripted opponent with deterministic spawn, movement, target selection, aim, fire schedule, and difficulty parameters.
- Emit a structured imminent-shot telegraph exactly 400 ms before each opponent shot.
- When `Shoot` is selected, use the same hardcoded nearest-visible-legal-target resolver, one-frame look-at/snap, and hitscan test in every research condition.
- Make mechanically impossible actions maskable; do not mask physically legal actions merely because they conflict with a strategy.

Goal conditioning:

- Add categorical goals `BALANCED`, `OFFENSIVE_RUSH`, `DEFENSIVE_RETREAT`, `SEEK_HEALTH`, and `CONSERVE_AMMO` at the BDQ shared representation.
- Use a deterministic teacher during training so every goal receives balanced scenario coverage.
- Use documented potential-based shaping for progress toward the active enemy, cover, health, or ammunition goal without replacing shared terminal and damage rewards.
- Randomize reflex availability during strategic training so one checkpoint per policy seed can be used unchanged across runtime ablations.
- Never use a live LLM during policy training.

Acceptance:

- All branches and goal categories have stable enum/index contracts and inference/export tests.
- Every condition uses identical visual input, goal encoding, action tuple, mechanics, and policy checkpoint for a given training seed.
- The scripted opponent and all environment randomization repeat from the scenario seed.
- Episode outcome, damage, shots, reloads, pickups, survival, directive occupancy, and terminal reason are recorded independently from training reward.
- A rule or scripted curriculum can demonstrate every goal-specific behavior before LLM integration.

## R5. Add and isolate the deterministic evade reflex

Goal: test whether a narrowly bounded urgent layer improves survival without depending on BDQ or LLM timing.

Steps:

- Implement `EvadeTelegraphedShot` as one collision-safe `0.6 m` lateral step with a one-second cooldown.
- Trigger only from the structured 400 ms imminent-shot event.
- Choose direction and clearance deterministically from shared actuator/physics data.
- Preempt only the movement portion of the currently held action tuple; do not change combat, utility, strategic goal, reward, or model state.
- Return movement control to the most recent BDQ intent after the bounded evade completes.
- Perform no wait, serialization, file I/O, network call, model inference, or LLM request before command dispatch.
- Record telegraph, reflex decision, command, requested/applied displacement, collision, visible onset, damage avoided, preemption duration, cooldown suppression, and control return.

Acceptance:

- Reflex-disabled and reflex-enabled conditions share all non-reflex code and configuration.
- A duplicate telegraph cannot cause duplicate evades.
- Walls constrain displacement and cannot be crossed by root teleportation.
- The reflex cannot aim or fire and receives no information unavailable to the shared actuator.
- Focused delay-injection tests demonstrate that LLM completion timing cannot enter the reflex call graph.

## R6. Scaffold the asynchronous local LLM strategic director

Goal: integrate a reproducible local model as a slow bounded goal selector without allowing it to control mechanics or urgent timing.

Runtime and model:

- Define a provider-neutral local HTTP interface and deterministic mock implementation.
- Use quantized Qwen3-8B in non-thinking/instruction mode through a pinned `llama.cpp` server, preferring a validated Vulkan backend on the AMD GPU.
- Record the exact server version/commit, model source, quantization, SHA-256, context, prompt template, schema, generation parameters, and hardware.
- Do not commit model weights.

State and output:

- Capture an immutable state snapshot every two seconds containing quantized health/ammunition; visible-enemy count, distance, and health categories; cover/pickup availability and distance categories; current directive; episode ID; sequence; and timestamp.
- Never send raw frames or continuous matrices to the LLM.
- Require schema-constrained JSON fields `strategic_intent`, `priority_target`, and `engagement_rule`.
- Accept only coherent templates for `BALANCED`, `OFFENSIVE_RUSH`, `DEFENSIVE_RETREAT`, `SEEK_HEALTH`, and `CONSERVE_AMMO`.
- Convert a valid template to the fixed categorical goal input. Never convert text directly into movement, aiming, shooting, reload, interaction, reward changes, or tactical action masks.

Concurrency and failure rules:

- Capture Unity state on the main thread.
- Perform HTTP, generation waiting, and parsing asynchronously without touching Unity objects.
- Publish results through a thread-safe queue and apply them on the main thread.
- Use a two-second request cadence, five-second timeout, four-second result TTL, monotonic sequence IDs, temperature zero, a recorded seed, and a small JSON-only output limit.
- Discard malformed, incoherent, stale, timed-out, and out-of-order results.
- Retain the latest valid directive; use `BALANCED` when no valid directive exists.
- Mock fixed responses, invalid JSON, connection loss, timeouts, out-of-order completions, and delays of `0`, `500`, `1000`, `2000`, and `3000 ms`.

Acceptance:

- Automated failures never pause physics, BDQ decisions, the shared actuator, or the reflex.
- Background work never accesses Unity objects.
- Every request/result transition and fallback is observable in telemetry.
- The same snapshot and pinned deterministic settings produce an auditable recorded output, while reproducibility claims acknowledge that model execution may not be bitwise identical across backends.
- Live-model effectiveness is not claimed until R7.

## R7. Run the registered factorial evaluation

Goal: measure causal contributions, timing isolation, and uncertainty with paired conditions.

Main 2×2 conditions:

1. BDQ with fixed `BALANCED` goal and reflex off.
2. BDQ + reflex with fixed `BALANCED` goal.
3. BDQ + LLM with reflex off.
4. BDQ + reflex + LLM.

Secondary controls:

- BDQ + deterministic rule director, reflex off.
- BDQ + deterministic rule director + reflex.
- The rule director receives the exact same abstract snapshot and emits the exact same directive schema as the LLM.

Run protocol:

- Evaluate each of five independently trained policy seeds on the same 100 held-out scenario seeds in every condition: 500 paired episodes per condition.
- Use the identical checkpoint for all conditions associated with a policy seed.
- Use greedy evaluation with no weight, replay, epsilon, reward, or optimizer updates.
- Predeclare exclusions for corrupted/incomplete runs based only on infrastructure validity, not performance.
- Use a 10,000-resample hierarchical bootstrap that resamples policy seed and then paired scenario seed.

Primary outcome:

```text
U = episode_outcome
  + 0.25 * (damage_dealt - damage_taken) / 100
  - 0.05 * missed_shot_fraction
  - 0.05 * wasted_resource_fraction
```

`episode_outcome` is `+1` for opponent elimination, `-1` for agent death, and `0` for timeout. Always report its components separately.

Registered decision criteria:

- H1: full hybrid minus BDQ-only utility is at least `0.10`, with paired 95% confidence interval above zero.
- H2: reflex conditions reduce damage per telegraphed shot, with paired 95% confidence interval below zero.
- H3: full-hybrid telegraph-to-visible-evade p95 is at most `50 ms` and no more than one `20 ms` physics step slower than BDQ+reflex at every injected LLM delay tier; use at least 200 reflex events per tier.
- H4: LLM factorial main effect is positive. A strong LLM claim additionally requires at least `0.05` utility improvement over the same-information rule director with paired 95% confidence interval above zero.

Required output:

- paired effect sizes, 95% confidence intervals, reflex/LLM main effects, interaction, and rule-director comparison;
- training and sample-efficiency metrics;
- utility and every raw combat component;
- BDQ inference, frame, fixed-step, reflex-command, visible-onset, and deadline metrics;
- LLM generation, validity, discard, timeout, fallback, and directive metrics;
- run, model, scene, configuration, seed, package, and hardware manifests.

Acceptance:

- All conditions pass the fairness and seed-pairing audit before analysis.
- No threshold or primary outcome is changed after viewing final results.
- Negative/null results and failed hypotheses are reported explicitly.
- If the LLM fails to beat the rule director, the report does not attribute a unique benefit to the LLM.

## R8. Curate the reproducible research artifact

Goal: make the experiment inspectable, rerunnable, and honest without committing large generated files.

Steps:

- Track environment/trainer/model-server configurations, dependency locks, schemas, analysis scripts, plotting code, curated aggregate tables, figures, checksums, and a limitations document.
- Keep raw JSONL/CSV, checkpoints, model weights, caches, and generated plots under the ignored artifact root until selected aggregates are curated.
- Document exact commands for environment creation, training, checkpoint evaluation, local-model launch, factorial runs, analysis, and figure regeneration.
- State which hypotheses were supported, rejected, or inconclusive and distinguish confirmatory from exploratory analysis.
- Report branch-factorization limitations, reward-shaping sensitivity, privileged scripted mechanics, model/backend reproducibility limits, and external validity beyond the two research scenes.
- Do not add a participant study to this prototype.

Acceptance:

- A fresh checkout can reconstruct the software environments and run smoke tests without untracked private instructions.
- Every published number and plot traces to a run manifest and analysis command.
- Model and dataset licenses permit the public research artifact.
- The public README remains a short project introduction; internal execution instructions stay in context, architecture, and task documents.

## Commit hygiene

- Commit Unity assets with their `.meta` files.
- Keep generated Unity and IDE files out of Git.
- Do not commit paid or unredistributable assets.
- Review `git status` before and after every task.
- Commit only after Unity compilation and the task’s acceptance test succeed.
