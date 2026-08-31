from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import torch
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
    DirectReplayCollector,
    LLAPIContractError,
    LinearEpsilonSchedule,
    ScheduledEpsilonGreedyBDQActionSelector,
    load_controller_checkpoint,
    network_sha256,
    save_controller_checkpoint,
)
from quickdraw_bdq.checkpoint import (  # noqa: E402
    CHECKPOINT_SCHEMA_VERSION,
    boundary_summary,
)
from quickdraw_bdq.network import OBSERVATION_SHAPE  # noqa: E402


CONTRACT_PATH = HERE / "bdq-checkpoint-contract-v1.json"
REPO_ROOT = HERE.parents[1]
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-checkpoint-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-checkpoint-roundtrip-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
WORKER_TIMEOUT_SECONDS = 600
RESULT_SCHEMA_VERSION = "quickdraw.bdq-checkpoint-roundtrip-result.v1"


def _runtime_contract() -> Dict[str, str]:
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }


def _reference_settings() -> BDQOptimizationSettings:
    return BDQOptimizationSettings(
        replay_capacity=32,
        replay_warmup_decisions=24,
        batch_size=8,
        optimizer_update_interval_decisions=4,
    )


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)

    binding = contract["base_fifth_update_contract"]
    base_contract_path = REPO_ROOT / binding["path"]
    if _sha256_file(base_contract_path) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    base_contract = json.loads(base_contract_path.read_text(encoding="utf-8"))
    if base_contract["schema_version"] != binding["schema_version"]:
        raise LLAPIContractError("R3P's R3O schema binding drifted.")

    if contract["runtime"] != _runtime_contract():
        raise LLAPIContractError("The active runtime differs from R3P.")
    if contract["runtime"] != base_contract["runtime"]:
        raise LLAPIContractError("R3P runtime differs from R3O.")
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError("The R3P package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError("The R3P package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point returned.")
    if contract["package"] != base_contract["package"]:
        raise LLAPIContractError("R3P package boundary differs from R3O.")

    boundary = contract["checkpoint_boundary"]
    if boundary["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise LLAPIContractError("R3P checkpoint schema version has drifted.")
    if not boundary["clean_boundary_required"]:
        raise LLAPIContractError("R3P must require a clean checkpoint boundary.")
    if boundary["failure_mode"] != "reject before any restored object is returned":
        raise LLAPIContractError("R3P checkpoint failure mode has drifted.")

    workload = contract["reference_workload"]
    settings = _reference_settings()
    if workload["settings"] != dataclasses.asdict(settings):
        raise LLAPIContractError("R3P reference workload settings have drifted.")
    if (
        workload["schedule"]
        != dataclasses.asdict(LinearEpsilonSchedule())
    ):
        raise LLAPIContractError("R3P reference schedule has drifted.")
    transitions = workload["transitions_before_checkpoint"]
    if transitions != 36:
        raise LLAPIContractError("R3P reference boundary is not 36 transitions.")
    if workload["optimizer_updates_at_save"] != 4:
        raise LLAPIContractError("R3P reference boundary must hold 4 updates.")
    if workload["replay_size_at_save"] != min(transitions, settings.replay_capacity):
        raise LLAPIContractError("R3P replay size at save has drifted.")
    if workload["replay_cursor_at_save"] != transitions % settings.replay_capacity:
        raise LLAPIContractError("R3P replay cursor at save has drifted.")
    if workload["replay_unique_frames_at_save"] != 20:
        raise LLAPIContractError("R3P replay frame count at save has drifted.")
    next_update_count = workload["next_update_decision_count"]
    if next_update_count != transitions + workload["continuation_transitions"]:
        raise LLAPIContractError("R3P continuation does not reach update 5.")
    if next_update_count % settings.optimizer_update_interval_decisions != 0:
        raise LLAPIContractError("R3P continuation does not open an update.")
    if workload["bounded_optimizer_updates_after_restore"] != 1:
        raise LLAPIContractError("R3P must bound restoration to one update.")

    determinism = contract["determinism"]
    if determinism["fresh_processes"] != 3:
        raise LLAPIContractError("R3P requires three fresh processes.")
    if determinism["unity_player_required"]:
        raise LLAPIContractError("R3P must not require a Unity player.")
    return result_schema


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_deterministic_execution() -> None:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)


def _observation(value: float) -> np.ndarray:
    return np.full(OBSERVATION_SHAPE, value, dtype=np.float32)


def _masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def _drive_transition(
    index: int,
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    collector: DirectReplayCollector,
) -> tuple[list[int], Any]:
    masks = _masks()
    observation = _observation((index % 20) / 20.0)
    action = selector.select(
        observation,
        masks,
        completed_transition_count=controller.decision_count,
    )
    collector.begin(0, observation, action, masks)
    _, result = collector.complete(
        0,
        float((index % 5) - 2),
        _observation(((index + 1) % 20) / 20.0),
        masks,
        terminated=index % 11 == 10,
        truncated=index % 7 == 6,
    )
    return [int(value) for value in action], result


def _build_trainer() -> tuple[
    BDQOptimizerController,
    ScheduledEpsilonGreedyBDQActionSelector,
    DirectReplayCollector,
]:
    controller = BDQOptimizerController(51001, _reference_settings())
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        controller.online_network,
        schedule=LinearEpsilonSchedule(),
        seed=61001,
    )
    collector = DirectReplayCollector(controller)
    return controller, selector, collector


