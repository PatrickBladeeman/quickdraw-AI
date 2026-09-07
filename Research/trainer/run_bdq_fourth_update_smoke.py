from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    LLAPIContractError,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    PYPROJECT_PATH,
    load_bound_contract,
    validate_runtime_and_package,
    validate_schema_pair,
)
from quickdraw_bdq.trajectory_validation import (  # noqa: E402
    validate_continuation_boundary,
    validate_continuous_schedule,
    validate_inherited_fields,
    validate_scheduled_optimization,
    validate_scheduled_update_trace,
    validate_player_execution,
)
from quickdraw_bdq.trajectory_runner import TrajectoryGate, run_trajectory  # noqa: E402
from quickdraw_bdq.update_gate import (  # noqa: E402
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-fourth-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-fourth-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-fourth-update-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3m-fourth-update-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-fourth-update-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-fourth-update-smoke-result.v1"


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3M",
    description="Run two fresh continuous scheduled-epsilon collections through the fourth production optimizer update.",
    cli="comparison",
    timeout_wait=300,
    progress_interval=1_000,
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_third_update_contract"]
    base_contract = load_bound_contract(
        binding,
        schema_error="R3M's R3K schema binding drifted.",
        repo_root=REPO_ROOT,
    )

    validate_runtime_and_package(contract, "R3M", pyproject_path=PYPROJECT_PATH)
    validate_inherited_fields(
        contract,
        base_contract,
        ("runtime", "package", "transport"),
        context="R3M",
        base_name="R3K",
    )

    validate_player_execution(
        contract["player_execution"],
        repo_root=REPO_ROOT,
        task_name="R3M",
    )

    validate_scheduled_optimization(
        contract,
        base_contract,
        task_name="R3M",
        base_name="R3K",
        update_count=4,
    )
    collection = contract["collection"]

    validate_continuous_schedule(
        contract,
        base_contract,
        task_name="R3M",
        base_name="R3K",
        update_count=4,
    )

    prefix = contract["r3k_prefix"]
    if prefix["transition_count"] != base_contract["collection"][
        "transition_limit"
    ]:
        raise LLAPIContractError("R3M prefix does not contain all of R3K.")
    validate_inherited_fields(
        prefix,
        base_contract["r3j_prefix"],
        (
            "online_after_first_update_sha256",
            "online_after_second_update_sha256",
            "frozen_target_sha256",
            "first_update_loss",
            "first_update_mean_absolute_td_error",
            "second_update_loss",
            "second_update_mean_absolute_td_error",
        ),
        context="R3M prefix",
        base_name="R3K",
    )
    if prefix["online_after_third_update_sha256"] == prefix[
        "online_after_second_update_sha256"
    ]:
        raise LLAPIContractError("R3M's R3K prefix omits update 3.")

    validate_continuation_boundary(
        contract["fourth_update_boundary"],
        prefix,
        collection,
        task_name="R3M",
        base_name="R3K",
        update_count=4,
        continuation_description="four",
        post_update_action_key="select_action_after_fourth_update",
    )
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3M",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_scheduled_update_trace(
        trace,
        contract["r3k_prefix"],
        contract["epsilon_schedule"],
        task_name="R3M",
        base_name="R3K",
        update_count=4,
    )


def print_summary(trace: Dict[str, Any]) -> None:
    updates = trace["optimization"]["update_events"]
    fourth_update = updates[3]
    print("fresh_processes=2")
    print("transitions=10012")
    print("scheduled_actions=10012")
    print("r3k_prefix_transitions=10008")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"truncation_events={len(trace['truncation_events'])}")
    print("pending_decisions=0")
    print("optimizer_updates=4")
    print("update_decisions=10000,10004,10008,10012")
    print("target_synchronizations=0")
    print(f"update_4_loss={fourth_update['loss']}")
    print(
        "update_4_mean_absolute_td_error="
        f"{fourth_update['mean_absolute_td_error']}"
    )
    print(f"update_4_online_sha256={fourth_update['online_after_sha256']}")
    print("r3k_prefix_preserved=pass")
    print("continuous_scheduled_selector=pass")
    print("fourth_update_online_weights_changed=pass")
    print("target_weights_unchanged=pass")
    print("no_post_update_action=pass")
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
