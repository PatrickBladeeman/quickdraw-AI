from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Sequence

from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    LLAPIContractError,
    LinearEpsilonSchedule,
)
from run_bdq_epsilon_collection_smoke import sha256_file  # noqa: E402
from run_bdq_post_update_handoff_smoke import (  # noqa: E402
    _masked_argmax,
    canonical_json_sha256,
)
from run_bdq_warmup_update_smoke import (  # noqa: E402
    ARTIFACT_ROOT,
    PYPROJECT_PATH,
    _registered_settings,
    execute_update_gate_worker,
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


def _runtime_contract() -> Dict[str, str]:
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)

    binding = contract["base_third_update_contract"]
    base_contract_path = REPO_ROOT / binding["path"]
    if sha256_file(base_contract_path) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    base_contract = json.loads(base_contract_path.read_text(encoding="utf-8"))
    if base_contract["schema_version"] != binding["schema_version"]:
        raise LLAPIContractError("R3L's R3K schema binding drifted.")

    if contract["runtime"] != _runtime_contract():
        raise LLAPIContractError("The active runtime differs from R3L.")
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError("The R3L package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError("The R3L package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point returned.")
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
    prefix_count = int(prefix["transition_count"])
    if canonical_json_sha256(trace["transitions"][:prefix_count]) != prefix[
        "canonical_transitions_sha256"
    ]:
        raise LLAPIContractError("R3L did not preserve the canonical R3K prefix.")

    optimization = trace["optimization"]
    events = optimization["update_events"]
    expected_events = (
        (
            prefix["online_after_first_update_sha256"],
            prefix["first_update_loss"],
            prefix["first_update_mean_absolute_td_error"],
        ),
        (
            prefix["online_after_second_update_sha256"],
            prefix["second_update_loss"],
            prefix["second_update_mean_absolute_td_error"],
        ),
        (
            prefix["online_after_third_update_sha256"],
            prefix["third_update_loss"],
            prefix["third_update_mean_absolute_td_error"],
        ),
    )
    for event, (online_hash, loss, td_error) in zip(events, expected_events):
        if event["online_after_sha256"] != online_hash:
            raise LLAPIContractError("R3L changed an R3K post-update online hash.")
        if event["loss"] != loss or event["mean_absolute_td_error"] != td_error:
            raise LLAPIContractError("R3L changed an R3K optimizer metric.")
    if optimization["online_after_sha256"] != prefix[
        "online_after_third_update_sha256"
    ]:
        raise LLAPIContractError("R3L final online hash differs from R3K update 3.")
    if optimization["target_before_sha256"] != prefix[
        "frozen_target_sha256"
    ] or optimization["target_after_sha256"] != prefix["frozen_target_sha256"]:
        raise LLAPIContractError("R3L changed the frozen R3K target network.")

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
        task_name="R3L",
        record_update_hashes=True,
    )


def run_fresh_worker(
    executable: Path,
    output_directory: Path,
    worker_index: int,
    contract: Dict[str, Any],
) -> tuple[Dict[str, Any], Path]:
    worker_output = output_directory / f"run-{worker_index + 1}"
    print(f"worker_{worker_index + 1}=starting", flush=True)
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        f"--env={executable}",
        f"--worker-output={worker_output}",
        f"--worker-index={worker_index}",
    ]
    process_environment = dict(os.environ)
    process_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    thread_count = str(contract["determinism"]["torch_num_threads"])
    process_environment["OMP_NUM_THREADS"] = thread_count
    process_environment["MKL_NUM_THREADS"] = thread_count
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=process_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=1800,
        check=False,
    )
    log_path = output_directory / f"worker-{worker_index + 1}.log"
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Fresh R3L worker {worker_index + 1} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )
    trace_path = worker_output / TRACE_FILE_NAME
    if not trace_path.is_file():
        raise RuntimeError(f"Fresh R3L worker omitted {trace_path}.")
    print(f"worker_{worker_index + 1}=complete", flush=True)
    return json.loads(trace_path.read_text(encoding="utf-8")), trace_path


def _validate_distinct_trace_paths(first_path: Path, second_path: Path) -> None:
    if not first_path.is_file():
        raise FileNotFoundError(first_path)
    if not second_path.is_file():
        raise FileNotFoundError(second_path)
    if first_path == second_path or first_path.samefile(second_path):
        raise ValueError("R3L comparison requires two distinct trace files.")


