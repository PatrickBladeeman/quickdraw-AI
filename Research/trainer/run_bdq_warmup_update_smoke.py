from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.provenance import sha256_file  # noqa: E402
from quickdraw_bdq import BDQOptimizationSettings, LLAPIContractError  # noqa: E402
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


CONTRACT_PATH = HERE / "bdq-warmup-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-warmup-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-warmup-update-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3f-warmup-update-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-warmup-update-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-warmup-update-smoke-result.v1"


GATE = TrajectoryGate(
    runner_path=Path(__file__),
    contract_path=CONTRACT_PATH,
    trace_file_name=TRACE_FILE_NAME,
    trace_schema_version=TRACE_SCHEMA_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    task_name="R3F",
    description="Run the production BDQ warmup and first update twice, or run one diagnostic watch session.",
    cli="warmup",
    record_update_hashes=False,
    announce_workers=False,
)


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3F",
        require_update_hashes=False,
    )


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract,
        CONTRACT_SCHEMA_PATH,
        RESULT_SCHEMA_PATH,
    )
    binding = contract["base_epsilon_collection_contract"]
    if sha256_file(REPO_ROOT / binding["path"]) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    validate_runtime_and_package(contract, "R3F", pyproject_path=PYPROJECT_PATH)
    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3F differs from production optimizer defaults.")
    collection = contract["collection"]
    if collection["transition_limit"] != settings.replay_warmup_decisions:
        raise LLAPIContractError("R3F cutoff differs from production warmup.")
    if optimization["expected_first_update_decision"] != collection[
        "transition_limit"
    ]:
        raise LLAPIContractError("R3F update decision differs from its cutoff.")
    if (
        optimization["expected_first_update_decision"]
        % settings.optimizer_update_interval_decisions
        != 0
    ):
        raise LLAPIContractError("R3F warmup is not an optimizer-update boundary.")
    return result_schema


def print_summary(trace: Dict[str, Any]) -> None:
    update = trace["optimization"]["update_events"][0]
    print("fresh_processes=2")
    print("transitions=10000")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"episode_resets={trace['episode_reset_count']}")
    print(f"unique_action_tuples={trace['selector']['unique_action_tuple_count']}")
    print("pending_decisions=0")
    print("optimizer_updates=1")
    print("first_update_decision=10000")
    print("target_synchronizations=0")
    print(f"loss={update['loss']}")
    print(f"mean_absolute_td_error={update['mean_absolute_td_error']}")
    print("online_weights_changed=pass")
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
