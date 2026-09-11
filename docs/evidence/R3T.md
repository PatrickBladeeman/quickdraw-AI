# R3T: Basic BDQ five-seed training and complete lineage

Status: accepted and verified on 2026-09-10 in the pinned Windows CPU
environment. R3T is a bounded training and artifact-integrity gate. It
demonstrates finite training completion, complete ordered lineage, checkpoint
restore parity, and process/player provenance for five independent Basic runs.
It does not demonstrate policy effectiveness, convergence, generalization,
sample efficiency, held-out success, or a final policy choice.

## Contract and claim boundary

The registered decision record is
[`ADR-0013`](../decisions/ADR-0013-r3t-basic-multiseed-training.md). The
machine-readable contract is
[`bdq-r3t-basic-multiseed-contract-v1.json`](../../Research/trainer/bdq-r3t-basic-multiseed-contract-v1.json)
with SHA-256
`409a2037e74c632754c0afa5054b7b9271a7c817f7c4e575dd1a3dcc504dee30`.
Its schema is
[`bdq-r3t-basic-multiseed-contract.schema.json`](../../Research/schemas/bdq-r3t-basic-multiseed-contract.schema.json)
with SHA-256
`c41d6ae77d6f9d3425fdcec0726c4632ff0d42d5b3c7df2821f2f84511c8b7bc`, and the
result schema is
[`bdq-r3t-basic-multiseed-result.schema.json`](../../Research/schemas/bdq-r3t-basic-multiseed-result.schema.json)
with SHA-256
`c485deca33e8ecba6798117463eae5eb5a202598b61ecd251431bb2baf0386d8`.

The accepted raw campaign result is retained under the ignored path
`Artifacts/Experiments/r3t-basic-multiseed/result.json`.

| Artifact | Accepted value |
|---|---|
| Campaign result SHA-256 | `9d5154b549c22eec7cb1d8433b09036e49e20052a434eecaed78f251876ed8b2` |
| Canonical campaign SHA-256 | `ad385a1e9bbdb6c953238a94d47f6bcc7c9fdf9d419a837bb7e07291ebc4cffd` |
| Campaign manifest bytes / SHA-256 | `11257` / `8bf3d1b531ab7824c50b2ed8ce68f62345878a22aa72d869119159d1830c1832` |
| Run count / exact seed coverage | `5` / `true` |
| Fresh training / restore process count | `5` / `5` |

The source player is the accepted R3R Basic player copy, bound by manifest
SHA-256
`83cb3b701e842d26e732be7f01ba6559dbc360c8cad53e10846b970ec1c7429d`
(`187` files, `104896089` bytes) and executable SHA-256
`54e68068a5db103d572ae99f2d378c87cd2ba05bde395df7cf41e3ee42d3a55e`.
Each seed received a fresh complete copy under the R3T artifact root. The
source player directory was not written. The only registered run-owned player
mutation was the timer sidecar
`QuickDrawResearchBasic_Data/ML-Agents/Timers/Research_Basic_timers.json`,
which the Unity timer writer updates during execution; its per-run before/after
hashes are retained in each result.

## Registered execution and accepted boundary

The five explicit policy mappings were:

| Run | Policy initialization / replay sampling | Exploration | Scenario |
|---|---:|---:|---:|
| `seed-51001` | `51001` / `51001` | `61001` | `31001` |
| `seed-51002` | `51002` / `51002` | `61001` | `31001` |
| `seed-51003` | `51003` / `51003` | `61001` | `31001` |
| `seed-51004` | `51004` / `51004` | `61001` | `31001` |
| `seed-51005` | `51005` / `51005` | `61001` | `31001` |

Each run started fresh with empty replay, fresh optimizer and selector state,
and fresh online/target initialization. The common registered boundary and
telemetry were:

| Field | Accepted value |
|---|---:|
| Completed transitions / decisions | `49996` / `49996` |
| Optimizer updates | `10000` |
| Target synchronizations | `1`, at update `10000` |
| Post-boundary action | `false` |
| Pending agent IDs at stop | `[]` |
| Last selection completed transition | `49995` |
| Replay capacity / final size / cursor | `100000` / `49996` / `49996` |
| Replay frame references / unique frames | `399968` / `81` |
| Accounted replay bytes / remaining under 4 GiB | `12037184` / `4282930112` |
| Learning-curve points per run | `100`, at updates `100, 200, ..., 10000` |
| Full-exploration / decayed selections | `10001` / `39995` |

