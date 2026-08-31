# Evidence archive

This directory is the tracked, curated record of completed validation work.
It answers **what was demonstrated, against which frozen contract, with which
exact evidence, and what was not demonstrated**. It is not the current-state
authority, task queue, architecture specification, or research registration.

Raw traces, players, logs, checkpoints, environments, and generated result
files remain under the ignored `Artifacts/Experiments/` tree. The files here
record the minimum hashes and summaries needed to audit that ignored evidence
without committing large generated artifacts.

## Evidence vocabulary

- **Contract SHA-256** hashes the tracked contract file's exact bytes.
- **Canonical trace SHA-256** hashes the schema-defined normalized trace
  object. It intentionally excludes fields such as timing when the runner's
  contract says those fields are non-deterministic.
- **Serialized trace SHA-256** hashes the raw accepted JSON trace bytes.
- **Accepted-result SHA-256** hashes the generated result wrapper that binds
  the accepted workers and canonical trace.
- **Prefix or transition SHA-256** hashes only the named trace subset. It is
  not interchangeable with a complete canonical-trace hash.
- **Curated ignored-artifact hash** was recomputed from an accepted generated
  file under the ignored artifact root during the 2026-08-29 documentation
  migration. The raw artifact is not tracked and the hash is not presented as
  a Git-contained result.

Failed, timed-out, operator-stopped, rejected, diagnostic, and invalidly
invoked runs never count as acceptance evidence. Their records are retained
where they materially qualify a result. A bounded smoke or deterministic
replay is not a benchmark, extended training run, or policy-effectiveness
study unless its milestone file explicitly says otherwise.

## Evidence index

| Scope | Record | Current evidentiary meaning |
|---|---|---|
| Tasks 1-8 and R0-R2 | [DETERMINISTIC-R0-R2.md](DETERMINISTIC-R0-R2.md) | Deterministic Unity substrate, communicator, CPU reference, ROCm compatibility/parity, and Basic environment |
| R3A-R3C | [R3A-R3C.md](R3A-R3C.md) | Pure-Python BDQ foundation, synthetic optimizer, and superseded high-level trajectory experiment |
| R3D | [R3D.md](R3D.md) | Direct LLAPI terminal/truncation replay collection |
| R3E | [R3E.md](R3E.md) | Fixed seeded epsilon-1 collection below warmup |
| R3F | [R3F.md](R3F.md) | Production warmup and optimizer update 1 |
| R3G | [R3G.md](R3G.md) | Optimizer update 2 |
| R3H | [R3H.md](R3H.md) | Live greedy handoff after update 2 |
| R3I | [R3I.md](R3I.md) | Stateless production epsilon schedule unit gate |
| R3J | [R3J.md](R3J.md) | Continuous scheduled selector live handoff |
| R3K | [R3K.md](R3K.md) | Optimizer update 3 |
| R3L | [R3L.md](R3L.md) | Diagnostic greedy handoff after update 3 |
| R3M | [R3M.md](R3M.md) | Optimizer update 4 and rejected operational attempts |
| R3N | [R3N.md](R3N.md) | Lossless memory-bounded replay and frozen R3M regression |
| R3O | [R3O.md](R3O.md) | Bounded scheduled optimizer update 5 |
| R3P | [R3P.md](R3P.md) | Deterministic Python checkpoint round-trip |

## Shared R3D-R3P runtime and optimizer reference

The individual R3D-R3N contracts pin Python `3.11.13`,
`mlagents_envs==1.1.0`, NumPy `1.23.5`, PyTorch `2.12.0+cpu`, device `cpu`,
and `quickdraw-bdq-trainer==0.3.0` with no current
`mlagents.trainer_type` entry point. The Unity behavior is
`QuickDrawResearchBasic`, with one agent, float32 HWC `[84,84,4]`
observations, discrete branches `[3,2]`, and no privileged scene inference.

Where collection uses the production seeded stream, the seeds are scenario
`31001`, policy `51001`, and exploration `61001`. The registered optimizer
defaults are replay capacity `100000`, replay warmup `10000` completed
transitions, batch size `64`, `gamma=0.99`, Adam learning rate `0.0001`, one
update every `4` decisions, and hard target synchronization every `10000`
optimizer updates. Accepted deterministic live gates use one PyTorch intra-op
thread, one inter-op thread, and deterministic algorithms.

The initial online and frozen target network SHA-256 is:

`b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`

Through R3O, the accepted live boundary contains exactly five optimizer
updates and zero target synchronizations. R3P demonstrates deterministic
Python-only checkpoint save/restore on the registered synthetic workload
without Unity; it does not resume the frozen Unity trajectory. Update 6, an
extended epsilon-decay rollout, resume of the frozen Unity trajectory,
inference export, ROCm training, held-out learned-policy evaluation,
strategic combat, the research evade reflex, and the local LLM runtime are not
demonstrated by this archive.
