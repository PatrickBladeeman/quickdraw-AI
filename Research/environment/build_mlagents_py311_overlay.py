from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Dict


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
DEFAULT_CONTRACT_PATH = Path(__file__).with_name(
    "mlagents-rocm-compatibility-contract-v1.json"
)
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_digest(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
    return "sha256=" + encoded.rstrip(b"=").decode("ascii")


def require_artifact_directory(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != ARTIFACT_ROOT and ARTIFACT_ROOT not in resolved.parents:
        raise ValueError(f"Path must be below {ARTIFACT_ROOT}: {resolved}")
    return resolved


def replace_exactly_once(content: str, before: str, after: str) -> str:
    if content.count(before) != 1:
        raise RuntimeError(f"Expected one metadata line {before!r}.")
    return content.replace(before, after)


def patched_wheel_name(filename: str, build_tag: str) -> str:
    suffix = "-py3-none-any.whl"
    if not filename.endswith(suffix):
        raise ValueError(f"Unexpected pure-Python wheel filename: {filename}")
    return filename[: -len(suffix)] + f"-{build_tag}{suffix}"


def patch_wheel(
    source_path: Path,
    output_path: Path,
    overlay: Dict[str, object],
) -> None:
    with zipfile.ZipFile(source_path, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist()}

    metadata_names = [name for name in files if name.endswith(".dist-info/METADATA")]
    wheel_names = [name for name in files if name.endswith(".dist-info/WHEEL")]
    record_names = [name for name in files if name.endswith(".dist-info/RECORD")]
    if len(metadata_names) != 1 or len(wheel_names) != 1 or len(record_names) != 1:
        raise RuntimeError("Wheel must contain one METADATA, WHEEL, and RECORD file.")

    metadata_name = metadata_names[0]
    wheel_name = wheel_names[0]
    record_name = record_names[0]
    metadata = files[metadata_name].decode("utf-8")
    metadata = replace_exactly_once(
        metadata,
        f"Requires-Python: {overlay['requires_python_before']}",
        f"Requires-Python: {overlay['requires_python_after']}",
    )
    metadata = replace_exactly_once(
        metadata,
        f"Requires-Dist: {overlay['grpcio_before']}",
        f"Requires-Dist: {overlay['grpcio_after']}",
    )
    header, separator, body = metadata.partition("\n\n")
    if not separator:
        raise RuntimeError("Wheel METADATA did not contain a header boundary.")
    header += (
        "\nX-QuickDraw-Compatibility-Overlay: metadata-only"
        "\nX-QuickDraw-Runtime-Code-Changes: false"
    )
    metadata = header + separator + body
    files[metadata_name] = metadata.encode("utf-8")

    wheel_metadata = files[wheel_name].decode("utf-8")
    if "Build:" in wheel_metadata:
        raise RuntimeError("Official wheel already contains a build tag.")
    wheel_metadata = replace_exactly_once(
        wheel_metadata,
        "Root-Is-Purelib:",
        f"Build: {overlay['build_tag']}\nRoot-Is-Purelib:",
    )
    files[wheel_name] = wheel_metadata.encode("utf-8")

    rows = []
    for name in sorted(files):
        if name == record_name:
            continue
        content = files[name]
        rows.append((name, record_digest(content), str(len(content))))
    rows.append((record_name, "", ""))
    record_stream = io.StringIO(newline="")
    writer = csv.writer(record_stream, lineterminator="\n")
    writer.writerows(rows)
    files[record_name] = record_stream.getvalue().encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name], compresslevel=9)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic metadata-only ML-Agents Python 3.11 wheels."
    )
    parser.add_argument("--source-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    source_directory = require_artifact_directory(arguments.source_directory)
    output_directory = require_artifact_directory(arguments.output_directory)
    contract = json.loads(arguments.contract.read_text(encoding="utf-8"))
    overlay = contract["metadata_overlay"]

    for package in contract["official_wheels"].values():
        source_path = source_directory / package["filename"]
        if sha256_file(source_path) != package["sha256"]:
            raise RuntimeError(f"Official wheel hash mismatch: {source_path}")
        output_name = patched_wheel_name(
            package["filename"],
            overlay["build_tag"],
        )
        output_path = output_directory / output_name
        patch_wheel(source_path, output_path, overlay)
        print(f"wheel={output_path}")
        print(f"sha256={sha256_file(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
