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
    LinearEpsilonSchedule,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    PYPROJECT_PATH,
    canonical_json_sha256,
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


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract, CONTRACT_SCHEMA_PATH, RESULT_SCHEMA_PATH
    )

    binding = contract["base_scheduled_handoff_contract"]
    base_contract_path = REPO_ROOT / binding["path"]
    if sha256_file(base_contract_path) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    base_contract = json.loads(base_contract_path.read_text(encoding="utf-8"))
    if base_contract["schema_version"] != binding["schema_version"]:
        raise LLAPIContractError("R3K's R3J schema binding drifted.")

    validate_runtime_and_package(contract, "R3K", pyproject_path=PYPROJECT_PATH)
    for key in ("runtime", "package", "transport"):
        if contract[key] != base_contract[key]:
            raise LLAPIContractError(f"R3K {key} differs from R3J.")

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError("R3K differs from production optimizer defaults.")
    expected_updates = [
        settings.replay_warmup_decisions
        + index * settings.optimizer_update_interval_decisions
        for index in range(3)
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError("R3K update decisions differ from its schedule.")
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError("R3K must stop after optimizer update 3.")
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError("R3K must not synchronize the target network.")

    collection = contract["collection"]
    if collection["transition_limit"] != expected_updates[-1]:
        raise LLAPIContractError("R3K cutoff must equal optimizer update 3.")
    if collection["scheduled_transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3K must schedule every collected action.")
    for key in ("scenario_seed", "policy_seed", "exploration_seed", "selector"):
        if collection[key] != base_contract["collection"][key]:
            raise LLAPIContractError(f"R3K collection {key} differs from R3J.")

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
            raise LLAPIContractError(f"R3K epsilon schedule {key} differs from R3J.")
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
        raise LLAPIContractError("R3K epsilon samples differ from its schedule.")
    if schedule_contract["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3K selector count differs from its cutoff.")
    if schedule_contract["full_exploration_selection_count"] != (
        schedule.replay_warmup_decisions + 1
    ):
        raise LLAPIContractError("R3K full-exploration count drifted.")
    if schedule_contract["decay_selection_count"] != (
        collection["transition_limit"]
        - schedule_contract["full_exploration_selection_count"]
    ):
        raise LLAPIContractError("R3K decay-selection count drifted.")
    if schedule_contract["last_selection_completed_transition_count"] != (
        collection["transition_limit"] - 1
    ):
        raise LLAPIContractError("R3K selected an action after update 3.")

    prefix = contract["r3j_prefix"]
    if prefix["transition_count"] != base_contract["collection"][
        "transition_limit"
    ]:
        raise LLAPIContractError("R3K prefix does not contain all of R3J.")
    for key in (
        "online_after_first_update_sha256",
        "online_after_second_update_sha256",
        "frozen_target_sha256",
        "first_update_loss",
        "first_update_mean_absolute_td_error",
        "second_update_loss",
        "second_update_mean_absolute_td_error",
    ):
        if prefix[key] != base_contract["r3g_prefix"][key]:
            raise LLAPIContractError(f"R3K prefix {key} differs from R3J.")

    boundary = contract["third_update_boundary"]
    if boundary["continuation_after_transition_count"] != prefix[
        "transition_count"
    ]:
        raise LLAPIContractError("R3K continuation does not begin after R3J.")
    if boundary["new_transition_count"] != (
        collection["transition_limit"] - prefix["transition_count"]
    ):
        raise LLAPIContractError("R3K continuation is not exactly three transitions.")
    if boundary["first_new_selection_completed_transition_count"] != prefix[
        "transition_count"
    ]:
        raise LLAPIContractError("R3K first new selection is not contiguous.")
    if boundary["last_new_selection_completed_transition_count"] != (
        collection["transition_limit"] - 1
    ):
        raise LLAPIContractError("R3K last new selection count drifted.")
    if boundary["completion_decision_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3K completion count differs from its cutoff.")
    if boundary["optimizer_update_count_before_continuation"] != 2:
        raise LLAPIContractError("R3K does not continue after R3J update 2.")
    if boundary["optimizer_update_count_after_completion"] != len(
        expected_updates
    ):
        raise LLAPIContractError("R3K completion is not optimizer update 3.")
    if boundary["target_sync_count_after_completion"] != 0:
        raise LLAPIContractError("R3K boundary includes a target synchronization.")
    if boundary["select_action_after_third_update"]:
        raise LLAPIContractError("R3K must stop before a post-update action.")
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
    prefix = contract["r3j_prefix"]
    prefix_count = int(prefix["transition_count"])
    if canonical_json_sha256(trace["transitions"][:prefix_count]) != prefix[
        "canonical_transitions_sha256"
    ]:
        raise LLAPIContractError("R3K did not preserve the canonical R3J prefix.")

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
    )
    for event, (online_hash, loss, td_error) in zip(
        events[:2], expected_prefix_events
    ):
        if event["online_after_sha256"] != online_hash:
            raise LLAPIContractError("R3K changed an R3J post-update online hash.")
        if event["loss"] != loss or event["mean_absolute_td_error"] != td_error:
            raise LLAPIContractError("R3K changed an R3J optimizer metric.")

    third_update = events[2]
    if third_update["online_after_sha256"] == prefix[
        "online_after_second_update_sha256"
    ]:
        raise LLAPIContractError("R3K update 3 did not change the online network.")
    if optimization["online_after_sha256"] != third_update[
        "online_after_sha256"
    ]:
        raise LLAPIContractError("R3K final online hash differs from update 3.")
    if optimization["target_before_sha256"] != prefix[
        "frozen_target_sha256"
    ] or optimization["target_after_sha256"] != prefix["frozen_target_sha256"]:
        raise LLAPIContractError("R3K changed the frozen R3J target network.")

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
        raise LLAPIContractError("R3K trace epsilon samples drifted.")
    for key in (
        "selection_count",
        "full_exploration_selection_count",
        "decay_selection_count",
        "first_decay_completed_transition_count",
        "last_selection_completed_transition_count",
    ):
        if selector[key] != schedule_contract[key]:
            raise LLAPIContractError(f"R3K selector {key} drifted.")
    if selector["completed_transition_count_source"] != schedule_contract[
        "completed_transition_count_source"
    ]:
        raise LLAPIContractError("R3K selector counter source drifted.")
    if selector["last_selection_completed_transition_count"] >= trace["replay"][
        "decision_count"
    ]:
        raise LLAPIContractError("R3K selected an action after update 3.")


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
        task_name="R3K",
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
        task_name="R3K",
        announce=True,
        repo_root=REPO_ROOT,
        timeout_seconds=1800,
    )


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run two fresh continuous scheduled-epsilon collections through "
            "the third production optimizer update."
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
        raise FileExistsError(f"R3K output must be fresh: {output_directory}.")
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
        task_name="R3K",
        validate_trace=validate_trace,
    )
    updates = first["optimization"]["update_events"]
    third_update = updates[2]
    print(f"result={result_path}")
    print("fresh_processes=2")
    print("transitions=10008")
    print("scheduled_actions=10008")
    print("r3j_prefix_transitions=10005")
    print(f"completed_episodes={first['completed_episode_count']}")
    print(f"truncation_events={len(first['truncation_events'])}")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
