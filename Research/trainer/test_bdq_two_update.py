from __future__ import annotations

import copy
import json
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

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
    network_sha256,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    registered_settings as _registered_settings,
    sha256_file,
)
from quickdraw_bdq.update_gate import _complete_gate_transition  # noqa: E402
from run_bdq_two_update_smoke import (  # noqa: E402
    _execution_mode,
    parse_arguments,
    validate_contract,
)


CONTRACT_PATH = HERE / "bdq-two-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-two-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-two-update-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def observation(value: float) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def test_r3g_contract_schema_binding_runtime_and_schedule_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_warmup_update_contract"]
    assert sha256_file(ROOT / binding["path"]) == binding["sha256"]
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

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    assert _registered_settings(settings) == {
        key: optimization[key] for key in _registered_settings(settings)
    }
    assert contract["collection"]["transition_limit"] == 10_004
    assert optimization["expected_update_decisions"] == [10_000, 10_004]
    assert optimization["expected_optimizer_updates"] == 2
    assert optimization["expected_target_synchronizations"] == 0
    assert validate_contract(contract) == result_schema


def test_r3g_contract_rejects_a_drifted_r3f_binding() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    drifted = copy.deepcopy(contract)
    drifted["base_warmup_update_contract"]["sha256"] = "0" * 64

    with pytest.raises(ValidationError):
        validate_contract(drifted)


def test_collection_helper_opens_two_updates_on_the_registered_schedule() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=4,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=10_000,
    )
    controller = BDQOptimizerController(seed=51001, settings=settings)
    collector = DirectReplayCollector(controller)
    transitions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    online_hashes = [network_sha256(controller.online_network)]
    target_before = network_sha256(controller.target_network)

    for index in range(6):
        collector.begin(
            0,
            observation(index / 10.0),
            np.asarray([index % 3, index % 2], dtype=np.int64),
            masks(),
        )
        result = _complete_gate_transition(
            collector,
            0,
            float(index - 1),
            observation((index + 1) / 10.0),
            masks(),
            terminated=index == 5,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_update_decisions=(4, 6),
            task_name="R3G",
        )
        if result.updated:
            update_hash = network_sha256(controller.online_network)
            events[-1]["online_after_sha256"] = update_hash
            online_hashes.append(update_hash)

    assert len(transitions) == 6
    assert [event["decision_count"] for event in events] == [4, 6]
    assert [event["optimizer_update_count"] for event in events] == [1, 2]
    assert [event["replay_size"] for event in events] == [4, 6]
    assert len(set(online_hashes)) == 3
    assert network_sha256(controller.target_network) == target_before
    assert controller.optimizer_update_count == 2
    assert controller.target_sync_count == 0
    assert collector.pending_agent_ids == ()


def test_collection_helper_rejects_an_unregistered_second_update() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=4,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=10_000,
    )
    controller = BDQOptimizerController(seed=51001, settings=settings)
    collector = DirectReplayCollector(controller)
    transitions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    for index in range(6):
        collector.begin(0, observation(index / 10.0), np.asarray([0, 0]), masks())
        if index == 5:
            with pytest.raises(LLAPIContractError, match="wrong decision"):
                _complete_gate_transition(
                    collector,
                    0,
                    0.0,
                    observation(0.6),
                    masks(),
                    terminated=False,
                    truncated=False,
                    transitions=transitions,
                    optimization_events=events,
                    episode_index=0,
                    episode_decision_index=index,
                    expected_update_decisions=(4,),
                    task_name="R3G",
                )
            break
        _complete_gate_transition(
            collector,
            0,
            0.0,
            observation((index + 1) / 10.0),
            masks(),
            terminated=False,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_update_decisions=(4,),
            task_name="R3G",
        )


def test_collection_helper_rejects_a_missed_registered_update() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=4,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=10_000,
    )
    controller = BDQOptimizerController(seed=51001, settings=settings)
    collector = DirectReplayCollector(controller)
    transitions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    for index in range(5):
        collector.begin(0, observation(index / 10.0), np.asarray([0, 0]), masks())
        if index == 4:
            with pytest.raises(LLAPIContractError, match="missed"):
                _complete_gate_transition(
                    collector,
                    0,
                    0.0,
                    observation(0.5),
                    masks(),
                    terminated=False,
                    truncated=False,
                    transitions=transitions,
                    optimization_events=events,
                    episode_index=0,
                    episode_decision_index=index,
                    expected_update_decisions=(4, 5),
                    task_name="R3G",
                )
            break
        _complete_gate_transition(
            collector,
            0,
            0.0,
            observation((index + 1) / 10.0),
            masks(),
            terminated=False,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_update_decisions=(4, 5),
            task_name="R3G",
        )


def test_r3g_event_schema_requires_a_per_update_online_hash() -> None:
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    event_schema = {
        **result_schema["$defs"]["optimization_event"],
        "$defs": result_schema["$defs"],
    }
    event = {
        "decision_count": 10_000,
        "replay_size": 10_000,
        "optimizer_update_count": 1,
        "target_sync_count": 0,
        "updated": True,
        "target_synced": False,
        "loss": 0.1,
        "mean_absolute_td_error": 0.2,
        "online_after_sha256": "a" * 64,
    }

    Draft202012Validator(event_schema).validate(event)
    event.pop("online_after_sha256")
    with pytest.raises(ValidationError):
        Draft202012Validator(event_schema).validate(event)


def test_r3g_cli_separates_parent_and_worker_modes() -> None:
    parent = parse_arguments(
        ["--env", "player.exe", "--output", "r3g-acceptance"]
    )
    worker = parse_arguments(
        [
            "--env",
            "player.exe",
            "--worker-output",
            "run-1",
            "--worker-index",
            "0",
        ]
    )

    assert _execution_mode(parent) == "parent"
    assert _execution_mode(worker) == "worker"
