# R3D: direct LLAPI collection and truncation-mask transport

Status: completed and pushed in
`a4b449d4c484ae9607f9765083dd5008a05bb4dc` on 2026-08-22.

## Frozen contract

The tracked
[`quickdraw.bdq-llapi.v1`](../../Research/trainer/bdq-llapi-contract-v1.json)
contract has SHA-256
`5e321f320d109c8cc60d65b6993e64e77e5926c95cb5308e6db0ca8b3b7b3c94`.
It binds:

- Basic contract SHA-256
  `d0803181993a9b31d089a483fc0e4499980ec5893625be5a9188e0db68c7153d`
- R3A foundation SHA-256
  `9a97d8b58ed08e816f032784069e7b1c38b7185df73b4b8edd504dc58112cfb9`
- R3B optimizer SHA-256
  `1095419f9ebc11050e188ce042b55ca578cf8bf320a6321a5b98470bc98e3849`

The runtime is the shared R3D-R3N CPU runtime in [README.md](README.md).
Collection used scenario seed `31001` and policy seed `51001`.

R3D replaced the high-level trajectory/plugin experiment with synchronous
`mlagents_envs.environment.UnityEnvironment` collection. One pending decision
per agent is completed exactly once when that agent next appears in
`DecisionSteps` or `TerminalSteps`. Ordinary continuation receives its next
mask from `DecisionSteps`; a true terminal uses an irrelevant all-available
sentinel because it does not bootstrap.

For decision-limit truncation, Unity publishes the authoritative final-state
mask over `quickdraw.basic-truncation-mask.v1`, channel UUID
`0541088f-93b9-4299-8c9e-af7431da553a`. Python does not infer the mask from
scene state. The contract fixes decision limit `300`; mask value `true` means
unavailable.

## Accepted live evidence

Two fresh Windows player/Python processes produced exactly the same `302`
transitions apiece:

| Episode | End | Transitions | Return | Selector |
|---:|---|---:|---:|---|
| `0` | terminal `target_hit` | `2` | `0.9600000102072954` | online-network masked greedy |
| `1` | interrupted `decision_limit` | `300` | `-2.9999999329447746` | fixed left, then stay/idle |

The truncated episode ended at slot `-4` with final masks
`[[false,true,false],[false,false]]`. Every decision became one immutable
replay transition. Optimizer-update and target-synchronization counts remained
`0`; online and target hashes both remained
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

The following hashes were recomputed during the documentation migration from
the accepted ignored files under
`Artifacts/Experiments/r3d-llapi/acceptance-final/`. They are curated hashes
of ignored artifacts; the raw generated files are not tracked:

- canonical trace SHA-256
  `c0cfff120bd5a41d0bf748681608f0b8e366b5844e53450215762df0767ec9d4`
- each serialized worker trace SHA-256
  `a7d2a6a38f622ad09fe7b501d068fc7a63f389fec2bdda903018323f7a5299af`
- accepted result SHA-256
  `a5852ee10eef1f7fcb9a29893e9aa30c124b36f53a6d66ff4d33ee6e64d09376`

## Validation and limits

Validation passed all `39` trainer tests, all `56` Python research tests,
`13` focused Unity Basic episode tests, and the complete `31`-test Edit Mode
suite. The saved Windows `Research_Basic` player was used for both fresh
processes.

R3D is terminal/truncation transport and replay-construction evidence. It is
not a training session and demonstrates no optimizer update, target sync,
epsilon schedule, checkpoint, export, ROCm training, learned-policy quality,
strategic combat, reflex, or LLM behavior.

