# quickdraw-AI — Architecture and Code Contracts

## Authority and status

`CONTEXT.md` is the primary authoritative memory and requirements document. `PROJECT_CONTEXT.md` is its tracked, sanitized backup of public project information and the tracked progress record. This file translates their synchronized public project context into current architecture and code boundaries. It distinguishes the implemented deterministic `Test_Arena`, R1B/R1C communicator smoke, and R2A Basic environment from the still-unimplemented trainer, learned-policy, strategic-combat, and LLM architecture; planned contracts must not be described as existing runtime behavior.

## System overview

```text
Test_Arena (implemented deterministic regression fixture)
  Player.IsAiming
    → structured aim-threat stimulus
    → soft perception and one-shot threat confirmation
    → synchronous activity interruption
    → deterministic Flinch_StepBack command
    → observed visible-motion onset
    → buffered typed telemetry

Research_Basic (implemented R2A environment benchmark)
  84×84 grayscale frame stack
    → random/scripted baseline policy (BDQ planned)
    → [lateral movement, shoot] action tuple
    → shared fixed-forward hitscan actuator
    → seeded reward/episode result

Research_Strategic (planned factorial benchmark)
  egocentric frame stack + categorical strategic goal
    → goal-conditioned BDQ at 10 Hz
    → shared action tuple held by the 50 Hz actuator
    → optional event-driven evade reflex
    → optional asynchronous local-LLM goal update at 0.5 Hz
    → typed episode, timing, model, and system telemetry
```

The default `Test_Arena` flow never maps a camera hit directly to a reflex. An explicit debug-only bypass may confirm a threat for isolated regression testing, but it is disabled in evaluation. The research actuator may use internal target geometry for the controlled aiming mechanic only because the exact same actuator and data are supplied to every condition.

## Modules and dependency direction

- `QuickDraw.Core` — player controller and development overlay.
- `QuickDraw.AI.Stimuli` — structured aiming stimulus or emitter.
- `QuickDraw.AI.Perception` — soft FOV, suspicion, visibility, and orientation.
- `QuickDraw.AI.Activity` — the current interruptible NPC activity.
- `QuickDraw.AI.Reflex` — reaction selection and immediate motion command.
- `QuickDraw.AI.Behavior` — explicit high-level state and recovery coordination.
- `QuickDraw.Logging` — structured event buffering, serialization, and summaries.
- `QuickDraw.Research.Environment` — the isolated R1B/R1C communicator-smoke protocol and state machine.
- `QuickDraw.Research.Actuation` — stable semantic action enums and the typed multi-branch action tuple.
- `QuickDraw.Research.Basic` — R2A visual sensor, deterministic episode state, Basic actuator, target, and ML-Agents lifecycle.
- `QuickDraw.Research.Policy` (planned) — BDQ inference boundary and policy metadata; training remains in the pinned Python plugin.
- `QuickDraw.Research.Reflex` (planned) — the optional imminent-shot evade preemption.
- `QuickDraw.Research.Strategy` (planned) — strategic snapshots, directive validation, rule director, mock director, and local-LLM client.
- `QuickDraw.Research.Telemetry` (planned) — research episode records and run manifests, building on the buffered logging pattern.

Dependency rules:

- Core does not know about individual NPCs.
- Stimuli describe the player state; they do not select reactions.
- Perception confirms threats but does not implement activities or tactical recovery.
- The behavior coordinator owns interruption and state edges.
- Reflex never calls logging file I/O, networking, tactical planning, or an LLM.
- Existing deterministic AI components remain independent of the research scenes and ML dependencies.
- The environment owns seed/reset/reward/terminal truth; the policy cannot modify those contracts.
- The policy outputs a typed action intent and never presses keyboard/mouse controls.
- The shared actuator is the only research component that translates intents into mechanics.
- The reflex may preempt only movement for its bounded duration and never invokes policy, logging, networking, or LLM code before motion.
- Strategy publishes validated future-facing categorical goals; it cannot call actuators or change rewards/action legality.
- The local-LLM transport never touches Unity objects off the main thread.
- Telemetry observes gameplay/model events without becoming a dependency of urgent control code.

