# R3A-R3C: BDQ foundation, optimizer, and superseded trajectory experiment

## R3A: pure-Python BDQ foundation

Status: completed and pushed in
`20aeab772a70c9526a8b635a195098ccb20a7533`; documentation synchronization
followed in `7df359e0891ab2835e00c068bd308b574f8fc755`.

The tracked
[`quickdraw.bdq-foundation.v1`](../../Research/trainer/bdq-foundation-contract-v1.json)
contract has SHA-256
`9a97d8b58ed08e816f032784069e7b1c38b7185df73b4b8edd504dc58112cfb9`
and binds the Basic contract SHA-256
`d0803181993a9b31d089a483fc0e4499980ec5893625be5a9188e0db68c7153d`.

The pinned CPU runtime is Python `3.11.13`, ML-Agents and ML-Agents Envs
`1.1.0`, NumPy `1.23.5`, and PyTorch `2.12.0+cpu`. The frozen observation is
float32 HWC `[84,84,4]` on the wire and CHW in the encoder. Branch sizes are
`[3,2]`; `true` means unavailable in action masks; joint index is
`movement_index * 2 + combat_index`.

Network contract:

1. Conv `32`, kernel `8`, stride `4`
2. Conv `64`, kernel `4`, stride `2`
3. Conv `64`, kernel `3`, stride `1`
4. shared representation `512`
5. scalar value head plus advantage heads `[3,2]`
6. `Q_i = V + A_i - mean(A_i)`

Replay is a seeded uniform-without-replacement PCG64 ring with capacity
`100000` and warmup `10000`. Double DQN uses online per-branch selection,
target evaluation, `gamma=0.99`, no true-terminal bootstrap, truncation
bootstrap, and next-action masks on the online argmax. Loss is Huber with
`beta=1.0`, reduced as the mean over batch and branches. Registered defaults
include batch `64`, Adam `0.0001`, update interval `4`, hard target sync every
`10000` optimizer updates, epsilon `1.0` to `0.1`, exploratory evaluation
epsilon `0.05`, greedy final evaluation, and training seeds
`[51001,51002,51003,51004,51005]`.

Fifteen deterministic synthetic CPU tests covered contract/schema/runtime
binding, the future plugin seam, action mapping, immutable replay and seeded
sampling, masks, exact layers and shapes, gradients, hand-calculated targets,
terminal/truncation behavior, loss reduction, and replay-to-backward
composition.

R3A did not register a trainer, launch Unity, collect experience, run an
optimizer or training loop, execute ROCm, create checkpoints/exports, or
demonstrate learned-policy effectiveness.

## R3B: deterministic optimizer smoke

Status: completed and pushed with bounded R2A visual/lifecycle maintenance in
`500bc2433288daeb773c8105d260f6fdcf1f7cf0`.

The historical
[`quickdraw.bdq-optimizer.v1`](../../Research/trainer/bdq-optimizer-contract-v1.json)
contract has SHA-256
`1095419f9ebc11050e188ce042b55ca578cf8bf320a6321a5b98470bc98e3849`
and binds R3A SHA-256
`9a97d8b58ed08e816f032784069e7b1c38b7185df73b4b8edd504dc58112cfb9`.
Its historical package version was `0.2.0`.

R3B registered the production defaults already listed for R3A and proved
seeded online/target initialization, exact target deep copy, Adam updates,
decision/update counters, online-only gradients, frozen target behavior before
the boundary, and post-update hard synchronization. Decision count increments
after a validated replay insert. An update requires decision count and replay
size at least `10000` and `decision_count % 4 == 0`; target synchronization
occurs after an optimizer step when update count is divisible by `10000`.

Validation passed `22` focused R3B CPU tests, all `37` trainer tests, and all
`54` Python research tests. It included official plugin discovery,
`TrainerFactory` construction, no premature update, a real batch-`64` update,
online-only weight change, frozen-target behavior, exact hard sync, and
tensor-for-tensor seeded repeatability. Unity CLI `1.0.0-beta.5` also matched
the legacy batch-mode result for one exact focused Edit Mode test: one
selected, one passed, zero failed or skipped. That CLI is local tooling, not a
project dependency; `com.unity.pipeline` was not installed.

The R3B trainer/settings/plugin shell was experimental scaffolding and is no
longer part of the current package. R3B did not create an ML-Agents policy,
consume Unity experience, train a policy, execute ROCm, decay epsilon,
checkpoint/resume, export ONNX, or demonstrate effectiveness.

## R3C: high-level trajectory experiment — superseded and removed

R3C was an uncommitted local experiment. It showed that the ML-Agents trainer
controller could deliver one terminal trajectory, but its
`Trainer`/`Policy`/`Trajectory` lifecycle and next-mask registry obscured the
direct environment-step boundary. It never became accepted evidence and none
of its experimental scaffolding was committed.

R3D removed the experimental trainer class, settings class, plugin entry
point, trajectory adapter, configuration YAML, runner, contracts, schemas,
next-mask registry, and focused trajectory tests. R3C therefore supplies no
current runtime, contract hash, accepted trace, training result, or policy
claim. Its only durable conclusion is the architectural decision to use the
direct synchronous low-level API boundary established by R3D.
