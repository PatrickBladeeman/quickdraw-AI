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

The deterministic Unity fixture implements player control, NPC patrol and perception, one-shot interruption, a measurable reflex, visible-motion observation, and buffered JSONL telemetry. Research infrastructure pins the CPU dependency set, installs Unity ML-Agents 4.0.0, passes a repeatable communicator smoke gate, and records an exactly repeatable 10,000-decision CPU LLAPI transport reference. R1E established the Python 3.11.13 / ML-Agents 1.1.0 / ROCm 7.14.0 compatibility lane on the exact RX 7900 XT. R1F passed every fixed-policy trace, action, return, checkpoint, ONNX, finiteness, and `1e-5` logit gate; ROCm's 98.3215 decisions/s median exceeded CPU's 93.2145 for that registered batch-size-one fixture. R2A implements the deterministic `Research_Basic` environment: an actual `[84,84,4]` HWC grayscale observation, a lit high-contrast room and compact fixed reticle, shared typed actions and center-camera hitscan, seeded and Domain-Reload-safe resets, terminal/truncation semantics, and schema-validated random/scripted LLAPI baselines whose fresh-process traces repeat exactly. R3A adds the strict pure-Python BDQ replay/network/target foundation, and R3B proves the exact Adam, replay-warmup, update, and hard-target-sync schedule with deterministic synthetic CPU transitions. R3D retires the experimental R3C high-level trainer/trajectory scaffolding and proves exact terminal/truncation replay through direct LLAPI collection. R3E extends that boundary with fixed, seeded, mask-safe epsilon-greedy collection below warmup. R3F then reaches the production 10,000-transition warmup and performs exactly one repeatable batch-64 CPU optimizer update from real Unity experience: online weights change, target weights remain frozen, and two fresh complete traces match byte-for-byte. A separate single-run watch mode makes that collection observable in the Unity Editor or a visible standalone player without weakening the two-process acceptance gate. R3G extends the same seeded trace by four transitions and proves the second scheduled update at decision 10,004. R3H preserves that complete prefix, then proves the twice-updated online network selects and completes one legal masked-greedy Unity action while the frozen target supplies an explicit Q-value comparison. R3I adds the hash-bound, stateless production epsilon schedule and a seeded mask-safe scheduled selector. R3J connects one continuous scheduled selector to a bounded two-process Unity run, preserves the exact R3G prefix, and completes a legal action at epsilon `0.999964` without a third update or target synchronization. R3K preserves all 10,005 R3J transitions, continues the same scheduled selector for exactly three actions, and completes optimizer update 3 at decision 10,008 with a new online hash, frozen target, and no pending decision. R3L preserves that exact 10,008-transition prefix, bypasses the production epsilon schedule for one explicitly diagnostic epsilon-zero handoff, and proves the update-3 online network selects and completes legal masked-greedy action `[2,1]` before update 4; two independent fresh-process traces match byte-for-byte. R3M returns to the uninterrupted production schedule, preserves R3K's complete prefix, consumes exactly the four scheduled selections at counts 10,008 through 10,011, and completes optimizer update 4 at decision 10,012 with a new online hash, frozen target, no pending decision, and byte-identical two-process traces. R3N replaces the impractical 21.03 GiB full-capacity replay payload with exact deduplicated float32 frames and columnar metadata under a fail-closed 4 GiB accounting ceiling; one fresh R3M trace remains byte-identical to the frozen pre-R3N trace. Extended training, learned-policy evaluation, strategic combat, and the local-model runtime have not begun.

## Technology

- Unity 6 and C#
- Universal Render Pipeline
- Unity Input System
- Unity ML-Agents 4.0.0 (installed; communicator and CPU reference trace verified)
- Python 3.10.12 historical CPU transport reference plus the Python 3.11.13 / PyTorch 2.12.0 R3A-R3N BDQ foundation, memory-bounded replay, optimizer, direct LLAPI collection, first four scheduled live updates, update-3 policy handoff, bounded live production-epsilon integration, and accepted ROCm inference lane (extended training not yet implemented)
- Qwen3-8B through a local `llama.cpp` server (planned strategic layer)
- ProBuilder
- Structured JSONL telemetry

## License and citation

Code is available under the [MIT License](LICENSE). Third-party asset requirements are described in [ASSETS_LICENSE.md](ASSETS_LICENSE.md). Citation metadata is provided in [CITATION.cff](CITATION.cff).
