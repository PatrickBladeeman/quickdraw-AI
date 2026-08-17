from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
CONTRACT_PATH = Path(__file__).with_name(
    "mlagents-rocm-compatibility-contract-v1.json"
)
SUPPORT_LOCK_PATH = Path(__file__).with_name(
    "requirements-rocm-py311-support-lock.txt"
)
OVERLAY_BUILDER_PATH = Path(__file__).with_name(
    "build_mlagents_py311_overlay.py"
)
AMD_INDEX = "https://repo.amd.com/rocm/whl-multi-arch/"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_artifact_directory(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != ARTIFACT_ROOT and ARTIFACT_ROOT not in resolved.parents:
        raise ValueError(f"Path must be below {ARTIFACT_ROOT}: {resolved}")
    return resolved


def run(arguments: List[str]) -> None:
    subprocess.run(arguments, cwd=REPO_ROOT, check=True)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the ignored R1E ROCm and ML-Agents Python environment."
    )
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--artifact-directory", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    python = arguments.python.resolve()
    artifact_directory = require_artifact_directory(
        arguments.artifact_directory
    )
    if not python.is_file():
        raise FileNotFoundError(python)

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    target = contract["target"]
    version_check = subprocess.run(
        [str(python), "-c", "import platform; print(platform.python_version())"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if version_check != target["python_version"]:
        raise RuntimeError(
            f"Python was {version_check}, expected {target['python_version']}."
        )

    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "pip==25.2",
            "setuptools==80.9.0",
            "wheel==0.45.1",
        ]
    )
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--index-url",
            AMD_INDEX,
            "rocm[libraries,device-gfx1100]==7.14.0",
        ]
    )
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--index-url",
            AMD_INDEX,
            "torch[device-gfx1100]==2.12.0+rocm7.14.0",
            "torchvision[device-gfx1100]==0.27.0+rocm7.14.0",
            "torchaudio==2.11.0+rocm7.14.0",
        ]
    )

    source_directory = artifact_directory / "official-wheels"
    overlay_directory = artifact_directory / "overlay-wheels"
    source_directory.mkdir(parents=True, exist_ok=True)
    overlay_directory.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(python),
            "-m",
            "pip",
            "download",
            "--no-deps",
            "--ignore-requires-python",
            "--dest",
            str(source_directory),
            "mlagents==1.1.0",
            "mlagents-envs==1.1.0",
        ]
    )
    run(
        [
            str(python),
            str(OVERLAY_BUILDER_PATH),
            "--source-directory",
            str(source_directory),
            "--output-directory",
            str(overlay_directory),
        ]
    )

    expected_overlay = contract["metadata_overlay"]["overlay_wheels"]
    overlay_paths = []
    for filename, expected_hash in expected_overlay.items():
        path = overlay_directory / filename
        if sha256_file(path) != expected_hash:
            raise RuntimeError(f"Compatibility wheel hash mismatch: {path}")
        overlay_paths.append(str(path))
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            *sorted(overlay_paths),
        ]
    )

    exception = contract["transitive_metadata_exception"]
    exception_directory = artifact_directory / "transitive-source"
    exception_directory.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(python),
            "-m",
            "pip",
            "download",
            "--no-deps",
            "--no-binary",
            ":all:",
            "--ignore-requires-python",
            "--dest",
            str(exception_directory),
            f"{exception['package']}=={exception['version']}",
        ]
    )
    exception_path = exception_directory / exception["source_filename"]
    if sha256_file(exception_path) != exception["source_sha256"]:
        raise RuntimeError(f"Transitive source hash mismatch: {exception_path}")
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--ignore-requires-python",
            str(exception_path),
        ]
    )
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--requirement",
            str(SUPPORT_LOCK_PATH),
        ]
    )
    run([str(python), "-m", "pip", "check"])

    freeze = subprocess.run(
        [str(python), "-m", "pip", "freeze"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    freeze_path = artifact_directory / "environment-freeze.txt"
    freeze_path.write_text(freeze, encoding="utf-8")
    print(f"python={platform.python_version()}")
    print(f"freeze={freeze_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
