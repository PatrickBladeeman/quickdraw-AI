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
- The originally proposed first recovery controller was a finite-state machine; that unfinished task is now superseded by the approved research pivot.
- The earlier handoff deferred reinforcement learning and LLM work until the local loop was functional and measured. Tasks 1–8 supplied that deterministic substrate, so the controlling research program below now authorizes bounded deep-RL and local-LLM work.

## Current approved research program

This section is the controlling public project scope. It supersedes the older deterministic-slice summary and historical plans below wherever they conflict. The deterministic work remains an implemented regression fixture, but the active research target is now a hierarchical FPS agent combining deterministic control, deep reinforcement learning, and an asynchronous local LLM.

### Mission and terminology

Build and evaluate a reproducible Unity FPS agent with four explicitly separated timescales:

1. A shared deterministic actuator executes movement, aiming, shooting, reload, and interaction at the 50 Hz physics rate.
2. An optional event-driven reflex may preempt movement by the next physics step for a confirmed imminent threat.
3. A visual goal-conditioned Branching Double Deep Q-Network selects tactical intents every five physics steps, or 10 Hz.
4. An optional local LLM evaluates a compact strategic snapshot asynchronously every two seconds, or 0.5 Hz.

DQN and BDQ are deep reinforcement learning, not traditional machine learning. The accurate research framing is deterministic control + deep reinforcement learning + local LLM.

### Scope resolutions

- Tasks 1–8 are preserved as the completed deterministic control-and-measurement substrate.
- `Test_Arena` remains the regression fixture for player control, patrol, soft perception, one-shot interruption, `Flinch_StepBack`, visible-onset measurement, and typed telemetry.
- The old Task 9 tactical-recovery FSM is superseded before implementation and is not complete.
- Shooting, damage, health, ammunition, reload, cover, pickups, and interaction are now in scope only for named research environments.
- The first learned task is a Unity hitscan analogue inspired by ViZDoom Basic, not a claim to reproduce ViZDoom's published numeric results.
- Mechanical aim is a controlled variable implemented by one identical hardcoded actuator for all conditions.
- The primary learned policy is Branching Double DQN. A joint-action Double DQN sanity baseline tests BDQ's branch-factorization assumption on the six-action Basic task.
- The main evaluation is a 2×2 reflex-by-LLM factorial. Deterministic rule-director controls receive the same abstract strategic state as the LLM.
- The local-model default is quantized Qwen3-8B through a version-pinned `llama.cpp` server.

### Honest current state

Implemented and previously verified:

