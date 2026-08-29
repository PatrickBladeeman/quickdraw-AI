# quickdraw-AI — Registered Research Contract

## Purpose and authority

This file is the canonical human-readable scientific design for quickdraw-AI.
It defines the research question, registered interventions, fairness rules,
environment contracts, learning defaults, outcomes, hypotheses, analysis, and
claim boundaries. It is a design contract, not an implementation-status or
results ledger.

- Current implementation truth belongs in [STATE.md](STATE.md).
- Validation results, hashes, provenance, and negative evidence belong in the
  [evidence index](docs/evidence/README.md).
- Code ownership and runtime boundaries belong in [ARCH.md](ARCH.md).
- The currently authorized unit of work belongs in [TASK.md](TASK.md).
- Major ordering and planned milestones belong in [ROADMAP.md](ROADMAP.md).

The machine-readable contracts under `Research/` remain executable companions
to this document. In particular:

- `Research/configs/research-contracts-v1.json` freezes cross-cutting timing,
  observation, action, reward, reset, seed, side-channel, and artifact rules.
- `Research/basic/basic-contract-v1.json` freezes the implemented Basic
  environment.
- The versioned `bdq-...-contract-v1.json` files under `Research/trainer/`
  freeze the BDQ learning and collection boundaries.

If this document and a machine-readable contract disagree, scientific work
must stop until the discrepancy is resolved. Do not silently select the more
convenient value.

### Change control

A registered scientific choice may change only with all of the following:

1. explicit user authorization for the design change;
2. a decision record under `docs/decisions/` explaining the rationale,
   alternatives, compatibility effect, and evidence invalidated;
3. synchronized updates to this file and every affected machine-readable
   contract, schema, configuration, command, and analysis;
4. a new major contract version for a breaking field, enum/index,
   preprocessing, reward, reset, timing, intervention, outcome, or threshold
   change; and
5. new comparison runs when the change affects experimental comparability.

Registered thresholds and the primary outcome must not be changed after final
results are viewed. A post-registration variation must retain the original
confirmatory analysis and be labeled exploratory; it must never overwrite or
retroactively redefine the registered result.

## Mission, terminology, and research question

Build and evaluate a reproducible Unity FPS agent whose control is separated
across four timescales:

1. a shared deterministic actuator executes mechanics at the 50 Hz physics
   rate;
2. an optional event-driven reflex may preempt movement by the next physics
   step for a confirmed imminent threat;
3. a visual goal-conditioned Branching Double Deep Q-Network selects tactical
   action intents every five physics steps, or 10 Hz; and
4. an optional local LLM evaluates a compact strategic snapshot asynchronously
   every two seconds, or 0.5 Hz.

DQN and BDQ are deep reinforcement learning. The accurate framing is
deterministic control + deep reinforcement learning + local LLM. The Basic
benchmark is a Unity hitscan analogue inspired by the ViZDoom Basic Scenario;
it is not a claim to reproduce ViZDoom's published numeric results.

The research question is whether temporal partitioning can improve combat
decisions while keeping urgent visible reaction latency independent of slow
strategic inference.

## Central thesis and registered hypotheses

> Under identical visual observations, action interfaces, mechanical
> actuators, learned policy weights, opponent scripts, and evaluation seeds, a
> temporally partitioned FPS agent—combining a goal-conditioned Branching
> Double DQN, an event-driven deterministic evade reflex, and an asynchronous
> local-LLM strategic director—will improve combat utility over BDQ alone while
> preserving urgent reaction latency independently of LLM inference latency.

The registered hypotheses are:

- **H1 — utility:** Full hybrid minus BDQ-only mean combat utility is at least
  `0.10`, with the paired 95% hierarchical-bootstrap confidence interval above
  zero.
- **H2 — reflex protection:** Reflex-enabled conditions reduce damage received
  per telegraphed shot, with the paired 95% confidence interval below zero.
- **H3 — timing isolation:** Full-hybrid telegraph-to-visible-evade p95 is at
  most `50 ms` and is within one `20 ms` physics step of BDQ+reflex at every
  injected LLM delay of `0`, `500`, `1000`, `2000`, and `3000 ms`. Each delay
  tier must contain at least 200 reflex events.
