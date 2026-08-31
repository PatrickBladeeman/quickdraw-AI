# BDQ trainer and LLAPI runbook

This directory contains QuickDraw's reusable Branching Double DQN core,
synchronous ML-Agents low-level-API boundary, versioned milestone contracts,
bounded runners, validators, and focused tests.

- Architecture and module ownership: [`ARCH.md`](../../ARCH.md)
- Registered network/training values: [`RESEARCH.md`](../../RESEARCH.md)
- Current implementation boundary: [`STATE.md`](../../STATE.md)
- Exact R3 results, hashes, failures, and limitations:
  [`docs/evidence`](../../docs/evidence/README.md)

This file owns operating commands. It does not duplicate accepted result
records. All output paths below are generated and ignored.

## Package map

`quickdraw_bdq` contains:

- `action_space.py` — branch/joint mapping and strict mask-aware selection;
- `network.py` — the visual dueling branching network;
- `targets.py` — per-branch Double-DQN targets and Huber loss;
- `replay.py` — immutable transitions, exact frame interning, columnar ring
  storage, seeded sampling, reclamation, and fail-closed accounting;
- `optimizer.py` — online/target networks, Adam, update and target-sync
  counters;
- `exploration.py` — the stateless epsilon schedule and seeded selector; and
- `llapi.py` — behavior validation, pending decisions, transition completion,
  action selection, and truncation-mask side-channel ingestion.

The former high-level ML-Agents trainer, policy, trajectory, settings, YAML,
plugin registration, and next-mask registry were superseded and removed.
`pyproject.toml` intentionally registers no `mlagents.trainer_type` entry point.

For each agent, LLAPI collection stores `(observation, action, current masks)`
when an action is sent and completes one transition only after Unity supplies
the next `DecisionStep` or `TerminalStep`. Ordinary continuation gets its next
mask from `DecisionSteps`; a true terminal uses a non-bootstrapped sentinel;
truncation uses Unity's authoritative final-state side-channel mask.

## Python environment and tests

Use the isolated Python 3.11 CPU environment established by the research
environment runbook:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe'
& $python -B -m pip install --no-deps -e Research\trainer
& $python -B -m pytest -p no:cacheprovider Research\trainer
```

The package expects the pinned versions recorded in `pyproject.toml` and the
environment contracts. Do not upgrade them as part of running a gate.

## Build the current Basic player

The camera observation requires normal graphics. The player may run while
unfocused, but runners must not add headless or batch-mode player arguments.

With the installed Unity CLI:

```powershell
$unity = "$env:LOCALAPPDATA\Unity\bin\unity.exe"
& $unity --non-interactive build . `
  --target StandaloneWindows64 `
  --execute-method QuickDraw.Editor.ResearchBasicBuild.BuildWindows `
  --args '-quickdrawBasicOutput Artifacts/Experiments/r3m-fourth-update/build/QuickDrawResearchBasic.exe' `
  --log-file Artifacts/Experiments/r3m-fourth-update/build.log `
  --allow-dirty-build --no-tail
```

Legacy Unity Editor batch mode may also invoke the same
`QuickDraw.Editor.ResearchBasicBuild.BuildWindows` method. Build logs may
contain sensitive command-line context; retain only necessary excerpts.

## Milestone runners

Each acceptance runner requires a fresh `--output` directory. It starts two
fresh workers unless its contract says otherwise, validates the complete trace,
and fails closed on contract, prefix, behavior, shape, mask, schedule, hash, or
pending-decision drift.

| Gate | Runner | Canonical evidence |
| --- | --- | --- |
| R3D direct collection | `run_bdq_llapi_smoke.py` | [`R3D.md`](../../docs/evidence/R3D.md) |
| R3E fixed epsilon collection | `run_bdq_epsilon_collection_smoke.py` | [`R3E.md`](../../docs/evidence/R3E.md) |
| R3F warmup/update 1 | `run_bdq_warmup_update_smoke.py` | [`R3F.md`](../../docs/evidence/R3F.md) |
| R3G update 2 | `run_bdq_two_update_smoke.py` | [`R3G.md`](../../docs/evidence/R3G.md) |
| R3H greedy handoff | `run_bdq_post_update_handoff_smoke.py` | [`R3H.md`](../../docs/evidence/R3H.md) |
| R3I schedule unit gate | `test_bdq_epsilon_schedule.py` | [`R3I.md`](../../docs/evidence/R3I.md) |
| R3J scheduled handoff | `run_bdq_scheduled_epsilon_handoff_smoke.py` | [`R3J.md`](../../docs/evidence/R3J.md) |
| R3K update 3 | `run_bdq_third_update_smoke.py` | [`R3K.md`](../../docs/evidence/R3K.md) |
| R3L diagnostic greedy handoff | `run_bdq_third_update_greedy_handoff_smoke.py` | [`R3L.md`](../../docs/evidence/R3L.md) |
| R3M update 4 | `run_bdq_fourth_update_smoke.py` | [`R3M.md`](../../docs/evidence/R3M.md) |
| R3N replay regression | `validate_bdq_replay_storage_regression.py` | [`R3N.md`](../../docs/evidence/R3N.md) |
| R3O update 5 | `run_bdq_fifth_update_smoke.py` | [`R3O.md`](../../docs/evidence/R3O.md) |
| R3P checkpoint round-trip | `run_bdq_checkpoint_roundtrip_smoke.py` | [`R3P.md`](../../docs/evidence/R3P.md) |

