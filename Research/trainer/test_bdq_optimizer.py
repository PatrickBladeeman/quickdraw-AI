from __future__ import annotations

import hashlib
import json
import math
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch
from jsonschema import Draft202012Validator
from mlagents import plugins as mlagents_plugins
from mlagents.plugins.trainer_type import register_trainer_plugins
from mlagents.trainers.settings import TrainerSettings
from mlagents.trainers.trainer import TrainerFactory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
    QuickDrawBDQSettings,
    QuickDrawBDQTrainer,
    ReplayTransition,
    R3BRolloutUnavailableError,
    validate_registered_plugin_api,
)


CONTRACT_PATH = HERE / "bdq-optimizer-contract-v1.json"
SCHEMA_PATH = ROOT / "Research" / "schemas" / "bdq-optimizer-contract.schema.json"
FOUNDATION_CONTRACT_PATH = HERE / "bdq-foundation-contract-v1.json"
PYPROJECT_PATH = HERE / "pyproject.toml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def observation(value: float) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def transition(index: int) -> ReplayTransition:
    return ReplayTransition(
        observation=observation((index % 20) / 20.0),
        action=np.asarray([index % 3, index % 2], dtype=np.int64),
        reward=float((index % 5) - 2),
        next_observation=observation(((index + 1) % 20) / 20.0),
        action_masks=masks(),
        next_action_masks=masks(),
        terminated=index % 11 == 10,
        truncated=index % 7 == 6,
    )