- Unity `6000.0.57f1`, URP, Input System, reproducible settings, and a successful Windows standalone build.
- The 16-by-16-unit open-top `Test_Arena` and its direct, peripheral, and occluded fixtures.
- `SimpleFPSController`, collision-aware `PatrolActivity`, `AimThreatStimulus`, `SoftFOVPerception`, one-shot interruption, and deterministic `Flinch_StepBack`.
- Separate `ReflexCommanded` and observed `visible_motion_started` events.
- Typed buffered JSONL telemetry, stage summaries, failure containment, and Domain-Reload-safe lifecycle.
- Forty-one Play Mode tests covering Tasks 1–8.
- Unity ML-Agents `4.0.0`, its locked Inference Engine `2.2.1` dependency, an isolated R1B/R1C Unity/Python communicator fixture with six focused Edit Mode tests, an isolated R1E Python 3.11 / ROCm / ML-Agents compatibility gate with six focused environment-contract tests, and the R1F fixed-policy CPU-versus-ROCm parity gate with four focused tests.
- R2A's separate `Research_Basic` scene, typed action/actuator boundary, deterministic seeded episode state, actual uncompressed `[84,84,4]` HWC Rec. 601 grayscale stack, lit high-contrast room, smaller fixed reticle with the same center-camera hitscan, Domain-Reload-safe missing-reset recovery, and schema-validated random/scripted LLAPI baselines.
- R3A's strict pure-Python BDQ foundation contract/schema, immutable seeded replay, exact visual dueling branch network, legal action masking, branch/joint mapping, Double-DQN targets, and averaged branch Huber loss, verified by 15 synthetic CPU tests without launching Unity or training a policy.
- R3B's seeded CPU optimizer scheduler and historical plugin-discovery proof. Twenty-two focused R3B tests established exact production defaults, no premature update, online-only optimization, frozen-target behavior, hard synchronization, batch-64 execution, and tensor-for-tensor repeatability. The reusable optimizer remains; the experimental trainer/settings/plugin shell is retired from the current package.
- The R3D direct-LLAPI collector and hash-bound `quickdraw.bdq-llapi.v1` contract: exact Basic behavior validation, mask-aware online-network action selection, one pending decision per agent, one-to-one immutable replay completion, and strict Unity-authored decision-limit mask transport. All 39 trainer tests and all 56 Python research tests pass. Two fresh Windows player/Python processes each inserted the same 302 transitions across one terminal and one truncated episode, performed zero optimizer/target-sync operations, preserved online/target weights, and produced byte-identical traces.
- R3E's hash-bound `quickdraw.bdq-epsilon-collection.v1` gate: fixed starting epsilon `1.0`, exploration seed `61001`, uniform branch-wise sampling from legal actions, and an exact 1,000-transition cutoff below the registered 10,000-decision replay warmup. All 47 trainer tests and all 64 Python research tests pass. Two fresh player/Python processes each crossed 18 episode resets, exercised all six action tuples, handled one authoritative truncation mask, stopped with no pending decision, performed zero optimizer updates or target synchronizations, preserved both networks, and produced byte-identical traces.
- R3F's hash-bound `quickdraw.bdq-warmup-update.v1` gate: the same fixed seeded epsilon `1.0` LLAPI collector reaches exactly 10,000 production replay transitions, performs no update through transition 9,999, and opens exactly one batch-64 Adam update at transition 10,000. All 62 trainer tests and all 79 Python research tests pass. Two fresh player/Python processes each crossed 215 episode resets, handled three truncations, exercised all six action tuples, stopped without a pending decision, produced the same finite loss `0.01628389209508896` and mean absolute TD error `0.06243317946791649`, changed the online hash from `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb` to `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e`, left the target hash unchanged, performed zero target synchronizations, and produced byte-identical traces. A separate single-run watch path connects to the Unity Editor on port 5004 or launches a visible standalone player at time scale 1, reports progress every 100 transitions by default, and writes one diagnostic trace rather than acceptance evidence.
- R3G's hash-bound `quickdraw.bdq-two-update.v1` gate: the fixed R3F trace continues through exactly 10,004 transitions and performs its second batch-64 Adam update at decision 10,004. All 69 trainer tests and all 86 Python research tests pass. Two fresh player/Python processes each crossed 215 episode resets, handled three truncations, exercised all six action tuples, and stopped without a pending decision. R3G preserves R3F's first 10,000 transitions, first loss, first TD error, and first post-update online hash exactly. Its second update has loss `0.014819225296378136`, mean absolute TD error `0.06711231172084808`, and online hash `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471`; the target remains unchanged, target synchronization stays at zero, and the two complete traces are byte-identical.
- R3H's hash-bound `quickdraw.bdq-post-update-handoff.v1` gate: the exact 10,004-transition R3G prefix and both optimizer events remain unchanged, then the twice-updated online network evaluates the live decision observation and selects one epsilon-`0.0` legal masked-greedy action. Two fresh processes each complete transition 10,005 with action `[2,1]` under movement mask `[false,true,false]`, record a maximum online-versus-frozen-target Q delta of `0.08040044084191322`, and stop with two optimizer updates, zero target synchronizations, and no pending decision. All 77 trainer tests and all 94 Python research tests pass, and the two complete traces are byte-identical. This proves the updated online weights reach live action selection, not that an effective policy has been trained.
- R3I's hash-bound `quickdraw.bdq-epsilon-schedule.v1` gate: a frozen stateless schedule derives epsilon only from the completed-transition count, keeps it at `1.0` through the 10,000-transition replay warmup, decays it linearly across the next 100,000 transitions, and clamps it at `0.1` from transition 110,000 onward. The scheduled seeded branch selector preserves physical action masks and the epsilon-`1.0` no-inference fast path without changing R3E–R3H's fixed selector. All 30 focused R3I tests, all 107 trainer tests, and all 124 Python research tests pass. No Unity process, optimizer update, target synchronization, trained weight, or effectiveness claim is part of R3I.
- R3J's hash-bound `quickdraw.bdq-scheduled-epsilon-handoff.v1` gate: one continuous scheduled selector owns all 10,005 actions and receives `BDQOptimizerController.decision_count` directly. Two fresh Python/Unity processes preserve the canonical 10,004-transition R3G prefix, both exact optimizer results and online hashes, and the frozen target. At count 10,004, exact epsilon `0.999964` selects legal exploratory action `[0,0]` under movement mask `[false,true,false]`; transition 10,005 completes with no pending decision, third update, or target synchronization. Both serialized traces have SHA-256 `135d6a30c8526cd7422f9e30ff21cd997bd05a0ccbcdc5efd75b6fe1182d04a7`. All 11 focused R3J tests, all 118 trainer tests, and all 135 Python research tests pass. This proves bounded live schedule integration, not that updated weights chose the exploratory action or that a useful policy exists.
- R3K's hash-bound `quickdraw.bdq-third-update.v1` gate: the same scheduled selector, RNG, optimizer controller, replay, networks, and optimizer preserve the exact first 10,005 R3J transitions, then select only at completed counts 10,005, 10,006, and 10,007 with epsilons `0.999955`, `0.999946`, and `0.999937`. Transition 10,008 triggers optimizer update 3 with loss `0.008735351264476776`, mean absolute TD error `0.06769348680973053`, and online hash `4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b`; the target remains frozen, target synchronization stays at zero, and no decision remains pending. Two fresh Python/Unity processes each complete 215 episodes, handle three truncations, exercise all six action tuples, stop before selecting an action at count 10,008, and produce byte-identical traces. All 13 focused R3K cases, all 131 trainer tests, and all 148 Python research tests pass. This proves the recurring update boundary, not extended training or policy effectiveness.

