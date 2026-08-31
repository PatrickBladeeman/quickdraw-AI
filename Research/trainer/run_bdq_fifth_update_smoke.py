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

    binding = contract["base_fourth_update_contract"]
    base_contract_path = REPO_ROOT / binding["path"]
    if sha256_file(base_contract_path) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    base_contract = json.loads(base_contract_path.read_text(encoding="utf-8"))
    if base_contract["schema_version"] != binding["schema_version"]:
        raise LLAPIContractError("R3O's R3M schema binding drifted.")

    storage_binding = contract["base_replay_storage_contract"]
    storage_contract_path = REPO_ROOT / storage_binding["path"]
    if sha256_file(storage_contract_path) != storage_binding["sha256"]:
        raise LLAPIContractError(
            f"Contract binding drifted: {storage_binding['path']}."
        )
    storage_contract = json.loads(storage_contract_path.read_text(encoding="utf-8"))
    if storage_contract["schema_version"] != storage_binding["schema_version"]:
        raise LLAPIContractError("R3O's R3N schema binding drifted.")
    storage_base = storage_contract["base_fourth_update_contract"]
    if (
        storage_base["path"] != binding["path"]
        or storage_base["sha256"] != binding["sha256"]
    ):
        raise LLAPIContractError("R3N does not bind R3O's active R3M contract.")

    if contract["runtime"] != _runtime_contract():
        raise LLAPIContractError("The active runtime differs from R3O.")
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError("The R3O package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError("The R3O package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point returned.")
    for key in ("runtime", "package", "transport"):
        if contract[key] != base_contract[key]:
            raise LLAPIContractError(f"R3O {key} differs from R3M.")
    if (
        contract["runtime"] != storage_contract["runtime"]
        or contract["package"] != storage_contract["package"]
    ):
        raise LLAPIContractError("R3O differs from the R3N replay-storage boundary.")

    player_execution = contract["player_execution"]
    project_settings_path = REPO_ROOT / player_execution[
        "project_settings_path"
    ]
    project_settings = project_settings_path.read_text(encoding="utf-8")
    expected_background_setting = (
        "  runInBackground: 1"
        if player_execution["run_in_background"]
        else "  runInBackground: 0"
    )
    if expected_background_setting not in project_settings.splitlines():
        raise LLAPIContractError(
            "R3O's standalone-player background setting has drifted."
        )
    if player_execution["no_graphics"]:
        raise LLAPIContractError("R3O visual observations require graphics.")
    if player_execution["standalone_player_arguments"]:
        raise LLAPIContractError(
            "R3O must not alter visual observations with player arguments."
        )

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3O differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions
        + index * settings.optimizer_update_interval_decisions
        for index in range(5)
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3O update decisions differ from its schedule.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3O must stop after optimizer update 5.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3O must not synchronize the target network.")

    collection = contract["collection"]
    if collection["transition_limit"] != expected_updates[-1]:
        raise LLAPIContractError("R3O cutoff must equal optimizer update 5.")
    if collection["scheduled_transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3O must schedule every collected action.")
    for key in ("scenario_seed", "policy_seed", "exploration_seed", "selector"):
        if collection[key] != base_contract["collection"][key]:
            raise LLAPIContractError(f"R3O collection {key} differs from R3M.")

    schedule_contract = contract["epsilon_schedule"]
    base_schedule = base_contract["epsilon_schedule"]
    for key in (
        "class",
        "selector_class",
        "completed_transition_count_source",
        "replay_warmup_decisions",
        "decay_decisions",
        "initial_epsilon",
        "final_epsilon",
        "continuous_selector_rng_from_completed_count_zero",
    ):
        if schedule_contract[key] != base_schedule[key]:
            raise LLAPIContractError(f"R3O epsilon schedule {key} differs from R3M.")
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=schedule_contract["replay_warmup_decisions"],
        decay_decisions=schedule_contract["decay_decisions"],
        initial_epsilon=schedule_contract["initial_epsilon"],
        final_epsilon=schedule_contract["final_epsilon"],
    )
    sample_counts = schedule_contract[
        "trace_sample_completed_transition_counts"
    ]
    expected_sample_epsilons = [
        schedule.epsilon_at(count) for count in sample_counts
    ]
    if schedule_contract["trace_sample_epsilons"] != expected_sample_epsilons:
        raise LLAPIContractError("R3O epsilon samples differ from its schedule.")
    if schedule_contract["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3O selector count differs from its cutoff.")
    if schedule_contract["full_exploration_selection_count"] != (
        schedule.replay_warmup_decisions + 1
    ):
        raise LLAPIContractError("R3O full-exploration count drifted.")
    if schedule_contract["decay_selection_count"] != (
        collection["transition_limit"]
        - schedule_contract["full_exploration_selection_count"]
    ):
        raise LLAPIContractError("R3O decay-selection count drifted.")
    if schedule_contract["last_selection_completed_transition_count"] != (
        collection["transition_limit"] - 1
    ):
        raise LLAPIContractError("R3O selected an action after update 5.")

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
    update_prefix_fields = (
        (
            "online_after_first_update_sha256",
            "first_update_loss",
            "first_update_mean_absolute_td_error",
        ),
        (
            "online_after_second_update_sha256",
            "second_update_loss",
            "second_update_mean_absolute_td_error",
        ),
        (
            "online_after_third_update_sha256",
            "third_update_loss",
            "third_update_mean_absolute_td_error",
        ),
        (
            "online_after_fourth_update_sha256",
            "fourth_update_loss",
            "fourth_update_mean_absolute_td_error",
        ),
    )
    for index, (hash_key, loss_key, td_error_key) in enumerate(
        update_prefix_fields
    ):
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
    for key in (
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
    ):
        if prefix[key] != base_contract["r3k_prefix"][key]:
            raise LLAPIContractError(f"R3O prefix {key} differs from R3M.")
    if prefix["online_after_fourth_update_sha256"] == prefix[
        "online_after_third_update_sha256"
    ]:
        raise LLAPIContractError("R3O's R3M prefix omits update 4.")

    boundary = contract["fifth_update_boundary"]
    if boundary["continuation_after_transition_count"] != prefix[
        "transition_count"
    ]:
        raise LLAPIContractError("R3O continuation does not begin after R3M.")
    if boundary["new_transition_count"] != (
        collection["transition_limit"] - prefix["transition_count"]
    ):
        raise LLAPIContractError("R3O continuation is not exactly four transitions.")
    if boundary["first_new_selection_completed_transition_count"] != prefix[
        "transition_count"
    ]:
        raise LLAPIContractError("R3O first new selection is not contiguous.")
    if boundary["last_new_selection_completed_transition_count"] != (
        collection["transition_limit"] - 1
    ):
        raise LLAPIContractError("R3O last new selection count drifted.")
    if boundary["completion_decision_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3O completion count differs from its cutoff.")
    if boundary["optimizer_update_count_before_continuation"] != 4:
        raise LLAPIContractError("R3O does not continue after R3M update 4.")
    if boundary["optimizer_update_count_after_completion"] != len(
        expected_updates
    ):
        raise LLAPIContractError("R3O completion is not optimizer update 5.")
    if boundary["target_sync_count_after_completion"] != 0:
        raise LLAPIContractError("R3O boundary includes a target synchronization.")
    if boundary["select_action_after_fifth_update"]:
        raise LLAPIContractError("R3O must stop before a post-update action.")
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
    prefix = contract["r3m_prefix"]
    prefix_count = int(prefix["transition_count"])
    if canonical_json_sha256(trace["transitions"][:prefix_count]) != prefix[
        "canonical_transitions_sha256"
    ]:
        raise LLAPIContractError("R3O did not preserve the canonical R3M prefix.")

    optimization = trace["optimization"]
    events = optimization["update_events"]
    expected_prefix_events = (
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
        (
            prefix["online_after_fourth_update_sha256"],
            prefix["fourth_update_loss"],
            prefix["fourth_update_mean_absolute_td_error"],
        ),
    )
    for event, (online_hash, loss, td_error) in zip(
        events[:4], expected_prefix_events
    ):
        if event["online_after_sha256"] != online_hash:
            raise LLAPIContractError("R3O changed an R3M post-update online hash.")
        if event["loss"] != loss or event["mean_absolute_td_error"] != td_error:
            raise LLAPIContractError("R3O changed an R3M optimizer metric.")

    fifth_update = events[4]
    if fifth_update["online_after_sha256"] == prefix[
        "online_after_fourth_update_sha256"
    ]:
        raise LLAPIContractError("R3O update 5 did not change the online network.")
    if optimization["online_after_sha256"] != fifth_update[
        "online_after_sha256"
    ]:
        raise LLAPIContractError("R3O final online hash differs from update 5.")
    if optimization["target_before_sha256"] != prefix[
        "frozen_target_sha256"
    ] or optimization["target_after_sha256"] != prefix["frozen_target_sha256"]:
        raise LLAPIContractError("R3O changed the frozen R3M target network.")

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
        raise LLAPIContractError("R3O trace epsilon samples drifted.")
    for key in (
        "selection_count",
        "full_exploration_selection_count",
        "decay_selection_count",
        "first_decay_completed_transition_count",
        "last_selection_completed_transition_count",
    ):
        if selector[key] != schedule_contract[key]:
            raise LLAPIContractError(f"R3O selector {key} drifted.")
    if selector["completed_transition_count_source"] != schedule_contract[
        "completed_transition_count_source"
    ]:
        raise LLAPIContractError("R3O selector counter source drifted.")
    if selector["last_selection_completed_transition_count"] >= trace["replay"][
        "decision_count"
    ]:
        raise LLAPIContractError("R3O selected an action after update 5.")


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
        task_name="R3O",
        record_update_hashes=True,
        timeout_wait=300,
        progress_interval=1_000,
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
            f"Fresh R3O worker {worker_index + 1} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )
    trace_path = worker_output / TRACE_FILE_NAME
    if not trace_path.is_file():
        raise RuntimeError(f"Fresh R3O worker omitted {trace_path}.")
    print(f"worker_{worker_index + 1}=complete", flush=True)
    return json.loads(trace_path.read_text(encoding="utf-8")), trace_path


def _validate_distinct_trace_paths(first_path: Path, second_path: Path) -> None:
    if not first_path.is_file():
        raise FileNotFoundError(first_path)
    if not second_path.is_file():
        raise FileNotFoundError(second_path)
    if first_path == second_path or first_path.samefile(second_path):
        raise ValueError("R3O comparison requires two distinct trace files.")


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
            f"Fresh R3O traces differ: {first_path} versus {second_path}."
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
            "Run two fresh continuous scheduled-epsilon collections through "
            "the fifth production optimizer update."
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
        raise FileExistsError(f"R3O output must be fresh: {output_directory}.")

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
    updates = accepted_trace["optimization"]["update_events"]
    fifth_update = updates[4]
    print(f"result={result_path}")
    print(f"first_trace={first_path}")
    print(f"second_trace={second_path}")
    print("fresh_processes=2")
    print("transitions=10016")
    print("scheduled_actions=10016")
    print("r3m_prefix_transitions=10012")
    print(f"completed_episodes={accepted_trace['completed_episode_count']}")
    print(f"truncation_events={len(accepted_trace['truncation_events'])}")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