def state_snapshot(network: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {
        name: value.detach().clone()
        for name, value in network.state_dict().items()
    }


def states_are_equal(
    left: dict[str, torch.Tensor],
    right: dict[str, torch.Tensor],
) -> bool:
    return left.keys() == right.keys() and all(
        torch.equal(left[name], right[name]) for name in left
    )


class FakeParameterManager:
    def get_minimum_reward_buffer_size(self, behavior_name: str) -> int:
        assert behavior_name
        return 1


def structured_trainer_settings() -> TrainerSettings:
    return TrainerSettings.structure(
        {
            "trainer_type": "quickdraw_bdq",
            "hyperparameters": {},
        },
        TrainerSettings,
    )


def generated_trainer(tmp_path: Path, seed: int = 71001) -> QuickDrawBDQTrainer:
    settings = structured_trainer_settings()
    factory = TrainerFactory(
        trainer_config={"QuickDrawBasic": settings},
        output_path=str(tmp_path),
        train_model=True,
        load_model=False,
        seed=seed,
        param_manager=FakeParameterManager(),  # type: ignore[arg-type]
    )
    trainer = factory.generate("QuickDrawBasic")
    assert isinstance(trainer, QuickDrawBDQTrainer)
    return trainer


def test_contract_schema_runtime_foundation_hash_and_package_are_exact() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION_CONTRACT_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(contract)
    assert contract["base_foundation_contract"] == {
        "path": "Research/trainer/bdq-foundation-contract-v1.json",
        "sha256": sha256_file(FOUNDATION_CONTRACT_PATH),
        "schema_version": foundation["schema_version"],
    }
    assert contract["runtime"] == {
        "python": "3.11.13",
        "mlagents": version("mlagents"),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "r3b_device": "cpu",
    }
    assert pyproject["project"]["name"] == contract["package"]["distribution"]
    assert pyproject["project"]["version"] == contract["package"]["version"]
    assert pyproject["project"]["entry-points"]["mlagents.trainer_type"] == {
        contract["plugin"]["entry_point_name"]: contract["plugin"][
            "entry_point_value"
        ]
    }


def test_official_plugin_discovery_settings_and_factory(tmp_path: Path) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    boundary = validate_registered_plugin_api()
    expected_boundary = {
        **contract["plugin"],
        "distribution": contract["package"]["distribution"],
        "distribution_version": contract["package"]["version"],
    }
    assert boundary.__dict__ == expected_boundary

    mlagents_plugins.all_trainer_types.clear()
    mlagents_plugins.all_trainer_settings.clear()
    trainer_types, trainer_settings = register_trainer_plugins()
    assert trainer_types["quickdraw_bdq"] is QuickDrawBDQTrainer
    assert trainer_settings["quickdraw_bdq"] is QuickDrawBDQSettings

    settings = structured_trainer_settings()
    assert isinstance(settings.hyperparameters, QuickDrawBDQSettings)
    trainer = generated_trainer(tmp_path)
    assert trainer.get_trainer_name() == "quickdraw_bdq"
    assert trainer.optimizer_controller.settings == BDQOptimizationSettings()


def test_registered_trainer_fails_closed_for_unimplemented_rollout(
    tmp_path: Path,
) -> None:
    register_trainer_plugins()
    trainer = generated_trainer(tmp_path)
    calls: tuple[tuple[str, tuple[Any, ...]], ...] = (
        ("save_model", ()),
        ("end_episode", ()),
        ("create_policy", (None, None)),
        ("add_policy", (None, None)),
        ("advance", ()),
    )
    for method_name, arguments in calls:
        with pytest.raises(R3BRolloutUnavailableError, match="R3B is synthetic only"):
            getattr(trainer, method_name)(*arguments)


def test_production_optimizer_and_exploration_defaults_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    registered = contract["registered_defaults"]
    plugin_settings = QuickDrawBDQSettings()
    optimizer_settings = plugin_settings.to_optimization_settings()

    assert optimizer_settings == BDQOptimizationSettings()
    assert {
        "replay_capacity": optimizer_settings.replay_capacity,
        "replay_warmup_decisions": optimizer_settings.replay_warmup_decisions,
        "batch_size": optimizer_settings.batch_size,
        "gamma": optimizer_settings.gamma,
        "optimizer": "Adam",
        "learning_rate": optimizer_settings.learning_rate,
        "optimizer_update_interval_decisions": (
            optimizer_settings.optimizer_update_interval_decisions
        ),
        "optimizer_updates_per_boundary": 1,
        "hard_target_sync_interval_optimizer_updates": (
            optimizer_settings.hard_target_sync_interval_optimizer_updates
        ),
        "epsilon_start": plugin_settings.epsilon_start,
        "epsilon_end": plugin_settings.epsilon_end,
        "exploratory_evaluation_epsilon": (
            plugin_settings.exploratory_evaluation_epsilon
        ),
        "final_evaluation_epsilon": plugin_settings.final_evaluation_epsilon,
    } == registered


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"replay_capacity": 0}, "replay_capacity"),
        ({"replay_capacity": 3, "replay_warmup_decisions": 4}, "capacity"),
        ({"replay_warmup_decisions": 1, "batch_size": 2}, "batch size"),
        ({"batch_size": True}, "batch_size"),
        ({"gamma": math.nan}, "Gamma"),
        ({"gamma": 1.01}, "Gamma"),
        ({"learning_rate": 0.0}, "Learning rate"),
        ({"optimizer_update_interval_decisions": 0}, "update_interval"),
        ({"hard_target_sync_interval_optimizer_updates": 0}, "sync_interval"),
        ({"device": "cuda"}, "CPU device only"),
    ],
)
def test_optimizer_settings_reject_invalid_values(
    overrides: dict[str, object],
    message: str,
) -> None:
    defaults: dict[str, object] = {
        "replay_capacity": 8,
        "replay_warmup_decisions": 4,
        "batch_size": 2,
        "gamma": 0.99,
        "learning_rate": 1.0e-4,
        "optimizer_update_interval_decisions": 2,
        "hard_target_sync_interval_optimizer_updates": 2,
        "device": "cpu",
    }
    defaults.update(overrides)
    with pytest.raises(ValueError, match=message):
        BDQOptimizationSettings(**defaults)  # type: ignore[arg-type]


