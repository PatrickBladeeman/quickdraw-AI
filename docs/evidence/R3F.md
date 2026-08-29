# R3F: production warmup and first Unity-derived update

Status: completed and pushed in
`7edf7a3d54455e78e7207b04025bd75fae1b4c9f` on 2026-08-23.

## Frozen contract

The tracked
[`quickdraw.bdq-warmup-update.v1`](../../Research/trainer/bdq-warmup-update-contract-v1.json)
contract has SHA-256
`edc2af190d778b9d43238a440e30c9ffd36a4b246a07933c03e233b3e2e94875`
and binds R3E SHA-256
`3673e37f20edfcb0f4044b6257fce88d65ff8d56ab09c25166459192cac77f2c`.

R3F retains scenario seed `31001`, policy seed `51001`, exploration seed
`61001`, fixed epsilon `1.0`, legal branch-wise sampling, and the shared
production optimizer defaults. No update may occur through transition
`9999`; exactly one batch-`64` Adam update opens at completed transition
`10000`.

## Accepted live evidence

Each of two fresh CPU player/Python processes completed:

- `10000` transitions
- `215` completed episodes/reset boundaries and one active cutoff record
- `3` truncations
- all six action tuples, counts `[1853,1741,1592,1603,1592,1619]`
- one optimizer update at decision `10000`
- zero target synchronizations
- no pending decision

Update 1 recorded:

- Huber loss `0.01628389209508896`
- mean absolute TD error `0.06243317946791649`
- online hash before
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`
- online hash after
  `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e`
- unchanged target hash
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`

These hashes were recomputed from accepted ignored artifacts under
`Artifacts/Experiments/r3f-warmup-update/acceptance-2/`:

- canonical trace SHA-256
  `75c265377bbb171c24d817c7c45fb022e011b73fdb24749dd21c771ed436f08b`
- each serialized worker trace SHA-256
  `aee36f7bc5c2e2202e2738709c021826878de717d22b91345001dafd8599f0b2`
- accepted result SHA-256
  `8c35aad1249d9ffc14e755d2abc90c902d3e8f8c2b2761f94d972236c8a315cd`

They are curated hashes of ignored artifacts. The standalone watch validation
also produced serialized SHA-256
`aee36f7bc5c2e2202e2738709c021826878de717d22b91345001dafd8599f0b2`
but intentionally produced no `result.json`; it is diagnostic observation,
not a third acceptance worker. Watch mode uses one run, time scale `1`, Unity
Editor port `5004` or a visible standalone player, and reports every `100`
transitions by default.

## Validation and limits

All `62` trainer tests and all `79` Python research tests passed. R3F is the
first minimal optimizer operation on real Unity experience. One batch update
does not constitute extended training or demonstrate useful learned behavior,
epsilon decay, target synchronization, checkpoint/resume, ONNX export, ROCm
training, or policy effectiveness.

