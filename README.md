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

The deterministic Unity fixture currently implements player control, NPC patrol and perception, one-shot interruption, a measurable reflex, visible-motion observation, and buffered JSONL telemetry. The learned-agent environments, BDQ trainer, strategic combat benchmark, and local-model integration are the next research phases.

## Technology

- Unity 6 and C#
- Universal Render Pipeline
- Unity Input System
- Unity ML-Agents (planned research bridge)
- Python and PyTorch (planned BDQ trainer)
- Qwen3-8B through a local `llama.cpp` server (planned strategic layer)
- ProBuilder
- Structured JSONL telemetry

## License and citation

Code is available under the [MIT License](LICENSE). Third-party asset requirements are described in [ASSETS_LICENSE.md](ASSETS_LICENSE.md). Citation metadata is provided in [CITATION.cff](CITATION.cff).
