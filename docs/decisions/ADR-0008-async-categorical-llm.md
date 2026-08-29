# ADR-0008: Limit the asynchronous LLM to categorical strategy

- **Status:** Accepted research design; runtime not implemented
- **Recorded:** 2026-08-29, retrospectively

## Context

Local language-model inference is slow and may fail, time out, or complete out
of order. Allowing free-form text to drive frame-level mechanics would confound
the timing hypothesis and make safety, reproducibility, and action fairness
difficult to audit.

## Decision

The planned local director receives a compact immutable abstract snapshot every
two seconds, never raw frames or a continuous scene matrix. It returns
schema-constrained fields that must form one of five coherent categorical goals:
`BALANCED`, `OFFENSIVE_RUSH`, `DEFENSIVE_RETREAT`, `SEEK_HEALTH`, or
`CONSERVE_AMMO`.

HTTP waiting and parsing occur off the Unity main thread; capture, validation,
and application occur on it. Use a five-second timeout, four-second result TTL,
monotonic request/snapshot sequences, and fail-safe retention of the last valid
goal with `BALANCED` as the no-valid-result fallback. The goal conditions BDQ;
it never becomes an actuator command, reward edit, or tactical mask.

## Consequences

- LLM delay cannot enter physics, reflex, or BDQ decision paths.
- Mock delay/failure cases can be tested before a model is introduced.
- The design measures strategic value, not text-to-control dexterity.

See the registered design in [`RESEARCH.md`](../../RESEARCH.md).
