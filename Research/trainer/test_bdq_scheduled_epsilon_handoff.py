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
    DuelingBranchingQNetwork,
    LLAPIContractError,
    LinearEpsilonSchedule,
    ScheduledEpsilonGreedyBDQActionSelector,
    network_sha256,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    canonical_json_sha256,
    registered_settings as _registered_settings,
    sha256_file,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    _complete_gate_transition,
    _select_scheduled_epsilon_handoff_action,
)
from run_bdq_scheduled_epsilon_handoff_smoke import (  # noqa: E402
    _execution_mode,
    parse_arguments,
    validate_contract,
)


CONTRACT_PATH = HERE / "bdq-scheduled-epsilon-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-scheduled-epsilon-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-scheduled-epsilon-handoff-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def observation(value: float = 0.25) -> np.ndarray:
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
            task_name="R3J",
        )
        if result.updated:
            events[-1]["online_after_sha256"] = network_sha256(
                controller.online_network
            )

    assert controller.decision_count == 4
    assert controller.optimizer_update_count == 2
    assert controller.target_sync_count == 0
    return controller, events, target_before


class RecordingScheduledSelector:
    def __init__(self, schedule: LinearEpsilonSchedule) -> None:
        self.schedule = schedule
        self.completed_transition_counts: list[int] = []

    def select(
        self,
        value: np.ndarray,
        action_masks: tuple[np.ndarray, np.ndarray],
        *,
        completed_transition_count: int,
    ) -> np.ndarray:
        del value, action_masks
        self.completed_transition_counts.append(completed_transition_count)
        return np.asarray([0, 0], dtype=np.int64)


def test_r3j_contract_schema_bindings_runtime_and_schedule_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    for binding_name in (
        "base_epsilon_schedule_contract",
        "live_prefix_source_contract",
    ):
        binding = contract[binding_name]
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
    schedule = LinearEpsilonSchedule()
    assert schedule.epsilon_at(10_004) == 0.999964
    assert contract["epsilon_schedule"]["selection_count"] == 10_005
    assert contract["epsilon_schedule"][
        "full_exploration_selection_count"
    ] == 10_001
    assert contract["epsilon_schedule"]["decay_selection_count"] == 4
    assert contract["scheduled_epsilon_handoff"]["epsilon"] == (
        schedule.epsilon_at(10_004)
    )
    assert contract["scheduled_epsilon_handoff"][
        "expected_selected_action"
    ] == [0, 0]
    assert validate_contract(contract) == result_schema


@pytest.mark.parametrize(
    "binding_name",
    ["base_epsilon_schedule_contract", "live_prefix_source_contract"],
)
def test_r3j_contract_rejects_binding_drift(binding_name: str) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    drifted = copy.deepcopy(contract)
    drifted[binding_name]["sha256"] = "0" * 64

    with pytest.raises(ValidationError):
        validate_contract(drifted)


def test_r3j_contract_rejects_counter_or_epsilon_drift() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(contract_schema)

    wrong_count = copy.deepcopy(contract)
    wrong_count["scheduled_epsilon_handoff"][
        "selection_after_decision_count"
    ] = 10_003
    with pytest.raises(ValidationError):
        validator.validate(wrong_count)

    wrong_epsilon = copy.deepcopy(contract)
    wrong_epsilon["scheduled_epsilon_handoff"]["epsilon"] = 1.0
    with pytest.raises(ValidationError):
        validator.validate(wrong_epsilon)


def test_scheduled_handoff_passes_the_controller_count_and_preserves_masks() -> None:
    controller, events, target_before = controller_after_two_updates()
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=2,
        decay_decisions=100,
    )
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        controller.online_network,
        schedule=schedule,
        seed=61001,
    )
    action_masks = (
        np.asarray([False, True, False], dtype=np.bool_),
        np.asarray([False, False], dtype=np.bool_),
    )

    action, evidence = _select_scheduled_epsilon_handoff_action(
        controller,
        selector,
        observation(0.45),
        action_masks,
        handoff_contract={
            "selection_after_decision_count": 4,
            "required_optimizer_update_count": 2,
            "completed_transition_count_source": (
                "BDQOptimizerController.decision_count"
            ),
            "epsilon": schedule.epsilon_at(4),
        },
        optimization_events=events,
        target_before_sha256=target_before,
        episode_index=3,
        episode_decision_index=17,
    )

    assert evidence["selection_after_decision_count"] == 4
    assert evidence["transition_index"] == 4
    assert evidence["selection_ordinal"] == 4
    assert evidence["epsilon"] == schedule.epsilon_at(controller.decision_count)
    assert evidence["optimizer_update_count"] == 2
    assert evidence["target_sync_count"] == 0
    assert evidence["online_sha256"] == events[-1]["online_after_sha256"]
    assert evidence["target_sha256"] == target_before
    assert evidence["selected_action"] == action.tolist()
    assert evidence["selected_action_legal"] is True
    assert action[0] != 1


