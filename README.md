# quickdraw-AI

**Latency-bounded hybrid NPC behavior in Unity.**

`quickdraw-AI` is an independent systems/HCI research project exploring how real-time NPCs can react in human time without waiting for slower generative reasoning.

The central question is simple: how can an NPC preserve immediate, believable responses during urgent interactions while still supporting tactical context, memory, and generated dialogue asynchronously?

## Approach

The prototype separates behavior by urgency:

- **Soft perception** models notice, suspicion, line of sight, and orientation.
- **Interruption** allows an NPC to stop an ongoing activity when a threat is confirmed.
- **Local reflexes** begin visible motion immediately without network or LLM dependency.
- **Tactical recovery** determines whether the NPC remains threatened, complies, flees, or resumes its activity.
- **Asynchronous enrichment** may later add cached dialogue or structured memory without entering the reflex path.

```text
ongoing activity
→ perception and orientation
→ threat confirmation
→ interruption
→ immediate reflex
→ recovery
```

## Evaluation

The primary metric is confirmed threat to first observed visible motion:

- median under 150 ms;
- p95 under 250 ms.

Perception delay, suspicion, orientation, reflex dispatch, and visible onset are recorded as separate stages in structured telemetry.

## Status

The project is in early development. The current focus is a reproducible greybox vertical slice with one NPC activity, soft field-of-view perception, interruption, a measurable placeholder reflex, and simple recovery. Generative dialogue and memory are later extensions.

## Technology

- Unity 6 and C#
- Universal Render Pipeline
- Unity Input System
- ProBuilder
- Structured JSONL telemetry

## License and citation

Code is available under the [MIT License](LICENSE). Third-party asset requirements are described in [ASSETS_LICENSE.md](ASSETS_LICENSE.md). Citation metadata is provided in [CITATION.cff](CITATION.cff).
