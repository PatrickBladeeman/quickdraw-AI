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
from run_bdq_post_update_handoff_smoke import (  # noqa: E402
    _execution_mode,
    _masked_argmax,
    canonical_json_sha256,
    parse_arguments,
    sha256_file,
    validate_contract,
)
from run_bdq_warmup_update_smoke import (  # noqa: E402
    _complete_gate_transition,
    _registered_settings,
    _select_post_update_greedy_action,
)


CONTRACT_PATH = HERE / "bdq-post-update-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-post-update-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-post-update-handoff-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def observation(value: float) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def controller_after_two_updates() -> tuple[
    BDQOptimizerController,
    list[dict[str, object]],
    str,
]:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=2,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=10_000,
    )
    controller = BDQOptimizerController(seed=51001, settings=settings)
    collector = DirectReplayCollector(controller)
    transitions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    target_before = network_sha256(controller.target_network)

    for index in range(4):
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
            terminated=False,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_update_decisions=(2, 4),
            task_name="R3H",
        )
        if result.updated:
            events[-1]["online_after_sha256"] = network_sha256(
                controller.online_network
            )

    assert controller.decision_count == 4
    assert controller.optimizer_update_count == 2
    assert controller.target_sync_count == 0
    assert len(events) == 2
    assert collector.pending_agent_ids == ()
    return controller, events, target_before


def test_r3h_contract_schema_binding_runtime_and_handoff_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_two_update_contract"]
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
    assert contract["r3g_prefix"]["transition_count"] == 10_004
    assert contract["collection"]["transition_limit"] == 10_005
    assert optimization["expected_update_decisions"] == [10_000, 10_004]
    assert optimization["expected_optimizer_updates"] == 2
    assert optimization["expected_target_synchronizations"] == 0
    assert contract["post_update_greedy_handoff"] == {
        "selection_after_decision_count": 10_004,
        "completed_transition_index": 10_004,
        "required_optimizer_update_count": 2,
        "epsilon": 0.0,
        "action_source": "masked_argmax_twice_updated_online_network",
        "comparison_network": "frozen_initial_target_network",
        "require_finite_q_values": True,
        "require_online_target_q_divergence": True,
        "require_action_legal": True,
        "require_no_pending_decision_after_completion": True,
    }
    assert validate_contract(contract) == result_schema


def test_r3h_contract_rejects_a_drifted_r3g_binding() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    drifted = copy.deepcopy(contract)
    drifted["base_two_update_contract"]["sha256"] = "0" * 64

    with pytest.raises(ValidationError):
        validate_contract(drifted)


def test_post_update_handoff_uses_latest_online_network_and_legal_argmax() -> None:
    controller, events, target_before = controller_after_two_updates()
    decision_observation = observation(0.45)
    action_masks = (
        np.asarray([False, True, False], dtype=np.bool_),
        np.asarray([False, False], dtype=np.bool_),
    )

    action, evidence = _select_post_update_greedy_action(
        controller,
        decision_observation,
        action_masks,
        handoff_contract={
            "selection_after_decision_count": 4,
            "required_optimizer_update_count": 2,
            "epsilon": 0.0,
        },
        optimization_events=events,
        target_before_sha256=target_before,
        episode_index=3,
        episode_decision_index=17,
    )

    expected_action = [
        _masked_argmax(values, mask)
        for values, mask in zip(
            evidence["online_q_values"],
            evidence["action_masks"],
        )
    ]
    assert action.tolist() == expected_action
    assert evidence["selected_action"] == expected_action
    assert evidence["selection_after_decision_count"] == 4
    assert evidence["transition_index"] == 4
    assert evidence["optimizer_update_count"] == 2
    assert evidence["target_sync_count"] == 0
    assert evidence["online_sha256"] == events[-1]["online_after_sha256"]
    assert evidence["target_sha256"] == target_before
    assert evidence["max_absolute_q_delta"] > 0.0
    assert evidence["selected_action_legal"] is True
    assert evidence["masked_argmax_verified"] is True
    assert action[0] != 1


def test_post_update_handoff_rejects_a_changed_comparison_target() -> None:
    controller, events, _ = controller_after_two_updates()

    with pytest.raises(LLAPIContractError, match="comparison target changed"):
        _select_post_update_greedy_action(
            controller,
            observation(0.45),
            masks(),
            handoff_contract={
                "selection_after_decision_count": 4,
                "required_optimizer_update_count": 2,
                "epsilon": 0.0,
            },
            optimization_events=events,
            target_before_sha256="0" * 64,
            episode_index=0,
            episode_decision_index=4,
        )


def test_masked_argmax_skips_unavailable_actions_and_rejects_empty_branch() -> None:
    assert _masked_argmax([0.1, 100.0, 0.2], [False, True, False]) == 2

    with pytest.raises(LLAPIContractError, match="removes every"):
        _masked_argmax([0.1, 0.2], [True, True])


def test_canonical_json_sha256_ignores_object_key_order() -> None:
    first = [{"index": 0, "action": [1, 0]}]
    second = [{"action": [1, 0], "index": 0}]

    assert canonical_json_sha256(first) == canonical_json_sha256(second)


def test_r3h_handoff_schema_requires_q_value_evidence() -> None:
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    handoff_schema = {
        **result_schema["$defs"]["handoff"],
        "$defs": result_schema["$defs"],
    }
    handoff = {
        "selection_after_decision_count": 10_004,
        "transition_index": 10_004,
        "episode_index": 0,
        "episode_decision_index": 0,
        "epsilon": 0.0,
        "optimizer_update_count": 2,
        "target_sync_count": 0,
        "online_sha256": "a" * 64,
        "target_sha256": "b" * 64,
        "observation_sha256": "c" * 64,
        "action_masks": [[False, False, True], [False, False]],
        "online_q_values": [[0.1, 0.2, 0.3], [0.4, 0.5]],
        "target_q_values": [[0.0, 0.0, 0.0], [0.0, 0.0]],
        "max_absolute_q_delta": 0.5,
        "selected_action": [1, 1],
        "selected_action_legal": True,
        "masked_argmax_verified": True,
    }

    Draft202012Validator(handoff_schema).validate(handoff)
    handoff.pop("online_q_values")
    with pytest.raises(ValidationError):
        Draft202012Validator(handoff_schema).validate(handoff)


def test_r3h_cli_separates_parent_and_worker_modes() -> None:
    parent = parse_arguments(
        ["--env", "player.exe", "--output", "r3h-acceptance"]
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
