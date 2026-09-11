## The academic framing

The most defensible description is:

> quickDraw is a reproducible, multi-rate visual-control research platform designed to test whether urgent reflexes and slow strategic reasoning can be added to learned tactical control without compromising responsiveness.

The project is inspired by the use of simple first-person environments such as ViZDoom for visual reinforcement learning, especially the ViZDoom Basic Scenario. quickDraw adapts that idea into a deterministic Unity benchmark with explicit physics, action masks, episode semantics, reflex events, and future strategic interventions. It is explicitly not claiming to reproduce ViZDoom’s published numerical results. See [RESEARCH.md](C:/projects/quickdraw-AI/RESEARCH.md:51).

The strongest contribution so far is not a new DQN algorithm. It is the combination of:

- a carefully factorized temporal architecture;
- a controlled Unity visual benchmark;
- explicit causal and fairness controls;
- reproducible RL infrastructure; and
- a planned evaluation that can distinguish hierarchy, reflex, and LLM effects.

## 1. The temporal hierarchy

The central architectural decision is to separate control by timescale:

```text
50 Hz physics actuator
        ↑
urgent event-driven reflex
        ↑
10 Hz learned tactical policy
        ↑
0.5 Hz strategic director
```

The implemented research design uses:

- a deterministic actuator at Unity’s `0.02 s` physics timestep;
- a learned BDQ tactical decision every five physics steps, or `10 Hz`;
- a future reflex that can preempt only movement by the next physics step;
- a future strategic director that publishes a categorical goal every two seconds.

This is described in [ADR-0001](C:/projects/quickdraw-AI/docs/decisions/ADR-0001-temporal-hierarchy.md:1).

The scientific justification is latency and failure isolation. A language model may take hundreds of milliseconds or fail entirely, but it should not block physics, movement, or an urgent evade. This turns an informal design intuition into a testable hypothesis:

> If the architecture is correctly separated, increasing LLM delay should not substantially change reflex visible-response latency.

That is the basis of registered hypothesis H3, which requires testing delays from `0` to `3000 ms` and measuring actual visible motion rather than merely issuing a command.

This is more rigorous than saying “the LLM runs asynchronously.” The architecture defines exactly what it is allowed to affect and what it is forbidden to affect.

## 2. Separate experimental surfaces

The project deliberately uses different Unity scenes for different scientific purposes:

- `Test_Arena`: deterministic perception, interruption, reflex, and telemetry fixture;
- `Research_Smoke`: transport and backend compatibility fixture;
- `Research_Basic`: minimal visual control benchmark;
- `Research_Strategic`: planned full temporal-hierarchy benchmark.

This separation prevents a common research failure: changing the environment, mechanics, and learning problem simultaneously.

`Test_Arena` was built before the RL system. It verifies that threat perception, activity interruption, visible motion, and telemetry can be tested without ML complexity. `Research_Basic` is intentionally much simpler: lateral movement, shooting, a fixed crosshair, a target in one of nine slots, and a small branched action space.

Academically, this is a staged reduction of the problem. It allows the project to establish:

1. deterministic mechanics;
2. deterministic transport;
3. deterministic visual control;
4. learned training;
5. strategic and reflex interventions.

The roadmap records this progression from the deterministic fixture through R1, R2, and R3. See [ROADMAP.md](C:/projects/quickdraw-AI/ROADMAP.md:8).

## 3. Why a branching dueling Double DQN?

This is one of the most important algorithmic choices.

### The action-space problem

The strategic action is naturally factored into branches:

- movement: `[Stay, Forward, Backward, Left, Right]`;
- combat: `[Idle, Shoot]`;
- utility: `[Idle, Reload, Interact]`.

A vanilla joint-action DQN would need one output for every combination:

```text
5 × 2 × 3 = 30 joint actions
```

That scales multiplicatively. If more branches or branch values are added, the output space grows rapidly.

The branching architecture instead uses:

```text
shared visual representation
        ↓
shared scalar value V(s)
        ↓
movement advantage head
combat advantage head
utility advantage head
```

The strategic network therefore has approximately `5 + 2 + 3 = 10` branch outputs rather than 30 joint outputs. In the Basic benchmark, the comparison is `3 × 2 = 6` joint actions versus separate movement and combat heads.

