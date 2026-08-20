# R3A/R3B BDQ trainer foundation and optimizer smoke

This directory contains the bounded pure-Python work for the custom Branching
Double DQN trainer. R3A freezes the replay, visual tensor, branched action,
masking, dueling-network, Double-DQN target, and Huber-loss meanings. R3B adds
the real ML-Agents entry point and settings boundary plus a deterministic CPU
optimizer/scheduler smoke. Neither slice launches Unity or claims that a policy
has learned the Basic task.

`bdq-foundation-contract-v1.json` binds R3A to the exact `Research_Basic`
contract hash, the `[84,84,4]` HWC float32 observation, branches `[3,2]`, and
the row-major six-action mapping. `bdq-optimizer-contract-v1.json` binds R3B to
that exact R3A file and freezes plugin registration, production optimizer
defaults, decision/update counters, and hard target synchronization timing.

`quickdraw_bdq` contains:

- `replay.py`: immutable validated transitions and seeded uniform ring-buffer
  sampling;
- `network.py`: the registered three-convolution encoder, 512-unit shared
  representation, scalar value head, and mean-centered `[3,2]` advantage heads;
- `action_space.py`: branch/joint mapping and fail-closed legal-action masking
  for greedy and epsilon-greedy selection;
- `targets.py`: per-branch Double-DQN targets and mean branch Huber loss;
- `optimizer.py`: online and target networks, seeded replay, Adam updates, and
  explicit decision/update/synchronization counters;
- `settings.py`: the registered production defaults for ML-Agents 1.1;
- `trainer.py`: the factory-compatible trainer shell, whose Unity rollout
  methods fail closed because rollout belongs to a later slice;
- `plugin.py`: both the historical R3A seam check and the installed R3B
  registration callable.

True `target_hit` terminals do not bootstrap. The registered 300-decision time
limit is a truncation, so it bootstraps from its final observation and legal
next-action mask. A transition cannot be both terminal and truncated.

Install the editable plugin into the isolated Python 3.11 environment from the
repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe'
& $python -B -m pip install --no-deps -e Research\trainer
```

Then run both focused suites:

```powershell
& $python -B -m pytest -p no:cacheprovider Research\trainer
```

The registered production defaults are replay capacity 100,000, warmup 10,000
decisions, batch size 64, `gamma=0.99`, Adam `1e-4`, one update every four
decisions, and a hard target copy every 10,000 optimizer updates. Tests may
inject smaller capacities and intervals without changing those defaults.

R3B excludes Unity policy creation, trajectory collection, environment rollout,
epsilon-decay rollout, ROCm execution, checkpoint/resume, ONNX export, trained
weights, gradual motion, strategic combat, reflexes, and LLM work. The next
trainer slice must build on these tested seams rather than replacing their
meanings silently.
