# Deterministic substrate and R0-R2 evidence

This record covers the completed deterministic Unity substrate, research
infrastructure, backend gates, and the environment-only Basic benchmark. It
contains public project evidence only.

## Tasks 1-8 and R0 checkpoint

The deterministic `Test_Arena` substrate was checkpointed in consecutive
commits:

- `ac1274e81cc6cc6a12d7ecd27c2c75cf0f1e2c5b` —
  `task 8 : Logging and telemetry`
- `b5532e1107ce550edd355b6682778c5e06c4aa1b` —
  `task 8 continued`

Unity `6000.0.57f1` passed the complete `41`-test Play Mode suite and a
Windows standalone build. The implemented fixture includes player control,
patrol, structured aim stimulus, soft-FOV perception, one-shot interruption,
deterministic collision-aware `Flinch_StepBack`, and typed buffered JSONL
telemetry. `reflex_commanded` and observed `visible_motion_started` are
separate one-shot events. Visible onset requires at least `0.01 m` root
displacement or `1 degree` root rotation; command dispatch alone is not
visible-motion evidence.

R0 added no ML-Agents, research combat, learned policy, or LLM functionality.
The former tactical-recovery FSM was not implemented and was superseded by the
registered research program.

## R1A: contract and dependency preflight

Status: completed and pushed in
`7117b81be198f4f920f3df11dc6e9149fa9b1d9f`.

The root research contract is
[`Research/configs/research-contracts-v1.json`](../../Research/configs/research-contracts-v1.json),
SHA-256
`b6777d7a3b45a8134358c5946c9284c37c3414aad85c8e763dbdf0faf9e33523`.
R1A pinned the historical Python `3.10.12` CPU reference environment and the
Release 23 boundary pairing Unity ML-Agents `4.0.0` with Python
`mlagents`/`mlagents-envs` `1.1.0`. It added machine-readable observation,
action, reward, reset, terminal, truncation, seed, side-channel, run-manifest,
and artifact contracts and established ignored `Artifacts/Experiments/`
storage.

R1A did not install a learned task, complete Unity communicator evidence,
measure the CPU reference, test AMD parity, or train a policy.

## R1B: deterministic communicator smoke

Status: completed and pushed in
`48631536f4746f504bd1550e227d415f73de061e`.

The tracked contract is
[`Research/smoke/smoke-contract-v1.json`](../../Research/smoke/smoke-contract-v1.json),
SHA-256
`32c62bc3cd95152b4f61e2c156e856fc50fe57bd9f386806712d1081907fbe08`.
Two fresh standalone runs used base seed `21001`; their canonical traces were
structurally and numerically identical. Each run completed one `smoke_goal`
terminal episode and one `decision_limit` truncation with
`interrupted=true`.

Validation comprised five focused Edit Mode tests, the existing `41` Play
Mode tests, the isolated smoke-player build, and the normal `Test_Arena`
Windows build in Unity `6000.0.57f1`.

R1B demonstrated communication and repeatability only. It did not provide the
10,000-decision CPU reference, a learned environment, replay, training, AMD
acceleration, or an LLM result.

## R1C: 10,000-decision CPU transport reference

Status: completed and pushed in
`5bae5f1c35555606015c96eb04b8277b70f8196c`.

The tracked contract is
[`Research/smoke/cpu-reference-contract-v1.json`](../../Research/smoke/cpu-reference-contract-v1.json),
SHA-256
`b55fdb462f3a0872d84d75025b242baf5485929ab57fb4e96e28eabee994a77a`.
Two base-seed-`21001` standalone runs each produced exactly `10000`
transitions and ended with `decision_limit` and `interrupted=true`. Their
canonical trace SHA-256 was
`d5080b62ea3cc6c33a18567461f690a568339d2168f9d253ea3134b7c85572c5`.

The timed synchronous Python-LLAPI-to-Unity step measurements were:

| Run | Timed seconds | Decisions/s |
|---|---:|---:|
| CPU 1 | `92.0502828` | `108.636` |
| CPU 2 | `93.0801134` | `107.434` |

