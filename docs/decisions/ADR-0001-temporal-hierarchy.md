# ADR-0001: Separate control by timescale

- **Status:** Accepted
- **Recorded:** 2026-08-29, retrospectively

## Context

Mechanical execution, urgent threat response, learned tactics, and local-model
reasoning have materially different latency and failure characteristics. A slow
or failed strategic request must not pause physics or urgent motion.

## Decision

Use four explicit layers:

1. one deterministic actuator executes the last accepted action at the `0.02 s`
   fixed timestep (`50 Hz`);
2. an optional event-driven reflex may preempt movement by the next physics step;
3. BDQ selects a tactical intent every five physics steps (`10 Hz`) and that
   intent is held between decisions;
4. an optional local director captures a strategic snapshot every two seconds
   (`0.5 Hz`) and publishes only a validated future-facing goal.

The reflex cannot wait for or call the learned policy or director. The director
cannot call the actuator or alter action legality or rewards.

## Consequences

- Urgent latency can be evaluated independently of LLM latency.
- Every ablation can share one actuator and policy cadence.
- Preemption and restoration of the held movement intent must be explicit.
- Additional asynchronous work must preserve the same main-thread boundaries.

See [`ARCH.md`](../../ARCH.md) and the registered timing contract in
[`RESEARCH.md`](../../RESEARCH.md).