class _ReplaySampleRecorder:
    """Record replay sample indices without changing any drawn stream."""

    def __init__(self, controller: BDQOptimizerController) -> None:
        replay = controller.replay
        self.samples: list[list[int]] = []
        original_sample = replay.sample

        def recording_sample(batch_size: int) -> Any:
            batch = original_sample(batch_size)
            self.samples.append(
                [int(value) for value in batch.indices]
            )
            return batch

        replay.sample = recording_sample  # type: ignore[method-assign]


def _drive_continuation(
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    collector: DirectReplayCollector,
    first_index: int,
) -> Dict[str, Any]:
    recorder = _ReplaySampleRecorder(controller)
    actions: list[list[int]] = []
    update = None
    for index in range(first_index, first_index + 4):
        action, result = _drive_transition(
            index, controller, selector, collector
        )
        actions.append(action)
        if result.updated:
            update = result
    if update is None or not update.updated:
        raise LLAPIContractError("R3P continuation did not open an update.")
    if update.optimizer_update_count != 5 or update.target_synced:
        raise LLAPIContractError("R3P continuation left the bounded boundary.")
    return {
        "decision_count": int(update.decision_count),
        "optimizer_update_count": int(update.optimizer_update_count),
        "replay_size": int(update.replay_size),
        "target_sync_count": int(update.target_sync_count),
        "sampled_indices": recorder.samples[-1],
        "loss": float(update.loss),
        "mean_absolute_td_error": float(update.mean_absolute_td_error),
        "online_after_sha256": network_sha256(controller.online_network),
        "target_after_sha256": network_sha256(controller.target_network),
        "continuation_actions": actions,
    }


def _write_summary(summary: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_reference_worker(summary_path: Path) -> int:
    _configure_deterministic_execution()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    transitions = contract["reference_workload"]["transitions_before_checkpoint"]
    controller, selector, collector = _build_trainer()
    for index in range(transitions):
        _drive_transition(index, controller, selector, collector)
    at_boundary = boundary_summary(controller, selector, collector)
    next_update = _drive_continuation(controller, selector, collector, transitions)
    if next_update["online_after_sha256"] == at_boundary[
        "online_network_sha256"
    ]:
        raise LLAPIContractError("R3P reference update 5 changed no weights.")
    _write_summary(
        {"at_boundary": at_boundary, "next_update": next_update},
        summary_path,
    )
    print(f"summary={summary_path}")
    return 0


def _run_saver_worker(
    checkpoint_path: Path,
    summary_path: Path,
) -> int:
    _configure_deterministic_execution()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    transitions = contract["reference_workload"]["transitions_before_checkpoint"]
    controller, selector, collector = _build_trainer()
    for index in range(transitions):
        _drive_transition(index, controller, selector, collector)
    summary = save_controller_checkpoint(
        checkpoint_path, controller, collector, selector
    )
    _write_summary(
        {
            "at_boundary": summary,
            "checkpoint_sha256": _sha256_file(checkpoint_path),
            "checkpoint_bytes": checkpoint_path.stat().st_size,
        },
        summary_path,
    )
    print(f"checkpoint={checkpoint_path}")
    print(f"summary={summary_path}")
    return 0


def _run_restored_worker(
    checkpoint_path: Path,
    summary_path: Path,
) -> int:
    _configure_deterministic_execution()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    transitions = contract["reference_workload"]["transitions_before_checkpoint"]
    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=_reference_settings(),
        controller_seed=51001,
        exploration_seed=61001,
        schedule=LinearEpsilonSchedule(),
    )
    next_update = _drive_continuation(
        loaded.controller,
        loaded.selector,
        loaded.collector,
        transitions,
    )
    _write_summary(
        {
            "restored_boundary": loaded.verification,
            "next_update": next_update,
        },
        summary_path,
    )
    print(f"summary={summary_path}")
    return 0