Set the player once, then select the required command:

```powershell
$player = 'Artifacts\Experiments\r3m-fourth-update\build\QuickDrawResearchBasic.exe'

& $python Research\trainer\run_bdq_llapi_smoke.py `
  --env $player --output Artifacts\Experiments\r3d-llapi\acceptance

& $python Research\trainer\run_bdq_epsilon_collection_smoke.py `
  --env $player --output Artifacts\Experiments\r3e-epsilon-collection\acceptance

& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --env $player --output Artifacts\Experiments\r3f-warmup-update\acceptance

& $python Research\trainer\run_bdq_two_update_smoke.py `
  --env $player --output Artifacts\Experiments\r3g-two-update\acceptance

& $python Research\trainer\run_bdq_post_update_handoff_smoke.py `
  --env $player --output Artifacts\Experiments\r3h-post-update-handoff\acceptance

& $python Research\trainer\run_bdq_scheduled_epsilon_handoff_smoke.py `
  --env $player --output Artifacts\Experiments\r3j-scheduled-epsilon-handoff\acceptance

& $python Research\trainer\run_bdq_third_update_smoke.py `
  --env $player --output Artifacts\Experiments\r3k-third-update\acceptance

& $python Research\trainer\run_bdq_third_update_greedy_handoff_smoke.py `
  --env $player --output Artifacts\Experiments\r3l-third-update-greedy-handoff\acceptance

& $python Research\trainer\run_bdq_fourth_update_smoke.py `
  --env $player --output Artifacts\Experiments\r3m-fourth-update\acceptance

& $python Research\trainer\run_bdq_fifth_update_smoke.py `
  --env Artifacts\Experiments\r3o-fifth-update\build\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3o-fifth-update\acceptance

& $python Research\trainer\run_bdq_checkpoint_roundtrip_smoke.py `
  --output Artifacts\Experiments\r3p-checkpoint-roundtrip\acceptance
```

R3I is a Python-only unit gate:

```powershell
& $python -B -m pytest -p no:cacheprovider `
  Research\trainer\test_bdq_epsilon_schedule.py
```

Do not interpret a later gate as authorization to regenerate an earlier
accepted result. Consult its evidence record before reproduction.

## Watch mode

Watch mode is a one-worker diagnostic path. It writes one validated trace but
cannot create the two-fresh-process acceptance result.

To watch in the Unity Editor, open `Research_Basic`, leave Play Mode off, run:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --watch `
  --output Artifacts\Experiments\r3f-warmup-update\editor-watch
```

When Python reports that it is listening on port `5004`, enter Play Mode. The
runner forces time scale `1` and prints progress every 100 transitions by
default; use `--progress-interval N` to change that interval. Stop Play Mode
after the runner finishes.

To launch a visible standalone player instead:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --watch --env $player `
  --output Artifacts\Experiments\r3f-warmup-update\standalone-watch
```

Every rerun needs a new output directory or the previous diagnostic directory
must be deliberately handled under a separately authorized cleanup task.

## Completed-trace recovery comparison

R3L, R3M, and R3O can compare two already completed worker traces when valid
workers finished under separate parent attempts. This mode still validates full
contracts and requires distinct files, object equality, and raw-byte equality.
Failed or partial traces cannot count.

```powershell
& $python Research\trainer\run_bdq_third_update_greedy_handoff_smoke.py `
  --output Artifacts\Experiments\r3l-third-update-greedy-handoff\accepted-pair `
  --first-trace <first-complete-trace.json> `
  --second-trace <second-complete-trace.json>

& $python Research\trainer\run_bdq_fourth_update_smoke.py `
  --output Artifacts\Experiments\r3m-fourth-update\accepted-pair `
  --first-trace <first-complete-trace.json> `
  --second-trace <second-complete-trace.json>

& $python Research\trainer\run_bdq_fifth_update_smoke.py `
  --output Artifacts\Experiments\r3o-fifth-update\accepted-pair `
  --first-trace <first-complete-trace.json> `
  --second-trace <second-complete-trace.json>
```

## R3N replay validation

Run the focused storage tests, then validate a fresh post-R3N R3M trace against
the frozen pre-R3N contract:

```powershell
& $python -B -m pytest -p no:cacheprovider `
  Research\trainer\test_bdq_replay_storage.py

& $python -B Research\trainer\validate_bdq_replay_storage_regression.py `
  --trace Artifacts\Experiments\r3n-replay-storage\live-regression\run-1\r3m-fourth-update-trace.json
```

The validator owns bit-exact legacy-oracle, sample-index, accounting, and
frozen-trace checks. Exact accepted values and the first invalid `-nographics`
Unity invocation are preserved in [`R3N.md`](../../docs/evidence/R3N.md).

## Claim boundary

These runners are bounded collection/integration gates. They do not demonstrate
extended training, target synchronization, checkpoint/export, learned-policy
evaluation, ROCm training, strategic combat, reflex behavior, local-model
behavior, or policy effectiveness. Current truth is maintained in
[`STATE.md`](../../STATE.md).