R1B and R2A assembly boundaries now isolate the communicator environment, stable action tuple, Basic runtime, and research Edit Mode tests. Add policy, reflex, strategy, and research-telemetry assemblies only with their approved tasks. Do not retrofit the completed `Test_Arena` components merely to satisfy a speculative abstraction.

## Implemented `Test_Arena` component contracts

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

`NpcBehaviorController` is the current narrow coordinator. It subscribes to `SoftFOVPerception.ThreatConfirmed`, suspends `PatrolActivity` synchronously, records the interruption metadata and outcome in observable properties, and emits `ActivityInterrupted` only after patrol has stopped. It then commands `ReflexSelector` only when the activity remains stopped. The `(episode ID, confirmation timestamp)` pair guards duplicate interruption delivery while the selector independently guards duplicate reflex commands by episode ID. The coordinator does not write telemetry, choose recovery, or resume the activity.

`NpcBehaviorControllerEditor` is an editor-only diagnostic surface for those existing properties. It preserves the normal serialized-reference controls, presents interruption count and metadata as read-only runtime values, and repaints during Play Mode without duplicating or serializing coordinator state.

Historical recovery sketch (not implemented):

```text
Activity
→ ThreatConfirmed
→ Reflex
→ RemainThreatened or Comply or FleeToMarker
→ Recover
→ ResumeActivity or Idle
```

No recovery state machine is implemented, and the superseded automatic-recovery task must not be added to `Test_Arena`. The current coordinator remains narrowly responsible for one-shot interruption and reflex sequencing.

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

The implemented Task 7B selector replaces the original scaffold's name hashing, raw transform displacement, deferred hands-up animation, and direct logger dependency. `NPC_01` uses serialized seed `1001`, a `0.35 ± 0.05 m` step, and a deterministic yaw offset within `±30°`. It rotates on the horizontal plane and uses the existing `CharacterController.Move` path so arena colliders constrain displacement. Read-only command metadata and an editor-only live Inspector make command count, episode, timing, requested/applied movement, yaw, collision flags, and the pre-command root pose observable. `ReflexCommanded` remains a command event only.

### Visible-onset observer

Purpose: identify when the commanded reaction becomes visibly measurable.

Acceptable signals include:

- root position or rotation exceeds a defined threshold;
- a tracked bone rotates beyond a threshold;
- a rig weight crosses a threshold;
- the Animator enters the target state and advances;
- an animation event explicitly marks first motion.

The implemented `VisibleMotionObserver` stores the selector's pre-command root pose when `reflex_commanded` fires, then checks the actual root pose in `LateUpdate`. A position delta of at least `0.01 m` or rotation delta of at least `1°` emits `visible_motion_started` once for that threat episode. The event reports which root signal crossed threshold plus command-to-visible and confirmed-threat-to-visible timing. The observer has no logging, serialization, or file dependency; a live read-only custom Inspector exposes its measured state.

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

The implemented Task 8B pipeline uses explicit Newtonsoft-serialized records in `LogEvents.cs`. A scene-wired `TelemetryRecorder` observes the existing emitter, perception, behavior, reflex, visible-onset, and patrol lifecycle events without adding a `QuickDraw.Logging` dependency to those gameplay components. Event handlers only construct and enqueue typed records. `JsonlLogger.Update` performs bounded serialization and periodic UTF-8 JSONL flushing, while quit handling drains the queue, appends per-stage summaries, and flushes once more.

`JsonlLogger` resets its singleton through `SubsystemRegistration`, uses a session-unique path under `Application.persistentDataPath`, retains buffered lines after a failed write, and catches serialization or file exceptions so behavior continues. Its summaries contain count, min, max, mean, p50, p95, and population standard deviation. A read-only custom Inspector exposes the session path, queue/buffer counts, written and dropped records, failed flushes, and the last error.

Task 8 records the perception `Recovering` edge as `threat_released` and records a real manual `activity_resumed` edge when it occurs. The former Task 9 tactical-recovery state machine was not implemented and is superseded by the research roadmap. Do not fabricate it in historical telemetry or make it a dependency of the research scenes.

## Research contracts

