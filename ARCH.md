# quickdraw-AI — Software Architecture

## Authority and status

This file is the canonical description of software structure, ownership,
interfaces, event flow, timing boundaries, and runtime failure isolation.

- Current implementation status: [`STATE.md`](STATE.md)
- Registered scientific values: [`RESEARCH.md`](RESEARCH.md)
- Current authorization: [`TASK.md`](TASK.md)
- Decision rationale: [`docs/decisions/`](docs/decisions/README.md)
- Acceptance results: [`docs/evidence/`](docs/evidence/README.md)

Sections explicitly marked **planned** describe required future boundaries, not
existing runtime behavior. Exact research values are owned by `RESEARCH.md` and
the versioned machine-readable contracts under `Research/`.

## System overview

```text
Test_Arena — implemented deterministic regression fixture
  player aiming state
    → structured aim stimulus
    → soft perception and one-shot confirmation
    → synchronous activity interruption
    → deterministic Flinch_StepBack command
    → observed visible-motion onset
    → buffered typed telemetry

Research_Smoke — implemented transport fixture
  ordered Python configuration
    ↔ ML-Agents side channel and LLAPI
    ↔ deterministic vector observation/action/episode state

Research_Basic — implemented visual-control benchmark
  Unity HWC frame stack
    ↔ synchronous Python LLAPI collector
    → lossless replay
    → BDQ online/target networks and optimizer
    → typed [movement, combat] action
    → one shared Unity actuator
    → reward and episode boundary

Research_Strategic — planned factorial benchmark
  visual stack + categorical strategic goal
    → goal-conditioned BDQ intent
    → shared deterministic actuator
    ↔ optional movement-only reflex preemption
    ↔ optional asynchronous strategic director
    → research telemetry
```

The deterministic fixture and research scenes are intentionally isolated.
`Test_Arena` remains a regression surface; it is not retrofitted into a
training environment. `Research_Basic` remains a minimal learning control;
strategic mechanics belong in a separate future scene.

## Modules and dependency direction

### Implemented Unity assemblies and namespaces

- `QuickDraw.Core` owns the player controller and development overlay.
- `QuickDraw.AI.Stimuli` owns structured aim state and stimulus production.
- `QuickDraw.AI.Perception` owns visibility, suspicion, orientation, and threat
  confirmation.
- `QuickDraw.AI.Activity` owns the current interruptible patrol activity.
- `QuickDraw.AI.Behavior` owns high-level interruption and state-edge ordering.
- `QuickDraw.AI.Reflex` owns deterministic immediate reaction selection and
  visible-onset observation.
- `QuickDraw.Logging` owns typed event DTOs, buffering, serialization, and
  summaries.
- `QuickDraw.Research.Environment` owns the isolated communicator fixture.
- `QuickDraw.Research.Actuation` owns stable semantic action values and the
  typed research action tuple.
- `QuickDraw.Research.Basic` owns the Basic scene contract, visual sensor,
  episode state, target, actuator, and ML-Agents agent lifecycle.

### Implemented Python package

`Research/trainer/quickdraw_bdq` is split by responsibility:

- `action_space.py` validates branch sizes, tuples, masks, and joint indices.
- `network.py` owns the visual dueling branching network.
- `targets.py` owns legal masked Double-DQN target and Huber-loss calculation.
- `replay.py` owns immutable transition validation, lossless frame interning,
  columnar metadata, ring overwrite, sampling, and storage accounting.
- `optimizer.py` owns online/target initialization, Adam updates, counters,
  eligibility, and hard target synchronization.
- `exploration.py` owns the stateless epsilon schedule and seeded mask-safe
  branch selector.
- `llapi.py` owns Unity behavior validation, pending-decision completion,
  truncation-mask transport, and collection records.
- `checkpoint.py` owns the versioned fail-closed trainer checkpoint: exact
  state encoding, identity binding, integrity hashing, and clean-boundary
  save plus fresh-object restore.
