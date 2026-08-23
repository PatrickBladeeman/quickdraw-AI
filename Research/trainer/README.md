# R3A-R3F BDQ foundation, direct LLAPI collection, and first update

This directory contains QuickDraw's bounded Branching Double DQN implementation.
R3A freezes tensors, replay, masks, the visual network, Double-DQN targets, and
Huber loss. R3B freezes the optimizer and update schedule. R3C records the
superseded high-level ML-Agents trajectory experiment. R3D replaces that
experiment with synchronous `DecisionSteps`/`TerminalSteps` collection. R3E
adds deterministic mask-safe epsilon-greedy collection below replay warmup.
R3F reaches the exact production warmup and performs one CPU update from real
Unity transitions.

The tracked contract chain is:

- `bdq-foundation-contract-v1.json`: historical R3A foundation;
- `bdq-optimizer-contract-v1.json`: historical R3B optimizer contract;
- `bdq-llapi-contract-v1.json`: current R3D direct-collection and
  truncation-mask contract.
- `bdq-epsilon-collection-contract-v1.json`: R3E's hash-bound, fixed-epsilon,
  exactly-1,000-transition collection contract.
- `bdq-warmup-update-contract-v1.json`: R3F's hash-bound, exactly-10,000-
  transition production-warmup and first-update contract.

`quickdraw_bdq` now contains only the reusable learning core and direct LLAPI
boundary:

- `replay.py`: immutable validated transitions and seeded uniform replay;
- `network.py`: the three-convolution visual encoder and dueling `[3,2]`
  branch heads;
- `action_space.py`: branch/joint mapping and strict mask-aware selection;
- `targets.py`: per-branch Double-DQN targets and averaged Huber loss;
- `optimizer.py`: online/target networks, Adam, replay, and exact counters;
- `llapi.py`: behavior validation, online-network action selection, one pending
  decision per agent, direct replay completion, and strict truncation-mask
  side-channel ingestion. It also exposes the fixed seeded epsilon-greedy
  selector used by R3E and R3F. At epsilon `1.0`, the selector preserves the
  exact exploration RNG sequence without evaluating unused network Q-values.

The former `Trainer`, `Policy`, `Trajectory`, settings, plugin-registration,
YAML, and next-mask-registry scaffolding has been removed. `pyproject.toml`
therefore registers no `mlagents.trainer_type` entry point and depends only on
`mlagents-envs`, NumPy, and PyTorch.

For each agent, the runner stores `(observation, action, current masks)` when a
decision is sent. When that agent next appears, it completes exactly one replay
transition with the delivered reward and next observation. A `DecisionStep`
supplies the next masks for ordinary continuation. A true terminal uses an
irrelevant all-available sentinel because it does not bootstrap. A decision-limit
truncation receives the authoritative final-state mask from Unity over the
dedicated `quickdraw.basic-truncation-mask.v1` side channel; Python never infers
that mask from privileged scene state.

Install the editable package in the isolated Python 3.11 environment:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe'
& $python -B -m pip install --no-deps -e Research\trainer
```

Run the focused trainer suite:

```powershell
& $python -B -m pytest -p no:cacheprovider Research\trainer
```

Build the already-saved `Research_Basic` scene, then run the real two-process
gate:

```powershell
& 'C:\Program Files\Unity\Hub\Editor\6000.0.57f1\Editor\Unity.exe' `
  -batchmode -nographics -quit `
  -projectPath 'C:\projects\quickdraw-AI' `
  -executeMethod QuickDraw.Editor.ResearchBasicBuild.BuildWindows `
  -quickdrawBasicOutput 'Artifacts\Experiments\r3d-llapi\build\QuickDrawResearchBasic.exe' `
  -logFile 'Artifacts\Experiments\r3d-llapi\build.log'

& $python Research\trainer\run_bdq_llapi_smoke.py `
  --env Artifacts\Experiments\r3d-llapi\build\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3d-llapi\live-smoke
```

Each fresh process collects two episodes. The unchanged online network greedily
finishes the first. The second moves left four times, idles through decision
300, and ends as an interrupted truncation at slot `-4`, whose Unity-authored
movement mask is `[false,true,false]`. Every one of the 302 decisions becomes
one replay transition. The gate requires exact trace equality, zero optimizer
updates, zero target synchronizations, and unchanged online/target weight
hashes.

Run the R3E collection gate against the same saved-scene player:

```powershell
& $python Research\trainer\run_bdq_epsilon_collection_smoke.py `
  --env Artifacts\Experiments\r3d-llapi\build\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3e-epsilon-collection\acceptance
```

R3E fixes epsilon at the registered starting value `1.0` and uses exploration
seed `61001`; decay is deliberately closed. Each fresh process completes
exactly 1,000 transitions across resets, stops before issuing a replacement
action, and therefore leaves no pending decision. The accepted local pair
completed 18 episodes, exercised all six action tuples, handled one truncation,
performed zero optimizer updates or target synchronizations, preserved both
networks, and produced byte-identical traces.

Run the R3F production-warmup and first-update gate:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3f-warmup-update\acceptance
```

Each accepted fresh process collected exactly 10,000 complete transitions,
crossed 215 episode resets, handled three truncations, and exercised all six
action tuples. No update occurred through transition 9,999. Transition 10,000
opened exactly one registered batch-64 Adam update with loss
`0.01628389209508896` and mean absolute TD error `0.06243317946791649`. The
online weights changed, the target weights remained frozen, target-sync and
pending-decision counts stayed zero, and the two complete traces matched byte
for byte.

To watch one diagnostic run in the Unity Editor, open `Research_Basic` but
leave the Editor out of Play Mode, then start Python:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --watch `
  --output Artifacts\Experiments\r3f-warmup-update\editor-watch
```

When Python reports that it is listening on port `5004`, press Play in Unity.
The runner forces `Time.timeScale` to `1`, targets 60 frames per second, and
prints the completed transition count, current episode and episode decision,
selected action, reward, replay size, optimizer-update count, and target-sync
count every 100 transitions. `--progress-interval N` changes that terminal
reporting interval. The run stops after transition 10,000 and its first update;
stop Play Mode manually afterward.

The same one-run diagnostic can launch a visible standalone player:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --watch `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3f-warmup-update\standalone-watch
```

Both watch forms write one validated trace only. They are explicitly
observational and never produce the two-fresh-process `result.json` required by
the unchanged R3F acceptance gate. A local standalone watch validation completed
all 10,000 transitions at time scale 1, performed the same single update, and
produced trace SHA-256
`aee36f7bc5c2e2202e2738709c021826878de717d22b91345001dafd8599f0b2`,
byte-identical to each accepted worker trace, without creating `result.json`.

R3D and R3E are collection evidence. R3F is one minimal learning operation on
real Unity experience, not an extended training run or effectiveness result.
Epsilon decay, a second update, target synchronization, checkpoint/resume, ONNX
export, ROCm training, learned-policy evaluation, gradual motion, strategic
combat, reflexes, and LLM work remain outside this slice.
