from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    LLAPIContractError,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    PYPROJECT_PATH,
    registered_settings as _registered_settings,
    run_fresh_worker_process,
    sha256_file,
    standard_execution_mode as _execution_mode,
    validate_runtime_and_package,
    validate_schema_pair,
    write_two_process_result,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    execute_update_gate_worker,
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


def execute_worker(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    return execute_update_gate_worker(
        executable,
        worker_output,
        worker_index,
        contract,
        contract_path=CONTRACT_PATH,
        trace_file_name=TRACE_FILE_NAME,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        task_name="R3G",
        record_update_hashes=True,
    )


def run_fresh_worker(
    executable: Path,
    output_directory: Path,
    worker_index: int,
    contract: Dict[str, Any],
) -> tuple[Dict[str, Any], Path]:
    return run_fresh_worker_process(
        runner_path=Path(__file__),
        executable=executable,
        output_directory=output_directory,
        worker_index=worker_index,
        contract=contract,
        trace_file_name=TRACE_FILE_NAME,
        task_name="R3G",
        announce=True,
        repo_root=REPO_ROOT,
        timeout_seconds=1800,
    )


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run two fresh fixed-epsilon Unity collections through the second "
            "production optimizer update."
        )
    )
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)




def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    executable = arguments.env.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result_schema = validate_contract(contract)

    if mode == "worker":
        assert arguments.worker_output is not None
        assert arguments.worker_index is not None
        trace = execute_worker(
            executable,
            arguments.worker_output.resolve(),
            arguments.worker_index,
            contract,
        )
        validate_trace(trace, result_schema)
        print(f"trace={arguments.worker_output.resolve() / TRACE_FILE_NAME}")
        return 0

    assert arguments.output is not None
    output_directory = arguments.output.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(f"R3G output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)

    first, first_path = run_fresh_worker(
        executable,
        output_directory,
        0,
        contract,
    )
    second, second_path = run_fresh_worker(
        executable,
        output_directory,
        1,
        contract,
    )
    result_path = write_two_process_result(
        first=first,
        first_path=first_path,
        second=second,
        second_path=second_path,
        output_directory=output_directory,
        result_schema=result_schema,
        result_schema_version=RESULT_SCHEMA_VERSION,
        contract_path=CONTRACT_PATH,
        task_name="R3G",
        validate_trace=validate_trace,
    )
    updates = first["optimization"]["update_events"]
    print(f"result={result_path}")
    print("fresh_processes=2")
    print("transitions=10004")
    print(f"completed_episodes={first['completed_episode_count']}")
    print(f"episode_resets={first['episode_reset_count']}")
    print(f"unique_action_tuples={first['selector']['unique_action_tuple_count']}")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
