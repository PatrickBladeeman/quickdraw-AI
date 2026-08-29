# Architecture decision records

These ADRs retrospectively record consequential decisions already present in
the architecture, research contract, or implemented milestones. They explain
rationale and consequences; they do not by themselves authorize implementation
or override [`RESEARCH.md`](../../RESEARCH.md), [`ARCH.md`](../../ARCH.md),
[`STATE.md`](../../STATE.md), or [`TASK.md`](../../TASK.md).

All records below are accepted unless a later ADR explicitly supersedes one.

1. [ADR-0001: Separate control by timescale](ADR-0001-temporal-hierarchy.md)
2. [ADR-0002: Route aim threat through structured perception](ADR-0002-stimulus-through-perception.md)
3. [ADR-0003: Trigger interruption and reflexes on event edges](ADR-0003-edge-triggered-reflex.md)
4. [ADR-0004: Separate command time from visible-motion time](ADR-0004-command-vs-visible-motion.md)
5. [ADR-0005: Use explicit, domain-separated seeds](ADR-0005-seeded-reproducibility.md)
6. [ADR-0006: Use BDQ with a joint-action control](ADR-0006-bdq-and-joint-action-control.md)
7. [ADR-0007: Collect experience through the ML-Agents low-level API](ADR-0007-direct-llapi.md)
8. [ADR-0008: Limit the asynchronous LLM to categorical strategy](ADR-0008-async-categorical-llm.md)
9. [ADR-0009: Include a same-information rule director](ADR-0009-rule-director-control.md)
10. [ADR-0010: Share mechanical aiming across conditions](ADR-0010-shared-mechanical-aim.md)
11. [ADR-0011: Transport final masks for bootstrapped truncations](ADR-0011-terminal-truncation-mask.md)
12. [ADR-0012: Store replay losslessly under a hard memory ceiling](ADR-0012-lossless-bounded-replay.md)

The documentation migration that extracted these records is described in
[`DOCUMENTATION_MIGRATION_2026-08-29.md`](../history/DOCUMENTATION_MIGRATION_2026-08-29.md).
