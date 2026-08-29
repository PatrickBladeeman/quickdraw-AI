# ADR-0009: Include a same-information rule director

- **Status:** Accepted research design; runtime not implemented
- **Recorded:** 2026-08-29, retrospectively

## Context

An LLM condition receives a structured strategic snapshot. Comparing only
against a fixed goal cannot distinguish value from that structured state and
goal interface from value unique to language-model reasoning.

## Decision

Add deterministic rule-director conditions with reflex off and on. The rule
director receives the exact same abstract snapshot and emits the exact same
directive schema as the LLM. It receives no extra state and uses the same policy
checkpoint, actuator, opponent schedule, and paired scenario seeds.

## Consequences

- The primary `2 × 2` reflex-by-LLM factorial remains intact.
- A strong LLM-specific claim additionally requires at least `0.05` utility over
  the rule director with a paired 95% confidence interval above zero.
- If the hierarchy improves outcomes but the LLM does not beat the rule
  director, the conclusion must credit hierarchy rather than unique LLM value.

See [`RESEARCH.md`](../../RESEARCH.md) for the complete registered analysis.
