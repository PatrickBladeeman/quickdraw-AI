# Communicator, CPU-reference, and parity runbook

`Research_Smoke` is a deterministic abstract ML-Agents transport and lifecycle
fixture. It is not gameplay and is not a policy-training or effectiveness
environment.

- Component architecture: [`ARCH.md`](../../ARCH.md)
- Registered cross-cutting design: [`RESEARCH.md`](../../RESEARCH.md)
- Exact R1B/R1C/R1E/R1F results and limitations:
  [`DETERMINISTIC-R0-R2.md`](../../docs/evidence/DETERMINISTIC-R0-R2.md)
- Environment construction: [`Research/environment/README.md`](../environment/README.md)

This file owns operating commands. Raw builds, traces, manifests, and logs stay
under ignored `Artifacts/Experiments/`.

## Implemented boundary

The fixture contains one four-float vector observation, discrete branches
`[3,2]`, deterministic legal masks/rewards, one true terminal, one
decision-limit truncation, and a strict ordered custom side channel.
`smoke-contract-v1.json` owns the default run; `cpu-reference-contract-v1.json`
owns the 10,000-decision timing mode.

`run_smoke.py` validates behavior shape, observations, masks, actions, rewards,
episode ends, side-channel schema/hash/run/sequence identity, run manifests,
and ignored-artifact boundaries. `--compare-to` performs structural and numeric
canonical-trace comparison.

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

Build the isolated player:

```powershell
$smokePlayer = "$project\Artifacts\Experiments\r1b-smoke\build\QuickDrawResearchSmoke.exe"
& $unity -batchmode -nographics -projectPath $project `
  -executeMethod QuickDraw.Editor.ResearchSmokeBuild.BuildWindows `
  -quickdrawSmokeOutput $smokePlayer -quit `
  -logFile "$project\Logs\R1B-SmokeBuild.log"
```

## Default communicator smoke

Run from the historical pinned CPU environment:

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

Use fresh output directories. The comparison fails on contract, shape,
sequence, outcome, manifest, dependency, artifact, or canonical-trace drift.

## CPU transport reference

The dedicated mode runs one decision-limit episode and times only the
synchronous LLAPI action/step loop, including scripted selection and in-memory
transition capture. Startup, trace comparison, and JSON serialization are
outside the timing window.

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

This mode measures Unity/Python communicator transport, not trainer throughput,
network inference throughput, sample efficiency, or policy quality.

## Python 3.11 / ROCm communicator check

R1E reuses the default communicator contract. The candidate marker records the
environment under test; it does not move Unity transport onto the GPU.

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

Repeatability across independently constructed environments is validated by
the environment probe, not by this runner alone.

## Fixed-policy backend parity mode

`--mode backend-parity` runs the registered warmup followed by one separately
timed fixed-policy episode. It requires:

- `--policy-checkpoint`;
- `--policy-model`;
- `--policy-backend cpu|rocm`; and
- the registered scenario seed, distinct from the policy seed.

The timed section includes synchronous backend inference, legal mask/argmax
selection, in-memory transition/logit capture, and LLAPI stepping. Process
startup, warmup, serialization, and aggregate comparison are excluded.

The aggregate evaluator in `Research/environment/evaluate_r1f_parity.py`
compares the frozen CPU reference, all registered CPU/ROCm traces,
PyTorch logits/actions, CPU ONNX Runtime output, checkpoint lineage, and the
frozen throughput decision. Exact accepted values belong in the evidence record
and `amd-backend-parity-result-v1.json`.

## Deliberate exclusions

These modes do not implement `Research_Basic`, visual learning observations,
replay, training, combat, a strategic reflex, or an LLM. Fixed-policy parity is
limited to its registered batch-size-one inference fixture and does not establish
training support or learned-model quality.