def _spawn_worker(
    output_directory: Path,
    arguments: Sequence[str],
    log_name: str,
) -> None:
    command = [sys.executable, "-B", str(Path(__file__).resolve()), *arguments]
    process_environment = dict(os.environ)
    process_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process_environment["OMP_NUM_THREADS"] = "1"
    process_environment["MKL_NUM_THREADS"] = "1"
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=process_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=WORKER_TIMEOUT_SECONDS,
        check=False,
    )
    log_path = output_directory / log_name
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"R3P worker {log_name} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prove a deterministic Python trainer checkpoint round-trip "
            "against an uninterrupted reference without Unity."
        )
    )
    parser.add_argument(
        "--mode",
        choices=["reference", "saver", "restored"],
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--summary", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.mode is not None:
        if arguments.output is not None:
            raise ValueError("Worker mode must not set --output.")
        if arguments.mode in {"saver", "restored"}:
            if (
                arguments.checkpoint is None
                or arguments.summary is None
            ):
                raise ValueError(
                    "Worker mode requires --checkpoint and --summary."
                )
        if arguments.mode == "reference" and arguments.summary is None:
            raise ValueError("Reference mode requires --summary.")
        return "worker"
    if arguments.checkpoint is not None or arguments.summary is not None:
        raise ValueError(
            "Parent mode requires only --output and no worker arguments."
        )
    if arguments.output is None:
        raise ValueError("Parent mode requires --output.")
    return "parent"


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result_schema = validate_contract(contract)

    if mode == "worker":
        assert arguments.mode is not None
        if arguments.mode == "reference":
            assert arguments.summary is not None
            return _run_reference_worker(arguments.summary.resolve())
        assert arguments.checkpoint is not None
        assert arguments.summary is not None
        if arguments.mode == "saver":
            return _run_saver_worker(
                arguments.checkpoint.resolve(),
                arguments.summary.resolve(),
            )
        return _run_restored_worker(
            arguments.checkpoint.resolve(),
            arguments.summary.resolve(),
        )

    assert arguments.output is not None
    output_directory = arguments.output.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(f"R3P output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)

    checkpoint_path = output_directory / "checkpoint.json"
    _spawn_worker(
        output_directory,
        ["--mode", "saver", "--checkpoint", str(checkpoint_path), "--summary", str(output_directory / "saver.json")],
        "saver.log",
    )
    _spawn_worker(
        output_directory,
        ["--mode", "reference", "--summary", str(output_directory / "reference.json")],
        "reference.log",
    )
    _spawn_worker(
        output_directory,
        ["--mode", "restored", "--checkpoint", str(checkpoint_path), "--summary", str(output_directory / "restored.json")],
        "restored.log",
    )

    saver_summary = json.loads(
        (output_directory / "saver.json").read_text(encoding="utf-8")
    )
    reference_summary = json.loads(
        (output_directory / "reference.json").read_text(encoding="utf-8")
    )
    restored_summary = json.loads(
        (output_directory / "restored.json").read_text(encoding="utf-8")
    )

    if saver_summary["at_boundary"] != reference_summary["at_boundary"]:
        raise LLAPIContractError(
            "R3P reference and saver boundaries differ across processes."
        )
    if restored_summary["restored_boundary"] != reference_summary[
        "at_boundary"
    ]:
        raise LLAPIContractError(
            "R3P restored boundary differs from the reference boundary."
        )
    if restored_summary["next_update"] != reference_summary["next_update"]:
        raise LLAPIContractError(
            "R3P restored continuation differs from the uninterrupted "
            "reference."
        )
    next_update = reference_summary["next_update"]
    if next_update["online_after_sha256"] == reference_summary["at_boundary"][
        "online_network_sha256"
    ]:
        raise LLAPIContractError("R3P restored update 5 changed no weights.")

    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "contract_sha256": _sha256_file(CONTRACT_PATH),
        "checkpoint_sha256": saver_summary["checkpoint_sha256"],
        "checkpoint_bytes": saver_summary["checkpoint_bytes"],
        "fresh_process_count": 3,
        "clean_boundary_pending_agent_ids": [],
        "reference_and_saver_boundaries_identical": True,
        "restored_boundary_matches_reference": True,
        "same_next_replay_sample": True,
        "same_next_optimizer_result": True,
        "loaded_without_unity": True,
        "at_boundary": reference_summary["at_boundary"],
        "next_update": next_update,
    }
    Draft202012Validator(result_schema).validate(result)
    result_path = output_directory / "result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    at_boundary = result["at_boundary"]
    print(f"result={result_path}")
    print(f"checkpoint={checkpoint_path}")
    print(f"checkpoint_sha256={result['checkpoint_sha256']}")
    print(f"checkpoint_bytes={result['checkpoint_bytes']}")
    print("fresh_processes=3")
    print("transitions_before_checkpoint=36")
    print(f"decision_count_at_save={at_boundary['decision_count']}")
    print(f"optimizer_updates_at_save={at_boundary['optimizer_update_count']}")
    print(f"target_syncs_at_save={at_boundary['target_sync_count']}")
    print(f"replay_size_at_save={at_boundary['replay']['size']}")
    print(f"replay_cursor_at_save={at_boundary['replay']['cursor']}")
    print(
        "replay_unique_frames_at_save="
        f"{at_boundary['replay']['unique_frame_count']}"
    )
    print("clean_boundary=pass")
    print(f"next_update_decision_count={next_update['decision_count']}")
    print(f"next_update_loss={next_update['loss']}")
    print(
        "next_update_mean_absolute_td_error="
        f"{next_update['mean_absolute_td_error']}"
    )
    print(f"sampled_indices={next_update['sampled_indices']}")
    print(
        "next_update_online_sha256="
        f"{next_update['online_after_sha256']}"
    )
    print("reference_and_saver_boundaries_identical=pass")
    print("restored_boundary_matches_reference=pass")
    print("same_next_replay_sample=pass")
    print("same_next_optimizer_result=pass")
    print("loaded_without_unity=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
