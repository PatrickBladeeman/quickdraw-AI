# R3K: scheduled optimizer update 3

Status: completed and pushed in
`2960e5bd1a1a6629d7229d261f7c2bdd4e53c106` on 2026-08-27.

## Frozen contract

The tracked
[`quickdraw.bdq-third-update.v1`](../../Research/trainer/bdq-third-update-contract-v1.json)
contract has SHA-256
`930839d2a19022b6debc0ad48cfc7f64cd86ff948be2690a9989a48598cda528`
and binds R3J SHA-256
`a8d47b166cdf1d553a9da5dbe0b028b7a658341bea894de359848644fa3be8a5`.
The exact R3J prefix contains `10005` transitions, transition-subset SHA-256
`0cf694116eba2678d2e17f1178e2bd3552a6835e4f0b2960e0fa6beba0adf812`,
and source canonical trace SHA-256
`5e3a8ea3d2c0f0afb87fd87f92f6bf90036a6a95fc3f6124ccc0910ca07aa906`.

## Accepted live evidence

After preserving all R3J state, the same selector made only these new
selections:

| Completed transitions | Epsilon |
|---:|---:|
| `10005` | `0.999955` |
| `10006` | `0.999946` |
| `10007` | `0.999937` |

Completing transition `10008` opened update 3. The full update sequence was:

| Update | Decision | Loss | Mean absolute TD error | Online SHA-256 |
|---:|---:|---:|---:|---|
| `1` | `10000` | `0.01628389209508896` | `0.06243317946791649` | `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e` |
| `2` | `10004` | `0.014819225296378136` | `0.06711231172084808` | `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471` |
| `3` | `10008` | `0.008735351264476776` | `0.06769348680973053` | `4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b` |

Each fresh process completed `10008` transitions, `215` episodes, three
truncations, action counts `[1857,1742,1592,1605,1593,1619]`, three updates,
zero target syncs, and no pending decision or post-update selection. The
target remained
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

Evidence hashes:

- R3K transition-prefix SHA-256
  `18817aa05c80a6d361dbb288665ba344fe3540bfcb067d773fbb712d1d37f9bd`
- canonical trace SHA-256
  `c3fafe259dfc03d69e06c758af0c2ba4df3b5da3322d325a5e361cdcf3a4ff02`
- each serialized trace SHA-256
  `4e4733dd5e5cbfbd7daa21f6d2ad8c48981b4369769d8df000b709e9c115dde4`
- accepted ignored result SHA-256
  `f8531f98077be1e4ccadfd374bdff7f76b1bedce305e6bdd4f46561cfc1e2da4`

The accepted-result hash was recomputed from the ignored artifact during the
documentation migration.

## Validation and limits

All `13` focused R3K cases, all `131` trainer tests, all `148` Python research
tests, and the pinned dependency check passed. R3K proves the recurring update
boundary through update 3 only. It does not demonstrate update 4, a post-update
action, extended training, target sync, checkpoint/export, ROCm training, or
policy effectiveness.