### Why branching?

Branching provides a useful inductive bias:

- visual features are shared across branches;
- each branch learns its own action preferences;
- action masks can be applied branch by branch;
- the output size grows additively rather than multiplicatively;
- the architecture matches the semantic structure of movement, combat, and utility.

This is especially attractive for a research platform where the action vocabulary may expand.

### Why dueling?

The dueling decomposition separates:

- how valuable the state is overall; and
- how much each action differs from the other actions in that state.

That is useful in many FPS states where several actions are nearly equivalent. For example, while waiting for a target to align, the value of the state may be more important than distinguishing among several low-value movement alternatives.

The mean-centering constraint is important because otherwise `V` and `A` are not uniquely identifiable: value can be shifted from one stream to the other without changing Q-values.

### Why Double DQN?

Standard DQN can overestimate action values because the same noisy estimates are used both to select and evaluate the maximum action.

quickDraw separates these roles:

- the online network selects the legal next action;
- the target network evaluates it;
- the target network is synchronized only at a registered hard boundary.

This gives a more stable bootstrapping target and makes the update process auditable.

The implementation uses:

- batch size `64`;
- replay warmup of `10,000` transitions;
- `γ = 0.99`;
- Adam with learning rate `0.0001`;
- one optimizer update every four completed transitions;
- hard target synchronization every `10,000` optimizer updates.

These choices are specified in [RESEARCH.md](C:/projects/quickdraw-AI/RESEARCH.md:363) and [ADR-0006](C:/projects/quickdraw-AI/docs/decisions/ADR-0006-bdq-and-joint-action-control.md:1).

### The important scientific caveat

Branching assumes that the joint action can be usefully represented through branch-level advantages. That may fail if movement and shooting have strong nonlinear interactions.

The project therefore registers a six-joint-action Double DQN as a Basic benchmark control. This is excellent scientific practice: the factorization is treated as an empirical assumption, not hidden as a free advantage.

The eventual comparison can answer:

> Does branching preserve performance while reducing action-space complexity, or does it lose important cross-branch interactions?

## 4. Why experience replay?

Experience replay serves two roles.

### Standard RL role

Sequential game experience is highly correlated. Consecutive frames often show almost the same scene and action. Training directly on consecutive transitions can produce unstable updates and poor use of data.

Replay helps by:

- decorrelating updates;
- reusing past experience;
- approximating independent sampling;
- stabilizing nonlinear function approximation;
- allowing the optimizer to learn from rare events more than once.

### Scientific infrastructure role

In quickDraw, replay is also part of the reproducibility contract. The project records:

- transition order;
- actions and masks;
- rewards;
- terminal/truncation flags;
- replay cursor and size;
- random-generator state;
- sampled replay indices.

That makes it possible to ask not merely “did the network produce similar results?” but:

> Did two fresh processes reconstruct the same replay contents, sample the same transitions, and perform the same next optimizer update?

This is why replay state is included in checkpoints rather than treating it as disposable implementation detail.

## 5. Why lossless, bounded replay?

Raw replay is expensive. Two full float32 observations per transition at `[84,84,4]` would require approximately:

```text
100,000 transitions × 84 × 84 × 4 × 4 bytes × 2
≈ 22.6 GB
```

before Python overhead.

The project therefore stores:

- exact float32 frames interned by content;
- eight frame references per transition;
- columnar metadata for actions, rewards, masks, and terminal flags;
- reference counts to reclaim frames after ring-buffer overwrite.

This exploits the fact that adjacent four-frame stacks overlap heavily while preserving exact numerical values. Lossy compression or quantization would change the replay distribution and could invalidate deterministic comparisons.

A deterministic `4 GiB` accounting ceiling was added. The accepted long-horizon run used:

- 49,996 transitions;
- 81 unique frames;
- 12,037,184 accounted replay bytes.

The design and rationale are recorded in [ADR-0012](C:/projects/quickdraw-AI/docs/decisions/ADR-0012-lossless-bounded-replay.md:1).

This is not being presented as a novel compression algorithm. The contribution is that memory engineering is integrated with reproducible RL semantics rather than silently changing the data seen by the optimizer.

## 6. Why use the ML-Agents low-level API instead of its trainer?