The clean stop completed transition `49996`, its update and target
synchronization, and then stopped before selecting another live action. Every
run recorded the ordered transitions and episodes, action/mask fields,
rewards, terminal/truncation flags, decision/update counters, epsilon,
replay/accounting state, target-sync history, optimizer losses and TD errors,
network hashes, sampled replay indices, finite Q-value summaries, checkpoint
state hashes, timing, return, success, and explicit denominators. The learning
curve and all registered metric fields passed finite-value and relational
validation. The recorded training success/return fields are descriptive
telemetry only and are not an effectiveness comparison.

The four checkpoints per run were saved at optimizer updates `2500`, `5000`,
`7500`, and `10000`. Selection was fixed to update `10000` before observing any
training outcome. Each selected checkpoint was restored in a fresh Python
process without Unity; all five runs reported parity for boundary, replay,
selector RNG, settings, and state hash.

## Accepted artifact hashes

Raw accepted result, serialized trace/metrics, and canonical trace/metrics
hashes are below. Raw traces and metrics remain ignored artifacts; these values
are curated so the accepted run can be audited without tracking large files.

| Run | Result SHA-256 | Canonical trace SHA-256 | Serialized trace bytes / SHA-256 |
|---|---|---|---|
| `seed-51001` | `ae86913e92c5b1232f342b50475d27b30332577139e536749f8563440bedc59e` | `9d8ac7833ff48acb925f89dec68ce3add1eef9f30deceb79456c1f1138e47bbc` | `53486676` / `d0bd75f0bdd407d7561fbb6c1cfaa1ddc71133b46f706a428507ff4a6b3deb07` |
| `seed-51002` | `651f5851fe23e2b0acb71bfa2b714e52996956e47fa253fd80a0ead6c8c022ab` | `68f03164cf520a78c45968ae2ad8b2f8865eab42e9efee894f92f2546be20e23` | `53394133` / `33fa761eca76a2c9197fbba028dcf3b14180577146b54799c20848fd5eed0802` |
| `seed-51003` | `642f9e5567c914f0758a7089b0ddc38dd58d118d94a28416a82d88ea649f0e97` | `ca2791c0d551456d4bec835828caacced782a901e0fcbdd0109e2797c6455b21` | `53433956` / `864561234263903cf07fbe891bbb22a80fa526e83f8ba333355a518dfe2908d5` |
| `seed-51004` | `c219e13f6e4ad8aaab9bb02b3060dc351eb01c774cab09a6527f587c25456920` | `d0bc0486597b1706bcab6d243b8889745426e70bec9f029586a6e6fffe68559f` | `53411319` / `01c1db1a6af80a8fdb9310425d4cbabb5bcc34c4f688e2b2d40461426d83bf51` |
| `seed-51005` | `2561bff887e3b568741010086098b939c55b87f47dd1f54a1ec059aa5339e2fc` | `bdc9972a55fce36161c8af7e8c3fcf94afebf6b91ceb93d23cea5cd5d3050580` | `53382090` / `bb83590da20e7235df9fbff30241e7a206ff08743088ab5f0973d1593446953f` |

| Run | Canonical metrics SHA-256 | Serialized metrics bytes / SHA-256 |
|---|---|---|
| `seed-51001` | `b9c0ba9d23e443d45820682320f296045c5be51a22dbc479497ddc34b9752115` | `316719` / `d4b46d6f1d5a51daea8f6dce22c0a4ee3e8b55d9dec4de32fbd4f9efee8e33fa` |
| `seed-51002` | `50433e287a7013a551f15af8c00f289ccdc840b89918113c5890356326445fd4` | `317064` / `f42e9b86648a0a556de310cfb0dd25f1f30286a2c77b49b540edeac5ff43cea5` |
| `seed-51003` | `7fa321505102b03bf44c5e01e1fd94798900085f73e238c1f5ede51b33979aba` | `316526` / `ad4a26c13fb7551698a29bbff11eb2b0b5e5e71c44c02dcf142fc976e2803dcd` |
| `seed-51004` | `34c811675d16a0ec2e4c80d6293b068dfdb8ad8bf0794c09a3dd11fdb4ad5f53` | `317011` / `1531e45397225c7c0b2e7b7ad91aca08502382b2ad0dc2a2a7e1cb120e3649d9` |
| `seed-51005` | `02a462ec6bc6e3d98318131609a4966bf817fef40b3dd75752f09f8ade05b884` | `316186` / `977dbace0e43264914c2ff7df8b1fedf9f532fc0c2b08ff10cc098c392bc8658` |

