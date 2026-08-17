from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker
from mlagents_envs.base_env import ActionTuple
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.incoming_message import IncomingMessage
from mlagents_envs.side_channel.outgoing_message import OutgoingMessage
from mlagents_envs.side_channel.side_channel import SideChannel


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
CONTRACT_PATH = REPO_ROOT / "Research" / "configs" / "research-contracts-v1.json"
SMOKE_CONTRACT_PATH = Path(__file__).with_name("smoke-contract-v1.json")
CPU_REFERENCE_CONTRACT_PATH = Path(__file__).with_name(
    "cpu-reference-contract-v1.json"
)
MANIFEST_SCHEMA_PATH = REPO_ROOT / "Research" / "schemas" / "run-manifest.schema.json"
SCENE_PATH = REPO_ROOT / "Assets" / "_Project" / "Scenes" / "Research_Smoke.unity"
UNITY_VERSION = "6000.0.57f1"
UNITY_REVISION = "b7b9860b7bbd"
UNITY_ML_AGENTS_VERSION = "4.0.0"
TRACE_FORMAT = "quickdraw.communicator-smoke-trace.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_command(arguments: List[str]) -> str:
    result = subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class ResearchSmokeSideChannel(SideChannel):
    def __init__(self, run_id: str, contract: Dict[str, Any]) -> None:
        channel = contract["side_channel"]
        super().__init__(uuid.UUID(channel["channel_uuid"]))
        self._run_id = run_id
        self._schema_version = channel["schema_version"]
        self._incoming_sequence: Dict[int, int] = {}
        self.events: List[Dict[str, Any]] = []

    def send(
        self,
        message_type: str,
        episode_id: int,
        sequence: int,
        payload: Dict[str, Any],
    ) -> None:
        envelope = {
            "schema_version": self._schema_version,
            "message_type": message_type,
            "run_id": self._run_id,
            "episode_id": episode_id,
            "sequence": sequence,
            "payload": payload,
        }
        message = OutgoingMessage()
        message.write_string(json.dumps(envelope, separators=(",", ":"), sort_keys=True))
        self.queue_message_to_send(message)

    def on_message_received(self, message: IncomingMessage) -> None:
        envelope = json.loads(message.read_string())
        required = {
            "schema_version",
            "message_type",
            "run_id",
            "episode_id",
            "sequence",
            "payload",
        }
        if set(envelope) != required:
            raise RuntimeError(f"Unexpected side-channel envelope fields: {sorted(envelope)}")
        if envelope["schema_version"] != self._schema_version:
            raise RuntimeError("Unity returned an unexpected side-channel schema.")
        if envelope["run_id"] != self._run_id:
            raise RuntimeError("Unity returned an unexpected run ID.")
        if envelope["message_type"] not in {
            "run_ready",
            "episode_started",
            "episode_ended",
            "infrastructure_error",
        }:
            raise RuntimeError("Unity returned an unsupported message type.")

        episode_id = int(envelope["episode_id"])
        expected_sequence = self._incoming_sequence.get(episode_id, 0) + 1
        if int(envelope["sequence"]) != expected_sequence:
            raise RuntimeError(
                f"Side-channel sequence for episode {episode_id} was "
                f"{envelope['sequence']}, expected {expected_sequence}."
            )
        self._incoming_sequence[episode_id] = expected_sequence
        self.events.append(
            {
                "message_type": envelope["message_type"],
                "episode_id": episode_id,
                "sequence": expected_sequence,
                "payload": envelope["payload"],
            }
        )


def round_floats(values: np.ndarray) -> List[float]:
    return [round(float(value), 7) for value in values.tolist()]


def action_masks_for_agent(decision_steps: Any, index: int) -> List[List[bool]]:
    if decision_steps.action_mask is None:
        raise RuntimeError("The discrete smoke behavior did not return action masks.")
    return [
        [bool(value) for value in branch[index].tolist()]
        for branch in decision_steps.action_mask
    ]


def choose_action(observation: np.ndarray, expected_end: str) -> Tuple[int, int]:
    position = int(round(float(observation[0])))
    target = int(round(float(observation[1])))
    if expected_end == "truncation":
        return 0, 0
    if position < target:
        return 2, 0
    if position > target:
        return 1, 0
    return 0, 1