- **H4 — strategic intervention:** The LLM factorial main effect is positive.
  A strong LLM-specific claim additionally requires at least `0.05` utility
  improvement over the same-information deterministic rule director, with the
  paired 95% confidence interval above zero.

If the hierarchy beats BDQ but the LLM does not beat the rule director, the
supported conclusion is that the hierarchy helps; LLM-specific value was not
demonstrated.

## Primary outcome

Combat utility is calculated after the episode and must not be silently
substituted for the training reward:

```text
U = episode_outcome
  + 0.25 * (damage_dealt - damage_taken) / 100
  - 0.05 * missed_shot_fraction
  - 0.05 * wasted_resource_fraction
```

`episode_outcome` is:

- `+1` when the opponent is eliminated;
- `-1` when the agent dies; and
- `0` on timeout.

Episode outcome, deaths, damage dealt, damage taken, shots, hits, misses,
reloads, pickups, survival time, missed-shot fraction, and wasted-resource
fraction must always be stored and reported separately. The exact denominators
for the two fractions remain not yet registered and must be frozen before R7
data collection.

## Experimental invariants and fairness

The following are controlled across applicable comparisons:

- identical camera transform, projection, render settings, preprocessing,
  channel order, normalization, frame cadence, and reset behavior;
- identical policy observation and categorical-goal encoding;
- identical typed action tuple, action-index tables, and mechanical masks;
- identical shared actuator, target resolver, look-at/snap, hitscan, damage,
  cooldown, reload, pickup, and collision paths;
- identical learned checkpoint for every condition associated with a given
  policy-training seed;
- identical scripted-opponent configuration and schedule;
- paired held-out scenario seeds in every condition;
- identical shared terminal and damage rewards;
- the same compact snapshot and directive schema for the LLM and rule director;
  and
- infrastructure-validity exclusions declared without reference to
  performance.

Mechanical aim is a controlled variable, not a learned intervention. No
optional layer receives a different aim path or additional target data. Only
mechanically impossible actions may be masked; a director must not mask a
physically legal action merely because it conflicts with a strategy.

Final evaluation is greedy and performs no weight, replay, epsilon, reward, or
optimizer update. Training scenarios and held-out evaluation scenarios are
disjoint.

## Temporal hierarchy and clocks

- Unity fixed timestep: `0.02 s`.
- Deterministic actuator rate: 50 Hz.
- Policy decision interval: five fixed steps.
- BDQ decision rate: 10 Hz.
- Strategic snapshot/request interval: `2.0 s`.
- Strategic rate: 0.5 Hz.
- Gameplay and cross-stage clock: `Time.realtimeSinceStartup`.
- Simulation step, completed-transition count, and episode counters are
  recorded so wall-clock time is not conflated with simulation or learning
  progress.

The actuator holds the last accepted tuple between policy decisions. A reflex
may preempt only its movement branch for a bounded duration and then restores
the latest held BDQ movement intent. Strategy can publish only a validated
future-facing categorical goal. It cannot call the actuator, change reward,
or change action legality.

Command dispatch and observed visible motion are distinct events and latency
stages. A command timestamp alone is never evidence of a visible reaction.

## Observation contract

The primary learned observation is:

- shape `[84,84,4]` on the wire;
- HWC wire layout and CHW encoder layout;
- `float32` values in `[0.0,1.0]`;
- one grayscale channel per frame using Rec. 601 luma;
- four frames ordered oldest to newest; and
- no compression.

At reset, one post-reset frame is captured and copied into all four channels
before the first decision. No prior-episode frame may leak into the new stack.

Basic receives only the visual stack. Strategic receives the identical stack
plus a five-category strategic-intent one-hot encoding. Prohibited learned
inputs are object IDs, target coordinates, debug labels, raw scene matrices,
and the LLM snapshot. The LLM never receives policy frames.

## Action contract

Stable semantic values are:

| Branch | Values |
| --- | --- |
| Movement | `Stay=0`, `Forward=1`, `Backward=2`, `Left=3`, `Right=4` |
| Combat | `Idle=0`, `Shoot=1` |
| Utility | `Idle=0`, `Reload=1`, `Interact=2` |

