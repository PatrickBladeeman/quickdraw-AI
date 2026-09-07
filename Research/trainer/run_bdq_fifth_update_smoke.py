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
    UPDATE_PREFIX_FIELDS,
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


CONTRACT_PATH = HERE / "bdq-fifth-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-fifth-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-fifth-update-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3o-fifth-update-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-fifth-update-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-fifth-update-smoke-result.v1"


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3O",
    description="Run two fresh continuous scheduled-epsilon collections through the fifth production optimizer update.",
    cli="comparison",
    timeout_wait=300,
    progress_interval=1_000,
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_fourth_update_contract"]
    base_contract = load_bound_contract(
        binding,
        schema_error="R3O's R3M schema binding drifted.",
        repo_root=REPO_ROOT,
    )

    storage_binding = contract["base_replay_storage_contract"]
    storage_contract = load_bound_contract(
        storage_binding,
        schema_error="R3O's R3N schema binding drifted.",
        repo_root=REPO_ROOT,
    )
    storage_base = storage_contract["base_fourth_update_contract"]
    if (
        storage_base["path"] != binding["path"]
        or storage_base["sha256"] != binding["sha256"]
    ):
        raise LLAPIContractError("R3N does not bind R3O's active R3M contract.")

    validate_runtime_and_package(contract, "R3O", pyproject_path=PYPROJECT_PATH)
    validate_inherited_fields(
        contract,
        base_contract,
        ("runtime", "package", "transport"),
        context="R3O",
        base_name="R3M",
    )
    if (
        contract["runtime"] != storage_contract["runtime"]
        or contract["package"] != storage_contract["package"]
    ):
        raise LLAPIContractError("R3O differs from the R3N replay-storage boundary.")

    validate_player_execution(
        contract["player_execution"],
        repo_root=REPO_ROOT,
        task_name="R3O",
    )

    validate_scheduled_optimization(
        contract,
        base_contract,
        task_name="R3O",
        base_name="R3M",
        update_count=5,
    )
    collection = contract["collection"]

    validate_continuous_schedule(
        contract,
        base_contract,
        task_name="R3O",
        base_name="R3M",
        update_count=5,
    )

    prefix = contract["r3m_prefix"]
    if prefix["transition_count"] != base_contract["collection"][
        "transition_limit"
    ]:
        raise LLAPIContractError("R3O prefix does not contain all of R3M.")
    regression = storage_contract["r3m_regression"]
    if prefix["transition_count"] != regression["transition_count"]:
        raise LLAPIContractError("R3O prefix count differs from frozen R3N evidence.")
    if prefix["canonical_transitions_sha256"] != regression[
        "all_transitions_sha256"
    ]:
        raise LLAPIContractError(
            "R3O prefix transitions differ from frozen R3N evidence."
        )
    if prefix["source_canonical_trace_sha256"] != regression[
        "canonical_trace_sha256"
    ]:
        raise LLAPIContractError(
            "R3O prefix source trace differs from frozen R3N evidence."
        )
    for index, (hash_key, loss_key, td_error_key) in enumerate(UPDATE_PREFIX_FIELDS):
        if prefix[hash_key] != regression["online_hashes_after_updates"][index]:
            raise LLAPIContractError(f"R3O prefix {hash_key} differs from R3N.")
        if prefix[loss_key] != regression["update_losses"][index]:
            raise LLAPIContractError(f"R3O prefix {loss_key} differs from R3N.")
        if prefix[td_error_key] != regression["update_mean_absolute_td_errors"][
            index
        ]:
            raise LLAPIContractError(
                f"R3O prefix {td_error_key} differs from R3N."
            )
    validate_inherited_fields(
        prefix,
        base_contract["r3k_prefix"],
        (
            "online_after_first_update_sha256",
            "online_after_second_update_sha256",
            "online_after_third_update_sha256",
            "frozen_target_sha256",
            "first_update_loss",
            "first_update_mean_absolute_td_error",
            "second_update_loss",
            "second_update_mean_absolute_td_error",
            "third_update_loss",
            "third_update_mean_absolute_td_error",
        ),
        context="R3O prefix",
        base_name="R3M",
    )
    if prefix["online_after_fourth_update_sha256"] == prefix[
        "online_after_third_update_sha256"
    ]:
        raise LLAPIContractError("R3O's R3M prefix omits update 4.")

    validate_continuation_boundary(
        contract["fifth_update_boundary"],
        prefix,
        collection,
        task_name="R3O",
        base_name="R3M",
        update_count=5,
        continuation_description="four",
        post_update_action_key="select_action_after_fifth_update",
    )
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3O",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_scheduled_update_trace(
        trace,
        contract["r3m_prefix"],
        contract["epsilon_schedule"],
        task_name="R3O",
        base_name="R3M",
        update_count=5,
    )


def print_summary(trace: Dict[str, Any]) -> None:
    updates = trace["optimization"]["update_events"]
    fifth_update = updates[4]
    print("fresh_processes=2")
    print("transitions=10016")
    print("scheduled_actions=10016")
    print("r3m_prefix_transitions=10012")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"truncation_events={len(trace['truncation_events'])}")
    print("pending_decisions=0")
    print("optimizer_updates=5")
    print("update_decisions=10000,10004,10008,10012,10016")
    print("target_synchronizations=0")
    print(f"update_5_loss={fifth_update['loss']}")
    print(
        "update_5_mean_absolute_td_error="
        f"{fifth_update['mean_absolute_td_error']}"
    )
    print(f"update_5_online_sha256={fifth_update['online_after_sha256']}")
    print("r3m_prefix_preserved=pass")
    print("continuous_scheduled_selector=pass")
    print("fifth_update_online_weights_changed=pass")
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
