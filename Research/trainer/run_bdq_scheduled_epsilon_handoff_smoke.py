from __future__ import annotations

import argparse
import hashlib
import json
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
    canonical_json_sha256,
)
from run_bdq_warmup_update_smoke import (  # noqa: E402
    ARTIFACT_ROOT,
    PYPROJECT_PATH,
    _registered_settings,
    execute_update_gate_worker,
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-scheduled-epsilon-handoff-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-scheduled-epsilon-handoff-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-scheduled-epsilon-handoff-smoke-result.schema.json"
)
TRACE_FILE_NAME = "r3j-scheduled-epsilon-handoff-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-scheduled-epsilon-handoff-trace.v1"
RESULT_SCHEMA_VERSION = (
    "quickdraw.bdq-scheduled-epsilon-handoff-smoke-result.v1"
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

    schedule_binding = contract["base_epsilon_schedule_contract"]
    schedule_contract_path = REPO_ROOT / schedule_binding["path"]
    if sha256_file(schedule_contract_path) != schedule_binding["sha256"]:
        raise LLAPIContractError(
            f"Contract binding drifted: {schedule_binding['path']}."
        )
    base_schedule_contract = json.loads(
        schedule_contract_path.read_text(encoding="utf-8")
    )
    if base_schedule_contract["schema_version"] != schedule_binding[
        "schema_version"
    ]:
        raise LLAPIContractError("R3J's R3I schema binding drifted.")

    prefix_binding = contract["live_prefix_source_contract"]
    prefix_contract_path = REPO_ROOT / prefix_binding["path"]
    if sha256_file(prefix_contract_path) != prefix_binding["sha256"]:
        raise LLAPIContractError(
            f"Contract binding drifted: {prefix_binding['path']}."
        )
    prefix_contract = json.loads(prefix_contract_path.read_text(encoding="utf-8"))
    if prefix_contract["schema_version"] != prefix_binding["schema_version"]:
        raise LLAPIContractError("R3J's R3H schema binding drifted.")
    inherited_section = prefix_binding["inherited_section"]
    if prefix_contract[inherited_section] != contract["r3g_prefix"]:
        raise LLAPIContractError("R3J's registered R3G prefix drifted from R3H.")

    if contract["runtime"] != _runtime_contract():
        raise LLAPIContractError("The active runtime differs from R3J.")
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError("The R3J package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError("The R3J package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point returned.")

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3J differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions,
        settings.replay_warmup_decisions
        + settings.optimizer_update_interval_decisions,
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3J update decisions differ from R3G.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3J update count differs from R3G.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3J must not synchronize the target network.")

    schedule_contract = contract["epsilon_schedule"]
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=schedule_contract["replay_warmup_decisions"],
        decay_decisions=schedule_contract["decay_decisions"],
        initial_epsilon=schedule_contract["initial_epsilon"],
        final_epsilon=schedule_contract["final_epsilon"],
    )
    if schedule_contract["replay_warmup_decisions"] != (
        base_schedule_contract["schedule"]["replay_warmup_decisions"]
    ):
        raise LLAPIContractError("R3J warmup differs from R3I.")
    if schedule_contract["decay_decisions"] != base_schedule_contract[
        "schedule"
    ]["decay_decisions"]:
        raise LLAPIContractError("R3J decay length differs from R3I.")
    sample_counts = schedule_contract[
        "trace_sample_completed_transition_counts"
    ]
    expected_sample_epsilons = [
        schedule.epsilon_at(count) for count in sample_counts
    ]
    if schedule_contract["trace_sample_epsilons"] != expected_sample_epsilons:
        raise LLAPIContractError("R3J epsilon samples differ from its schedule.")

    collection = contract["collection"]
    handoff = contract["scheduled_epsilon_handoff"]
    prefix = contract["r3g_prefix"]
    if prefix["transition_count"] != expected_updates[-1]:
        raise LLAPIContractError("R3J prefix does not end at R3G update 2.")
    if handoff["selection_after_decision_count"] != prefix["transition_count"]:
        raise LLAPIContractError("R3J handoff does not immediately follow R3G.")
    if handoff["completed_transition_index"] != prefix["transition_count"]:
        raise LLAPIContractError("R3J handoff transition index is not contiguous.")
    if handoff["selection_ordinal"] != prefix["transition_count"]:
        raise LLAPIContractError("R3J selector lifetime was reset at handoff.")
    if handoff["required_optimizer_update_count"] != len(expected_updates):
        raise LLAPIContractError("R3J handoff is not bound to update 2.")
    expected_handoff_epsilon = schedule.epsilon_at(
        handoff["selection_after_decision_count"]
    )
    if handoff["epsilon"] != expected_handoff_epsilon:
        raise LLAPIContractError("R3J handoff epsilon differs from R3I.")
    if collection["transition_limit"] != prefix["transition_count"] + 1:
        raise LLAPIContractError("R3J must complete exactly one new transition.")
    if collection["scheduled_transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3J must schedule every collected action.")
    if schedule_contract["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3J schedule count differs from its cutoff.")
    if schedule_contract["full_exploration_selection_count"] != (
        schedule.replay_warmup_decisions + 1
    ):
        raise LLAPIContractError("R3J full-exploration selection count drifted.")
    if schedule_contract["decay_selection_count"] != (
        collection["transition_limit"]
        - schedule_contract["full_exploration_selection_count"]
    ):
        raise LLAPIContractError("R3J decay selection count drifted.")
    if collection["transition_limit"] % (
        settings.optimizer_update_interval_decisions
    ) == 0:
        raise LLAPIContractError("R3J accidentally opens a third update.")
    return result_schema


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name="R3J",
        require_update_hashes=True,
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    prefix = contract["r3g_prefix"]
    prefix_count = int(prefix["transition_count"])
    if canonical_json_sha256(trace["transitions"][:prefix_count]) != prefix[
        "canonical_transitions_sha256"
    ]:
        raise LLAPIContractError("R3J did not preserve the canonical R3G prefix.")

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
    )
    for event, (online_hash, loss, td_error) in zip(events, expected_events):
        if event["online_after_sha256"] != online_hash:
            raise LLAPIContractError("R3J changed an R3G post-update online hash.")
        if event["loss"] != loss or event["mean_absolute_td_error"] != td_error:
            raise LLAPIContractError("R3J changed an R3G optimizer metric.")
    if optimization["online_after_sha256"] != prefix[
        "online_after_second_update_sha256"
    ]:
        raise LLAPIContractError("R3J final online hash differs from R3G update 2.")
    if optimization["target_before_sha256"] != prefix[
        "frozen_target_sha256"
    ] or optimization["target_after_sha256"] != prefix["frozen_target_sha256"]:
        raise LLAPIContractError("R3J changed the frozen R3G target network.")

    schedule_contract = contract["epsilon_schedule"]
    selector = trace["selector"]
    expected_samples = [
        {"completed_transition_count": count, "epsilon": epsilon}
        for count, epsilon in zip(
            schedule_contract["trace_sample_completed_transition_counts"],
            schedule_contract["trace_sample_epsilons"],
        )
    ]
    if selector["epsilon_samples"] != expected_samples:
        raise LLAPIContractError("R3J trace epsilon samples drifted.")
    for key in (
        "selection_count",
        "full_exploration_selection_count",
        "decay_selection_count",
        "first_decay_completed_transition_count",
        "last_selection_completed_transition_count",
    ):
        if selector[key] != schedule_contract[key]:
            raise LLAPIContractError(f"R3J selector {key} drifted.")
    if selector["completed_transition_count_source"] != schedule_contract[
        "completed_transition_count_source"
    ]:
        raise LLAPIContractError("R3J selector counter source drifted.")

    handoff_contract = contract["scheduled_epsilon_handoff"]
    handoff = trace["scheduled_epsilon_handoff"]
    final_transition = trace["transitions"][handoff["transition_index"]]
    if handoff["selection_after_decision_count"] != handoff_contract[
        "selection_after_decision_count"
    ]:
        raise LLAPIContractError("R3J handoff opened at the wrong decision.")
    if handoff["selection_ordinal"] != handoff_contract["selection_ordinal"]:
        raise LLAPIContractError("R3J scheduled selector was not continuous.")
    if handoff["epsilon"] != handoff_contract["epsilon"]:
        raise LLAPIContractError("R3J handoff recorded the wrong epsilon.")
    if handoff["online_sha256"] != events[-1]["online_after_sha256"]:
        raise LLAPIContractError("R3J handoff did not use the update-2 network.")
    if handoff["target_sha256"] != optimization["target_after_sha256"]:
        raise LLAPIContractError("R3J handoff did not observe the frozen target.")
    if handoff["observation_sha256"] != final_transition[
        "observation_sha256"
    ]:
        raise LLAPIContractError("R3J handoff observation differs from replay.")
    if handoff["action_masks"] != final_transition["action_masks"]:
        raise LLAPIContractError("R3J handoff masks differ from replay.")
    if handoff["selected_action"] != final_transition["action"]:
        raise LLAPIContractError("R3J handoff action differs from replay.")
    if handoff["observation_sha256"] != handoff_contract[
        "expected_observation_sha256"
    ]:
        raise LLAPIContractError("R3J handoff observed an unexpected live state.")
    if handoff["action_masks"] != handoff_contract["expected_action_masks"]:
        raise LLAPIContractError("R3J handoff action masks drifted.")
    if handoff["selected_action"] != handoff_contract[
        "expected_selected_action"
    ]:
        raise LLAPIContractError("R3J continuous selector action drifted.")
    if any(
        handoff["action_masks"][branch][action]
        for branch, action in enumerate(handoff["selected_action"])
    ):
        raise LLAPIContractError("R3J handoff selected an unavailable action.")


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
        task_name="R3J",
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
            f"Fresh R3J worker {worker_index + 1} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )
    trace_path = worker_output / TRACE_FILE_NAME
    if not trace_path.is_file():
        raise RuntimeError(f"Fresh R3J worker omitted {trace_path}.")
    print(f"worker_{worker_index + 1}=complete", flush=True)
    return json.loads(trace_path.read_text(encoding="utf-8")), trace_path


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run two fresh continuous scheduled-epsilon collections through "
            "one live action after the second optimizer update."
        )
    )
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.worker_output is not None:
        if arguments.worker_index is None or arguments.output is not None:
            raise ValueError(
                "Worker mode requires only --env, --worker-output, and "
                "--worker-index."
            )
        return "worker"
    if arguments.output is None or arguments.worker_index is not None:
        raise ValueError("Parent mode requires --output and no worker index.")
    return "parent"


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
        raise FileExistsError(f"R3J output must be fresh: {output_directory}.")
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
    validate_trace(first, result_schema)
    validate_trace(second, result_schema)
    if first != second or first_path.read_bytes() != second_path.read_bytes():
        raise LLAPIContractError(
            f"Fresh R3J traces differ: {first_path} versus {second_path}."
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
    result_path = output_directory / "result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    handoff = first["scheduled_epsilon_handoff"]
    print(f"result={result_path}")
    print("fresh_processes=2")
    print("transitions=10005")
    print("scheduled_actions=10005")
    print("r3g_prefix_transitions=10004")
    print(f"scheduled_handoff_epsilon={handoff['epsilon']}")
    print(f"scheduled_handoff_action={handoff['selected_action']}")
    print("pending_decisions=0")
    print("optimizer_updates=2")
    print("target_synchronizations=0")
    print("r3g_prefix_preserved=pass")
    print("continuous_scheduled_selector=pass")
    print("scheduled_handoff_legal=pass")
    print("exact_trace_equality=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
