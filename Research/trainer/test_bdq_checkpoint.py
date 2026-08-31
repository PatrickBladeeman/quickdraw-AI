from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest
import torch
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
    DirectReplayCollector,
    LLAPIContractError,
    LinearEpsilonSchedule,
    LoadedCheckpoint,
    ScheduledEpsilonGreedyBDQActionSelector,
    load_controller_checkpoint,
    network_sha256,
    save_controller_checkpoint,
)
from quickdraw_bdq.checkpoint import boundary_summary  # noqa: E402
from quickdraw_bdq.network import OBSERVATION_SHAPE  # noqa: E402
from run_bdq_checkpoint_roundtrip_smoke import (  # noqa: E402
    _drive_continuation,
    _drive_transition,
    _build_trainer,
    _execution_mode,
    parse_arguments,
    validate_contract,
)


CONTRACT_PATH = HERE / "bdq-checkpoint-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-checkpoint-contract.schema.json"
)
CHECKPOINT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-checkpoint.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-checkpoint-roundtrip-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
BOUNDARY_TRANSITIONS = 36


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _settings() -> BDQOptimizationSettings:
    return BDQOptimizationSettings(
        replay_capacity=32,
        replay_warmup_decisions=24,
        batch_size=8,
        optimizer_update_interval_decisions=4,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_to_boundary() -> tuple[
    BDQOptimizerController,
    ScheduledEpsilonGreedyBDQActionSelector,
    DirectReplayCollector,
]:
    controller, selector, collector = _build_trainer()
    for index in range(BOUNDARY_TRANSITIONS):
        _drive_transition(index, controller, selector, collector)
    return controller, selector, collector


def _raw_states_equal(left: Any, right: Any) -> bool:
    if isinstance(left, torch.Tensor) or isinstance(right, torch.Tensor):
        return (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.dtype == right.dtype
            and left.shape == right.shape
            and torch.equal(left, right)
        )
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return (
            isinstance(left, np.ndarray)
            and isinstance(right, np.ndarray)
            and left.dtype == right.dtype
            and left.shape == right.shape
            and np.array_equal(left, right)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _raw_states_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _raw_states_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, bytes) or isinstance(right, bytes):
        return (
            isinstance(left, bytes)
            and isinstance(right, bytes)
            and left == right
        )
    return left == right


def _rewrite_checkpoint(
    checkpoint: dict[str, Any],
    path: Path,
) -> None:
    path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_r3p_contract_schema_binding_and_registration_are_exact() -> None:
    contract = _contract()
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    checkpoint_schema = json.loads(CHECKPOINT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(checkpoint_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_fifth_update_contract"]
    assert _sha256_file(ROOT / binding["path"]) == binding["sha256"]
    assert contract["runtime"] == {
        "python": ".".join(str(item) for item in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }
    assert pyproject["project"]["name"] == contract["package"]["distribution"]
    assert pyproject["project"]["version"] == contract["package"]["version"]
    assert "entry-points" not in pyproject["project"]

    import dataclasses

    workload = contract["reference_workload"]
    assert workload["settings"] == dataclasses.asdict(_settings())
    assert workload["schedule"] == dataclasses.asdict(LinearEpsilonSchedule())
    assert workload["transitions_before_checkpoint"] == 36
    assert workload["optimizer_updates_at_save"] == 4
    assert workload["replay_size_at_save"] == 32
    assert workload["replay_cursor_at_save"] == 36 % 32
    assert workload["replay_unique_frames_at_save"] == 20
    assert workload["continuation_transitions"] == 4
    assert workload["next_update_decision_count"] == 40
    assert workload["bounded_optimizer_updates_after_restore"] == 1
    assert contract["determinism"]["fresh_processes"] == 3
    assert contract["determinism"]["unity_player_required"] is False
    assert validate_contract(contract) == result_schema


def test_r3p_checkpoint_round_trip_preserves_exact_state(
    tmp_path: Path,
) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    summary = save_controller_checkpoint(
        checkpoint_path, controller, collector, selector
    )

    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=_settings(),
        controller_seed=51001,
        exploration_seed=61001,
        schedule=LinearEpsilonSchedule(),
    )

    assert isinstance(loaded, LoadedCheckpoint)
    assert loaded.verification == summary
    assert loaded.verification["decision_count"] == 36
    assert loaded.verification["optimizer_update_count"] == 4
    assert loaded.verification["target_sync_count"] == 0
    assert loaded.verification["replay"]["size"] == 32
    assert loaded.verification["replay"]["cursor"] == 4
    assert loaded.verification["replay"]["unique_frame_count"] == 20
    assert loaded.verification["pending_agent_ids"] == []
    assert (
        network_sha256(loaded.controller.online_network)
        == summary["online_network_sha256"]
    )
    assert (
        network_sha256(loaded.controller.target_network)
        == summary["target_network_sha256"]
    )
    assert _raw_states_equal(
        loaded.controller.export_checkpoint_state(),
        controller.export_checkpoint_state(),
    )
    assert _raw_states_equal(
        loaded.controller.replay.export_checkpoint_state(),
        controller.replay.export_checkpoint_state(),
    )
    assert _raw_states_equal(
        loaded.selector.export_checkpoint_state(),
        selector.export_checkpoint_state(),
    )

    original_batch = controller.replay.sample(8)
    restored_batch = loaded.controller.replay.sample(8)
    assert [int(value) for value in restored_batch.indices] == [
        int(value) for value in original_batch.indices
    ]
    assert np.array_equal(restored_batch.observations, original_batch.observations)
    assert np.array_equal(
        restored_batch.next_observations, original_batch.next_observations
    )


def test_r3p_restored_continuation_matches_uninterrupted_reference(
    tmp_path: Path,
) -> None:
    reference_controller, reference_selector, reference_collector = (
        _build_to_boundary()
    )
    at_boundary = boundary_summary(
        reference_controller, reference_selector, reference_collector
    )
    reference_update = _drive_continuation(
        reference_controller,
        reference_selector,
        reference_collector,
        BOUNDARY_TRANSITIONS,
    )

    saver_controller, saver_selector, saver_collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(
        checkpoint_path, saver_controller, saver_collector, saver_selector
    )

    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=_settings(),
        controller_seed=51001,
        exploration_seed=61001,
        schedule=LinearEpsilonSchedule(),
    )
    restored_update = _drive_continuation(
        loaded.controller,
        loaded.selector,
        loaded.collector,
        BOUNDARY_TRANSITIONS,
    )

    assert boundary_summary(
        saver_controller, saver_selector, saver_collector
    ) == at_boundary
    assert loaded.verification == at_boundary
    assert restored_update == reference_update
    assert restored_update["decision_count"] == 40
    assert restored_update["optimizer_update_count"] == 5
    assert restored_update["replay_size"] == 32
    assert restored_update["target_sync_count"] == 0
    assert (
        restored_update["online_after_sha256"]
        != at_boundary["online_network_sha256"]
    )
    assert (
        restored_update["target_after_sha256"]
        == at_boundary["target_network_sha256"]
    )


def test_r3p_checkpoint_file_bytes_are_deterministic(
    tmp_path: Path,
) -> None:
    controller, selector, collector = _build_to_boundary()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    save_controller_checkpoint(first_path, controller, collector, selector)

    rebuilt_controller, rebuilt_selector, rebuilt_collector = _build_to_boundary()
    save_controller_checkpoint(
        second_path, rebuilt_controller, rebuilt_collector, rebuilt_selector
    )

    assert first_path.read_bytes() == second_path.read_bytes()
    assert _sha256_file(first_path) == _sha256_file(second_path)


def test_r3p_checkpoint_schema_validates_the_saved_file(
    tmp_path: Path,
) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    schema = json.loads(CHECKPOINT_SCHEMA_PATH.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(checkpoint)


def test_r3p_save_rejects_a_pending_decision_boundary(
    tmp_path: Path,
) -> None:
    controller, selector, collector = _build_to_boundary()
    observation = np.zeros(OBSERVATION_SHAPE, dtype=np.float32)
    collector.begin(
        0,
        observation,
        np.asarray([0, 0], dtype=np.int64),
        (np.zeros(3, dtype=np.bool_), np.zeros(2, dtype=np.bool_)),
    )
    checkpoint_path = tmp_path / "checkpoint.json"

    with pytest.raises(LLAPIContractError, match="pending"):
        save_controller_checkpoint(
            checkpoint_path, controller, collector, selector
        )
    assert not checkpoint_path.exists()


def test_r3p_load_rejects_a_corrupt_state(tmp_path: Path) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    corrupt = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    corrupt["state"]["controller"]["decision_count"] = 35
    _rewrite_checkpoint(corrupt, checkpoint_path)

    with pytest.raises(LLAPIContractError, match="state hash mismatch"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=_settings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3p_load_rejects_an_incomplete_checkpoint(tmp_path: Path) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    incomplete = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    del incomplete["state"]["replay"]
    _rewrite_checkpoint(incomplete, checkpoint_path)

    with pytest.raises(LLAPIContractError, match="schema validation failed"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=_settings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3p_load_rejects_a_crafted_incoherent_state(tmp_path: Path) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    crafted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    entries = crafted["state"]["replay"]["frame_refcounts"]["entries"]
    entries[0][1] = int(entries[0][1]) + 1
    canonical = json.dumps(
        crafted["state"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    crafted["state_sha256"] = hashlib.sha256(canonical).hexdigest()
    _rewrite_checkpoint(crafted, checkpoint_path)

    with pytest.raises(LLAPIContractError, match="refcount"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=_settings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3p_load_rejects_a_crafted_masked_action_row(
    tmp_path: Path,
) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    crafted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    actions_payload = crafted["state"]["replay"]["actions"]
    actions = (
        np.frombuffer(
            base64.b64decode(actions_payload["data"]),
            dtype=np.int64,
        )
        .copy()
        .reshape(actions_payload["shape"])
    )
    movement_payload = crafted["state"]["replay"]["action_masks"]["items"][0]
    movement = (
        np.frombuffer(
            base64.b64decode(movement_payload["data"]),
            dtype=np.bool_,
        )
        .copy()
        .reshape(movement_payload["shape"])
    )
    movement[0, actions[0, 0]] = True
    movement_payload["data"] = base64.b64encode(
        movement.tobytes(order="C")
    ).decode("ascii")
    canonical = json.dumps(
        crafted["state"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    crafted["state_sha256"] = hashlib.sha256(canonical).hexdigest()
    _rewrite_checkpoint(crafted, checkpoint_path)

    with pytest.raises(LLAPIContractError, match="masked by their own row"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=_settings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3p_load_rejects_a_crafted_incomplete_optimizer_state(
    tmp_path: Path,
) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    crafted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    entries = crafted["state"]["controller"]["optimizer_state_dict"][
        "state"
    ]["entries"]
    entries.pop()
    canonical = json.dumps(
        crafted["state"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    crafted["state_sha256"] = hashlib.sha256(canonical).hexdigest()
    _rewrite_checkpoint(crafted, checkpoint_path)

    with pytest.raises(LLAPIContractError, match="optimizer state is incomplete"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=_settings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda checkpoint: checkpoint["identity"]["settings"].__setitem__(
                "batch_size", 9
            ),
            LLAPIContractError,
        ),
        (
            lambda checkpoint: checkpoint["identity"]["seeds"].__setitem__(
                "controller_seed", 51002
            ),
            LLAPIContractError,
        ),
        (
            lambda checkpoint: checkpoint["identity"]["package"].__setitem__(
                "version", "0.4.0"
            ),
            LLAPIContractError,
        ),
        (
            lambda checkpoint: checkpoint["identity"]["runtime"].__setitem__(
                "numpy", "1.24.0"
            ),
            LLAPIContractError,
        ),
        (
            lambda checkpoint: checkpoint.__setitem__(
                "contract_sha256", "0" * 64
            ),
            LLAPIContractError,
        ),
        (
            lambda checkpoint: checkpoint.__setitem__(
                "schema_version", "quickdraw.bdq-checkpoint.v2"
            ),
            LLAPIContractError,
        ),
    ],
)
def test_r3p_load_rejects_incompatible_identity(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    expected: type[Exception],
) -> None:
    controller, selector, collector = _build_to_boundary()
    checkpoint_path = tmp_path / "checkpoint.json"
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)

    drifted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    mutate(drifted)
    _rewrite_checkpoint(drifted, checkpoint_path)

    with pytest.raises(expected):
        load_controller_checkpoint(
            checkpoint_path,
            settings=_settings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3p_cli_separates_parent_and_worker_modes() -> None:
    parent = parse_arguments(["--output", "r3p-acceptance"])
    reference = parse_arguments(
        ["--mode", "reference", "--summary", "reference.json"]
    )
    saver = parse_arguments(
        [
            "--mode",
            "saver",
            "--checkpoint",
            "checkpoint.json",
            "--summary",
            "saver.json",
        ]
    )

    assert _execution_mode(parent) == "parent"
    assert _execution_mode(reference) == "worker"
    assert _execution_mode(saver) == "worker"

    with pytest.raises(ValueError, match="Worker mode"):
        _execution_mode(
            parse_arguments(["--mode", "saver", "--summary", "saver.json"])
        )
    with pytest.raises(ValueError, match="Parent mode"):
        _execution_mode(
            parse_arguments(
                ["--output", "r3p-acceptance", "--summary", "saver.json"]
            )
        )
    with pytest.raises(ValueError, match="Parent mode"):
        _execution_mode(parse_arguments(["--checkpoint", "checkpoint.json"]))
