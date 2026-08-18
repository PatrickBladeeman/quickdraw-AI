from __future__ import annotations

import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pytest
import torch
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BRANCH_SIZES,
    COMBAT_NAMES,
    MOVEMENT_NAMES,
    DuelingBranchingQNetwork,
    ReplayBuffer,
    ReplayTransition,
    branch_double_dqn_targets,
    branches_from_joint_indices,
    epsilon_greedy_actions,
    greedy_actions,
    joint_indices_from_branches,
    mean_branch_huber_loss,
    validate_installed_plugin_api,
)


CONTRACT_PATH = HERE / "bdq-foundation-contract-v1.json"
SCHEMA_PATH = ROOT / "Research" / "schemas" / "bdq-foundation-contract.schema.json"
BASIC_CONTRACT_PATH = ROOT / "Research" / "basic" / "basic-contract-v1.json"


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


def transition(index: int, **overrides: object) -> ReplayTransition:
    values = {
        "observation": observation(index / 20.0),
        "action": np.asarray([index % 3, index % 2], dtype=np.int32),
        "reward": float(index),
        "next_observation": observation((index + 1) / 20.0),
        "action_masks": masks(),
        "next_action_masks": masks(),
        "terminated": False,
        "truncated": False,
    }
    values.update(overrides)
    return ReplayTransition(**values)  # type: ignore[arg-type]


