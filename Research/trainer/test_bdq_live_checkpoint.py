from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
    DirectReplayCollector,
    LLAPIContractError,
    LinearEpsilonSchedule,
    ReplayTransition,
    ScheduledEpsilonGreedyBDQActionSelector,
    checkpoint_state_sha256,
    save_controller_checkpoint,
)
from quickdraw_bdq.acceptance import replay_sample_fingerprint  # noqa: E402
from quickdraw_bdq.replay import ReplayBatch  # noqa: E402
from quickdraw_bdq.update_gate import _checkpoint_handoff  # noqa: E402
from run_bdq_live_checkpoint_smoke import (  # noqa: E402
    CONTRACT_PATH,
    CONTRACT_SCHEMA_PATH,
    R3O_CONTRACT_PATH,
    RESULT_SCHEMA_PATH,
    _execution_mode,
    _validate_boundary,
    parse_arguments,
    validate_contract,
)


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_boundary() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = _contract()
    r3o_contract = json.loads(R3O_CONTRACT_PATH.read_text(encoding="utf-8"))
    accepted = contract["accepted_live_boundary"]
    boundary = {
        "schema_version": "quickdraw.bdq-checkpoint.v1",
        "controller_seed": accepted["policy_seed"],
        "exploration_seed": accepted["exploration_seed"],
        "decision_count": accepted["decision_count"],
        "optimizer_update_count": accepted["optimizer_update_count"],
        "target_sync_count": accepted["target_sync_count"],
        "online_network_sha256": accepted["online_network_sha256"],
        "target_network_sha256": accepted["target_network_sha256"],
        "replay": {
            "capacity": accepted["replay"]["capacity"],
            "size": accepted["replay"]["size"],
            "unique_frame_count": 1,
            "frame_reference_count": 80128,
            "frame_payload_bytes": 1,
            "metadata_payload_bytes": 1,
            "accounted_storage_bytes": 2,
            "max_accounted_storage_bytes": accepted["replay"][
                "max_accounted_storage_bytes"
            ],
            "remaining_accounted_storage_bytes": (
                accepted["replay"]["max_accounted_storage_bytes"] - 2
            ),
            "legacy_observation_payload_bytes": 1,
            "legacy_capacity_observation_payload_bytes": 1,
            "cursor": accepted["replay"]["cursor"],
        },
        "pending_agent_ids": [],
    }
    return boundary, r3o_contract, contract


def test_r3q_contract_schema_bindings_and_boundary_are_exact() -> None:
    contract = _contract()
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    for binding_name in ("base_fifth_update_contract", "base_checkpoint_contract"):
        binding = contract[binding_name]
        assert _sha256_file(ROOT / binding["path"]) == binding["sha256"]

    accepted = contract["accepted_live_boundary"]
    assert accepted["transition_count"] == 10_016
    assert accepted["decision_count"] == 10_016
    assert accepted["optimizer_update_count"] == 5
    assert accepted["target_sync_count"] == 0
    assert accepted["pending_agent_ids"] == []
    assert accepted["post_update_action_selected"] is False
    assert contract["checkpoint"]["sample_batch_size"] == 64
    assert contract["determinism"]["fresh_processes"] == 2
    assert validate_contract(contract) == result_schema


def test_r3q_contract_rejects_live_boundary_drift() -> None:
    drifted = copy.deepcopy(_contract())
    drifted["accepted_live_boundary"]["transition_count"] = 10_017

    with pytest.raises(ValidationError):
        validate_contract(drifted)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda boundary: boundary.__setitem__("controller_seed", 1),
        lambda boundary: boundary.__setitem__(
            "online_network_sha256", "0" * 64
        ),
        lambda boundary: boundary["replay"].__setitem__("accounted_storage_bytes", 0),
        lambda boundary: boundary["replay"].__setitem__("cursor", 0),
        lambda boundary: boundary["replay"].__setitem__("frame_reference_count", 0),
        lambda boundary: boundary.__setitem__("pending_agent_ids", [0]),
    ],
)
def test_r3q_boundary_rejects_state_drift(mutation: Any) -> None:
    boundary, r3o_contract, r3q_contract = _valid_boundary()
    mutation(boundary)

    with pytest.raises(LLAPIContractError):
        _validate_boundary(boundary, r3o_contract, r3q_contract)


def test_r3q_cli_separates_parent_saver_and_restorer_modes() -> None:
    parent = parse_arguments(["--env", "player.exe", "--output", "out"])
    saver = parse_arguments(
        ["--env", "player.exe", "--worker-output", "run-1", "--worker-index", "0"]
    )
    restorer = parse_arguments(
        [
            "--mode",
            "restorer",
            "--checkpoint",
            "checkpoint.json",
            "--summary",
            "restored.json",
        ]
    )

    assert _execution_mode(parent) == "parent"
    assert _execution_mode(saver) == "live-worker"
    assert _execution_mode(restorer) == "restorer"

    with pytest.raises(ValueError, match="Live worker mode"):
        _execution_mode(
            parse_arguments(["--env", "player.exe", "--worker-output", "run-1"])
        )
    with pytest.raises(ValueError, match="Restorer mode"):
        _execution_mode(parse_arguments(["--mode", "restorer", "--checkpoint", "checkpoint.json"]))


