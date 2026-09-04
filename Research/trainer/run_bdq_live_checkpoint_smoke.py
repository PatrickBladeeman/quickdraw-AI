from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

import torch
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    DirectReplayCollector,
    LLAPIContractError,
    LinearEpsilonSchedule,
    ScheduledEpsilonGreedyBDQActionSelector,
    checkpoint_state_sha256,
    load_controller_checkpoint,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    canonical_json_sha256,
    replay_sample_fingerprint,
    run_fresh_python_process,
    run_fresh_worker_process,
    sha256_file,
    validate_runtime_and_package,
    validate_schema_pair,
)
from quickdraw_bdq.checkpoint import (  # noqa: E402
    CHECKPOINT_SCHEMA_VERSION,
    boundary_summary,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    configure_torch,
    execute_update_gate_worker,
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-live-checkpoint-contract-v1.json"
R3O_CONTRACT_PATH = HERE / "bdq-fifth-update-contract-v1.json"
R3P_CONTRACT_PATH = HERE / "bdq-checkpoint-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-live-checkpoint-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-live-checkpoint-result.schema.json"
)
R3O_CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-fifth-update-contract.schema.json"
)
R3P_CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-checkpoint-contract.schema.json"
)
R3O_RESULT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-fifth-update-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
TRACE_FILE_NAME = "r3q-live-checkpoint-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-fifth-update-trace.v1"
CHECKPOINT_FILE_NAME = "checkpoint.json"
SAVER_SUMMARY_FILE_NAME = "saver.json"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-live-checkpoint-result.v1"
WORKER_TIMEOUT_SECONDS = 1800


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LLAPIContractError(f"Expected a JSON object at {path}.")
    return value


