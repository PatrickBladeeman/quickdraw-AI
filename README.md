# quickdraw-AI

**A hierarchical deep-reinforcement-learning and local-LLM FPS research
platform in Unity.**

`quickdraw-AI` investigates whether temporally separated mechanical control,
urgent reflexes, learned visual tactics, and bounded local-model strategy can
improve combat decisions without coupling urgent response time to slow
strategic inference.

## Approach

- A shared deterministic actuator executes mechanics.
- An optional event-driven reflex may briefly preempt movement.
- A goal-conditioned Branching Double DQN selects tactical action intents.
- An optional asynchronous local LLM supplies a categorical strategic goal,
  never frame-level commands.

```text
egocentric observation → learned tactical intent → shared actuator
imminent threat        → optional urgent movement preemption
abstract match state   → optional asynchronous strategic goal
```

## Evaluation

The registered program compares BDQ, BDQ+reflex, BDQ+LLM, and the full hybrid,
with same-information rule-director controls. It keeps policy checkpoints,
mechanics, observations, actions, opponent schedules, and held-out scenarios
paired across conditions. Combat outcomes, policy learning, reflex visible
latency, director behavior, failures, and system timing are recorded separately.

The complete frozen design, hypotheses, thresholds, and fairness rules are in
[`RESEARCH.md`](RESEARCH.md).

## Status

The deterministic Unity fixture, reproducible ML infrastructure, and
slot-based `Research_Basic` visual benchmark are implemented and verified. The
custom Python BDQ path has progressed through direct LLAPI collection, lossless
bounded replay, the production epsilon schedule, and four bounded Unity-derived
optimizer updates ending at transition 10,012. This is integration evidence,
not extended training or a useful-policy result.

Extended training, target synchronization, checkpoint/export, learned-policy
evaluation, strategic combat, the research evade reflex, the local-model
runtime, and factorial evaluation remain unimplemented. See
[`STATE.md`](STATE.md) for current truth and
[`docs/evidence/`](docs/evidence/README.md) for exact results and limitations.

## Documentation

- [Current state](STATE.md)
- [Current authorized task](TASK.md)
- [Software architecture](ARCH.md)
- [Registered research contract](RESEARCH.md)
- [Research roadmap](ROADMAP.md)
- [Documentation map](docs/README.md)
- [Environment and repository reference](docs/reference/README.md)

## Technology

- Unity 6, C#, Universal Render Pipeline, and the Unity Input System
- Unity ML-Agents 4.0.0
- Python 3.11.13, NumPy, and PyTorch for the current BDQ reference path
- A narrowly accepted ROCm fixed-policy inference lane; ROCm training is not
  established
- Qwen3-8B through a pinned local `llama.cpp` service for the planned strategic
  director
- Structured JSONL telemetry

## License and citation

Code is available under the [MIT License](LICENSE). Third-party asset
requirements are described in [ASSETS_LICENSE.md](ASSETS_LICENSE.md). Citation
metadata is provided in [CITATION.cff](CITATION.cff).