Basic uses branch-local movement indices `[Stay=0, Left=1, Right=2]`, combat
indices `[Idle=0, Shoot=1]`, and utility fixed to `Idle`. Strategic uses the
complete `[5,2,3]` branch sizes. These branch-local tables intentionally differ
from the stable semantic movement enum and must be versioned and tested.

In ML-Agents action masks, `true` means unavailable. The Basic joint-index
sanity mapping is `movement_index * 2 + combat_index`.

The shared actuator is the exclusive path from action intent to mechanics. It
owns collision-conscious translation, action holding, cooldown, ammunition,
hitscan, damage, reload, pickup interaction, impossible-action masks, reflex
override application/completion, and applied/rejected events. It must not
inspect Q-values, prompts, LLM text, training rewards, or experimental labels,
apart from the explicit reflex-enable condition flag.

## Environment contracts

### `Test_Arena` deterministic regression fixture

`Test_Arena` preserves the implemented player-control, patrol, soft-perception,
one-shot interruption, `Flinch_StepBack`, visible-onset, and typed-telemetry
substrate. Its confirmed-threat-to-visible-motion regression targets are:

- p50 below `150 ms`;
- p95 below `250 ms`; and
- reflex selection/command execution substantially below `1 ms`.

These fixture targets are distinct from H3's strategic telegraph-to-visible-
evade threshold. Direct camera-hit threat confirmation is debug-only and is
disabled in evaluation.

### Basic visual-control benchmark

The registered identity is:

- schema `quickdraw.research-basic.v1`;
- behavior `QuickDrawResearchBasic`;
- scene `Assets/_Project/Scenes/Research_Basic.unity`;
- scenario seed `31001`; and
- 12 registered baseline episodes.

The environment is a narrow primitive room. The agent begins at the south end
in lateral slot `0`; the target appears near the north end in one of nine slots
from `-4` through `4`, spaced `0.75` world units apart. Target placement is the
unsigned 32-bit `quickdraw.basic-target-slot.v1` hash of the scenario seed and
zero-based episode index, modulo nine.

Basic mechanics are:

- action branches `[3,2]`: movement `[Stay,Left,Right]` and combat
  `[Idle,Shoot]`;
- movement is applied once at the policy decision before `Shoot` is resolved;
- only outward movement at the two lateral boundaries is masked;
- a fixed visible crosshair and the center-camera ray identify the same
  hitscan;
- ammunition capacity `300`;
- shot cooldown `0` decisions; and
- hitscan distance `40.0` world units.

Basic reward is additive:

- `-0.01` per decision;
- `+1.0` for a hit; and
- `-0.02` for a missed shot.

`target_hit` is a true terminal. `decision_limit` at exactly 300 decisions is a
truncation. Infrastructure invalidity is not an episode outcome. A true
terminal does not bootstrap; a registered decision-limit truncation does and
therefore requires the Unity-authored final-state action mask.

Reset restores agent slot, target placement, ammunition, cooldown, decision,
shot, miss, reward, policy-runner telemetry, deterministic random state, and
the post-reset four-channel frame stack.

Registered rendering values are:

- Universal Render Pipeline with `Universal Render Pipeline/Lit` world
  materials;
- shadowless directional light at Euler `[50.0,-30.0,0.0]`, color
  `[1.0,0.95686275,0.8392157,1.0]`, intensity `1.25`;
- floor color `[0.045,0.06,0.08,1.0]`;
- wall color `[0.28,0.38,0.5,1.0]`;
- target color `[1.0,1.0,1.0,1.0]`;
- agent color `[0.16,0.2,0.24,1.0]`; and
- unlit crosshair color `[0.1,0.85,0.95,1.0]`, segment length `0.006`,
  thickness `0.001`, center offset `0.006`, and camera depth `0.11` world
  units.

Baseline policies use the same LLAPI action/actuator path:

- `random-visual-v1`, seed `41001`, samples each branch uniformly from legal
  actions;
- `scripted-visual-v1`, seed `41002`, thresholds the newest grayscale frame,
  moves toward the bright-target centroid, and shoots only when centered,
  without privileged target state; and
- two fresh runs per policy must produce structurally and numerically identical
  canonical traces for the registered seeds.

