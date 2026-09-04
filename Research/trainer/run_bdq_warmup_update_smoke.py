from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import BDQOptimizationSettings, LLAPIContractError  # noqa: E402
from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    PYPROJECT_PATH,
    registered_settings as _registered_settings,
    run_fresh_worker_process,
    sha256_file,
    validate_runtime_and_package,
    validate_schema_pair,
    write_two_process_result,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    WATCH_BASE_PORT,
    WATCH_PROGRESS_INTERVAL,
    WATCH_TARGET_FRAME_RATE,
    WATCH_TIME_SCALE,
    execute_update_gate_worker,
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


def execute_worker(
    executable: Path | None,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
    *,
    base_port: int = 5045,
    timeout_wait: int = 120,
    watch: bool = False,
    progress_interval: int = 0,
) -> Dict[str, Any]:
    return execute_update_gate_worker(
        executable,
        worker_output,
        worker_index,
        contract,
        contract_path=CONTRACT_PATH,
        trace_file_name=TRACE_FILE_NAME,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        task_name="R3F",
        record_update_hashes=False,
        base_port=base_port,
        timeout_wait=timeout_wait,
        watch=watch,
        progress_interval=progress_interval,
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
        task_name="R3F",
        announce=False,
        repo_root=REPO_ROOT,
    )


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the production BDQ warmup and first update twice, or run one "
            "diagnostic watch session."
        )
    )
    parser.add_argument(
        "--env",
        type=Path,
        help=(
            "Unity player executable. Required for acceptance; optional with "
            "--watch to connect to the Unity Editor on port 5004."
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--watch",
        action="store_true",
        help=(
            "Run one visible, real-time diagnostic session. This does not "
            "produce two-process R3F acceptance evidence."
        ),
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        help="Watch-mode terminal progress interval (default: 100 transitions).",
    )
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.worker_output is not None:
        if (
            arguments.env is None
            or arguments.worker_index is None
            or arguments.output is not None
            or arguments.watch
            or arguments.progress_interval is not None
        ):
            raise ValueError(
                "Worker mode requires only --env, --worker-output, and "
                "--worker-index."
            )
        return "worker"
    if arguments.worker_index is not None:
        raise ValueError("--worker-index requires --worker-output.")
    if arguments.output is None:
        raise ValueError("Parent and watch modes require --output.")
    if arguments.watch:
        if (
            arguments.progress_interval is not None
            and arguments.progress_interval <= 0
        ):
            raise ValueError("--progress-interval must be positive.")
        return "watch"
    if arguments.env is None:
        raise ValueError("R3F acceptance mode requires --env.")
    if arguments.progress_interval is not None:
        raise ValueError("--progress-interval requires --watch.")
    return "acceptance"


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    executable = arguments.env.resolve() if arguments.env is not None else None
    if executable is not None and not executable.is_file():
        raise FileNotFoundError(executable)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result_schema = validate_contract(contract)

    if mode == "worker":
        assert executable is not None
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
        raise FileExistsError(f"R3F output must be fresh: {output_directory}.")

    if mode == "watch":
        progress_interval = (
            arguments.progress_interval
            if arguments.progress_interval is not None
            else WATCH_PROGRESS_INTERVAL
        )
        print("watch_mode=diagnostic_only", flush=True)
        print("acceptance_evidence=false", flush=True)
        print(f"time_scale={WATCH_TIME_SCALE:g}", flush=True)
        print(f"target_frame_rate={WATCH_TARGET_FRAME_RATE}", flush=True)
        if executable is None:
            print("watch_source=unity_editor", flush=True)
            print(f"listening_port={WATCH_BASE_PORT}", flush=True)
            print(
                "Open the Research_Basic scene in Unity, then press Play now.",
                flush=True,
            )
        else:
            print("watch_source=standalone_player", flush=True)
        trace = execute_worker(
            executable,
            output_directory,
            0,
            contract,
            base_port=WATCH_BASE_PORT,
            timeout_wait=300 if executable is None else 120,
            watch=True,
            progress_interval=progress_interval,
        )
        validate_trace(trace, result_schema)
        update = trace["optimization"]["update_events"][0]
        print(f"trace={output_directory / TRACE_FILE_NAME}")
        print("watch_complete=true")
        print("acceptance_evidence=false")
        print(f"transitions={trace['replay']['decision_count']}")
        print(f"completed_episodes={trace['completed_episode_count']}")
        print(f"optimizer_updates={trace['optimization']['optimizer_update_count']}")
        print(f"loss={update['loss']}")
        if executable is None:
            print("Stop Play Mode in the Unity Editor when you are finished watching.")
        return 0

    assert executable is not None
    output_directory.mkdir(parents=True)
    first, first_path = run_fresh_worker(executable, output_directory, 0, contract)
    second, second_path = run_fresh_worker(executable, output_directory, 1, contract)
    result_path = write_two_process_result(
        first=first,
        first_path=first_path,
        second=second,
        second_path=second_path,
        output_directory=output_directory,
        result_schema=result_schema,
        result_schema_version=RESULT_SCHEMA_VERSION,
        contract_path=CONTRACT_PATH,
        task_name="R3F",
        validate_trace=validate_trace,
    )

    update = first["optimization"]["update_events"][0]
    print(f"result={result_path}")
    print("fresh_processes=2")
    print("transitions=10000")
    print(f"completed_episodes={first['completed_episode_count']}")
    print(f"episode_resets={first['episode_reset_count']}")
    print(f"unique_action_tuples={first['selector']['unique_action_tuple_count']}")
    print("pending_decisions=0")
    print("optimizer_updates=1")
    print("first_update_decision=10000")
    print("target_synchronizations=0")
    print(f"loss={update['loss']}")
    print(f"mean_absolute_td_error={update['mean_absolute_td_error']}")
    print("online_weights_changed=pass")
    print("target_weights_unchanged=pass")
    print("exact_trace_equality=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
