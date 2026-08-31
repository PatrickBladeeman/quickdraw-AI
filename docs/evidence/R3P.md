# R3P: deterministic Python trainer checkpoint round-trip

Status: completed in the working tree on 2026-08-31; not yet committed.

## Frozen contract

The tracked
[`quickdraw.bdq-checkpoint.v1`](../../Research/trainer/bdq-checkpoint-contract-v1.json)
contract has SHA-256
`071fa03eac09f451bf87455951a634943e77ba6873a3457ca6bf00a4d447c755`.
It binds the frozen R3O contract SHA-256
`35dcd10971878bef31d8e2dd9392599cd71607a009ac6cb8d93bff3857eadcb0`
(pushed commit `028143fff494c6234fd17832dd41199aee5a6fad`).

## Accepted live evidence

The checkpoint boundary saved at a clean point of the registered synthetic
workload: decision count `36`, four completed optimizer updates, zero target
synchronizations, an empty pending-decision set, and a wrapped replay ring
(`32` of `32` transitions, cursor `4`, `20` unique frames, `656128` accounted
bytes, `7225344` legacy bytes). The boundary online network SHA-256 was
`352c14f2fc6e89019505db35b9c809e7004c39d19f5048beae186051d1f26d61`; the
target network still equaled the registered initial network
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`
because the workload uses policy seed `51001` and never synchronizes.

Three independent fresh CPU Python processes — an uninterrupted reference, a
saver, and a restored process — agreed exactly:

- the saver boundary matched the reference boundary field-for-field;
- the restored process loaded the checkpoint without Unity and reproduced the
  reference boundary exactly (network hashes, counters, replay contents,
  cursor, accounting, and RNG states);
- the next replay sample after the boundary was the same in both continuations
  (sampled indices `[16,6,10,28,17,5,20,13]`); and
- the bounded next optimizer update at decision count `40` matched exactly:
  loss `0.5934518575668335`, mean absolute TD error `0.99898761510849`,
  online-after SHA-256
  `3117157b5df094235256308bdc56f50d92bf46f43ebf818b62f6e0cd9bfe4bbe`,
  unchanged target hash `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`,
  and continuation actions `[[1,1],[0,1],[1,1],[2,0]]`.

Evidence hashes:

- accepted checkpoint SHA-256
  `45b37bad4fa4093acc6e2f72fa5af5be47e83588ca4c35715d96d5a5d5638fda`
  (`36785844` bytes, stored only under the ignored artifact root)
- accepted result SHA-256
  `3a0bc6b5469353ba0c72000bae954c04c2f13b1ee92f3ef47abbc7b3071a3c60`

The checkpoint itself carries a SHA-256 over its canonical encoded state
subtree and is rejected on load when unreadable, schema-incomplete, corrupted,
or incompatible (schema version, contract, package, runtime, settings, or seed
drift). Rejection happens before any restored object is returned.

## Negative and rejected evidence

No live attempt failed: the three workers and every comparison passed on the
first run, and the final hardened code reproduced the identical accepted
evidence (including byte-identical checkpoint bytes and an identical result
file). Corruption, incompleteness, incompatibility, a dirty pending boundary,
a hash-consistent but internally incoherent state, a hash-consistent masked
action row, and a hash-consistent incomplete Adam state are exercised only by
the focused negative tests, which prove each rejection path raises before any
restored state becomes visible. No acceptance threshold or registered value
was changed after observing results.

## Validation and limits

Validation passed all `18` focused R3P cases, all `214` trainer tests, all
`231` Python research tests, contract/checkpoint/result schema validation,
bytecode compilation, the pinned dependency check (now declaring
`jsonschema==4.23.0`, which the checkpoint module requires), and the
three-fresh-process boundary without a Unity player.

R3P proves deterministic Python-only persistence and restoration of one
registered synthetic boundary. It does not open a Unity rollout, transition
`10017` on the R3O trajectory, optimizer update 6 on that trajectory, an action
with update-5 weights, target synchronization, extended training, final
checkpoint selection, ONNX export or exported-inference parity, ROCm training,
multi-environment collection, or any effectiveness claim.
