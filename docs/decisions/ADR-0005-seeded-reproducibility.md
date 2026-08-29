# ADR-0005: Use explicit, domain-separated seeds

- **Status:** Accepted
- **Recorded:** 2026-08-29, retrospectively

## Context

Runtime object-name hashes are not stable enough for reproducible behavior, and
one undifferentiated seed can accidentally couple environment scenarios, model
initialization, exploration, and replay sampling.

## Decision

Use explicit serialized or manifest-recorded seeds with separate ownership:

- style/profile seeds control deterministic fixture variation;
- scenario seeds control environment and opponent schedules;
- policy-training seeds control initialization, replay sampling, and exploration;
- evaluation uses held-out scenario seeds paired across conditions.

Never derive research seeds from runtime names or unstable platform hashes. As
a registered infrastructure example, R1F used scenario seed `21001` and the
distinct policy-initialization seed `11001`. Final research evaluation uses five
independent policy seeds and the same 100 held-out scenario seeds per condition.

## Consequences

- Same-seed trace equality becomes a meaningful contract.
- Policy and scenario variation can be resampled separately in the hierarchical
  bootstrap.
- Every run manifest must record the relevant seed domains.

See [`RESEARCH.md`](../../RESEARCH.md) and
[`Research/configs/research-contracts-v1.json`](../../Research/configs/research-contracts-v1.json).
