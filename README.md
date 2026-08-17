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

The deterministic Unity fixture currently implements player control, NPC patrol and perception, one-shot interruption, a measurable reflex, visible-motion observation, and buffered JSONL telemetry. Research infrastructure pins the Python 3.10.12 CPU dependency set, installs Unity ML-Agents 4.0.0, passes a repeatable standalone Unity/Python communicator smoke gate, and records an exactly repeatable 10,000-decision CPU LLAPI transport reference. R1E established the disclosed Python 3.11.13 / ML-Agents 1.1.0 / ROCm 7.14.0 compatibility lane on the exact RX 7900 XT. R1F then passed every fixed-policy trace, action, return, checkpoint, ONNX, finiteness, and `1e-5` logit gate. Across alternating 10,000-decision runs, CPU measured 81.321 and 105.108 decisions/s while ROCm measured 96.430 and 100.213; the medians were 93.2145 and 98.3215, so ROCm is accepted for this batch-size-one synchronous inference fixture. This does not establish training throughput or model quality. Learned benchmarks, training, strategic combat, and local-model integration remain future phases.

## Technology

- Unity 6 and C#
- Universal Render Pipeline
- Unity Input System
- Unity ML-Agents 4.0.0 (installed; communicator and CPU reference trace verified)
- Python 3.10.12 CPU reference plus the accepted Python 3.11.13 / PyTorch 2.12.0 ROCm inference lane (BDQ trainer planned)
- Qwen3-8B through a local `llama.cpp` server (planned strategic layer)
- ProBuilder
- Structured JSONL telemetry

## License and citation

Code is available under the [MIT License](LICENSE). Third-party asset requirements are described in [ASSETS_LICENSE.md](ASSETS_LICENSE.md). Citation metadata is provided in [CITATION.cff](CITATION.cff).
