"""Run the bounded R3S live-resume and learned-network export gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from importlib.metadata import version
from multiprocessing.connection import Client, Connection, Listener
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import onnx
import onnxruntime as ort
import torch
from jsonschema import Draft202012Validator
from mlagents_envs.base_env import ActionTuple
from mlagents_envs.environment import UnityEnvironment


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    canonical_json_sha256,
    copy_complete_player,
    masks_to_json,
    run_fresh_python_process,
    run_fresh_worker_process,
    transition_to_json,
    validate_runtime_and_package,
)
from quickdraw_bdq.action_space import greedy_actions  # noqa: E402
from quickdraw_bdq.checkpoint import (  # noqa: E402
    boundary_summary,
    checkpoint_state_sha256,
    load_controller_checkpoint,
    save_controller_checkpoint,
)
from quickdraw_bdq.exploration import LinearEpsilonSchedule  # noqa: E402
from quickdraw_bdq.llapi import (  # noqa: E402
    BASIC_BEHAVIOR_NAME,
    BasicTruncationMaskSideChannel,
    LLAPIContractError,
    network_sha256,
    observation_sha256,
    read_action_masks,
    validate_action_masks,
    validate_observation,
)
from quickdraw_bdq.optimizer import BDQOptimizationSettings  # noqa: E402
from quickdraw_bdq.provenance import (  # noqa: E402
    directory_file_manifest,
    process_creation_marker,
    runtime_contract,
    sha256_file,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    configure_torch,
    execute_update_gate_worker,
)
from run_bdq_long_horizon_smoke import (  # noqa: E402
    _stage_contract as r3r_stage_contract,
    _validate_prefix_boundary as validate_r3r_prefix_boundary,
    _validate_trace as validate_r3r_trace,
)


CONTRACT_PATH = HERE / "bdq-live-resume-export-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-live-resume-export-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-live-resume-export-result.schema.json"
)
R3R_RESULT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-long-horizon-smoke-result.schema.json"
)
RESULT_SCHEMA_VERSION = "quickdraw.bdq-live-resume-export-result.v1"
TASK_NAME = "R3S"
R3R_TRACE_FILE_NAME = "r3r-start-trace.json"
R3R_CHECKPOINT_FILE_NAME = "r3r-start-checkpoint.json"
LIVE_RESULT_FILE_NAME = "live-resume-result.json"
HANDOFF_MANIFEST_FILE_NAME = "handoff-manifest.json"
ATTEMPT_FILE_NAME = "attempt.json"
FINAL_CHECKPOINT_FILE_NAME = "post-resume-checkpoint.json"
POST_RESUME_OBSERVATION_FILE_NAME = "post-resume-observation.npy"
CORPUS_FILE_NAME = "parity-corpus.npz"
CORPUS_METADATA_FILE_NAME = "parity-corpus.json"
ONNX_FILE_NAME = "accepted-r3r-online.onnx"
EXPORT_METADATA_FILE_NAME = "export-metadata.json"
HANDOFF_AUTH_ENV = "QUICKDRAW_R3S_HANDOFF_AUTH"
BASE_WORKER_PORT = 5_145
LIVE_WORKER_TIMEOUT_SECONDS = 14_400
HANDOFF_TIMEOUT_SECONDS = 600


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LLAPIContractError(f"JSON root is not an object: {path}.")
    return value


def _write_json(value: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _array_sha256(values: Sequence[tuple[str, np.ndarray]]) -> str:
    digest = hashlib.sha256()
    for name, raw in values:
        value = np.ascontiguousarray(raw)
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(json.dumps(list(value.shape), separators=(",", ":")).encode())
        digest.update(b"\0")
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _bound_path(binding: Dict[str, Any], *, repo_root: Path) -> Path:
    path = (repo_root / binding["path"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if actual != binding["sha256"]:
        raise LLAPIContractError(f"Hash binding drifted: {binding['path']}.")
    return path


def _schedule(r3r_contract: Dict[str, Any]) -> LinearEpsilonSchedule:
    schedule = r3r_contract["epsilon_schedule"]
    return LinearEpsilonSchedule(
        replay_warmup_decisions=int(schedule["replay_warmup_decisions"]),
        decay_decisions=int(schedule["decay_decisions"]),
        initial_epsilon=float(schedule["initial_epsilon"]),
        final_epsilon=float(schedule["final_epsilon"]),
    )


def _synchronization_collection(r3r_contract: Dict[str, Any]) -> Dict[str, Any]:
    return r3r_contract["stages"]["synchronization"]["collection"]


def _validate_starting_relationships(
    contract: Dict[str, Any],
    r3r_contract: Dict[str, Any],
    r3r_result: Dict[str, Any],
    r3r_trace: Dict[str, Any],
    checkpoint: Dict[str, Any],
) -> None:
    accepted = contract["accepted_r3r"]
    boundary = accepted["boundary"]
    canonical_trace = r3r_result["canonical_trace"]
    if r3r_contract["schema_version"] != contract["base_r3r_contract"][
        "schema_version"
    ]:
        raise LLAPIContractError("R3S R3R contract schema binding drifted.")
    if r3r_result["schema_version"] != accepted["result"]["schema_version"]:
        raise LLAPIContractError("R3S accepted result schema binding drifted.")
    if r3r_result["contract_sha256"] != contract["base_r3r_contract"]["sha256"]:
        raise LLAPIContractError("R3S accepted result contract binding drifted.")
    if r3r_result["stage"] != "synchronization":
        raise LLAPIContractError("R3S accepted result is not the sync stage.")
    if r3r_result["canonical_trace_sha256"] != accepted[
        "canonical_trace_sha256"
    ] or canonical_json_sha256(canonical_trace) != accepted[
        "canonical_trace_sha256"
    ]:
        raise LLAPIContractError("R3S accepted canonical trace binding drifted.")
    if r3r_trace != canonical_trace:
        raise LLAPIContractError("R3S accepted trace differs from its result.")
    final = canonical_trace["final_clean_boundary"]
    for key in (
        "transition_count",
        "decision_count",
        "optimizer_update_count",
        "target_sync_count",
        "last_selection_completed_transition_count",
        "pending_agent_ids",
        "post_boundary_action_selected",
    ):
        if final[key] != boundary[key]:
            raise LLAPIContractError(f"R3S accepted boundary {key} drifted.")
    optimization = canonical_trace["optimization"]
    if optimization["online_after_sha256"] != boundary["online_network_sha256"]:
        raise LLAPIContractError("R3S accepted online network drifted.")
    if optimization["target_after_sha256"] != boundary["target_network_sha256"]:
        raise LLAPIContractError("R3S accepted target network drifted.")
    if optimization["target_before_sha256"] != boundary[
        "target_before_sync_sha256"
    ]:
        raise LLAPIContractError("R3S accepted pre-sync target drifted.")
    storage = canonical_trace["replay"]["storage"]
    for key, accepted_key in (
        ("capacity", "replay_capacity"),
        ("size", "replay_size"),
        ("cursor", "replay_cursor"),
        ("frame_reference_count", "frame_reference_count"),
        ("max_accounted_storage_bytes", "maximum_accounted_storage_bytes"),
    ):
        if storage[key] != boundary[accepted_key]:
            raise LLAPIContractError(f"R3S accepted replay {key} drifted.")
    if checkpoint["state_sha256"] != accepted["checkpoint"]["state_sha256"]:
        raise LLAPIContractError("R3S accepted checkpoint state hash drifted.")


def validate_contract(
    contract: Dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Validate schema and every hash-bound prerequisite before relationships."""

    contract_schema = _read_json(CONTRACT_SCHEMA_PATH)
    result_schema = _read_json(RESULT_SCHEMA_PATH)
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)

    validate_runtime_and_package(contract, TASK_NAME)
    if sha256_file(repo_root / contract["package"]["metadata_path"]) != contract[
        "package"
    ]["metadata_sha256"]:
        raise LLAPIContractError("R3S package metadata hash drifted.")
    for dependency in ("base_support_lock", "cpu_parity_lock"):
        _bound_path(contract["export_dependencies"][dependency], repo_root=repo_root)
    if version("onnx") != contract["export_dependencies"]["onnx"]:
        raise LLAPIContractError("The active ONNX package differs from R3S.")
    if version("onnxruntime") != contract["export_dependencies"]["onnxruntime"]:
        raise LLAPIContractError("The active ONNX Runtime package differs from R3S.")

    r3r_contract_path = _bound_path(contract["base_r3r_contract"], repo_root=repo_root)
    result_path = _bound_path(contract["accepted_r3r"]["result"], repo_root=repo_root)
    trace_path = _bound_path(contract["accepted_r3r"]["trace"], repo_root=repo_root)
    checkpoint_path = _bound_path(
        contract["accepted_r3r"]["checkpoint"], repo_root=repo_root
    )
    source_executable = (repo_root / contract["player"]["source_executable"]).resolve()
    if not source_executable.is_file():
        raise FileNotFoundError(source_executable)
    if sha256_file(source_executable) != contract["player"]["executable_sha256"]:
        raise LLAPIContractError("R3S accepted player executable hash drifted.")
    player_manifest = directory_file_manifest(source_executable.parent)
    if canonical_json_sha256(player_manifest) != contract["player"][
        "source_manifest_sha256"
    ]:
        raise LLAPIContractError("R3S accepted player manifest drifted.")
    if player_manifest["file_count"] != contract["player"][
        "source_file_count"
    ] or player_manifest["total_bytes"] != contract["player"]["source_total_bytes"]:
        raise LLAPIContractError("R3S accepted player manifest accounting drifted.")
    for sibling in contract["player"]["required_siblings"]:
        if not (source_executable.parent / sibling).exists():
            raise FileNotFoundError(source_executable.parent / sibling)

    r3r_contract = _read_json(r3r_contract_path)
    r3r_result = _read_json(result_path)
    r3r_trace = _read_json(trace_path)
    checkpoint = _read_json(checkpoint_path)
    _validate_starting_relationships(
        contract, r3r_contract, r3r_result, r3r_trace, checkpoint
    )
    return result_schema, r3r_contract, r3r_result


