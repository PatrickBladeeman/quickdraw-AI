from __future__ import annotations

import copy
import json
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    LLAPIContractError,
    LinearEpsilonSchedule,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    registered_settings as _registered_settings,
    sha256_file,
)
from run_bdq_fourth_update_smoke import (  # noqa: E402
    _execution_mode,
    _validate_distinct_trace_paths,
    execute_worker,
    parse_arguments,
    validate_contract,
    validate_trace,
)


CONTRACT_PATH = HERE / "bdq-fourth-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-fourth-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-fourth-update-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
PROJECT_SETTINGS_PATH = ROOT / "ProjectSettings" / "ProjectSettings.asset"


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _task_trace(contract: dict[str, Any]) -> dict[str, Any]:
    prefix = contract["r3k_prefix"]
    schedule = contract["epsilon_schedule"]
    events = [
        {
            "decision_count": 10_000,
            "replay_size": 10_000,
            "optimizer_update_count": 1,
            "target_sync_count": 0,
            "updated": True,
            "target_synced": False,
            "loss": prefix["first_update_loss"],
            "mean_absolute_td_error": prefix[
                "first_update_mean_absolute_td_error"
            ],
            "online_after_sha256": prefix[
                "online_after_first_update_sha256"
            ],
        },
        {
            "decision_count": 10_004,
            "replay_size": 10_004,
            "optimizer_update_count": 2,
            "target_sync_count": 0,
            "updated": True,
            "target_synced": False,
            "loss": prefix["second_update_loss"],
            "mean_absolute_td_error": prefix[
                "second_update_mean_absolute_td_error"
            ],
            "online_after_sha256": prefix[
                "online_after_second_update_sha256"
            ],
        },
        {
            "decision_count": 10_008,
            "replay_size": 10_008,
            "optimizer_update_count": 3,
            "target_sync_count": 0,
            "updated": True,
            "target_synced": False,
            "loss": prefix["third_update_loss"],
            "mean_absolute_td_error": prefix[
                "third_update_mean_absolute_td_error"
            ],
            "online_after_sha256": prefix[
                "online_after_third_update_sha256"
            ],
        },
        {
            "decision_count": 10_012,
            "replay_size": 10_012,
            "optimizer_update_count": 4,
            "target_sync_count": 0,
            "updated": True,
            "target_synced": False,
            "loss": 0.01,
            "mean_absolute_td_error": 0.02,
            "online_after_sha256": "1" * 64,
        },
    ]
    samples = [
        {"completed_transition_count": count, "epsilon": epsilon}
        for count, epsilon in zip(
            schedule["trace_sample_completed_transition_counts"],
            schedule["trace_sample_epsilons"],
        )
    ]
    return {
        "transitions": [],
        "optimization": {
            "update_events": events,
            "online_after_sha256": "1" * 64,
            "target_before_sha256": prefix["frozen_target_sha256"],
            "target_after_sha256": prefix["frozen_target_sha256"],
        },
        "selector": {
            "selection_count": schedule["selection_count"],
            "full_exploration_selection_count": schedule[
                "full_exploration_selection_count"
            ],
            "decay_selection_count": schedule["decay_selection_count"],
            "first_decay_completed_transition_count": schedule[
                "first_decay_completed_transition_count"
            ],
            "last_selection_completed_transition_count": schedule[
                "last_selection_completed_transition_count"
            ],
            "completed_transition_count_source": schedule[
                "completed_transition_count_source"
            ],
            "epsilon_samples": samples,
        },
        "replay": {"decision_count": 10_012},
    }


def test_r3m_contract_schemas_binding_runtime_and_boundaries_are_exact() -> None:
    contract = _contract()
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_third_update_contract"]
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
    assert contract["player_execution"] == {
        "project_settings_path": "ProjectSettings/ProjectSettings.asset",
        "run_in_background": True,
        "no_graphics": False,
        "standalone_player_arguments": [],
    }
    assert "  runInBackground: 1" in PROJECT_SETTINGS_PATH.read_text(
        encoding="utf-8"
    ).splitlines()

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    assert _registered_settings(settings) == {
        key: optimization[key] for key in _registered_settings(settings)
    }
    assert optimization["expected_update_decisions"] == [
        10_000,
        10_004,
        10_008,
        10_012,
    ]
    assert optimization["expected_optimizer_updates"] == 4
    assert optimization["expected_target_synchronizations"] == 0
    assert contract["collection"]["transition_limit"] == 10_012
    assert contract["r3k_prefix"]["transition_count"] == 10_008
    assert contract["fourth_update_boundary"]["new_transition_count"] == 4
    assert (
        contract["fourth_update_boundary"]["select_action_after_fourth_update"]
        is False
    )

    schedule = LinearEpsilonSchedule()
    assert [
        schedule.epsilon_at(count)
        for count in (10_008, 10_009, 10_010, 10_011)
    ] == [
        0.999928,
        0.999919,
        0.99991,
        0.999901,
    ]
    assert contract["epsilon_schedule"]["selection_count"] == 10_012
    assert contract["epsilon_schedule"]["decay_selection_count"] == 11
    assert contract["epsilon_schedule"][
        "last_selection_completed_transition_count"
    ] == 10_011
    assert "scheduled_epsilon_handoff" not in contract
    assert validate_contract(contract) == result_schema


