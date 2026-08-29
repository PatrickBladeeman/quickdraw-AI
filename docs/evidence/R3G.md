# R3G: second Unity-derived optimizer update

Status: completed and pushed in
`df036ebfc86a9e8367d501b9b6ff598ec52a7d8e` on 2026-08-23.

## Frozen contract

The tracked
[`quickdraw.bdq-two-update.v1`](../../Research/trainer/bdq-two-update-contract-v1.json)
contract has SHA-256
`436329e61c3a40d5a7d94df73ff022b89931a6a6927cfe4ab49b391d2877a53d`
and binds R3F SHA-256
`edc2af190d778b9d43238a440e30c9ffd36a4b246a07933c03e233b3e2e94875`.

The unchanged fixed-epsilon seeded run stops at `10004` transitions and
registers update decisions `[10000,10004]`.

## Accepted live evidence

Each of two fresh CPU player/Python processes completed:

- `10004` transitions
- `215` completed episodes/reset boundaries and one active cutoff record
- `3` truncations
- all six action tuples, counts `[1854,1741,1592,1605,1593,1619]`
- exactly `2` optimizer updates
- zero target synchronizations
- no pending decision

The first `10000` transitions and first-update evidence exactly preserve R3F.
The update sequence is:

| Update | Decision | Loss | Mean absolute TD error | Online SHA-256 after update |
|---:|---:|---:|---:|---|
| `1` | `10000` | `0.01628389209508896` | `0.06243317946791649` | `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e` |
| `2` | `10004` | `0.014819225296378136` | `0.06711231172084808` | `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471` |

The target stayed at
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

These hashes were recomputed from accepted ignored artifacts under
`Artifacts/Experiments/r3g-two-update/acceptance-1/`:

- canonical trace SHA-256
  `3f545cb1b483cd82b8d70cb86668a53ca95beb348c83d89a8f136a2536ccd6e8`
- each serialized worker trace SHA-256
  `157cc826d99696fa5c137b596e8eafd04b4abba520c8af5d93b7355b8bdc5576`
- accepted result SHA-256
  `e344de1fcf76092e8d2c9f7a3712020663b5f7d358aaedbeeaea536184ae6d2f`

They are curated hashes of ignored artifacts; the raw evidence is not tracked.

## Validation and limits

All `69` trainer tests and all `86` Python research tests passed. R3G proves
one recurrence of the production update boundary. It does not demonstrate a
third update, epsilon decay, target synchronization, an extended training
rollout, checkpoint/export, ROCm training, or learned-policy effectiveness.

