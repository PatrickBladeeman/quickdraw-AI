# R3L: diagnostic greedy handoff after optimizer update 3

Status: completed and pushed in
`f5865076aae926c6aa013fd242f27a0f998c1dc9` on 2026-08-27.

## Frozen contract

The tracked
[`quickdraw.bdq-third-update-greedy-handoff.v1`](../../Research/trainer/bdq-third-update-greedy-handoff-contract-v1.json)
contract has SHA-256
`f56cfab90ba82e616e0e2be55f5d77d3262c98ac2dcc9bd604e735831f4b0ce6`
and binds R3K SHA-256
`930839d2a19022b6debc0ad48cfc7f64cd86ff948be2690a9989a48598cda528`.
Its R3K prefix has `10008` transitions, transition-subset SHA-256
`18817aa05c80a6d361dbb288665ba344fe3540bfcb067d773fbb712d1d37f9bd`,
and source canonical trace SHA-256
`c3fafe259dfc03d69e06c758af0c2ba4df3b5da3322d325a5e361cdcf3a4ff02`.

## Accepted live evidence

At completed count `10008`, R3L deliberately did **not** consume the
production epsilon `0.999928`. It performed one diagnostic epsilon-`0.0`
evaluation using the update-3 online network and frozen target. It selected
legal action `[2,1]` under masks `[[false,true,false],[false,false]]` and
completed transition `10009`.

Exact handoff values:

- episode index `215`, episode decision index `47`
- observation SHA-256
  `38cb9993ce836cb711c5b740cf5abcbaf7224a341194a506a133970e74b025b8`
- online movement Q-values
  `[0.06138045713305473,0.04502251371741295,0.08202166855335236]`
- online combat Q-values
  `[0.04990188032388687,0.07571455091238022]`
- target movement Q-values
  `[-0.02081460878252983,-0.027409732341766357,0.06080974265933037]`
- target combat Q-values
  `[-0.003548678010702133,0.011938948184251785]`
- maximum absolute Q delta `0.08219506591558456`
- online SHA-256
  `4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b`
- target SHA-256
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`

Each accepted trace has `10009` transitions, `215` completed episodes, three
truncations, action counts `[1857,1742,1592,1605,1593,1620]`, three optimizer
updates, zero target syncs, and no pending decision.

Evidence hashes:

- canonical trace SHA-256
  `19d5681bc78d8b1c7df0bef0e4ea3a5a32f757629428e11fa2961c5cafd581e3`
- each accepted serialized trace SHA-256
  `1334f396fa0445cf4c4563c28ef22e8fa8cfc8ce383687b3c2918d1515bc4665`
- accepted result SHA-256
  `d53971c1155634722375cdc564f7c4a5207c2fa59b0d27c1abacd3d70de898ac`

The completed workers came from separate parent attempts and were revalidated
through the fail-closed recovery comparison path. That path requires distinct
files, full schema/contract validation, object equality, and raw-byte equality.

## Negative evidence

- Three attempted Unity workers timed out at the LLAPI transport boundary.
- Two retries were operator-stopped: one for the requested cleanup and one to
  correct the sleep-suppression wrapper.
- Failed and partial workers did not count toward `fresh_process_count=2`.
- No contract, trace requirement, or acceptance threshold was weakened.

## Validation and limits

All `22` focused R3L cases, all `153` trainer tests, all `170` Python research
tests, result/schema revalidation, bytecode compilation, and the pinned
dependency check passed.

R3L proves that update-3 online weights reach one live greedy selection. It
does not prove that update 3 changed the chosen action or that the policy is
effective. It excludes update 4, production epsilon consumption at `10008`,
extended training, target sync, checkpoint/export, ROCm training, and held-out
evaluation.
