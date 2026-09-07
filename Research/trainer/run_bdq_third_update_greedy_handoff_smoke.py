from __future__ import annotations

import json
import math
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
    masked_argmax as _masked_argmax,
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
)
from quickdraw_bdq.trajectory_runner import TrajectoryGate, run_trajectory  # noqa: E402
from quickdraw_bdq.update_gate import (  # noqa: E402
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-third-update-greedy-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-greedy-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-greedy-handoff-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3l-third-update-greedy-handoff-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-third-update-greedy-handoff-trace.v1"
RESULT_SCHEMA_VERSION = (
    "quickdraw.bdq-third-update-greedy-handoff-smoke-result.v1"
)


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3L",
    description="Run two fresh R3K-prefix collections followed by one update-3 diagnostic masked-greedy Unity transition.",
    cli="comparison",
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_third_update_contract"]
    base_contract = load_bound_contract(
        binding,
        schema_error="R3L's R3K schema binding drifted.",
        repo_root=REPO_ROOT,
    )

    validate_runtime_and_package(contract, "R3L", pyproject_path=PYPROJECT_PATH)
    for key in ("runtime", "package", "transport", "optimization"):
        if contract[key] != base_contract[key]:
            raise LLAPIContractError(f"R3L {key} differs from R3K.")

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3L differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions
        + index * settings.optimizer_update_interval_decisions
        for index in range(3)
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3L update decisions differ from R3K.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3L must preserve exactly three updates.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3L must not synchronize the target network.")

    collection = contract["collection"]
    base_collection = base_contract["collection"]
    prefix = contract["r3k_prefix"]
    if prefix["transition_count"] != base_collection["transition_limit"]:
        raise LLAPIContractError("R3L prefix does not contain all of R3K.")
    if collection["scheduled_transition_prefix"] != prefix["transition_count"]:
        raise LLAPIContractError("R3L scheduled prefix length differs from R3K.")
    if collection["post_update_greedy_transition_count"] != 1:
        raise LLAPIContractError("R3L must contain one greedy transition only.")
    if collection["transition_limit"] != prefix["transition_count"] + 1:
        raise LLAPIContractError("R3L cutoff does not complete one greedy action.")
    next_update_decision = (
        expected_updates[-1] + settings.optimizer_update_interval_decisions
    )
    if collection["transition_limit"] >= next_update_decision:
        raise LLAPIContractError("R3L accidentally opens optimizer update 4.")
    for key in ("scenario_seed", "policy_seed", "exploration_seed"):
        if collection[key] != base_collection[key]:
            raise LLAPIContractError(f"R3L collection {key} differs from R3K.")

    schedule_contract = contract["epsilon_schedule"]
    if schedule_contract != base_contract["epsilon_schedule"]:
        raise LLAPIContractError("R3L scheduled prefix differs from R3K.")
    if schedule_contract["selection_count"] != prefix["transition_count"]:
        raise LLAPIContractError("R3L scheduled selection count differs from R3K.")
    if schedule_contract["last_selection_completed_transition_count"] != (
        prefix["transition_count"] - 1
    ):
        raise LLAPIContractError("R3L scheduled prefix selected after update 3.")

    base_prefix = base_contract["r3j_prefix"]
    for key in (
        "online_after_first_update_sha256",
        "online_after_second_update_sha256",
        "frozen_target_sha256",
        "first_update_loss",
        "first_update_mean_absolute_td_error",
        "second_update_loss",
        "second_update_mean_absolute_td_error",
    ):
        if prefix[key] != base_prefix[key]:
            raise LLAPIContractError(f"R3L prefix {key} differs from R3K.")

    handoff = contract["post_update_greedy_handoff"]
    if handoff["selection_after_decision_count"] != prefix["transition_count"]:
        raise LLAPIContractError("R3L greedy handoff does not follow R3K.")
    if handoff["completed_transition_index"] != prefix["transition_count"]:
        raise LLAPIContractError("R3L greedy transition index is not contiguous.")
    if handoff["required_optimizer_update_count"] != len(expected_updates):
        raise LLAPIContractError("R3L greedy handoff is not bound to update 3.")
    if handoff["epsilon"] != 0.0:
        raise LLAPIContractError("R3L diagnostic handoff must be fully greedy.")
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=schedule_contract["replay_warmup_decisions"],
        decay_decisions=schedule_contract["decay_decisions"],
        initial_epsilon=schedule_contract["initial_epsilon"],
        final_epsilon=schedule_contract["final_epsilon"],
    )
    production_epsilon = schedule.epsilon_at(prefix["transition_count"])
    if not math.isclose(
        production_epsilon,
        handoff["production_epsilon_if_used"],
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise LLAPIContractError("R3L production comparison epsilon drifted.")
    if not handoff["require_scheduled_selector_not_consumed"]:
        raise LLAPIContractError("R3L must not consume the scheduled selector.")
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3L",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    prefix = contract["r3k_prefix"]
    validate_transition_prefix(
        trace["transitions"],
        prefix,
        task_name="R3L",
        base_name="R3K",
    )

    optimization = trace["optimization"]
    events = optimization["update_events"]
    validate_prefix_updates(
        events,
        prefix_update_values(prefix, 3),
        task_name="R3L",
        base_name="R3K",
    )
    if optimization["online_after_sha256"] != prefix[
        "online_after_third_update_sha256"
    ]:
        raise LLAPIContractError("R3L final online hash differs from R3K update 3.")
    validate_frozen_target(
        optimization,
        prefix,
        task_name="R3L",
        base_name="R3K",
    )

    collection = contract["collection"]
    schedule_contract = contract["epsilon_schedule"]
    selector = trace["selector"]
    if selector["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3L total selector count drifted.")
    if selector["scheduled_selection_count"] != schedule_contract[
        "selection_count"
    ]:
        raise LLAPIContractError("R3L scheduled selector count drifted.")
    if selector["post_update_greedy_selection_count"] != 1:
        raise LLAPIContractError("R3L did not record one greedy selection.")
    expected_samples = [
        {"completed_transition_count": count, "epsilon": epsilon}
        for count, epsilon in zip(
            schedule_contract["trace_sample_completed_transition_counts"],
            schedule_contract["trace_sample_epsilons"],
        )
    ]
    if selector["epsilon_samples"] != expected_samples:
        raise LLAPIContractError("R3L scheduled epsilon samples drifted.")
    for key in (
        "full_exploration_selection_count",
        "decay_selection_count",
        "first_decay_completed_transition_count",
        "last_selection_completed_transition_count",
    ):
        if selector[key] != schedule_contract[key]:
            raise LLAPIContractError(f"R3L selector {key} drifted.")
    if selector["completed_transition_count_source"] != schedule_contract[
        "completed_transition_count_source"
    ]:
        raise LLAPIContractError("R3L selector counter source drifted.")

    handoff_contract = contract["post_update_greedy_handoff"]
    handoff = trace["post_update_greedy_handoff"]
    final_transition = trace["transitions"][handoff["transition_index"]]
    if handoff["selection_after_decision_count"] != handoff_contract[
        "selection_after_decision_count"
    ]:
        raise LLAPIContractError("R3L handoff opened at the wrong decision.")
    if handoff["transition_index"] != handoff_contract[
        "completed_transition_index"
    ]:
        raise LLAPIContractError("R3L handoff completed the wrong transition.")
    if handoff["epsilon"] != handoff_contract["epsilon"]:
        raise LLAPIContractError("R3L handoff was not diagnostic greedy.")
    if handoff["optimizer_update_count"] != handoff_contract[
        "required_optimizer_update_count"
    ]:
        raise LLAPIContractError("R3L handoff did not follow update 3.")
    if handoff["online_sha256"] != prefix["online_after_third_update_sha256"]:
        raise LLAPIContractError("R3L handoff did not use the update-3 network.")
    if handoff["target_sha256"] != prefix["frozen_target_sha256"]:
        raise LLAPIContractError("R3L handoff did not use the frozen target.")
    if handoff["observation_sha256"] != handoff_contract[
        "expected_observation_sha256"
    ]:
        raise LLAPIContractError("R3L handoff did not continue from R3K's state.")
    if handoff["action_masks"] != handoff_contract["expected_action_masks"]:
        raise LLAPIContractError("R3L handoff masks differ from the R3K boundary.")
    if handoff["observation_sha256"] != final_transition[
        "observation_sha256"
    ]:
        raise LLAPIContractError("R3L handoff observation differs from replay.")
    if handoff["action_masks"] != final_transition["action_masks"]:
        raise LLAPIContractError("R3L handoff masks differ from replay.")
    if handoff["selected_action"] != final_transition["action"]:
        raise LLAPIContractError("R3L handoff action differs from replay.")

    online_q = handoff["online_q_values"]
    target_q = handoff["target_q_values"]
    flat_values = [
        value
        for branches in (online_q, target_q)
        for branch in branches
        for value in branch
    ]
    if not all(math.isfinite(value) for value in flat_values):
        raise LLAPIContractError("R3L handoff contains a non-finite Q-value.")
    maximum_delta = max(
        abs(online_value - target_value)
        for online_branch, target_branch in zip(online_q, target_q)
        for online_value, target_value in zip(online_branch, target_branch)
    )
    if maximum_delta <= 0.0 or not math.isclose(
        maximum_delta,
        handoff["max_absolute_q_delta"],
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise LLAPIContractError("R3L online and target Q evidence is inconsistent.")
    expected_action = [
        _masked_argmax(values, mask)
        for values, mask in zip(online_q, handoff["action_masks"])
    ]
    if handoff["selected_action"] != expected_action:
        raise LLAPIContractError("R3L action is not the masked online argmax.")
    if any(
        handoff["action_masks"][branch][action]
        for branch, action in enumerate(handoff["selected_action"])
    ):
        raise LLAPIContractError("R3L greedy handoff action is unavailable.")


def print_summary(trace: Dict[str, Any]) -> None:
    handoff = trace["post_update_greedy_handoff"]
    print("fresh_processes=2")
    print("transitions=10009")
    print("r3k_prefix_transitions=10008")
    print("scheduled_actions=10008")
    print("post_update_greedy_actions=1")
    print(f"greedy_action={handoff['selected_action']}")
    print(f"max_absolute_q_delta={handoff['max_absolute_q_delta']}")
    print(f"online_sha256={handoff['online_sha256']}")
    print(f"target_sha256={handoff['target_sha256']}")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"truncation_events={len(trace['truncation_events'])}")
    print("pending_decisions=0")
    print("optimizer_updates=3")
    print("target_synchronizations=0")
    print("r3k_prefix_preserved=pass")
    print("scheduled_selector_not_consumed_at_handoff=pass")
    print("masked_greedy_handoff=pass")
    print("no_fourth_update=pass")
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