def _write_acceptance_result(
    first: Dict[str, Any],
    first_path: Path,
    second: Dict[str, Any],
    second_path: Path,
    output_directory: Path,
    result_schema: Dict[str, Any],
) -> tuple[Path, Dict[str, Any]]:
    validate_trace(first, result_schema)
    validate_trace(second, result_schema)
    if first != second or first_path.read_bytes() != second_path.read_bytes():
        raise LLAPIContractError(
            f"Fresh R3L traces differ: {first_path} versus {second_path}."
        )

    canonical_bytes = json.dumps(
        first,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "fresh_process_count": 2,
        "exact_trace_equality": True,
        "canonical_trace_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "canonical_trace": first,
    }
    Draft202012Validator(result_schema).validate(result)
    output_directory.mkdir(parents=True, exist_ok=True)
    result_path = output_directory / "result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result_path, first


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run two fresh R3K-prefix collections followed by one update-3 "
            "diagnostic masked-greedy Unity transition."
        )
    )
    parser.add_argument("--env", type=Path)
    parser.add_argument("--output", type=Path)
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
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def _execution_mode(arguments: argparse.Namespace) -> str:
    trace_paths_supplied = (
        arguments.first_trace is not None or arguments.second_trace is not None
    )
    if trace_paths_supplied:
        if (
            arguments.first_trace is None
            or arguments.second_trace is None
            or arguments.output is None
            or arguments.env is not None
            or arguments.worker_output is not None
            or arguments.worker_index is not None
        ):
            raise ValueError(
                "Trace-comparison mode requires only --output, --first-trace, "
                "and --second-trace."
            )
        return "compare"
    if arguments.worker_output is not None:
        if (
            arguments.env is None
            or arguments.worker_index is None
            or arguments.output is not None
        ):
            raise ValueError(
                "Worker mode requires only --env, --worker-output, and "
                "--worker-index."
            )
        return "worker"
    if (
        arguments.env is None
        or arguments.output is None
        or arguments.worker_index is not None
    ):
        raise ValueError("Parent mode requires --output and no worker index.")
    return "parent"


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result_schema = validate_contract(contract)

    if mode == "worker":
        assert arguments.env is not None
        assert arguments.worker_output is not None
        assert arguments.worker_index is not None
        executable = arguments.env.resolve()
        if not executable.is_file():
            raise FileNotFoundError(executable)
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
        raise FileExistsError(f"R3L output must be fresh: {output_directory}.")

    if mode == "compare":
        assert arguments.first_trace is not None
        assert arguments.second_trace is not None
        first_path = arguments.first_trace.resolve()
        second_path = arguments.second_trace.resolve()
        _validate_distinct_trace_paths(first_path, second_path)
        first = json.loads(first_path.read_text(encoding="utf-8"))
        second = json.loads(second_path.read_text(encoding="utf-8"))
    else:
        assert arguments.env is not None
        executable = arguments.env.resolve()
        if not executable.is_file():
            raise FileNotFoundError(executable)
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

    result_path, accepted_trace = _write_acceptance_result(
        first,
        first_path,
        second,
        second_path,
        output_directory,
        result_schema,
    )

    handoff = accepted_trace["post_update_greedy_handoff"]
    print(f"result={result_path}")
    print(f"first_trace={first_path}")
    print(f"second_trace={second_path}")
    print("fresh_processes=2")
    print("transitions=10009")
    print("r3k_prefix_transitions=10008")
    print("scheduled_actions=10008")
    print("post_update_greedy_actions=1")
    print(f"greedy_action={handoff['selected_action']}")
    print(f"max_absolute_q_delta={handoff['max_absolute_q_delta']}")
    print(f"online_sha256={handoff['online_sha256']}")
    print(f"target_sha256={handoff['target_sha256']}")
    print(f"completed_episodes={accepted_trace['completed_episode_count']}")
    print(f"truncation_events={len(accepted_trace['truncation_events'])}")
    print("pending_decisions=0")
    print("optimizer_updates=3")
    print("target_synchronizations=0")
    print("r3k_prefix_preserved=pass")
    print("scheduled_selector_not_consumed_at_handoff=pass")
    print("masked_greedy_handoff=pass")
    print("no_fourth_update=pass")
    print("exact_trace_equality=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
