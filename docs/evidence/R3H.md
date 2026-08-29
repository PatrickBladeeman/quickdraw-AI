# R3H: live greedy handoff after optimizer update 2

Status: completed and pushed in
`769c4de4cdba7f5a116341ac7b9194518d5a7f77` on 2026-08-23.

## Frozen contract

The tracked
[`quickdraw.bdq-post-update-handoff.v1`](../../Research/trainer/bdq-post-update-handoff-contract-v1.json)
contract has SHA-256
`53331db49c21d16c005ba6b1e7409a1cf40a1480d4f14d72d325700099bef581`
and binds R3G SHA-256
`436329e61c3a40d5a7d94df73ff022b89931a6a6927cfe4ab49b391d2877a53d`.
Its frozen R3G prefix contains `10004` transitions with transition-subset
SHA-256
`45554af94700fa1429e3487dcf2bd62f1c71f7419b4f1f80f0cf0ad905670f69`.

## Accepted live evidence

Two fresh processes preserved every R3G transition and both optimizer events,
then evaluated the live decision-`10004` observation with the twice-updated
online network and frozen target. One explicit epsilon-`0.0` masked online
argmax selected legal action `[2,1]` under masks
`[[false,true,false],[false,false]]` and completed transition `10005`.

The handoff evidence is:

- episode index `215`, episode decision index `43`
- observation SHA-256
  `8d10e324956e2d5b7b8a7d70da58d33a9b170598727998146dcfec858bab8a83`
- online movement Q-values
  `[0.05902547389268875,0.04061580449342728,0.09654882550239563]`
- online combat Q-values
  `[0.0541328564286232,0.07666055113077164]`
- target movement Q-values
  `[-0.021374966949224472,-0.02829865738749504,0.060257185250520706]`
- target combat Q-values
  `[-0.004793909378349781,0.011849619448184967]`
- maximum absolute online-target Q delta
  `0.08040044084191322`
- online SHA-256
  `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471`
- frozen target SHA-256
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`

Each process finished with `10005` transitions, `215` completed episodes,
three truncations, action counts `[1854,1741,1592,1605,1593,1620]`, two
optimizer updates, zero target synchronizations, and no pending decision.

Evidence hashes:

- canonical trace SHA-256
  `062deda3e8296499d6366a68bd4a0b84e539127ec320a337a7544f496395217e`
- each serialized worker trace SHA-256
  `4341790871e0b5e3a990923601b45c052e9fb85e1e8ca20ae179421bb7977a87`
- accepted ignored result SHA-256
  `b65bbbe396725503da9fcfb93104430535b07b6c9af59775cb4da0139bd49928`

The result hash was recomputed from the ignored accepted artifact during the
documentation migration; the raw result is not tracked.

## Validation and limits

All `77` trainer tests and all `94` Python research tests passed. R3H proves
that the twice-updated online weights reach one legal live action-selection
boundary. It does not prove that either update caused the chosen action, that
the policy is effective, or that extended training, epsilon decay, update 3,
target synchronization, checkpoint/export, or ROCm training works.

