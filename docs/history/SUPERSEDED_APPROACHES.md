# Superseded approaches

> **Historical and non-authoritative.** The items below are retained so an old
> plan, prompt, or comment cannot silently reintroduce them. They must not be
> implemented unless a new authorized task and current decision explicitly
> adopt them.

## Broader game scope

Survival/extraction mechanics, hunger, thirst, crafting, loot economies,
multiplayer, procedural worlds, production art, group AI, speech recognition,
high-quality TTS, and unrestricted conversational NPCs were removed from the
research prototype. They are neither prerequisites nor implied future work.

## Direct threat-to-reflex raycast

Early sketches routed a permanent camera hit directly to reaction selection.
The accepted design uses a structured aim stimulus through soft perception.
Any direct confirmation is debug-only and disabled for evaluation. See
[`ADR-0002`](../decisions/ADR-0002-stimulus-through-perception.md).

## Command time treated as visible latency

Earlier guidance treated an animation trigger or movement command as response
onset. The accepted implementation observes actual root displacement or
rotation and records command and visible timestamps separately. See
[`ADR-0004`](../decisions/ADR-0004-command-vs-visible-motion.md).

## First reaction and unstable variation

`RaiseHands_High` was once proposed as the first reaction despite the absence of
a suitable rig. `Flinch_StepBack` became the measurable first placeholder;
hands-up remains only a later animation reference. Runtime object-name hashing
was replaced by explicit serialized seeds.

## Premature tactical and generative layers

Early Utility/GOAP work and an early LLM worker were deferred before
implementation. The former Tasks 9–13—automatic tactical recovery, completion
of the old slice, reaction-family expansion, its original experiment harness,
and optional dialogue/memory enrichment—were superseded by the hierarchical
deep-RL research program. The tactical-recovery FSM was never completed.

The current planned local model is a bounded asynchronous categorical director,
not a dialogue agent or frame-level controller. See
[`ADR-0008`](../decisions/ADR-0008-async-categorical-llm.md).

## Reinforcement learning as a permanent non-goal

During the deterministic slice, reinforcement learning and combat were deferred
until a trustworthy local loop existed. Tasks 1–8 satisfied that prerequisite.
Historical statements treating RL, combat, or a local model as permanent
non-goals are superseded only for the named research environments and registered
program.

## R1D exploratory accelerator lane

R1D explored a Windows accelerator candidate and registered an all-or-nothing
parity procedure without accepting a backend. The ROCm `7.14.0` compatibility
matrix later listed the exact RX 7900 XT / `gfx1100` / Windows 11 25H2 target.
Revised R1E replaced the exploratory candidate with the Python 3.11/ROCm lane;
obsolete R1D probes, locks, schemas, results, and tests were retired. R1F later
accepted ROCm only for its registered batch-size-one inference fixture, not for
training generally.

## R3C high-level trainer and trajectory experiment

R3C explored the high-level ML-Agents trainer/trajectory interface. It left
next-state mask information split across delivery boundaries and introduced
registry state that did not simplify the custom BDQ contract. The experiment
was superseded and removed. R3D adopted synchronous direct LLAPI collection.
See [`ADR-0007`](../decisions/ADR-0007-direct-llapi.md).

## In-place gradual movement

Changing R2A's one-slot movement in place was rejected because it would change
the environment dynamics and invalidate the canonical control. A gradual-motion
Basic scenario remains deferred as a separately versioned environment with its
own training and evaluation. The discrete action branches may remain the same;
gradual movement is not a continuous action space.