R1A freezes the machine-readable contract in `Research/configs/research-contracts-v1.json`. R2A now implements the Basic environment portion; the BDQ trainer and strategic environment remain planned until their corresponding `TASKS.md` work is separately accepted. A breaking contract change requires a new major contract version; implementations must not silently diverge from the tracked contract.

### Implemented R1B/R1C communicator boundary

`Research_Smoke` is an isolated, abstract ML-Agents transport fixture. It contains one `ResearchSmokeAgent`, one `ResearchSmokeCoordinator`, a four-float vector observation, discrete branches `[3, 2]`, and the frozen custom side-channel UUID. It deliberately contains no visual sensor, player/NPC component, combat mechanic, trainer, model, reflex, or LLM integration.

The coordinator accepts one ordered run configuration and ordered per-episode configurations, rejects wrong schema/hash/run/sequence data, and reports `run_ready`, `episode_started`, `episode_ended`, or `infrastructure_error`. The state machine owns its explicit seed, mechanically legal action masks, additive smoke rewards, `smoke_goal` terminal, and `decision_limit` truncation. `EndEpisode` and `EpisodeInterrupted` preserve terminal versus truncation semantics across the ML-Agents low-level API.

`Research/smoke/run_smoke.py` launches the standalone player, verifies behavior specifications, records complete canonical transition/side-channel traces, validates run manifests, and compares a second same-seed trace exactly. Its default R1B mode drives one terminal and one truncated smoke episode. Its dedicated R1C CPU-reference mode drives one 10,000-decision truncation and times the synchronous low-level-API decision loop with `time.perf_counter_ns`, including scripted action selection and in-memory transition capture; process startup, trace comparison, and JSON serialization are excluded. The two R1C base-seed-`21001` traces were byte-identical, while their separately recorded rates were 108.636 and 107.434 decisions/s. This is CPU communicator-transport throughput, not training throughput, model-inference throughput, sample-efficiency evidence, or support for the research hypotheses.

### Implemented R1E backend-compatibility boundary

The current AMD ROCm `7.14.0` matrix explicitly lists the exact RX 7900 XT / `gfx1100` / Windows 11 25H2 combination. The earlier exploratory DirectML lane was retired after this support correction; it is not an active candidate, dependency, schema, probe, or manifest option. `Research/environment/requirements-lock.txt` remains the untouched CPU reference, and the registered future parity procedure compares that reference only with ROCm.

R1E adds a separate ignored Python 3.11.13 environment for ROCm 7.14.0 and PyTorch `2.12.0+rocm7.14.0`. ML-Agents 1.1.0's official runtime files are retained byte-for-byte; a deterministic wheel overlay changes only the published Python upper bound and the `grpcio` maximum to the Release 23-compatible 1.53.2. The overlay, the transitive PettingZoo metadata exception, all source hashes, and the fact that no runtime code changed are explicit contract data.

Two independently constructed environments passed dependency, import, CLI, exact-device, and CPU-versus-ROCm forward/backward gates. Two Unity communicator runs in each environment produced the same canonical trace SHA-256 `5c5a5190f36e320a7bf05f85543681ba8f98e04aef1e71922d277f805ccf42b5`. The tensor forward maximum absolute difference was `4.76837158203125e-07`, with zero input- and weight-gradient differences. R1E recorded `conditional_go` and retained CPU pending the separately frozen checkpoint, export, trace, return, tolerance, and throughput gates. R1F later passed all of those registered fixed-policy gates and accepted ROCm only for that batch-size-one inference fixture.

### Implemented R2A Basic environment boundary

`Research_Basic` is isolated from `Test_Arena` and `Research_Smoke`. `ResearchBasicAgent` owns ML-Agents lifecycle and maps the two discrete branches into the stable `ResearchActionTuple`. `ResearchBasicActuator` is the only mechanical path: it applies one lateral slot movement per 10 Hz decision and then, for `Shoot`, casts the same fixed camera-center ray indicated by the visible open-center reticle. Held actions on the intervening 50 Hz physics steps do not repeat movement, shooting, rewards, or the decision counter.

