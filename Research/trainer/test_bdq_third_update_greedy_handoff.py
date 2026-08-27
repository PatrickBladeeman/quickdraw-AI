from __future__ import annotations

import copy
import json
import math
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

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
    network_sha256,
)
from run_bdq_third_update_greedy_handoff_smoke import (  # noqa: E402
    _execution_mode,
    _masked_argmax,
    _validate_distinct_trace_paths,
    parse_arguments,
    sha256_file,
    validate_contract,
    validate_trace,
)
from run_bdq_warmup_update_smoke import (  # noqa: E402
    _complete_gate_transition,
    _registered_settings,
    _select_post_update_greedy_action,
)


CONTRACT_PATH = HERE / "bdq-third-update-greedy-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-greedy-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-greedy-handoff-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _observation(value: float) -> np.ndarray:
    return np.full((84, 84, 4), value, dtype=np.float32)


def _masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def _controller_after_three_updates() -> tuple[
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

    for index in range(6):
        collector.begin(
            0,
            _observation(index / 10.0),
            np.asarray([index % 3, index % 2], dtype=np.int64),
            _masks(),
        )
        result = _complete_gate_transition(
            collector,
            0,
            float(index - 2),
            _observation((index + 1) / 10.0),
            _masks(),
            terminated=False,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_update_decisions=(2, 4, 6),
            task_name="R3L",
        )
        if result.updated:
            events[-1]["online_after_sha256"] = network_sha256(
                controller.online_network
            )

    assert controller.decision_count == 6
    assert controller.optimizer_update_count == 3
    assert controller.target_sync_count == 0
    assert len(events) == 3
    assert collector.pending_agent_ids == ()
    return controller, events, target_before


def _task_trace(contract: dict[str, Any]) -> dict[str, Any]:
    prefix = contract["r3k_prefix"]
    schedule = contract["epsilon_schedule"]
    handoff_contract = contract["post_update_greedy_handoff"]
    update_specs = (
        (
            10_000,
            1,
            prefix["first_update_loss"],
            prefix["first_update_mean_absolute_td_error"],
            prefix["online_after_first_update_sha256"],
        ),
        (
            10_004,
            2,
            prefix["second_update_loss"],
            prefix["second_update_mean_absolute_td_error"],
            prefix["online_after_second_update_sha256"],
        ),
        (
            10_008,
            3,
            prefix["third_update_loss"],
            prefix["third_update_mean_absolute_td_error"],
            prefix["online_after_third_update_sha256"],
        ),
    )
    events = [
        {
            "decision_count": decision_count,
            "replay_size": decision_count,
            "optimizer_update_count": update_count,
            "target_sync_count": 0,
            "updated": True,
            "target_synced": False,
            "loss": loss,
            "mean_absolute_td_error": td_error,
            "online_after_sha256": online_hash,
        }
        for decision_count, update_count, loss, td_error, online_hash in update_specs
    ]
    action_masks = copy.deepcopy(handoff_contract["expected_action_masks"])
    online_q = [[0.1, 100.0, 0.3], [0.4, 0.5]]
    target_q = [[0.0, 0.0, 0.0], [0.0, 0.0]]
    selected_action = [2, 1]
    final_transition = {
        "observation_sha256": handoff_contract["expected_observation_sha256"],
        "action_masks": action_masks,
        "action": selected_action,
    }
    transitions = [{} for _ in range(10_008)] + [final_transition]
    return {
        "transitions": transitions,
        "optimization": {
            "update_events": events,
            "online_after_sha256": prefix["online_after_third_update_sha256"],
            "target_before_sha256": prefix["frozen_target_sha256"],
            "target_after_sha256": prefix["frozen_target_sha256"],
        },
        "selector": {
            "selection_count": 10_009,
            "scheduled_selection_count": schedule["selection_count"],
            "post_update_greedy_selection_count": 1,
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
            "epsilon_samples": [
                {"completed_transition_count": count, "epsilon": epsilon}
                for count, epsilon in zip(
                    schedule["trace_sample_completed_transition_counts"],
                    schedule["trace_sample_epsilons"],
                )
            ],
        },
        "post_update_greedy_handoff": {
            "selection_after_decision_count": 10_008,
            "transition_index": 10_008,
            "episode_index": 215,
            "episode_decision_index": 47,
            "epsilon": 0.0,
            "optimizer_update_count": 3,
            "target_sync_count": 0,
            "online_sha256": prefix["online_after_third_update_sha256"],
            "target_sha256": prefix["frozen_target_sha256"],
            "observation_sha256": handoff_contract[
                "expected_observation_sha256"
            ],
            "action_masks": action_masks,
            "online_q_values": online_q,
            "target_q_values": target_q,
            "max_absolute_q_delta": 100.0,
            "selected_action": selected_action,
            "selected_action_legal": True,
            "masked_argmax_verified": True,
        },
    }


def test_r3l_contract_schemas_runtime_binding_and_boundaries_are_exact() -> None:
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

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    assert _registered_settings(settings) == {
        key: optimization[key] for key in _registered_settings(settings)
    }
    assert optimization["expected_update_decisions"] == [10_000, 10_004, 10_008]
    assert optimization["expected_optimizer_updates"] == 3
    assert optimization["expected_target_synchronizations"] == 0
    assert contract["r3k_prefix"]["transition_count"] == 10_008
    assert contract["collection"]["transition_limit"] == 10_009
    assert contract["epsilon_schedule"]["selection_count"] == 10_008
    assert contract["epsilon_schedule"][
        "last_selection_completed_transition_count"
    ] == 10_007
    handoff = contract["post_update_greedy_handoff"]
    assert handoff["selection_after_decision_count"] == 10_008
    assert handoff["completed_transition_index"] == 10_008
    assert handoff["required_optimizer_update_count"] == 3
    assert handoff["epsilon"] == 0.0
    assert LinearEpsilonSchedule().epsilon_at(10_008) == 0.999928
    assert handoff["production_epsilon_if_used"] == 0.999928
    assert validate_contract(contract) == result_schema


def test_r3l_contract_rejects_a_drifted_r3k_binding() -> None:
    drifted = copy.deepcopy(_contract())
    drifted["base_third_update_contract"]["sha256"] = "0" * 64

    with pytest.raises(ValidationError):
        validate_contract(drifted)


def _change_transition_limit(contract: dict[str, Any]) -> None:
    contract["collection"]["transition_limit"] = 10_010


def _remove_third_update(contract: dict[str, Any]) -> None:
    contract["optimization"]["expected_update_decisions"] = [10_000, 10_004]


def _change_scheduled_prefix(contract: dict[str, Any]) -> None:
    contract["collection"]["scheduled_transition_prefix"] = 10_009


def _change_greedy_count(contract: dict[str, Any]) -> None:
    contract["collection"]["post_update_greedy_transition_count"] = 2


def _change_handoff_update(contract: dict[str, Any]) -> None:
    contract["post_update_greedy_handoff"][
        "required_optimizer_update_count"
    ] = 2


def _change_handoff_epsilon(contract: dict[str, Any]) -> None:
    contract["post_update_greedy_handoff"]["epsilon"] = 0.1


@pytest.mark.parametrize(
    "mutate",
    [
        _change_transition_limit,
        _remove_third_update,
        _change_scheduled_prefix,
        _change_greedy_count,
        _change_handoff_update,
        _change_handoff_epsilon,
    ],
)
def test_r3l_contract_schema_rejects_boundary_drift(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    contract = copy.deepcopy(_contract())
    mutate(contract)

    with pytest.raises(ValidationError):
        validate_contract(contract)


def test_r3l_result_schema_freezes_mixed_selector_and_handoff_cutoff() -> None:
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = schema["$defs"]["trace"]
    selector = trace["properties"]["selector"]["properties"]
    handoff = schema["$defs"]["handoff"]

    assert trace["properties"]["transitions"]["minItems"] == 10_009
    assert trace["properties"]["transitions"]["maxItems"] == 10_009
    assert trace["properties"]["optimization"]["properties"][
        "optimizer_update_count"
    ] == {"const": 3}
    assert trace["properties"]["optimization"]["properties"][
        "target_sync_count"
    ] == {"const": 0}
    assert selector["selection_count"] == {"const": 10_009}
    assert selector["scheduled_selection_count"] == {"const": 10_008}
    assert selector["post_update_greedy_selection_count"] == {"const": 1}
    assert selector["last_selection_completed_transition_count"] == {
        "const": 10_007
    }
    assert "post_update_greedy_handoff" in trace["required"]
    assert handoff["properties"]["transition_index"] == {"const": 10_008}
    assert handoff["properties"]["optimizer_update_count"] == {"const": 3}
    assert "online_q_values" in handoff["required"]
    assert "target_q_values" in handoff["required"]


def test_r3l_handoff_uses_update_3_online_network_and_legal_argmax() -> None:
    controller, events, target_before = _controller_after_three_updates()
    action_masks = (
        np.asarray([False, True, False], dtype=np.bool_),
        np.asarray([False, False], dtype=np.bool_),
    )

    action, evidence = _select_post_update_greedy_action(
        controller,
        _observation(0.75),
        action_masks,
        handoff_contract={
            "selection_after_decision_count": 6,
            "required_optimizer_update_count": 3,
            "epsilon": 0.0,
        },
        optimization_events=events,
        target_before_sha256=target_before,
        episode_index=2,
        episode_decision_index=7,
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
    assert evidence["optimizer_update_count"] == 3
    assert evidence["online_sha256"] == events[-1]["online_after_sha256"]
    assert evidence["target_sha256"] == target_before
    assert evidence["max_absolute_q_delta"] > 0.0
    assert action[0] != 1


def test_r3l_handoff_rejects_the_wrong_optimizer_boundary() -> None:
    controller, events, target_before = _controller_after_three_updates()

    with pytest.raises(LLAPIContractError, match="wrong optimizer count"):
        _select_post_update_greedy_action(
            controller,
            _observation(0.75),
            _masks(),
            handoff_contract={
                "selection_after_decision_count": 6,
                "required_optimizer_update_count": 2,
                "epsilon": 0.0,
            },
            optimization_events=events,
            target_before_sha256=target_before,
            episode_index=0,
            episode_decision_index=6,
        )


def test_r3l_task_trace_validation_accepts_exact_prefix_and_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = _task_trace(contract)
    monkeypatch.setattr(
        "run_bdq_third_update_greedy_handoff_smoke.validate_update_gate_trace",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "run_bdq_third_update_greedy_handoff_smoke.canonical_json_sha256",
        lambda value: contract["r3k_prefix"]["canonical_transitions_sha256"],
    )

    validate_trace(trace, result_schema)


def _change_update_3_metric(trace: dict[str, Any]) -> None:
    trace["optimization"]["update_events"][2]["loss"] = 1.0


def _change_target(trace: dict[str, Any]) -> None:
    trace["optimization"]["target_after_sha256"] = "0" * 64


def _change_schedule_sample(trace: dict[str, Any]) -> None:
    trace["selector"]["epsilon_samples"][-1]["epsilon"] = 0.5


def _consume_schedule_at_handoff(trace: dict[str, Any]) -> None:
    trace["selector"]["scheduled_selection_count"] = 10_009


def _change_handoff_state(trace: dict[str, Any]) -> None:
    trace["post_update_greedy_handoff"]["observation_sha256"] = "0" * 64


def _change_handoff_to_non_argmax(trace: dict[str, Any]) -> None:
    trace["post_update_greedy_handoff"]["selected_action"] = [0, 1]
    trace["transitions"][10_008]["action"] = [0, 1]


def _make_handoff_q_nonfinite(trace: dict[str, Any]) -> None:
    trace["post_update_greedy_handoff"]["online_q_values"][0][0] = math.nan


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_change_update_3_metric, "optimizer metric"),
        (_change_target, "frozen"),
        (_change_schedule_sample, "epsilon samples"),
        (_consume_schedule_at_handoff, "scheduled selector count"),
        (_change_handoff_state, "continue from R3K"),
        (_change_handoff_to_non_argmax, "masked online argmax"),
        (_make_handoff_q_nonfinite, "non-finite Q-value"),
    ],
)
def test_r3l_task_trace_validation_rejects_evidence_drift(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    contract = _contract()
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = _task_trace(contract)
    monkeypatch.setattr(
        "run_bdq_third_update_greedy_handoff_smoke.validate_update_gate_trace",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "run_bdq_third_update_greedy_handoff_smoke.canonical_json_sha256",
        lambda value: contract["r3k_prefix"]["canonical_transitions_sha256"],
    )
    mutate(trace)

    with pytest.raises(LLAPIContractError, match=message):
        validate_trace(trace, result_schema)


def test_r3l_task_trace_validation_rejects_prefix_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    trace = _task_trace(contract)
    monkeypatch.setattr(
        "run_bdq_third_update_greedy_handoff_smoke.validate_update_gate_trace",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "run_bdq_third_update_greedy_handoff_smoke.canonical_json_sha256",
        lambda value: "0" * 64,
    )

    with pytest.raises(LLAPIContractError, match="canonical R3K prefix"):
        validate_trace(trace, result_schema)


def test_r3l_cli_separates_parent_worker_and_comparison_modes() -> None:
    parent = parse_arguments(
        ["--env", "player.exe", "--output", "r3l-acceptance"]
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
            "r3l-recovered-acceptance",
            "--first-trace",
            "attempt-1.json",
            "--second-trace",
            "attempt-2.json",
        ]
    )

    assert _execution_mode(parent) == "parent"
    assert _execution_mode(worker) == "worker"
    assert _execution_mode(comparison) == "compare"


def test_r3l_comparison_mode_requires_two_distinct_trace_files(
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
        ["--output", "r3l-acceptance", "--first-trace", str(first)]
    )
    with pytest.raises(ValueError, match="Trace-comparison mode"):
        _execution_mode(incomplete)