def test_plugin_settings_reject_fractional_update_interval() -> None:
    with pytest.raises(ValueError, match="positive whole number"):
        QuickDrawBDQSettings(steps_per_update=1.5).to_optimization_settings()


@pytest.mark.parametrize("seed", [-1, 1.0, True])
def test_optimizer_controller_rejects_invalid_seed(seed: object) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        BDQOptimizerController(seed)  # type: ignore[arg-type]


def test_update_and_hard_sync_follow_registered_counters_exactly() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=4,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=2,
    )
    controller = BDQOptimizerController(seed=72001, settings=settings)
    initial_online = state_snapshot(controller.online_network)
    initial_target = state_snapshot(controller.target_network)
    assert states_are_equal(initial_online, initial_target)
    assert all(
        not parameter.requires_grad
        for parameter in controller.target_network.parameters()
    )

    results = [controller.record_transition(transition(index)) for index in range(6)]
    assert [result.updated for result in results] == [
        False,
        False,
        False,
        True,
        False,
        True,
    ]
    assert [result.target_synced for result in results] == [
        False,
        False,
        False,
        False,
        False,
        True,
    ]
    assert [result.decision_count for result in results] == [1, 2, 3, 4, 5, 6]
    assert [result.replay_size for result in results] == [1, 2, 3, 4, 5, 6]
    assert [result.optimizer_update_count for result in results] == [0, 0, 0, 1, 1, 2]
    assert [result.target_sync_count for result in results] == [0, 0, 0, 0, 0, 1]
    for result in (results[3], results[5]):
        assert result.loss is not None and math.isfinite(result.loss)
        assert (
            result.mean_absolute_td_error is not None
            and math.isfinite(result.mean_absolute_td_error)
        )

    final_online = state_snapshot(controller.online_network)
    final_target = state_snapshot(controller.target_network)
    assert not states_are_equal(initial_online, final_online)
    assert states_are_equal(final_online, final_target)
    assert states_are_equal(initial_target, initial_online)


def test_target_remains_frozen_until_the_registered_sync_boundary() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=4,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=2,
    )
    controller = BDQOptimizerController(seed=73001, settings=settings)
    initial_online = state_snapshot(controller.online_network)
    initial_target = state_snapshot(controller.target_network)
    results = [controller.record_transition(transition(index)) for index in range(4)]

    assert results[-1].updated is True
    assert results[-1].target_synced is False
    assert not states_are_equal(initial_online, state_snapshot(controller.online_network))
    assert states_are_equal(initial_target, state_snapshot(controller.target_network))


def test_seeded_optimizer_runs_are_tensor_for_tensor_identical() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=4,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=2,
    )
    first = BDQOptimizerController(seed=74001, settings=settings)
    second = BDQOptimizerController(seed=74001, settings=settings)

    first_results = [first.record_transition(transition(index)) for index in range(6)]
    second_results = [
        second.record_transition(transition(index)) for index in range(6)
    ]

    assert first_results == second_results
    assert states_are_equal(
        state_snapshot(first.online_network),
        state_snapshot(second.online_network),
    )
    assert states_are_equal(
        state_snapshot(first.target_network),
        state_snapshot(second.target_network),
    )


def test_registered_batch_size_executes_one_complete_cpu_update() -> None:
    settings = BDQOptimizationSettings(
        replay_capacity=64,
        replay_warmup_decisions=64,
        batch_size=64,
        optimizer_update_interval_decisions=4,
        hard_target_sync_interval_optimizer_updates=10_000,
    )
    controller = BDQOptimizerController(seed=75001, settings=settings)
    results = [controller.record_transition(transition(index)) for index in range(64)]

    assert all(not result.updated for result in results[:-1])
    assert results[-1].updated is True
    assert results[-1].target_synced is False
    assert results[-1].decision_count == 64
    assert results[-1].replay_size == 64
    assert results[-1].optimizer_update_count == 1
    assert results[-1].target_sync_count == 0
