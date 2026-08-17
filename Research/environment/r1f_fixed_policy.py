from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
import torch
from torch import Tensor, nn


POLICY_SCHEMA_VERSION = "quickdraw.r1f-fixed-policy.v1"
POLICY_SEED = 11001
EXPECTED_GPU_NAME = "AMD Radeon RX 7900 XT"
INPUT_SIZE = 4
HIDDEN_SIZE = 32
MOVEMENT_SIZE = 3
SUBMIT_SIZE = 2


class FixedPolicyNetwork(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = nn.Linear(INPUT_SIZE, HIDDEN_SIZE)
        self.movement_head = nn.Linear(HIDDEN_SIZE, MOVEMENT_SIZE)
        self.submit_head = nn.Linear(HIDDEN_SIZE, SUBMIT_SIZE)

    def forward(self, observations: Tensor) -> Tuple[Tensor, Tensor]:
        hidden = torch.relu(self.hidden(observations))
        return self.movement_head(hidden), self.submit_head(hidden)


def parameter_specification() -> List[Dict[str, Any]]:
    return [
        {"name": "hidden.weight", "shape": [32, 4], "dtype": "float32"},
        {"name": "hidden.bias", "shape": [32], "dtype": "float32"},
        {"name": "movement_head.weight", "shape": [3, 32], "dtype": "float32"},
        {"name": "movement_head.bias", "shape": [3], "dtype": "float32"},
        {"name": "submit_head.weight", "shape": [2, 32], "dtype": "float32"},
        {"name": "submit_head.bias", "shape": [2], "dtype": "float32"},
    ]


def deterministic_state_dict(seed: int = POLICY_SEED) -> Dict[str, Tensor]:
    if not 0 <= seed <= 2_147_483_647:
        raise ValueError("Policy seed must be a signed 31-bit integer.")

    generator = np.random.Generator(np.random.PCG64(seed))

    def uniform(shape: Sequence[int], scale: float) -> Tensor:
        values = generator.uniform(-scale, scale, size=shape).astype(np.float32)
        return torch.from_numpy(values)

    state = {
        "hidden.weight": uniform((HIDDEN_SIZE, INPUT_SIZE), 0.1),
        "hidden.bias": uniform((HIDDEN_SIZE,), 0.02),
        "movement_head.weight": uniform((MOVEMENT_SIZE, HIDDEN_SIZE), 0.005),
        "movement_head.bias": torch.tensor([10.0, 0.0, 0.0], dtype=torch.float32),
        "submit_head.weight": uniform((SUBMIT_SIZE, HIDDEN_SIZE), 0.005),
        "submit_head.bias": torch.tensor([10.0, 0.0], dtype=torch.float32),
    }
    validate_state_dict(state)
    return state


def validate_state_dict(state_dict: Mapping[str, Tensor]) -> None:
    specification = parameter_specification()
    expected_names = [item["name"] for item in specification]
    if list(state_dict) != expected_names:
        raise RuntimeError(
            f"Policy parameters were {list(state_dict)}, expected {expected_names}."
        )
    for item in specification:
        tensor = state_dict[item["name"]]
        if list(tensor.shape) != item["shape"]:
            raise RuntimeError(
                f"{item['name']} shape was {list(tensor.shape)}, expected {item['shape']}."
            )
        if tensor.dtype != torch.float32:
            raise RuntimeError(f"{item['name']} must use torch.float32.")
        if not bool(torch.isfinite(tensor).all().item()):
            raise RuntimeError(f"{item['name']} contains NaN or infinity.")


def state_dict_sha256(state_dict: Mapping[str, Tensor]) -> str:
    validate_state_dict(state_dict)
    digest = hashlib.sha256()
    for item in parameter_specification():
        name = item["name"]
        tensor = state_dict[name].detach().cpu().contiguous()
        header = json.dumps(
            {"name": name, "shape": item["shape"], "dtype": item["dtype"]},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest.update(len(header).to_bytes(4, "little"))
        digest.update(header)
        digest.update(tensor.numpy().astype("<f4", copy=False).tobytes(order="C"))
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_checkpoint(path: Path, seed: int = POLICY_SEED) -> Dict[str, Any]:
    state_dict = deterministic_state_dict(seed)
    payload = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_seed": seed,
        "state_dict": state_dict,
        "state_dict_sha256": state_dict_sha256(state_dict),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return checkpoint_metadata(path, payload)


def load_checkpoint(path: Path) -> Dict[str, Any]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, dict):
        raise RuntimeError("Policy checkpoint must contain a dictionary.")
    if payload.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise RuntimeError("Policy checkpoint has the wrong schema version.")
    if payload.get("policy_seed") != POLICY_SEED:
        raise RuntimeError("Policy checkpoint has the wrong registered seed.")
    state_dict = payload.get("state_dict")
    if not isinstance(state_dict, dict):
        raise RuntimeError("Policy checkpoint is missing its state dictionary.")
    validate_state_dict(state_dict)
    actual_hash = state_dict_sha256(state_dict)
    if payload.get("state_dict_sha256") != actual_hash:
        raise RuntimeError("Policy checkpoint state hash does not match its tensors.")
    return payload


def checkpoint_metadata(path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "seed": int(payload["policy_seed"]),
        "checkpoint_sha256": sha256_file(path),
        "state_dict_sha256": str(payload["state_dict_sha256"]),
        "parameters": parameter_specification(),
    }


class FixedPolicyDriver:
    def __init__(
        self,
        checkpoint_path: Path,
        model_path: Path,
        backend: str,
        expected_gpu_name: str = EXPECTED_GPU_NAME,
    ) -> None:
        if backend not in {"cpu", "rocm"}:
            raise ValueError(f"Unsupported fixed-policy backend {backend}.")
        if not checkpoint_path.is_file():
            raise FileNotFoundError(checkpoint_path)
        if not model_path.is_file():
            raise FileNotFoundError(model_path)

        self.backend = backend
        self.checkpoint_path = checkpoint_path.resolve()
        self.model_path = model_path.resolve()
        payload = load_checkpoint(self.checkpoint_path)

        if backend == "rocm":
            if not torch.cuda.is_available():
                raise RuntimeError("ROCm backend requested but torch.cuda is unavailable.")
            if torch.version.hip is None:
                raise RuntimeError("ROCm backend requested from a non-HIP PyTorch build.")
            device_name = torch.cuda.get_device_name(0)
            if device_name != expected_gpu_name:
                raise RuntimeError(
                    f"ROCm device was {device_name!r}, expected {expected_gpu_name!r}."
                )
            self.device = torch.device("cuda:0")
            self.device_name = device_name
        else:
            self.device = torch.device("cpu")
            self.device_name = "cpu"
            torch.set_num_threads(1)

        self.network = FixedPolicyNetwork()
        self.network.load_state_dict(payload["state_dict"], strict=True)
        self.network.to(self.device)
        self.network.eval()
        self._checkpoint_metadata = checkpoint_metadata(self.checkpoint_path, payload)

    def act(
        self,
        observation: np.ndarray,
        action_masks: Sequence[Sequence[bool]],
    ) -> Tuple[int, int, List[List[float]]]:
        if observation.shape != (INPUT_SIZE,):
            raise RuntimeError(f"Policy observation shape was {observation.shape}.")
        if [len(branch) for branch in action_masks] != [MOVEMENT_SIZE, SUBMIT_SIZE]:
            raise RuntimeError("Policy action masks have the wrong branch sizes.")

        observation_tensor = torch.from_numpy(
            np.asarray(observation, dtype=np.float32)
        ).reshape(1, INPUT_SIZE).to(self.device)
        with torch.inference_mode():
            movement_logits, submit_logits = self.network(observation_tensor)
            movement_mask = torch.tensor(
                action_masks[0], dtype=torch.bool, device=self.device
            ).reshape(1, MOVEMENT_SIZE)
            submit_mask = torch.tensor(
                action_masks[1], dtype=torch.bool, device=self.device
            ).reshape(1, SUBMIT_SIZE)
            movement_masked = movement_logits.masked_fill(movement_mask, -torch.inf)
            submit_masked = submit_logits.masked_fill(submit_mask, -torch.inf)
            movement = int(torch.argmax(movement_masked, dim=1).item())
            submit = int(torch.argmax(submit_masked, dim=1).item())
            recorded = torch.cat((movement_logits, submit_logits), dim=1).cpu().numpy()[0]

        if not bool(np.isfinite(recorded).all()):
            raise RuntimeError("Policy produced NaN or infinite logits.")
        logits = [
            [float(value) for value in recorded[:MOVEMENT_SIZE]],
            [float(value) for value in recorded[MOVEMENT_SIZE:]],
        ]
        return movement, submit, logits

    def metadata(self) -> Dict[str, Any]:
        return {
            **self._checkpoint_metadata,
            "backend": self.backend,
            "device": str(self.device),
            "device_name": self.device_name,
            "torch_version": torch.__version__,
            "hip_version": torch.version.hip,
            "onnx_sha256": sha256_file(self.model_path),
        }
