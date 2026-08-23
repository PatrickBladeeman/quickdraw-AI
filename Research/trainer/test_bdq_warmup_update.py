from __future__ import annotations

import copy
import json
import math
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
    OptimizationStepResult,
    network_sha256,
)
from run_bdq_warmup_update_smoke import (  # noqa: E402
    _complete_transition,
    _emit_watch_progress,
    _environment_side_channels,
    _execution_mode,
    _optimization_event,
    _registered_settings,
    parse_arguments,
    sha256_file,
    validate_contract,
)


CONTRACT_PATH = HERE / "bdq-warmup-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-warmup-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-warmup-update-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def observation(value: float) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def test_r3f_contract_schema_binding_runtime_and_boundary_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_epsilon_collection_contract"]
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
    assert contract["collection"]["transition_limit"] == 10_000
    assert contract["collection"]["transition_limit"] == (
        settings.replay_warmup_decisions
    )
    assert optimization["expected_first_update_decision"] == 10_000
    assert optimization["expected_optimizer_updates"] == 1
    assert optimization["expected_target_synchronizations"] == 0
    assert validate_contract(contract) == result_schema


def test_r3f_contract_rejects_a_drifted_r3e_binding() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    drifted = copy.deepcopy(contract)
    drifted["base_epsilon_collection_contract"]["sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        validate_contract(drifted)


def test_collection_helper_opens_one_update_only_at_warmup() -> None:
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
    initial_online = network_sha256(controller.online_network)
    initial_target = network_sha256(controller.target_network)

    for index in range(4):
        collector.begin(
            0,
            observation(index / 10.0),
            np.asarray([index % 3, index % 2], dtype=np.int64),
            masks(),
        )
        _complete_transition(
            collector,
            0,
            float(index - 1),
            observation((index + 1) / 10.0),
            masks(),
            terminated=index == 3,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_first_update_decision=4,
        )
        if index < 3:
            assert controller.optimizer_update_count == 0

    assert len(transitions) == 4
    assert len(events) == 1
    assert events[0]["decision_count"] == 4
    assert events[0]["optimizer_update_count"] == 1
    assert events[0]["target_sync_count"] == 0
    assert math.isfinite(float(events[0]["loss"]))
    assert math.isfinite(float(events[0]["mean_absolute_td_error"]))
    assert controller.optimizer_update_count == 1
    assert controller.target_sync_count == 0
    assert network_sha256(controller.online_network) != initial_online
    assert network_sha256(controller.target_network) == initial_target
    assert collector.pending_agent_ids == ()


def test_watch_progress_reports_completed_transition(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = OptimizationStepResult(100, 100, 0, 0, False, False, None, None)
    _emit_watch_progress(
        result,
        {"action": [2, 1], "reward": -0.01},
        transition_limit=10_000,
        episode_index=2,
        episode_decision_index=7,
        progress_interval=100,
    )

    assert capsys.readouterr().out == (
        "watch_progress transition=100/10000 episode=3 episode_decision=8 "
        "action=[2,1] reward=-0.01 replay_size=100 optimizer_updates=0 "
        "target_syncs=0\n"
    )


def test_watch_progress_is_quiet_between_intervals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = OptimizationStepResult(99, 99, 0, 0, False, False, None, None)
    _emit_watch_progress(
        result,
        {"action": [0, 0], "reward": 0.0},
        transition_limit=10_000,
        episode_index=0,
        episode_decision_index=98,
        progress_interval=100,
    )

    assert capsys.readouterr().out == ""


def test_watch_engine_configuration_is_separate_from_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, float | int]] = []

    class FakeEngineConfigurationChannel:
        def set_configuration_parameters(self, **parameters: float | int) -> None:
            calls.append(parameters)

    monkeypatch.setattr(
        "run_bdq_warmup_update_smoke.EngineConfigurationChannel",
        FakeEngineConfigurationChannel,
    )
    truncation_channel = object()

    assert _environment_side_channels(truncation_channel, watch=False) == [
        truncation_channel
    ]
    assert calls == []
    watch_channels = _environment_side_channels(truncation_channel, watch=True)
    assert watch_channels[0] is truncation_channel
    assert isinstance(watch_channels[1], FakeEngineConfigurationChannel)
    assert calls == [{"time_scale": 1.0, "target_frame_rate": 60}]


def test_watch_mode_accepts_editor_or_standalone_sources() -> None:
    editor = parse_arguments(["--watch", "--output", "editor-watch"])
    standalone = parse_arguments(
        ["--watch", "--env", "player.exe", "--output", "player-watch"]
    )

    assert _execution_mode(editor) == "watch"
    assert editor.env is None
    assert _execution_mode(standalone) == "watch"
    assert standalone.env == Path("player.exe")


@pytest.mark.parametrize(
    "arguments, message",
    [
        (["--output", "acceptance"], "requires --env"),
        (
            [
                "--env",
                "player.exe",
                "--output",
                "acceptance",
                "--progress-interval",
                "10",
            ],
            "requires --watch",
        ),
        (
            [
                "--watch",
                "--output",
                "editor-watch",
                "--progress-interval",
                "0",
            ],
            "must be positive",
        ),
    ],
)
def test_invalid_watch_and_acceptance_argument_combinations_are_rejected(
    arguments: list[str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _execution_mode(parse_arguments(arguments))


def test_collection_helper_rejects_an_update_at_the_wrong_decision() -> None:
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

    for index in range(3):
        collector.begin(
            0,
            observation(index / 10.0),
            np.asarray([0, 0], dtype=np.int64),
            masks(),
        )
        _complete_transition(
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
            expected_first_update_decision=6,
        )
    collector.begin(0, observation(0.3), np.asarray([0, 0]), masks())
    with pytest.raises(LLAPIContractError, match="wrong decision"):
        _complete_transition(
            collector,
            0,
            0.0,
            observation(0.4),
            masks(),
            terminated=False,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=3,
            expected_first_update_decision=6,
        )


@pytest.mark.parametrize(
    "result",
    [
        OptimizationStepResult(4, 4, 1, 0, True, False, None, 1.0),
        OptimizationStepResult(4, 4, 1, 0, True, False, math.nan, 1.0),
        OptimizationStepResult(4, 4, 1, 0, True, False, 1.0, math.inf),
    ],
)
def test_optimization_event_rejects_missing_or_nonfinite_metrics(
    result: OptimizationStepResult,
) -> None:
    with pytest.raises(LLAPIContractError):
        _optimization_event(result)