def test_scheduled_handoff_uses_controller_count_without_copy_state() -> None:
    controller, events, target_before = controller_after_two_updates()
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=2,
        decay_decisions=100,
    )
    selector = RecordingScheduledSelector(schedule)

    action, evidence = _select_scheduled_epsilon_handoff_action(
        controller,
        selector,  # type: ignore[arg-type]
        observation(),
        masks(),
        handoff_contract={
            "selection_after_decision_count": 4,
            "required_optimizer_update_count": 2,
            "completed_transition_count_source": (
                "BDQOptimizerController.decision_count"
            ),
            "epsilon": schedule.epsilon_at(4),
            "expected_selected_action": [0, 0],
        },
        optimization_events=events,
        target_before_sha256=target_before,
        episode_index=0,
        episode_decision_index=4,
    )

    assert selector.completed_transition_counts == [controller.decision_count]
    assert evidence["selection_after_decision_count"] == controller.decision_count
    assert action.tolist() == [0, 0]


def test_scheduled_handoff_rejects_wrong_epsilon_or_changed_target() -> None:
    controller, events, target_before = controller_after_two_updates()
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        controller.online_network,
        schedule=LinearEpsilonSchedule(
            replay_warmup_decisions=2,
            decay_decisions=100,
        ),
        seed=61001,
    )
    handoff = {
        "selection_after_decision_count": 4,
        "required_optimizer_update_count": 2,
        "completed_transition_count_source": "BDQOptimizerController.decision_count",
        "epsilon": 1.0,
    }

    with pytest.raises(LLAPIContractError, match="wrong epsilon"):
        _select_scheduled_epsilon_handoff_action(
            controller,
            selector,
            observation(),
            masks(),
            handoff_contract=handoff,
            optimization_events=events,
            target_before_sha256=target_before,
            episode_index=0,
            episode_decision_index=4,
        )

    handoff["epsilon"] = selector.schedule.epsilon_at(4)
    with pytest.raises(LLAPIContractError, match="changed target"):
        _select_scheduled_epsilon_handoff_action(
            controller,
            selector,
            observation(),
            masks(),
            handoff_contract=handoff,
            optimization_events=events,
            target_before_sha256="0" * 64,
            episode_index=0,
            episode_decision_index=4,
        )


def test_continuous_selector_state_produces_registered_handoff_action() -> None:
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        DuelingBranchingQNetwork(),
        schedule=LinearEpsilonSchedule(),
        seed=61001,
    )
    all_available = masks()
    for completed_transition_count in range(10_004):
        selector.select(
            observation(),
            all_available,
            completed_transition_count=completed_transition_count,
        )

    final_action = selector.select(
        observation(),
        (
            np.asarray([False, True, False], dtype=np.bool_),
            np.asarray([False, False], dtype=np.bool_),
        ),
        completed_transition_count=10_004,
    )
    fresh_selector = ScheduledEpsilonGreedyBDQActionSelector(
        DuelingBranchingQNetwork(),
        schedule=LinearEpsilonSchedule(),
        seed=61001,
    )
    reset_action = fresh_selector.select(
        observation(),
        (
            np.asarray([False, True, False], dtype=np.bool_),
            np.asarray([False, False], dtype=np.bool_),
        ),
        completed_transition_count=10_004,
    )

    assert final_action.tolist() == [0, 0]
    assert reset_action.tolist() == [2, 1]


def test_r3j_handoff_schema_requires_schedule_evidence() -> None:
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    handoff_schema = {
        **result_schema["$defs"]["handoff"],
        "$defs": result_schema["$defs"],
    }
    handoff = {
        "selection_after_decision_count": 10_004,
        "transition_index": 10_004,
        "selection_ordinal": 10_004,
        "episode_index": 0,
        "episode_decision_index": 0,
        "completed_transition_count_source": (
            "BDQOptimizerController.decision_count"
        ),
        "epsilon": 0.999964,
        "optimizer_update_count": 2,
        "target_sync_count": 0,
        "online_sha256": (
            "6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471"
        ),
        "target_sha256": (
            "b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb"
        ),
        "observation_sha256": (
            "8d10e324956e2d5b7b8a7d70da58d33a9b170598727998146dcfec858bab8a83"
        ),
        "action_masks": [[False, True, False], [False, False]],
        "selected_action": [0, 0],
        "selected_action_legal": True,
    }

    Draft202012Validator(handoff_schema).validate(handoff)
    handoff.pop("completed_transition_count_source")
    with pytest.raises(ValidationError):
        Draft202012Validator(handoff_schema).validate(handoff)


def test_canonical_json_sha256_ignores_object_key_order() -> None:
    first = [{"index": 0, "action": [0, 0]}]
    second = [{"action": [0, 0], "index": 0}]

    assert canonical_json_sha256(first) == canonical_json_sha256(second)


def test_r3j_cli_separates_parent_and_worker_modes() -> None:
    parent = parse_arguments(
        ["--env", "player.exe", "--output", "r3j-acceptance"]
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