Startup, trace comparison, and JSON serialization were excluded from the
timed section. Validation included six focused Edit Mode tests, all `41` Play
Mode tests, both Windows builds, and the unchanged R1B exact-trace regression.
These numbers measure communicator transport, not training or model-inference
throughput.

## R1D: superseded AMD exploration

R1D was exploratory and is not an accepted backend result. Its executable
probe, package lock, contract, result schema, curated result, and focused tests
were retired after the current ROCm `7.14.0` compatibility lane replaced it.
No R1D result should be treated as current evidence.

## R1E: Python 3.11, ROCm 7.14, and ML-Agents 1.1 compatibility

Status: completed in the revised R1E/cleanup commit
`6d2aa3bc272fdf891b602a59ea540877e54c96fa`.

Tracked inputs:

- Contract
  [`mlagents-rocm-compatibility-contract-v1.json`](../../Research/environment/mlagents-rocm-compatibility-contract-v1.json),
  SHA-256
  `6312ac8b0a5a78f07b550a5612f323bdf6c6903034ae3d76aa0a017ec8420771`
- Curated result
  [`rocm-mlagents-compatibility-result-v1.json`](../../Research/environment/rocm-mlagents-compatibility-result-v1.json),
  SHA-256
  `d8f9c5b3bf45517bc9dc6d3a4f41505a46c50078a3aea4f6bdab64f8fe18e2c2`

The validated target was Windows 11 Home 25H2, build `26200`, Python
`3.11.13`, ROCm `7.14.0`, PyTorch `2.12.0+rocm7.14.0`, torchvision
`0.27.0+rocm7.14.0`, torchaudio `2.11.0+rocm7.14.0`, ML-Agents and
ML-Agents Envs `1.1.0`, NumPy `1.23.5`, `grpcio==1.53.2`, and
`PettingZoo==1.15.0`. The selected device was index `0`, AMD Radeon RX 7900
XT, exposed to PyTorch/ML-Agents as `cuda:0`. The recorded AMD software was
`26.7.1`; the RX 7900 XT driver was `32.0.31035.1003`.

Two independently clean-installed environments had identical
`71`-distribution inventories and passed `pip check`, imports, and
`mlagents-learn --help`. The fixed float32 CPU-versus-ROCm probe recorded:

- forward maximum absolute difference
  `4.76837158203125e-07`
- input-gradient maximum absolute difference `0.0`
- weight-gradient maximum absolute difference `0.0`
- registered tolerance `1e-5`

Two communicator traces from each environment passed; all four canonical
traces had SHA-256
`5c5a5190f36e320a7bf05f85543681ba8f98e04aef1e71922d277f805ccf42b5`.
The registered decision was `conditional_go`,
`backend_acceptance=not_accepted`, `cpu_reference_retained=true`, and
`full_parity_executed=false`. R1E did not accept ROCm training or establish
end-to-end backend parity; R1F performed the separately registered inference
gate.

## R1F: fixed-policy CPU-versus-ROCm parity

Status: completed and pushed in
`876ceddeffa5c4cb9c746edbefd75d0ab34e8def`. The commit subject still says
R1E; the project milestone record classifies its contents as R1F.

Tracked inputs and result:

- Contract
  [`backend-parity-contract-v1.json`](../../Research/environment/backend-parity-contract-v1.json),
  SHA-256
  `71c2519b97440899828aede94c087ed0b7da9b03a479a9929499a0f2c5e487b3`
- Curated result
  [`amd-backend-parity-result-v1.json`](../../Research/environment/amd-backend-parity-result-v1.json),
  SHA-256
  `0a1b4486eed5b9adee0127ea1fda9fa6e381940ce421e38ebb738d11e76ef11c`

