# R3O: scheduled optimizer update 5

Status: completed, verified, committed, and pushed on 2026-08-30 in
`028143fff494c6234fd17832dd41199aee5a6fad`.

## Frozen contract

The tracked
[`quickdraw.bdq-fifth-update.v1`](../../Research/trainer/bdq-fifth-update-contract-v1.json)
contract has SHA-256
`35dcd10971878bef31d8e2dd9392599cd71607a009ac6cb8d93bff3857eadcb0`.
It binds the frozen R3M contract SHA-256
`0a6f209d93ef6d522a53f24807d4ce48e6e820a344905e9762583bbe13a72dbb`
(pushed commit `2ec3ec39d25d5d3bb5686574255898f3f5605d3f`) and the frozen
R3N replay-storage contract SHA-256
`ece35b60208adbb9ca0d36f8d61b3be652aae4a94ffdb7d2bcafc9ace58e16a9`
(pushed commit `ca66335ce4e413ce7c4c35827d71154a254b850e`).

The frozen R3M/R3N prefix has `10012` transitions, canonical transitions
SHA-256
`9b3fc70c5e3cdbc40c9332460ef702304086aa6d07c8467a411c31bcba059bef`,
and source canonical trace SHA-256
`cd2fa70672432e74c16c34c0525035953961ac3845cbe3362e061373cf48a940`.

## Accepted live evidence

The same scheduled selector, RNG, controller, lossless replay, networks, and
optimizer continued without reset beyond the accepted R3M boundary:

| Completed transitions | Epsilon |
|---:|---:|
| `10012` | `0.999892` |
| `10013` | `0.999883` |
| `10014` | `0.999874` |
| `10015` | `0.999865` |

Completing transition `10016` opened update 5. The full optimizer record is:

| Update | Decision | Loss | Mean absolute TD error | Online SHA-256 |
|---:|---:|---:|---:|---|
| `1` | `10000` | `0.01628389209508896` | `0.06243317946791649` | `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e` |
| `2` | `10004` | `0.014819225296378136` | `0.06711231172084808` | `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471` |
| `3` | `10008` | `0.008735351264476776` | `0.06769348680973053` | `4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b` |
| `4` | `10012` | `0.0085072573274374` | `0.06249994412064552` | `a8356df1531b99a42966578c6fd784cd384c8bcd3d3c3092124df13b2587268f` |
| `5` | `10016` | `0.00121649622451514` | `0.03924498334527016` | `8275fed953fb594fea0e88c50da15a862e1db6a3e296dd953dd10e048c2c3cbe` |

Each accepted process completed `10016` transitions, `215` completed
episodes, three truncations, action counts
`[1859,1742,1594,1606,1596,1619]`, five updates, zero target syncs, and no
pending decision. No action was selected after update 5; the final four
selections used update-4 weights at completed-transition counts
`10012`-`10015`. The target stayed at
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

The standalone player was rebuilt from the unchanged Unity project with
normal graphics, ran while unfocused, and received no standalone-player
arguments. The rebuilt `globalgamemanagers` SHA-256 was
`23cce72e183cbb7c4c78850f1ba46d819e9d1bc60fbafbe970a112fa65cf4a47`. Exact
R3M-prefix validation established that this operational setting did not
alter accepted observations or transitions.

Evidence hashes:

- canonical trace SHA-256
  `e50182eb2ac6459b835648b3d3eadb7e16f27b33e3c22084de602bfe0c686eca`
- each accepted serialized trace SHA-256
  `798492f929b27dfbef5b4d3e6f9c886fdd34193f958359e4b6b9de49e535fc2f`
- accepted result SHA-256
  `149b784367d3de736ae86b9b3c9aa31e79a62d485895ba9a6cf5c2c3598e36ff`
- all-transitions SHA-256
  `3f973d98648255fda4e37637120c3591f14560e958c71cf048a09df506be37ba`
- tail-four-transitions SHA-256
  `d7cae368fd919de33d34f3dd519383b9f0ebe07f3e0d8cb26d46136cf5398a94`

The two completed traces came from independent fresh attempts and were
joined only by the fail-closed comparison in the acceptance runner.

## Negative and rejected evidence

None. The rebuilt player, both fresh workers, and the fail-closed comparison
passed on the first live R3O attempt; there are no rejected, timed-out,
batch-mode, or headless runs to qualify this record. No acceptance threshold,
trace requirement, or canonical prefix was changed after observing results.

## Validation and limits

Validation passed all `16` focused R3O cases, all `12` R3N replay
regressions, all `196` trainer tests, all `213` Python research tests,
contract and trace schema validation, bytecode compilation, the pinned
dependency check, the normal-graphics Unity player build, and the live
two-worker boundary.

R3O proves only the bounded fifth scheduled update on the unchanged R3N
production path. It does not open update 6, synchronize the target, select an
action with update-5 weights, run extended training, checkpoint/export,
execute ROCm training, perform held-out evaluation, or demonstrate policy
effectiveness.
