from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.provenance import sha256_file  # noqa: E402
from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    LLAPIContractError,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    PYPROJECT_PATH,
    masked_argmax as _masked_argmax,
    registered_settings as _registered_settings,
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


CONTRACT_PATH = HERE / "bdq-post-update-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-post-update-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-post-update-handoff-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3h-post-update-handoff-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-post-update-handoff-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-post-update-handoff-smoke-result.v1"


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3H",
    description="Run two fresh R3G-prefix collections followed by one post-update masked-greedy Unity transition.",
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_two_update_contract"]
    if sha256_file(REPO_ROOT / binding["path"]) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    validate_runtime_and_package(contract, "R3H", pyproject_path=PYPROJECT_PATH)

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3H differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions,
        (
            settings.replay_warmup_decisions
            + settings.optimizer_update_interval_decisions
        ),
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3H update decisions differ from R3G.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3H update count differs from R3G.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3H must not synchronize the target network.")

    collection = contract["collection"]
    prefix = contract["r3g_prefix"]
    handoff = contract["post_update_greedy_handoff"]
    if prefix["transition_count"] != expected_updates[-1]:
        raise LLAPIContractError("R3H prefix does not end at R3G update 2.")
    if collection["seeded_random_transition_prefix"] != prefix[
        "transition_count"
    ]:
        raise LLAPIContractError("R3H random prefix length differs from R3G.")
    if handoff["selection_after_decision_count"] != prefix["transition_count"]:
        raise LLAPIContractError("R3H greedy handoff does not follow R3G.")
    if handoff["completed_transition_index"] != prefix["transition_count"]:
        raise LLAPIContractError("R3H greedy transition index is not contiguous.")
    if handoff["required_optimizer_update_count"] != len(expected_updates):
        raise LLAPIContractError("R3H greedy handoff is not bound to update 2.")
    if handoff["epsilon"] != 0.0:
        raise LLAPIContractError("R3H handoff must be fully greedy.")
    if collection["post_update_greedy_transition_count"] != 1:
        raise LLAPIContractError("R3H must contain one greedy transition only.")
    if collection["transition_limit"] != prefix["transition_count"] + 1:
        raise LLAPIContractError("R3H cutoff does not complete one greedy action.")
    if (
        collection["transition_limit"]
        % settings.optimizer_update_interval_decisions
        == 0
    ):
        raise LLAPIContractError("R3H accidentally opens a third update.")
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3H",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    prefix_contract = contract["r3g_prefix"]
    prefix_count = validate_transition_prefix(
        trace["transitions"],
        prefix_contract,
        task_name="R3H",
        base_name="R3G",
    )

    optimization = trace["optimization"]
    events = optimization["update_events"]
    validate_prefix_updates(
        events,
        prefix_update_values(prefix_contract, 2),
        task_name="R3H",
        base_name="R3G",
    )
    if optimization["online_after_sha256"] != prefix_contract[
        "online_after_second_update_sha256"
    ]:
        raise LLAPIContractError("R3H final online hash differs from R3G update 2.")
    validate_frozen_target(
        optimization,
        prefix_contract,
        task_name="R3H",
        base_name="R3G",
    )

    selector = trace["selector"]
    if selector["seeded_random_selection_count"] != prefix_count:
        raise LLAPIContractError("R3H random selection count differs from R3G.")
    if selector["post_update_greedy_selection_count"] != 1:
        raise LLAPIContractError("R3H did not record one greedy selection.")

    handoff_contract = contract["post_update_greedy_handoff"]
    handoff = trace["post_update_greedy_handoff"]
    final_transition = trace["transitions"][handoff["transition_index"]]
    if handoff["selection_after_decision_count"] != handoff_contract[
        "selection_after_decision_count"
    ]:
        raise LLAPIContractError("R3H handoff opened at the wrong decision.")
    if handoff["transition_index"] != handoff_contract[
        "completed_transition_index"
    ]:
        raise LLAPIContractError("R3H handoff completed the wrong transition.")
    if handoff["online_sha256"] != events[-1]["online_after_sha256"]:
        raise LLAPIContractError("R3H handoff did not use the update-2 network.")
    if handoff["target_sha256"] != optimization["target_after_sha256"]:
        raise LLAPIContractError("R3H handoff did not use the frozen target.")
    if handoff["observation_sha256"] != final_transition[
        "observation_sha256"
    ]:
        raise LLAPIContractError("R3H handoff observation differs from replay.")
    if handoff["action_masks"] != final_transition["action_masks"]:
        raise LLAPIContractError("R3H handoff masks differ from replay.")
    if handoff["selected_action"] != final_transition["action"]:
        raise LLAPIContractError("R3H handoff action differs from replay.")

    online_q = handoff["online_q_values"]
    target_q = handoff["target_q_values"]
    flat_values = [
        value
        for branches in (online_q, target_q)
        for branch in branches
        for value in branch
    ]
    if not all(math.isfinite(value) for value in flat_values):
        raise LLAPIContractError("R3H handoff contains a non-finite Q-value.")
    maximum_delta = max(
        abs(online_value - target_value)
        for online_branch, target_branch in zip(online_q, target_q)
        for online_value, target_value in zip(online_branch, target_branch)
    )
    if maximum_delta <= 0.0 or not math.isclose(
        maximum_delta,
        handoff["max_absolute_q_delta"],
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise LLAPIContractError("R3H online and target Q evidence is inconsistent.")
    expected_action = [
        _masked_argmax(values, mask)
        for values, mask in zip(online_q, handoff["action_masks"])
    ]
    if handoff["selected_action"] != expected_action:
        raise LLAPIContractError("R3H action is not the masked online argmax.")
    if any(
        handoff["action_masks"][branch][action]
        for branch, action in enumerate(handoff["selected_action"])
    ):
        raise LLAPIContractError("R3H greedy handoff action is unavailable.")


def print_summary(trace: Dict[str, Any]) -> None:
    handoff = trace["post_update_greedy_handoff"]
    print("fresh_processes=2")
    print("transitions=10005")
    print("r3g_prefix_transitions=10004")
    print("seeded_random_actions=10004")
    print("post_update_greedy_actions=1")
    print(f"greedy_action={handoff['selected_action']}")
    print(f"max_absolute_q_delta={handoff['max_absolute_q_delta']}")
    print(f"online_sha256={handoff['online_sha256']}")
    print(f"target_sha256={handoff['target_sha256']}")
    print("pending_decisions=0")
    print("optimizer_updates=2")
    print("target_synchronizations=0")
    print("r3g_prefix_preserved=pass")
    print("masked_greedy_handoff=pass")
    print("online_target_q_divergence=pass")
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
