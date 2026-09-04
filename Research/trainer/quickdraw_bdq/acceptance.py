"""Shared, non-scientific plumbing for the BDQ acceptance runners.

Milestone runners own their registered assertions and summaries. This module owns
only stable serialization, runtime metadata, and fresh-process orchestration so
later milestones do not import implementation details from earlier runner files.
"""

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
from typing import Any, Callable, Dict, Sequence

import numpy as np
import torch
from jsonschema import Draft202012Validator

from .action_space import joint_indices_from_branches
from .llapi import LLAPIContractError, observation_sha256
from .optimizer import BDQOptimizationSettings
from .replay import ReplayTransition


TRAINER_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = TRAINER_ROOT.parents[1]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
PYPROJECT_PATH = TRAINER_ROOT / "pyproject.toml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def runtime_contract() -> Dict[str, str]:
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }


def registered_settings(settings: BDQOptimizationSettings) -> Dict[str, Any]:
    return {
        "replay_capacity": settings.replay_capacity,
        "replay_warmup_decisions": settings.replay_warmup_decisions,
        "batch_size": settings.batch_size,
        "gamma": settings.gamma,
        "optimizer": "Adam",
        "learning_rate": settings.learning_rate,
        "optimizer_update_interval_decisions": (
            settings.optimizer_update_interval_decisions
        ),
        "hard_target_sync_interval_optimizer_updates": (
            settings.hard_target_sync_interval_optimizer_updates
        ),
    }


def masks_to_json(masks: Sequence[np.ndarray]) -> list[list[bool]]:
    return [[bool(value) for value in branch] for branch in masks]


def transition_to_json(
    transition: ReplayTransition,
    index: int,
    episode_index: int,
    episode_decision_index: int,
) -> Dict[str, Any]:
    return {
        "index": index,
        "episode_index": episode_index,
        "episode_decision_index": episode_decision_index,
        "observation_sha256": observation_sha256(transition.observation),
        "next_observation_sha256": observation_sha256(
            transition.next_observation
        ),
        "observation_shape": list(transition.observation.shape),
        "action": [int(value) for value in transition.action],
        "reward": float(transition.reward),
        "action_masks": masks_to_json(transition.action_masks),
        "next_action_masks": masks_to_json(transition.next_action_masks),
        "terminated": transition.terminated,
        "truncated": transition.truncated,
    }


def episode_record(
    *,
    episode_index: int,
    transition_start_index: int,
    transition_count: int,
    episode_return: float,
    end_kind: str,
) -> Dict[str, Any]:
    if end_kind == "terminal":
        reason = "target_hit"
        interrupted = False
        unity_episode_ended = True
    elif end_kind == "truncated":
        reason = "decision_limit"
        interrupted = True
        unity_episode_ended = True
    elif end_kind == "collection_cutoff":
        reason = "collection_limit"
        interrupted = False
        unity_episode_ended = False
    else:
        raise LLAPIContractError(f"Unexpected R3E episode end kind {end_kind}.")
    return {
        "episode_index": episode_index,
        "transition_start_index": transition_start_index,
        "transition_count": transition_count,
        "return": float(episode_return),
        "end_kind": end_kind,
        "reason": reason,
        "interrupted": interrupted,
        "unity_episode_ended": unity_episode_ended,
    }


def action_tuple_counts(transitions: Sequence[Dict[str, Any]]) -> list[int]:
    counts = [0] * 6
    for transition in transitions:
        action = np.asarray(transition["action"], dtype=np.int64)
        joint = int(
            joint_indices_from_branches(
                torch.as_tensor(action[None, ...], dtype=torch.int64)
            )[0].item()
        )
        counts[joint] += 1
    return counts


def masked_argmax(
    branch_values: Sequence[float],
    unavailable: Sequence[bool],
    *,
    task_name: str = "R3H",
) -> int:
    available = [
        index for index, is_unavailable in enumerate(unavailable) if not is_unavailable
    ]
    if not available:
        raise LLAPIContractError(
            f"{task_name} handoff mask removes every branch action."
        )
    return max(available, key=lambda index: branch_values[index])


