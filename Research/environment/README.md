# R1A CPU environment, R1E ROCm compatibility, and R1F parity

This directory records the R1A CPU dependency decision, the separately
isolated R1E Python 3.11 / ROCm / ML-Agents compatibility gate, and the R1F
fixed-policy parity result. R1F accepts ROCm only for the registered
batch-size-one synchronous inference fixture. None of these slices adds
research gameplay, implements training, or makes a model-effectiveness claim.

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
- AMD RX 7900 XT Windows ROCm compatibility matrix: <https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html?fam=radeon&w=compute&gpu=rx-7900-xt&gfx=gfx1100&os=windows>
- AMD ROCm installation guide: <https://rocm.docs.amd.com/en/latest/install/rocm.html>
- AMD ROCm PyTorch guide: <https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html>

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

## ROCm support decision

R1A/R1C remain the historical CPU reference. The ROCm `7.14.0` matrix, dated
2026-07-16, explicitly lists the Radeon RX 7900 XT, its `gfx1100` architecture,
Windows 11 25H2, and Python 3.11. The superseded exploratory DirectML lane was
removed during repository cleanup so the active environment surface has one
accelerator candidate. R1C's two exactly matching 10,000-decision CPU
communicator traces and their 108.636 and 107.434 decisions/s measurements
remain the transport reference; R1E did not replace it. R1F separately accepts
ROCm for its fixed-policy inference scope after exact correctness and repeated
throughput gates.

## R1E Python 3.11 / ROCm / ML-Agents gate

The official `mlagents==1.1.0` and `mlagents-envs==1.1.0` wheels contain runtime
code that works in the tested Python 3.11 stack, but their published metadata
blocks it: `Requires-Python` ends at 3.10.12 and `grpcio` ends at 1.48.2, for
which no CPython 3.11 Windows wheel exists. Release 23 source widened `grpcio`
to 1.53.2, which does have that wheel, but identifies itself as `1.2.0.dev0`.
R1E therefore does not silently install Release 23 under the public 1.1.0 name.

Instead, `build_mlagents_py311_overlay.py` deterministically reconstructs the
two official 1.1.0 wheels with only these metadata changes:

- `Requires-Python`: `>=3.10.1,<=3.10.12` to `>=3.10.1,<3.12`;
- `grpcio`: maximum `1.48.2` to `1.53.2`;
- wheel build tag `1py311compat` and explicit QuickDraw metadata headers.

Every runtime file is checked byte-for-byte against the official wheel. The
official and reconstructed wheel hashes are frozen in
`mlagents-rocm-compatibility-contract-v1.json`. The old transitive
`PettingZoo==1.15.0` source also declares Python `<3.11`; R1E records its
official source hash and bypasses only that metadata check, without changing
its runtime source.

R1E clean-installed the stack twice in independent ignored environments. The
repository cleanup retained the primary environment for R1F and removed the
disposable reproduction environment after its result was recorded:

| Component | Validated version |
| --- | --- |
| Python | `3.11.13` |
| ROCm | `7.14.0` |
| PyTorch / HIP | `2.12.0+rocm7.14.0` / `7.14.60850` |
| torchvision / torchaudio | `0.27.0+rocm7.14.0` / `2.11.0+rocm7.14.0` |
| ML-Agents | official-runtime `1.1.0` metadata overlays |
| grpcio | `1.53.2` |

Both original constructions had identical 71-distribution inventories and
passed `pip check`, imports, `mlagents-learn --help`, exact RX 7900 XT selection,
and the fixed CPU-versus-ROCm forward/backward probe. The forward maximum absolute
difference was `4.76837158203125e-07`; input- and weight-gradient differences
were both `0.0`, below the registered `1e-5` tolerance. Two communicator runs
from each environment also passed, and all four canonical traces had SHA-256
`5c5a5190f36e320a7bf05f85543681ba8f98e04aef1e71922d277f805ccf42b5`.

The installed AMD Software `26.7.1` is newer than the matrix-validated `26.6.4`.
That is recorded as a support qualification; no driver or Windows security
setting was changed. The functional ROCm checks passed on the installed driver.

Create a Python 3.11.13 environment, then prepare it with the tracked pipeline:

```powershell
$environment = 'Artifacts\Experiments\.venvs\r1e-rocm-mlagents-py311'
$artifacts = 'Artifacts\Experiments\r1e-rocm-mlagents\environment-1'
micromamba create -y -p $environment -c conda-forge python=3.11.13

$python = Join-Path $environment 'python.exe'
& $python Research/environment/prepare_rocm_mlagents_py311.py `
  --python $python --artifact-directory $artifacts
```

Run `Research/smoke/run_smoke.py` twice with
`--accelerator-candidate rocm`, then validate those two run directories:

```powershell
& $python Research/environment/probe_rocm_mlagents_compatibility.py `
  --run-id r1e-rocm-mlagents-compatibility `
  --output 'Artifacts/Experiments/r1e-rocm-mlagents/raw-result.json' `
  --communicator-run 'Artifacts/Experiments/r1e-rocm-mlagents/communicator-run-1' `
  --communicator-run 'Artifacts/Experiments/r1e-rocm-mlagents/communicator-run-2'
```

The schema-validated R1E result is `conditional_go`, with
`backend_acceptance=not_accepted`, `cpu_reference_retained=true`, and
`full_parity_executed=false`. It proves that the ML-Agents 1.1 communicator and
ROCm tensor path can coexist on Python 3.11. It does not prove training,
checkpoint/export parity, end-to-end policy parity, or a throughput advantage.
Those claims are evaluated separately by R1F.

## R1F fixed-policy parity result

`backend-parity-contract-v1.json` registers a real 1,000-decision warmup
episode followed in the same Unity/Python process by a separately timed
10,000-decision episode. `r1f_fixed_policy.py` creates one deterministic
float32 4→32 ReLU MLP with two discrete heads from policy seed `11001`.
`prepare_r1f_policy.py` saves that checkpoint once and exports it once to ONNX.
CPU and ROCm independently reload the same checkpoint, apply the same masks and
argmax rule, and retain every logit and transition for the aggregate evaluator.
The Unity scenario seed remains the registered R1C value `21001`; the runner
rejects accidental substitution of the policy seed for the scenario seed.

The accepted alternating order was CPU-1, ROCm-1, CPU-2, ROCm-2. Every exact
trace/action/mask/outcome/return check passed, both repeat-logit comparisons
were exact, and the CPU-versus-ROCm and ONNX-versus-CPU maximum absolute errors
were both `9.5367431640625e-07`, below `1e-5`. Throughput was:

| Backend | Runs (decisions/s) | Median |
| --- | --- | --- |
| CPU | `81.321`, `105.108` | `93.2145` |
| ROCm | `96.430`, `100.213` | `98.3215` |

The ROCm/CPU median ratio is `1.0547876135150647`; therefore the frozen
all-or-nothing rule accepts ROCm for this fixture. The curated result is
`amd-backend-parity-result-v1.json`, validated by
`backend-parity-result.schema.json`. Raw traces, manifests, checkpoint, ONNX
file, environments, and diagnostic runs remain ignored below
`Artifacts/Experiments/r1f-backend-parity/`.

The CPU runner uses a separate Python 3.11.13 venv with the R1E support stack,
`torch==2.12.0+cpu`, and `onnxruntime==1.23.2`; the candidate environment remains
the retained `2.12.0+rocm7.14.0` environment. Both pass `pip check`. R1F does
not prove training throughput, larger-model performance, learned-policy
quality, or any `Research_Basic`/combat/LLM behavior.