`ResearchBasicEpisode` is a Unity-independent deterministic state machine. It owns the explicit scenario seed and zero-based episode index, nine-slot target sampler, position, ammunition, cooldown, counters, additive reward, `target_hit` terminal, and `decision_limit` truncation. It fails closed if decision ordering, semantic actions, physical hitscan results, or post-end continuation disagree with the contract.

The slot-based R2A dynamics remain the canonical control benchmark through R3. A separate gradual-motion Basic variant is deferred until the Q-learning acceptance gates pass. That variant may retain the same discrete `[Stay, Left, Right]` branch while holding the selected lateral intent across fixed physics steps, but it requires a separately versioned contract and separately trained/evaluated checkpoint; it must not silently alter R2A or be described as a continuous action space.

`ResearchBasicVisualSensor` sends one uncompressed float32 HWC `[84,84,4]` observation. Each frame is converted with Rec. 601 luma and channels are ordered oldest to newest. Sensor reset invalidates the stack; `OnEpisodeBegin` resets physical state, synchronizes transforms, captures one post-reset frame, and copies it into all four channels before the first decision. The standalone runner verifies this fill on every episode.

`Research/basic/run_basic_baseline.py` drives seeded random and visual-only scripted policies through the same LLAPI `ActionTuple` path. It hashes every observation, records action masks/actions/rewards/ends, validates the common `quickdraw.basic-episode.v1` schema, and compares complete traces across fresh processes. These baselines test the environment and export boundary; they are not training or learned-policy evidence.

### Shared clocks and decision cadence

- Unity physics and the shared actuator run with a `0.02 s` fixed timestep, or 50 Hz.
- BDQ requests a new action once every five physics steps, or 10 Hz.
- The actuator holds the last accepted action tuple between BDQ decisions.
- A reflex may preempt the movement branch by the next physics step and returns control to the held BDQ movement intent when the bounded evade ends.
- The strategic director captures at most one snapshot every two seconds, or 0.5 Hz.
- Gameplay and cross-stage timestamps use `Time.realtimeSinceStartup`; training-step and episode counters are also recorded so wall-clock and simulation time are not conflated.

### Visual observation contract

The primary policy observation is one egocentric `84×84` grayscale image with four-frame stacking. All conditions associated with a benchmark use the same camera transform, projection, render settings, preprocessing, channel order, normalization, frame cadence, and reset behavior.

Rules:

- Clear and refill the entire four-frame stack at episode reset; no previous episode frame may leak into a new episode.
- Record observation dimensions, grayscale conversion, stack order, and preprocessing version in the run manifest.
- The Basic policy receives only the visual stack.
- The strategic policy receives the same visual stack plus one validated categorical strategic-goal encoding.
- The LLM never receives these frames. Its compact snapshot is a separate experimental intervention.
- Debug sensors, labels, scene geometry, object IDs, or target coordinates may not be appended to the learned policy observation unless every condition receives them and the protocol is amended before final training.

### Action tuple

Use explicit stable enums and a typed value rather than raw magic indices:

```csharp
public enum MovementIntent
{
    Stay = 0,
    Forward = 1,
    Backward = 2,
    Left = 3,
    Right = 4
}

public enum CombatIntent
{
    Idle = 0,
    Shoot = 1
}

public enum UtilityIntent
{
    Idle = 0,
    Reload = 1,
    Interact = 2
}

public readonly struct ResearchActionTuple
{
    public MovementIntent Movement { get; }
    public CombatIntent Combat { get; }
    public UtilityIntent Utility { get; }
    public int DecisionStep { get; }
}
```

The Basic scene maps its three-action movement branch to `[Stay, Left, Right]`, uses the complete two-action combat branch, and fixes utility to `Idle`. The strategic scene uses all `5 × 2 × 3` branch choices. Branch index tables are versioned and verified against exported-model outputs.

### Shared research actuator

One deterministic actuator executes `ResearchActionTuple` in every condition. It owns:

- collision-conscious translation through a shared character-motion path;
- action holding between decisions;
- weapon cooldown, ammunition, hitscan, damage, and reload timing;
- legal target resolution and one-frame look-at/snap in the strategic scene;
- pickup interaction and mechanically impossible-action masks;
- application and completion of a reflex movement override;
- action-applied and action-rejected events.