Basic learned-policy acceptance requires:

- at least four of five BDQ seeds reaching at least 90% success over 500
  held-out target-placement seeds;
- every passing seed exceeding random-policy success by at least 30 percentage
  points;
- the six-joint-action Double DQN comparison being reported even if BDQ
  performs worse; and
- every model being traceable to its seed, configuration, learning curve,
  checkpoint, and hash.

The slot-based Basic benchmark remains the control through canonical R3. A
gradual-motion variant must use a separately versioned contract and separately
trained/evaluated checkpoint. It may retain the discrete
`[Stay,Left,Right]` branch while holding lateral intent across fixed steps; it
must not be called a continuous action space or silently replace Basic.

### Strategic combat benchmark

The registered strategic branches are:

- movement `[Stay,Forward,Backward,Left,Right]`;
- combat `[Idle,Shoot]`; and
- utility `[Idle,Reload,Interact]`.

Registered mechanics are:

- agent and opponent maximum health `100`;
- `20` damage per valid hitscan hit;
- six-round magazine and 18 reserve rounds;
- `0.25 s` shot cooldown;
- `1.5 s` reload;
- `30 s` episode limit;
- named collision-valid cover with line-of-sight tests;
- bounded health/ammunition pickups through `Interact`;
- one seeded scripted opponent with deterministic configuration and schedule;
  and
- one structured imminent-shot telegraph exactly `400 ms` before every
  scripted opponent shot.

When `Shoot` is selected, all conditions use the same nearest-visible-legal-
target resolver, one-frame look-at/snap, and hitscan. Masks cover only
mechanically impossible actions, such as reload with a full magazine or no
reserve, or interaction without a legal object in range.

The five strategic-intent categories are `BALANCED`, `OFFENSIVE_RUSH`,
`DEFENSIVE_RETREAT`, `SEEK_HEALTH`, and `CONSERVE_AMMO`.

Strategic training uses a deterministic teacher so every goal receives
balanced scenario coverage, randomizes reflex availability, and excludes live
LLM calls. Goal-specific potential shaping may reward progress toward enemy
pressure, cover, health, or ammunition without replacing shared terminal and
damage rewards. The potential definitions and coefficients must be registered
before strategic training.

One strategic checkpoint per policy-training seed is reused unchanged across
all runtime ablations for that seed.

## Branching Double DQN contract

### Runtime and collection boundary

The registered stack is Unity ML-Agents `4.0.0`, Python `3.11.13`,
`mlagents-envs` `1.1.0`, NumPy `1.23.5`, and PyTorch `2.12.0+cpu` for the CPU
training reference. Python `3.10.12` remains the historical official
compatibility baseline. A separately accepted batch-size-one ROCm inference
fixture is not by itself evidence of ROCm training support.

ML-Agents supplies sensors, branched-action transport, episode boundaries, and
exported-model inference. The Python BDQ loop directly owns synchronous LLAPI
collection, replay, targets, and optimization because the built-in trainers
are not DQN.

For each agent, the collector stores `(observation, action, current masks)`
when it sends a decision. When that agent next appears in `DecisionSteps` or
`TerminalSteps`, it completes exactly one immutable replay transition using
the delivered reward and next observation. Ordinary continuation gets the next
mask from the next `DecisionStep`; a true terminal uses an irrelevant all-
available sentinel; a truncation receives the authoritative final-state mask
through the dedicated Unity side channel. Python must not infer legality from
privileged scene state.

### Network

```text
4 × 84 × 84 grayscale stack
→ Conv(32, 8×8, stride 4)
→ Conv(64, 4×4, stride 2)
→ Conv(64, 3×3, stride 1)
→ 512-unit shared representation (+ categorical goal for strategic policy)
→ scalar dueling value V(s,g)
→ one mean-centered advantage head A_i(s,g,a_i) per branch
→ Q_i = V + A_i - mean(A_i)
```

Basic advantage outputs are `[3,2]`. Strategic adds the five-category goal at
the shared representation. A joint-action Double DQN with six tuple Q-values
is a Basic branch-factorization sanity control, not the primary architecture.

### Replay, targets, and loss

