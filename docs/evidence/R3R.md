# R3R: long-horizon continuation and first target synchronization

Status: completed and verified in the working tree on 2026-09-08. The task
changes remain uncommitted and unpushed as requested.

## Contract and claim boundary

The tracked
[`quickdraw.bdq-long-horizon.v1`](../../Research/trainer/bdq-long-horizon-contract-v1.json)
contract has SHA-256
`cfb0ecad1105411f8596eedba8cf18ea5f5238bbfdc4b75b5fa0f387d7febe56`.
Its schema is
[`bdq-long-horizon-contract.schema.json`](../../Research/schemas/bdq-long-horizon-contract.schema.json),
and the generated result is checked against
[`bdq-long-horizon-smoke-result.schema.json`](../../Research/schemas/bdq-long-horizon-smoke-result.schema.json).
The contract binds the unchanged R3O contract, R3Q live-checkpoint contract,
and R3P checkpoint contract by their registered SHA-256 values.

R3R is a bounded, one-seed continuation gate. It replays the accepted R3O
prefix into trainer state, validates the accepted R3Q checkpoint boundary, and
then collects from a fresh complete copy of the Basic player for each worker.
It does not claim to resume the original Unity process or the frozen R3O
player directory. It demonstrates deterministic continuation, checkpoint
differential/restore parity, and the first registered target synchronization;
it does not demonstrate policy effectiveness, convergence, all five policy
seeds, held-out evaluation, ONNX export, ROCm training, or unrestricted
training.

## Registered boundaries

| Stage | Transitions / decisions | Optimizer updates | Target synchronizations | Clean-boundary rule |
|---|---:|---:|---:|---|
| Pilot | `13,996` | `1,000` | `0` | stop before a live post-boundary action |
| Synchronization | `49,996` | `10,000` | `1` | stop before a live post-boundary action |

Both stages use scenario seed `31001`, policy seed `51001`, exploration seed
`61001`, replay capacity `100000`, warmup `10000`, batch size `64`,
`gamma=0.99`, Adam learning rate `0.0001`, update interval `4`, and hard
target synchronization every `10000` optimizer updates on the pinned CPU
runtime. The synchronization stage uses exactly one sync event at optimizer
update `10000`; no update `10001` is performed.

The accepted synchronization run uses the deterministic-prefix-replay option:
it reconstructs the validated R3Q boundary in each fresh worker rather than
loading the pilot checkpoint as mutable state. The required `--pilot-result`
is validated before the synchronization workers start, so the passing pilot
result gates this package while deterministic replay keeps the synchronization
attempts independently reproducible.

## Pilot evidence

The accepted result is retained under the ignored path
`Artifacts/Experiments/r3r-long-horizon-pilot-final/result.json`.

| Field | Accepted value |
|---|---:|
| Result SHA-256 | `e6d9d920cc143dcfad36a7861c4269d07bb3711b5dabefda227ec51ae689f98c` |
| Canonical trace SHA-256 | `07a4c27fc28ef348e634dea2e55f3319dd2bb86e9bbf3af5359723204ac0f829` |
| Worker count | `2` |
| Worker checkpoint bytes / SHA-256 | `40882701` / `d15edcf8f6cea735c22cc518e26879a228ae3da9621694fbe8bfc9b6d4ac7cce` |
| Checkpoint state SHA-256 | `6a2f0695e13a521959029807ac85ac78578a2349604d7c06a6668b7f6787f9a1` |
| Worker trace bytes / SHA-256 | `13226262` / `862b0b29cf56fd0461dd5a52bcaa1ebe46e94336a5340cd56b7367b2425661b3` |
| Target synchronizations | `0` |
| Post-boundary live action | `false` |

Both fresh workers produced identical checkpoint bytes, checkpoint state, and
trace bytes; the parent result records the same canonical trace. The pilot's clean boundary is
`13,996` transitions, `1,000` optimizer updates, zero target
synchronizations, no pending agents, and no live post-boundary action.

An earlier complete pilot reproduction remains under the ignored path
`Artifacts/Experiments/r3r-long-horizon-pilot/`. It reproduced the same
canonical trace, checkpoint bytes, and checkpoint state as the accepted pilot
above, but its result wrapper has SHA-256
`0a4807cca5c2fc343aa74d1d1d5fbfddbaa085728072e50749e61450c5f9f108`.
It is retained as a non-canonical duplicate and was not used as the
synchronization prerequisite.

## First synchronization evidence

The accepted result is retained under the ignored path
`Artifacts/Experiments/r3r-long-horizon-synchronization-final/result.json`.