Basic aiming is intentionally different but equally controlled: a fixed forward crosshair fires the identical hitscan ray, and the learned policy must move laterally to align with the target.

Strategic aiming is a controlled mechanical script. When `Shoot` is selected, it chooses the nearest visible legal target, reads the target hitbox position, applies the same one-frame look-at/snap, and resolves the same hitscan test for BDQ, BDQ+reflex, BDQ+LLM, full hybrid, and rule-director controls. No optional layer receives a different aim path or additional target data.

The actuator does not inspect Q-values, prompts, LLM text, training rewards, or condition labels other than the explicit reflex-enable flag needed for the ablation.

### Episode, seed, and reset ownership

The research environment owns a typed episode context containing:

- run ID, policy-training seed, scenario seed, episode index, and condition ID;
- scene/configuration/model hashes;
- start/end simulation and real times;
- terminal reason: success, agent death, opponent death, timeout, or infrastructure-invalid;
- cumulative training reward and the separately calculated evaluation outcome.

Reset order is fixed:

1. Stop and invalidate outstanding director requests for the prior episode.
2. Reset episode and sequence IDs.
3. Reset agent/opponent transforms, health, ammunition, cooldowns, pickups, cover state, and scripted schedules from the scenario seed.
4. Reset actuator, reflex, BDQ recurrent/stack state if any, directive, counters, and telemetry observers.
5. Render and fill the four-frame initial observation stack.
6. Emit `episode_started` with the complete manifest references.

Policy-training seeds control weight initialization, replay sampling, and exploration. Scenario seeds control environment/opponent variation. Final comparisons pair on scenario seed and never reuse training scenarios as held-out evaluation scenarios.

### Unity Basic environment

- Primitive long narrow room; agent fixed at the south start and target at a seeded random lateral position near the north end.
- `84×84` grayscale four-frame observation.
- movement `[Stay, Left, Right]`; combat `[Idle, Shoot]`; utility fixed `Idle`.
- fixed forward crosshair and hitscan.
- target hit ends the episode successfully; 300 decisions truncate it.
- training reward: `+1` hit, `-0.01` each decision, `-0.02` miss.
- random and scripted policies use the same observation-to-action and actuator path.
- a joint-action Double DQN produces six tuple Q-values solely as a branch-factorization sanity control.

### Strategic environment

Mechanics are fixed before final training:

- 100 maximum health for agent and opponent;
- 20 damage per valid hitscan hit;
- six-round magazine and 18 reserve rounds;
- 0.25-second weapon cooldown;
- 1.5-second reload;
- 30-second episode limit;
- named collision-valid cover objects and line-of-sight tests;
- bounded health/ammunition pickups through `Interact`;
- one seeded scripted opponent with fixed configuration and deterministic schedule;
- one `ImminentShotEvent` exactly 400 ms before each scripted shot.

The environment exposes physically impossible action masks only. Examples include reload with a full magazine/no reserve ammunition or interact with no legal object in range. It does not mask retreat, attack, firing, or movement merely to enforce a strategic directive.

### Research reflex

`EvadeTelegraphedShot` subscribes to `ImminentShotEvent` and, when enabled and off cooldown, preempts movement with one deterministic collision-safe `0.6 m` lateral evade. Cooldown is the registered one-second interval.

Direction selection uses the same physics/clearance information available to the shared actuator. It cannot:

- aim or shoot;
- change combat or utility intent;
- select or edit a strategic goal;
- query LLM state or Q-values;
- perform waits, coroutines, allocation-heavy serialization, file I/O, networking, or model inference before motion.

Required events include telegraph observed, reflex accepted/suppressed, command issued, requested/applied displacement, collision flags, visible motion, damage outcome, preemption ended, and BDQ movement restored. Duplicate telegraphs and cooldown-suppressed events cannot move the agent twice.

### Branching Double DQN (BDQ) inference and training boundary

Unity uses ML-Agents `4.0.0` for sensors, branched action transport, episode boundaries, and exported-model inference. Training uses matching Python packages in Python 3.10.12 plus a version-pinned custom off-policy trainer plugin. Built-in PPO/SAC configuration is not a substitute for BDQ.

Primary network:

