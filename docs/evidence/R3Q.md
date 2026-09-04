# R3Q: live-derived trainer checkpoint gate

Status: completed and verified in the working tree on 2026-09-04. The task
changes remain uncommitted and unpushed as requested.

## Frozen contract

The tracked
[`quickdraw.bdq-live-checkpoint.v1`](../../Research/trainer/bdq-live-checkpoint-contract-v1.json)
contract has SHA-256
`a5e96d9e40202c1326cee0c6d738cc98ee82dcc76812de823a12a84c1cb5f6f6`.
It binds the unchanged R3O contract SHA-256
`35dcd10971878bef31d8e2dd9392599cd71607a009ac6cb8d93bff3857eadcb0`
(pushed commit `028143fff494c6234fd17832dd41199aee5a6fad`) and the unchanged
R3P checkpoint contract SHA-256
`071fa03eac09f451bf87455951a634943e77ba6873a3457ca6bf00a4d447c755`
(pushed commit `0d78c783897225395ed44304fb6b0124a4620582`).

## Accepted live-derived evidence

The single fresh Unity-backed saver used the existing R3O Basic player and
stopped at the registered clean boundary:

| Field | Accepted value |
|---|---:|
| Completed transitions and decisions | `10016` |
| Optimizer updates | `5` |
| Target synchronizations | `0` |
| Completed episodes / truncations | `215` / `3` |
| Action-tuple counts | `[1859,1742,1594,1606,1596,1619]` |
| Policy / exploration seeds | `51001` / `61001` |
| Pending decisions | `[]` |
| Post-update action selected | `false` |
| Online network SHA-256 | `8275fed953fb594fea0e88c50da15a862e1db6a3e296dd953dd10e048c2c3cbe` |
| Target network SHA-256 | `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb` |

The lossless replay boundary contained capacity `100000`, size `10016`,
cursor `10016`, `80128` frame references, `81` unique frames,
`2286144` frame-payload bytes, `9600000` metadata-payload bytes,
`12037184` accounted bytes, and `4282930112` remaining bytes under the
registered `4294967296`-byte ceiling.

The saved checkpoint is `40373245` bytes with SHA-256
`fa6e70625807c7484f94b68f2c9a76aa9384c93e6a0ee67ebb9c4b889a0e9735`.
Its canonical encoded-state SHA-256 is
`a899a2e0832623ef933a11e086db1c9036d9e5fc112aab2cd6eccd59b7d9299b`.
The fresh CPU Python restorer reproduced that state digest and boundary
field-for-field before sampling, without starting Unity.

The next replay sample used batch size `64` and indices:

`[9145,3682,6154,4406,6348,8055,3188,969,7015,4785,658,7641,6678,9225,4175,6144,9992,7520,5595,5580,1693,6614,9478,5071,8829,4898,5957,5161,4972,3321,1863,4604,9863,5915,635,7350,34,7951,6328,9578,1568,1120,7539,2538,6081,9349,954,3118,4317,637,4358,9562,2644,5883,1507,6258,1493,6747,4940,3062,4515,6743,3659,3115]`

The saver and restorer matched all recorded field fingerprints, including
observations, actions, rewards, next observations, masks, terminal flags, and
truncation flags.

Evidence hashes:

- serialized live trace SHA-256
  `798492f929b27dfbef5b4d3e6f9c886fdd34193f958359e4b6b9de49e535fc2f`
- canonical live trace SHA-256
  `e50182eb2ac6459b835648b3d3eadb7e16f27b33e3c22084de602bfe0c686eca`
- accepted R3O result SHA-256
  `149b784367d3de736ae86b9b3c9aa31e79a62d485895ba9a6cf5c2c3598e36ff`
- R3Q result SHA-256
  `e68df0c254252d815b2edef81cb8e93dc2d0f6b22ec0b184ead3479f00478067`

The raw trace, checkpoint, logs, and result are retained only under the
ignored path `Artifacts/Experiments/r3q-live-checkpoint/acceptance/`.

## Validation and limits

Validation passed the `10` focused R3Q cases, all `232` trainer tests,
contract and result schema validation, bytecode compilation, and the live
one-saver/one-restorer boundary. The complete trainer suite includes the
frozen R3O and R3P regression cases. The run used no changed Unity code,
registered value, R3O artifact, or R3P schema/evidence.

R3Q proves live-derived checkpoint persistence and Unity-free Python restore at
the R3O boundary. It does not select an action after update 5, collect
transition `10017`, run optimizer update 6, synchronize the target, resume
Unity, extend training, select a final checkpoint, export ONNX, execute ROCm
training, perform held-out evaluation, or demonstrate policy effectiveness.