Task 8 is committed and pushed as two consecutive Task 8-only commits: `ac1274e` (`task 8 : Logging and telemetry`) and `b5532e1` (`task 8 continued`). R1A was committed and pushed as `7117b81`; R1B as `4863153`; R1C as `5bae5f1`; revised R1E plus cleanup as `6d2aa3b`; Bryan's R1F commit as `876cedd`; R2A as `3cf3494` (`R2A: add deterministic Basic visual baseline`); the gradual-motion roadmap update as `3427c14`; R3A as `20aeab7` (`R3A: BDQ contract and schema`); its follow-up documentation synchronization as `7df359e`; R3B plus the bounded R2A visual/lifecycle maintenance as `500bc24` (`add optimizer implementation and unity cli`); R3D as `a4b449d` (`R3D: llapi implementation + truncation maski + pending decision`); R3E as `6aef062` (`R3E: fixed episilon greedy test runs`); R3F as `7edf7a3` (`R3F: Watch mode and 10000 transition update warmup test`); and R3G as `df036eb` (`R3G: additional smoke tests with updates`). Those commits are pushed. R3G changes no Unity runtime or environment source.

R3H is committed and pushed as `769c4de` (`R3H: two-update smoke test with q-val difference`). Its contract SHA-256 is `53331db49c21d16c005ba6b1e7409a1cf40a1480d4f14d72d325700099bef581`; canonical trace SHA-256 is `062deda3e8296499d6366a68bd4a0b84e539127ec320a337a7544f496395217e`; and its two serialized worker traces share SHA-256 `4341790871e0b5e3a990923601b45c052e9fb85e1e8ca20ae179421bb7977a87`. Generated evidence remains ignored. R3H changes no Unity runtime or environment source.

R3I is committed and pushed as `8d999d4` (`R3I: deterministic episilon greedy tests`). Its contract SHA-256 is `0d0f3f855ecf19a642f5dab2e526a1be2d2f0a1a87dca70671f4fad3128c3fa7`. R3I changes only the Python trainer package, contract/schema/tests, and synchronized documentation; it launches no Unity process and changes no Unity runtime or environment source.