```text
4 × 84 × 84 grayscale stack
→ Conv(32, 8×8, stride 4)
→ Conv(64, 4×4, stride 2)
→ Conv(64, 3×3, stride 1)
→ 512-unit shared representation (+ categorical goal in strategic policy)
→ scalar dueling value V(s,g)
→ one mean-centered advantage head A_i(s,g,a_i) per action branch
→ branch Q_i = V + A_i - mean(A_i)
```

Use Double-DQN online action selection and target-network evaluation, replay capacity 100,000, replay warmup 10,000 decisions, batch 64, `gamma=0.99`, Adam `1e-4`, Huber loss averaged over selected branch values, update every four decisions, hard target synchronization every 10,000 optimizer updates, and epsilon decay `1.0 → 0.1`, followed by a `0.05` evaluation floor only during exploratory validation. Final evaluation is greedy.

Train five independent policy seeds. Each seed has its own configuration, learning curves, checkpoint lineage, export-parity test, and SHA-256. The same final strategic checkpoint for a seed is loaded into all factorial conditions for that seed.

Strategic training randomizes reflex availability and obtains directive labels from a deterministic teacher, not a live LLM. Goal-specific potential shaping may reward progress toward enemy pressure, cover, health, or ammunition while shared win/loss and damage rewards remain constant. Document every potential and coefficient before final training.

### Strategic directive

Use a closed categorical schema:

```csharp
public enum StrategicIntent
{
    Balanced = 0,
    OffensiveRush = 1,
    DefensiveRetreat = 2,
    SeekHealth = 3,
    ConserveAmmo = 4
}

public readonly struct StrategicDirective
{
    public StrategicIntent Intent { get; }
    public PriorityTarget PriorityTarget { get; }
    public EngagementRule EngagementRule { get; }
    public long RequestSequence { get; }
    public int EpisodeId { get; }
    public float SnapshotTimestamp { get; }
    public float CompletedTimestamp { get; }
}
```

Only coherent fixed templates are accepted:

- `BALANCED`;
- `OFFENSIVE_RUSH` + enemy + engage;
- `DEFENSIVE_RETREAT` + cover + hold fire unless threatened;
- `SEEK_HEALTH` + health pickup + disengage when possible;
- `CONSERVE_AMMO` + valid enemy opportunity + high-confidence fire only.

The validated intent becomes a categorical BDQ input. `PriorityTarget` and `EngagementRule` support validation, telemetry, and deterministic-teacher/rule-director parity; they do not directly call the actuator.

### Strategic snapshot and directors

The main thread captures an immutable snapshot every two seconds containing quantized agent health/ammunition, visible-enemy count/distance/health categories, nearest cover and pickup availability/distance categories, current directive, episode ID, sequence ID, and timestamp. Raw images and continuous object matrices are excluded.

All directors implement one request/result boundary:

- fixed `BALANCED` director for LLM-off factorial conditions;
- deterministic rule director receiving the same snapshot;
- deterministic mock director supporting failure/delay cases;
- local HTTP director for Qwen3-8B through `llama.cpp`.

The local-model default is a quantized Qwen3-8B non-thinking/instruction model. Pin the `llama.cpp` version/commit, prefer a validated Vulkan backend, and record model source, quantization, SHA-256, prompt, JSON schema, context, temperature zero, seed, and output-token cap. Model weights remain outside Git.

Transport rules:

- capture snapshot on the Unity main thread;
- perform HTTP waiting and parsing asynchronously without Unity API access;
- publish results through a thread-safe queue;
- validate and apply on the main thread;
- request every two seconds, timeout after five seconds, and reject results older than four seconds;
- reject malformed, incoherent, stale, timed-out, out-of-order, and prior-episode results;
- retain the latest valid directive; default to `BALANCED` when none exists.

The mock director must reproduce fixed output, invalid JSON, connection loss, timeout, out-of-order completion, and delays of `0`, `500`, `1000`, `2000`, and `3000 ms`.

### Research outcome and factorial contract

Primary combat utility is calculated after the episode and is not silently substituted for the training reward:

```text
U = episode_outcome
  + 0.25 * (damage_dealt - damage_taken) / 100
  - 0.05 * missed_shot_fraction
  - 0.05 * wasted_resource_fraction
```

