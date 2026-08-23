from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
    GreedyBDQActionSelector,
    SeededEpsilonGreedyBDQActionSelector,
)
from run_bdq_epsilon_collection_smoke import (  # noqa: E402
    _action_tuple_counts,
    validate_contract,
)


CONTRACT_PATH = HERE / "bdq-epsilon-collection-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-epsilon-collection-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-epsilon-collection-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def observation(value: float = 0.25) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks(
    movement: tuple[bool, bool, bool] = (False, False, False),
    combat: tuple[bool, bool] = (False, False),
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray(movement, dtype=np.bool_),
        np.asarray(combat, dtype=np.bool_),
    )


def test_r3e_contract_schema_hash_runtime_and_warmup_boundary_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_llapi_contract"]
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
    collection = contract["collection"]
    assert collection["transition_limit"] == 1000
    assert collection["transition_limit"] < settings.replay_warmup_decisions
    assert collection["replay_warmup_decisions"] == settings.replay_warmup_decisions
    assert validate_contract(contract) == result_schema


def test_seeded_epsilon_selector_repeats_and_never_selects_masks() -> None:
    first_controller = BDQOptimizerController(seed=51001)
    second_controller = BDQOptimizerController(seed=51001)
    first = SeededEpsilonGreedyBDQActionSelector(
        first_controller.online_network,
        epsilon=1.0,
        seed=61001,
    )
    second = SeededEpsilonGreedyBDQActionSelector(
        second_controller.online_network,
        epsilon=1.0,
        seed=61001,
    )
    unavailable = masks(movement=(False, True, False), combat=(False, False))

    first_actions = [first.select(observation(), unavailable) for _ in range(128)]
    second_actions = [second.select(observation(), unavailable) for _ in range(128)]
    assert [action.tolist() for action in first_actions] == [
        action.tolist() for action in second_actions
    ]
    assert len({tuple(action.tolist()) for action in first_actions}) >= 2
    for action in first_actions:
        assert action.dtype == np.int64
        assert not unavailable[0][action[0]]
        assert not unavailable[1][action[1]]


def test_zero_epsilon_selector_matches_masked_online_greedy() -> None:
    controller = BDQOptimizerController(seed=51001)
    epsilon_selector = SeededEpsilonGreedyBDQActionSelector(
        controller.online_network,
        epsilon=0.0,
        seed=61001,
    )
    greedy_selector = GreedyBDQActionSelector(controller.online_network)
    unavailable = masks(movement=(False, False, True), combat=(False, True))
    assert np.array_equal(
        epsilon_selector.select(observation(), unavailable),
        greedy_selector.select(observation(), unavailable),
    )


@pytest.mark.parametrize(
    ("epsilon", "seed"),
    [(-0.01, 61001), (1.01, 61001), (True, 61001), (1.0, -1)],
)
def test_seeded_epsilon_selector_rejects_invalid_configuration(
    epsilon: float,
    seed: int,
) -> None:
    controller = BDQOptimizerController(seed=51001)
    with pytest.raises(ValueError):
        SeededEpsilonGreedyBDQActionSelector(
            controller.online_network,
            epsilon=epsilon,
            seed=seed,
        )


def test_action_tuple_histogram_uses_the_registered_row_major_mapping() -> None:
    transitions = [
        {"action": [0, 0]},
        {"action": [0, 1]},
        {"action": [2, 1]},
        {"action": [2, 1]},
    ]
    assert _action_tuple_counts(transitions) == [1, 1, 0, 0, 0, 2]
