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
)
from quickdraw_bdq.trajectory_runner import TrajectoryGate, run_trajectory  # noqa: E402
from quickdraw_bdq.update_gate import (  # noqa: E402
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-third-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3k-third-update-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-third-update-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-third-update-smoke-result.v1"


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3K",
    description="Run two fresh continuous scheduled-epsilon collections through the third production optimizer update.",
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_scheduled_handoff_contract"]
    base_contract = load_bound_contract(
        binding,
        schema_error="R3K's R3J schema binding drifted.",
        repo_root=REPO_ROOT,
    )

    validate_runtime_and_package(contract, "R3K", pyproject_path=PYPROJECT_PATH)
    validate_inherited_fields(
        contract,
        base_contract,
        ("runtime", "package", "transport"),
        context="R3K",
        base_name="R3J",
    )

    validate_scheduled_optimization(
        contract,
        base_contract,
        task_name="R3K",
        base_name="R3J",
        update_count=3,
    )
    collection = contract["collection"]

    validate_continuous_schedule(
        contract,
        base_contract,
        task_name="R3K",
        base_name="R3J",
        update_count=3,
    )

    prefix = contract["r3j_prefix"]
    if prefix["transition_count"] != base_contract["collection"][
        "transition_limit"
    ]:
        raise LLAPIContractError("R3K prefix does not contain all of R3J.")
    validate_inherited_fields(
        prefix,
        base_contract["r3g_prefix"],
        (
            "online_after_first_update_sha256",
            "online_after_second_update_sha256",
            "frozen_target_sha256",
            "first_update_loss",
            "first_update_mean_absolute_td_error",
            "second_update_loss",
            "second_update_mean_absolute_td_error",
        ),
        context="R3K prefix",
        base_name="R3J",
    )

    validate_continuation_boundary(
        contract["third_update_boundary"],
        prefix,
        collection,
        task_name="R3K",
        base_name="R3J",
        update_count=3,
        continuation_description="three",
        post_update_action_key="select_action_after_third_update",
    )
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3K",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_scheduled_update_trace(
        trace,
        contract["r3j_prefix"],
        contract["epsilon_schedule"],
        task_name="R3K",
        base_name="R3J",
        update_count=3,
    )


def print_summary(trace: Dict[str, Any]) -> None:
    updates = trace["optimization"]["update_events"]
    third_update = updates[2]
    print("fresh_processes=2")
    print("transitions=10008")
    print("scheduled_actions=10008")
    print("r3j_prefix_transitions=10005")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"truncation_events={len(trace['truncation_events'])}")
    print("pending_decisions=0")
    print("optimizer_updates=3")
    print("update_decisions=10000,10004,10008")
    print("target_synchronizations=0")
    print(f"update_3_loss={third_update['loss']}")
    print(
        "update_3_mean_absolute_td_error="
        f"{third_update['mean_absolute_td_error']}"
    )
    print(f"update_3_online_sha256={third_update['online_after_sha256']}")
    print("r3j_prefix_preserved=pass")
    print("continuous_scheduled_selector=pass")
    print("third_update_online_weights_changed=pass")
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