- Replay capacity: `100000`.
- Replay warmup: `10000` completed validated transitions.
- Sampling: uniform without replacement.
- Replay RNG: `numpy.random.Generator.PCG64`.
- Batch size: `64`.
- Discount: `gamma=0.99`.
- Double-DQN selection network: online.
- Double-DQN evaluation network: target.
- Target scope: per branch.
- True-terminal bootstrap: disabled.
- Registered-truncation bootstrap: enabled.
- Next-state mask applies to the online argmax.
- Loss: Huber with `beta=1.0`.
- Reduction: mean over batch and branches.

Replay transitions contain observation, branch action, reward, next
observation, current masks, next masks, terminal flag, and truncation flag.

The current lossless replay representation stores exact C-contiguous
`float32` `[84,84]` channel frames by content and keeps eight `uint64` frame
references plus columnar metadata per transition. Frames use their exact
C-contiguous bytes as keys, reference counting reclaims orphaned frames after
ring overwrite, and reconstructed batches remain bit-exact HWC
`[84,84,4]` `float32` values. Lossy quantization and lossy compression are
prohibited.

Registered storage accounting is:

- frame payload `28224` bytes;
- per-frame accounting reserve `1024` bytes;
- metadata-array accounting reserve `256` bytes;
- fixed accounting reserve `65536` bytes;
- 10 metadata arrays;
- metadata payload at capacity `9600000` bytes;
- metadata accounted at capacity `9668096` bytes;
- maximum accounted storage `4294967296` bytes, or 4 GiB;
- registered Basic upper bound 81 distinct render states and `12037184`
  accounted bytes;
- conservative 100004-distinct-frame projection `2934585088` accounted bytes;
  and
- maximum unique frames within the registered budget `146515`.

Caller-owned transitions, sampled batches, interpreter/module baseline,
networks, optimizer state, and Unity process memory are outside that accounting
ceiling. A valid insertion that would exceed the ceiling raises `MemoryError`
before any visible replay mutation.

### Optimizer and exploration

- Optimizer: Adam.
- Learning rate: `1e-4` (`0.0001`).
- Update interval: every four completed transitions.
- Updates per eligible boundary: one.
- Hard target synchronization: every `10000` optimizer updates, after the
  optimizer step at the divisible boundary.
- Target initialization: exact deep copy of online.
- Online network receives gradients; target network does not.

An update requires all of:

```text
completed_transition_count >= 10000
replay_size >= 10000
completed_transition_count % 4 == 0
```

Training epsilon is a stateless function of completed replay transitions:

```text
epsilon = 1.0
        + (0.1 - 1.0)
        * clamp((completed_transition_count - 10000) / 100000, 0, 1)
```

Therefore:

- epsilon is `1.0` through count `10000`;
- epsilon is `0.55` at count `60000`;
- epsilon reaches `0.1` at count `110000`; and
- epsilon remains clamped at `0.1` afterward.

The selector uses exploration seed `61001`, a CPU `torch.Generator`, and
branch-wise uniform sampling over ascending unmasked indices. At epsilon
`1.0`, it preserves the exploration RNG stream without an unused network
forward pass. Exploratory validation may use epsilon `0.05`; final evaluation
uses epsilon `0.0`.

Gradient clipping is not a registered default. It may be added only if needed,
documented, and approved under change control.

## Seed contract

All seeds are signed 31-bit integers in `[0,2147483647]`. Registered categories
are policy initialization, replay sampling, exploration, scenario, opponent,
evaluation, and analysis bootstrap.

Rules:

- store every category explicitly in the run manifest;
- never derive a seed from an object name or runtime hash;
- keep training and held-out evaluation scenario seeds disjoint; and
- reuse identical policy and scenario seeds in paired conditions.

Registered exact seeds are:

| Purpose | Seed or seeds |
| --- | --- |
| R1 smoke/reference scenario | `21001` |
| Fixed-policy parity initialization | `11001` |
| Basic scenario | `31001` |
| Basic random visual baseline | `41001` |
| Basic scripted visual baseline | `41002` |
| BDQ policy training | `51001`, `51002`, `51003`, `51004`, `51005` |
| BDQ exploration | `61001` |