def _write_json(value: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _binding_path(binding: Dict[str, Any]) -> Path:
    path = REPO_ROOT / binding["path"]
    if sha256_file(path) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    return path


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    result_schema = validate_schema_pair(
        contract,
        CONTRACT_SCHEMA_PATH,
        RESULT_SCHEMA_PATH,
    )
    r3o_binding = contract["base_fifth_update_contract"]
    r3o_path = _binding_path(r3o_binding)
    r3o_contract = _read_json(r3o_path)
    r3o_schema = _read_json(R3O_CONTRACT_SCHEMA_PATH)
    Draft202012Validator.check_schema(r3o_schema)
    Draft202012Validator(r3o_schema).validate(r3o_contract)
    if r3o_contract["schema_version"] != r3o_binding["schema_version"]:
        raise LLAPIContractError("R3Q's R3O schema binding drifted.")

    r3p_binding = contract["base_checkpoint_contract"]
    r3p_path = _binding_path(r3p_binding)
    r3p_contract = _read_json(r3p_path)
    r3p_schema = _read_json(R3P_CONTRACT_SCHEMA_PATH)
    Draft202012Validator.check_schema(r3p_schema)
    Draft202012Validator(r3p_schema).validate(r3p_contract)
    if r3p_contract["schema_version"] != r3p_binding["schema_version"]:
        raise LLAPIContractError("R3Q's checkpoint schema binding drifted.")
    if r3p_contract["base_fifth_update_contract"] != r3o_binding:
        raise LLAPIContractError("R3P no longer binds R3Q's frozen R3O contract.")

    validate_runtime_and_package(contract, "R3Q", pyproject_path=PYPROJECT_PATH)
    if contract["runtime"] != r3o_contract["runtime"]:
        raise LLAPIContractError("R3Q runtime differs from R3O.")
    if contract["package"] != r3o_contract["package"]:
        raise LLAPIContractError("R3Q package boundary differs from R3O.")
    for key in (
        "fresh_processes",
        "torch_num_threads",
        "torch_num_interop_threads",
        "deterministic_algorithms",
    ):
        if contract["determinism"][key] != r3o_contract["determinism"][key]:
            raise LLAPIContractError(
                f"R3Q determinism field {key} differs from R3O."
            )

    accepted = contract["accepted_live_boundary"]
    collection = r3o_contract["collection"]
    optimization = r3o_contract["optimization"]
    if accepted["transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3Q boundary count differs from R3O.")
    if accepted["decision_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3Q decision count differs from R3O.")
    if accepted["optimizer_update_count"] != optimization["expected_optimizer_updates"]:
        raise LLAPIContractError("R3Q optimizer count differs from R3O.")
    if accepted["target_sync_count"] != optimization["expected_target_synchronizations"]:
        raise LLAPIContractError("R3Q target-sync count differs from R3O.")
    if accepted["policy_seed"] != collection["policy_seed"]:
        raise LLAPIContractError("R3Q policy seed differs from R3O.")
    if accepted["exploration_seed"] != collection["exploration_seed"]:
        raise LLAPIContractError("R3Q exploration seed differs from R3O.")
    if accepted["target_network_sha256"] != r3o_contract["r3m_prefix"]["frozen_target_sha256"]:
        raise LLAPIContractError("R3Q target hash differs from R3O's frozen target.")
    if contract["checkpoint"]["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise LLAPIContractError("R3Q checkpoint schema version drifted.")
    if contract["checkpoint"]["contract_binding_sha256"] != r3p_binding["sha256"]:
        raise LLAPIContractError("R3Q checkpoint contract binding drifted.")
    if contract["checkpoint"]["sample_batch_size"] != optimization["batch_size"]:
        raise LLAPIContractError("R3Q sample size differs from R3O.")
    return result_schema


def _validate_live_trace(
    trace: Dict[str, Any],
    trace_path: Path,
    r3o_contract: Dict[str, Any],
    r3q_contract: Dict[str, Any],
) -> None:
    r3o_result_schema = _read_json(R3O_RESULT_SCHEMA_PATH)
    validate_update_gate_trace(
        trace,
        r3o_result_schema,
        contract_path=R3O_CONTRACT_PATH,
        task_name="R3Q live saver",
        require_update_hashes=True,
    )
    accepted = r3q_contract["accepted_live_boundary"]
    if canonical_json_sha256(trace) != accepted["canonical_trace_sha256"]:
        raise LLAPIContractError("R3Q live trace differs from accepted R3O evidence.")
    if sha256_file(trace_path) != accepted["serialized_trace_sha256"]:
        raise LLAPIContractError("R3Q live trace bytes differ from accepted R3O evidence.")
    if trace["completed_episode_count"] != accepted["completed_episode_count"]:
        raise LLAPIContractError("R3Q completed-episode count differs from R3O.")
    if len(trace["truncation_events"]) != accepted["truncation_event_count"]:
        raise LLAPIContractError("R3Q truncation count differs from R3O.")
    if trace["selector"]["action_tuple_counts"] != accepted["action_tuple_counts"]:
        raise LLAPIContractError("R3Q action histogram differs from R3O.")
    if trace["selector"]["selection_count"] != accepted["selection_count"]:
        raise LLAPIContractError("R3Q selection count differs from R3O.")
    if (
        trace["selector"]["last_selection_completed_transition_count"]
        != accepted["last_selection_completed_transition_count"]
    ):
        raise LLAPIContractError("R3Q last selection count differs from R3O.")
    if trace["cutoff"]["pending_agent_ids"] != accepted["pending_agent_ids"]:
        raise LLAPIContractError("R3Q live saver retained a pending decision.")
    optimization = trace["optimization"]
    if optimization["online_after_sha256"] != accepted["online_network_sha256"]:
        raise LLAPIContractError("R3Q online network hash differs from R3O.")
    if optimization["target_after_sha256"] != accepted["target_network_sha256"]:
        raise LLAPIContractError("R3Q target network hash differs from R3O.")
    fifth = optimization["update_events"][-1]
    expected_fifth = accepted["update_5"]
    if {
        key: fifth[key]
        for key in (
            "decision_count",
            "optimizer_update_count",
            "target_sync_count",
            "loss",
            "mean_absolute_td_error",
            "online_after_sha256",
        )
    } != expected_fifth:
        raise LLAPIContractError("R3Q update 5 differs from accepted R3O evidence.")
    if trace["scenario_seed"] != r3o_contract["collection"]["scenario_seed"]:
        raise LLAPIContractError("R3Q scenario seed differs from R3O.")


def _validate_boundary(
    boundary: Dict[str, Any],
    r3o_contract: Dict[str, Any],
    r3q_contract: Dict[str, Any],
) -> None:
    accepted = r3q_contract["accepted_live_boundary"]
    expected = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "controller_seed": r3o_contract["collection"]["policy_seed"],
        "exploration_seed": r3o_contract["collection"]["exploration_seed"],
        "decision_count": accepted["decision_count"],
        "optimizer_update_count": accepted["optimizer_update_count"],
        "target_sync_count": accepted["target_sync_count"],
        "online_network_sha256": accepted["online_network_sha256"],
        "target_network_sha256": accepted["target_network_sha256"],
        "pending_agent_ids": accepted["pending_agent_ids"],
    }
    for key, value in expected.items():
        if boundary[key] != value:
            raise LLAPIContractError(f"R3Q checkpoint boundary field {key} drifted.")

    replay = boundary["replay"]
    accepted_replay = accepted["replay"]
    for key in ("capacity", "size", "cursor", "max_accounted_storage_bytes"):
        if replay[key] != accepted_replay[key]:
            raise LLAPIContractError(f"R3Q replay boundary field {key} drifted.")
    if replay["frame_reference_count"] != (
        replay["size"] * accepted_replay["frame_reference_count_per_transition"]
    ):
        raise LLAPIContractError("R3Q replay frame reference accounting drifted.")
    if replay["accounted_storage_bytes"] + replay["remaining_accounted_storage_bytes"] != replay[
        "max_accounted_storage_bytes"
    ]:
        raise LLAPIContractError("R3Q replay remaining accounting drifted.")
    if replay["unique_frame_count"] <= 0 or replay["frame_payload_bytes"] <= 0:
        raise LLAPIContractError("R3Q replay omitted live frame accounting.")
    if replay["metadata_payload_bytes"] <= 0:
        raise LLAPIContractError("R3Q replay omitted metadata accounting.")


def _schedule(r3o_contract: Dict[str, Any]) -> LinearEpsilonSchedule:
    schedule = r3o_contract["epsilon_schedule"]
    return LinearEpsilonSchedule(
        replay_warmup_decisions=int(schedule["replay_warmup_decisions"]),
        decay_decisions=int(schedule["decay_decisions"]),
        initial_epsilon=float(schedule["initial_epsilon"]),
        final_epsilon=float(schedule["final_epsilon"]),
    )


def _run_live_saver_worker(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    r3o_contract: Dict[str, Any],
    r3q_contract: Dict[str, Any],
) -> Dict[str, Any]:
    checkpoint_path = worker_output / CHECKPOINT_FILE_NAME
    trace_path = worker_output / TRACE_FILE_NAME
    summary_path = worker_output / SAVER_SUMMARY_FILE_NAME

    def save_boundary(
        controller: Any,
        collector: DirectReplayCollector,
        selector: ScheduledEpsilonGreedyBDQActionSelector,
    ) -> None:
        boundary = boundary_summary(controller, selector, collector)
        _validate_boundary(boundary, r3o_contract, r3q_contract)
        state_digest = checkpoint_state_sha256(controller, collector, selector)
        batch = controller.replay.sample(
            int(r3o_contract["optimization"]["batch_size"])
        )
        _write_json(
            {
                "boundary": boundary,
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "checkpoint_bytes": checkpoint_path.stat().st_size,
                "checkpoint_state_sha256": state_digest,
                "checkpoint_contract_sha256": sha256_file(R3P_CONTRACT_PATH),
                "next_replay_sample": replay_sample_fingerprint(batch),
            },
            summary_path,
        )

    trace = execute_update_gate_worker(
        executable,
        worker_output,
        worker_index,
        r3o_contract,
        contract_path=R3O_CONTRACT_PATH,
        trace_file_name=TRACE_FILE_NAME,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        task_name="R3Q",
        record_update_hashes=True,
        timeout_wait=300,
        progress_interval=1_000,
        checkpoint_path=checkpoint_path,
        checkpoint_callback=save_boundary,
    )
    _validate_live_trace(trace, trace_path, r3o_contract, r3q_contract)
    if not checkpoint_path.is_file() or not summary_path.is_file():
        raise LLAPIContractError("R3Q live saver omitted its checkpoint result.")
    print(f"checkpoint={checkpoint_path}")
    print(f"summary={summary_path}")
    return trace


def _run_restorer_worker(
    checkpoint_path: Path,
    summary_path: Path,
    r3o_contract: Dict[str, Any],
    r3q_contract: Dict[str, Any],
) -> int:
    configure_torch(r3q_contract["determinism"], "R3Q restorer")
    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=BDQOptimizationSettings(),
        controller_seed=int(r3o_contract["collection"]["policy_seed"]),
        exploration_seed=int(r3o_contract["collection"]["exploration_seed"]),
        schedule=_schedule(r3o_contract),
    )
    _validate_boundary(loaded.verification, r3o_contract, r3q_contract)
    state_digest = checkpoint_state_sha256(
        loaded.controller,
        loaded.collector,
        loaded.selector,
    )
    batch = loaded.controller.replay.sample(
        int(r3o_contract["optimization"]["batch_size"])
    )
    _write_json(
        {
            "restored_boundary": loaded.verification,
            "restored_checkpoint_state_sha256": state_digest,
            "next_replay_sample": replay_sample_fingerprint(batch),
            "loaded_without_unity": True,
        },
        summary_path,
    )
    print(f"summary={summary_path}")
    return 0


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.mode == "restorer":
        if (
            arguments.env is not None
            or arguments.output is not None
            or arguments.worker_output is not None
            or arguments.worker_index is not None
            or arguments.checkpoint is None
            or arguments.summary is None
        ):
            raise ValueError(
                "Restorer mode requires only --mode, --checkpoint, and --summary."
            )
        return "restorer"
    if arguments.mode is not None:
        raise ValueError("Unknown R3Q worker mode.")
    if arguments.worker_output is not None:
        if (
            arguments.env is None
            or arguments.output is not None
            or arguments.checkpoint is not None
            or arguments.summary is not None
            or arguments.worker_index is None
        ):
            raise ValueError(
                "Live worker mode requires only --env, --worker-output, "
                "and --worker-index."
            )
        return "live-worker"
    if (
        arguments.env is None
        or arguments.output is None
        or arguments.worker_index is not None
        or arguments.checkpoint is not None
        or arguments.summary is not None
    ):
        raise ValueError("Parent mode requires --env and --output.")
    return "parent"


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Save the R3O live trainer boundary and restore it in a fresh "
            "Python process without Unity."
        )
    )
    parser.add_argument("--env", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--summary", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--mode",
        choices=["restorer"],
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    r3q_contract = _read_json(CONTRACT_PATH)
    result_schema = validate_contract(r3q_contract)
    r3o_contract = _read_json(R3O_CONTRACT_PATH)

    if mode == "restorer":
        assert arguments.checkpoint is not None
        assert arguments.summary is not None
        return _run_restorer_worker(
            arguments.checkpoint.resolve(),
            arguments.summary.resolve(),
            r3o_contract,
            r3q_contract,
        )

    if mode == "live-worker":
        assert arguments.env is not None
        assert arguments.worker_output is not None
        assert arguments.worker_index is not None
        executable = arguments.env.resolve()
        if not executable.is_file():
            raise FileNotFoundError(executable)
        _run_live_saver_worker(
            executable,
            arguments.worker_output.resolve(),
            arguments.worker_index,
            r3o_contract,
            r3q_contract,
        )
        print(f"trace={arguments.worker_output.resolve() / TRACE_FILE_NAME}")
        return 0

    assert arguments.env is not None
    assert arguments.output is not None
    executable = arguments.env.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    output_directory = arguments.output.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(f"R3Q output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)

    trace, trace_path = run_fresh_worker_process(
        runner_path=Path(__file__),
        executable=executable,
        output_directory=output_directory,
        worker_index=0,
        contract=r3o_contract,
        trace_file_name=TRACE_FILE_NAME,
        task_name="R3Q",
        announce=True,
        repo_root=REPO_ROOT,
        timeout_seconds=WORKER_TIMEOUT_SECONDS,
    )
    _validate_live_trace(trace, trace_path, r3o_contract, r3q_contract)
    saver_summary_path = trace_path.parent / SAVER_SUMMARY_FILE_NAME
    checkpoint_path = trace_path.parent / CHECKPOINT_FILE_NAME
    saver_summary = _read_json(saver_summary_path)
    restorer_summary_path = output_directory / "restored.json"
    run_fresh_python_process(
        runner_path=Path(__file__),
        arguments=[
            "--mode=restorer",
            f"--checkpoint={checkpoint_path}",
            f"--summary={restorer_summary_path}",
        ],
        output_directory=output_directory,
        log_name="restorer.log",
        task_name="R3Q restorer",
        contract=r3o_contract,
        repo_root=REPO_ROOT,
        timeout_seconds=WORKER_TIMEOUT_SECONDS,
        failure_label="Fresh R3Q restorer",
    )
    restored_summary = _read_json(restorer_summary_path)

    if saver_summary["checkpoint_contract_sha256"] != sha256_file(R3P_CONTRACT_PATH):
        raise LLAPIContractError("R3Q saver checkpoint contract binding drifted.")
    _validate_boundary(saver_summary["boundary"], r3o_contract, r3q_contract)
    _validate_boundary(restored_summary["restored_boundary"], r3o_contract, r3q_contract)
    if saver_summary["boundary"] != restored_summary["restored_boundary"]:
        raise LLAPIContractError("R3Q restored boundary differs from the live saver.")
    if saver_summary["checkpoint_state_sha256"] != restored_summary[
        "restored_checkpoint_state_sha256"
    ]:
        raise LLAPIContractError("R3Q restored state differs from the live saver.")
    if saver_summary["next_replay_sample"] != restored_summary["next_replay_sample"]:
        raise LLAPIContractError("R3Q next replay samples differ across processes.")
    if not restored_summary["loaded_without_unity"]:
        raise LLAPIContractError("R3Q restorer did not prove Unity-free loading.")

    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "base_r3o_contract_sha256": sha256_file(R3O_CONTRACT_PATH),
        "checkpoint_contract_sha256": sha256_file(R3P_CONTRACT_PATH),
        "live_trace_sha256": sha256_file(trace_path),
        "live_trace_canonical_sha256": canonical_json_sha256(trace),
        "checkpoint_sha256": saver_summary["checkpoint_sha256"],
        "checkpoint_bytes": saver_summary["checkpoint_bytes"],
        "saver_checkpoint_state_sha256": saver_summary[
            "checkpoint_state_sha256"
        ],
        "restorer_checkpoint_state_sha256": restored_summary[
            "restored_checkpoint_state_sha256"
        ],
        "fresh_process_count": 2,
        "clean_boundary_pending_agent_ids": [],
        "loaded_without_unity": True,
        "same_boundary_state": True,
        "same_next_replay_sample": True,
        "saver_boundary": saver_summary["boundary"],
        "restored_boundary": restored_summary["restored_boundary"],
        "saver_next_replay_sample": saver_summary["next_replay_sample"],
        "restorer_next_replay_sample": restored_summary["next_replay_sample"],
    }
    Draft202012Validator(result_schema).validate(result)
    result_path = output_directory / "result.json"
    _write_json(result, result_path)

    boundary = result["saver_boundary"]
    replay = boundary["replay"]
    print(f"result={result_path}")
    print(f"checkpoint={checkpoint_path}")
    print(f"checkpoint_sha256={result['checkpoint_sha256']}")
    print(f"checkpoint_bytes={result['checkpoint_bytes']}")
    print("fresh_processes=2")
    print(f"transitions={boundary['decision_count']}")
    print(f"optimizer_updates={boundary['optimizer_update_count']}")
    print(f"target_synchronizations={boundary['target_sync_count']}")
    print(f"replay_size={replay['size']}")
    print(f"replay_cursor={replay['cursor']}")
    print(f"replay_unique_frames={replay['unique_frame_count']}")
    print(f"replay_accounted_storage_bytes={replay['accounted_storage_bytes']}")
    print(f"online_network_sha256={boundary['online_network_sha256']}")
    print(f"target_network_sha256={boundary['target_network_sha256']}")
    print("clean_boundary=pass")
    print("same_boundary_state=pass")
    print("same_next_replay_sample=pass")
    print("loaded_without_unity=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
