# Research Python and backend environment runbook

This directory owns reproducible environment construction and the fixed-policy
CPU/ROCm compatibility/parity tooling.

- Exact accepted R1A/R1E/R1F results and qualifications:
  [`DETERMINISTIC-R0-R2.md`](../../docs/evidence/DETERMINISTIC-R0-R2.md)
- Current runtime summary: [`STATE.md`](../../STATE.md)
- Stable Unity/package reference:
  [`UNITY_AND_REPOSITORY.md`](../../docs/reference/UNITY_AND_REPOSITORY.md)

Environment results do not establish training throughput, learned-policy
quality, or general accelerator support. Generated environments and raw runs
stay below ignored `Artifacts/Experiments/`.

## CPU reference decision

The historical Windows CPU reference uses the exact pins in
`requirements-lock.txt`, including Python `3.10.12`, ML-Agents/ML-Agents Envs
`1.1.0`, NumPy `1.23.5`, and the registered CPU PyTorch line. The lock, not this
summary, is the dependency source of truth.

Unity package `com.unity.ml-agents` `4.0.0` corresponds to the Release 23
Python `1.1.0` line. Published PyPI metadata limits Python to 3.10.12 and
`grpcio` to 1.48.2; this historical environment intentionally preserves those
published constraints.

Create and validate the environment without changing system Python:

```powershell
$environment = 'Artifacts/Experiments/.venvs/r1a-py31012'
micromamba create -y -p $environment -c conda-forge python=3.10.12

$python = Join-Path $environment 'python.exe'
& $python -m pip install 'pip==25.2' 'setuptools==80.9.0' 'wheel==0.45.1'
& $python -m pip install -r 'Research/environment/requirements-lock.txt'
& $python -m pip check
& $python -c "import mlagents, mlagents_envs, torch, numpy, matplotlib, pytest, jsonschema"
& (Join-Path $environment 'Scripts/mlagents-learn.exe') --help
```

Do not reuse this Windows x86-64 CPU lock for another operating system or
accelerator.

## Python 3.11 ML-Agents overlay

The current Python 3.11 lane does not relabel Release 23 development source as
the public `1.1.0` packages. `build_mlagents_py311_overlay.py` reconstructs the
two official `1.1.0` wheels while preserving every runtime file and changing
only registered compatibility metadata:

- Python range to `>=3.10.1,<3.12`;
- `grpcio` ceiling to `1.53.2`; and
- an explicit `1py311compat` build tag and QuickDraw provenance headers.

The script verifies source/runtime bytes and hashes against
`mlagents-rocm-compatibility-contract-v1.json`. The tracked preparation path
also handles the old PettingZoo Python metadata without modifying its runtime
source.

## ROCm compatibility environment

The registered candidate lane targets Python `3.11.13`, ROCm `7.14.0`, the
pinned PyTorch ROCm build, the official-runtime ML-Agents overlays, and the
exact support lock. Current compatibility and accepted-scope statements belong
in the evidence record, not in this runbook.

Create and prepare the isolated environment:

```powershell
$environment = 'Artifacts/Experiments/.venvs/r1e-rocm-mlagents-py311'
$artifacts = 'Artifacts/Experiments/r1e-rocm-mlagents/environment-1'
micromamba create -y -p $environment -c conda-forge python=3.11.13

$python = Join-Path $environment 'python.exe'
& $python Research/environment/prepare_rocm_mlagents_py311.py `
  --python $python --artifact-directory $artifacts
```

Drive two communicator runs from that environment using the commands in
[`Research/smoke/README.md`](../smoke/README.md), then validate them:

```powershell
& $python Research/environment/probe_rocm_mlagents_compatibility.py `
  --run-id r1e-rocm-mlagents-compatibility `
  --output Artifacts/Experiments/r1e-rocm-mlagents/raw-result.json `
  --communicator-run Artifacts/Experiments/r1e-rocm-mlagents/communicator-run-1 `
  --communicator-run Artifacts/Experiments/r1e-rocm-mlagents/communicator-run-2
```

The probe validates package inventory, imports, ML-Agents entry point, selected
device, CPU/ROCm tensor behavior, communicator traces, schemas, contracts, and
artifact boundaries. A clean-repeat requirement cannot be satisfied by copying
one environment or reusing one run directory.

## R1F fixed-policy parity

R1F uses one deterministic fixed-policy checkpoint and ONNX export for all
CPU/ROCm runs. `prepare_r1f_policy.py` creates the registered policy artifacts;
`r1f_fixed_policy.py` is the shared policy implementation; and
`evaluate_r1f_parity.py` validates the alternating CPU/ROCm run set against
`backend-parity-contract-v1.json` and its schema.

The CPU parity environment is a separate Python 3.11 environment using
`requirements-r1f-parity-lock.txt`; the ROCm candidate uses the retained
support environment. Both must pass `pip check` and load the same checkpoint.

The transport/inference runner and required mode arguments are documented in
[`Research/smoke/README.md`](../smoke/README.md). Accepted throughput and error
values are intentionally recorded only in
[`DETERMINISTIC-R0-R2.md`](../../docs/evidence/DETERMINISTIC-R0-R2.md) and the
tracked curated result `amd-backend-parity-result-v1.json`.

## Focused tests

Run environment-contract tests from a compatible Python environment:

```powershell
& $python -B -m pytest -p no:cacheprovider `
  Research/environment/test_rocm_mlagents_compatibility.py `
  Research/environment/test_r1f_backend_parity.py
```

Do not regenerate tracked result JSON as a side effect of an ordinary test.

## Primary external references

- [Unity 6000.0 ML-Agents package status](https://docs.unity3d.com/6000.0/Manual/com.unity.ml-agents.html)
- [ML-Agents releases and documentation](https://github.com/Unity-Technologies/ml-agents#releases--documentation)
- [Release 23](https://github.com/Unity-Technologies/ml-agents/releases/tag/release_23_tag)
- [ML-Agents installation guide](https://unity-technologies.github.io/ml-agents/Installation/)
- [AMD Radeon ROCm compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html?fam=radeon&w=compute&gpu=rx-7900-xt&gfx=gfx1100&os=windows)
- [AMD ROCm installation](https://rocm.docs.amd.com/en/latest/install/rocm.html)
- [AMD ROCm PyTorch guide](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html)

Compatibility pages and package metadata are mutable external facts; verify
them before changing a dependency or support claim.