def validate_schema_pair(
    contract: Dict[str, Any],
    contract_schema_path: Path,
    result_schema_path: Path,
) -> Dict[str, Any]:
    contract_schema = json.loads(contract_schema_path.read_text(encoding="utf-8"))
    result_schema = json.loads(result_schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    return result_schema


def validate_runtime_and_package(
    contract: Dict[str, Any],
    task_name: str,
    *,
    pyproject_path: Path = PYPROJECT_PATH,
) -> None:
    if contract["runtime"] != runtime_contract():
        raise LLAPIContractError(f"The active runtime differs from {task_name}.")
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError(f"The {task_name} package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError(f"The {task_name} package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point returned.")


def standard_execution_mode(arguments: argparse.Namespace) -> str:
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


def comparison_execution_mode(arguments: argparse.Namespace) -> str:
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


def validate_distinct_trace_paths(
    first_path: Path,
    second_path: Path,
    *,
    task_name: str,
) -> None:
    if not first_path.is_file():
        raise FileNotFoundError(first_path)
    if not second_path.is_file():
        raise FileNotFoundError(second_path)
    if first_path == second_path or first_path.samefile(second_path):
        raise ValueError(f"{task_name} comparison requires two distinct trace files.")


def run_fresh_worker_process(
    *,
    runner_path: Path,
    executable: Path,
    output_directory: Path,
    worker_index: int,
    contract: Dict[str, Any] | None,
    trace_file_name: str,
    task_name: str,
    announce: bool,
    repo_root: Path = REPO_ROOT,
    timeout_seconds: int = 1800,
) -> tuple[Dict[str, Any], Path]:
    worker_output = output_directory / f"run-{worker_index + 1}"
    if announce:
        print(f"worker_{worker_index + 1}=starting", flush=True)
    command = [
        sys.executable,
        "-B",
        str(runner_path.resolve()),
        f"--env={executable}",
        f"--worker-output={worker_output}",
        f"--worker-index={worker_index}",
    ]
    process_environment = dict(os.environ)
    process_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if contract is not None:
        thread_count = str(contract["determinism"]["torch_num_threads"])
        process_environment["OMP_NUM_THREADS"] = thread_count
        process_environment["MKL_NUM_THREADS"] = thread_count
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=process_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    log_path = output_directory / f"worker-{worker_index + 1}.log"
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Fresh {task_name} worker {worker_index + 1} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )
    trace_path = worker_output / trace_file_name
    if not trace_path.is_file():
        raise RuntimeError(f"Fresh {task_name} worker omitted {trace_path}.")
    if announce:
        print(f"worker_{worker_index + 1}=complete", flush=True)
    return json.loads(trace_path.read_text(encoding="utf-8")), trace_path


def write_two_process_result(
    *,
    first: Dict[str, Any],
    first_path: Path,
    second: Dict[str, Any],
    second_path: Path,
    output_directory: Path,
    result_schema: Dict[str, Any],
    result_schema_version: str,
    contract_path: Path,
    task_name: str,
    validate_trace: Callable[[Dict[str, Any], Dict[str, Any]], None],
) -> Path:
    validate_trace(first, result_schema)
    validate_trace(second, result_schema)
    if first != second or first_path.read_bytes() != second_path.read_bytes():
        raise LLAPIContractError(
            f"Fresh {task_name} traces differ: {first_path} versus {second_path}."
        )

    result = {
        "schema_version": result_schema_version,
        "contract_sha256": sha256_file(contract_path),
        "fresh_process_count": 2,
        "exact_trace_equality": True,
        "canonical_trace_sha256": canonical_json_sha256(first),
        "canonical_trace": first,
    }
    Draft202012Validator(result_schema).validate(result)
    output_directory.mkdir(parents=True, exist_ok=True)
    result_path = output_directory / "result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result_path
