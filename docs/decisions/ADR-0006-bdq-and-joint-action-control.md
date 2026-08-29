# ADR-0006: Use BDQ with a joint-action control

- **Status:** Accepted
- **Recorded:** 2026-08-29, retrospectively

## Context

The strategic action space is naturally branched into movement, combat, and
utility. Enumerating every combination scales multiplicatively, while an
additive branching representation can miss important interactions between
branches.

## Decision

Use a dueling Branching Double DQN as the primary learned architecture. It
shares one visual representation and scalar value head while producing one
mean-centered advantage head per action branch. Online-network argmax selects
legal next actions; the target network evaluates them.

For the Basic benchmark, whose two branches form only six joint tuples, also
run a joint-action Double DQN comparison. It is a factorization sanity control,
not a replacement for the registered primary architecture.

## Consequences

- The strategic policy avoids a full `5 × 2 × 3` output table.
- Branch losses and masks require explicit, stable index contracts.
- Any material loss caused by additive factorization must be reported rather
  than hidden by the primary model choice.

See [`RESEARCH.md`](../../RESEARCH.md) and
[`Research/trainer/bdq-foundation-contract-v1.json`](../../Research/trainer/bdq-foundation-contract-v1.json).
