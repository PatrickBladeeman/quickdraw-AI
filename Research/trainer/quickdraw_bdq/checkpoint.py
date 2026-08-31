"""Versioned fail-closed checkpoint persistence for the Python BDQ trainer."""

from __future__ import annotations

import base64
import binascii
import dataclasses
import hashlib
import json
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .exploration import LinearEpsilonSchedule
from .llapi import (
    DirectReplayCollector,
    LLAPIContractError,
    ScheduledEpsilonGreedyBDQActionSelector,
    network_sha256,
)
from .optimizer import BDQOptimizationSettings, BDQOptimizerController


CHECKPOINT_SCHEMA_VERSION = "quickdraw.bdq-checkpoint.v1"
PACKAGE_DISTRIBUTION = "quickdraw-bdq-trainer"

TRAINER_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_SCHEMA_PATH = (
    RESEARCH_ROOT / "schemas" / "bdq-checkpoint.schema.json"
)
CHECKPOINT_CONTRACT_PATH = (
    TRAINER_ROOT / "bdq-checkpoint-contract-v1.json"
)

_TORCH_DTYPE_TO_NUMPY = {
    "torch.float32": np.dtype(np.float32),
    "torch.float64": np.dtype(np.float64),
    "torch.int64": np.dtype(np.int64),
    "torch.int32": np.dtype(np.int32),
    "torch.uint8": np.dtype(np.uint8),
    "torch.bool": np.dtype(np.bool_),
}
_NUMPY_DTYPES = {
    "float32": np.dtype(np.float32),
    "float64": np.dtype(np.float64),
    "int64": np.dtype(np.int64),
    "int32": np.dtype(np.int32),
    "uint64": np.dtype(np.uint64),
    "uint8": np.dtype(np.uint8),
    "bool": np.dtype(np.bool_),
}


@dataclass(frozen=True)
class LoadedCheckpoint:
    """Fresh controller, selector, and collector restored from a checkpoint."""

    controller: BDQOptimizerController
    selector: ScheduledEpsilonGreedyBDQActionSelector
    collector: DirectReplayCollector
    verification: Dict[str, Any]


def _active_package_version() -> str:
    try:
        return version(PACKAGE_DISTRIBUTION)
    except PackageNotFoundError as error:
        raise LLAPIContractError(
            f"The {PACKAGE_DISTRIBUTION} distribution is not installed."
        ) from error


def _runtime_contract() -> Dict[str, str]:
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }


def _encode_bytes_payload(data: bytes, length: int) -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise LLAPIContractError("Byte payload is not bytes.")
    if len(data) != length:
        raise LLAPIContractError("Byte payload length is wrong.")
    return base64.b64encode(bytes(data)).decode("ascii")