`episode_outcome` is `+1` opponent eliminated, `-1` agent death, and `0` timeout. Store all components separately.

The main 2×2 conditions use identical checkpoints and paired scenario seeds:

1. BDQ, fixed `BALANCED`, reflex off.
2. BDQ + reflex, fixed `BALANCED`.
3. BDQ + local LLM, reflex off.
4. BDQ + reflex + local LLM.

Secondary rule-director conditions run with reflex off/on and the same snapshot/directive contract. For each of five training seeds, run every condition on the same 100 held-out scenario seeds, producing 500 paired episodes per condition. Analysis uses a 10,000-resample hierarchical bootstrap over policy seed and then paired scenario seed.

Registered thresholds:

- full-hybrid utility improvement over BDQ-only at least `0.10`, with paired 95% confidence interval above zero;
- reflex damage-per-telegraph difference below zero with paired 95% confidence interval below zero;
- full-hybrid telegraph-to-visible-evade p95 at most `50 ms` and within `20 ms` of BDQ+reflex at every injected delay tier, at least 200 events per tier;
- positive LLM factorial effect; strong LLM claim additionally requires at least `0.05` utility over the rule director with paired 95% confidence interval above zero.

### Research telemetry and artifact boundary

In addition to the existing stage timing, record:

- run/episode/condition/policy/scenario identifiers and hashes;
- observations/actions only in a bounded research-appropriate form, rewards, terminals, and resets;
- training return, success, learning-curve area, loss, TD error, epsilon, replay size, Q summaries, throughput, and inference time;
- health, damage, shots, hits, misses, reloads, pickups, survival, wasted actions, and directive occupancy;
- every reflex timing stage, collision, damage outcome, and deadline miss;
- every director request, first-token if available, completion, validation, application, discard reason, timeout, fallback, and goal change;
- main-thread/fixed-step timing, allocations, logger pressure, dropped events, and write failures.

Keep handler work bounded and enqueue typed records. Raw JSONL/CSV, checkpoints, weights, and generated files live under a project-local ignored artifact root. Track schemas, dependency locks, configurations, scripts, curated aggregates, plots, checksums, and conclusions. Every published number must trace to a run manifest and analysis command.

## Timing model

### `Test_Arena` regression timing

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

### Research timing

Required research timing stages include:

```text
policy_observation_requested → policy_action_available
policy_action_available → actuator_action_applied
opponent_telegraph → reflex_commanded
reflex_commanded → reflex_visible_motion
opponent_telegraph → reflex_visible_motion
reflex_visible_motion → preemption_ended
strategy_snapshot → director_request_started
director_request_started → first_token (when exposed)
director_request_started → director_response_completed
director_response_completed → directive_validated_or_rejected
directive_validated → directive_applied
```

Record simulation-step counts alongside real time. Never interpret accelerated training wall time as player-visible latency. Reflex H3 uses real-time standalone or controlled Editor runs at the registered physics/frame conditions, not accelerated headless training.

## Event schema

Representative records:

```json
{"t":"activity_started","ts":2.000,"npcId":"NPC_01","activity":"Patrol"}
{"t":"aim_stimulus_started","ts":5.000,"sourceId":"Player"}
{"t":"perception_notice","ts":5.050,"npcId":"NPC_01","angleDeg":62.4,"hasLos":true}
{"t":"suspicion_threshold","ts":5.420,"npcId":"NPC_01","suspicion":0.5,"notice_to_threshold_ms":370}
{"t":"turn_started","ts":5.421,"npcId":"NPC_01"}
{"t":"threat_confirmed","ts":5.650,"npcId":"NPC_01","episodeId":3}
{"t":"activity_interrupted","ts":5.651,"npcId":"NPC_01","episodeId":3,"activity":"Patrol","reason":"ConfirmedAimThreat","outcome":"Suspended"}
{"t":"reflex_commanded","ts":5.653,"npcId":"NPC_01","episodeId":3,"variant":"Flinch_StepBack","confirmation_to_command_ms":3}
{"t":"visible_motion_started","ts":5.690,"npcId":"NPC_01","episodeId":3,"signal":"root_position_rotation","command_to_visible_ms":37,"confirmation_to_visible_ms":40}
{"t":"threat_released","ts":6.100,"npcId":"NPC_01","episodeId":3}
{"t":"activity_resumed","ts":6.200,"npcId":"NPC_01","activity":"Patrol","threat_release_to_resume_ms":100}
```

