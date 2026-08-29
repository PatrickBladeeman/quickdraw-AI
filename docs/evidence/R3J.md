# R3J: continuous scheduled-epsilon live handoff

Status: completed and pushed in
`32e78c62c3ac6b2586b72dc18f8812a71eba1599` on 2026-08-26.

## Frozen contract

The tracked
[`quickdraw.bdq-scheduled-epsilon-handoff.v1`](../../Research/trainer/bdq-scheduled-epsilon-handoff-contract-v1.json)
contract has SHA-256
`a8d47b166cdf1d553a9da5dbe0b028b7a658341bea894de359848644fa3be8a5`
and binds R3I SHA-256
`0d0f3f855ecf19a642f5dab2e526a1be2d2f0a1a87dca70671f4fad3128c3fa7`.
It embeds the frozen R3G transition prefix SHA-256
`45554af94700fa1429e3487dcf2bd62f1c71f7419b4f1f80f0cf0ad905670f69`.

## Accepted live evidence

One continuous `ScheduledEpsilonGreedyBDQActionSelector` owned every selection
from completed count `0` through `10004`; it received the optimizer
controller's live decision count directly. Exact sampled values were:

| Completed transitions | Epsilon |
|---:|---:|
| `0` | `1.0` |
| `10000` | `1.0` |
| `10001` | `0.999991` |
| `10004` | `0.999964` |

At count `10004`, the seed-`61001` stream selected exploratory action `[0,0]`
under masks `[[false,true,false],[false,false]]` for observation SHA-256
`8d10e324956e2d5b7b8a7d70da58d33a9b170598727998146dcfec858bab8a83`.
It completed transition `10005` without opening update 3.

Each of two fresh processes completed `10005` transitions, `215` episodes,
three truncations, all six action tuples with counts
`[1855,1741,1592,1605,1593,1619]`, two optimizer updates, zero target syncs,
and no pending decision. Both R3G update metrics and online hashes remained
exact; the target remained
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

Evidence hashes:

- R3J transition-prefix SHA-256
  `0cf694116eba2678d2e17f1178e2bd3552a6835e4f0b2960e0fa6beba0adf812`
- canonical trace SHA-256
  `5e3a8ea3d2c0f0afb87fd87f92f6bf90036a6a95fc3f6124ccc0910ca07aa906`
- each serialized trace SHA-256
  `135d6a30c8526cd7422f9e30ff21cd997bd05a0ccbcdc5efd75b6fe1182d04a7`
- accepted ignored result SHA-256
  `e69a84b06ada4af1b71f668abc2dabd1cd1e244d870e06100abcabdf627ada3d`

The accepted-result hash was recomputed from the ignored artifact during the
documentation migration; the generated file is not tracked.

## Validation and limits

All `11` focused R3J tests, all `118` trainer tests, and all `135` Python
research tests passed. R3J proves bounded counter/RNG/mask integration. Its
handoff action was exploratory; it is not evidence that updated weights chose
the action or that a useful policy exists. It does not demonstrate update 3,
target synchronization, extended decay/training, checkpoint/export, ROCm
training, or held-out evaluation.
