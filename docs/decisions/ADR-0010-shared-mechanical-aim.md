# ADR-0010: Share mechanical aiming across conditions

- **Status:** Accepted; Basic path implemented, strategic path planned
- **Recorded:** 2026-08-29, retrospectively

## Context

Giving only a hybrid condition a target resolver or mechanically superior aim
would make an apparent architectural improvement indistinguishable from an aim
assist advantage.

## Decision

Mechanical aim is a controlled variable supplied identically within each
benchmark:

- Basic uses one fixed forward crosshair and the same camera-center hitscan; the
  policy must move laterally to align.
- The planned strategic actuator resolves the nearest visible legal target,
  applies the same one-frame look-at/snap, and fires the same hitscan for BDQ,
  reflex, LLM, full-hybrid, and rule-director conditions.

Optional layers receive no additional target coordinates or aim path.

## Consequences

- Comparisons isolate control-layer differences rather than motor precision.
- The learned action remains a semantic `Shoot` intent.
- Any future aim variant requires a separate, shared contract across conditions.

See [`ARCH.md`](../../ARCH.md) and [`RESEARCH.md`](../../RESEARCH.md).