| Field | Accepted value |
|---|---:|
| Result SHA-256 | `644a6c3c295f3c5a5c10f1a6c6f36a034e84dfffcecc2a0c4e133fd83034c1b7` |
| Canonical trace SHA-256 | `6605bb688cf4a7c3c4b5478e5042746a0bcb17b6d698676dd98ee2cb16ce3bff` |
| Worker count | `2` |
| Worker trace bytes / SHA-256 | `54092421` / `739c43fc0ff841cd3d1885e50cfe717f36bae0ee35ee5bfd841b339422eb6189` |
| Worker checkpoint bytes / SHA-256 | `45490741` / `c58c2cb8ff1b82b832055656be027145e3792643e3dd9a2623dbef449bc2613d` |
| Checkpoint state SHA-256 | `bb7bc2a0f52f20adc6fd13f49ea3057a8e4f1af1a94be3ee4b33f29bf459da27` |
| Live worker `loaded_without_unity` | `[false, false]` |
| Fresh restorer `loaded_without_unity` | `[true, true]` |

The two fresh workers matched byte-for-byte. The common clean boundary was:

- transition and decision count `49,996`;
- optimizer update count `10,000`;
- target synchronization count `1`;
- pending agent IDs `[]`;
- last selection completed at transition `49,995`;
- no post-boundary live action selected.

The sole target synchronization occurred at decision count `49,996` and
optimizer update `10,000`. The target network before the event was the R3Q
target `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`.
The online network after the update and the target network after synchronization
both had SHA-256
`5e455aac0264f98a364ec9d296671e91539fea0522d48f438b416950983f747f`.
All earlier target hashes remained equal to the R3Q target, and no update
event exceeded optimizer update `10000`.

The final replay storage accounting was:

| Field | Value |
|---|---:|
| Capacity / size / cursor | `100000` / `49996` / `49996` |
| Frame references / unique frames | `399968` / `81` |
| Frame-payload / metadata bytes | `2286144` / `9600000` |
| Accounted bytes / remaining under 4 GiB | `12037184` / `4282930112` |
| Full-exploration / decay selections | `10001` / `39995` |
| Last selection transition count | `49995` |

After the clean live boundary, the only action selection was the registered
synthetic post-sync check. It selected legal action `[2, 1]` from all-false
masks, with completed-transition count `49996`; no live action was selected.
Each fresh Python restorer reproduced the checkpoint state, next replay sample,
and synthetic post-boundary selection. The next replay sample used batch size
`64`, with indices SHA-256
`fefe50c1eb90755b417ee067b1939acc8f95175719be4e96c8891321ab7aea0b` and the
following field fingerprints:

| Field | SHA-256 |
|---|---|
| observations | `129c4c7773fc630061aa4e1617d84dfe420f84bde54d21c56d5a085cbd2c81f5` |
| actions | `1e6418dfe467cbf9c7d743aa6f2111a1550274e6cee29695d711b77295605b71` |
| rewards | `141d5a0c24425f8de7f3b88afbb0bc8863432027461d61b3c252aa7cfc5a0b6a` |
| next observations | `0906a7fc66c23e7b8611f812295f6027ed606e54c69703d9825477a00e6d5d93` |
| action masks branch 0 / 1 | `13c3780306a30b81ecc34414048eb928b1e19d9b0dede46d09114531cc0b6b1a` / `38723a2e5e8a17aa7950dc008209944e898f69a7bd10a23c839d341e935fd5ca` |
| next masks branch 0 / 1 | `f046627f2682710d2b1a65616d80ccfee72a58acb1f2dfb0dd5b9fad9e95f427` / `38723a2e5e8a17aa7950dc008209944e898f69a7bd10a23c839d341e935fd5ca` |
| terminated / truncated | `a5e4a99b891f881b3f2138826819e4d03e90a5cfbf181468f1eef33231133126` / `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |

## Validation and limits

The contract and both result schemas were validated, the 21 focused R3R tests
and historical R3O/R3Q regression tests passed, and the full trainer suite
passed 298 cases with 100 pre-existing ML-Agents protobuf deprecation
warnings. The independent read-only contract review is recorded at task close.
The run used no changed Unity code, gameplay setting, registered research
value, or frozen R3O/R3Q artifact.

One earlier synchronization attempt was operator-stopped by the pre-review
one-hour worker timeout before producing a completed worker result. Its
ignored directory, `Artifacts/Experiments/r3r-long-horizon-synchronization/`,
contains only the partial player log and is not acceptance evidence. The
accepted synchronization result above was produced by the final stage-specific
timeout configuration.