def test_checkpoint_state_digest_matches_persisted_state(tmp_path: Path) -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=4,
        replay_warmup_decisions=2,
        batch_size=2,
        optimizer_update_interval_decisions=2,
    )
    controller = BDQOptimizerController(51001, settings)
    collector = DirectReplayCollector(controller)
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        controller.online_network,
        schedule=LinearEpsilonSchedule(
            replay_warmup_decisions=2,
            decay_decisions=10,
        ),
        seed=61001,
    )
    checkpoint_path = tmp_path / "checkpoint.json"

    digest = checkpoint_state_sha256(controller, collector, selector)
    save_controller_checkpoint(checkpoint_path, controller, collector, selector)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert checkpoint["state_sha256"] == digest

    controller.record_transition(
        ReplayTransition(
            observation=np.zeros((84, 84, 4), dtype=np.float32),
            action=np.asarray([0, 0], dtype=np.int64),
            reward=0.0,
            next_observation=np.ones((84, 84, 4), dtype=np.float32),
            action_masks=(
                np.zeros(3, dtype=np.bool_),
                np.zeros(2, dtype=np.bool_),
            ),
            next_action_masks=(
                np.zeros(3, dtype=np.bool_),
                np.zeros(2, dtype=np.bool_),
            ),
            terminated=False,
            truncated=False,
        )
    )
    assert checkpoint_state_sha256(controller, collector, selector) != digest


def test_replay_sample_fingerprint_covers_all_batch_fields() -> None:
    observations = np.arange(8, dtype=np.float32).reshape(2, 2, 2)
    actions = np.asarray([[0, 1], [2, 0]], dtype=np.int64)
    rewards = np.asarray([0.5, -1.0], dtype=np.float32)
    next_observations = observations + 1
    action_masks = (
        np.zeros((2, 3), dtype=np.bool_),
        np.zeros((2, 2), dtype=np.bool_),
    )
    next_action_masks = (
        np.zeros((2, 3), dtype=np.bool_),
        np.zeros((2, 2), dtype=np.bool_),
    )
    batch = ReplayBatch(
        observations=observations,
        actions=actions,
        rewards=rewards,
        next_observations=next_observations,
        action_masks=action_masks,
        next_action_masks=next_action_masks,
        terminated=np.asarray([False, True], dtype=np.bool_),
        truncated=np.asarray([False, False], dtype=np.bool_),
        indices=np.asarray([1, 0], dtype=np.int64),
    )

    fingerprint = replay_sample_fingerprint(batch)
    assert fingerprint["batch_size"] == 2
    assert fingerprint["indices"] == [1, 0]
    assert set(fingerprint["fields"]) == {
        "indices",
        "observations",
        "actions",
        "rewards",
        "next_observations",
        "action_masks_0",
        "action_masks_1",
        "next_action_masks_0",
        "next_action_masks_1",
        "terminated",
        "truncated",
    }
    expected = hashlib.sha256(
        np.ascontiguousarray(observations).tobytes(order="C")
    ).hexdigest()
    assert fingerprint["fields"]["observations"] == {
        "dtype": "float32",
        "shape": [2, 2, 2],
        "sha256": expected,
    }


def test_checkpoint_handoff_saves_before_callback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []

    def fake_save(path: Path, controller: Any, collector: Any, selector: Any) -> None:
        del path, controller, collector, selector
        events.append("save")

    def callback(controller: Any, collector: Any, selector: Any) -> None:
        del controller, collector, selector
        events.append("callback")

    monkeypatch.setattr(
        "quickdraw_bdq.update_gate.save_controller_checkpoint", fake_save
    )
    _checkpoint_handoff(
        checkpoint_path=tmp_path / "checkpoint.json",
        checkpoint_callback=callback,
        controller=object(),
        collector=object(),
        scheduled_selector=object(),
        task_name="R3Q",
    )

    assert events == ["save", "callback"]

    with pytest.raises(LLAPIContractError, match="requires a saved"):
        _checkpoint_handoff(
            checkpoint_path=None,
            checkpoint_callback=callback,
            controller=object(),
            collector=object(),
            scheduled_selector=object(),
            task_name="R3Q",
        )

    with pytest.raises(LLAPIContractError, match="scheduled selector"):
        _checkpoint_handoff(
            checkpoint_path=tmp_path / "checkpoint.json",
            checkpoint_callback=None,
            controller=object(),
            collector=object(),
            scheduled_selector=None,
            task_name="R3Q",
        )