The project initially explored the high-level ML-Agents trainer and trajectory abstractions. That path was abandoned because it obscured the exact Unity environment-step boundary and complicated ownership of:

- replay;
- Double-DQN targets;
- branch masks;
- terminal/truncation handling;
- optimizer cadence;
- checkpoint state.

The current architecture uses ML-Agents for:

- sensor and action transport;
- Unity episode boundaries;
- branched action interfaces;
- environment communication.

Python directly owns:

- transition collection;
- replay;
- target computation;
- optimization;
- exploration;
- checkpoints.

For each submitted action, the collector stores:

```text
(observation, action, current masks)
```

When the same agent next appears in `DecisionSteps` or `TerminalSteps`, exactly one immutable transition is completed.

This creates a clean Markov transition boundary and prevents hidden framework behavior from becoming part of the algorithm. The rationale is in [ADR-0007](C:/projects/quickdraw-AI/docs/decisions/ADR-0007-direct-llapi.md:1).

The R3C-to-R3D transition is especially useful to discuss in an SOP: the team tried a more abstract framework, identified that it weakened observability and correctness, and deliberately replaced it with a narrower interface.

## 7. Why distinguish terminals from truncations?

This is a mathematically important detail.

For a true terminal state:

```text
target = reward
```

There is no future value to bootstrap.

For a time-limit truncation:

```text
target = reward + γ × next-state value
```

The final observation still represents a valid continuing state.

ML-Agents exposes an interrupted episode through `TerminalSteps`, where the ordinary next `DecisionStep` mask is unavailable. quickDraw therefore sends a Unity-authored final-state mask through a dedicated side channel.

Python never infers action legality from privileged Unity state.

This prevents two serious errors:

1. bootstrapping from illegal next actions;
2. treating time-limit truncations as absorbing terminals.

That decision is recorded in [ADR-0011](C:/projects/quickdraw-AI/docs/decisions/ADR-0011-terminal-truncation-mask.md:1).

For a PhD audience, this is worth emphasizing because it demonstrates that the project is concerned with the actual Bellman target, not only with neural-network code.

## 8. Observation and action contracts

The Basic policy receives only:

- an `[84,84,4]` grayscale frame stack;
- float32 values in `[0,1]`;
- frames ordered from oldest to newest;
- no target coordinates, object IDs, scene matrices, or privileged state.

The four-frame stack supplies short temporal context in a partially observed visual environment. At reset, the first post-reset frame is copied into all four channels, preventing leakage from the previous episode.

The wire format is HWC, while the neural encoder converts to CHW at one explicit boundary. This prevents silent layout changes between Unity and Python.

The action interface is semantic and stable, while branch-local indices are separately versioned. The shared actuator owns:

- movement;
- action holding;
- ammunition;
- hitscan;
- cooldown;
- reload;
- pickups;
- masks;
- reflex overrides.

The policy does not directly manipulate Unity objects. This keeps learning decisions separate from mechanics and makes all conditions comparable.

## 9. The shared actuator and shared mechanical aim

A major fairness decision is that all conditions must use the same mechanics.

In Basic, all policies use the same:

- fixed crosshair;
- camera-center hitscan;
- movement slots;
- action masks;
- actuator.

In the planned strategic environment, every condition uses the same:

- target resolver;
- one-frame look-at/snap;
- hitscan;
- damage;
- cooldown;
- reload;
- pickup;
- collision rules.

The LLM and reflex do not receive a special aim path or privileged target coordinates.

This matters because otherwise an apparent improvement could be caused by hidden aim assistance rather than temporal hierarchy. See [ADR-0010](C:/projects/quickdraw-AI/docs/decisions/ADR-0010-shared-mechanical-aim.md:1).

## 10. Structured perception and event-driven reflexes

The early `Test_Arena` architecture contains several subtle but important choices.

### Threats flow through perception

An aiming event first becomes a structured stimulus containing source, origin, direction, timestamp, range, and aiming state. It then passes through field-of-view, occlusion, suspicion, orientation, and rearming logic.

A direct center-camera raycast is allowed only as an explicit debug bypass.

This prevents the experiment from making perception decorative. The agent should react because the perception model confirms a threat, not merely because a ray happened to hit geometry. See [ADR-0002](C:/projects/quickdraw-AI/docs/decisions/ADR-0002-stimulus-through-perception.md:1).

