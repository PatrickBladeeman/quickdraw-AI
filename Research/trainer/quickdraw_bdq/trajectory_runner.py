"""CLI orchestration for the existing two-worker update trajectory gates.

Contracts and research assertions stay with their entry points. Checkpoint gates
have different process protocols and do not use this two-worker flow.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from .acceptance import (
    ARTIFACT_ROOT,
    comparison_execution_mode,
    run_fresh_worker_process,
    standard_execution_mode,
    validate_distinct_trace_paths,
    write_two_process_result,
)
from .update_gate import (
    WATCH_BASE_PORT,
    WATCH_PROGRESS_INTERVAL,
    WATCH_TARGET_FRAME_RATE,
    WATCH_TIME_SCALE,
    execute_update_gate_worker,
)


@dataclass(frozen=True)
class TrajectoryGate:
    runner_path: Path
    contract_path: Path
    trace_file_name: str
    trace_schema_version: str
    result_schema_version: str
    task_name: str
    description: str
    cli: Literal["standard", "comparison", "warmup"] = "standard"
    record_update_hashes: bool = True
    announce_workers: bool = True
    timeout_wait: int = 120
    progress_interval: int = 0


def parse_trajectory_arguments(
    gate: TrajectoryGate,
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=gate.description)
    if gate.cli == "warmup":
        parser.add_argument(
            "--env",
            type=Path,
            help=(
                "Unity player executable. Required for acceptance; optional with "
                "--watch to connect to the Unity Editor on port 5004."
            ),
        )
    else:
        parser.add_argument("--env", required=gate.cli == "standard", type=Path)
    parser.add_argument("--output", type=Path)
    if gate.cli == "comparison":
        parser.add_argument(
            "--first-trace",
            type=Path,
            help=(
                "Validate an already completed fresh-process trace together with "
                "--second-trace instead of launching new workers."
            ),
        )
        parser.add_argument(
            "--second-trace",
            type=Path,
            help=(
                "Second independently collected fresh-process trace for recovery "
                "validation."
            ),
        )
    if gate.cli == "warmup":
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


def trajectory_execution_mode(
    gate: TrajectoryGate, arguments: argparse.Namespace
) -> str:
    if gate.cli == "comparison":
        return comparison_execution_mode(arguments)
    if gate.cli == "standard":
        return standard_execution_mode(arguments)
    # Warmup alone supports a one-worker diagnostic watch, including the Editor.
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
        if arguments.progress_interval is not None and arguments.progress_interval <= 0:
            raise ValueError("--progress-interval must be positive.")
        return "watch"
    if arguments.env is None:
        raise ValueError("R3F acceptance mode requires --env.")
    if arguments.progress_interval is not None:
        raise ValueError("--progress-interval requires --watch.")
    return "acceptance"


def _resolve_executable(path: Path | None) -> Path | None:
    executable = path.resolve() if path is not None else None
    if executable is not None and not executable.is_file():
        raise FileNotFoundError(executable)
    return executable


def execute_trajectory_worker(
    gate: TrajectoryGate,
    executable: Path | None,
    worker_output: Path,
    worker_index: int,
    contract: dict[str, Any],
    *,
    watch: bool = False,
    progress_interval: int | None = None,
) -> dict[str, Any]:
    return execute_update_gate_worker(
        executable,
        worker_output,
        worker_index,
        contract,
        contract_path=gate.contract_path,
        trace_file_name=gate.trace_file_name,
        trace_schema_version=gate.trace_schema_version,
        task_name=gate.task_name,
        record_update_hashes=gate.record_update_hashes,
        base_port=WATCH_BASE_PORT if watch else 5045,
        timeout_wait=(
            (300 if executable is None else 120) if watch else gate.timeout_wait
        ),
        watch=watch,
        progress_interval=(
            progress_interval
            if progress_interval is not None
            else WATCH_PROGRESS_INTERVAL if watch else gate.progress_interval
        ),
    )


def _run_watch(
    gate: TrajectoryGate,
    executable: Path | None,
    output_directory: Path,
    contract: dict[str, Any],
    result_schema: dict[str, Any],
    validate_trace: Callable[[dict[str, Any], dict[str, Any]], None],
    progress_interval: int | None,
) -> int:
    print("watch_mode=diagnostic_only", flush=True)
    print("acceptance_evidence=false", flush=True)
    print(f"time_scale={WATCH_TIME_SCALE:g}", flush=True)
    print(f"target_frame_rate={WATCH_TARGET_FRAME_RATE}", flush=True)
    if executable is None:
        print("watch_source=unity_editor", flush=True)
        print(f"listening_port={WATCH_BASE_PORT}", flush=True)
        print(
            "Open the Research_Basic scene in Unity, then press Play now.", flush=True
        )
    else:
        print("watch_source=standalone_player", flush=True)
    trace = execute_trajectory_worker(
        gate,
        executable,
        output_directory,
        0,
        contract,
        watch=True,
        progress_interval=progress_interval,
    )
    validate_trace(trace, result_schema)
    update = trace["optimization"]["update_events"][0]
    print(f"trace={output_directory / gate.trace_file_name}")
    print("watch_complete=true")
    print("acceptance_evidence=false")
    print(f"transitions={trace['replay']['decision_count']}")
    print(f"completed_episodes={trace['completed_episode_count']}")
    print(f"optimizer_updates={trace['optimization']['optimizer_update_count']}")
    print(f"loss={update['loss']}")
    if executable is None:
        print("Stop Play Mode in the Unity Editor when you are finished watching.")
    return 0


def run_trajectory(
    gate: TrajectoryGate,
    *,
    validate_contract: Callable[[dict[str, Any]], dict[str, Any]],
    validate_trace: Callable[[dict[str, Any], dict[str, Any]], None],
    summarize: Callable[[dict[str, Any]], None],
    arguments: Sequence[str] | None = None,
) -> int:
    args = parse_trajectory_arguments(gate, arguments)
    mode = trajectory_execution_mode(gate, args)
    # Historical standard/watch commands check the player before the contract.
    # Comparison-capable commands check it only after contract and output checks.
    executable = _resolve_executable(args.env) if gate.cli != "comparison" else None
    contract = json.loads(gate.contract_path.read_text(encoding="utf-8"))
    result_schema = validate_contract(contract)

    if mode == "worker":
        if gate.cli == "comparison":
            executable = _resolve_executable(args.env)
        assert executable is not None
        trace = execute_trajectory_worker(
            gate,
            executable,
            args.worker_output.resolve(),
            args.worker_index,
            contract,
        )
        validate_trace(trace, result_schema)
        print(f"trace={args.worker_output.resolve() / gate.trace_file_name}")
        return 0

    output_directory = args.output.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(
            f"{gate.task_name} output must be fresh: {output_directory}."
        )

    if mode == "watch":
        return _run_watch(
            gate,
            executable,
            output_directory,
            contract,
            result_schema,
            validate_trace,
            args.progress_interval,
        )
    if mode == "compare":
        first_path, second_path = (
            args.first_trace.resolve(),
            args.second_trace.resolve(),
        )
        validate_distinct_trace_paths(first_path, second_path, task_name=gate.task_name)
        first = json.loads(first_path.read_text(encoding="utf-8"))
        second = json.loads(second_path.read_text(encoding="utf-8"))
    else:
        if gate.cli == "comparison":
            executable = _resolve_executable(args.env)
        assert executable is not None
        output_directory.mkdir(parents=True)
        workers = [
            run_fresh_worker_process(
                runner_path=gate.runner_path,
                executable=executable,
                output_directory=output_directory,
                worker_index=index,
                contract=contract,
                trace_file_name=gate.trace_file_name,
                task_name=gate.task_name,
                announce=gate.announce_workers,
            )
            for index in (0, 1)
        ]
        (first, first_path), (second, second_path) = workers
    result_path = write_two_process_result(
        first=first,
        first_path=first_path,
        second=second,
        second_path=second_path,
        output_directory=output_directory,
        result_schema=result_schema,
        result_schema_version=gate.result_schema_version,
        contract_path=gate.contract_path,
        task_name=gate.task_name,
        validate_trace=validate_trace,
    )
    print(f"result={result_path}")
    if gate.cli == "comparison":
        print(f"first_trace={first_path}")
        print(f"second_trace={second_path}")
    summarize(first)
    return 0