def finish_transition(
    pending: Dict[int, Dict[str, Any]],
    agent_id: int,
    reward: float,
    next_observation: np.ndarray,
    terminal: bool,
    interrupted: bool,
    episode_traces: Dict[int, Dict[str, Any]],
) -> None:
    transition = pending.pop(agent_id, None)
    if transition is None:
        raise RuntimeError(f"Missing pending transition for agent {agent_id}.")
    transition["reward"] = round(float(reward), 7)
    transition["next_observation"] = round_floats(next_observation)
    transition["terminal"] = terminal
    transition["interrupted"] = interrupted
    episode_traces[transition["episode_id"]]["transitions"].append(transition)


def validate_side_channel_events(
    events: List[Dict[str, Any]],
    smoke_contract: Dict[str, Any],
) -> None:
    errors = [event for event in events if event["message_type"] == "infrastructure_error"]
    if errors:
        raise RuntimeError(f"Unity reported infrastructure errors: {errors}")

    event_keys = [
        (event["message_type"], event["episode_id"])
        for event in events
    ]
    expected = [("run_ready", 0)]
    for episode in smoke_contract["episodes"]:
        episode_id = int(episode["episode_id"])
        expected.extend(
            [
                ("episode_started", episode_id),
                ("episode_ended", episode_id),
            ]
        )
    if event_keys != expected:
        raise RuntimeError(f"Side-channel events were {event_keys}, expected {expected}.")

    ready = events[0]["payload"]
    if ready.get("unity_package_version") != UNITY_ML_AGENTS_VERSION:
        raise RuntimeError("Unity reported the wrong ML-Agents package version.")
    if ready.get("contract_sha256") != sha256_file(CONTRACT_PATH):
        raise RuntimeError("Unity reported the wrong research-contract hash.")
    if ready.get("observation_size") != smoke_contract["observation"]["size"]:
        raise RuntimeError("Unity reported the wrong observation size.")
    if ready.get("discrete_branches") != smoke_contract["actions"]["discrete_branches"]:
        raise RuntimeError("Unity reported the wrong discrete action branches.")

    ended = {
        event["episode_id"]: event["payload"]
        for event in events
        if event["message_type"] == "episode_ended"
    }
    for episode in smoke_contract["episodes"]:
        payload = ended[int(episode["episode_id"])]
        if payload.get("reason") != episode["reason"]:
            raise RuntimeError("Unity returned the wrong episode end reason.")
        if bool(payload.get("interrupted")) != bool(episode["interrupted"]):
            raise RuntimeError("Unity returned the wrong interrupted state.")


