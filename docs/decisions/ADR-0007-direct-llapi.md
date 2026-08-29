# ADR-0007: Collect experience through the ML-Agents low-level API

- **Status:** Accepted and implemented for Basic collection
- **Recorded:** 2026-08-29, retrospectively

## Context

The high-level ML-Agents trainer interface is designed around built-in trainer
lifecycles and delivered trajectory fragments. QuickDraw owns a custom BDQ
replay, Double-DQN targets, masks, scheduling, and terminal/truncation behavior.
The R3C trainer/trajectory experiment added translation state without providing
a clearer correctness boundary.

## Decision

Retire the high-level trainer, policy, trajectory, settings, plugin, and
next-mask-registry scaffolding. Drive `UnityEnvironment` synchronously through
`DecisionSteps` and `TerminalSteps`.

For each agent, store one pending `(observation, action, current masks)` record
when an action is submitted. Complete exactly one immutable transition when the
same agent next appears. Reject duplicate or missing pending state and validate
the exact behavior name, observation shape, branch shape, and mask convention.

## Consequences

- Replay completion follows the environment step boundary directly.
- Custom algorithms can own update and target-sync schedules without pretending
  PPO or SAC is DQN.
- The collector must explicitly handle the final mask for truncations.

See [`Research/trainer/README.md`](../../Research/trainer/README.md) and
[`Research/trainer/bdq-llapi-contract-v1.json`](../../Research/trainer/bdq-llapi-contract-v1.json).
