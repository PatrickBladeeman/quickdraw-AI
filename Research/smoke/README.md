# R1B communicator smoke

R1B proves the version-locked Unity/Python communication boundary without
starting either learned benchmark. The fixture is a deterministic abstract
state machine, not gameplay and not a training environment for effectiveness
claims.

## Implemented boundary

- Unity package: `com.unity.ml-agents` `4.0.0`.
- Python packages: `mlagents`/`mlagents-envs` `1.1.0` in the R1A Python 3.10.12
  CPU reference environment.
- Unity behavior: one four-float vector observation and two discrete branches
  sized `[3, 2]`.
- Episodes: one true terminal (`smoke_goal`) and one decision-limit truncation
  (`decision_limit`, `interrupted=true`).
- Custom side channel: the frozen
  `quickdraw.research-side-channel.v1` UUID and envelope contract.
- Evidence: complete observations, action masks, actions, rewards, next
  observations, terminal flags, side-channel events, and a schema-validated run
  manifest.

The tracked smoke definition is `smoke-contract-v1.json`. Generated builds,
logs, traces, and manifests remain below ignored `Artifacts/Experiments/`.

## Rebuild and test

```powershell
$unity = 'C:\Program Files\Unity\Hub\Editor\6000.0.57f1\Editor\Unity.exe'
$project = 'C:\projects\quickdraw-AI'

& $unity -batchmode -nographics -projectPath $project `
  -executeMethod QuickDraw.Editor.ResearchSmokeBuild.RebuildScene -quit `
  -logFile "$project\Logs\R1B-SceneBuild.log"

& $unity -batchmode -nographics -projectPath $project `
  -runTests -testPlatform EditMode -testFilter QuickDraw.Tests.EditMode `
  -testResults "$project\Logs\R1B-EditMode-results.xml" `
  -logFile "$project\Logs\R1B-EditMode.log"
```

Build the isolated smoke player:

```powershell
$smokePlayer = "$project\Artifacts\Experiments\r1b-smoke\build\QuickDrawResearchSmoke.exe"
& $unity -batchmode -nographics -projectPath $project `
  -executeMethod QuickDraw.Editor.ResearchSmokeBuild.BuildWindows `
  -quickdrawSmokeOutput $smokePlayer -quit `
  -logFile "$project\Logs\R1B-SmokeBuild.log"
```

Run two identical traces from the pinned Python environment:

```powershell
$python = "$project\Artifacts\Experiments\.venvs\r1a-py31012\python.exe"
$runRoot = "$project\Artifacts\Experiments\r1b-smoke"

& $python Research/smoke/run_smoke.py `
  --env $smokePlayer --output "$runRoot\run-1" `
  --run-id r1b-smoke-run-1 --seed 21001

& $python Research/smoke/run_smoke.py `
  --env $smokePlayer --output "$runRoot\run-2" `
  --run-id r1b-smoke-run-2 --seed 21001 `
  --compare-to "$runRoot\run-1\trace.json"
```

The second command fails unless the canonical trace is structurally and
numerically identical to the first. The runner also fails on a contract-hash,
behavior-shape, side-channel sequence, end-reason, manifest-schema, dependency,
or artifact-boundary mismatch.

## Deliberate exclusions

R1B does not add `Research_Basic`, visual observations, combat, a replay buffer,
a trainer, a learned model, the 10,000-step throughput gate, AMD acceleration,
or LLM integration. It provides no model-quality evidence.