def test_contract_schema_runtime_and_basic_hash_are_exact() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    basic = json.loads(BASIC_CONTRACT_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(contract)

    assert contract["base_environment_contract"]["sha256"] == sha256_file(
        BASIC_CONTRACT_PATH
    )
    assert contract["base_environment_contract"]["schema_version"] == basic[
        "schema_version"
    ]
    assert contract["actions"]["branch_sizes"] == basic["actions"][
        "discrete_branches"
    ]
    assert tuple(
        basic["actions"]["movement"][str(index)]
        for index in range(BRANCH_SIZES[0])
    ) == MOVEMENT_NAMES
    assert tuple(
        basic["actions"]["combat"][str(index)]
        for index in range(BRANCH_SIZES[1])
    ) == COMBAT_NAMES
    assert contract["runtime"] == {
        "python": "3.11.13",
        "mlagents": version("mlagents"),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "r3a_device": "cpu",
    }


def test_installed_plugin_boundary_matches_mlagents_1_1() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    boundary = validate_installed_plugin_api()
    assert boundary.__dict__ == contract["plugin_boundary"]


def test_action_names_and_joint_indices_match_basic_branch_order() -> None:
    actions = torch.tensor(
        [[0, 0], [0, 1], [1, 0], [1, 1], [2, 0], [2, 1]],
        dtype=torch.int64,
    )
    joint = joint_indices_from_branches(actions)
    assert joint.tolist() == [0, 1, 2, 3, 4, 5]
    assert torch.equal(branches_from_joint_indices(joint), actions)
    assert BRANCH_SIZES == (3, 2)
    assert MOVEMENT_NAMES == ("Stay", "Left", "Right")
    assert COMBAT_NAMES == ("Idle", "Shoot")


def test_greedy_and_seeded_epsilon_actions_never_select_masks() -> None:
    q_values = (
        torch.tensor([[1.0, 100.0, 3.0], [5.0, 4.0, 3.0]]),
        torch.tensor([[2.0, 6.0], [7.0, 8.0]]),
    )
    unavailable = (
        torch.tensor([[False, True, False], [True, False, False]]),
        torch.tensor([[False, False], [False, True]]),
    )
    assert greedy_actions(q_values, unavailable).tolist() == [[2, 1], [1, 0]]

    first_generator = torch.Generator().manual_seed(61001)
    second_generator = torch.Generator().manual_seed(61001)
    first = epsilon_greedy_actions(q_values, unavailable, 1.0, first_generator)
    second = epsilon_greedy_actions(q_values, unavailable, 1.0, second_generator)
    assert torch.equal(first, second)
    for row in range(first.shape[0]):
        for branch in range(first.shape[1]):
            assert not unavailable[branch][row, first[row, branch]]


def test_action_selection_rejects_an_entirely_masked_branch() -> None:
    q_values = (torch.zeros((1, 3)), torch.zeros((1, 2)))
    unavailable = (
        torch.tensor([[True, True, True]]),
        torch.tensor([[False, False]]),
    )
    with pytest.raises(ValueError, match="masks every action"):
        greedy_actions(q_values, unavailable)


def test_replay_transition_is_validated_copied_and_immutable() -> None:
    original = observation(0.25)
    item = transition(1, observation=original)
    original.fill(0.75)
    assert float(item.observation[0, 0, 0]) == pytest.approx(0.25)
    with pytest.raises(ValueError):
        item.observation[0, 0, 0] = 1.0

    with pytest.raises(ValueError, match="both terminated and truncated"):
        transition(1, terminated=True, truncated=True)
    with pytest.raises(TypeError, match="terminated must be boolean"):
        transition(1, terminated="false")
    with pytest.raises(ValueError, match="Selected action"):
        transition(
            1,
            action=np.asarray([1, 1]),
            action_masks=masks(movement=(False, True, False)),
        )


def test_replay_sampling_is_seeded_bounded_and_tensor_ready() -> None:
    first = ReplayBuffer(capacity=5, seed=62001)
    second = ReplayBuffer(capacity=5, seed=62001)
    for index in range(7):
        first.add(transition(index))
        second.add(transition(index))

    assert len(first) == len(second) == 5
    first_batch = first.sample(4)
    second_batch = second.sample(4)
    assert first_batch.indices.tolist() == second_batch.indices.tolist()
    assert first_batch.rewards.tolist() == second_batch.rewards.tolist()
    assert set(first_batch.rewards.tolist()).issubset({2.0, 3.0, 4.0, 5.0, 6.0})

    tensors = first_batch.to_torch()
    assert tensors.observations.shape == (4, 84, 84, 4)
    assert tensors.observations.dtype == torch.float32
    assert tensors.actions.shape == (4, 2)
    assert tensors.actions.dtype == torch.int64
    assert [tuple(mask.shape) for mask in tensors.action_masks] == [(4, 3), (4, 2)]
    assert tensors.terminated.dtype == torch.bool
    assert tensors.truncated.dtype == torch.bool


def test_replay_sampling_rejects_underflow() -> None:
    replay = ReplayBuffer(capacity=4, seed=1)
    replay.add(transition(0))
    with pytest.raises(ValueError, match="more transitions"):
        replay.sample(2)


def test_network_outputs_registered_shapes_and_mean_centered_advantages() -> None:
    torch.manual_seed(63001)
    network = DuelingBranchingQNetwork()
    observations = torch.rand((2, 84, 84, 4), dtype=torch.float32)
    value, advantages = network.forward_components(observations)
    q_values = network(observations)

    assert value.shape == (2, 1)
    assert [tuple(item.shape) for item in advantages] == [(2, 3), (2, 2)]
    assert [tuple(item.shape) for item in q_values] == [(2, 3), (2, 2)]
    for branch_q in q_values:
        assert torch.allclose(branch_q.mean(dim=1, keepdim=True), value, atol=1e-6)

    loss = sum(item.square().mean() for item in q_values)
    loss.backward()
    assert all(
        parameter.grad is not None and torch.isfinite(parameter.grad).all()
        for parameter in network.parameters()
    )


def test_network_layers_match_the_registered_encoder_exactly() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    network = DuelingBranchingQNetwork()
    convolutions = [
        layer for layer in network.encoder if isinstance(layer, torch.nn.Conv2d)
    ]
    actual = [
        {
            "channels": layer.out_channels,
            "kernel": layer.kernel_size[0],
            "stride": layer.stride[0],
        }
        for layer in convolutions
    ]
    assert actual == contract["network"]["encoder"]
    shared = [layer for layer in network.encoder if isinstance(layer, torch.nn.Linear)]
    assert len(shared) == 1
    assert shared[0].in_features == 64 * 7 * 7
    assert shared[0].out_features == contract["network"]["shared_units"]
    assert network.value_head.out_features == contract["network"]["value_outputs"]
    assert [head.out_features for head in network.advantage_heads] == contract[
        "network"
    ]["advantage_outputs"]


def test_network_rejects_wrong_layout_dtype_and_range() -> None:
    network = DuelingBranchingQNetwork()
    with pytest.raises(ValueError, match="shape"):
        network(torch.zeros((1, 4, 84, 84), dtype=torch.float32))
    with pytest.raises(TypeError, match="float32"):
        network(torch.zeros((1, 84, 84, 4), dtype=torch.float64))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        network(torch.full((1, 84, 84, 4), 2.0, dtype=torch.float32))


def test_double_dqn_uses_online_selection_target_evaluation_and_masks() -> None:
    rewards = torch.tensor([1.0])
    online_next = (
        torch.tensor([[1.0, 100.0, 3.0]]),
        torch.tensor([[4.0, 2.0]]),
    )
    target_next = (
        torch.tensor([[10.0, 20.0, 30.0]]),
        torch.tensor([[7.0, 80.0]]),
    )
    next_masks = (
        torch.tensor([[False, True, False]]),
        torch.tensor([[False, False]]),
    )
    result = branch_double_dqn_targets(
        rewards,
        torch.tensor([False]),
        torch.tensor([False]),
        online_next,
        target_next,
        next_masks,
        gamma=0.9,
    )
    assert torch.allclose(result, torch.tensor([[28.0, 7.3]]), atol=1e-6)
    assert result.requires_grad is False


def test_terminal_does_not_bootstrap_but_truncation_does() -> None:
    rewards = torch.tensor([2.0, 3.0])
    online_next = (
        torch.tensor([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        torch.tensor([[0.0, 1.0], [1.0, 0.0]]),
    )
    target_next = (
        torch.tensor([[5.0, 6.0, 7.0], [8.0, 9.0, 10.0]]),
        torch.tensor([[11.0, 12.0], [13.0, 14.0]]),
    )
    next_masks = (
        torch.zeros((2, 3), dtype=torch.bool),
        torch.zeros((2, 2), dtype=torch.bool),
    )
    result = branch_double_dqn_targets(
        rewards,
        torch.tensor([True, False]),
        torch.tensor([False, True]),
        online_next,
        target_next,
        next_masks,
        gamma=0.5,
    )
    assert torch.allclose(
        result,
        torch.tensor([[2.0, 2.0], [8.0, 9.5]]),
    )


def test_mean_branch_huber_loss_averages_batch_and_branches() -> None:
    current_q = (
        torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
        torch.tensor([[7.0, 8.0], [9.0, 10.0]]),
    )
    actions = torch.tensor([[2, 0], [0, 1]])
    targets = torch.tensor([[2.0, 9.0], [6.0, 8.0]])
    loss = mean_branch_huber_loss(current_q, actions, targets)
    selected = torch.tensor([[3.0, 7.0], [4.0, 10.0]])
    expected = torch.nn.functional.smooth_l1_loss(
        selected,
        targets,
        reduction="mean",
        beta=1.0,
    )
    assert loss.item() == pytest.approx(expected.item())


def test_replay_network_targets_and_loss_compose_for_cpu_backward() -> None:
    replay = ReplayBuffer(capacity=4, seed=64001)
    replay.add(transition(1))
    replay.add(
        transition(
            2,
            next_action_masks=masks(
                movement=(False, True, False),
                combat=(False, True),
            ),
            truncated=True,
        )
    )
    batch = replay.sample(2).to_torch()

    torch.manual_seed(64002)
    online = DuelingBranchingQNetwork()
    target = DuelingBranchingQNetwork()
    target.load_state_dict(online.state_dict())

    current_q = online(batch.observations)
    with torch.no_grad():
        online_next_q = online(batch.next_observations)
        target_next_q = target(batch.next_observations)
    targets = branch_double_dqn_targets(
        batch.rewards,
        batch.terminated,
        batch.truncated,
        online_next_q,
        target_next_q,
        batch.next_action_masks,
        gamma=0.99,
    )
    loss = mean_branch_huber_loss(current_q, batch.actions, targets)
    loss.backward()

    assert targets.shape == (2, 2)
    assert torch.isfinite(targets).all()
    assert torch.isfinite(loss)
    assert any(
        parameter.grad is not None and torch.count_nonzero(parameter.grad) > 0
        for parameter in online.parameters()
    )