def _verify_loaded_start(
    loaded: Any,
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    accepted = contract["accepted_r3r"]
    expected = accepted["boundary"]
    actual = loaded.verification
    for key in (
        "decision_count",
        "optimizer_update_count",
        "target_sync_count",
        "pending_agent_ids",
    ):
        if actual[key] != expected[key]:
            raise LLAPIContractError(f"R3S restored starting {key} drifted.")
    if actual["online_network_sha256"] != expected["online_network_sha256"]:
        raise LLAPIContractError("R3S restored online network hash drifted.")
    if actual["target_network_sha256"] != expected["target_network_sha256"]:
        raise LLAPIContractError("R3S restored target network hash drifted.")
    if checkpoint_state_sha256(
        loaded.controller, loaded.collector, loaded.selector
    ) != accepted["checkpoint"]["state_sha256"]:
        raise LLAPIContractError("R3S restored checkpoint state drifted.")
    return actual


class AuditedUnityEnvironment(UnityEnvironment):
    """Count the only Unity operations relevant to the R3S handoff claim."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.reset_count = 0
        self.step_count = 0
        self.set_actions_count = 0
        super().__init__(*args, **kwargs)

    def reset(self) -> None:
        self.reset_count += 1
        super().reset()

    def set_actions(self, behavior_name: str, action: ActionTuple) -> None:
        self.set_actions_count += 1
        super().set_actions(behavior_name, action)

    def step(self) -> None:
        self.step_count += 1
        super().step()


def _process_identity(pid: int, executable: Path) -> Dict[str, Any]:
    return {
        "pid": pid,
        "creation_marker": process_creation_marker(pid),
        "executable_sha256": sha256_file(executable),
    }


def _command_arguments(arguments: str | Sequence[Any]) -> list[str]:
    if isinstance(arguments, str):
        return [arguments]
    return [str(value) for value in arguments]


def _assert_process_stopped(identity: Dict[str, Any], timeout_seconds: float = 10.0) -> None:
    """Reject an attempt while its exact Unity process is still alive."""

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            marker = process_creation_marker(int(identity["pid"]))
        except ProcessLookupError:
            return
        if marker != identity["creation_marker"]:
            return
        if time.monotonic() >= deadline:
            raise LLAPIContractError("R3S Unity player process leaked after its attempt.")
        time.sleep(0.1)


def _recv(connection: Connection, expected_type: str) -> Dict[str, Any]:
    if not connection.poll(HANDOFF_TIMEOUT_SECONDS):
        raise TimeoutError(f"R3S timed out waiting for {expected_type}.")
    message = connection.recv()
    if not isinstance(message, dict) or message.get("type") != expected_type:
        raise LLAPIContractError(f"R3S handoff expected {expected_type}.")
    return message


def _boundary_decision(
    environment: UnityEnvironment,
    behavior_id: str,
    trace: Dict[str, Any],
) -> Dict[str, Any]:
    decision_steps, terminal_steps = environment.get_steps(behavior_id)
    if len(decision_steps) != 1:
        raise LLAPIContractError(
            "R3S handoff requires one pre-existing live DecisionStep."
        )
    agent_id = int(decision_steps.agent_id[0])
    if len(terminal_steps) > 1 or (
        len(terminal_steps) == 1 and int(terminal_steps.agent_id[0]) != agent_id
    ):
        raise LLAPIContractError("R3S handoff observed a changed agent identity.")
    observation = validate_observation(
        decision_steps.obs[0][0], "R3S existing decision observation"
    )
    masks = read_action_masks(decision_steps, 0)
    last_episode = trace["episodes"][-1]
    episode_decision_index = (
        int(last_episode["transition_count"])
        if last_episode["end_kind"] == "collection_cutoff"
        else 0
    )
    return {
        "type": "boundary",
        "protocol": "quickdraw.r3s-local-supervisor-handoff.v1",
        "behavior_id": behavior_id,
        "agent_id": agent_id,
        "observation": np.array(observation, dtype=np.float32, copy=True),
        "action_masks": tuple(np.array(mask, copy=True) for mask in masks),
        "episode_index": int(trace["cutoff"]["active_episode_index"]),
        "episode_decision_index": episode_decision_index,
        "completed_transition_count": 49996,
    }


def _step_resumed_action(
    environment: AuditedUnityEnvironment,
    behavior_id: str,
    side_channel: BasicTruncationMaskSideChannel,
    boundary: Dict[str, Any],
    action: Sequence[int],
    event_log: list[str],
) -> Dict[str, Any]:
    validated_masks = validate_action_masks(
        boundary["action_masks"], "R3S transferred action masks"
    )
    if len(action) != 2:
        raise LLAPIContractError("R3S resumed action must contain two branches.")
    for branch, selected in enumerate(action):
        if type(selected) is not int or validated_masks[branch][selected]:
            raise LLAPIContractError("R3S restored trainer selected an illegal action.")
    environment.set_actions(
        behavior_id,
        ActionTuple(discrete=np.asarray([action], dtype=np.int32)),
    )
    event_log.append("resumed_action_applied")
    environment.step()
    event_log.append("unity_stepped_once")
    decision_steps, terminal_steps = environment.get_steps(behavior_id)
    agent_id = int(boundary["agent_id"])
    terminal_rows = np.flatnonzero(terminal_steps.agent_id == agent_id)
    decision_rows = np.flatnonzero(decision_steps.agent_id == agent_id)
    if terminal_rows.size == 1:
        row = int(terminal_rows[0])
        next_observation = validate_observation(
            terminal_steps.obs[0][row], "R3S terminal next observation"
        )
        reward = float(terminal_steps.reward[row])
        interrupted = bool(terminal_steps.interrupted[row])
        if interrupted:
            event = side_channel.take(
                int(boundary["episode_index"]),
                int(boundary["episode_decision_index"]) + 1,
            )
            next_masks = event.action_masks
        else:
            next_masks = (
                np.zeros(3, dtype=np.bool_),
                np.zeros(2, dtype=np.bool_),
            )
        terminated = not interrupted
        truncated = interrupted
    elif terminal_rows.size == 0 and decision_rows.size == 1:
        row = int(decision_rows[0])
        next_observation = validate_observation(
            decision_steps.obs[0][row], "R3S decision next observation"
        )
        reward = float(decision_steps.reward[row])
        next_masks = read_action_masks(decision_steps, row)
        terminated = False
        truncated = False
    else:
        raise LLAPIContractError(
            "R3S resumed action did not complete exactly once for the same agent."
        )
    side_channel.assert_empty()
    return {
        "type": "outcome",
        "behavior_id": behavior_id,
        "agent_id": agent_id,
        "reward": reward,
        "next_observation": np.array(next_observation, dtype=np.float32, copy=True),
        "next_action_masks": tuple(np.array(mask, copy=True) for mask in next_masks),
        "terminated": terminated,
        "truncated": truncated,
        "held_decision_agent_ids": [int(value) for value in decision_steps.agent_id],
        "terminal_agent_ids": [int(value) for value in terminal_steps.agent_id],
    }


def _run_handoff_supervisor(
    environment: AuditedUnityEnvironment,
    behavior_id: str,
    side_channel: BasicTruncationMaskSideChannel,
    worker_output: Path,
    checkpoint_path: Path,
    trace_path: Path,
    contract: Dict[str, Any],
    player_executable: Path,
) -> None:
    if sha256_file(trace_path) != contract["accepted_r3r"]["trace"]["sha256"]:
        raise LLAPIContractError("R3S reconstructed R3R trace hash drifted.")
    if sha256_file(checkpoint_path) != contract["accepted_r3r"]["checkpoint"][
        "sha256"
    ]:
        raise LLAPIContractError("R3S reconstructed R3R checkpoint hash drifted.")
    event_log = [
        "r3r_boundary_verified",
        "checkpoint_saved",
        "initial_trainer_detached_without_action",
    ]
    trace = _read_json(trace_path)
    boundary = _boundary_decision(environment, behavior_id, trace)
    expected_counters = contract["live_handoff"]["environment_counters"]
    if (
        environment.reset_count != expected_counters["resets_before_handoff"]
        or environment.step_count != expected_counters["steps_before_handoff"]
        or environment.set_actions_count != expected_counters["steps_before_handoff"]
    ):
        raise LLAPIContractError("R3S Unity operation counters drifted before handoff.")
    player_process = environment._process
    if player_process is None or player_process.poll() is not None:
        raise LLAPIContractError("R3S Unity player is not live at handoff.")
    player_before = _process_identity(player_process.pid, player_executable)

    authkey = secrets.token_bytes(32)
    listener = Listener(("127.0.0.1", 0), family="AF_INET", authkey=authkey)
    listener._listener._socket.settimeout(HANDOFF_TIMEOUT_SECONDS)  # type: ignore[attr-defined]
    host, port = listener.address
    child_output = worker_output / "restored-trainer"
    child_output.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--mode=restored-trainer",
        f"--checkpoint={checkpoint_path}",
        f"--worker-output={child_output}",
        f"--handoff-host={host}",
        f"--handoff-port={port}",
    ]
    process_environment = dict(os.environ)
    process_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process_environment["OMP_NUM_THREADS"] = "1"
    process_environment["MKL_NUM_THREADS"] = "1"
    process_environment[HANDOFF_AUTH_ENV] = authkey.hex()
    child_log = worker_output / "restored-trainer.log"
    child_process: subprocess.Popen[str] | None = None
    connection: Connection | None = None
    try:
        with child_log.open("w", encoding="utf-8") as log:
            child_process = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                env=process_environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            event_log.append("restored_trainer_started")
            connection = listener.accept()
            ready = _recv(connection, "ready")
            restored_identity = ready["trainer_identity"]
            if (
                not isinstance(restored_identity, dict)
                or set(restored_identity)
                != {"pid", "creation_marker", "executable_sha256"}
                or restored_identity["creation_marker"]
                != process_creation_marker(int(restored_identity["pid"]))
                or restored_identity["executable_sha256"]
                != sha256_file(Path(sys.executable))
            ):
                raise LLAPIContractError("R3S restored trainer identity drifted.")
            if int(restored_identity["pid"]) == os.getpid():
                raise LLAPIContractError("R3S did not start a fresh trainer process.")
            if (
                ready["checkpoint_state_sha256"]
                != contract["accepted_r3r"]["checkpoint"]["state_sha256"]
            ):
                raise LLAPIContractError("R3S restored trainer state hash drifted.")
            event_log.append("checkpoint_restored")
            connection.send(boundary)
            event_log.append("existing_decision_transferred")
            selection = _recv(connection, "selection")
            if int(selection["agent_id"]) != int(boundary["agent_id"]):
                raise LLAPIContractError("R3S selected for a changed agent identity.")
            event_log.append("resumed_action_selected")
            outcome = _step_resumed_action(
                environment,
                behavior_id,
                side_channel,
                boundary,
                selection["action"],
                event_log,
            )
            connection.send(outcome)
            completed = _recv(connection, "completed")
            event_log.append("transition_49997_completed")
            return_code = child_process.wait(timeout=HANDOFF_TIMEOUT_SECONDS)
            if return_code != 0:
                raise RuntimeError(
                    f"Fresh R3S restored trainer failed with exit code {return_code}; "
                    f"see {child_log}."
                )
    finally:
        if connection is not None:
            connection.close()
        listener.close()
        if child_process is not None and child_process.poll() is None:
            child_process.terminate()
            try:
                child_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child_process.kill()
                child_process.wait(timeout=10)
    if environment.reset_count != 1 or environment.step_count != 49997:
        raise LLAPIContractError("R3S Unity operation counters drifted after handoff.")
    if environment.set_actions_count != 49997:
        raise LLAPIContractError("R3S applied an unexpected number of actions.")
    if player_process.poll() is not None:
        raise LLAPIContractError("R3S Unity player exited during trainer handoff.")
    player_after = _process_identity(player_process.pid, player_executable)
    if player_before != player_after:
        raise LLAPIContractError("R3S Unity process identity changed during handoff.")
    if completed["result_sha256"] != sha256_file(child_output / LIVE_RESULT_FILE_NAME):
        raise LLAPIContractError("R3S restored trainer result hash drifted.")
    event_log.append("final_clean_boundary_verified")

    event_sequence = contract["live_handoff"]["canonical_event_sequence"]
    if event_log != event_sequence:
        raise LLAPIContractError("R3S observed handoff event sequence drifted.")
    manifest = {
        "schema_version": "quickdraw.r3s-handoff-manifest.v1",
        "canonical": {
            "protocol": contract["live_handoff"]["protocol"],
            "event_sequence": event_log,
            "environment_counters": {
                "launches": 1,
                "resets_before_handoff": environment.reset_count,
                "steps_before_handoff": environment.step_count - 1,
                "resumed_actions": environment.set_actions_count - 49996,
                "steps_after_handoff": environment.step_count,
            },
            "behavior_id": behavior_id,
            "agent_id": int(boundary["agent_id"]),
            "same_player_process": True,
            "same_player_copy": True,
            "fresh_trainer_process": True,
            "reset_during_handoff": False,
            "relaunch_during_handoff": False,
            "extra_environment_step": False,
            "discarded_decision": False,
        },
        "provenance": {
            "initial_trainer_identity": _process_identity(os.getpid(), Path(sys.executable)),
            "restored_trainer_identity": restored_identity,
            "player_identity_before": player_before,
            "player_identity_after": player_after,
            "player_copy": str(player_executable.parent.resolve()),
            "player_launch_command": _command_arguments(player_process.args),
            "restored_trainer_command": command,
            "loopback_host": host,
            "loopback_port": port,
            "restored_trainer_log": str(child_log.resolve()),
        },
    }
    _write_json(manifest, worker_output / HANDOFF_MANIFEST_FILE_NAME)


def _run_restored_trainer(
    checkpoint_path: Path,
    worker_output: Path,
    host: str,
    port: int,
    contract: Dict[str, Any],
    r3r_contract: Dict[str, Any],
) -> int:
    configure_torch(r3r_contract["determinism"], "R3S restored trainer")
    synchronization_collection = _synchronization_collection(r3r_contract)
    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=BDQOptimizationSettings(),
        controller_seed=int(synchronization_collection["policy_seed"]),
        exploration_seed=int(synchronization_collection["exploration_seed"]),
        schedule=_schedule(r3r_contract),
    )
    starting_summary = _verify_loaded_start(loaded, contract)
    auth_hex = os.environ.pop(HANDOFF_AUTH_ENV, None)
    if auth_hex is None:
        raise LLAPIContractError("R3S restored trainer omitted handoff authentication.")
    connection = Client((host, port), family="AF_INET", authkey=bytes.fromhex(auth_hex))
    try:
        trainer_identity = _process_identity(os.getpid(), Path(sys.executable))
        connection.send(
            {
                "type": "ready",
                "trainer_identity": trainer_identity,
                "starting_summary": starting_summary,
                "checkpoint_state_sha256": checkpoint_state_sha256(
                    loaded.controller, loaded.collector, loaded.selector
                ),
            }
        )
        boundary = _recv(connection, "boundary")
        if boundary["protocol"] != contract["live_handoff"]["protocol"]:
            raise LLAPIContractError("R3S handoff protocol drifted.")
        if boundary["behavior_id"] != f"{BASIC_BEHAVIOR_NAME}?team=0":
            raise LLAPIContractError("R3S handoff behavior identity drifted.")
        if boundary["completed_transition_count"] != starting_summary["decision_count"]:
            raise LLAPIContractError("R3S transferred decision count drifted.")
        observation = validate_observation(
            boundary["observation"], "R3S transferred observation"
        )
        masks = validate_action_masks(
            boundary["action_masks"], "R3S transferred action masks"
        )
        agent_id = int(boundary["agent_id"])
        action = loaded.selector.select(
            observation,
            masks,
            completed_transition_count=loaded.controller.decision_count,
        )
        loaded.collector.begin(agent_id, observation, action, masks)
        connection.send(
            {
                "type": "selection",
                "agent_id": agent_id,
                "action": [int(value) for value in action],
                "observation_sha256": observation_sha256(observation),
                "action_masks": masks_to_json(masks),
            }
        )
        outcome = _recv(connection, "outcome")
        if outcome["behavior_id"] != boundary["behavior_id"] or int(
            outcome["agent_id"]
        ) != agent_id:
            raise LLAPIContractError("R3S outcome behavior or agent identity drifted.")
        next_observation = validate_observation(
            outcome["next_observation"], "R3S resumed next observation"
        )
        next_masks = validate_action_masks(
            outcome["next_action_masks"], "R3S resumed next action masks"
        )
        transition, optimization = loaded.collector.complete(
            agent_id,
            float(outcome["reward"]),
            next_observation,
            next_masks,
            terminated=bool(outcome["terminated"]),
            truncated=bool(outcome["truncated"]),
        )
        final_expected = contract["live_handoff"]["final_boundary"]
        if optimization.updated or optimization.target_synced:
            raise LLAPIContractError("R3S executed an unauthorized optimizer event.")
        final_summary = boundary_summary(
            loaded.controller, loaded.selector, loaded.collector
        )
        for key in (
            "decision_count",
            "optimizer_update_count",
            "target_sync_count",
            "pending_agent_ids",
        ):
            if final_summary[key] != final_expected[key]:
                raise LLAPIContractError(f"R3S final {key} drifted.")
        if final_summary["online_network_sha256"] != contract["export"][
            "source_network_sha256"
        ] or final_summary["target_network_sha256"] != contract["export"][
            "source_network_sha256"
        ]:
            raise LLAPIContractError("R3S network changed during live resume.")
        final_checkpoint = worker_output / FINAL_CHECKPOINT_FILE_NAME
        save_controller_checkpoint(
            final_checkpoint,
            loaded.controller,
            loaded.collector,
            loaded.selector,
        )
        observation_path = worker_output / POST_RESUME_OBSERVATION_FILE_NAME
        np.save(observation_path, next_observation, allow_pickle=False)
        transition_record = transition_to_json(
            transition,
            49996,
            int(boundary["episode_index"]),
            int(boundary["episode_decision_index"]),
        )
        result = {
            "schema_version": "quickdraw.r3s-live-resume-attempt.v1",
            "start_boundary": contract["live_handoff"]["start_boundary"],
            "existing_decision": {
                "behavior_id": boundary["behavior_id"],
                "agent_id": agent_id,
                "observation_sha256": observation_sha256(observation),
                "action_masks": masks_to_json(masks),
            },
            "selected_action": [int(value) for value in action],
            "transition": transition_record,
            "final_boundary": {
                **contract["live_handoff"]["final_boundary"],
                "online_network_sha256": final_summary["online_network_sha256"],
                "target_network_sha256": final_summary["target_network_sha256"],
                "checkpoint_state_sha256": checkpoint_state_sha256(
                    loaded.controller, loaded.collector, loaded.selector
                ),
                "checkpoint_sha256": sha256_file(final_checkpoint),
                "replay": final_summary["replay"],
            },
            "post_resume_observation": {
                "sha256": observation_sha256(next_observation),
                "file_sha256": sha256_file(observation_path),
                "action_masks": masks_to_json(next_masks),
            },
            "optimizer_updated": False,
            "target_synchronized": False,
            "held_decision_agent_ids": outcome["held_decision_agent_ids"],
            "terminal_agent_ids": outcome["terminal_agent_ids"],
        }
        result_path = worker_output / LIVE_RESULT_FILE_NAME
        _write_json(result, result_path)
        connection.send(
            {
                "type": "completed",
                "result_sha256": sha256_file(result_path),
            }
        )
    finally:
        connection.close()
    return 0


def _run_live_worker(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
    r3r_contract: Dict[str, Any],
    r3r_result: Dict[str, Any],
) -> Dict[str, Any]:
    expected_copy_root = (
        worker_output.parent / "player-copies" / f"run-{worker_index + 1}"
    ).resolve()
    if executable.parent.resolve() != expected_copy_root:
        raise LLAPIContractError("R3S worker must use its run-owned player copy.")
    copy_manifest = directory_file_manifest(expected_copy_root)
    copy_manifest_sha256 = canonical_json_sha256(copy_manifest)
    if copy_manifest_sha256 != contract["player"]["source_manifest_sha256"]:
        raise LLAPIContractError("R3S fresh player copy manifest drifted.")
    _write_json(
        copy_manifest,
        worker_output.parent / "player-manifests" / f"run-{worker_index + 1}.json",
    )
    r3r_schema = _read_json(R3R_RESULT_SCHEMA_PATH)

    def validate_prefix(
        controller: Any,
        collector: Any,
        selector: Any,
        transitions: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return validate_r3r_prefix_boundary(
            controller, collector, selector, transitions, r3r_contract
        )

    checkpoint_path = worker_output / R3R_CHECKPOINT_FILE_NAME
    trace_path = worker_output / R3R_TRACE_FILE_NAME

    def handoff(
        environment: UnityEnvironment,
        behavior_id: str,
        side_channel: BasicTruncationMaskSideChannel,
    ) -> None:
        if not isinstance(environment, AuditedUnityEnvironment):
            raise LLAPIContractError("R3S omitted its audited Unity supervisor.")
        _run_handoff_supervisor(
            environment,
            behavior_id,
            side_channel,
            worker_output,
            checkpoint_path,
            trace_path,
            contract,
            executable,
        )

    trace = execute_update_gate_worker(
        executable,
        worker_output,
        worker_index,
        r3r_contract,
        gate_contract=r3r_stage_contract(r3r_contract, "synchronization"),
        contract_path=(REPO_ROOT / contract["base_r3r_contract"]["path"]),
        trace_file_name=R3R_TRACE_FILE_NAME,
        trace_schema_version="quickdraw.bdq-long-horizon-trace.v1",
        task_name="R3S accepted R3R reproduction",
        record_update_hashes=True,
        record_target_hashes=True,
        base_port=BASE_WORKER_PORT,
        timeout_wait=300,
        progress_interval=1_000,
        checkpoint_path=checkpoint_path,
        trace_metadata={"stage": "synchronization"},
        boundary_callback=validate_prefix,
        prefix_boundary_transition_count=int(
            r3r_contract["continuation_prefix"]["transition_count"]
        ),
        environment_factory=AuditedUnityEnvironment,
        live_boundary_callback=handoff,
    )
    validate_r3r_trace(trace, r3r_schema, r3r_contract, "synchronization")
    if trace != r3r_result["canonical_trace"]:
        raise LLAPIContractError("R3S reproduced R3R trace differs canonically.")
    live_result = _read_json(
        worker_output / "restored-trainer" / LIVE_RESULT_FILE_NAME
    )
    handoff_manifest = _read_json(worker_output / HANDOFF_MANIFEST_FILE_NAME)
    canonical = {
        "r3r_trace_sha256": sha256_file(trace_path),
        "r3r_checkpoint_sha256": sha256_file(checkpoint_path),
        "r3r_checkpoint_state_sha256": contract["accepted_r3r"]["checkpoint"][
            "state_sha256"
        ],
        "handoff": handoff_manifest["canonical"],
        "live_resume": live_result,
    }
    attempt = {
        "schema_version": "quickdraw.r3s-attempt.v1",
        "attempt_index": worker_index + 1,
        "canonical_sha256": canonical_json_sha256(canonical),
        "canonical": canonical,
        "provenance": {
            **handoff_manifest["provenance"],
            "player_manifest_sha256": copy_manifest_sha256,
            "player_manifest_path": str(
                (
                    worker_output.parent
                    / "player-manifests"
                    / f"run-{worker_index + 1}.json"
                ).resolve()
            ),
            "r3r_trace_path": str(trace_path.resolve()),
            "r3r_checkpoint_path": str(checkpoint_path.resolve()),
        },
    }
    _write_json(attempt, worker_output / ATTEMPT_FILE_NAME)
    return trace


def _mask_pattern_indices(loaded: Any, count: int) -> list[int]:
    state = loaded.controller.replay.export_checkpoint_state()
    branch_masks = state["action_masks"]
    first_by_pattern: Dict[tuple[bool, ...], int] = {}
    for index in range(int(state["size"])):
        pattern = tuple(
            bool(value)
            for branch in branch_masks
            for value in branch[index].tolist()
        )
        first_by_pattern.setdefault(pattern, index)
    if len(first_by_pattern) > count:
        raise LLAPIContractError("R3S parity corpus is too small for mask coverage.")
    indices = list(first_by_pattern.values())
    selected = set(indices)
    for index in range(int(state["size"])):
        if len(indices) == count:
            break
        if index not in selected:
            indices.append(index)
    if len(indices) != count:
        raise LLAPIContractError("R3S parity corpus omitted checkpoint rows.")
    return indices


def _masked_actions(
    q_values: Sequence[np.ndarray], masks: Sequence[np.ndarray]
) -> np.ndarray:
    if len(q_values) != 2 or len(masks) != 2:
        raise LLAPIContractError("R3S Q-values and masks require two branches.")
    try:
        torch_q_values = tuple(torch.from_numpy(np.asarray(value)) for value in q_values)
        torch_masks = tuple(torch.from_numpy(np.asarray(value)) for value in masks)
        return greedy_actions(torch_q_values, torch_masks).cpu().numpy().astype(
            np.int64, copy=False
        )
    except (TypeError, ValueError) as error:
        raise LLAPIContractError(
            f"R3S masked action selection failed: {error}"
        ) from error


def _graph_metadata(model_path: Path) -> Dict[str, Any]:
    model = onnx.load(str(model_path))
    onnx.checker.check_model(model)

    def tensor(value: Any) -> Dict[str, Any]:
        tensor_type = value.type.tensor_type
        shape = []
        for dimension in tensor_type.shape.dim:
            if dimension.dim_param:
                shape.append(dimension.dim_param)
            else:
                shape.append(int(dimension.dim_value))
        return {
            "name": value.name,
            "element_type": int(tensor_type.elem_type),
            "shape": shape,
        }

    return {
        "ir_version": int(model.ir_version),
        "opsets": [
            {"domain": item.domain, "version": int(item.version)}
            for item in model.opset_import
        ],
        "inputs": [tensor(value) for value in model.graph.input],
        "outputs": [tensor(value) for value in model.graph.output],
    }


def _expected_graph(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Build the registered graph interface once for export and validation."""

    export = contract["export"]
    return {
        "inputs": [
            {
                "name": export["input"]["name"],
                "element_type": int(onnx.TensorProto.FLOAT),
                "shape": export["input"]["shape"],
            }
        ],
        "outputs": [
            {
                "name": output["name"],
                "element_type": int(onnx.TensorProto.FLOAT),
                "shape": output["shape"],
            }
            for output in export["outputs"]
        ],
    }


def _create_corpus_and_export(
    output_directory: Path,
    attempts: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
    r3r_contract: Dict[str, Any],
) -> Dict[str, Any]:
    configure_torch(r3r_contract["determinism"], "R3S export")
    synchronization_collection = _synchronization_collection(r3r_contract)
    accepted_checkpoint = (
        REPO_ROOT / contract["accepted_r3r"]["checkpoint"]["path"]
    ).resolve()
    loaded = load_controller_checkpoint(
        accepted_checkpoint,
        settings=BDQOptimizationSettings(),
        controller_seed=int(synchronization_collection["policy_seed"]),
        exploration_seed=int(synchronization_collection["exploration_seed"]),
        schedule=_schedule(r3r_contract),
    )
    _verify_loaded_start(loaded, contract)
    source_hash_before = network_sha256(loaded.controller.online_network)
    if source_hash_before != contract["export"]["source_network_sha256"]:
        raise LLAPIContractError("R3S export source network hash drifted.")

    checkpoint_count = int(
        contract["export"]["parity_corpus"]["accepted_checkpoint_observation_count"]
    )
    indices = _mask_pattern_indices(loaded, checkpoint_count)
    batch = loaded.controller.replay.batch_at_indices(indices)
    live_observations = []
    live_masks = []
    for attempt in attempts:
        attempt_index = int(attempt["attempt_index"])
        live_path = (
            output_directory
            / f"run-{attempt_index}"
            / "restored-trainer"
            / POST_RESUME_OBSERVATION_FILE_NAME
        )
        live_observations.append(np.load(live_path, allow_pickle=False))
        live_masks.append(
            attempt["canonical"]["live_resume"]["post_resume_observation"][
                "action_masks"
            ]
        )
    if not np.array_equal(live_observations[0], live_observations[1]):
        raise LLAPIContractError("R3S post-resume observations differ across attempts.")
    if live_masks[0] != live_masks[1]:
        raise LLAPIContractError("R3S post-resume masks differ across attempts.")
    live_observation = validate_observation(
        live_observations[0], "R3S post-resume parity observation"
    )
    validated_live_masks = validate_action_masks(
        [np.asarray(value, dtype=np.bool_) for value in live_masks[0]],
        "R3S post-resume parity masks",
    )
    observations = np.concatenate(
        (batch.observations, live_observation[None, ...]), axis=0
    ).astype(np.float32, copy=False)
    masks = (
        np.concatenate((batch.action_masks[0], validated_live_masks[0][None, ...])),
        np.concatenate((batch.action_masks[1], validated_live_masks[1][None, ...])),
    )
    expected_count = int(contract["export"]["parity_corpus"]["count"])
    if observations.shape != (expected_count, 84, 84, 4):
        raise LLAPIContractError("R3S parity corpus observation shape drifted.")
    state = loaded.controller.replay.export_checkpoint_state()
    all_patterns = {
        tuple(
            bool(value)
            for branch in state["action_masks"]
            for value in branch[index].tolist()
        )
        for index in range(int(state["size"]))
    }
    corpus_patterns = {
        tuple(
            bool(value)
            for branch in masks
            for value in branch[index].tolist()
        )
        for index in range(checkpoint_count)
    }
    if corpus_patterns != all_patterns:
        raise LLAPIContractError("R3S parity corpus omitted a checkpoint mask pattern.")
    if not any(bool(mask.any()) for mask in masks):
        raise LLAPIContractError("R3S parity corpus omitted unavailable actions.")

    network = loaded.controller.online_network.eval()
    with torch.no_grad():
        python_q = tuple(
            value.detach().cpu().numpy().astype(np.float32, copy=False)
            for value in network(torch.from_numpy(observations))
        )
    python_actions = _masked_actions(python_q, masks)
    export_directory = output_directory / "export"
    export_directory.mkdir(parents=True, exist_ok=False)
    corpus_path = export_directory / CORPUS_FILE_NAME
    np.savez(
        corpus_path,
        observations=observations,
        branch_0_masks=masks[0],
        branch_1_masks=masks[1],
        python_branch_0_q_values=python_q[0],
        python_branch_1_q_values=python_q[1],
        python_actions=python_actions,
        replay_indices=np.asarray([*indices, -1], dtype=np.int64),
    )
    corpus_content_sha256 = _array_sha256(
        (
            ("observations", observations),
            ("branch_0_masks", masks[0]),
            ("branch_1_masks", masks[1]),
            ("python_branch_0_q_values", python_q[0]),
            ("python_branch_1_q_values", python_q[1]),
            ("python_actions", python_actions),
            ("replay_indices", np.asarray([*indices, -1], dtype=np.int64)),
        )
    )
    corpus_metadata = {
        "schema_version": contract["export"]["parity_corpus"]["schema_version"],
        "selection_rule": contract["export"]["parity_corpus"]["selection_rule"],
        "count": expected_count,
        "accepted_checkpoint_indices": indices,
        "post_resume_attempts": [1, 2],
        "mask_patterns": [list(pattern) for pattern in sorted(corpus_patterns)],
        "observation_minimum": float(observations.min()),
        "observation_maximum": float(observations.max()),
        "corpus_file_sha256": sha256_file(corpus_path),
        "corpus_content_sha256": corpus_content_sha256,
        "python_q_values_sha256": _array_sha256(
            (("branch_0", python_q[0]), ("branch_1", python_q[1]))
        ),
        "python_actions_sha256": _array_sha256((("actions", python_actions),)),
    }
    _write_json(corpus_metadata, export_directory / CORPUS_METADATA_FILE_NAME)

    model_path = export_directory / ONNX_FILE_NAME
    torch.onnx.export(
        network,
        torch.zeros((1, 84, 84, 4), dtype=torch.float32),
        model_path,
        export_params=True,
        opset_version=int(contract["export"]["opset"]),
        do_constant_folding=True,
        input_names=[contract["export"]["input"]["name"]],
        output_names=[value["name"] for value in contract["export"]["outputs"]],
        dynamic_axes={
            contract["export"]["input"]["name"]: {0: "N"},
            contract["export"]["outputs"][0]["name"]: {0: "N"},
            contract["export"]["outputs"][1]["name"]: {0: "N"},
        },
        dynamo=False,
    )
    source_hash_after = network_sha256(network)
    if source_hash_after != source_hash_before:
        raise LLAPIContractError("R3S export changed the source network.")
    graph = _graph_metadata(model_path)
    expected_graph = _expected_graph(contract)
    if (
        graph["inputs"] != expected_graph["inputs"]
        or graph["outputs"] != expected_graph["outputs"]
    ):
        raise LLAPIContractError("R3S exported graph interface drifted.")
    export_metadata = {
        "schema_version": "quickdraw.bdq-onnx-export.v1",
        "source_network_sha256_before": source_hash_before,
        "source_network_sha256_after": source_hash_after,
        "onnx_sha256": sha256_file(model_path),
        "onnx_bytes": model_path.stat().st_size,
        "exporter": "torch.onnx.export",
        "torch_version": version("torch"),
        "onnx_version": version("onnx"),
        "onnxruntime_version": version("onnxruntime"),
        "opset": int(contract["export"]["opset"]),
        "graph": graph,
    }
    _write_json(export_metadata, export_directory / EXPORT_METADATA_FILE_NAME)

    inference_results = []
    for index in range(2):
        result_path = export_directory / f"inference-{index + 1}.json"
        output_path = export_directory / f"inference-{index + 1}.npz"
        run_fresh_python_process(
            runner_path=Path(__file__),
            arguments=[
                "--mode=parity-worker",
                f"--onnx={model_path}",
                f"--corpus={corpus_path}",
                f"--inference-result={result_path}",
                f"--inference-output={output_path}",
            ],
            output_directory=export_directory,
            log_name=f"inference-{index + 1}.log",
            task_name=f"R3S ONNX inference {index + 1}",
            contract=r3r_contract,
            repo_root=REPO_ROOT,
            timeout_seconds=600,
        )
        inference_results.append(_read_json(result_path))
    repeated_fields = ("canonical_outputs_sha256", "actions_sha256")
    if any(
        inference_results[0][field] != inference_results[1][field]
        for field in repeated_fields
    ):
        raise LLAPIContractError("R3S fresh ONNX inference results differ.")
    return {
        "export_metadata": export_metadata,
        "corpus": corpus_metadata,
        "fresh_inference_process_count": 2,
        "exact_repeat_outputs": True,
        "inference": inference_results[0],
        "inference_attempts": inference_results,
    }


def _run_parity_worker(
    model_path: Path,
    corpus_path: Path,
    result_path: Path,
    output_path: Path,
    contract: Dict[str, Any],
) -> int:
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    with np.load(corpus_path, allow_pickle=False) as corpus:
        observations = validate_observation_batch(corpus["observations"])
        masks = (
            np.asarray(corpus["branch_0_masks"], dtype=np.bool_),
            np.asarray(corpus["branch_1_masks"], dtype=np.bool_),
        )
        python_q = (
            np.asarray(corpus["python_branch_0_q_values"], dtype=np.float32),
            np.asarray(corpus["python_branch_1_q_values"], dtype=np.float32),
        )
        python_actions = np.asarray(corpus["python_actions"], dtype=np.int64)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path),
        sess_options=options,
        providers=[contract["export_dependencies"]["execution_provider"]],
    )
    input_name = contract["export"]["input"]["name"]
    output_names = [item["name"] for item in contract["export"]["outputs"]]
    outputs = tuple(
        np.asarray(value)
        for value in session.run(output_names, {input_name: observations})
    )
    single_outputs = tuple(
        np.asarray(value)
        for value in session.run(output_names, {input_name: observations[:1]})
    )
    expected_shapes = ((observations.shape[0], 3), (observations.shape[0], 2))
    if tuple(value.shape for value in outputs) != expected_shapes:
        raise LLAPIContractError("R3S ONNX output shape drifted.")
    if any(value.dtype != np.float32 for value in outputs):
        raise LLAPIContractError("R3S ONNX output dtype drifted.")
    if any(not np.isfinite(value).all() for value in outputs):
        raise LLAPIContractError("R3S ONNX output contains a non-finite value.")
    tolerance = float(contract["export"]["maximum_absolute_difference"])
    differences = [
        float(np.max(np.abs(actual - expected)))
        for actual, expected in zip(outputs, python_q)
    ]
    maximum_difference = max(differences)
    if maximum_difference > tolerance:
        raise LLAPIContractError("R3S ONNX parity tolerance was exceeded.")
    actions = _masked_actions(outputs, masks)
    if not np.array_equal(actions, python_actions):
        raise LLAPIContractError("R3S ONNX masked legal actions differ from Python.")
    single_differences = [
        float(np.max(np.abs(single - batched[:1])))
        for single, batched in zip(single_outputs, outputs)
    ]
    if max(single_differences) > tolerance:
        raise LLAPIContractError("R3S ONNX single-item and batch outputs differ.")
    if not np.array_equal(
        _masked_actions(single_outputs, (masks[0][:1], masks[1][:1])), actions[:1]
    ):
        raise LLAPIContractError("R3S ONNX single-item action differs from batch.")
    np.savez(output_path, branch_0_q_values=outputs[0], branch_1_q_values=outputs[1], actions=actions)
    result = {
        "schema_version": "quickdraw.bdq-onnx-parity-worker.v1",
        "process_identity": _process_identity(os.getpid(), Path(sys.executable)),
        "onnx_sha256": sha256_file(model_path),
        "corpus_sha256": sha256_file(corpus_path),
        "output_file_sha256": sha256_file(output_path),
        "canonical_outputs_sha256": _array_sha256(
            (("branch_0", outputs[0]), ("branch_1", outputs[1]))
        ),
        "actions_sha256": _array_sha256((("actions", actions),)),
        "maximum_absolute_difference": maximum_difference,
        "single_item_maximum_absolute_difference": max(single_differences),
        "all_outputs_finite": True,
        "all_actions_match": True,
        "single_and_batched_inference": True,
        "input_shape": list(observations.shape),
        "output_shapes": [list(value.shape) for value in outputs],
        "output_dtype": "float32",
    }
    _write_json(result, result_path)
    return 0


