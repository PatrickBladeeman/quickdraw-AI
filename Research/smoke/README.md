# R1B communicator smoke, R1C CPU reference, and R1E compatibility reuse

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

The tracked smoke definition is `smoke-contract-v1.json`. The separate
`cpu-reference-contract-v1.json` registers one 10,000-decision truncation and
its timing boundary. Generated builds, logs, traces, and manifests remain below
ignored `Artifacts/Experiments/`.

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

## Run the R1C CPU reference

Use the same player and Python environment, adding the dedicated mode:

```powershell
$runRoot = "$project\Artifacts\Experiments\r1c-cpu-reference"

& $python Research/smoke/run_smoke.py --mode cpu-reference `
  --env $smokePlayer --output "$runRoot\run-1" `
  --run-id r1c-cpu-reference-1 --seed 21001

& $python Research/smoke/run_smoke.py --mode cpu-reference `
  --env $smokePlayer --output "$runRoot\run-2" `
  --run-id r1c-cpu-reference-2 --seed 21001 `
  --compare-to "$runRoot\run-1\trace.json"
```

Timing begins immediately before the first LLAPI action submission and ends
when the 10,000th `environment.step()` returns. The measured synchronous driver
loop includes scripted action selection and in-memory transition capture.
Player startup, trace comparison, and JSON serialization are excluded. The
canonical trace also excludes timing so deterministic state evidence can be
compared exactly while each run manifest retains its own performance result.

The two accepted base-seed-`21001` runs both produced trace SHA-256
`d5080b62ea3cc6c33a18567461f690a568339d2168f9d253ea3134b7c85572c5`.
They recorded 108.636 and 107.434 decisions/s. This is CPU Unity/Python LLAPI
transport throughput, not trainer or model-inference throughput.

## R1E Python 3.11 / ROCm communicator check

R1E deliberately reuses the same standalone player and default two-episode
contract. The runner's `--accelerator-candidate rocm` option records that the
Python process belongs to the isolated ROCm candidate environment; it does not
move Unity communication onto the GPU or claim training throughput.

From each independently constructed Python 3.11.13 environment, run the default
smoke twice:

```powershell
$python = "$project\Artifacts\Experiments\.venvs\r1e-rocm-mlagents-py311\python.exe"
$runRoot = "$project\Artifacts\Experiments\r1e-rocm-mlagents"

& $python Research/smoke/run_smoke.py `
  --env $smokePlayer --output "$runRoot\communicator-run-1" `
  --run-id r1e-rocm-communicator-1 --seed 21001 `
  --accelerator-candidate rocm

& $python Research/smoke/run_smoke.py `
  --env $smokePlayer --output "$runRoot\communicator-run-2" `
  --run-id r1e-rocm-communicator-2 --seed 21001 `
  --accelerator-candidate rocm `
  --compare-to "$runRoot\communicator-run-1\trace.json"
```

The same pair was repeated from a second clean environment. All four canonical
traces had SHA-256
`5c5a5190f36e320a7bf05f85543681ba8f98e04aef1e71922d277f805ccf42b5`.
Their manifests record Python 3.11.13, ML-Agents 1.1.0, ROCm as the candidate,
and successful Unity communication. This proves the revised Python package
boundary can drive the Unity communicator; the separate R1E tensor probe proves
the GPU path.

## Deliberate exclusions

R1B/R1C/R1E do not add `Research_Basic`, visual observations, combat, a replay
buffer, a trainer, a learned model, or LLM integration. R1E verifies ROCm tensor
access but does not train through the communicator or execute full CPU-versus-
ROCm policy, checkpoint, export, or throughput parity. The 10,000-decision CPU
result remains the deterministic transport baseline and provides no model-quality
evidence.
