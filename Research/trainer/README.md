# R3A-R3E BDQ foundation and direct LLAPI collection

This directory contains QuickDraw's bounded Branching Double DQN implementation.
R3A freezes tensors, replay, masks, the visual network, Double-DQN targets, and
Huber loss. R3B freezes the optimizer and update schedule. R3C records the
superseded high-level ML-Agents trajectory experiment. R3D replaces that
experiment with synchronous `DecisionSteps`/`TerminalSteps` collection. R3E
adds deterministic mask-safe epsilon-greedy collection below replay warmup.

The tracked contract chain is:

- `bdq-foundation-contract-v1.json`: historical R3A foundation;
- `bdq-optimizer-contract-v1.json`: historical R3B optimizer contract;
- `bdq-llapi-contract-v1.json`: current R3D direct-collection and
  truncation-mask contract.
- `bdq-epsilon-collection-contract-v1.json`: R3E's hash-bound, fixed-epsilon,
  exactly-1,000-transition collection contract.

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
  selector used by R3E.

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

These are collection results, not training evidence. Epsilon decay, replay
warmup completion, gradient updates on Unity experience, checkpoint/resume,
ONNX export, ROCm training, learned-policy evaluation, gradual motion,
strategic combat, reflexes, and LLM work remain outside this slice.
