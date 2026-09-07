from __future__ import annotations

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
    registered_settings as _registered_settings,
    validate_runtime_and_package,
    validate_schema_pair,
)
from quickdraw_bdq.trajectory_runner import TrajectoryGate, run_trajectory  # noqa: E402
from quickdraw_bdq.update_gate import (  # noqa: E402
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-two-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-two-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-two-update-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3g-two-update-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-two-update-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-two-update-smoke-result.v1"


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3G",
    description="Run two fresh fixed-epsilon Unity collections through the second production optimizer update.",
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_warmup_update_contract"]
    if sha256_file(REPO_ROOT / binding["path"]) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    validate_runtime_and_package(contract, "R3G", pyproject_path=PYPROJECT_PATH)

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3G differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions,
        (
            settings.replay_warmup_decisions
            + settings.optimizer_update_interval_decisions
        ),
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3G update decisions differ from its schedule.")
    if optimization["expected_first_update_decision"] != expected_updates[0]:
        raise LLAPIContractError("R3G first update differs from production warmup.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3G update count differs from its schedule.")
    if contract["collection"]["transition_limit"] != expected_updates[-1]:
        raise LLAPIContractError("R3G cutoff differs from its second update.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3G must not synchronize the target network.")
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3G",
        require_update_hashes=True,
    )


def print_summary(trace: Dict[str, Any]) -> None:
    updates = trace["optimization"]["update_events"]
    print("fresh_processes=2")
    print("transitions=10004")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"episode_resets={trace['episode_reset_count']}")
    print(f"unique_action_tuples={trace['selector']['unique_action_tuple_count']}")
    print("pending_decisions=0")
    print("optimizer_updates=2")
    print("update_decisions=10000,10004")
    print("target_synchronizations=0")
    for index, update in enumerate(updates, start=1):
        print(f"update_{index}_loss={update['loss']}")
        print(
            f"update_{index}_mean_absolute_td_error="
            f"{update['mean_absolute_td_error']}"
        )
        print(f"update_{index}_online_sha256={update['online_after_sha256']}")
    print("online_weights_changed_after_each_update=pass")
    print("target_weights_unchanged=pass")
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