Session summaries should include counts and descriptive statistics for each defined stage, including min, max, mean, p50, p95, and optional standard deviation. A single reflex summary is insufficient for the final evaluation.

## Arena responsibilities

`Test_Arena` is the implemented deterministic test fixture. Each object must support a named regression scenario:

- open lane for direct frontal threat;
- visual edge for peripheral notice;
- full-height divider for occlusion;
- two patrol markers for ongoing activity;
- interaction marker for interruption;
- low block and interaction marker retained from the deterministic fixture.

Required initial scenarios:

1. Direct frontal threat.
2. Peripheral notice and orientation.
3. Occluded player with no false detection.
4. Patrol interrupted once.
5. Threat release and manual resume edge recording; the superseded automatic recovery FSM is not required.

`Research_Basic` is a separate minimal learning fixture. Every object must support lateral alignment, visual observation, deterministic target placement, hitscan resolution, reward, or reset. It contains no cover, health, reload, pickup, LLM, or opponent complexity.

`Research_Strategic` is a separate factorial fixture. Every object must support a named mechanic or experimental condition: spawn, cover, pickup, opponent schedule, telegraph, action execution, reflex clearance, or observation. Decorative objects and unregistered random effects are excluded.

## File-map boundaries

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
        NpcBehaviorController.cs
      Reflex/
        ReflexSelector.cs
        VisibleMotionObserver.cs
    Logging/
      JsonlLogger.cs
      LogEvents.cs
      TelemetryRecorder.cs
    Research/
      Environment/                       (R1B/R1C communicator smoke)
      Actuation/                         (R2A stable semantic action tuple)
      Basic/                             (R2A scene runtime, sensor, episode, actuator)
      Policy/                            (planned)
      Reflex/                            (planned)
      Strategy/                          (planned)
      Telemetry/                         (planned)
  Scenes/
    Test_Arena.unity
    Research_Smoke.unity                  (R1B communicator fixture)
    Research_Basic.unity                 (R2A deterministic visual benchmark)
    Research_Strategic.unity             (planned)
  Tests/
    EditMode/                             (R1B/R1C smoke and R2A Basic tests)
    PlayMode/

Research/                                (non-Unity research source and contracts)
  environment/                           (R1A dependency lock and setup record)
  configs/                               (R1A versioned contracts)
  schemas/                               (R1A run-manifest schema/example)
  smoke/                                 (R1B config, driver, and instructions)
  basic/                                 (R2A contract, LLAPI baselines, tests, instructions)
  trainer/                               (planned)
  analysis/                              (planned)

Artifacts/Experiments/                   (generated/ignored root established by R1A)
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
- An old episode frame leaks into the new four-frame observation stack.
- Branch indices differ between Unity, trainer, checkpoint, and exported inference.
- A joint-action interaction is lost by BDQ's additive branch factorization and goes unreported.
- Training and evaluation reuse the same scenario seeds.
- Episode reset leaves health, ammunition, cooldown, opponent schedule, directive, request, reflex, or replay-facing state behind.
- Optional conditions receive a different camera, actuator, aim resolver, target data, action mask, checkpoint, or opponent schedule.
- The LLM directly outputs actuator commands or changes inference rewards.
- Strategic masks forbid legal actions and create an artificial performance gain.
- An asynchronous task touches Unity objects off the main thread.
- A stale or prior-episode LLM result is applied after reset.
- LLM timeout, invalid JSON, out-of-order response, or server loss blocks physics, BDQ, or reflex work.
- A cached/local-model response is counted as live inference without being labeled.
- Accelerated training wall time is reported as player-visible response latency.
- Only aggregate combat utility is reported, hiding deaths, damage, misses, or resource waste.
- Final thresholds or exclusions are changed after results without an exploratory label.
- Raw checkpoints, model weights, proprietary assets, or large logs are committed accidentally.