The exact strategic held-out scenario list, opponent-seed list, analysis-
bootstrap RNG seed, and live-LLM seed are not yet numerically registered. They
must be frozen before the corresponding data are generated.

## Deterministic evade reflex

`EvadeTelegraphedShot` subscribes to the structured imminent-shot event. When
enabled and off cooldown, it preempts movement with one deterministic,
collision-safe `0.6 m` lateral evade. Its cooldown is exactly one second.

Direction and clearance use the same physics information available to the
shared actuator. The reflex cannot aim, shoot, change combat or utility intent,
select or edit a strategic goal, query LLM state or Q-values, alter reward, or
perform waits, coroutines, allocation-heavy serialization, file I/O,
networking, or model inference before motion.

Duplicate telegraphs and cooldown-suppressed events cannot move the agent
twice. Required records include telegraph observed, accepted/suppressed,
command, requested/applied displacement, collision flags, visible onset,
damage outcome/avoided, preemption duration/end, deadline miss, and restoration
of BDQ movement control.

## Strategic directors and local LLM

All directors implement the same request/result boundary:

- fixed `BALANCED` director for LLM-off conditions;
- deterministic rule director receiving the same snapshot as the LLM;
- deterministic mock director for failure and delay tests; and
- local HTTP director for Qwen3-8B through `llama.cpp`.

### Snapshot and directive

Every two seconds, the Unity main thread captures an immutable snapshot with:

- quantized agent health and ammunition;
- visible-enemy count, distance, and health categories;
- nearest-cover and pickup availability/distance categories;
- current directive;
- episode ID;
- monotonic request sequence; and
- timestamp.

Raw frames and continuous object matrices are excluded.

Schema-constrained output contains `strategic_intent`, `priority_target`, and
`engagement_rule`. Only coherent templates are valid:

- `BALANCED`;
- `OFFENSIVE_RUSH` + enemy + engage;
- `DEFENSIVE_RETREAT` + cover + hold fire unless threatened;
- `SEEK_HEALTH` + health pickup + disengage when possible; and
- `CONSERVE_AMMO` + valid enemy opportunity + high-confidence fire only.

The validated intent becomes a categorical BDQ goal input. `priority_target`
and `engagement_rule` support validation, telemetry, deterministic-teacher
parity, and rule-director parity; they never call mechanics directly.

### Local-model and transport defaults

- Model family: quantized Qwen3-8B.
- Mode: non-thinking/instruction.
- Server: version-pinned local `llama.cpp` HTTP service.
- Preferred backend: validated Vulkan.
- Request cadence: two seconds.
- Timeout: five seconds.
- Result TTL: four seconds.
- Sequence: monotonic.
- Temperature: zero.
- Seed: recorded.
- Output: small JSON-only token budget.

Record the exact server version/commit, model source, quantization, model
SHA-256, prompt, JSON schema, context, generation settings, seed, token cap,
and hardware. Model weights remain outside Git.

Snapshot capture and result application occur on the Unity main thread. HTTP,
generation waiting, and parsing run asynchronously without Unity-object access
and publish plain results through a thread-safe queue.

Malformed, incoherent, stale, timed-out, out-of-order, and prior-episode
results are discarded. The last valid directive remains active. If no valid
directive exists, the fallback is `BALANCED`.

The mock director must cover fixed output, invalid JSON, connection loss,
timeout, out-of-order completion, and injected delays of `0`, `500`, `1000`,
`2000`, and `3000 ms`.

Exact model quantization, server commit, context size, prompt, JSON token cap,
and numeric live-model seed remain not yet registered. They must be frozen
before live-model evaluation.

## Factorial evaluation protocol

The main 2×2 conditions are:

1. BDQ, fixed `BALANCED`, reflex off.
2. BDQ + reflex, fixed `BALANCED`.
3. BDQ + local LLM, reflex off.
4. BDQ + reflex + local LLM.

Secondary controls are:

1. BDQ + deterministic rule director, reflex off.
2. BDQ + deterministic rule director, reflex on.

For each of the five independently trained policy seeds, run every condition
on the same 100 held-out scenario seeds. This yields 500 paired episodes per
condition. Each seed's identical final strategic checkpoint is loaded into all
conditions associated with that seed.