def _encode_state(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        array = value.detach().cpu().contiguous().numpy()
        return {
            "kind": "tensor",
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "data": _encode_bytes_payload(
                array.tobytes(order="C"), array.nbytes
            ),
        }
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        return {
            "kind": "ndarray",
            "dtype": array.dtype.name,
            "shape": list(array.shape),
            "data": _encode_bytes_payload(
                array.tobytes(order="C"), array.nbytes
            ),
        }
    if isinstance(value, (bytes, bytearray)):
        return {
            "kind": "bytes",
            "length": len(value),
            "data": _encode_bytes_payload(value, len(value)),
        }
    if isinstance(value, np.generic):
        return _encode_state(value.item())
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [_encode_state(item) for item in value]}
    if isinstance(value, list):
        return [_encode_state(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _encode_state(dataclasses.asdict(value))
    if isinstance(value, dict):
        if value and all(type(key) is int for key in value):
            return {
                "kind": "int_keyed_mapping",
                "entries": [
                    [key, _encode_state(item)]
                    for key, item in sorted(value.items())
                ],
            }
        if all(isinstance(key, str) for key in value):
            return {key: _encode_state(item) for key, item in value.items()}
        raise LLAPIContractError("Mapping keys are not serializable.")
    if isinstance(value, (bool, int, str, float)) or value is None:
        return value
    raise LLAPIContractError(
        f"Checkpoint state contains an unsupported type: {type(value).__name__}."
    )


def _decode_state(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_state(item) for item in value]
    if not isinstance(value, dict):
        return value
    kind = value.get("kind")
    if kind is None:
        return {key: _decode_state(item) for key, item in value.items()}
    try:
        if kind == "tensor":
            dtype = _TORCH_DTYPE_TO_NUMPY[value["dtype"]]
            decoded = base64.b64decode(value["data"], validate=True)
            array = (
                np.frombuffer(decoded, dtype=dtype)
                .copy()
                .reshape([int(dim) for dim in value["shape"]])
            )
            return torch.from_numpy(array)
        if kind == "ndarray":
            dtype = _NUMPY_DTYPES[value["dtype"]]
            decoded = base64.b64decode(value["data"], validate=True)
            return (
                np.frombuffer(decoded, dtype=dtype)
                .copy()
                .reshape([int(dim) for dim in value["shape"]])
            )
        if kind == "bytes":
            decoded = base64.b64decode(value["data"], validate=True)
            if len(decoded) != value["length"]:
                raise LLAPIContractError("Bytes payload length is wrong.")
            return decoded
        if kind == "tuple":
            return tuple(_decode_state(item) for item in value["items"])
        if kind == "int_keyed_mapping":
            return {
                int(key): _decode_state(item) for key, item in value["entries"]
            }
    except (KeyError, binascii.Error, ValueError, TypeError) as error:
        if isinstance(error, LLAPIContractError):
            raise
        raise LLAPIContractError(
            f"Checkpoint state entry is malformed: {error}."
        ) from error
    raise LLAPIContractError(f"Unknown checkpoint payload kind: {kind}.")


def _canonical_state_sha256(encoded_state: Any) -> str:
    canonical = json.dumps(
        encoded_state,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def boundary_summary(
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    collector: DirectReplayCollector,
) -> Dict[str, Any]:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "controller_seed": controller.seed,
        "exploration_seed": selector.seed,
        "decision_count": controller.decision_count,
        "optimizer_update_count": controller.optimizer_update_count,
        "target_sync_count": controller.target_sync_count,
        "online_network_sha256": network_sha256(controller.online_network),
        "target_network_sha256": network_sha256(controller.target_network),
        "replay": {
            **controller.replay.storage_metrics.as_dict(),
            "cursor": controller.replay.cursor,
        },
        "pending_agent_ids": list(collector.pending_agent_ids),
    }


def _checkpoint_schema() -> Dict[str, Any]:
    schema = json.loads(CHECKPOINT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _validate_checkpoint_schema(checkpoint: Dict[str, Any]) -> None:
    try:
        Draft202012Validator(_checkpoint_schema()).validate(checkpoint)
    except ValidationError as error:
        raise LLAPIContractError(
            f"Checkpoint schema validation failed: {error.message}."
        ) from error


def save_controller_checkpoint(
    checkpoint_path: Path,
    controller: BDQOptimizerController,
    collector: DirectReplayCollector,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
) -> Dict[str, Any]:
    """Persist one clean-boundary trainer state and return its summary.

    Saving is refused while any LLAPI decision is pending. The written file is
    schema-validated and carries a SHA-256 over its canonical encoded state.
    """

    pending = collector.pending_agent_ids
    if pending:
        raise LLAPIContractError(
            "Checkpoint boundary must be clean; pending decisions remain: "
            f"{list(pending)}."
        )
    summary = boundary_summary(controller, selector, collector)
    state = {
        "controller": controller.export_checkpoint_state(),
        "selector": selector.export_checkpoint_state(),
        "replay": controller.replay.export_checkpoint_state(),
        "verification": summary,
    }
    encoded_state = _encode_state(state)
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "contract_sha256": _sha256_file(CHECKPOINT_CONTRACT_PATH),
        "identity": {
            "package": {
                "distribution": PACKAGE_DISTRIBUTION,
                "version": _active_package_version(),
            },
            "runtime": _runtime_contract(),
            "settings": dataclasses.asdict(controller.settings),
            "seeds": {
                "controller_seed": controller.seed,
                "exploration_seed": selector.seed,
            },
        },
        "state": encoded_state,
        "state_sha256": _canonical_state_sha256(encoded_state),
    }
    _validate_checkpoint_schema(checkpoint)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def load_controller_checkpoint(
    checkpoint_path: Path,
    *,
    settings: BDQOptimizationSettings,
    controller_seed: int,
    exploration_seed: int,
    schedule: LinearEpsilonSchedule,
) -> LoadedCheckpoint:
    """Restore a checkpoint into fresh objects in this process without Unity.

    Malformed, schema-incomplete, corrupted, and incompatible checkpoints are
    rejected before any restored object is returned. Partial restoration is
    confined to internal scratch objects that are discarded on failure.
    """

    try:
        checkpoint = json.loads(
            checkpoint_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LLAPIContractError(
            f"Checkpoint {checkpoint_path} is not readable JSON: {error}."
        ) from error
    if not isinstance(checkpoint, dict):
        raise LLAPIContractError("Checkpoint root must be an object.")
    _validate_checkpoint_schema(checkpoint)

    if checkpoint["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise LLAPIContractError("Checkpoint schema version is incompatible.")
    if checkpoint["contract_sha256"] != _sha256_file(CHECKPOINT_CONTRACT_PATH):
        raise LLAPIContractError("Checkpoint contract binding has drifted.")
    identity = checkpoint["identity"]
    if identity["package"] != {
        "distribution": PACKAGE_DISTRIBUTION,
        "version": _active_package_version(),
    }:
        raise LLAPIContractError("Checkpoint package identity is incompatible.")
    if identity["runtime"] != _runtime_contract():
        raise LLAPIContractError("Checkpoint runtime is incompatible.")
    if identity["settings"] != dataclasses.asdict(settings):
        raise LLAPIContractError("Checkpoint settings are incompatible.")
    seeds = identity["seeds"]
    if (
        type(seeds["controller_seed"]) is not int
        or type(seeds["exploration_seed"]) is not int
        or seeds
        != {
            "controller_seed": controller_seed,
            "exploration_seed": exploration_seed,
        }
    ):
        raise LLAPIContractError("Checkpoint seeds are incompatible.")
    if checkpoint["state_sha256"] != _canonical_state_sha256(
        checkpoint["state"]
    ):
        raise LLAPIContractError("Checkpoint state hash mismatch.")

    state = _decode_state(checkpoint["state"])
    if not isinstance(state, dict) or set(state) != {
        "controller",
        "selector",
        "replay",
        "verification",
    }:
        raise LLAPIContractError("Checkpoint state sections are incomplete.")

    try:
        controller = BDQOptimizerController(controller_seed, settings)
        controller.load_checkpoint_state(state["controller"])
        controller.replay.import_checkpoint_state(state["replay"])
        selector = ScheduledEpsilonGreedyBDQActionSelector(
            controller.online_network,
            schedule=schedule,
            seed=exploration_seed,
        )
        selector.load_checkpoint_state(state["selector"])
    except LLAPIContractError:
        raise
    except (ValueError, TypeError, RuntimeError, KeyError) as error:
        raise LLAPIContractError(
            f"Checkpoint state could not be restored: {error}."
        ) from error
    collector = DirectReplayCollector(controller)

    restored_summary = boundary_summary(controller, selector, collector)
    if restored_summary != state["verification"]:
        raise LLAPIContractError(
            "Restored checkpoint state failed its boundary verification."
        )
    return LoadedCheckpoint(
        controller=controller,
        selector=selector,
        collector=collector,
        verification=restored_summary,
    )
