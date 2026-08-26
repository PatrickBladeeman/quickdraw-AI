from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pytest
import torch
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    LinearEpsilonSchedule,
    ScheduledEpsilonGreedyBDQActionSelector,
)


CONTRACT_PATH = HERE / "bdq-epsilon-schedule-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-epsilon-schedule-contract.schema.json"
)
BASE_CONTRACT_PATH = HERE / "bdq-post-update-handoff-contract-v1.json"
PYPROJECT_PATH = HERE / "pyproject.toml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def observation(value: float = 0.25) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([False, True, False], dtype=np.bool_),
        np.asarray([False, False], dtype=np.bool_),
    )


class FixedQNetwork(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.forward_count = 0

    def forward(self, value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        self.forward_count += 1
        batch_size = value.shape[0]
        return (
            torch.tensor([[0.1, 4.0, 0.3]], dtype=torch.float32).repeat(
                batch_size, 1
            ),
            torch.tensor([[0.2, 0.8]], dtype=torch.float32).repeat(batch_size, 1),
        )


def test_r3i_contract_schema_hash_runtime_and_defaults_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    base_contract = json.loads(BASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(contract)
    assert contract["base_post_update_handoff_contract"] == {
        "path": "Research/trainer/bdq-post-update-handoff-contract-v1.json",
        "sha256": sha256_file(BASE_CONTRACT_PATH),
        "schema_version": base_contract["schema_version"],
    }
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

    schedule = LinearEpsilonSchedule()
    settings = BDQOptimizationSettings()
    registered = contract["schedule"]
    assert schedule.replay_warmup_decisions == settings.replay_warmup_decisions
    assert schedule.decay_decisions == settings.replay_capacity
    assert schedule.initial_epsilon == registered["initial_epsilon"]
    assert schedule.final_epsilon == registered["final_epsilon"]
    assert (
        schedule.decay_start_completed_transitions
        == registered["decay_start_completed_transitions"]
    )
    assert (
        schedule.decay_end_completed_transitions
        == registered["decay_end_completed_transitions"]
    )


def test_r3i_contract_rejects_schedule_drift() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    drifted = copy.deepcopy(contract)
    drifted["schedule"]["decay_decisions"] = 99_999

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(drifted)


@pytest.mark.parametrize(
    ("completed_transition_count", "expected_epsilon"),
    [
        (0, 1.0),
        (9_999, 1.0),
        (10_000, 1.0),
        (10_001, 0.999991),
        (60_000, 0.55),
        (109_999, 0.100009),
        (110_000, 0.1),
        (110_001, 0.1),
    ],
)
def test_production_schedule_has_exact_boundaries(
    completed_transition_count: int,
    expected_epsilon: float,
) -> None:
    assert LinearEpsilonSchedule().epsilon_at(
        completed_transition_count
    ) == pytest.approx(expected_epsilon, abs=1.0e-12)


def test_schedule_is_stateless_and_count_derived() -> None:
    schedule = LinearEpsilonSchedule()
    before = dict(schedule.__dict__)

    first = schedule.epsilon_at(60_000)
    schedule.epsilon_at(110_000)
    schedule.epsilon_at(0)
    second = schedule.epsilon_at(60_000)

    assert first == second == pytest.approx(0.55)
    assert schedule.__dict__ == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"replay_warmup_decisions": -1},
        {"replay_warmup_decisions": True},
        {"decay_decisions": 0},
        {"decay_decisions": 1.5},
        {"initial_epsilon": True},
        {"initial_epsilon": math.nan},
        {"initial_epsilon": 1.01},
        {"final_epsilon": -0.01},
        {"initial_epsilon": 0.1, "final_epsilon": 0.1},
        {"initial_epsilon": 0.1, "final_epsilon": 0.2},
    ],
)
def test_schedule_rejects_invalid_configuration(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        LinearEpsilonSchedule(**overrides)  # type: ignore[arg-type]


@pytest.mark.parametrize("completed_transition_count", [-1, True, 1.5, "10000"])
def test_schedule_rejects_invalid_completed_transition_count(
    completed_transition_count: object,
) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        LinearEpsilonSchedule().epsilon_at(
            completed_transition_count  # type: ignore[arg-type]
        )


def test_scheduled_selector_repeats_and_never_selects_masks() -> None:
    first_network = FixedQNetwork()
    second_network = FixedQNetwork()
    schedule = LinearEpsilonSchedule()
    first = ScheduledEpsilonGreedyBDQActionSelector(
        first_network,  # type: ignore[arg-type]
        schedule=schedule,
        seed=61001,
    )
    second = ScheduledEpsilonGreedyBDQActionSelector(
        second_network,  # type: ignore[arg-type]
        schedule=schedule,
        seed=61001,
    )
    unavailable = masks()
    counts = [0, 9_999, 10_000, 10_001, 60_000, 109_999, 110_000, 110_001]

    first_actions = [
        first.select(
            observation(),
            unavailable,
            completed_transition_count=count,
        )
        for count in counts * 8
    ]
    second_actions = [
        second.select(
            observation(),
            unavailable,
            completed_transition_count=count,
        )
        for count in counts * 8
    ]

    assert [action.tolist() for action in first_actions] == [
        action.tolist() for action in second_actions
    ]
    for action in first_actions:
        assert action.dtype == np.int64
        assert not unavailable[0][action[0]]
        assert not unavailable[1][action[1]]


def test_scheduled_selector_skips_warmup_inference_then_uses_online_q_values() -> None:
    network = FixedQNetwork()
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        network,  # type: ignore[arg-type]
        schedule=LinearEpsilonSchedule(),
        seed=61001,
    )

    selector.select(
        observation(),
        masks(),
        completed_transition_count=10_000,
    )
    assert network.forward_count == 0

    selector.select(
        observation(),
        masks(),
        completed_transition_count=10_001,
    )
    assert network.forward_count == 1


@pytest.mark.parametrize(
    ("schedule", "seed"),
    [(object(), 61001), (LinearEpsilonSchedule(), -1), (LinearEpsilonSchedule(), True)],
)
def test_scheduled_selector_rejects_invalid_configuration(
    schedule: object,
    seed: object,
) -> None:
    with pytest.raises(ValueError):
        ScheduledEpsilonGreedyBDQActionSelector(
            FixedQNetwork(),  # type: ignore[arg-type]
            schedule=schedule,  # type: ignore[arg-type]
            seed=seed,  # type: ignore[arg-type]
        )