- `acceptance.py` owns reusable, non-scientific acceptance plumbing: canonical
  hashing and serialization, runtime/package checks, execution-mode checks,
  fresh-worker launch, deterministic worker comparison, and result writing.
- `update_gate.py` owns the shared bounded Unity collection and optimizer-gate
  mechanism used by the update-trajectory milestones.

The milestone runners in `Research/trainer/` are historical compatibility
entry points. They load milestone-specific contracts, expectations, schemas,
and summaries, then compose the shared package modules into bounded acceptance
gates. They are not a separate training framework and must not become the
canonical owner of generic behavior needed by another milestone. The retired
high-level ML-Agents `Trainer`/`Policy`/`Trajectory` experiment is historical,
not an available runtime path.

### Planned research modules

- `QuickDraw.Research.Policy` — learned-policy inference and checkpoint
  metadata boundary.
- `QuickDraw.Research.Reflex` — imminent-shot movement preemption.
- `QuickDraw.Research.Strategy` — snapshots, directive validation, fixed/rule/
  mock/local directors, and asynchronous transport.
- `QuickDraw.Research.Telemetry` — research run, episode, policy, reflex,
  director, and system records.
- `Research/analysis` — paired factorial aggregation and bootstrap analysis.

Planned assemblies are added only by an authorized task. Their absence must
not be hidden behind placeholder descriptions that imply implementation.

### Dependency rules

- Core never depends on individual NPC or research behavior.
- Stimuli describe source state; they do not confirm threats or select actions.
- Perception confirms threats; it does not own activity, mechanics, or recovery.
- Behavior owns interruption ordering and state edges.
- Deterministic reflex code performs no logging I/O, networking, model
  inference, or tactical planning before motion.
- Existing deterministic AI does not depend on ML-Agents or research scenes.
- The Unity environment owns scenario, reset, reward, action legality, and
  terminal/truncation truth.
- Python owns collection, replay, action selection, targets, and optimization;
  it never infers Unity legality from privileged scene state.
- Every research milestone states a genuinely new acceptance or research
  claim. It extends an existing execution boundary through shared acceptance
  mechanisms plus contract/configuration data unless the claim also requires a
  substantially different contract or execution boundary; only then is a
  bespoke runner/test/schema stack justified. A new label, cutoff, or expected
  value alone is not a new boundary.
- Policies emit typed intent; they do not emulate keyboard or mouse input.
- The shared actuator is the exclusive intent-to-mechanics path.
- A strategic director may publish only a validated categorical goal. It may
  not call mechanics, edit rewards, or change legal-action masks.
- Background director work may handle plain data only. Unity-object capture and
  result application stay on the main thread.
- Telemetry observes control and model events without becoming a dependency of
  urgent control paths.

## `Test_Arena` component contracts — implemented

### Player and aim stimulus

`SimpleFPSController` requires a `CharacterController`, uses the Unity Input
System directly, implements first-person movement/look/gravity/cursor handling,
and exposes a read-only aiming state. It has no NPC or Starter Assets
dependency.

`AimThreatEmitter` samples the configured player camera in `LateUpdate` and
publishes a structured value containing source identity, origin, direction,
timestamp, maximum distance, and aiming state. It emits one start/end edge per
aim-state transition. It never selects an NPC response.

A center-camera threat-confirmation bypass may exist only behind the explicit
debug flag. It defaults off and is excluded from evaluation. The normal path is
always stimulus through perception; see
[`ADR-0002`](docs/decisions/ADR-0002-stimulus-through-perception.md).

### Soft perception

`SoftFOVPerception` owns:

1. distance rejection;
2. total-cone to half-angle comparison;
3. conditional line-of-sight testing;
4. suspicion accumulation/decay using measured perception-tick elapsed time;
5. orientation toward a valid source;
6. one confirmed-threat edge per armed episode; and
7. recovery/rearming before another episode may confirm.

