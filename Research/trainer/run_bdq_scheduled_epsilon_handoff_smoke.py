from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    LLAPIContractError,
    LinearEpsilonSchedule,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    PYPROJECT_PATH,
    registered_settings as _registered_settings,
    load_bound_contract,
    validate_runtime_and_package,
    validate_schema_pair,
)
from quickdraw_bdq.trajectory_validation import (  # noqa: E402
    prefix_update_values,
    validate_frozen_target,
    validate_prefix_updates,
    validate_transition_prefix,
    validate_scheduled_selector,
)
from quickdraw_bdq.trajectory_runner import TrajectoryGate, run_trajectory  # noqa: E402
from quickdraw_bdq.update_gate import (  # noqa: E402
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-scheduled-epsilon-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-scheduled-epsilon-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-scheduled-epsilon-handoff-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3j-scheduled-epsilon-handoff-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-scheduled-epsilon-handoff-trace.v1"
RESULT_SCHEMA_VERSION = (
    "quickdraw.bdq-scheduled-epsilon-handoff-smoke-result.v1"
)


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3J",
    description="Run two fresh continuous scheduled-epsilon collections through one live action after the second optimizer update.",
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    schedule_binding = contract["base_epsilon_schedule_contract"]
    base_schedule_contract = load_bound_contract(
        schedule_binding,
        schema_error="R3J's R3I schema binding drifted.",
        repo_root=REPO_ROOT,
    )

    prefix_binding = contract["live_prefix_source_contract"]
    prefix_contract = load_bound_contract(
        prefix_binding,
        schema_error="R3J's R3H schema binding drifted.",
        repo_root=REPO_ROOT,
    )
    inherited_section = prefix_binding["inherited_section"]
    if prefix_contract[inherited_section] != contract["r3g_prefix"]:
        raise LLAPIContractError("R3J's registered R3G prefix drifted from R3H.")

    validate_runtime_and_package(contract, "R3J", pyproject_path=PYPROJECT_PATH)

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3J differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions,
        settings.replay_warmup_decisions
        + settings.optimizer_update_interval_decisions,
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3J update decisions differ from R3G.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3J update count differs from R3G.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3J must not synchronize the target network.")

    schedule_contract = contract["epsilon_schedule"]
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=schedule_contract["replay_warmup_decisions"],
        decay_decisions=schedule_contract["decay_decisions"],
        initial_epsilon=schedule_contract["initial_epsilon"],
        final_epsilon=schedule_contract["final_epsilon"],
    )
    if schedule_contract["replay_warmup_decisions"] != (
        base_schedule_contract["schedule"]["replay_warmup_decisions"]
    ):
        raise LLAPIContractError("R3J warmup differs from R3I.")
    if schedule_contract["decay_decisions"] != base_schedule_contract[
        "schedule"
    ]["decay_decisions"]:
        raise LLAPIContractError("R3J decay length differs from R3I.")
    sample_counts = schedule_contract[
        "trace_sample_completed_transition_counts"
    ]
    expected_sample_epsilons = [
        schedule.epsilon_at(count) for count in sample_counts
    ]
    if schedule_contract["trace_sample_epsilons"] != expected_sample_epsilons:
        raise LLAPIContractError("R3J epsilon samples differ from its schedule.")

    collection = contract["collection"]
    handoff = contract["scheduled_epsilon_handoff"]
    prefix = contract["r3g_prefix"]
    if prefix["transition_count"] != expected_updates[-1]:
        raise LLAPIContractError("R3J prefix does not end at R3G update 2.")
    if handoff["selection_after_decision_count"] != prefix["transition_count"]:
        raise LLAPIContractError("R3J handoff does not immediately follow R3G.")
    if handoff["completed_transition_index"] != prefix["transition_count"]:
        raise LLAPIContractError("R3J handoff transition index is not contiguous.")
    if handoff["selection_ordinal"] != prefix["transition_count"]:
        raise LLAPIContractError("R3J selector lifetime was reset at handoff.")
    if handoff["required_optimizer_update_count"] != len(expected_updates):
        raise LLAPIContractError("R3J handoff is not bound to update 2.")
    expected_handoff_epsilon = schedule.epsilon_at(
        handoff["selection_after_decision_count"]
    )
    if handoff["epsilon"] != expected_handoff_epsilon:
        raise LLAPIContractError("R3J handoff epsilon differs from R3I.")
    if collection["transition_limit"] != prefix["transition_count"] + 1:
        raise LLAPIContractError("R3J must complete exactly one new transition.")
    if collection["scheduled_transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3J must schedule every collected action.")
    if schedule_contract["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3J schedule count differs from its cutoff.")
    if schedule_contract["full_exploration_selection_count"] != (
        schedule.replay_warmup_decisions + 1
    ):
        raise LLAPIContractError("R3J full-exploration selection count drifted.")
    if schedule_contract["decay_selection_count"] != (
        collection["transition_limit"]
        - schedule_contract["full_exploration_selection_count"]
    ):
        raise LLAPIContractError("R3J decay selection count drifted.")
    if collection["transition_limit"] % (
        settings.optimizer_update_interval_decisions
    ) == 0:
        raise LLAPIContractError("R3J accidentally opens a third update.")
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3J",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    prefix = contract["r3g_prefix"]
    validate_transition_prefix(
        trace["transitions"],
        prefix,
        task_name="R3J",
        base_name="R3G",
    )

    optimization = trace["optimization"]
    events = optimization["update_events"]
    validate_prefix_updates(
        events,
        prefix_update_values(prefix, 2),
        task_name="R3J",
        base_name="R3G",
    )
    if optimization["online_after_sha256"] != prefix[
        "online_after_second_update_sha256"
    ]:
        raise LLAPIContractError("R3J final online hash differs from R3G update 2.")
    validate_frozen_target(
        optimization,
        prefix,
        task_name="R3J",
        base_name="R3G",
    )

    validate_scheduled_selector(
        trace["selector"],
        contract["epsilon_schedule"],
        task_name="R3J",
    )

    handoff_contract = contract["scheduled_epsilon_handoff"]
    handoff = trace["scheduled_epsilon_handoff"]
    final_transition = trace["transitions"][handoff["transition_index"]]
    if handoff["selection_after_decision_count"] != handoff_contract[
        "selection_after_decision_count"
    ]:
        raise LLAPIContractError("R3J handoff opened at the wrong decision.")
    if handoff["selection_ordinal"] != handoff_contract["selection_ordinal"]:
        raise LLAPIContractError("R3J scheduled selector was not continuous.")
    if handoff["epsilon"] != handoff_contract["epsilon"]:
        raise LLAPIContractError("R3J handoff recorded the wrong epsilon.")
    if handoff["online_sha256"] != events[-1]["online_after_sha256"]:
        raise LLAPIContractError("R3J handoff did not use the update-2 network.")
    if handoff["target_sha256"] != optimization["target_after_sha256"]:
        raise LLAPIContractError("R3J handoff did not observe the frozen target.")
    if handoff["observation_sha256"] != final_transition[
        "observation_sha256"
    ]:
        raise LLAPIContractError("R3J handoff observation differs from replay.")
    if handoff["action_masks"] != final_transition["action_masks"]:
        raise LLAPIContractError("R3J handoff masks differ from replay.")
    if handoff["selected_action"] != final_transition["action"]:
        raise LLAPIContractError("R3J handoff action differs from replay.")
    if handoff["observation_sha256"] != handoff_contract[
        "expected_observation_sha256"
    ]:
        raise LLAPIContractError("R3J handoff observed an unexpected live state.")
    if handoff["action_masks"] != handoff_contract["expected_action_masks"]:
        raise LLAPIContractError("R3J handoff action masks drifted.")
    if handoff["selected_action"] != handoff_contract[
        "expected_selected_action"
    ]:
        raise LLAPIContractError("R3J continuous selector action drifted.")
    if any(
        handoff["action_masks"][branch][action]
        for branch, action in enumerate(handoff["selected_action"])
    ):
        raise LLAPIContractError("R3J handoff selected an unavailable action.")


def print_summary(trace: Dict[str, Any]) -> None:
    handoff = trace["scheduled_epsilon_handoff"]
    print("fresh_processes=2")
    print("transitions=10005")
    print("scheduled_actions=10005")
    print("r3g_prefix_transitions=10004")
    print(f"scheduled_handoff_epsilon={handoff['epsilon']}")
    print(f"scheduled_handoff_action={handoff['selected_action']}")
    print("pending_decisions=0")
    print("optimizer_updates=2")
    print("target_synchronizations=0")
    print("r3g_prefix_preserved=pass")
    print("continuous_scheduled_selector=pass")
    print("scheduled_handoff_legal=pass")
    print("exact_trace_equality=pass")


def main() -> int:
    return run_trajectory(
        GATE,
        validate_contract=validate_contract,
        validate_trace=validate_trace,
        summarize=print_summary,
    )


if __name__ == "__main__":
    raise SystemExit(main())