The selected checkpoint records were:

| Run | Bytes | Serialized checkpoint SHA-256 | Checkpoint state SHA-256 |
|---|---:|---|---|
| `seed-51001` | `45490741` | `c58c2cb8ff1b82b832055656be027145e3792643e3dd9a2623dbef449bc2613d` | `bb7bc2a0f52f20adc6fd13f49ea3057a8e4f1af1a94be3ee4b33f29bf459da27` |
| `seed-51002` | `45490738` | `7efb8cef4b06c947d96ff930aa36d827ef4968d6604289525e80cb6fbf467ce4` | `156903fb87228787c38e5fd320930b4d00cede4cc90767a4e862f639e86e7544` |
| `seed-51003` | `45490737` | `297aeaaf64cd9e5d8a424a8e81f6eec72d41bd78db52d10b6bd027b6f254d1c2` | `9d7bb04fd6d28f0fcee85552badf2627bb3e4227d3f2d8d2456ab5cfc3c72f21` |
| `seed-51004` | `45490732` | `b8eb0b860457eba6f0409af03d21111a4d5ea99018e466ff01c746ea7afd55fd` | `25a491374e4cf1aa8bff94a7d70bb70345ccdd9f56a5bfd7e05b020647fa7ba9` |
| `seed-51005` | `45490734` | `a05f366b647b997a89dfb19faf6746c083012b2e6ad9beef1f8b6a3023370b7f` | `765abb4805fc071675a21352b8e350e832f470ca7584e7fa4585e53bd898ce13` |

## Rejected attempts and verification

Two earlier attempts are retained under the ignored artifact tree and are not
acceptance evidence:

| Retained artifact | Result | Reason |
|---|---|---|
| `Artifacts/Experiments/r3t-basic-multiseed-rejected-attempt-1/` | Rejected before Unity training | Initial repository/artifact-root path handling failed for seed `51001`; the partial player/log/result were retained. |
| `Artifacts/Experiments/r3t-basic-multiseed-rejected-attempt-2/` | Rejected after the exact training boundary | The Unity timer sidecar mutation had not yet been registered in the R3T player-mutation contract; the completed partial lineage was retained. |

The final campaign used the corrected contract, which explicitly registers
that run-owned timer sidecar. No training horizon, checkpoint choice, seed,
metric, or acceptance threshold was changed in response to a training outcome.
The superseded pre-canonicalization result wrapper is retained beside the
accepted result as
`Artifacts/Experiments/r3t-basic-multiseed/result-pre-canonicalization-fix.json`
(raw SHA-256
`ffa7d2b3344c6e0ba8bae55f405d61f8d19cff9bfca03024abc6bc655d6ed521`). It is
not acceptance input; the accepted result’s wrapper metadata was mechanically
rebound after excluding serialized trace/metrics timing descriptors from
campaign canonicalization, without changing transitions, checkpoints, or
selection data.

The pinned command was:

```powershell
& Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe -B `
  Research\trainer\run_bdq_r3t_multiseed.py `
  --env Artifacts\Experiments\r3r-long-horizon-synchronization-final\player-copies\run-1\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3t-basic-multiseed
```

The contract and result schemas were validated before collection. The current
result schema also validates the accepted artifacts after tightening the
registered truncation-event upper bound from `167` to the feasible maximum
`166`. After collection, the runner’s current validators were rerun over all
five raw traces, metrics,
checkpoints, result wrappers, provenance records, and the campaign result; all
five passed. The focused R3T/acceptance suite passed `58` tests, the focused
R3O/R3Q/R3R/R3S regression set passed `64` tests, and the complete trainer
suite passed `364` tests with the repository’s `100` pre-existing ML-Agents
protobuf deprecation warnings. The final read-only contract review found no
blocking issue. Existing R3O/R3Q/R3R/R3S artifacts were not modified.

This record demonstrates finite training and artifact lineage only. In
particular, the recorded training success/return telemetry must not be cited as
success-rate improvement or policy effectiveness. No held-out learned-policy
evaluation, convergence claim, generalization claim, sample-efficiency claim,
joint-action comparison, Unity-process resume, ONNX boundary, or ViZDoom
numeric replication is included.