Its conceptual states are:

```text
Idle → Noticed/Suspicious → Orienting → ThreatConfirmed → Recovering
```

Repeated valid aim within the same episode may continue orientation but cannot
increment the episode or re-emit confirmation. Invalid aim does not steer the
NPC. Perception has no activity or reflex dependency.

### Activity and behavior coordinator

`PatrolActivity` exposes whether it is running and interruptible, its target or
progress, and interruption/resume metadata. It must stop motion before a reflex
is dispatched and must not resume while the threat remains active.

`NpcBehaviorController` subscribes to the confirmation edge, synchronously
suspends patrol, records the interruption, emits `ActivityInterrupted` only
after motion has stopped, and then commands `ReflexSelector`. The confirmation
episode/timestamp and the selector's episode guard prevent duplicate delivery.

The coordinator does not write telemetry, select automatic recovery, or resume
activity. The old tactical-recovery state machine is superseded history and is
not part of this architecture.

### Reflex and visible onset

`ReflexSelector` owns the implemented collision-aware `Flinch_StepBack`. It
uses an explicit stable style seed, rejects duplicate commands for an episode,
selects deterministic step/yaw variation, and moves through the existing
`CharacterController` path. It emits command metadata separately from visible
motion.

`VisibleMotionObserver` captures the pre-command root pose and inspects the
actual pose in `LateUpdate`. Crossing the registered position or rotation
threshold emits one `visible_motion_started` record for the episode. Calling a
movement method or setting an animation trigger is not visible-onset evidence;
see [`ADR-0004`](docs/decisions/ADR-0004-command-vs-visible-motion.md).

### Buffered telemetry

`TelemetryRecorder` observes stimulus, perception, behavior, reflex,
visible-onset, and patrol events and enqueues explicit DTOs. Gameplay
components do not depend on `QuickDraw.Logging`.

`JsonlLogger` serializes and flushes outside urgent handlers, bounds work per
update, uses a session-unique path, retains buffered records on a failed write,
and resets static/singleton state when Domain Reload is disabled. Summaries are
derived from typed stage measurements rather than replacing raw event stages.

## `Research_Smoke` boundary — implemented

`Research_Smoke` is a transport/lifecycle fixture, not a learned environment.
It contains one `ResearchSmokeAgent`, `ResearchSmokeCoordinator`,
`ResearchSmokeEpisode`, and `ResearchSmokeProtocol`.

- `ResearchSmokeProtocol` owns envelope/configuration serialization and strict
  schema/contract/run/sequence validation.
- `ResearchSmokeCoordinator` owns side-channel registration, ordered run and
  per-episode configuration, readiness, reset, and infrastructure errors.
- `ResearchSmokeEpisode` owns the deterministic observation state, legal-action
  masks, additive smoke rewards, and terminal/truncation choice.
- `ResearchSmokeAgent` adapts ML-Agents observation/action/episode callbacks to
  the coordinator and episode state.

The protocol uses independent monotonic sequences per direction. A Unity→Python
message and a Python→Unity message do not share a single counter. `EndEpisode`
represents a true terminal; `EpisodeInterrupted` represents a truncation.

`Research/smoke/run_smoke.py` launches or connects to Unity, validates the
behavior specification, drives LLAPI decisions, records the complete canonical
trace, and can compare two same-seed fresh processes. CPU reference and backend
parity modes extend the same boundary without making it a trainer.

## `Research_Basic` Unity boundary — implemented

### Scene and ownership

`Research_Basic.unity` contains one learning agent, target, camera/visual
sensor, episode owner, actuator, and ML-Agents decision requester. The scene is
independent of `Test_Arena` and contains no cover, health, reload, pickup,
opponent, reflex, or director mechanics.

`ResearchBasicContract` centralizes Unity-side identity and invariant checks.
The machine-readable Basic contract remains the executable cross-language
source for exact registered values.