R3J is committed and pushed as `32e78c6` (`R3J: deterministic epsilon greedy decay tests`). Its contract SHA-256 is `a8d47b166cdf1d553a9da5dbe0b028b7a658341bea894de359848644fa3be8a5`; canonical trace SHA-256 is `5e3a8ea3d2c0f0afb87fd87f92f6bf90036a6a95fc3f6124ccc0910ca07aa906`. R3J changes only the Python trainer runner boundary, contracts/schemas/tests, and synchronized documentation; it changes no Unity source. Generated traces, player logs, and result evidence remain ignored.

R3K is implemented and verified locally but is not committed or pushed. Its contract SHA-256 is `930839d2a19022b6debc0ad48cfc7f64cd86ff948be2690a9989a48598cda528`; canonical trace SHA-256 is `c3fafe259dfc03d69e06c758af0c2ba4df3b5da3322d325a5e361cdcf3a4ff02`; and both serialized worker traces have SHA-256 `4e4733dd5e5cbfbd7daa21f6d2ad8c48981b4369769d8df000b709e9c115dde4`. R3K changes only the Python live-worker boundary, contract/schemas/runner/tests, and synchronized documentation; it changes no Unity source. Generated traces, player logs, and result evidence remain ignored.

Unity CLI `1.0.0-beta.5` is installed as local developer tooling, recognizes and structurally verifies Unity `6000.0.57f1`, and reproduced the same one-test NUnit result as the legacy Editor batch-mode path for `ResearchBasicSceneAcceptanceTests.DedicatedSceneMatchesTheFrozenBasicContract`. This is tooling parity evidence, not a performance result or a new project dependency. The experimental `com.unity.pipeline` package is not installed. Raw Editor stderr can include authentication command-line arguments and must be treated as sensitive rather than echoed into logs or reports.

Not implemented:

- Multi-environment Unity collection, an extended environment learning loop or epsilon-decay rollout, checkpoint/export lifecycle, learned-policy evaluation, or trained policies. R3K stops exactly at optimizer update 3 without selecting another action; it does not open update 4 or an extended rollout. R1F accepts ROCm only for its fixed-policy inference fixture.
- Combat, cover, the scripted opponent, or `EvadeTelegraphedShot` research reflex.
- Qwen3/`llama.cpp`, the local HTTP client, strategic directives, failure injection, or LLM evaluation.
- The seeded factorial runner, confidence-interval analysis, or curated research report.

The existing tests prove software contracts, not the research hypothesis. A single telemetry trace is not a latency distribution.

### Central thesis

> Under identical visual observations, action interfaces, mechanical actuators, learned policy weights, opponent scripts, and evaluation seeds, a temporally partitioned FPS agent—combining a goal-conditioned Branching Double DQN, an event-driven deterministic evade reflex, and an asynchronous local-LLM strategic director—will improve combat utility over BDQ alone while preserving urgent reaction latency independently of LLM inference latency.

Registered hypotheses:

- **H1:** Full hybrid exceeds BDQ-only mean combat utility by at least `0.10`, with the paired 95% hierarchical-bootstrap confidence interval above zero.
- **H2:** Reflex-enabled conditions reduce damage received per telegraphed shot, with the paired 95% confidence interval below zero.
- **H3:** Full-hybrid telegraph-to-visible-evade p95 is at most `50 ms` and within one `20 ms` physics step of BDQ+reflex under injected LLM delays of `0`, `500`, `1000`, `2000`, and `3000 ms`; each delay tier contains at least 200 reflex events.
- **H4:** The LLM factorial main effect is positive. A strong LLM-specific claim additionally requires the LLM director to beat the same-information rule director by at least `0.05` utility with the 95% confidence interval above zero.

If the hierarchy beats BDQ but the LLM does not beat the rule director, the supported conclusion is that hierarchy helps but LLM-specific value was not demonstrated. Registered thresholds are not changed after final evaluation.

Primary episode utility:

```text
U = episode_outcome
  + 0.25 * (damage_dealt - damage_taken) / 100
  - 0.05 * missed_shot_fraction
  - 0.05 * wasted_resource_fraction
```

