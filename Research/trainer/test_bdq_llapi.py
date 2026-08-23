from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pytest
import torch
from jsonschema import Draft202012Validator
from mlagents_envs.base_env import (
    ActionSpec,
    BehaviorSpec,
    DecisionSteps,
    DimensionProperty,
    ObservationSpec,
    ObservationType,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizerController,
    BasicTruncationMaskSideChannel,
    DirectReplayCollector,
    GreedyBDQActionSelector,
    LLAPIContractError,
    branch_double_dqn_targets,
    read_action_masks,
    validate_basic_behavior_spec,
)


CONTRACT_PATH = HERE / "bdq-llapi-contract-v1.json"
CONTRACT_SCHEMA_PATH = ROOT / "Research" / "schemas" / "bdq-llapi-contract.schema.json"
RESULT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-llapi-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def observation(value: float) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks(
    movement: tuple[bool, bool, bool] = (False, False, False),
    combat: tuple[bool, bool] = (False, False),
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray(movement, dtype=np.bool_),
        np.asarray(combat, dtype=np.bool_),
    )


def behavior_spec() -> BehaviorSpec:
    visual = ObservationSpec(
        shape=(84, 84, 4),
        dimension_property=(
            DimensionProperty.TRANSLATIONAL_EQUIVARIANCE,
            DimensionProperty.TRANSLATIONAL_EQUIVARIANCE,
            DimensionProperty.NONE,
        ),
        observation_type=ObservationType.DEFAULT,
        name="ResearchBasicVisual",
    )
    return BehaviorSpec((visual,), ActionSpec.create_discrete((3, 2)))


def decision_steps() -> DecisionSteps:
    return DecisionSteps(
        obs=[observation(0.25)[None, ...]],
        reward=np.asarray([0.0], dtype=np.float32),
        agent_id=np.asarray([1], dtype=np.int32),
        action_mask=tuple(branch[None, ...] for branch in masks()),
        group_id=np.asarray([0], dtype=np.int32),
        group_reward=np.asarray([0.0], dtype=np.float32),
    )


def test_contract_schema_hash_bindings_runtime_and_retirement_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    for name in (
        "base_environment_contract",
        "base_foundation_contract",
        "base_optimizer_contract",
    ):
        binding = contract[name]
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
    for relative_path in contract["retired_trajectory_scaffolding"]:
        assert not (ROOT / relative_path).exists()


def test_behavior_and_decision_masks_match_the_direct_llapi_contract() -> None:
    validate_basic_behavior_spec(behavior_spec())
    actual = read_action_masks(decision_steps(), 0)
    assert [item.tolist() for item in actual] == [
        [False, False, False],
        [False, False],
    ]

    bad_spec = BehaviorSpec(
        behavior_spec().observation_specs,
        ActionSpec.create_discrete((3, 3)),
    )
    with pytest.raises(LLAPIContractError, match="branches"):
        validate_basic_behavior_spec(bad_spec)


def test_direct_collector_completes_each_pending_decision_once() -> None:
    controller = BDQOptimizerController(seed=51001)
    collector = DirectReplayCollector(controller)
    collector.begin(
        1,
        observation(0.1),
        np.asarray([2, 0], dtype=np.int64),
        masks(),
    )
    transition, result = collector.complete(
        1,
        -0.01,
        observation(0.2),
        masks(movement=(False, False, True)),
        terminated=False,
        truncated=False,
    )

    assert transition.action.tolist() == [2, 0]
    assert transition.reward == pytest.approx(-0.01)
    assert np.array_equal(transition.next_observation, observation(0.2))
    assert transition.next_action_masks[0].tolist() == [False, False, True]
    assert result.decision_count == result.replay_size == 1
    assert result.updated is False
    assert collector.pending_agent_ids == ()
    with pytest.raises(LLAPIContractError, match="no pending decision"):
        collector.complete(
            1,
            0.0,
            observation(0.3),
            masks(),
            terminated=False,
            truncated=False,
        )


def test_greedy_selector_uses_the_online_network_and_rejects_masked_actions() -> None:
    controller = BDQOptimizerController(seed=51001)
    selector = GreedyBDQActionSelector(controller.online_network)
    action = selector.select(
        observation(0.25),
        masks(movement=(False, True, False), combat=(False, True)),
    )
    assert action.shape == (2,)
    assert action.dtype == np.int64
    assert action[0] in (0, 2)
    assert action[1] == 0


def test_truncation_channel_is_strict_correlated_and_supplies_replay_mask() -> None:
    channel = BasicTruncationMaskSideChannel()
    payload = {
        "schema_version": "quickdraw.basic-truncation-mask.v1",
        "message_type": "truncation_mask",
        "scenario_seed": 31001,
        "episode_index": 1,
        "decision_count": 300,
        "reason": "decision_limit",
        "position_slot": -4,
        "movement_unavailable": [False, True, False],
        "combat_unavailable": [False, False],
    }
    channel.accept_json(json.dumps(payload))
    event = channel.take(1, 300)
    assert event.position_slot == -4
    assert event.action_masks[0].tolist() == [False, True, False]
    channel.assert_empty()

    channel.accept_json(json.dumps(payload))
    with pytest.raises(LLAPIContractError, match="Duplicate"):
        channel.accept_json(json.dumps(payload))

    wrong_mask = {**payload, "episode_index": 2, "movement_unavailable": [False, False, False]}
    with pytest.raises(LLAPIContractError, match="final slot"):
        BasicTruncationMaskSideChannel().accept_json(json.dumps(wrong_mask))


def test_authoritative_truncation_mask_controls_double_dqn_bootstrap() -> None:
    rewards = torch.tensor([1.0])
    terminated = torch.tensor([False])
    truncated = torch.tensor([True])
    online_next = (
        torch.tensor([[1.0, 100.0, 3.0]]),
        torch.tensor([[4.0, 2.0]]),
    )
    target_next = (
        torch.tensor([[10.0, 20.0, 30.0]]),
        torch.tensor([[40.0, 50.0]]),
    )
    next_masks = (
        torch.tensor([[False, True, False]]),
        torch.tensor([[False, False]]),
    )

    actual = branch_double_dqn_targets(
        rewards,
        terminated,
        truncated,
        online_next,
        target_next,
        next_masks,
        gamma=0.5,
    )
    assert torch.equal(actual, torch.tensor([[16.0, 21.0]]))