### Visual sensor and frame stack

`ResearchBasicVisualSensorComponent` is the `SensorComponent` that creates the
internal `ResearchBasicVisualSensor` `ISensor` consumed by the agent. The
component owns serialized Unity references and lifecycle integration; the
sensor owns observation shape, capture/update, and write behavior.

One camera render is converted to one grayscale float32 frame. A circular
`ResearchBasicFrameStack` retains four frames physically while exposing them
logically oldest-to-newest. On episode reset, one post-reset capture fills all
four logical positions before the next policy decision. An update cannot push a
new frame until that reset fill has occurred; this prevents prior-episode
leakage.

The Unity/Python wire boundary is uncompressed HWC. Python converts to CHW only
at the encoder boundary. Neither Unity nor Python may silently reinterpret
channel order, mask polarity, or observation dtype.

### Agent, episode, target, and actuator

`ResearchBasicAgent` is the ML-Agents adapter. The separate sensor component
writes the visual observation, while the agent accepts decisions at the
registered cadence, converts discrete branches to a typed action tuple,
publishes environment-authored masks, and delegates reset/action processing.
It does not contain Q-learning logic.

`ResearchBasicEpisode` owns deterministic target placement, agent slot,
decision/shot/miss counters, cumulative reward, reset state, and the distinction
between target-hit terminal and decision-limit truncation.

`ResearchBasicTarget` exposes the fixed target hit surface and reset placement.
`ResearchBasicActuator` is the only path from the typed tuple to lateral motion
and combat. It applies movement before resolving shoot, uses the shared
camera-center hitscan/crosshair convention, and returns structured action
outcomes to the episode owner.

Movement remains slot-based. A gradual-motion environment is a separately
versioned planned variant, not an in-place change to the Basic control.

### Terminal/truncation mask transport

Ordinary continuation masks arrive with the next `DecisionStep`. True terminal
transitions do not bootstrap, so Python uses an explicit irrelevant sentinel.
Decision-limit truncations do bootstrap, but ML-Agents exposes the final state
through `TerminalSteps` without the normal next-decision mask.

Immediately before `EpisodeInterrupted()`, Unity therefore sends the
authoritative final-state unavailable-action mask over the dedicated Basic side
channel. Python binds it to the exact run/episode/agent/sequence and fails on
missing, duplicate, stale, or mismatched messages. Python never derives the
mask from slot state; see
[`ADR-0011`](docs/decisions/ADR-0011-terminal-truncation-mask.md).

## Python BDQ boundary — implemented through bounded acceptance

### Collection transaction

For each agent, the collector stores exactly one pending record when it sends an
action:

```text
(observation, chosen branch action, current unavailable-action masks)
```

When the same agent next appears in `DecisionSteps` or `TerminalSteps`, the
collector combines that pending record with delivered reward, next observation,
next masks, and episode flags to create exactly one immutable transition. It
rejects a missing pending action, a second pending action, duplicate completion,
or behavior/shape/mask mismatch.

This is a one-step environment transaction. A four-frame observation is one
state; it does not mean four transitions. The pending record exists because the
next state is available only after Unity executes the submitted action.

### Replay representation

The public replay contract presents immutable transitions and sampled batches.
Internally, `replay.py` interns exact C-contiguous float32 channel bytes and
stores eight frame references plus preallocated metadata columns in a ring.
Reference counts reclaim orphaned frames after overwrite. Reconstruction is
bit-exact and preserves the public HWC dtype, shapes, order, indices, and seeded
sampling stream.

Storage accounting is explicit and fail-closed. A valid insert that would
exceed the registered ceiling raises `MemoryError` before visible mutation.
Lossy quantization and compression are outside the contract. The rationale is
recorded in [`ADR-0012`](docs/decisions/ADR-0012-lossless-bounded-replay.md).

### Network, target, loss, and updates