`episode_outcome` is `+1` for eliminating the opponent, `-1` for agent death, and `0` for timeout. Win rate, deaths, damage, shots, reloads, pickups, and survival time are always reported separately.

### Environment contracts

`Test_Arena` remains unchanged as the deterministic fixture. Its regression targets remain confirmed-threat-to-visible-motion p50 below `150 ms`, p95 below `250 ms`, reflex command execution substantially below `1 ms`, and a strict distinction between command and observed motion.

The Unity Basic benchmark contains a narrow primitive room, an agent at the south end, and a target at a seeded random lateral position near the north end. It uses:

- one egocentric `84×84` grayscale observation with four-frame stacking;
- movement `[Stay, Left, Right]`;
- combat `[Idle, Shoot]`;
- a fixed forward crosshair and identical hitscan mechanic;
- episode termination on a hit or after 300 decisions;
- reward `+1` hit, `-0.01` per decision, and `-0.02` missed shot;
- deterministic reset of transforms, ammunition, counters, frame stack, and seed.

At least four of five BDQ seeds must reach 90% success on 500 held-out target placements and exceed random success by at least 30 percentage points.

The strategic benchmark uses:

- movement `[Stay, Forward, Backward, Left, Right]`;
- combat `[Idle, Shoot]`;
- utility `[Idle, Reload, Interact]`;
- 100 health, 20 hitscan damage, a six-round magazine, 18 reserve rounds, a 0.25-second shot cooldown, a 1.5-second reload, and a 30-second episode limit;
- named cover, health/ammunition pickups, and one seeded scripted opponent;
- a 400 ms telegraph before every opponent shot;
- identical one-frame nearest-visible-target resolution and hitscan execution after `Shoot` in every condition;
- one collision-safe `0.6 m` lateral evade reflex with a one-second cooldown.

The reflex records threat, command, applied motion, collision, observed onset, preemption duration, and return of control. It cannot aim, shoot, select goals, perform I/O, or call a model.

### BDQ contract

Pin `com.unity.ml-agents` 4.0.0 and Python `mlagents-envs` 1.1.0. Python 3.10.12 remains the official historical compatibility baseline; current BDQ work uses the separately validated metadata-only Python 3.11.13 lane with NumPy 1.23.5 and PyTorch 2.12.0. ML-Agents supplies the Unity bridge, while the BDQ loop owns synchronous LLAPI collection, replay, targets, and optimization directly because the built-in trainers are not DQN.

The network uses four stacked `84×84` grayscale frames; convolution layers `(32, 8×8, stride 4)`, `(64, 4×4, stride 2)`, and `(64, 3×3, stride 1)`; a 512-unit shared representation; a scalar dueling value head; and one centered advantage head per action branch. The strategic-goal category joins the shared representation for the goal-conditioned model.

Training defaults:

- Double-DQN selection/evaluation and a target network;
- replay capacity 100,000 and 10,000-decision warmup;
- batch 64, `gamma=0.99`, Adam `1e-4`, and Huber loss;
- update every four decisions and hard target synchronization every 10,000 optimizer updates;
- epsilon `1.0` through 10,000 completed transitions, then linear decay to `0.1` across 100,000 transitions, followed by a `0.05` evaluation floor only during exploratory validation; final evaluation is greedy;
- five independent training seeds, each with checkpoints, curves, manifests, and hashes.

One strategic checkpoint per training seed is reused unchanged across runtime ablations. Training randomizes reflex availability and uses a deterministic teacher to provide every strategic goal. Potential-based goal shaping may guide attack, cover, health, or ammunition behavior without replacing shared terminal and damage rewards. Live LLM calls are excluded from policy training.

R1F completed the pre-training 10,000-step deterministic CPU/backend parity and throughput gate. Seeded traces, returns, checkpoint reload, ONNX export, actions, and floating-point tolerances passed; ROCm median throughput exceeded CPU and is accepted for the registered batch-size-one synchronous inference fixture. The development system has an AMD Radeon RX 7900 XT and 32 GB RAM. Training support and larger learned-model throughput remain unproven and require separate gates.

### Local LLM contract