The delay study injects `0`, `500`, `1000`, `2000`, and `3000 ms` director
delays and requires at least 200 reflex events in each tier. Delay injection
must not enter the reflex call graph or pause physics, BDQ decisions, or the
shared actuator.

Runs may be excluded only under predeclared infrastructure-invalid criteria,
never because of poor performance. Failed, negative, null, and inconclusive
outcomes remain part of the research record.

## Analysis and reporting

Use a `10000`-resample hierarchical bootstrap. Resample policy seed first and
paired scenario seed second. Report paired effects, 95% confidence intervals,
reflex and LLM factorial main effects, their interaction, and the same-
information rule-director comparison.

Required training and policy measurements include:

- training return and success;
- learning-curve area;
- Huber loss and mean absolute TD error;
- epsilon, replay size, and Q-value summaries;
- environment steps per second and policy inference latency;
- checkpoint/configuration hashes; and
- checkpoint restore and exported-inference parity.

Required episode and combat measurements include utility and every raw utility
component, health, damage, shots, hits, misses, reloads, pickups, survival,
wasted actions, directive occupancy, terminal reason, and infrastructure
validity.

Required system measurements include frame/fixed-step time, allocations,
logger pressure, dropped events, failures, and run, episode, condition, policy,
scenario, scene, configuration, model, package, and hardware identifiers and
hashes.

Required reflex measurements include every telegraph, decision, command,
requested/applied displacement, collision, visible onset, damage outcome,
preemption, restoration, and deadline stage.

Required director measurements include every request, first-token timestamp if
available, completion, validation, application, discard reason, timeout,
fallback, directive occupancy, and goal change.

Every published number and plot must trace to a run manifest and an exact
analysis command. Report the BDQ-versus-joint-action result, shaping
sensitivity, privileged scripted mechanics, backend reproducibility limits,
and external-validity limits even when unfavorable.

## Artifact boundary

Raw JSONL, CSV, run manifests, checkpoints, model weights, model outputs,
caches, and generated plots live under the ignored `Artifacts/Experiments/`
root. Track schemas, dependency locks, configurations, scripts, curated
aggregates, selected plots, checksums, commands, conclusions, and limitations.

Do not commit model weights. A public artifact must respect model, dataset, and
asset licenses. No participant study is included.

## Registered claim boundaries and non-goals

Software-contract tests, deterministic traces, bounded smoke updates, and
backend probes are not evidence that the scientific hypotheses hold. A single
trace is not a latency distribution. Transport or fixed-policy inference
throughput is not training throughput, sample efficiency, or policy quality.

Current research-program non-goals are:

- survival or extraction systems;
- crafting or loot economies;
- multiplayer or networking;
- production art;
- procedural worlds;
- group AI;
- speech or TTS;
- unrestricted conversation;
- LLM training or fine-tuning;
- LLM frame-level control;
- hybrid-only privileged mechanics;
- strategic masks for physically legal actions;
- visible-latency claims without visible-onset observation; and
- post-hoc changes to registered thresholds without an exploratory label.

The local LLM is a bounded strategic intervention, not an actuator, tactical
policy, reward source, or legality oracle. The reflex is a bounded urgent
movement intervention, not an aiming, shooting, planning, or inference layer.

## Values that must be registered before their dependent work

The following are intentionally unresolved rather than silently inferred:

- strategic terminal/damage reward coefficients and all goal-shaping
  potentials and coefficients;
- exact strategic training-scenario, held-out evaluation, opponent, and
  analysis-bootstrap seed lists;
- exact cover geometry, pickup amounts/radii, and scripted-opponent schedule
  and difficulty parameters;
- exact definitions and denominators for `missed_shot_fraction` and
  `wasted_resource_fraction`;
- exact live-model source/revision, quantization, SHA-256, `llama.cpp` commit,
  prompt, context, generation limit, and numeric seed;
- full `priority_target` and `engagement_rule` enum/index tables;
- Basic/strategic training-duration, checkpoint-selection, stopping, and
  export-parity tolerances not already frozen by a versioned contract; and
- any gradual-motion Basic speed, bounds, persistence, reset, training, or
  evaluation values.

Register those values before generating dependent confirmatory data. Their
absence does not authorize an implementation to choose them implicitly.
