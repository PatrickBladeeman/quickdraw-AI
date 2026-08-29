# R3N: lossless memory-bounded replay storage

Status: completed and pushed in
`ca66335ce4e413ce7c4c35827d71154a254b850e` on 2026-08-29.

## Frozen contract

The tracked
[`quickdraw.bdq-replay-storage.v1`](../../Research/trainer/bdq-replay-storage-contract-v1.json)
contract has SHA-256
`ece35b60208adbb9ca0d36f8d61b3be652aae4a94ffdb7d2bcafc9ace58e16a9`.
It binds R3M contract SHA-256
`0a6f209d93ef6d522a53f24807d4ce48e6e820a344905e9762583bbe13a72dbb`
and full pushed commit
`2ec3ec39d25d5d3bb5686574255898f3f5605d3f`.

## Storage contract

The unchanged public replay interface has capacity `100000`, batch size `64`,
float32 HWC `[84,84,4]` observations, uniform sampling without replacement via
NumPy `Generator.PCG64`, physical ring-slot indices, and transition fields:
observation, action, reward, next observation, current/next masks, terminated,
and truncated.

The former storage owned two complete float32 observation stacks per
transition:

- bytes per observation `112896`
- bytes per transition's observations `225792`
- capacity payload `22579200000` bytes, or `21.03 GiB`, before Python overhead

R3N stores exact raw float32 `[84,84]` channel frames keyed by their exact
C-contiguous bytes, plus preallocated columnar transition metadata. Exact
values are:

- bytes per frame `28224`
- frame-reference dtype `uint64`
- frame references per transition `8`
- reference counting and orphan reclamation enabled
- reconstruction bit-exact, C-contiguous, float32 HWC
- no quantization or lossy compression
- an over-budget insertion raises `MemoryError` before visible replay mutation

Accounted-storage values:

- ceiling `4294967296` bytes (`4 GiB`)
- frame accounting reserve `1024` bytes per frame
- metadata-array reserve `256` bytes
- fixed reserve `65536` bytes
- metadata arrays `10`
- metadata payload at capacity `9600000` bytes
- metadata accounted at capacity `9668096` bytes
- registered Basic distinct render-state upper bound `81`
- registered Basic projected accounted bytes `12037184`
- conservative sequential unique-frame count `100004`
- conservative sequential projection `2934585088` bytes
- maximum unique frames within the accounting ceiling `146515`

The accounting intentionally excludes caller-owned transitions, transient
sampled batches, Python/interpreter baseline, online and target networks,
optimizer state, and Unity process memory.

## Exact replay equivalence

Legacy-oracle comparison is bitwise for indices, observations, actions,
rewards, next observations, both mask sets, terminated, and truncated fields.
It preserves shapes, dtypes, order, seeded RNG consumption, ring wraparound,
terminal discontinuities, and truncation discontinuities.

Production sample-index hashes are:

| Replay size | SHA-256 |
|---:|---|
| `10000` | `ce3daae8cb092f11074c30299313c8e61052bb42f76e8b90bb46281af53c9a49` |
| `10004` | `c1a8b2fd7fcd64dc8c1375e536d8d2e5cd9e88809349d79336cf63777f8284f4` |
| `10008` | `c2e180bea9bd403ae2b0296fe55478aea10a44cbb6d1d1726e966c0df8dcbb4d` |
| `10012` | `de8af0d1e05eecfcb37bb52015fbd61f7124ec6ce46f3c3eef35e72cea86750a` |

Combined production sample-index SHA-256:
`f2e64136bd4dda6500e3a12c34ba9f4c362d0c1afba9e0743d766a786dd1ff9b`.

## Fresh frozen-R3M regression

One fresh post-R3N process was compared against the frozen two-worker pre-R3N
R3M evidence. It retained:

- transition count `10012`
- optimizer-update count `4`
- target-sync count `0`
- serialized trace SHA-256
  `762fd1d090dc88529f3ad86cd0ad87080aff6494587c10223ae89118bb910a51`
- canonical trace SHA-256
  `cd2fa70672432e74c16c34c0525035953961ac3845cbe3362e061373cf48a940`
- all-transitions SHA-256
  `9b3fc70c5e3cdbc40c9332460ef702304086aa6d07c8467a411c31bcba059bef`
- tail-four-transitions SHA-256
  `6c5d8647a1868f4f3c770b98e5bd8077f6b12a24bafceb4f5f384751156104e1`
- update-events SHA-256
  `7f8d558ae177c52170841b8b48136e4b35eccb9fb478e9c0ce42d3193deaceba`

The update decisions remained `[10000,10004,10008,10012]`; losses remained
`[0.01628389209508896,0.014819225296378136,0.008735351264476776,0.0085072573274374]`;
mean absolute TD errors remained
`[0.06243317946791649,0.06711231172084808,0.06769348680973053,0.06249994412064552]`;
and online hashes remained:

1. `7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e`
2. `6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471`
3. `4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b`
4. `a8356df1531b99a42966578c6fd784cd384c8bcd3d3c3092124df13b2587268f`

The target remained
`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.

The accepted trace contained `1549` distinct full-stack hashes. Treating all
channels as distinct gives a conservative `6196`-frame,
`174875904`-byte frame-payload upper bound and `190888704`-byte accounted
upper bound.

## Validation and negative evidence

Validation passed all `12` focused R3N cases, all `180` trainer tests, all
`197` Python research tests, all `31` normal-graphics Unity EditMode tests,
contract/live-trace validation, bytecode compilation, the pinned dependency
check, and the Unity player build.

The first Unity visual-sensor test invocation incorrectly used `-nographics`,
forcing a null graphics device. It produced `30` passes and one expected
camera-rendering failure. The unchanged normal-graphics rerun passed `31` of
`31`; no code, contract, or acceptance threshold changed.

R3N is lossless replay-equivalence and bounded-accounting evidence for the
registered stream. It is not a throughput or memory-performance benchmark,
does not prove that every possible arbitrary float32 stream fits, and does not
demonstrate update 5, target synchronization, extended training,
checkpoint/resume/export, ROCm training, Unity behavior changes, or policy
effectiveness.