### Reflexes are edge-triggered

Threat confirmation and interruption happen on state transitions, not every frame. This avoids:

- repeated commands;
- compounded displacement;
- duplicate telemetry;
- invalid latency counts.

See [ADR-0003](C:/projects/quickdraw-AI/docs/decisions/ADR-0003-edge-triggered-reflex.md:1).

### Command time is not visible-response time

The project records both:

- `reflex_commanded`;
- `visible_motion_started`.

Visible onset requires actual position or rotation change, observed after the command. This avoids claiming low latency merely because a function was called quickly.

The original fixture uses thresholds of `0.01 m` or `1°`. Its p50/p95 targets are regression criteria for the fixture, not a claimed latency distribution. See [ADR-0004](C:/projects/quickdraw-AI/docs/decisions/ADR-0004-command-vs-visible-motion.md:1).

The actual research `EvadeTelegraphedShot` remains planned; the current accepted evidence does not establish reflex effectiveness.

## 11. Why constrain the LLM to categorical strategy?

The planned LLM does not issue frame-level actions or free-form movement commands.

It receives a compact abstract snapshot every two seconds and returns a validated categorical goal such as:

- `BALANCED`;
- `OFFENSIVE_RUSH`;
- `DEFENSIVE_RETREAT`;
- `SEEK_HEALTH`;
- `CONSERVE_AMMO`.

The LLM cannot:

- call the actuator;
- alter rewards;
- change action legality;
- inspect raw frames;
- directly aim or shoot;
- block physics or reflex execution.

Networking and generation happen asynchronously. Unity applies only validated, current results on the main thread. Timeouts, stale results, malformed JSON, and out-of-order responses are discarded; the last valid directive remains active.

This design makes the research question about strategic intervention rather than language-model text-to-control latency. It also makes failure behavior testable before introducing a real model.

The LLM runtime is not implemented or empirically evaluated yet. This is currently a registered research design, described in [ADR-0008](C:/projects/quickdraw-AI/docs/decisions/ADR-0008-async-categorical-llm.md:1).

## 12. Why include a rule director?

An LLM condition receives a structured strategic snapshot. If it outperforms a fixed goal, that improvement might come from the snapshot-and-goal interface rather than language-model reasoning.

The planned deterministic rule director therefore receives exactly the same snapshot and emits exactly the same directive schema.

The comparison becomes:

```text
LLM director vs same-information rule director
```

rather than:

```text
LLM with rich state vs fixed baseline with no state
```

A strong LLM-specific claim requires at least `0.05` utility improvement over the rule director with a paired confidence interval above zero.

This is one of the strongest experimental-design decisions in the project. It shows awareness of confounding and ablation quality. See [ADR-0009](C:/projects/quickdraw-AI/docs/decisions/ADR-0009-rule-director-control.md:1).

## 13. Seeds, pairing, and statistical design

The project uses separate seed domains for:

- environment scenarios;
- policy initialization;
- replay sampling;
- exploration;
- evaluation;
- opponent behavior;
- statistical bootstrap.

This avoids accidentally coupling “which scenario occurred” with “which policy initialization occurred.” The rule is explicit: training and held-out scenario seeds must be disjoint, while paired conditions reuse the same scenario seeds.

The planned evaluation uses:

- five independent policy-training seeds;
- 100 paired held-out scenarios per condition;
- the same learned checkpoint across ablated runtime conditions;
- a hierarchical bootstrap that resamples policy seeds first and scenarios second.

This recognizes that episodes are not independent if they share a trained policy seed. A flat confidence interval over episodes would overstate certainty.

The full factorial design is:

1. BDQ;
2. BDQ + reflex;
3. BDQ + LLM;
4. BDQ + reflex + LLM;

with rule-director controls for the relevant cases. See [RESEARCH.md](C:/projects/quickdraw-AI/RESEARCH.md:663).

## 14. Checkpointing, live handoff, and ONNX export

A checkpoint is not just a neural-network weight file. It contains:

- online and target networks;
- optimizer state;
- replay contents;
- selector and RNG state;
- counters;
- settings;
- seed identity;
- integrity hashes;
- provenance.

The reason is scientific: restoring only weights does not reproduce the next learning step. The optimizer, replay distribution, and random streams are part of the algorithmic state.