The encoder converts HWC batches to CHW and feeds a shared convolutional/dueling
representation. One advantage head per branch produces branch-local Q-values.
The online network selects the best legal next action per branch; the frozen
target evaluates that selected action. True terminals suppress bootstrap;
registered truncations retain it.

For each transition/branch, the online value of the action actually taken is
compared with its Double-DQN target using Huber loss. The optimizer reduces over
the batch and branches, updates only the online network, and hard-copies online
to target only at the registered optimizer-update boundary. Exact layers,
hyperparameters, and schedules belong in [`RESEARCH.md`](RESEARCH.md).

The scheduler counts validated completed transitions, not frames, calls, or
episodes. The epsilon schedule is a stateless function of that same count. One
seeded selector owns its RNG stream and samples only from legal ascending branch
indices. At full exploration it skips an unused network forward pass without
changing RNG consumption.

Current bounded progress and exact update evidence belong in
[`STATE.md`](STATE.md) and [`docs/evidence/`](docs/evidence/README.md), not here.

## Strategic architecture — planned

### Shared actuator and environment

`Research_Strategic` will own health, damage, ammunition, reload, pickups,
cover, opponent schedule, telegraphs, reward, reset, and episode outcome. All
factorial conditions must use the same camera, observations, checkpoint,
mechanical target resolver, look-at/snap, hitscan, collision path, action masks,
and actuator.

The actuator holds the latest BDQ tuple between policy decisions. It is the
only component permitted to execute movement, shooting, reload, and interaction.
The exact strategic mechanics and fairness contract live in `RESEARCH.md`.

### Research evade reflex

The planned reflex subscribes to a structured imminent-shot edge. If enabled
and eligible, it may preempt only movement with one deterministic collision-safe
evade, then restore the latest held BDQ movement intent. It cannot aim, shoot,
reload, interact, inspect Q-values, change a goal or reward, call a director, or
perform waits/I/O/inference before motion.

Duplicate/cooldown-suppressed events cannot cause extra displacement. Command,
applied motion, collision, visible onset, preemption end, restoration, damage
outcome, and deadline status remain distinct observable stages.

### Strategic snapshot and directors

The Unity main thread periodically captures a compact immutable categorical
snapshot with episode and monotonic sequence identity. The policy frame is not
sent to the director, and the snapshot is not sent to the policy.

All directors share one request/result interface:

- fixed goal for director-off conditions;
- deterministic same-information rule director;
- deterministic mock for failure and delay testing; and
- local HTTP model director.

HTTP waiting and parsing run away from Unity objects and publish plain results
through a thread-safe queue. The main thread validates schema coherence,
sequence, episode, age, and timeout state before applying a categorical goal.
Malformed, stale, timed-out, out-of-order, and prior-episode results are
discarded. The latest valid goal remains active; the registered fallback is
used when none exists.

The director never calls the actuator, supplies tactical masks, edits reward,
or chooses branch actions. See
[`ADR-0008`](docs/decisions/ADR-0008-async-categorical-llm.md) and
[`ADR-0009`](docs/decisions/ADR-0009-rule-director-control.md).

### Thread ownership

| Work | Owner |
| --- | --- |
| Unity object reads/writes and snapshot capture | Unity main thread |
| Physics and mechanical actuation | Unity fixed-step path |
| Policy decision request/application | Unity main thread at policy boundary |
| Reflex eligibility and command | event edge, motion by next fixed step |
| HTTP wait and response parsing | background task, plain data only |
| Directive validation/application | Unity main thread |
| Event serialization and disk flush | deferred/bounded logger path |

No background task may hold or dereference a Unity object.

## Timing and event boundaries

Use one monotonic real-time clock for cross-stage player-visible latency and
record fixed-step, decision, completed-transition, optimizer-update, episode,
request-sequence, and run counters separately. Accelerated simulation time must
not be reported as visible response latency.

Important event chains are:

```text
aim stimulus
  → perception notice
  → suspicion threshold
  → orientation start
  → threat confirmation
  → activity interruption
  → reflex command
  → observed visible motion

policy observation
  → action selection
  → Unity action application
  → next DecisionStep or TerminalStep
  → immutable replay transition
  → optional optimizer update

opponent telegraph
  → reflex accepted/suppressed
  → reflex command
  → applied displacement
  → observed visible motion
  → preemption end and BDQ movement restoration

strategy snapshot
  → request start
  → optional first token
  → response complete
  → validation/discard
  → directive application
```

Command timestamps and visible-motion timestamps are never interchangeable.
Decision count, completed-transition count, and optimizer-update count are
never interchangeable.

## Scene and file boundaries

```text
Assets/_Project/
  Code/
    Core/                 player and development UI
    AI/                   deterministic stimulus/perception/activity/behavior/reflex
    Logging/              deterministic typed telemetry
    Research/
      Environment/        communicator smoke
      Actuation/          stable research action tuple
      Basic/              Basic sensor, episode, target, actuator, agent
      Policy/             planned
      Reflex/             planned
      Strategy/           planned
      Telemetry/          planned
  Scenes/
    Test_Arena.unity      deterministic regression fixture
    Research_Smoke.unity  communicator fixture
    Research_Basic.unity  visual-control benchmark
    Research_Strategic.unity  planned
  Tests/
    EditMode/
    PlayMode/

Research/
  configs/                cross-cutting machine-readable contracts
  environment/            dependency/backend runbooks and fixtures
  schemas/                run-manifest schemas/examples
  smoke/                  communicator runner and contracts
  basic/                  Basic contract and baseline runners
  trainer/                BDQ package, contracts, runners, validators, tests
  analysis/               planned analysis code

Artifacts/Experiments/    ignored generated runs, players, logs, models, plots
docs/                     decisions, evidence, history, and stable reference
```

There is no required `ThreatRaycaster.cs` in the accepted architecture.

## Failure modes to test explicitly

### Deterministic fixture

- Total FOV is interpreted as a half-angle.
- Suspicion uses render-frame delta inside a lower-frequency perception tick.
- Occlusion masks are empty or include the target incorrectly.
- Confirmation, interruption, or reflex dispatch repeats every tick.
- Patrol motion continues before the reflex command or resumes under threat.
- The debug confirmation bypass remains enabled in evaluation.
- Root translation passes through collision geometry.
- Runtime-name hashing changes style behavior across sessions.
- Command time is reported as visible onset.
- Logging allocates/serializes/writes in the urgent path.
- Static state survives incorrectly with Domain Reload disabled.

### Basic and BDQ

- A prior-episode frame enters the new observation stack.
- Wire HWC/encoder CHW order, dtype, normalization, or mask polarity drifts.
- Unity and Python branch-index tables disagree.
- A decision is completed without exactly one pending action.
- A truncation bootstraps without its authoritative final-state mask.
- A terminal is accidentally bootstrapped or a truncation is not.
- Replay mutation is partially visible after a validation or budget failure.
- Ring overwrite leaks orphaned frames or changes sample RNG consumption.
- Online and target network roles are swapped or target receives gradients.
- Update, epsilon, or target-sync schedules count frames/episodes instead of
  completed transitions or optimizer updates.
- A bounded deterministic smoke is described as extended training or policy
  effectiveness.

### Planned strategic system

- Optional conditions receive different camera, actuator, aim, checkpoint,
  legal masks, target data, or opponent schedule.
- The director outputs mechanics, action masks, or reward edits.
- A background task accesses Unity objects.
- A stale, out-of-order, or prior-episode directive is applied.
- Director failure blocks physics, policy decisions, or reflex motion.
- Delay injection enters the reflex call graph.
- Accelerated wall time is reported as player-visible latency.
- Aggregate utility hides deaths, damage, misses, or resource waste.
- A historical or planned component is described as implemented.