Serve a quantized Qwen3-8B non-thinking/instruction model through a pinned `llama.cpp` local HTTP server, preferring a validated Vulkan backend. Record runtime version, model source, quantization, context and generation settings, and SHA-256. Model weights are not committed.

Every two seconds Unity captures an immutable compact snapshot: quantized health/ammunition, visible-enemy count/distance/health categories, cover and pickup availability/distance categories, current directive, episode ID, sequence, and timestamp. The LLM receives no raw frame or continuous scene matrix.

Schema-constrained output contains `strategic_intent`, `priority_target`, and `engagement_rule`. Valid coherent directives are `BALANCED`, `OFFENSIVE_RUSH`, `DEFENSIVE_RETREAT`, `SEEK_HEALTH`, and `CONSERVE_AMMO`. The validated directive becomes a categorical BDQ goal input, never an actuator action or a tactical legality mask.

Runtime defaults are one request every two seconds, five-second timeout, four-second TTL, monotonic sequence IDs, temperature zero, recorded seed, and a small JSON-only token budget. Invalid, incoherent, stale, timed-out, and out-of-order results are discarded. The last valid directive remains active; no valid directive falls back to `BALANCED`.

Main-thread code captures and applies plain data. HTTP and parsing run asynchronously without accessing Unity objects and publish through a thread-safe queue. A deterministic mock covers fixed responses, invalid JSON, connection loss, timeout, out-of-order completion, and all five registered delay tiers before live inference.

### Evaluation and artifacts

Main conditions:

1. BDQ, fixed `BALANCED`, reflex off.
2. BDQ + reflex, fixed `BALANCED`.
3. BDQ + LLM, reflex off.
4. BDQ + reflex + LLM.

Secondary controls replace the LLM with a deterministic rule director using the identical state snapshot and directive schema, with reflex off and on.

For each of five policy seeds, run every condition on the same 100 held-out scenario seeds: 500 paired episodes per condition. Use a 10,000-resample hierarchical bootstrap over policy seed and paired scenario seed. Report paired effects, 95% confidence intervals, factorial main effects and interaction, and the rule-director comparison.

Required measurements include training return, success, learning-curve area, TD statistics, epsilon, replay size, steps per second, utility and all raw combat components, BDQ inference latency, frame/fixed-step time, all reflex timing and collision stages, damage avoided, deadline misses, all LLM request/validation/discard/fallback stages, directive occupancy, logger pressure/failures, allocations, and model/scene/configuration hashes.

Raw JSONL, CSV, checkpoints, and model outputs live under an ignored project-local experiment-artifact directory with run manifests. Track schemas, scripts, configurations, curated aggregate tables, plots, model checksums, and conclusions. No participant study is included. Negative and null results remain valid research results.

### Ordered next work and non-goals

Research Tasks R0, R1A, R1B, R1C, revised R1E, R1F, the R2A environment-only slice, R3A, R3B, R3D, R3E, R3F, R3G, R3H, R3I, and R3J are complete and pushed; R3K is implemented and verified locally; the bounded R2A visual/lifecycle maintenance is included in `500bc24`; the exploratory R1D lane is superseded and retired. R3C records the uncommitted, superseded high-level trainer/trajectory experiment. R3A freezes tensor/replay meanings, R3B supplies deterministic optimization, R3D proves terminal and bootstrapped-truncation replay with exact fresh-process repeatability and no weight change, and R3E proves fixed seeded epsilon-greedy collection across resets below warmup with no learning operation. Pushed R3F reaches the exact 10,000-transition production warmup and performs one deterministic CPU update on real Unity experience; pushed R3G adds the second scheduled update at decision 10,004; pushed R3H preserves that complete prefix and proves that the twice-updated online network selects and completes one live legal masked-greedy action while the target stays frozen; pushed R3I freezes and unit-tests the stateless production epsilon schedule and mask-safe scheduled selector; pushed R3J drives one continuous scheduled selector through the same prefix and completes a count-10,004 live scheduled handoff without opening update 3; local R3K preserves the full R3J prefix and opens update 3 exactly at decision 10,008. Update 4, an extended Unity decay rollout, target synchronization, checkpoint/export, learned-policy evaluation, strategic combat, and LLM runtime remain unimplemented and require separately approved work. After the full R3 Q-learning acceptance gates pass, the separately versioned gradual-motion Basic variant remains planned; it must preserve slot-based R2A as the control and use its own training/evaluation.