def execute_trace(
    executable: Path,
    run_id: str,
    base_seed: int,
    output_directory: Path,
    smoke_contract: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    side_channel = ResearchSmokeSideChannel(run_id, smoke_contract)
    side_channel.send(
        "configure_run",
        0,
        1,
        {"contract_sha256": sha256_file(CONTRACT_PATH)},
    )
    for episode in smoke_contract["episodes"]:
        side_channel.send(
            "configure_episode",
            int(episode["episode_id"]),
            1,
            {
                "seed": base_seed + int(episode["seed_offset"]),
                "decision_limit": int(episode["decision_limit"]),
                "expected_end": episode["expected_end"],
            },
        )

    player_log_directory = output_directory / "player-log"
    player_log_directory.mkdir(parents=True, exist_ok=True)
    environment = UnityEnvironment(
        file_name=str(executable),
        seed=base_seed,
        no_graphics=True,
        timeout_wait=120,
        side_channels=[side_channel],
        log_folder=str(player_log_directory),
    )

    episode_specs = {
        int(episode["episode_id"]): episode
        for episode in smoke_contract["episodes"]
    }
    episode_traces = {
        episode_id: {
            "episode_id": episode_id,
            "seed": base_seed + int(spec["seed_offset"]),
            "expected_end": spec["expected_end"],
            "transitions": [],
        }
        for episode_id, spec in episode_specs.items()
    }
    pending: Dict[int, Dict[str, Any]] = {}
    completed_episodes = 0
    total_iterations = 0
    maximum_iterations = (
        sum(int(spec["decision_limit"]) for spec in episode_specs.values())
        + len(episode_specs)
        + 2
    )
    measurement = smoke_contract.get("measurement")
    expected_decision_count = (
        int(measurement["decision_count"])
        if measurement is not None
        else None
    )
    decisions_sent = 0
    timing_started_ns: Optional[int] = None
    timing_ended_ns: Optional[int] = None

    try:
        environment.reset()
        behavior_names = list(environment.behavior_specs)
        if len(behavior_names) != 1:
            raise RuntimeError(f"Expected one behavior, found {behavior_names}.")
        behavior_name = behavior_names[0]
        if not behavior_name.startswith(smoke_contract["behavior_name"]):
            raise RuntimeError(f"Unexpected behavior name {behavior_name}.")

        behavior_spec = environment.behavior_specs[behavior_name]
        observation_shapes = [list(spec.shape) for spec in behavior_spec.observation_specs]
        action_branches = list(behavior_spec.action_spec.discrete_branches)
        if observation_shapes != [[smoke_contract["observation"]["size"]]]:
            raise RuntimeError(f"Unexpected observation shapes {observation_shapes}.")
        if action_branches != smoke_contract["actions"]["discrete_branches"]:
            raise RuntimeError(f"Unexpected action branches {action_branches}.")

        while completed_episodes < len(episode_specs):
            total_iterations += 1
            if total_iterations > maximum_iterations:
                raise RuntimeError(
                    "Communicator trace exceeded its contract-derived iteration bound."
                )

            decision_steps, terminal_steps = environment.get_steps(behavior_name)

            for terminal_index, raw_agent_id in enumerate(terminal_steps.agent_id):
                agent_id = int(raw_agent_id)
                finish_transition(
                    pending,
                    agent_id,
                    float(terminal_steps.reward[terminal_index]),
                    terminal_steps.obs[0][terminal_index],
                    True,
                    bool(terminal_steps.interrupted[terminal_index]),
                    episode_traces,
                )
                completed_episodes += 1

            if completed_episodes >= len(episode_specs):
                break

            active_episode_id = completed_episodes + 1
            for decision_index, raw_agent_id in enumerate(decision_steps.agent_id):
                agent_id = int(raw_agent_id)
                observation = decision_steps.obs[0][decision_index]
                if agent_id in pending:
                    finish_transition(
                        pending,
                        agent_id,
                        float(decision_steps.reward[decision_index]),
                        observation,
                        False,
                        False,
                        episode_traces,
                    )

                spec = episode_specs[active_episode_id]
                movement, submit = choose_action(observation, spec["expected_end"])
                masks = action_masks_for_agent(decision_steps, decision_index)
                if masks[0][movement] or masks[1][submit]:
                    raise RuntimeError(
                        f"Driver selected a masked action {(movement, submit)} from {masks}."
                    )
                pending[agent_id] = {
                    "episode_id": active_episode_id,
                    "decision": len(episode_traces[active_episode_id]["transitions"]),
                    "observation": round_floats(observation),
                    "action_masks": masks,
                    "action": [movement, submit],
                }

            if len(decision_steps) > 0:
                if measurement is not None and timing_started_ns is None:
                    timing_started_ns = time.perf_counter_ns()
                actions = np.zeros((len(decision_steps), 2), dtype=np.int32)
                for decision_index, raw_agent_id in enumerate(decision_steps.agent_id):
                    selected = pending[int(raw_agent_id)]["action"]
                    actions[decision_index] = selected
                environment.set_actions(behavior_name, ActionTuple(discrete=actions))
                decisions_sent += len(decision_steps)
                if (
                    expected_decision_count is not None
                    and decisions_sent > expected_decision_count
                ):
                    raise RuntimeError(
                        "CPU reference trace exceeded its registered decision count."
                    )

            environment.step()
            if (
                expected_decision_count is not None
                and decisions_sent == expected_decision_count
                and timing_ended_ns is None
            ):
                timing_ended_ns = time.perf_counter_ns()

        if pending:
            raise RuntimeError(f"Unfinished transitions remain: {sorted(pending)}")

        validate_side_channel_events(side_channel.events, smoke_contract)
        for episode in smoke_contract["episodes"]:
            episode_id = int(episode["episode_id"])
            transitions = episode_traces[episode_id]["transitions"]
            if not transitions:
                raise RuntimeError(f"Episode {episode_id} has no transitions.")
            final = transitions[-1]
            if not final["terminal"]:
                raise RuntimeError(f"Episode {episode_id} has no terminal step.")
            if final["interrupted"] != bool(episode["interrupted"]):
                raise RuntimeError(f"Episode {episode_id} has the wrong interrupted result.")

        performance = None
        if measurement is not None:
            if decisions_sent != expected_decision_count:
                raise RuntimeError(
                    f"CPU reference trace recorded {decisions_sent} decisions, "
                    f"expected {expected_decision_count}."
                )
            if timing_started_ns is None or timing_ended_ns is None:
                raise RuntimeError("CPU reference timing boundary was not observed.")
            elapsed_seconds = (timing_ended_ns - timing_started_ns) / 1_000_000_000
            if elapsed_seconds <= 0:
                raise RuntimeError("CPU reference elapsed time must be positive.")
            performance = {
                "measurement_scope": measurement["scope"],
                "decision_count": decisions_sent,
                "elapsed_seconds": round(elapsed_seconds, 9),
                "decisions_per_second": round(decisions_sent / elapsed_seconds, 3),
                "startup_excluded": True,
                "timing_clock": "time.perf_counter_ns",
            }

        trace = {
            "trace_format": smoke_contract.get("trace_format", TRACE_FORMAT),
            "base_seed": base_seed,
            "behavior": {
                "name": smoke_contract["behavior_name"],
                "observation_shapes": observation_shapes,
                "discrete_branches": action_branches,
            },
            "side_channel_events": side_channel.events,
            "episodes": [
                episode_traces[episode_id]
                for episode_id in sorted(episode_traces)
            ],
        }
        return trace, performance
    finally:
        environment.close()


def windows_memory_bytes() -> int:
    if os.name != "nt":
        return 1

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return int(status.total_physical)


def windows_gpus() -> List[Dict[str, str]]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,DriverVersion | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
    )
    raw = json.loads(result.stdout)
    items = raw if isinstance(raw, list) else [raw]
    return [
        {
            "name": str(item["Name"]),
            "driver_version": str(item["DriverVersion"]),
        }
        for item in items
    ]


