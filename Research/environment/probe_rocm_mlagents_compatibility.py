from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import metadata, version
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
ENVIRONMENT_ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ENVIRONMENT_ROOT / "mlagents-rocm-compatibility-contract-v1.json"
SUPPORT_LOCK_PATH = (
    ENVIRONMENT_ROOT / "requirements-rocm-py311-support-lock.txt"
)
BUILDER_PATH = ENVIRONMENT_ROOT / "build_mlagents_py311_overlay.py"
PREPARER_PATH = ENVIRONMENT_ROOT / "prepare_rocm_mlagents_py311.py"
PROBE_PATH = Path(__file__).resolve()
RESULT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "rocm-mlagents-compatibility.schema.json"
)
MANIFEST_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "run-manifest.schema.json"
)
SMOKE_RUNNER_PATH = REPO_ROOT / "Research" / "smoke" / "run_smoke.py"
CPU_LOCK_PATH = ENVIRONMENT_ROOT / "requirements-lock.txt"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(arguments: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def windows_identity() -> Dict[str, Any]:
    if sys.platform != "win32":
        raise RuntimeError("The registered R1E probe requires native Windows.")
    command = (
        "$os=Get-CimInstance Win32_OperatingSystem;"
        "$cv=Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion';"
        "$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1;"
        "$gpus=@(Get-CimInstance Win32_VideoController | ForEach-Object {"
        "[pscustomobject]@{name=$_.Name;driver_version=$_.DriverVersion}});"
        "$amd=Get-ItemProperty "
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' "
        "-ErrorAction SilentlyContinue | "
        "Where-Object {$_.DisplayName -eq 'AMD Software'} "
        "| Select-Object -First 1;"
        "[pscustomobject]@{os=[pscustomobject]@{name=$os.Caption;"
        "version=$os.Version;build=$os.BuildNumber;display_version=$cv.DisplayVersion};"
        "cpu=$cpu.Name.Trim();memory_bytes=[int64]$os.TotalVisibleMemorySize*1024;"
        "gpus=$gpus;amd_software=$amd.DisplayVersion} | "
        "ConvertTo-Json -Compress -Depth 5"
    )
    result = run_command(["powershell", "-NoProfile", "-Command", command])
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def import_checks(module_names: List[str]) -> Dict[str, bool]:
    checks: Dict[str, bool] = {}
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
            checks[module_name] = True
        except Exception:
            checks[module_name] = False
    return checks


def execute_tensor_probe(contract: Dict[str, Any]) -> Dict[str, Any]:
    import torch
    from mlagents.torch_utils import default_device
    from mlagents.torch_utils.torch import set_torch_config
    from mlagents.trainers.settings import TorchSettings

    target_name = contract["target"]["gpu_name_exact"]
    devices = [
        torch.cuda.get_device_name(index)
        for index in range(torch.cuda.device_count())
    ]
    matches = [
        index for index, name in enumerate(devices) if name == target_name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one ROCm device named {target_name!r}, found {devices}."
        )
    index = matches[0]
    device = torch.device(f"cuda:{index}")
    set_torch_config(TorchSettings(device=str(device)))
    if default_device() != device:
        raise RuntimeError("ML-Agents did not retain the selected ROCm device.")

    cpu = torch.device("cpu")
    x_cpu = (
        torch.arange(1, 13, dtype=torch.float32, device=cpu)
        .reshape(3, 4)
        / 7.0
    )
    weight_cpu = (
        torch.arange(1, 21, dtype=torch.float32, device=cpu)
        .reshape(4, 5)
        / 11.0
    )
    bias_cpu = torch.tensor(
        [-0.2, 0.1, 0.3, -0.4, 0.5],
        dtype=torch.float32,
        device=cpu,
    )
    x_cpu.requires_grad_(True)
    weight_cpu.requires_grad_(True)
    expected = torch.relu(x_cpu @ weight_cpu + bias_cpu)
    expected.sum().backward()

    x_candidate = x_cpu.detach().to(device).requires_grad_(True)
    weight_candidate = weight_cpu.detach().to(device).requires_grad_(True)
    actual = torch.relu(
        x_candidate @ weight_candidate + bias_cpu.to(device)
    )
    actual.sum().backward()
    torch.cuda.synchronize(device)

    forward_max_abs = float(
        (actual.detach().cpu() - expected.detach()).abs().max()
    )
    input_gradient_max_abs = float(
        (x_candidate.grad.detach().cpu() - x_cpu.grad).abs().max()
    )
    weight_gradient_max_abs = float(
        (weight_candidate.grad.detach().cpu() - weight_cpu.grad).abs().max()
    )
    finite = bool(
        torch.isfinite(actual).all()
        and torch.isfinite(x_candidate.grad).all()
        and torch.isfinite(weight_candidate.grad).all()
    )
    tolerance = float(
        contract["tensor_probe"]["forward_max_abs_tolerance"]
    )
    tolerances_passed = bool(
        finite
        and max(
            forward_max_abs,
            input_gradient_max_abs,
            weight_gradient_max_abs,
        )
        <= tolerance
    )
    return {
        "available": bool(torch.cuda.is_available()),
        "hip_version": str(torch.version.hip),
        "devices": devices,
        "selected_device": {
            "index": index,
            "name": devices[index],
            "torch_device": str(device),
            "mlagents_default_device": str(default_device()),
        },
        "forward_max_abs": forward_max_abs,
        "input_gradient_max_abs": input_gradient_max_abs,
        "weight_gradient_max_abs": weight_gradient_max_abs,
        "finite": finite,
        "tolerances_passed": tolerances_passed,
    }


def validate_communicator_runs(run_directories: List[Path]) -> Dict[str, Any]:
    if len(run_directories) != 2:
        raise ValueError("Exactly two communicator run directories are required.")
    manifest_schema = json.loads(
        MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(manifest_schema)
    validator = Draft202012Validator(
        manifest_schema,
        format_checker=FormatChecker(),
    )
    trace_hashes = []
    for directory in run_directories:
        resolved = directory.resolve()
        if ARTIFACT_ROOT not in resolved.parents:
            raise ValueError(f"Run must be below {ARTIFACT_ROOT}: {resolved}")
        trace_path = resolved / "trace.json"
        manifest_path = resolved / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validator.validate(manifest)
        python = manifest["software"]["python"]
        if python["version"] != "3.11.13":
            raise RuntimeError("Communicator manifest used the wrong Python.")
        if python["packages"]["mlagents"] != "1.1.0":
            raise RuntimeError("Communicator manifest used the wrong ML-Agents.")
        if manifest["backend"]["accelerator_candidate"] != "rocm":
            raise RuntimeError("Communicator manifest did not register ROCm.")
        if not manifest["validation"]["unity_communication"]:
            raise RuntimeError("Communicator validation was not successful.")
        trace_hashes.append(sha256_file(trace_path))
    if len(set(trace_hashes)) != 1:
        raise RuntimeError("Communicator traces were not identical.")
    return {
        "run_count": len(run_directories),
        "trace_sha256": trace_hashes[0],
        "traces_identical": True,
        "manifests_valid": True,
        "unity_communication": True,
    }


def create_result(
    run_id: str,
    contract: Dict[str, Any],
    run_directories: List[Path],
) -> Dict[str, Any]:
    errors: List[str] = []
    pip_check = run_command([sys.executable, "-m", "pip", "check"])
    if pip_check.returncode != 0:
        errors.append((pip_check.stdout + pip_check.stderr).strip())
    imports = import_checks(
        ["mlagents", "mlagents_envs", "torch", "torchvision", "torchaudio"]
    )
    if not all(imports.values()):
        errors.append("One or more required imports failed.")

    cli_path = Path(sys.executable).parent / "Scripts" / "mlagents-learn.exe"
    cli = run_command([str(cli_path), "--help"])
    if cli.returncode != 0:
        errors.append("mlagents-learn --help failed.")

    tensor = execute_tensor_probe(contract)
    if not tensor["tolerances_passed"]:
        errors.append("ROCm tensor tolerances failed.")
    communicator = validate_communicator_runs(run_directories)

    package_names = [
        "mlagents",
        "mlagents-envs",
        "PettingZoo",
        "grpcio",
        "numpy",
        "rocm",
        "torch",
        "torchvision",
        "torchaudio",
    ]
    packages = {name: version(name) for name in package_names}
    overlay_valid = bool(
        metadata("mlagents").get("X-QuickDraw-Compatibility-Overlay")
        == "metadata-only"
        and metadata("mlagents-envs").get(
            "X-QuickDraw-Compatibility-Overlay"
        )
        == "metadata-only"
    )
    if not overlay_valid:
        errors.append("ML-Agents compatibility overlay metadata was absent.")

    git_commit = run_command(["git", "rev-parse", "HEAD"])
    git_status = run_command(["git", "status", "--porcelain"])
    conditional_go = bool(
        not errors
        and pip_check.returncode == 0
        and all(imports.values())
        and cli.returncode == 0
        and tensor["available"]
        and tensor["tolerances_passed"]
        and communicator["traces_identical"]
        and overlay_valid
    )
    return {
        "schema_version": "quickdraw.r1e-rocm-mlagents-compatibility-result.v1",
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "repository": {
            "commit": git_commit.stdout.strip(),
            "dirty": bool(git_status.stdout.strip()),
        },
        "inputs": {
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "support_lock_sha256": sha256_file(SUPPORT_LOCK_PATH),
            "builder_sha256": sha256_file(BUILDER_PATH),
            "preparer_sha256": sha256_file(PREPARER_PATH),
            "probe_sha256": sha256_file(PROBE_PATH),
            "result_schema_sha256": sha256_file(RESULT_SCHEMA_PATH),
            "manifest_schema_sha256": sha256_file(MANIFEST_SCHEMA_PATH),
            "smoke_runner_sha256": sha256_file(SMOKE_RUNNER_PATH),
            "cpu_lock_sha256": sha256_file(CPU_LOCK_PATH),
        },
        "system": windows_identity(),
        "software": {
            "python_version": platform.python_version(),
            "packages": packages,
            "overlay_valid": overlay_valid,
            "pip_check": pip_check.returncode == 0,
            "imports": imports,
            "mlagents_cli": cli.returncode == 0,
        },
        "rocm": tensor,
        "communicator": communicator,
        "errors": errors,
        "decision": {
            "status": "conditional_go" if conditional_go else "no_go",
            "backend_acceptance": "not_accepted",
            "cpu_reference_retained": True,
            "full_parity_executed": False,
        },
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe the R1E Python 3.11, ROCm, and ML-Agents boundary."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--communicator-run",
        required=True,
        action="append",
        type=Path,
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    output_path = arguments.output.resolve()
    if ARTIFACT_ROOT not in output_path.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result = create_result(
        arguments.run_id,
        contract,
        arguments.communicator_run,
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"result={output_path}")
    print(f"decision={result['decision']['status']}")
    print(f"device={result['rocm']['selected_device']}")
    print(f"trace_sha256={result['communicator']['trace_sha256']}")
    return 0 if result["decision"]["status"] == "conditional_go" else 2


if __name__ == "__main__":
    raise SystemExit(main())
