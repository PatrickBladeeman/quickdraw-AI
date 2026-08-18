# quickdraw-AI

**A hierarchical deep-reinforcement-learning and local-LLM FPS research platform in Unity.**

`quickdraw-AI` explores whether an FPS agent can combine learned tactical control and local language-model reasoning without sacrificing urgent responsiveness.

The central question is: can a temporally partitioned system improve combat decisions while keeping time-critical reflexes independent of slow strategic inference?

## Approach

The research architecture separates control by timescale:

- **Deterministic actuation** executes shared movement, aiming, shooting, reload, and interaction mechanics.
- **Local reflexes** may briefly preempt movement for a confirmed imminent threat.
- **Branching Double DQN** learns visual tactical action intents.
- **A local asynchronous LLM** supplies bounded strategic goals rather than frame-level commands.

```text
egocentric observations
→ learned tactical intent
→ shared deterministic actuator

imminent threat → optional urgent evade
abstract match state → optional local-LLM strategy
```

## Evaluation

The project uses controlled ablations to compare BDQ, BDQ+reflex, BDQ+LLM, and the full hybrid. Evaluation includes:

- combat utility and its raw win, damage, accuracy, and resource components;
- sample efficiency and learned-policy inference latency;
- threat-to-visible-reflex latency under injected LLM delays;
- local-model validity, timeout, fallback, and strategic-effect metrics.

Timing stages are recorded separately in structured telemetry so model latency, command latency, and actual observed motion are not conflated.

## Status

The deterministic Unity fixture implements player control, NPC patrol and perception, one-shot interruption, a measurable reflex, visible-motion observation, and buffered JSONL telemetry. Research infrastructure pins the CPU dependency set, installs Unity ML-Agents 4.0.0, passes a repeatable communicator smoke gate, and records an exactly repeatable 10,000-decision CPU LLAPI transport reference. R1E established the Python 3.11.13 / ML-Agents 1.1.0 / ROCm 7.14.0 compatibility lane on the exact RX 7900 XT. R1F passed every fixed-policy trace, action, return, checkpoint, ONNX, finiteness, and `1e-5` logit gate; ROCm's 98.3215 decisions/s median exceeded CPU's 93.2145 for that registered batch-size-one fixture. R2A implements the deterministic `Research_Basic` environment: an actual `[84,84,4]` HWC grayscale observation, shared typed actions and center-camera hitscan, seeded resets, terminal/truncation semantics, and schema-validated random/scripted LLAPI baselines whose fresh-process traces repeat exactly. R3A now adds a strict pure-Python BDQ foundation: immutable seeded replay, exact `[3,2]` dueling branch outputs, legal-action masking, branch/joint mapping, Double-DQN target math, and averaged branch Huber loss, all verified on synthetic CPU tensors. No Unity training rollout, optimizer-driven learning, learned policy, strategic combat environment, or local-model runtime has begun.

## Technology

- Unity 6 and C#
- Universal Render Pipeline
- Unity Input System
- Unity ML-Agents 4.0.0 (installed; communicator and CPU reference trace verified)
- Python 3.10.12 historical CPU transport reference plus the Python 3.11.13 / PyTorch 2.12.0 R3A CPU foundation and accepted ROCm inference lane (trainer rollout not yet implemented)
- Qwen3-8B through a local `llama.cpp` server (planned strategic layer)
- ProBuilder
- Structured JSONL telemetry

## License and citation

Code is available under the [MIT License](LICENSE). Third-party asset requirements are described in [ASSETS_LICENSE.md](ASSETS_LICENSE.md). Citation metadata is provided in [CITATION.cff](CITATION.cff).
