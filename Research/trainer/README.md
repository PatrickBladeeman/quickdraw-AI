# R3A BDQ trainer foundation

This directory is the bounded R3A pure-Python foundation for the later custom
Branching Double DQN trainer. It freezes and tests the replay, visual tensor,
branched action, masking, dueling-network, Double-DQN target, Huber-loss, and
ML-Agents plugin seams without launching Unity or claiming that training works.

The machine-readable contract is `bdq-foundation-contract-v1.json`. It binds
this package to the exact `Research_Basic` contract hash, the `[84,84,4]` HWC
float32 observation, branches `[3,2]`, row-major six-action mapping, and the
installed ML-Agents `mlagents.trainer_type` entry-point group. R3A deliberately
does not register a trainer entry point until a real trainer class and settings
type exist in a later approved slice.

`quickdraw_bdq` contains:

- `replay.py`: immutable validated transitions and seeded uniform ring-buffer
  sampling;
- `network.py`: the registered three-convolution encoder, 512-unit shared
  representation, scalar value head, and mean-centered `[3,2]` advantage heads;
- `action_space.py`: branch/joint mapping and fail-closed legal-action masking
  for greedy and epsilon-greedy selection;
- `targets.py`: per-branch Double-DQN targets and mean branch Huber loss;
- `plugin.py`: validation of the pinned ML-Agents plugin boundary only.

True `target_hit` terminals do not bootstrap. The registered 300-decision time
limit is a truncation, so it bootstraps from its final observation and legal
next-action mask. A transition cannot be both terminal and truncated.

Run the focused suite from the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe'
& $python -B -m pytest -p no:cacheprovider Research\trainer\test_bdq_foundation.py
```

R3A excludes Unity rollout, an optimizer/training loop, ROCm execution,
checkpoint/resume, ONNX export, trained weights, gradual motion, strategic
combat, reflexes, and LLM work. The next trainer slice must build on these
tested seams rather than replacing their meanings silently.
