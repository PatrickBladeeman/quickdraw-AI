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
- `exploration.py` — the stateless epsilon schedule and seeded selector;
- `llapi.py` — behavior validation, pending decisions, transition completion,
  action selection, and truncation-mask side-channel ingestion;
- `checkpoint.py` — versioned, integrity-bound trainer state save and restore;
- `provenance.py` — dependency-light raw-file hashing and CPU runtime identity;
- `acceptance.py` — canonical JSON hashing, serialization, runtime checks,
  fresh process execution, deterministic comparison, and result writing;
- `trajectory_runner.py` — shared CLI dispatch and orchestration for the eight
  update/handoff entry points, preserving their existing modes;
- `trajectory_validation.py` — repeated contract/prefix and scheduled-selector
  relationships for the registered historical gates, with explicit historical
  field mappings; and
- `update_gate.py` — shared bounded Unity collection and optimizer-gate
  execution for the update-trajectory milestones;
- `run_bdq_long_horizon_smoke.py` — the contract-driven R3R continuation pilot
  and first target-synchronization gate, including fresh player copies,
  checkpoint differential checks, and Unity-free restore checks.

The `run_bdq_*` files preserve historical commands and milestone-specific
contracts, expectations, validation, and summaries. Generic behavior used by
multiple milestones belongs in `quickdraw_bdq`, not in a milestone runner.
Future milestones must state a genuinely new acceptance or research claim and
extend a shared execution mechanism through contract/configuration data. A new
bespoke runner/test/schema stack is appropriate only when that claim requires a
substantially different contract or execution boundary; a new label, cutoff,
or expected value alone is not enough.

The shared trajectory validators are deliberately specialized to these
registered milestones. `UPDATE_PREFIX_FIELDS` explicitly names the first four
historical update fields, and the scheduled-optimization and continuation
checks enforce the registered pre-target-synchronization and no-post-update
action boundaries. These checks preserve the existing acceptance gates; they do
not make the package an unrestricted training runner. A future update or open-
ended training path needs its own contract mapping, boundary rules, and tests.

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

Shared orchestration tests live in `test_bdq_trajectory_runner.py`; parameterized
R3K/R3M/R3O relationship cases live in `test_bdq_scheduled_updates.py`.
`bdq_test_support.py` provides small synthetic fixtures with independent
accepted update values. Unit cases that stub the generic validator test only
milestone relationships. Real composed validation requires a full accepted
trace and its unchanged schema; it does not establish live collection parity.
Historical per-milestone test paths retain registration and distinct research
claims. R3P/R3Q keep their separate checkpoint protocols and tests.

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

## Isolated historical player copies

Any command that launches a standalone historical player must use a fresh copy
of the complete player directory. Copy the executable, its `*_Data` directory,
`UnityPlayer.dll`, and every other sibling file before starting a runner. The
ML-Agents timer writer places `ML-Agents/Timers/<scene>_timers.json` beneath the
player data directory, so pointing `--env` at a historical build directory can
rewrite a frozen profiling log even when the runner's output directory is new.

The following copies both player directories into ignored, fresh locations and
then uses only those copies for standalone runs. Choose new destination names
for every reproduction; the command deliberately refuses an existing target.

```powershell
$isolatedPlayers = 'Artifacts\Experiments\isolated-players'
New-Item -ItemType Directory -LiteralPath $isolatedPlayers -Force | Out-Null

$playerSources = @{
  R3M = 'Artifacts\Experiments\r3m-fourth-update\build'
  R3O = 'Artifacts\Experiments\r3o-fifth-update\build'
}
foreach ($name in $playerSources.Keys) {
  $destination = Join-Path $isolatedPlayers $name
  if (Test-Path -LiteralPath $destination) {
    throw "Choose a fresh isolated player directory: $destination"
  }
  New-Item -ItemType Directory -LiteralPath $destination | Out-Null
  Copy-Item -Path (Join-Path $playerSources[$name] '*') `
    -Destination $destination -Recurse
}

$player = Join-Path $isolatedPlayers 'R3M\QuickDrawResearchBasic.exe'
$playerR3O = Join-Path $isolatedPlayers 'R3O\QuickDrawResearchBasic.exe'
```

## Milestone runners

Each acceptance runner requires a fresh `--output` directory. It starts two
fresh workers unless its contract says otherwise, validates the complete trace,
and fails closed on contract, prefix, behavior, shape, mask, schedule, hash, or
pending-decision drift. R3Q starts one Unity-backed saver and one fresh
Unity-free Python restorer, as registered by its contract.

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
| R3Q live-derived checkpoint | `run_bdq_live_checkpoint_smoke.py` | [`R3Q.md`](../../docs/evidence/R3Q.md) |
| R3R long-horizon continuation and first sync | `run_bdq_long_horizon_smoke.py` | [`R3R.md`](../../docs/evidence/R3R.md) |

Set up the isolated copies above, then select the required command:

```powershell
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
  --env $playerR3O `
  --output Artifacts\Experiments\r3o-fifth-update\acceptance

& $python Research\trainer\run_bdq_checkpoint_roundtrip_smoke.py `
  --output Artifacts\Experiments\r3p-checkpoint-roundtrip\acceptance

& $python Research\trainer\run_bdq_live_checkpoint_smoke.py `
  --env $playerR3O `
  --output Artifacts\Experiments\r3q-live-checkpoint\acceptance
```

R3R creates a fresh complete copy for each of its two workers. Run the pilot
first; the synchronization command refuses to start without its passing pilot
result:

```powershell
$r3rPilot = 'Artifacts\Experiments\r3r-long-horizon-pilot-reproduction'
$r3rSync = 'Artifacts\Experiments\r3r-long-horizon-synchronization-reproduction'

& $python Research\trainer\run_bdq_long_horizon_smoke.py `
  --stage pilot `
  --env Artifacts\Experiments\r3o-fifth-update\build\QuickDrawResearchBasic.exe `
  --output $r3rPilot

& $python Research\trainer\run_bdq_long_horizon_smoke.py `
  --stage synchronization `
  --pilot-result (Join-Path $r3rPilot 'result.json') `
  --env Artifacts\Experiments\r3o-fifth-update\build\QuickDrawResearchBasic.exe `
  --output $r3rSync
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

These runners are bounded collection/integration gates. R3R demonstrates only
its registered one-seed continuation boundaries, first target synchronization,
checkpoint differential, and deterministic Unity-free restore checks. The suite
does not demonstrate unrestricted training, convergence, learned-policy
effectiveness, held-out evaluation, checkpoint/export beyond the registered
restore checks, ROCm training, strategic combat, reflex behavior, or local-model
behavior. Current truth is maintained in
[`STATE.md`](../../STATE.md).
