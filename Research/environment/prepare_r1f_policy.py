from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict

import onnx
import torch

from r1f_fixed_policy import (
    POLICY_SEED,
    FixedPolicyDriver,
    FixedPolicyNetwork,
    create_checkpoint,
    load_checkpoint,
    parameter_specification,
    sha256_file,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the single registered R1F checkpoint and ONNX export."
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        type=Path,
        help="Ignored R1F fixture artifact directory.",
    )
    return parser.parse_args()


def export_onnx(checkpoint_path: Path, output_path: Path) -> None:
    payload = load_checkpoint(checkpoint_path)
    network = FixedPolicyNetwork()
    network.load_state_dict(payload["state_dict"], strict=True)
    network.eval()
    example = torch.zeros((1, 4), dtype=torch.float32)
    torch.onnx.export(
        network,
        example,
        output_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["observations"],
        output_names=["movement_logits", "submit_logits"],
        dynamic_axes={
            "observations": {0: "batch"},
            "movement_logits": {0: "batch"},
            "submit_logits": {0: "batch"},
        },
        dynamo=False,
    )
    model = onnx.load(output_path)
    onnx.checker.check_model(model)


def main() -> int:
    arguments = parse_arguments()
    output_directory = arguments.output_directory.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    output_directory.mkdir(parents=True, exist_ok=True)

    checkpoint_path = output_directory / "fixed-policy.pt"
    onnx_path = output_directory / "fixed-policy.onnx"
    metadata_path = output_directory / "policy-fixture.json"
    if checkpoint_path.exists() or onnx_path.exists() or metadata_path.exists():
        raise FileExistsError(
            "R1F fixture output already exists; use a new artifact directory."
        )

    checkpoint = create_checkpoint(checkpoint_path, POLICY_SEED)
    export_onnx(checkpoint_path, onnx_path)
    driver = FixedPolicyDriver(checkpoint_path, onnx_path, "cpu")
    reloaded = driver.metadata()
    if checkpoint["state_dict_sha256"] != reloaded["state_dict_sha256"]:
        raise RuntimeError("Independent CPU reload changed the state dictionary.")

    metadata: Dict[str, Any] = {
        "schema_version": "quickdraw.r1f-policy-fixture.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy_seed": POLICY_SEED,
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "state_dict_sha256": checkpoint["state_dict_sha256"],
        "onnx_sha256": sha256_file(onnx_path),
        "parameters": parameter_specification(),
        "export": {
            "opset": 17,
            "input": {"name": "observations", "dtype": "float32", "shape": ["batch", 4]},
            "outputs": [
                {"name": "movement_logits", "dtype": "float32", "shape": ["batch", 3]},
                {"name": "submit_logits", "dtype": "float32", "shape": ["batch", 2]},
            ],
        },
        "software": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "onnx": version("onnx"),
        },
        "training_performed": False,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"checkpoint={checkpoint_path}")
    print(f"onnx={onnx_path}")
    print(f"metadata={metadata_path}")
    print(f"state_dict_sha256={metadata['state_dict_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
