# R3E: seeded epsilon-greedy collection below warmup

Status: completed and pushed in
`6aef0626fbc05e55fc90406b542becdfb5cadbc5` on 2026-08-23.

## Frozen contract

The tracked
[`quickdraw.bdq-epsilon-collection.v1`](../../Research/trainer/bdq-epsilon-collection-contract-v1.json)
contract has SHA-256
`3673e37f20edfcb0f4044b6257fce88d65ff8d56ab09c25166459192cac77f2c`
and binds R3D contract SHA-256
`5e321f320d109c8cc60d65b6993e64e77e5926c95cb5308e6db0ca8b3b7b3c94`.

Collection used scenario seed `31001`, policy seed `51001`, exploration seed
`61001`, fixed epsilon `1.0`, and a CPU `torch.Generator`. Each branch samples
uniformly over ascending legal indices. Epsilon decay is disabled. The cutoff
is exactly `1000` transitions, below replay warmup `10000`.

## Accepted live evidence

Two fresh player/Python processes produced byte-identical complete traces.
Each had:

- exactly `1000` transitions
- `18` completed episodes/reset boundaries
- one authoritative truncation
- one active collection-cutoff episode, so `19` episode records in the trace
- all six action tuples with counts `[167,191,154,167,155,166]`
- no pending decision at cutoff
- zero optimizer updates and zero target synchronizations
- unchanged online and target hash
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`

The truncation occurred in episode `17` at decision `300`, slot `4`, with
final masks `[[false,false,true],[false,false]]`. The next active episode was
cut off cleanly after `51` transitions without claiming a Unity episode end.

These hashes were recomputed from accepted ignored artifacts under
`Artifacts/Experiments/r3e-epsilon-collection/acceptance-1/` during the
documentation migration:

- canonical trace SHA-256
  `d581bce8ee9facf4509f47aad93de1515019e7f4098e3a79433e4ac161d30b81`
- each serialized worker trace SHA-256
  `c33421f689082f85db49ff5b99ef247b34a75f7b05a4bb2a5278bbe4c2511472`
- accepted result SHA-256
  `e22461512a2eb241a50c230fddd866aeec04462e3a7d339067af2be829d7f1b7`

They are curated hashes of ignored artifacts; the generated files are not
tracked.

## Validation and limits

All `47` trainer tests and all `64` Python research tests passed. R3E proves
deterministic mask-safe exploration across reset boundaries and a clean
below-warmup cutoff. It does not demonstrate gradients, changed weights,
epsilon decay, checkpoint/export, ROCm execution, extended training, or policy
effectiveness.