The fixture used scenario seed `21001`, policy seed `11001`, one
`1000`-decision warmup, and a separately timed `10000`-decision episode. The
deterministic float32 network was `4 -> 32 ReLU` with separate `3`-logit and
`2`-logit heads. No training was performed. The checkpoint SHA-256 was
`fc1b19eb0abe2122c0d3b12a58cf312998049cd21c429a43c856e503aa51b519`,
ONNX SHA-256 was
`6c15f3fa2686ea7dee2f3ab6c056b1d20685aab2fd1f090df449eb713e9e0b1f`,
and state-dict SHA-256 was
`7351ce3de0d9bc3ec77cb3242324d16f66aa5b7c12bd62d516afb6376385192f`.

The required run order was CPU-1, ROCm-1, CPU-2, ROCm-2. Every registered
trace, action-mask, action, decision-count, seeded-return, terminal,
interrupted, checkpoint-reload, finiteness, masked-argmax, ONNX-action, and
repeat-logit gate passed. All four seeded returns were `-100.0`. Maximum
absolute differences were CPU repeat `0.0`, ROCm repeat `0.0`, CPU-versus-ROCm
`9.5367431640625e-07`, and ONNX-versus-CPU
`9.5367431640625e-07`, under tolerance `1e-5`.

| Backend | Runs (decisions/s) | Median |
|---|---|---:|
| CPU | `81.321`, `105.108` | `93.2145` |
| ROCm | `96.430`, `100.213` | `98.3215` |

The ROCm/CPU median ratio was `1.0547876135150647`. Under the frozen
no-partial-acceptance rule, ROCm was accepted because all correctness gates
passed and its median throughput was strictly greater.

This acceptance is limited to batch-size-one synchronous inference in the
`Research_Smoke` LLAPI fixture. It does not establish training throughput,
larger-model performance, learned-policy quality, `Research_Basic`, combat,
or LLM behavior. Four focused R1F tests covered the gate.

## R2A: deterministic Basic environment

Status: completed and pushed in
`3cf34942e5b8fc2597f9dc7206cd16c9d54ae9cd`. The separately versioned
gradual-motion roadmap note was added in
`3427c1472a96bc8c9e7877025a9ba7dbe6fb6642`; it did not change R2A.

The tracked contract is
[`Research/basic/basic-contract-v1.json`](../../Research/basic/basic-contract-v1.json),
SHA-256
`d0803181993a9b31d089a483fc0e4499980ec5893625be5a9188e0db68c7153d`.

Registered environment values:

- Unity scene `Assets/_Project/Scenes/Research_Basic.unity`
- behavior `QuickDrawResearchBasic`
- scenario seed `31001`
- `12` baseline episodes
- physics fixed delta `0.02 s`
- one policy decision every `5` fixed steps, or `10 Hz`
- hold the last tuple between decisions
- uncompressed float32 HWC `[84,84,4]` Rec. 601 grayscale stack, oldest to
  newest, value range `[0.0,1.0]`
- movement branch `[Stay, Left, Right]` and combat branch `[Idle, Shoot]`
- slots `-4` through `4`, spaced `0.75` world units, agent start slot `0`
- ammunition capacity `300`, zero decision cooldown, hitscan distance `40.0`
- additive reward: `-0.01` per decision, `+1.0` hit, `-0.02` missed shot
- terminal reason `target_hit`; truncation reason `decision_limit`; limit
  `300`
- random-policy seed `41001`; scripted visual-policy seed `41002`
- two fresh standalone runs per policy

The frozen visual values include a directional key light at Euler
`[50.0,-30.0,0.0]`, intensity `1.25`, no shadows, and an unlit cyan reticle
with segment length `0.006`, thickness `0.001`, center offset `0.006`, and
camera depth `0.11` world units. Reset captures one post-reset frame and copies
it into all four channels before the first decision.

Validation passed `30` Edit Mode tests, all `41` existing Play Mode tests,
seven Basic Python tests, the isolated Basic Windows build, and the normal
`Test_Arena` Windows build. Random traces matched exactly across their two
fresh processes; scripted traces matched exactly, and the scripted policy
completed all `12` episodes with one aligned hit and zero misses per episode.

R2A is environment-only evidence. It contains no replay buffer, optimizer,
BDQ training run, learned weight, strategic combat expansion, or LLM runtime.