The accepted R3P/R3Q/R3R/R3S sequence progressively verified:

1. Python-only checkpoint restoration;
2. restoration from a live Unity-derived boundary;
3. deterministic continuation through the first target synchronization;
4. live Unity-process handoff after a fresh trainer restore;
5. ONNX/CPU inference equivalence.

The strongest accepted result is R3R/R3S:

- `49,996` transitions;
- `10,000` optimizer updates;
- exactly one target synchronization;
- two independent workers with byte-identical traces/checkpoints;
- live handoff to transition `49,997`;
- Python/ONNX maximum Q-value difference of `2.38 × 10⁻⁷`.

See [R3R evidence](C:/projects/quickdraw-AI/docs/evidence/R3R.md:79) and [R3S evidence](C:/projects/quickdraw-AI/docs/evidence/R3S.md:35).

This is not evidence of a useful policy. It is evidence that the research system can preserve and transport a policy state correctly.

## Milestone progression

| Phase | Architectural purpose | Accepted result |
|---|---|---|
| Tasks 1–8 / R0 | Deterministic control, perception, interruption, visible onset, telemetry | 41 Unity Play Mode tests and standalone build |
| R1 | Contracts, transport, runtime identity, backend checks | Two exact 10,000-decision transport traces; CPU measured at 107.4–108.6 decisions/s |
| R2A | Small visual-control benchmark and baselines | Random/scripted traces reproduced; scripted baseline completed 12 episodes with aligned hits and no misses |
| R3A–R3B | Pure Python BDQ, replay, targets, optimizer, schedule | Deterministic algorithmic foundation |
| R3C–R3D | Decide how to connect Unity to custom RL | High-level trainer retired; direct LLAPI adopted |
| R3E–R3H | Establish seeded collection and real Unity-derived updates | Warmup and first live optimizer updates accepted |
| R3I–R3O | Integrate scheduled exploration and continue update path | Five scheduled updates accepted; target synchronization still intentionally deferred |
| R3N | Make replay exact and memory-bounded | Accepted lossless replay accounting and frozen-trace regression |
| R3P–R3Q | Verify checkpoint persistence | Fresh-process state and replay-sample parity |
| R3R | Cross the first target-sync boundary | 49,996 transitions, 10,000 updates, one synchronization |
| R3S | Verify live handoff and serving boundary | Live Unity continuity and ONNX/CPU parity |
| R3T | Current implementation task | Five-seed campaign machinery exists, but no accepted campaign result yet |

The current repository state explicitly says that R3T training, held-out evaluation, and learned-policy effectiveness remain incomplete. See [STATE.md](C:/projects/quickdraw-AI/STATE.md:19).

## The actual claims a PhD admissions panel should hear

A strong explanation would be:

> I did not begin by claiming that a complex hybrid agent was effective. I first built a deterministic visual-control substrate and separated the system into independently testable temporal layers. I chose Branching Double DQN because the FPS action space is naturally factored into movement, combat, and utility, but I also registered a joint-action control because branching introduces an explicit factorization assumption. I then implemented a direct Unity low-level API collector, lossless replay, exact checkpointing, and process-level reproducibility so that later policy comparisons would not be confounded by transport, masking, or random-state drift. The current accepted results show exact continuation through 49,996 transitions and 10,000 updates, live-process handoff, and ONNX inference parity. The central behavioral hypothesis—whether reflexes and delayed strategic reasoning improve combat utility—remains the next experiment rather than an already-established conclusion.

That framing demonstrates:

- understanding of inductive bias;
- awareness of action-space complexity;
- concern for Bellman-target correctness;
- causal experimental design;
- reproducibility discipline;
- respect for negative and incomplete evidence.

Avoid saying:

- “The LLM improved the agent” — no LLM evaluation exists.
- “The agent converged” — no accepted convergence result exists.
- “BDQ outperformed DQN” — the joint-action comparison has not been run.
- “The hybrid agent reacts faster” — the strategic reflex study has not been run.
- “quickDraw reproduces ViZDoom” — it is only inspired by the ViZDoom Basic Scenario.

The academically honest position is that quickDraw has already produced a serious research instrument and a validated RL systems foundation. The scientific performance result is deliberately still open.
