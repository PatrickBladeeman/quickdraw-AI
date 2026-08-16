# R1A environment preflight

This directory records the dependency decision for the first research
infrastructure slice. R1A is configuration and contract work only: it does not
install a Unity package, add a research scene, implement a trainer, or make a
model-effectiveness claim.

## Compatibility decision

The CPU reference stack is:

| Component | Pin | Decision basis |
| --- | --- | --- |
| Unity Editor | `6000.0.57f1` (`b7b9860b7bbd`) | Current tracked project version |
| Unity ML-Agents package | `com.unity.ml-agents` `4.0.0` | Release 23 and the Unity 6000.0 package manual |
| Python | `3.10.12`, x86-64 | ML-Agents supported range is `>=3.10.1, <=3.10.12`; Unity recommends 3.10.12 |
| `mlagents` | `1.1.0` from PyPI | Release 23 maps Python `1.1.0` to Unity package `4.0.0` |
| `mlagents-envs` | `1.1.0` from PyPI | Must match `mlagents` |
| PyTorch | `2.2.1+cpu` | ML-Agents requires `>=2.1.1`; Unity's Windows guidance uses the 2.2.1 line, and PyTorch publishes a CPU wheel |
| NumPy | `1.23.5` | Exact lower bound of ML-Agents' required `>=1.23.5,<1.24.0` range |
| Matplotlib | `3.7.5` | Pinned plotting dependency validated on Python 3.10.12 |
| pytest | `8.3.5` | Pinned test dependency validated on Python 3.10.12 |
| jsonschema | `4.23.0` | Pinned manifest-validation dependency validated on Python 3.10.12 |
| pip / setuptools / wheel | `25.2` / `80.9.0` / `0.45.1` | Reproduced bootstrap; ML-Agents 1.1.0 still imports `pkg_resources`, so setuptools must remain below 81 |

Primary sources:

- Unity 6000.0 package status: <https://docs.unity3d.com/6000.0/Manual/com.unity.ml-agents.html>
- ML-Agents release table: <https://github.com/Unity-Technologies/ml-agents#releases--documentation>
- Release 23 notes and tag: <https://github.com/Unity-Technologies/ml-agents/releases/tag/release_23_tag>
- Official installation guide: <https://unity-technologies.github.io/ml-agents/Installation/>
- `mlagents` 1.1.0 metadata: <https://pypi.org/pypi/mlagents/1.1.0/json>
- `mlagents-envs` 1.1.0 metadata: <https://pypi.org/pypi/mlagents-envs/1.1.0/json>
- PyTorch 2.2.1 CPU command: <https://pytorch.org/get-started/previous-versions/#v221>
- ML-Agents `pkg_resources` import: <https://github.com/Unity-Technologies/ml-agents/blob/release_23/ml-agents/mlagents/torch_utils/torch.py>
- DirectML package metadata: <https://pypi.org/pypi/torch-directml/json>

The PyPI `mlagents==1.1.0` metadata constrains `grpcio` to `<=1.48.2`.
Release 23 source widened that bound to `<=1.53.2` without publishing a new
Python package version. This lock deliberately uses the published PyPI wheels
and therefore retains `grpcio==1.48.2`. Switching to packages built from the
Release 23 source tag is a separate versioned decision.

## Windows CPU environment

Use a conda-compatible manager so the exact Python patch release can be
created without changing the system Python. The generated environment stays
under the ignored experiment root.

```powershell
$envPath = 'Artifacts/Experiments/.venvs/r1a-py31012'
micromamba create -y -p $envPath -c conda-forge python=3.10.12

$python = Join-Path $envPath 'python.exe'
& $python -m pip install 'pip==25.2' 'setuptools==80.9.0' 'wheel==0.45.1'
& $python -m pip install -r 'Research/environment/requirements-lock.txt'
& $python -m pip check
& $python -c "import mlagents, mlagents_envs, torch, numpy, matplotlib, pytest, jsonschema"
& (Join-Path $envPath 'Scripts/mlagents-learn.exe') --help
```

The lock is for the Windows x86-64 CPU reference. Do not silently reuse it for
another operating system or accelerator.

## Recorded R1A validation

Validated on 2026-08-12 using:

- Windows 11 Home `10.0.26200`;
- AMD Ryzen 5 9600X;
- Python `3.10.12` from conda-forge;
- micromamba `2.9.0`;
- the complete `requirements-lock.txt`;
- `pip check` with no broken requirements;
- successful imports of ML-Agents, PyTorch, NumPy, Matplotlib, pytest,
  jsonschema, and ONNX;
- a successful `mlagents-learn --help` entry-point smoke check.

The Unity package and Unity/Python communicator were intentionally not
installed or exercised in R1A.

## R1B continuation

R1B subsequently installed and locked `com.unity.ml-agents==4.0.0` and used
this exact Python reference environment to drive two identical fixed-seed
standalone communicator traces. See `Research/smoke/README.md` for the isolated
fixture, commands, evidence, and deliberate exclusions. R1B did not install a
trainer plugin or test an accelerated backend.

## Accelerator decision

CPU remains the reference backend. PyTorch 2.2.1 publishes ROCm wheels for
Linux, not native Windows. The current `torch-directml` preview package pins
`torch==2.4.1`, which conflicts with this verified `torch==2.2.1+cpu` lock.
DirectML is therefore not part of this environment and no AMD acceleration
claim is made. A later backend task must use an isolated lock and pass the
registered trace, return, checkpoint, export, tolerance, and throughput gates
before it can replace CPU.