def validate_observation_batch(value: np.ndarray) -> np.ndarray:
    observations = np.asarray(value)
    if (
        observations.ndim != 4
        or observations.shape[0] <= 0
        or tuple(observations.shape[1:]) != (84, 84, 4)
    ):
        raise LLAPIContractError("R3S observations must have shape [N,84,84,4].")
    if observations.dtype != np.float32:
        raise LLAPIContractError("R3S observations must use float32 dtype.")
    if not np.isfinite(observations).all():
        raise LLAPIContractError("R3S observations contain a non-finite value.")
    if float(observations.min()) < 0.0 or float(observations.max()) > 1.0:
        raise LLAPIContractError("R3S observations must remain within [0,1].")
    return observations


def _validate_result_artifacts(
    result: Dict[str, Any], contract: Dict[str, Any], artifact_root: Path
) -> None:
    """Bind an accepted summary back to every fixed-path R3S raw artifact."""

    root = artifact_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    attempts = result["live_resume"]["attempts"]
    live_observations = []
    for index, attempt in enumerate(attempts, start=1):
        run_root = root / f"run-{index}"
        trace_path = run_root / R3R_TRACE_FILE_NAME
        checkpoint_path = run_root / R3R_CHECKPOINT_FILE_NAME
        attempt_path = run_root / ATTEMPT_FILE_NAME
        manifest_path = run_root / HANDOFF_MANIFEST_FILE_NAME
        restored_root = run_root / "restored-trainer"
        live_result_path = restored_root / LIVE_RESULT_FILE_NAME
        final_checkpoint_path = restored_root / FINAL_CHECKPOINT_FILE_NAME
        observation_path = restored_root / POST_RESUME_OBSERVATION_FILE_NAME
        player_manifest_path = root / "player-manifests" / f"run-{index}.json"
        for path in (
            trace_path,
            checkpoint_path,
            attempt_path,
            manifest_path,
            live_result_path,
            final_checkpoint_path,
            observation_path,
            player_manifest_path,
            root / f"worker-{index}.log",
            run_root / "restored-trainer.log",
        ):
            if not path.is_file():
                raise FileNotFoundError(path)
        if (
            sha256_file(trace_path)
            != contract["accepted_r3r"]["trace"]["sha256"]
            or sha256_file(checkpoint_path)
            != contract["accepted_r3r"]["checkpoint"]["sha256"]
        ):
            raise LLAPIContractError("R3S raw R3R boundary artifact drifted.")
        if _read_json(attempt_path) != attempt:
            raise LLAPIContractError("R3S raw attempt summary drifted.")
        manifest = _read_json(manifest_path)
        if (
            manifest["canonical"] != attempt["canonical"]["handoff"]
            or _read_json(live_result_path)
            != attempt["canonical"]["live_resume"]
        ):
            raise LLAPIContractError("R3S raw handoff evidence drifted.")
        player_manifest = _read_json(player_manifest_path)
        if canonical_json_sha256(player_manifest) != contract["player"][
            "source_manifest_sha256"
        ]:
            raise LLAPIContractError("R3S raw player manifest drifted.")
        final_checkpoint = _read_json(final_checkpoint_path)
        final = attempt["canonical"]["live_resume"]["final_boundary"]
        if (
            sha256_file(final_checkpoint_path) != final["checkpoint_sha256"]
            or final_checkpoint["state_sha256"] != final["checkpoint_state_sha256"]
        ):
            raise LLAPIContractError("R3S post-resume checkpoint drifted.")
        observation = validate_observation(
            np.load(observation_path, allow_pickle=False),
            "R3S retained post-resume observation",
        )
        post_resume = attempt["canonical"]["live_resume"][
            "post_resume_observation"
        ]
        if (
            sha256_file(observation_path) != post_resume["file_sha256"]
            or observation_sha256(observation) != post_resume["sha256"]
        ):
            raise LLAPIContractError("R3S post-resume observation artifact drifted.")
        live_observations.append(observation)

    export = result["export_parity"]
    export_root = root / "export"
    model_path = export_root / ONNX_FILE_NAME
    corpus_path = export_root / CORPUS_FILE_NAME
    metadata_path = export_root / EXPORT_METADATA_FILE_NAME
    corpus_metadata_path = export_root / CORPUS_METADATA_FILE_NAME
    for path in (model_path, corpus_path, metadata_path, corpus_metadata_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if (
        _read_json(metadata_path) != export["export_metadata"]
        or _read_json(corpus_metadata_path) != export["corpus"]
        or sha256_file(model_path) != export["export_metadata"]["onnx_sha256"]
        or sha256_file(corpus_path) != export["corpus"]["corpus_file_sha256"]
        or _graph_metadata(model_path) != export["export_metadata"]["graph"]
    ):
        raise LLAPIContractError("R3S retained export artifact drifted.")

    with np.load(corpus_path, allow_pickle=False) as raw_corpus:
        observations = validate_observation_batch(raw_corpus["observations"])
        masks = (
            np.asarray(raw_corpus["branch_0_masks"]),
            np.asarray(raw_corpus["branch_1_masks"]),
        )
        python_q = (
            np.asarray(raw_corpus["python_branch_0_q_values"]),
            np.asarray(raw_corpus["python_branch_1_q_values"]),
        )
        python_actions = np.asarray(raw_corpus["python_actions"])
        replay_indices = np.asarray(raw_corpus["replay_indices"])
    if (
        masks[0].dtype != np.bool_
        or masks[1].dtype != np.bool_
        or masks[0].shape != (64, 3)
        or masks[1].shape != (64, 2)
        or python_q[0].dtype != np.float32
        or python_q[1].dtype != np.float32
        or python_q[0].shape != (64, 3)
        or python_q[1].shape != (64, 2)
        or python_actions.dtype != np.int64
        or python_actions.shape != (64, 2)
        or replay_indices.dtype != np.int64
        or replay_indices.shape != (64,)
        or int(replay_indices[-1]) != -1
        or not all(np.isfinite(value).all() for value in python_q)
    ):
        raise LLAPIContractError("R3S retained parity corpus arrays drifted.")
    if not np.array_equal(observations[-1], live_observations[0]):
        raise LLAPIContractError("R3S corpus omitted the live-resume observation.")
    if not np.array_equal(_masked_actions(python_q, masks), python_actions):
        raise LLAPIContractError("R3S retained Python masked actions drifted.")
    corpus_content_sha256 = _array_sha256(
        (
            ("observations", observations),
            ("branch_0_masks", masks[0]),
            ("branch_1_masks", masks[1]),
            ("python_branch_0_q_values", python_q[0]),
            ("python_branch_1_q_values", python_q[1]),
            ("python_actions", python_actions),
            ("replay_indices", replay_indices),
        )
    )
    corpus_metadata = export["corpus"]
    if (
        corpus_content_sha256 != corpus_metadata["corpus_content_sha256"]
        or _array_sha256((("branch_0", python_q[0]), ("branch_1", python_q[1])))
        != corpus_metadata["python_q_values_sha256"]
        or _array_sha256((("actions", python_actions),))
        != corpus_metadata["python_actions_sha256"]
    ):
        raise LLAPIContractError("R3S parity corpus content hash drifted.")

    for index, inference in enumerate(export["inference_attempts"], start=1):
        result_path = export_root / f"inference-{index}.json"
        output_path = export_root / f"inference-{index}.npz"
        log_path = export_root / f"inference-{index}.log"
        for path in (result_path, output_path, log_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        if (
            _read_json(result_path) != inference
            or sha256_file(output_path) != inference["output_file_sha256"]
        ):
            raise LLAPIContractError("R3S retained inference artifact drifted.")
        with np.load(output_path, allow_pickle=False) as raw_output:
            outputs = (
                np.asarray(raw_output["branch_0_q_values"]),
                np.asarray(raw_output["branch_1_q_values"]),
            )
            actions = np.asarray(raw_output["actions"])
        maximum_difference = max(
            float(np.max(np.abs(actual - expected)))
            for actual, expected in zip(outputs, python_q)
        )
        masked_actions = _masked_actions(outputs, masks)
        if (
            outputs[0].dtype != np.float32
            or outputs[1].dtype != np.float32
            or outputs[0].shape != (64, 3)
            or outputs[1].shape != (64, 2)
            or actions.dtype != np.int64
            or actions.shape != (64, 2)
            or not all(np.isfinite(value).all() for value in outputs)
            or not np.array_equal(actions, python_actions)
            or maximum_difference != inference["maximum_absolute_difference"]
            or maximum_difference
            > float(contract["export"]["maximum_absolute_difference"])
            or masked_actions.shape != actions.shape
            or not np.array_equal(masked_actions, actions)
            or _array_sha256(
                (("branch_0", outputs[0]), ("branch_1", outputs[1]))
            )
            != inference["canonical_outputs_sha256"]
            or _array_sha256((("actions", actions),))
            != inference["actions_sha256"]
        ):
            raise LLAPIContractError("R3S retained inference content drifted.")


def validate_result(
    result: Dict[str, Any],
    result_schema: Dict[str, Any],
    contract: Dict[str, Any],
    *,
    artifact_root: Path,
) -> None:
    """Validate generic result shape before R3S relational requirements."""

    Draft202012Validator(result_schema).validate(result)
    if result["contract_sha256"] != sha256_file(CONTRACT_PATH):
        raise LLAPIContractError("R3S result contract binding drifted.")
    if result["starting_boundary"] != contract["accepted_r3r"]:
        raise LLAPIContractError("R3S result starting-boundary binding drifted.")
    attempts = result["live_resume"]["attempts"]
    if len(attempts) != contract["live_handoff"]["fresh_attempts"]:
        raise LLAPIContractError("R3S requires two live handoff attempts.")
    if attempts[0]["canonical"] != attempts[1]["canonical"]:
        raise LLAPIContractError("R3S canonical live attempts differ.")
    if [attempt["attempt_index"] for attempt in attempts] != [1, 2]:
        raise LLAPIContractError("R3S live attempt ordering drifted.")
    if result["live_resume"]["canonical_attempt_sha256"] != attempts[0][
        "canonical_sha256"
    ]:
        raise LLAPIContractError("R3S live comparison hash drifted.")
    for attempt in attempts:
        if canonical_json_sha256(attempt["canonical"]) != attempt["canonical_sha256"]:
            raise LLAPIContractError("R3S attempt canonical hash drifted.")
        canonical = attempt["canonical"]
        if canonical["r3r_trace_sha256"] != contract["accepted_r3r"]["trace"][
            "sha256"
        ]:
            raise LLAPIContractError("R3S reproduced trace binding drifted.")
        if canonical["r3r_checkpoint_sha256"] != contract["accepted_r3r"][
            "checkpoint"
        ]["sha256"]:
            raise LLAPIContractError("R3S reproduced checkpoint binding drifted.")
        if canonical["r3r_checkpoint_state_sha256"] != contract["accepted_r3r"][
            "checkpoint"
        ]["state_sha256"]:
            raise LLAPIContractError("R3S reproduced checkpoint state drifted.")
        if canonical["handoff"]["event_sequence"] != contract["live_handoff"][
            "canonical_event_sequence"
        ]:
            raise LLAPIContractError("R3S handoff event sequence drifted.")
        if canonical["handoff"]["environment_counters"] != {
            key: contract["live_handoff"]["environment_counters"][key]
            for key in (
                "launches",
                "resets_before_handoff",
                "steps_before_handoff",
                "resumed_actions",
                "steps_after_handoff",
            )
        }:
            raise LLAPIContractError("R3S handoff operation counters drifted.")
        for claim in (
            "same_player_process",
            "same_player_copy",
            "fresh_trainer_process",
        ):
            if canonical["handoff"][claim] is not True:
                raise LLAPIContractError(f"R3S handoff claim failed: {claim}.")
        for forbidden in (
            "reset_during_handoff",
            "relaunch_during_handoff",
            "extra_environment_step",
            "discarded_decision",
        ):
            if canonical["handoff"][forbidden] is not False:
                raise LLAPIContractError(f"R3S handoff recorded {forbidden}.")
        live = canonical["live_resume"]
        if live["start_boundary"] != contract["live_handoff"]["start_boundary"]:
            raise LLAPIContractError("R3S live starting boundary drifted.")
        final = live["final_boundary"]
        for key, value in contract["live_handoff"]["final_boundary"].items():
            if final[key] != value:
                raise LLAPIContractError(f"R3S live final {key} drifted.")
        if live["optimizer_updated"] or live["target_synchronized"]:
            raise LLAPIContractError("R3S crossed an unauthorized update boundary.")
        selected = live["selected_action"]
        masks = live["existing_decision"]["action_masks"]
        if any(masks[branch][selected[branch]] for branch in range(2)):
            raise LLAPIContractError("R3S live action was masked.")
        if live["transition"]["action"] != selected:
            raise LLAPIContractError("R3S live action differs from its transition.")
        transition = live["transition"]
        existing = live["existing_decision"]
        post_resume = live["post_resume_observation"]
        if existing["behavior_id"] != canonical["handoff"]["behavior_id"] or existing[
            "agent_id"
        ] != canonical["handoff"]["agent_id"]:
            raise LLAPIContractError("R3S live behavior or agent identity drifted.")
        if (
            transition["observation_sha256"] != existing["observation_sha256"]
            or transition["action_masks"] != existing["action_masks"]
            or transition["next_observation_sha256"] != post_resume["sha256"]
            or transition["next_action_masks"] != post_resume["action_masks"]
        ):
            raise LLAPIContractError("R3S live transition boundary data drifted.")
        if final["decision_count"] != 49997 or transition["index"] != 49996:
            raise LLAPIContractError("R3S did not complete exactly transition 49997.")
        replay = final["replay"]
        if (
            replay["capacity"] != contract["accepted_r3r"]["boundary"][
                "replay_capacity"
            ]
            or replay["size"] != 49997
            or replay["cursor"] != 49997
            or replay["frame_reference_count"] != 399976
            or replay["max_accounted_storage_bytes"]
            != contract["accepted_r3r"]["boundary"][
                "maximum_accounted_storage_bytes"
            ]
            or replay["accounted_storage_bytes"]
            > replay["max_accounted_storage_bytes"]
        ):
            raise LLAPIContractError("R3S final replay state drifted.")
        ended = bool(transition["terminated"] or transition["truncated"])
        if transition["terminated"] and transition["truncated"]:
            raise LLAPIContractError("R3S transition cannot terminate and truncate.")
        expected_agent_id = existing["agent_id"]
        if ended:
            # ML-Agents may deliver a terminal step and the next episode's
            # DecisionStep for the same agent in one exchange.
            held_valid = live["held_decision_agent_ids"] in ([], [expected_agent_id])
            outcome_valid = live["terminal_agent_ids"] == [expected_agent_id]
        else:
            held_valid = live["held_decision_agent_ids"] == [expected_agent_id]
            outcome_valid = live["terminal_agent_ids"] == []
        if not held_valid or not outcome_valid:
            raise LLAPIContractError("R3S post-step agent outcome drifted.")
        if (
            final["online_network_sha256"]
            != contract["export"]["source_network_sha256"]
            or final["target_network_sha256"]
            != contract["export"]["source_network_sha256"]
        ):
            raise LLAPIContractError("R3S network changed after live resume.")
        provenance = attempt["provenance"]
        if provenance["player_identity_before"] != provenance[
            "player_identity_after"
        ]:
            raise LLAPIContractError("R3S player PID/start marker changed.")
        if provenance["initial_trainer_identity"] == provenance[
            "restored_trainer_identity"
        ]:
            raise LLAPIContractError("R3S restored trainer was not fresh.")
        if provenance["initial_trainer_identity"]["pid"] == provenance[
            "restored_trainer_identity"
        ]["pid"]:
            raise LLAPIContractError("R3S restored trainer reused the initial PID.")
        if not provenance["player_process_stopped_after_attempt"]:
            raise LLAPIContractError("R3S player process leak check failed.")
        if provenance["player_manifest_sha256"] != contract["player"][
            "source_manifest_sha256"
        ]:
            raise LLAPIContractError("R3S player copy manifest drifted.")
    export = result["export_parity"]
    metadata = export["export_metadata"]
    source_hash = contract["export"]["source_network_sha256"]
    if metadata["source_network_sha256_before"] != source_hash or metadata[
        "source_network_sha256_after"
    ] != source_hash:
        raise LLAPIContractError("R3S ONNX source network hash drifted.")
    expected_graph = _expected_graph(contract)
    if (
        metadata["exporter"] != contract["export"]["exporter"]
        or metadata["opset"] != contract["export"]["opset"]
        or metadata["torch_version"] != contract["runtime"]["torch"]
        or metadata["onnx_version"] != contract["export_dependencies"]["onnx"]
        or metadata["onnxruntime_version"]
        != contract["export_dependencies"]["onnxruntime"]
        or metadata["graph"]["inputs"] != expected_graph["inputs"]
        or metadata["graph"]["outputs"] != expected_graph["outputs"]
        or {"domain": "", "version": contract["export"]["opset"]}
        not in metadata["graph"]["opsets"]
    ):
        raise LLAPIContractError("R3S ONNX export metadata or interface drifted.")
    corpus = export["corpus"]
    corpus_contract = contract["export"]["parity_corpus"]
    if (
        corpus["schema_version"] != corpus_contract["schema_version"]
        or corpus["selection_rule"] != corpus_contract["selection_rule"]
        or corpus["count"] != corpus_contract["count"]
        or len(corpus["accepted_checkpoint_indices"])
        != corpus_contract["accepted_checkpoint_observation_count"]
        or corpus["post_resume_attempts"] != [1, 2]
        or not any(any(pattern) for pattern in corpus["mask_patterns"])
    ):
        raise LLAPIContractError("R3S parity corpus metadata drifted.")
    inference = export["inference"]
    if inference["onnx_sha256"] != metadata["onnx_sha256"]:
        raise LLAPIContractError("R3S ONNX inference used a stale export.")
    if inference["corpus_sha256"] != export["corpus"]["corpus_file_sha256"]:
        raise LLAPIContractError("R3S ONNX inference used a stale corpus.")
    inference_attempts = export["inference_attempts"]
    if inference != inference_attempts[0]:
        raise LLAPIContractError("R3S primary inference record drifted.")
    if (
        inference_attempts[0]["process_identity"]["pid"]
        == inference_attempts[1]["process_identity"]["pid"]
        or inference_attempts[0]["process_identity"]["creation_marker"]
        == inference_attempts[1]["process_identity"]["creation_marker"]
    ):
        raise LLAPIContractError("R3S ONNX parity workers were not fresh processes.")
    for inference_attempt in inference_attempts:
        if (
            inference_attempt["onnx_sha256"] != metadata["onnx_sha256"]
            or inference_attempt["corpus_sha256"] != corpus["corpus_file_sha256"]
            or inference_attempt["actions_sha256"]
            != corpus["python_actions_sha256"]
            or inference_attempt["maximum_absolute_difference"]
            > contract["export"]["maximum_absolute_difference"]
            or inference_attempt["single_item_maximum_absolute_difference"]
            > contract["export"]["maximum_absolute_difference"]
            or not inference_attempt["all_outputs_finite"]
            or not inference_attempt["all_actions_match"]
            or not inference_attempt["single_and_batched_inference"]
        ):
            raise LLAPIContractError("R3S ONNX parity requirement failed.")
    if (
        inference_attempts[0]["canonical_outputs_sha256"]
        != inference_attempts[1]["canonical_outputs_sha256"]
        or inference_attempts[0]["actions_sha256"]
        != inference_attempts[1]["actions_sha256"]
        or not export["exact_repeat_outputs"]
    ):
        raise LLAPIContractError("R3S ONNX repeat inference drifted.")
    if export["fresh_inference_process_count"] != contract["export"][
        "fresh_cpu_inference_processes"
    ]:
        raise LLAPIContractError("R3S ONNX fresh process count drifted.")
    _validate_result_artifacts(result, contract, artifact_root)


def _parent_run(
    output_directory: Path,
    contract: Dict[str, Any],
    result_schema: Dict[str, Any],
    r3r_contract: Dict[str, Any],
    r3r_result: Dict[str, Any],
) -> Path:
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(f"R3S output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)
    _write_json(
        {
            "schema_version": "quickdraw.r3s-run-metadata.v1",
            "command": _command_arguments([sys.executable, *sys.argv]),
            "runtime": runtime_contract(),
            "onnx": version("onnx"),
            "onnxruntime": version("onnxruntime"),
            "contract_sha256": sha256_file(CONTRACT_PATH),
        },
        output_directory / "run-metadata.json",
    )
    try:
        source_executable = (
            REPO_ROOT / contract["player"]["source_executable"]
        ).resolve()
        attempts = []
        for index in range(2):
            copied_executable = copy_complete_player(
                source_executable,
                output_directory / "player-copies" / f"run-{index + 1}",
                required_siblings=contract["player"]["required_siblings"],
            )
            trace, _ = run_fresh_worker_process(
                runner_path=Path(__file__),
                executable=copied_executable,
                output_directory=output_directory,
                worker_index=index,
                contract=r3r_contract,
                trace_file_name=R3R_TRACE_FILE_NAME,
                task_name=TASK_NAME,
                announce=True,
                repo_root=REPO_ROOT,
                timeout_seconds=LIVE_WORKER_TIMEOUT_SECONDS,
                worker_arguments=["--mode=live-worker"],
            )
            if trace != r3r_result["canonical_trace"]:
                raise LLAPIContractError("R3S parent observed an R3R trace drift.")
            attempt_path = output_directory / f"run-{index + 1}" / ATTEMPT_FILE_NAME
            attempt = _read_json(attempt_path)
            _assert_process_stopped(attempt["provenance"]["player_identity_after"])
            attempt["provenance"]["player_process_stopped_after_attempt"] = True
            _write_json(attempt, attempt_path)
            attempts.append(attempt)
        if attempts[0]["canonical"] != attempts[1]["canonical"]:
            raise LLAPIContractError("R3S live attempts differ canonically.")
        export_parity = _create_corpus_and_export(
            output_directory, attempts, contract, r3r_contract
        )
        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "status": "accepted",
            "starting_boundary": contract["accepted_r3r"],
            "live_resume": {
                "fresh_attempt_count": 2,
                "exact_canonical_match": True,
                "canonical_attempt_sha256": attempts[0]["canonical_sha256"],
                "attempts": attempts,
            },
            "export_parity": export_parity,
            "claim_boundary": {
                "live_unity_process_continuity": True,
                "exported_inference_software_parity": True,
                "policy_effectiveness": False,
                "convergence": False,
                "held_out_evaluation": False,
            },
        }
        validate_result(
            result,
            result_schema,
            contract,
            artifact_root=output_directory,
        )
        result_path = output_directory / "result.json"
        _write_json(result, result_path)
        return result_path
    except Exception as error:
        _write_json(
            {
                "schema_version": "quickdraw.r3s-rejected-result.v1",
                "status": "rejected",
                "contract_sha256": sha256_file(CONTRACT_PATH),
                "error_type": type(error).__name__,
                "error": str(error),
            },
            output_directory / "rejected-result.json",
        )
        raise


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.mode == "live-worker":
        if (
            arguments.env is None
            or arguments.worker_output is None
            or arguments.worker_index is None
            or arguments.output is not None
        ):
            raise ValueError("R3S live-worker mode requires env, output, and index.")
        return "live-worker"
    if arguments.mode == "restored-trainer":
        if (
            arguments.checkpoint is None
            or arguments.worker_output is None
            or arguments.handoff_host is None
            or arguments.handoff_port is None
        ):
            raise ValueError("R3S restored-trainer mode requires checkpoint and handoff.")
        return "restored-trainer"
    if arguments.mode == "parity-worker":
        if any(
            value is None
            for value in (
                arguments.onnx,
                arguments.corpus,
                arguments.inference_result,
                arguments.inference_output,
            )
        ):
            raise ValueError("R3S parity-worker mode requires model, corpus, and outputs.")
        return "parity-worker"
    if arguments.mode is not None:
        raise ValueError("Unknown R3S mode.")
    if arguments.output is None:
        raise ValueError("R3S parent mode requires --output.")
    return "parent"


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mode", choices=["live-worker", "restored-trainer", "parity-worker"], help=argparse.SUPPRESS)
    parser.add_argument("--env", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--checkpoint", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--handoff-host", help=argparse.SUPPRESS)
    parser.add_argument("--handoff-port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--onnx", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--corpus", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--inference-result", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--inference-output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    contract = _read_json(CONTRACT_PATH)
    result_schema, r3r_contract, r3r_result = validate_contract(contract)
    if mode == "live-worker":
        assert arguments.env is not None
        assert arguments.worker_output is not None
        assert arguments.worker_index is not None
        _run_live_worker(
            arguments.env.resolve(),
            arguments.worker_output.resolve(),
            arguments.worker_index,
            contract,
            r3r_contract,
            r3r_result,
        )
        return 0
    if mode == "restored-trainer":
        assert arguments.checkpoint is not None
        assert arguments.worker_output is not None
        assert arguments.handoff_host is not None
        assert arguments.handoff_port is not None
        return _run_restored_trainer(
            arguments.checkpoint.resolve(),
            arguments.worker_output.resolve(),
            arguments.handoff_host,
            arguments.handoff_port,
            contract,
            r3r_contract,
        )
    if mode == "parity-worker":
        assert arguments.onnx is not None
        assert arguments.corpus is not None
        assert arguments.inference_result is not None
        assert arguments.inference_output is not None
        return _run_parity_worker(
            arguments.onnx.resolve(),
            arguments.corpus.resolve(),
            arguments.inference_result.resolve(),
            arguments.inference_output.resolve(),
            contract,
        )
    assert arguments.output is not None
    result_path = _parent_run(
        arguments.output.resolve(),
        contract,
        result_schema,
        r3r_contract,
        r3r_result,
    )
    print(f"result={result_path}")
    print("live_resume_attempts=2")
    print("post_resume_transition=49997")
    print("optimizer_updates=10000")
    print("target_synchronizations=1")
    print("onnx_parity=pass")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LLAPIContractError,
        ValueError,
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        TimeoutError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"error={error}", file=sys.stderr)
        raise SystemExit(2) from error