Current non-goals are survival/extraction systems, crafting or loot economies, multiplayer/networking, production art, procedural worlds, group AI, speech/TTS, unrestricted conversation, LLM training/fine-tuning, LLM frame-level control, hybrid-only privileged mechanics, tactical masks for legal actions, unobserved visible-latency claims, and post-hoc changes to registered thresholds without an exploratory label.

## Superseded deterministic-slice summary (historical)

The following material records the earlier downsized vertical-slice scope. It remains useful for the implemented `Test_Arena` fixture but does not control the active research roadmap where it conflicts with the section above.

### Historical mission

Build a small Unity FPS behavior laboratory that demonstrates how an NPC can preserve human-time responsiveness during urgent interactions while slower tactical or generative systems remain off the urgent path.

This is independent systems/HCI/applied-AI work. It is not a survival game, an extraction shooter, or core machine-learning research.

## Historical downsized scope

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

## Historical deterministic control flow

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

## Historical deterministic layer responsibilities

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

During that historical deterministic phase, LLM integration was deferred until the local loop was functional and measured. The approved research program above now replaces that deferral with a bounded asynchronous strategic-director experiment; the agent must still behave correctly when the director is absent.

## Historical deterministic timing and telemetry

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

## Historical deterministic technical baseline

- Unity: `6000.0.57f1`.
- Intended render pipeline: URP.
- Input: Unity Input System using `Keyboard.current` and `Mouse.current`; no Input Actions asset is required for the first controller. Active Input Handling may be `Input System Package (New)` or `Both`.
- Current relevant packages include Input System, ProBuilder, Animation Rigging, Newtonsoft JSON, AI Navigation, and URP.
- Starter Assets are not required and must not become a dependency.
- VSync should be off and Incremental GC on.
- Enter Play Mode should use Domain Reload off and Scene Reload on, with static lifecycle safeguards.

### Current repository baseline

The repository is still a pre-MVP scaffold:

- `Test_Arena` is a 16-by-16-unit controlled fixture containing the required player hierarchy, light, floor, four enclosing walls, a full-height occlusion divider, a low block, player/NPC spawn markers, two patrol markers, an interaction marker, one capsule NPC with perception-eye and non-colliding facing markers, and a `Systems` container with the structured logger and telemetry recorder. It is intentionally open-top for clear lighting and playtest visibility.
- `SimpleFPSController` is an attachable custom Input System controller with WASD movement, mouse look, gravity, sprint, jump, cursor toggling, RMB aim, smooth FOV, and public read-only `IsAiming` state. Upward velocity is cleared on overhead collision so a blocked jump immediately begins falling.
- `PatrolActivity` moves the NPC deterministically between the two patrol markers through a collision-aware `CharacterController` and exposes explicit start, tick, interrupt, resume, cancel, and reset operations with observable activity state, real-time timing, and lifecycle events.
- `AimThreatStimulus` is a plain six-field value, and the camera-backed `AimThreatEmitter` on the player publishes real-time-stamped current snapshots plus one start or end event for each RMB aim transition. It has no NPC, perception, reflex, logging, or debug-bypass dependency.
- `SoftFOVPerception` is wired to the NPC and Task 5 emitter. It applies a 20-unit visual limit, total-FOV half-angle checks, non-allocating line of sight, measured 12 Hz suspicion timing, 0.5/0.3 hysteresis, 300-degree-per-second orientation, and one confirmation per released-and-rearmed aim episode. A confirmed episode continues tracking a renewed valid aim without rearming, incrementing the episode, or re-emitting confirmation; tracking stops when the active aim is no longer valid. Camera-ray intersection with NPC bounds qualifies threat relevance but never bypasses perception or invokes a reflex. In Play Mode, renderer-local property blocks color both the capsule and facing marker by state so transitions are observable directly in the Game view without changing the shared arena material.
- Forty-one Unity Play Mode tests verify the Task 2 controller and jump behavior, Task 3 open-top arena dimensions and sightlines, Task 4 patrol behavior, Task 5 stimulus snapshots and RMB edges, Task 6 perception and visualization, Task 7A one-shot activity interruption, Task 7B deterministic one-shot reflex dispatch, Task 8A measured visible onset, and Task 8B structured telemetry; the tests pass, and a Windows standalone build also succeeds in Unity `6000.0.57f1`.
- User layer 8 is named `NPC` for NPC activity and perception queries.
- `NpcBehaviorController` is wired to `NPC_01` as the explicit Task 7A/7B state-edge owner. It subscribes to one-shot threat confirmation, synchronously suspends `PatrolActivity`, records the interruption metadata, and commands a reflex only after the activity remains stopped. Duplicate confirmation delivery is ignored, and a rearmed episode produces another interruption/reflex only after activity was deliberately resumed. The controller does not resume activity automatically.
- `ReflexSelector` replaces the old name-hashed, raw-transform, logger-coupled scaffold. It commands one immediate `Flinch_StepBack` per interrupted threat episode through `CharacterController.Move`, using serialized seed `1001`, deterministic `0.35 ± 0.05 m` distance variation, and yaw within `±30°`. It exposes `ReflexCommanded` plus the pre-command pose and other read-only command metadata without claiming dispatch is visible onset.
- `VisibleMotionObserver` measures the first root displacement of at least `0.01 m` or rotation of at least `1°` after a reflex command, emits one separate `visible_motion_started` event per episode, and exposes command-to-visible and confirmed-threat-to-visible timings. It has no logging or file dependency.
- The old anonymous-`JsonUtility` logger scaffold is replaced. `TelemetryRecorder` observes gameplay events without adding logging dependencies to AI components, while `JsonlLogger` queues typed Newtonsoft event records, serializes and periodically flushes outside urgent dispatch, uses a Domain-Reload-safe singleton and session-unique JSONL path, retains buffered lines after failed writes, and emits per-stage count/min/max/mean/p50/p95/standard-deviation summaries. Read-only custom Inspectors expose visible-onset and telemetry diagnostics in Play Mode.
- Task 8 records real threat-release and manual activity-resume edges but does not implement or fabricate Task 9 tactical recovery. `DevOverlay` remains an unwired scaffold.
- Tracked URP renderer and pipeline assets now resolve in Graphics and both Quality levels; `Test_Arena` passed batch-mode pipeline and material validation in Unity `6000.0.57f1`.
- `Test_Arena` is the sole enabled Build Settings scene; the package lock and editor settings are tracked; VSync is off, Incremental GC is on, Active Input Handling is `Both`, and Enter Play Mode disables Domain Reload while retaining Scene Reload.

At that historical point, the planned next task was the now-superseded tactical-recovery state machine.

## Historical arena scope

`Assets/_Project/Scenes/Test_Arena.unity` is a controlled greybox testbed. Its eventual minimum contents are:

- an open-top floor and four walls;
- one full-height occluder and one low block;
- player spawn and NPC spawn;
- two patrol markers;
- one interaction marker;
- a `Systems` object for diagnostics and logging.

Do not add production art, a large map, complex NavMesh layout, combat encounters, loot, or decorative props that do not support a named test.

## Historical deterministic definition of done

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

## Historical hard non-goals

Do not implement without an explicit scope change:

- inventory, hunger, thirst, crafting, loot, or an extraction economy;
- firearms, shooting, ammo, reloads, damage, or full combat;
- multiplayer or networking;
- reinforcement learning or LLM training within that historical deterministic slice;
- large behavior-tree or GOAP frameworks;
- production art, procedural worlds, group AI, speech recognition, or high-quality TTS.

## Historical deterministic work discipline

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
- upward `CharacterController` collision clears positive vertical velocity immediately

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

The implemented structured stimulus contains:

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

The scene began with only:

- floor,
- ceiling.

The ceiling has since been removed. The current 16-by-16-unit open-top fixture, walls, markers, player, and NPC are recorded in the current repository baseline above.

#### 14.2 Minimal map elements

Current minimum:

- floor,
- open top with no ceiling,
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
