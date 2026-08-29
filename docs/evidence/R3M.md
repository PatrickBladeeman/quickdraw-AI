# R3M: scheduled optimizer update 4

Status: completed and pushed in
`2ec3ec39d25d5d3bb5686574255898f3f5605d3f` on 2026-08-28.

## Frozen contract

The tracked
[`quickdraw.bdq-fourth-update.v1`](../../Research/trainer/bdq-fourth-update-contract-v1.json)
contract has SHA-256
`0a6f209d93ef6d522a53f24807d4ce48e6e820a344905e9762583bbe13a72dbb`
and binds R3K SHA-256
`930839d2a19022b6debc0ad48cfc7f64cd86ff948be2690a9989a48598cda528`.
It resumes R3K's uninterrupted production trajectory and explicitly excludes
R3L's diagnostic epsilon-zero transition.

The frozen R3K prefix has `10008` transitions, transition-subset SHA-256
`18817aa05c80a6d361dbb288665ba344fe3540bfcb067d773fbb712d1d37f9bd`,
and source canonical trace SHA-256
`c3fafe259dfc03d69e06c758af0c2ba4df3b5da3322d325a5e361cdcf3a4ff02`.

## Accepted live evidence

The same scheduled selector, RNG, controller, replay, networks, and optimizer
continued without reset:

| Completed transitions | Epsilon |
|---:|---:|
| `10008` | `0.999928` |
| `10009` | `0.999919` |
| `10010` | `0.99991` |
| `10011` | `0.999901` |

Completing transition `10012` opened update 4. The full optimizer record is:

| Update | Decision | Loss | Mean absolute TD error | Online SHA-256 |
|---:|---:|---:|---:|---|
| `1` | `10000` | `0.01628389209508896` | `0.06243317946791649` | `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e` |
| `2` | `10004` | `0.014819225296378136` | `0.06711231172084808` | `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471` |
| `3` | `10008` | `0.008735351264476776` | `0.06769348680973053` | `4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b` |
| `4` | `10012` | `0.0085072573274374` | `0.06249994412064552` | `a8356df1531b99a42966578c6fd784cd384c8bcd3d3c3092124df13b2587268f` |

Each accepted process completed `10012` transitions, `215` completed
episodes, three truncations, action counts
`[1857,1742,1593,1606,1595,1619]`, four updates, zero target syncs, and no
pending decision. No action was selected after update 4. The target stayed at
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

The standalone player was changed only to run while unfocused. Graphics
remained enabled, no standalone-player arguments were supplied, and the
rebuilt `globalgamemanagers` SHA-256 was
`23cce72e183cbb7c4c78850f1ba46d819e9d1bc60fbafbe970a112fa65cf4a47`.
Exact R3K-prefix validation established that this operational setting did not
alter accepted observations or transitions.

Evidence hashes:

- canonical trace SHA-256
  `cd2fa70672432e74c16c34c0525035953961ac3845cbe3362e061373cf48a940`
- each accepted serialized trace SHA-256
  `762fd1d090dc88529f3ad86cd0ad87080aff6494587c10223ae89118bb910a51`
- accepted result SHA-256
  `b79a1ba8ab0d23964c225a9b33236226b1c033f8e3de972d61e759f90d890d67`

The two completed traces came from independent fresh attempts and were joined
only by the fail-closed comparison mode.

## Required negative and rejected evidence

- Five runs of the older background-disabled player timed out at
  `environment.step()`.
- A `-batchmode` experiment completed, but its camera-observation hash diverged
  at transition `0`.
- The completed batchmode trace was rejected by the exact canonical R3K-prefix
  gate and did not count toward acceptance.
- No acceptance threshold, trace requirement, timeout result, or canonical
  prefix was weakened after these failures.

## Validation and limits

All `15` focused R3M cases, all `168` trainer tests, all `185` Python research
tests, all `31` Unity EditMode tests, the pinned dependency check, Unity player
build, and accepted-result/schema revalidation passed.

R3M proves only the bounded fourth scheduled update. It does not open update
5, synchronize the target, select a post-update action, run extended training,
checkpoint/export, execute ROCm training, perform held-out evaluation, or
demonstrate policy effectiveness.