def windows_system_identity() -> Tuple[str, str, str, str]:
    if os.name != "nt":
        return (
            platform.system(),
            platform.version() or "unknown",
            platform.release() or "unknown",
            platform.processor() or "unknown-cpu",
        )

    command = (
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "[pscustomobject]@{Name=$os.Caption;Version=$os.Version;"
        "Build=$os.BuildNumber;Cpu=$cpu.Name} | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
    )
    identity = json.loads(result.stdout)
    return (
        str(identity["Name"]).strip(),
        str(identity["Version"]).strip(),
        str(identity["Build"]).strip(),
        str(identity["Cpu"]).strip(),
    )


def create_manifest(
    run_id: str,
    base_seed: int,
    output_directory: Path,
    compared: bool,
    smoke_contract: Dict[str, Any],
    smoke_contract_path: Path,
    performance: Optional[Dict[str, Any]],
    accelerator_candidate: Optional[str],
) -> Dict[str, Any]:
    relative_output = output_directory.resolve().relative_to(ARTIFACT_ROOT).as_posix()
    git_commit = run_command(["git", "rev-parse", "HEAD"])
    git_dirty = bool(run_command(["git", "status", "--porcelain"]))
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if pip_check.returncode != 0:
        raise RuntimeError(f"pip check failed: {pip_check.stdout}{pip_check.stderr}")

    os_name, os_version, os_build, cpu = windows_system_identity()
    seed_values = [base_seed + offset for offset in range(7)]
    is_cpu_reference = performance is not None

    manifest = {
        "schema_version": "quickdraw.run-manifest.v1",
        "run_id": run_id,
        "run_kind": "latency" if is_cpu_reference else "smoke",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "identity": {
            "condition_id": (
                "r1c-cpu-reference-trace"
                if is_cpu_reference
                else "r1b-communicator-smoke"
            ),
            "policy_id": "scripted-smoke-driver-v1",
            "scenario_set_id": (
                f"cpu-reference-seed-{base_seed}"
                if is_cpu_reference
                else f"communicator-smoke-seed-{base_seed}"
            ),
            "episode_count": len(smoke_contract["episodes"]),
        },
        "git": {"commit": git_commit, "dirty": git_dirty},
        "software": {
            "unity": {
                "editor_version": UNITY_VERSION,
                "editor_revision": UNITY_REVISION,
                "ml_agents_package": {
                    "version": UNITY_ML_AGENTS_VERSION,
                    "installed": True,
                },
            },
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "packages": {
                    "mlagents": version("mlagents"),
                    "mlagents-envs": version("mlagents-envs"),
                    "torch": version("torch"),
                    "numpy": version("numpy"),
                    "matplotlib": version("matplotlib"),
                    "pytest": version("pytest"),
                    "jsonschema": version("jsonschema"),
                },
            },
            "trainer_plugin": {"installed": False, "version": None},
        },
        "hardware": {
            "os": {"name": os_name, "version": os_version, "build": os_build},
            "cpu": cpu,
            "memory_bytes": windows_memory_bytes(),
            "gpus": windows_gpus(),
        },
        "contracts": {
            "schema_version": "quickdraw.research-contracts.v1",
            "sha256": sha256_file(CONTRACT_PATH),
        },
        "artifacts": {
            "root": "Artifacts/Experiments",
            "run_relative_path": relative_output,
        },
        "backend": {
            "reference": "cpu",
            "selected": "cpu",
            "accelerator_candidate": accelerator_candidate,
            "accelerator_status": "deferred",
            "reason": (
                "R1C records the CPU LLAPI transport reference only; "
                "accelerator parity is deferred."
                if is_cpu_reference
                else (
                    "R1E validates the Python 3.11 Unity communicator boundary "
                    "only; ROCm inference parity and throughput remain deferred."
                    if accelerator_candidate == "rocm"
                    else "R1B validates communication only; backend parity and "
                    "throughput remain deferred."
                )
            ),
        },
        "seeds": {
            "policy_initialization": seed_values[0],
            "replay_sampling": seed_values[1],
            "exploration": seed_values[2],
            "scenario": seed_values[3],
            "opponent": seed_values[4],
            "evaluation": seed_values[5],
            "analysis_bootstrap": seed_values[6],
        },
        "hashes": {
            "scene": sha256_file(SCENE_PATH),
            "configuration": sha256_file(smoke_contract_path),
            "policy": None,
            "model": None,
        },
        "validation": {
            "dependency_imports": True,
            "pip_check": True,
            "manifest_schema": True,
            "unity_communication": True,
            "notes": (
                [
                    "Completed one deterministic 10,000-decision truncation trace.",
                    "Measured CPU LLAPI transport round trips; process startup and trace serialization were excluded.",
                    "Canonical trace comparison passed." if compared else "Canonical trace captured for comparison.",
                    "No trainer, learned model, combat, Basic benchmark, AMD parity, or LLM code was exercised.",
                ]
                if is_cpu_reference
                else [
                    "Completed one terminal and one truncated deterministic communicator episode.",
                    "Canonical trace comparison passed." if compared else "Canonical trace captured for comparison.",
                    "No trainer, learned model, combat, Basic benchmark, AMD parity, or LLM code was exercised.",
                ]
            ),
        },
    }
    if performance is not None:
        manifest["performance"] = performance
    return manifest


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a deterministic communicator or CPU-reference trace."
    )
    parser.add_argument("--env", required=True, type=Path, help="Path to the smoke player executable.")
    parser.add_argument("--output", required=True, type=Path, help="Ignored run artifact directory.")
    parser.add_argument("--run-id", required=True, help="Run-manifest identifier.")
    parser.add_argument("--seed", required=True, type=int, help="Signed 31-bit base seed.")
    parser.add_argument("--compare-to", type=Path, help="Canonical trace from the first run.")
    parser.add_argument(
        "--mode",
        choices=("smoke", "cpu-reference"),
        default="smoke",
        help="Trace contract to run; defaults to the R1B smoke regression.",
    )
    parser.add_argument(
        "--accelerator-candidate",
        choices=("rocm",),
        default=None,
        help="Candidate recorded in the manifest; the scripted smoke stays on CPU.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    executable = arguments.env.resolve()
    output_directory = arguments.output.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if not 0 <= arguments.seed <= 2_147_483_640:
        raise ValueError("Base seed must leave room for all signed 31-bit seed categories.")
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")

    output_directory.mkdir(parents=True, exist_ok=True)
    smoke_contract_path = (
        CPU_REFERENCE_CONTRACT_PATH
        if arguments.mode == "cpu-reference"
        else SMOKE_CONTRACT_PATH
    )
    smoke_contract = json.loads(smoke_contract_path.read_text(encoding="utf-8"))
    if smoke_contract["side_channel"]["contract_sha256"] != sha256_file(CONTRACT_PATH):
        raise RuntimeError("The smoke config and frozen research-contract hash differ.")

    trace, performance = execute_trace(
        executable,
        arguments.run_id,
        arguments.seed,
        output_directory,
        smoke_contract,
    )
    trace_path = output_directory / "trace.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    compared = arguments.compare_to is not None
    if compared:
        reference = json.loads(arguments.compare_to.read_text(encoding="utf-8"))
        if trace != reference:
            raise RuntimeError(
                f"Canonical trace differs from reference {arguments.compare_to}."
            )

    manifest = create_manifest(
        arguments.run_id,
        arguments.seed,
        output_directory,
        compared,
        smoke_contract,
        smoke_contract_path,
        performance,
        arguments.accelerator_candidate,
    )
    schema = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(manifest)
    manifest_path = output_directory / "run-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"trace={trace_path}")
    print(f"manifest={manifest_path}")
    print(f"comparison={'pass' if compared else 'reference-captured'}")
    if performance is not None:
        print(f"decision_count={performance['decision_count']}")
        print(f"elapsed_seconds={performance['elapsed_seconds']}")
        print(f"decisions_per_second={performance['decisions_per_second']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