def test_r3m_contract_rejects_a_drifted_r3k_binding() -> None:
    drifted = copy.deepcopy(_contract())
    drifted["base_third_update_contract"]["sha256"] = "0" * 64

    with pytest.raises(ValidationError):
        validate_contract(drifted)


def test_r3m_worker_registers_progress_and_extended_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    recorded: dict[str, Any] = {}

    def fake_execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        recorded.update(kwargs)
        return {}

    monkeypatch.setattr(
        "run_bdq_fourth_update_smoke.execute_update_gate_worker",
        fake_execute,
    )

    execute_worker(
        tmp_path / "player.exe",
        tmp_path / "output",
        0,
        _contract(),
    )

    assert recorded["timeout_wait"] == 300
    assert recorded["progress_interval"] == 1_000
    assert recorded["record_update_hashes"] is True


def _set_transition_limit(contract: dict[str, Any]) -> None:
    contract["collection"]["transition_limit"] = 10_013


def _remove_fourth_update(contract: dict[str, Any]) -> None:
    contract["optimization"]["expected_update_decisions"] = [
        10_000,
        10_004,
        10_008,
    ]


def _reset_selector_count(contract: dict[str, Any]) -> None:
    contract["epsilon_schedule"]["selection_count"] = 3


def _select_after_update(contract: dict[str, Any]) -> None:
    contract["fourth_update_boundary"]["select_action_after_fourth_update"] = True


@pytest.mark.parametrize(
    "mutate",
    [
        _set_transition_limit,
        _remove_fourth_update,
        _reset_selector_count,
        _select_after_update,
    ],
)
def test_r3m_contract_schema_rejects_boundary_drift(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    contract = copy.deepcopy(_contract())
    mutate(contract)

    with pytest.raises(ValidationError):
        validate_contract(contract)


def test_r3m_result_schema_freezes_the_no_handoff_cutoff() -> None:
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = schema["$defs"]["trace"]
    selector = trace["properties"]["selector"]["properties"]

    assert trace["properties"]["transitions"]["minItems"] == 10_012
    assert trace["properties"]["transitions"]["maxItems"] == 10_012
    assert trace["properties"]["optimization"]["properties"][
        "optimizer_update_count"
    ] == {"const": 4}
    assert selector["selection_count"] == {"const": 10_012}
    assert selector["last_selection_completed_transition_count"] == {
        "const": 10_011
    }
    assert "scheduled_epsilon_handoff" not in trace["required"]
    assert "scheduled_epsilon_handoff" not in trace["properties"]


def test_r3m_task_trace_validation_preserves_prefix_and_update_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = _task_trace(contract)
    monkeypatch.setattr(
        "run_bdq_fourth_update_smoke.validate_update_gate_trace",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "run_bdq_fourth_update_smoke.canonical_json_sha256",
        lambda value: contract["r3k_prefix"]["canonical_transitions_sha256"],
    )

    validate_trace(trace, result_schema)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda trace: trace["optimization"]["update_events"][0].__setitem__(
                "loss", 1.0
            ),
            "optimizer metric",
        ),
        (
            lambda trace: trace["optimization"]["update_events"][3].__setitem__(
                "online_after_sha256",
                trace["optimization"]["update_events"][2][
                    "online_after_sha256"
                ],
            ),
            "did not change",
        ),
        (
            lambda trace: trace["optimization"].__setitem__(
                "target_after_sha256", "2" * 64
            ),
            "frozen",
        ),
        (
            lambda trace: trace["selector"]["epsilon_samples"][0].__setitem__(
                "epsilon", 0.5
            ),
            "epsilon samples",
        ),
    ],
)
def test_r3m_task_trace_validation_rejects_drift(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    contract = _contract()
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = _task_trace(contract)
    monkeypatch.setattr(
        "run_bdq_fourth_update_smoke.validate_update_gate_trace",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "run_bdq_fourth_update_smoke.canonical_json_sha256",
        lambda value: contract["r3k_prefix"]["canonical_transitions_sha256"],
    )
    mutate(trace)

    with pytest.raises(LLAPIContractError, match=message):
        validate_trace(trace, result_schema)


def test_r3m_cli_separates_parent_worker_and_comparison_modes() -> None:
    parent = parse_arguments(
        ["--env", "player.exe", "--output", "r3m-acceptance"]
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
    comparison = parse_arguments(
        [
            "--output",
            "r3m-recovered-acceptance",
            "--first-trace",
            "attempt-1.json",
            "--second-trace",
            "attempt-2.json",
        ]
    )

    assert _execution_mode(parent) == "parent"
    assert _execution_mode(worker) == "worker"
    assert _execution_mode(comparison) == "compare"


def test_r3m_comparison_mode_requires_two_distinct_trace_files(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    _validate_distinct_trace_paths(first.resolve(), second.resolve())
    with pytest.raises(ValueError, match="two distinct trace files"):
        _validate_distinct_trace_paths(first.resolve(), first.resolve())

    incomplete = parse_arguments(
        ["--output", "r3m-acceptance", "--first-trace", str(first)]
    )
    with pytest.raises(ValueError, match="Trace-comparison mode"):
        _execution_mode(incomplete)
