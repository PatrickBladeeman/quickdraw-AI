"""Run the bounded R3R continuation pilot or first-sync acceptance gate.

The live worker replays the accepted R3O prefix through a fresh complete Unity
player copy, validates the R3Q trainer boundary before selecting a continuation
action, and then stops at one registered clean boundary.  Checkpoint
continuation checks are deliberately synthetic and Unity-free; they do not
claim that a Unity process was resumed.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import torch
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    canonical_json_sha256,
    copy_complete_player,
    load_bound_contract,
    replay_sample_fingerprint,
    registered_settings,
    run_fresh_python_process,
    run_fresh_worker_process,
    validate_runtime_and_package,
)
from quickdraw_bdq.checkpoint import (  # noqa: E402
    CHECKPOINT_SCHEMA_VERSION,
    boundary_summary,
    checkpoint_state_sha256,
    load_controller_checkpoint,
    save_controller_checkpoint,
)
from quickdraw_bdq.exploration import LinearEpsilonSchedule  # noqa: E402
from quickdraw_bdq.llapi import (  # noqa: E402
    DirectReplayCollector,
    LLAPIContractError,
    ScheduledEpsilonGreedyBDQActionSelector,
    network_sha256,
    validate_action_masks,
)
from quickdraw_bdq.network import OBSERVATION_SHAPE  # noqa: E402
from quickdraw_bdq.optimizer import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
)
from quickdraw_bdq.provenance import sha256_file  # noqa: E402
from quickdraw_bdq.trajectory_validation import (  # noqa: E402
    validate_player_execution,
    validate_transition_prefix,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    configure_torch,
    validate_update_gate_trace,
    execute_update_gate_worker,
)


CONTRACT_PATH = HERE / "bdq-long-horizon-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-long-horizon-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-long-horizon-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
TRACE_FILE_NAME = "trace.json"
CHECKPOINT_FILE_NAME = "checkpoint.json"
CHECKPOINT_SUMMARY_FILE_NAME = "checkpoint-summary.json"
RESULT_FILE_NAME = "result.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-long-horizon-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-long-horizon-smoke-result.v1"
TASK_NAME = "R3R"
PILOT_WORKER_TIMEOUT_SECONDS = 3_600
SYNCHRONIZATION_WORKER_TIMEOUT_SECONDS = 14_400
BASE_WORKER_PORT = 5_045


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


def _expected_update_decisions(stage: Dict[str, Any]) -> list[int]:
    optimization = stage["optimization"]
    schedule = optimization["expected_update_decision_schedule"]
    count = int(schedule["optimizer_update_count"])
    decisions = [
        int(schedule["first_decision"])
        + index * int(schedule["interval_decisions"])
        for index in range(count)
    ]
    if decisions[-1] != int(schedule["last_decision"]):
        raise LLAPIContractError("Long-horizon update schedule is self-inconsistent.")
    return decisions


def _stage_contract(
    contract: Dict[str, Any],
    stage_name: str,
) -> Dict[str, Any]:
    stage = copy.deepcopy(contract["stages"][stage_name])
    decisions = _expected_update_decisions(stage)
    schedule = copy.deepcopy(contract["epsilon_schedule"])
    schedule.update(stage["epsilon_schedule"])
    sample_counts = [0, *(decision - 1 for decision in decisions)]
    schedule["trace_sample_completed_transition_counts"] = sample_counts
    return {
        "collection": stage["collection"],
        "optimization": stage["optimization"],
        "epsilon_schedule": schedule,
        "determinism": contract["determinism"],
    }


def _validate_stage_registration(
    contract: Dict[str, Any],
    stage_name: str,
) -> None:
    if stage_name not in {"pilot", "synchronization"}:
        raise ValueError(f"Unknown R3R stage: {stage_name}.")
    stage = contract["stages"][stage_name]
    expected = {
        "pilot": {
            "order": 1,
            "transition_limit": 13_996,
            "updates": 1_000,
            "syncs": 0,
            "last_decision": 13_996,
            "decay_selections": 3_995,
        },
        "synchronization": {
            "order": 2,
            "transition_limit": 49_996,
            "updates": 10_000,
            "syncs": 1,
            "last_decision": 49_996,
            "decay_selections": 39_995,
        },
    }[stage_name]
    if stage["order"] != expected["order"]:
        raise LLAPIContractError(f"{TASK_NAME} stage order drifted.")
    collection = stage["collection"]
    optimization = stage["optimization"]
    schedule = stage["epsilon_schedule"]
    if collection["start_transition_count"] != 10_016:
        raise LLAPIContractError(f"{TASK_NAME} continuation start drifted.")
    if collection["transition_limit"] != expected["transition_limit"]:
        raise LLAPIContractError(f"{TASK_NAME} transition boundary drifted.")
    if collection["scheduled_transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError(f"{TASK_NAME} schedule count differs from cutoff.")
    if optimization["expected_optimizer_updates"] != expected["updates"]:
        raise LLAPIContractError(f"{TASK_NAME} optimizer boundary drifted.")
    if optimization["expected_target_synchronizations"] != expected["syncs"]:
        raise LLAPIContractError(f"{TASK_NAME} synchronization boundary drifted.")
    if optimization["expected_target_sync_update_counts"] != (
        [] if expected["syncs"] == 0 else [10_000]
    ):
        raise LLAPIContractError(f"{TASK_NAME} synchronization event list drifted.")
    decisions = _expected_update_decisions(stage)
    if decisions[0] != 10_000 or decisions[-1] != expected["last_decision"]:
        raise LLAPIContractError(f"{TASK_NAME} update list boundary drifted.")
    if len(decisions) != expected["updates"] or any(
        right - left != 4 for left, right in zip(decisions, decisions[1:])
    ):
        raise LLAPIContractError(f"{TASK_NAME} update list interval drifted.")
    if schedule["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError(f"{TASK_NAME} selector count drifted.")
    if schedule["full_exploration_selection_count"] != 10_001:
        raise LLAPIContractError(f"{TASK_NAME} exploration boundary drifted.")
    if schedule["decay_selection_count"] != expected["decay_selections"]:
        raise LLAPIContractError(f"{TASK_NAME} decay selection count drifted.")
    if schedule["last_selection_completed_transition_count"] != (
        collection["transition_limit"] - 1
    ):
        raise LLAPIContractError(
            f"{TASK_NAME} registered last-selection boundary drifted."
        )
    settings = BDQOptimizationSettings()
    registered = {
        key: optimization[key]
        for key in (
            "replay_capacity",
            "replay_warmup_decisions",
            "batch_size",
            "gamma",
            "optimizer",
            "learning_rate",
            "optimizer_update_interval_decisions",
            "hard_target_sync_interval_optimizer_updates",
        )
    }
    if registered != registered_settings(settings):
        raise LLAPIContractError(f"{TASK_NAME} optimizer settings drifted.")
    final_boundary = stage["final_clean_boundary"]
    if {
        key: final_boundary[key]
        for key in (
            "transition_count",
            "decision_count",
            "optimizer_update_count",
            "target_sync_count",
            "last_selection_completed_transition_count",
        )
    } != {
        "transition_count": collection["transition_limit"],
        "decision_count": collection["transition_limit"],
        "optimizer_update_count": expected["updates"],
        "target_sync_count": expected["syncs"],
        "last_selection_completed_transition_count": collection[
            "transition_limit"
        ]
        - 1,
    }:
        raise LLAPIContractError(f"{TASK_NAME} final clean boundary drifted.")
    if expected["syncs"] == 0:
        if stage["target_sync_events"]:
            raise LLAPIContractError(f"{TASK_NAME} registered an unexpected sync.")
        if not final_boundary["target_unchanged_from_prefix"]:
            raise LLAPIContractError(f"{TASK_NAME} pilot target policy drifted.")
    else:
        if len(stage["target_sync_events"]) != 1:
            raise LLAPIContractError(f"{TASK_NAME} omitted its sync event.")
        sync = stage["target_sync_events"][0]
        if sync["optimizer_update_count"] != 10_000:
            raise LLAPIContractError(f"{TASK_NAME} sync update ordinal drifted.")
        if sync["target_before_sha256"] != contract["continuation_prefix"][
            "target_network_sha256"
        ]:
            raise LLAPIContractError(f"{TASK_NAME} sync target-before drifted.")
        if not final_boundary["target_equals_online"]:
            raise LLAPIContractError(f"{TASK_NAME} sync equality policy drifted.")


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the new contract before any relational or process work."""

    contract_schema = _read_json(CONTRACT_SCHEMA_PATH)
    result_schema = _read_json(RESULT_SCHEMA_PATH)
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)

    validate_runtime_and_package(contract, TASK_NAME, pyproject_path=PYPROJECT_PATH)
    validate_player_execution(
        contract["player_execution"], repo_root=HERE.parents[1], task_name=TASK_NAME
    )
    bindings = (
        ("base_r3o_contract", "R3O contract binding drifted."),
        ("base_r3q_contract", "R3Q contract binding drifted."),
        ("base_checkpoint_contract", "Checkpoint contract binding drifted."),
    )
    bound = {
        name: load_bound_contract(
            contract[name], schema_error=error, repo_root=HERE.parents[1]
        )
        for name, error in bindings
    }
    r3o = bound["base_r3o_contract"]
    r3q = bound["base_r3q_contract"]
    checkpoint_contract = bound["base_checkpoint_contract"]
    for name, base in bound.items():
        if base["runtime"] != contract["runtime"]:
            raise LLAPIContractError(f"{TASK_NAME} {name} runtime differs.")
        if base["package"] != contract["package"]:
            raise LLAPIContractError(f"{TASK_NAME} {name} package differs.")
    if r3q["base_fifth_update_contract"]["path"] != contract[
        "base_r3o_contract"
    ]["path"] or r3q["base_fifth_update_contract"]["sha256"] != contract[
        "base_r3o_contract"
    ]["sha256"]:
        raise LLAPIContractError(f"{TASK_NAME} no longer binds frozen R3O.")
    if r3q["base_checkpoint_contract"]["path"] != contract[
        "base_checkpoint_contract"
    ]["path"] or r3q["base_checkpoint_contract"]["sha256"] != contract[
        "base_checkpoint_contract"
    ]["sha256"]:
        raise LLAPIContractError(f"{TASK_NAME} no longer binds frozen checkpoint.")
    if checkpoint_contract["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise LLAPIContractError(f"{TASK_NAME} checkpoint schema drifted.")

    prefix = contract["continuation_prefix"]
    accepted = r3q["accepted_live_boundary"]
    for prefix_key, accepted_key in (
        ("transition_count", "transition_count"),
        ("decision_count", "decision_count"),
        ("optimizer_update_count", "optimizer_update_count"),
        ("target_sync_count", "target_sync_count"),
        ("online_network_sha256", "online_network_sha256"),
        ("target_network_sha256", "target_network_sha256"),
    ):
        if prefix[prefix_key] != accepted[accepted_key]:
            raise LLAPIContractError(f"{TASK_NAME} accepted prefix drifted.")
    if prefix["accepted_serialized_trace_sha256"] != accepted[
        "serialized_trace_sha256"
    ] or prefix["accepted_canonical_trace_sha256"] != accepted[
        "canonical_trace_sha256"
    ]:
        raise LLAPIContractError(f"{TASK_NAME} accepted trace binding drifted.")
    if r3o["collection"]["transition_limit"] != prefix["transition_count"]:
        raise LLAPIContractError(f"{TASK_NAME} R3O boundary drifted.")
    for stage_name in ("pilot", "synchronization"):
        _validate_stage_registration(contract, stage_name)
    if contract["stages"]["pilot"]["order"] >= contract["stages"][
        "synchronization"
    ]["order"]:
        raise LLAPIContractError(f"{TASK_NAME} package ordering drifted.")
    return result_schema


def _schedule(contract: Dict[str, Any]) -> LinearEpsilonSchedule:
    return LinearEpsilonSchedule(
        replay_warmup_decisions=int(contract["epsilon_schedule"]["replay_warmup_decisions"]),
        decay_decisions=int(contract["epsilon_schedule"]["decay_decisions"]),
        initial_epsilon=float(contract["epsilon_schedule"]["initial_epsilon"]),
        final_epsilon=float(contract["epsilon_schedule"]["final_epsilon"]),
    )


def _validate_prefix_boundary(
    controller: BDQOptimizerController,
    collector: DirectReplayCollector,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    transitions: Sequence[Dict[str, Any]],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    prefix = contract["continuation_prefix"]
    validate_transition_prefix(
        transitions,
        prefix,
        task_name=TASK_NAME,
        base_name="R3Q accepted",
    )
    if collector.pending_agent_ids:
        raise LLAPIContractError(f"{TASK_NAME} prefix has a pending decision.")
    summary = boundary_summary(controller, selector, collector)
    expected = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "controller_seed": 51001,
        "exploration_seed": 61001,
        "decision_count": prefix["decision_count"],
        "optimizer_update_count": prefix["optimizer_update_count"],
        "target_sync_count": prefix["target_sync_count"],
        "online_network_sha256": prefix["online_network_sha256"],
        "target_network_sha256": prefix["target_network_sha256"],
        "pending_agent_ids": [],
    }
    for key, value in expected.items():
        if summary[key] != value:
            raise LLAPIContractError(f"{TASK_NAME} continuation prefix {key} drifted.")
    if checkpoint_state_sha256(controller, collector, selector) != prefix[
        "checkpoint_state_sha256"
    ]:
        raise LLAPIContractError(f"{TASK_NAME} continuation checkpoint state drifted.")
    return {
        "transition_count": len(transitions),
        "decision_count": controller.decision_count,
        "optimizer_update_count": controller.optimizer_update_count,
        "target_sync_count": controller.target_sync_count,
        "canonical_transitions_sha256": canonical_json_sha256(
            list(transitions[: prefix["transition_count"]])
        ),
        "online_network_sha256": network_sha256(controller.online_network),
        "target_network_sha256": network_sha256(controller.target_network),
        "checkpoint_state_sha256": checkpoint_state_sha256(
            controller, collector, selector
        ),
        "pending_agent_ids": list(collector.pending_agent_ids),
        "post_boundary_action_selected": False,
    }


def _validate_trace(
    trace: Dict[str, Any],
    result_schema: Dict[str, Any],
    contract: Dict[str, Any],
    stage_name: str,
) -> None:
    trace_schema = {
        **result_schema["$defs"]["trace"],
        "$defs": result_schema["$defs"],
    }
    Draft202012Validator(trace_schema).validate(trace)
    if trace["stage"] != stage_name:
        raise LLAPIContractError(f"{TASK_NAME} trace stage differs from the runner.")
    stage = contract["stages"][stage_name]
    gate_contract = _stage_contract(contract, stage_name)
    expected_sync_updates = tuple(
        int(value)
        for value in stage["optimization"]["expected_target_sync_update_counts"]
    )
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name=f"{TASK_NAME} {stage_name}",
        require_update_hashes=True,
        contract=gate_contract,
        allow_replay_storage=True,
        allow_target_synchronization=bool(expected_sync_updates),
        expected_target_sync_updates=expected_sync_updates,
        require_target_hashes=True,
    )
    prefix = contract["continuation_prefix"]
    expected_prefix = {
        "transition_count": prefix["transition_count"],
        "decision_count": prefix["decision_count"],
        "optimizer_update_count": prefix["optimizer_update_count"],
        "target_sync_count": prefix["target_sync_count"],
        "canonical_transitions_sha256": prefix["canonical_transitions_sha256"],
        "online_network_sha256": prefix["online_network_sha256"],
        "target_network_sha256": prefix["target_network_sha256"],
        "checkpoint_state_sha256": prefix["checkpoint_state_sha256"],
        "pending_agent_ids": [],
        "post_boundary_action_selected": False,
    }
    if trace["continuation_prefix"] != expected_prefix:
        raise LLAPIContractError(f"{TASK_NAME} continuation prefix differs from contract.")
    final_boundary = stage["final_clean_boundary"]
    final = trace["final_clean_boundary"]
    for key in (
        "transition_count",
        "decision_count",
        "optimizer_update_count",
        "target_sync_count",
        "pending_agent_ids",
        "post_boundary_action_selected",
        "last_selection_completed_transition_count",
    ):
        if final[key] != final_boundary[key]:
            raise LLAPIContractError(f"{TASK_NAME} final boundary {key} drifted.")
    selector = trace["selector"]
    for key in (
        "selection_count",
        "full_exploration_selection_count",
        "decay_selection_count",
        "first_decay_completed_transition_count",
        "last_selection_completed_transition_count",
    ):
        if selector[key] != stage["epsilon_schedule"][key]:
            raise LLAPIContractError(f"{TASK_NAME} selector {key} drifted.")
    events = trace["optimization"]["update_events"]
    decisions = _expected_update_decisions(stage)
    if [event["decision_count"] for event in events] != decisions:
        raise LLAPIContractError(f"{TASK_NAME} update decision list drifted.")
    schedule = _schedule(contract)
    expected_epsilon_samples = [
        {
            "completed_transition_count": 0,
            "epsilon": schedule.epsilon_at(0),
        }
    ]
    expected_epsilon_samples.extend(
        {
            "completed_transition_count": decision - 1,
            "epsilon": schedule.epsilon_at(decision - 1),
        }
        for decision in decisions
    )
    if selector["epsilon_samples"] != expected_epsilon_samples:
        raise LLAPIContractError(f"{TASK_NAME} epsilon samples drifted.")
    if trace["optimization"]["update_epsilon_samples"] != [
        event["epsilon_sample"] for event in events
    ]:
        raise LLAPIContractError(f"{TASK_NAME} update epsilon samples drifted.")
    optimization = trace["optimization"]
    if optimization["target_weights_unchanged"] != (
        stage["optimization"]["expected_target_synchronizations"] == 0
    ):
        raise LLAPIContractError(f"{TASK_NAME} target-change flag drifted.")
    target_sync_events = optimization["target_sync_events"]
    if len(target_sync_events) != len(expected_sync_updates):
        raise LLAPIContractError(f"{TASK_NAME} target-sync list length drifted.")
    if expected_sync_updates:
        event = target_sync_events[0]
        if event["optimizer_update_count"] != 10_000:
            raise LLAPIContractError(f"{TASK_NAME} sync event ordinal drifted.")
        if event["target_before_sha256"] != prefix["target_network_sha256"]:
            raise LLAPIContractError(f"{TASK_NAME} target-before hash drifted.")
        if event["target_after_sha256"] != event["online_after_sha256"]:
            raise LLAPIContractError(f"{TASK_NAME} target-after equality drifted.")
        if optimization["target_after_sha256"] != optimization[
            "online_after_sha256"
        ]:
            raise LLAPIContractError(f"{TASK_NAME} final sync equality drifted.")
    else:
        if optimization["target_before_sha256"] != prefix["target_network_sha256"]:
            raise LLAPIContractError(f"{TASK_NAME} pilot target-before drifted.")
        if optimization["target_after_sha256"] != prefix["target_network_sha256"]:
            raise LLAPIContractError(f"{TASK_NAME} pilot target-after drifted.")


def _validate_worker_player_copy(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    required_siblings: Sequence[str],
) -> None:
    expected_root = (
        worker_output.resolve().parent
        / "player-copies"
        / f"run-{worker_index + 1}"
    ).resolve()
    if executable.resolve().parent != expected_root:
        raise LLAPIContractError(
            f"{TASK_NAME} worker must launch its run-owned complete player copy."
        )
    for sibling in (executable.name, *required_siblings):
        if not (expected_root / sibling).exists():
            raise LLAPIContractError(
                f"{TASK_NAME} worker player copy omitted {sibling}."
            )


def _validate_checkpoint_boundary(
    boundary: Dict[str, Any],
    trace: Dict[str, Any],
    contract: Dict[str, Any],
    stage_name: str,
) -> None:
    stage = contract["stages"][stage_name]
    final = stage["final_clean_boundary"]
    expected = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "controller_seed": 51001,
        "exploration_seed": 61001,
        "decision_count": final["decision_count"],
        "optimizer_update_count": final["optimizer_update_count"],
        "target_sync_count": final["target_sync_count"],
        "online_network_sha256": trace["optimization"]["online_after_sha256"],
        "target_network_sha256": trace["optimization"]["target_after_sha256"],
        "pending_agent_ids": [],
    }
    for key, value in expected.items():
        if boundary[key] != value:
            raise LLAPIContractError(f"{TASK_NAME} checkpoint boundary {key} drifted.")
    replay = boundary["replay"]
    if replay["capacity"] != 100_000 or replay["size"] != final["decision_count"]:
        raise LLAPIContractError(f"{TASK_NAME} checkpoint replay boundary drifted.")
    if replay["frame_reference_count"] != replay["size"] * 8:
        raise LLAPIContractError(f"{TASK_NAME} checkpoint replay references drifted.")
    if (
        replay["accounted_storage_bytes"]
        + replay["remaining_accounted_storage_bytes"]
        != replay["max_accounted_storage_bytes"]
    ):
        raise LLAPIContractError(f"{TASK_NAME} checkpoint storage accounting drifted.")


class _ReplaySampleRecorder:
    """Record exact replay samples without changing their random stream."""

    def __init__(self, controller: BDQOptimizerController) -> None:
        self.samples: list[Dict[str, Any]] = []
        replay = controller.replay
        original_sample = replay.sample

        def recording_sample(batch_size: int) -> Any:
            batch = original_sample(batch_size)
            self.samples.append(replay_sample_fingerprint(batch))
            return batch

        replay.sample = recording_sample  # type: ignore[method-assign]


def _observation(value: float) -> np.ndarray:
    return np.full(OBSERVATION_SHAPE, value, dtype=np.float32)


def _masks() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.zeros(3, dtype=np.bool_),
        np.zeros(2, dtype=np.bool_),
    )


def _drive_synthetic_transition(
    index: int,
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    collector: DirectReplayCollector,
) -> tuple[list[int], Any]:
    masks = _masks()
    validate_action_masks(masks, "synthetic action masks")
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
        truncated=index % 7 == 6 and index % 11 != 10,
    )
    return [int(value) for value in action], result


def _drive_next_update(
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    collector: DirectReplayCollector,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    recorder = _ReplaySampleRecorder(controller)
    actions: list[list[int]] = []
    update = None
    first_index = controller.decision_count
    for index in range(first_index, first_index + 4):
        action, result = _drive_synthetic_transition(
            index, controller, selector, collector
        )
        actions.append(action)
        if result.updated:
            update = result
    if update is None or not update.updated:
        raise LLAPIContractError(f"{TASK_NAME} bounded continuation missed its update.")
    if update.optimizer_update_count != 1_001 or update.target_synced:
        raise LLAPIContractError(f"{TASK_NAME} bounded continuation crossed a sync.")
    if len(recorder.samples) != 1:
        raise LLAPIContractError(f"{TASK_NAME} bounded continuation sample count drifted.")
    result = {
        "decision_count": int(update.decision_count),
        "optimizer_update_count": int(update.optimizer_update_count),
        "replay_size": int(update.replay_size),
        "target_sync_count": int(update.target_sync_count),
        "sampled_indices": recorder.samples[-1]["indices"],
        "loss": float(update.loss),
        "mean_absolute_td_error": float(update.mean_absolute_td_error),
        "online_after_sha256": network_sha256(controller.online_network),
        "target_after_sha256": network_sha256(controller.target_network),
        "continuation_actions": actions,
    }
    return result, recorder.samples[-1]


def _synthetic_post_boundary_selection(
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    sample = replay_sample_fingerprint(
        controller.replay.sample(controller.settings.batch_size)
    )
    masks = _masks()
    observation = _observation(0.25)
    action = selector.select(
        observation,
        masks,
        completed_transition_count=controller.decision_count,
    )
    return sample, {
        "completed_transition_count": controller.decision_count,
        "action": [int(value) for value in action],
        "action_masks": [[False, False, False], [False, False]],
        "legal": all(
            not bool(masks[branch][int(value)])
            for branch, value in enumerate(action)
        ),
    }


def _boundary_observation(
    checkpoint_path: Path,
    trace_path: Path,
    summary_path: Path,
    controller: BDQOptimizerController,
    collector: DirectReplayCollector,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    contract: Dict[str, Any],
    stage_name: str,
) -> None:
    trace = _read_json(trace_path)
    _validate_trace(trace, _read_json(RESULT_SCHEMA_PATH), contract, stage_name)
    boundary = boundary_summary(controller, selector, collector)
    _validate_checkpoint_boundary(boundary, trace, contract, stage_name)
    state_digest = checkpoint_state_sha256(controller, collector, selector)
    if not checkpoint_path.is_file():
        raise LLAPIContractError(f"{TASK_NAME} omitted its saved checkpoint.")

    next_update = None
    next_sample = None
    post_selection = None
    if stage_name == "pilot":
        next_update, next_sample = _drive_next_update(
            controller, selector, collector
        )
    else:
        next_sample, post_selection = _synthetic_post_boundary_selection(
            controller, selector
        )
    _write_json(
        {
            "boundary": boundary,
            "boundary_state_sha256": state_digest,
            "next_replay_sample": next_sample,
            "bounded_optimizer_result": next_update,
            "synthetic_post_boundary_selection": post_selection,
            "loaded_without_unity": False,
        },
        summary_path,
    )


def _run_live_worker(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
    result_schema: Dict[str, Any],
    stage_name: str,
) -> Dict[str, Any]:
    stage_contract = _stage_contract(contract, stage_name)
    checkpoint_path = worker_output / CHECKPOINT_FILE_NAME
    trace_path = worker_output / TRACE_FILE_NAME
    summary_path = worker_output / CHECKPOINT_SUMMARY_FILE_NAME

    def validate_prefix(
        controller: BDQOptimizerController,
        collector: DirectReplayCollector,
        selector: ScheduledEpsilonGreedyBDQActionSelector,
        transitions: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return _validate_prefix_boundary(
            controller, collector, selector, transitions, contract
        )

    def save_boundary(
        controller: BDQOptimizerController,
        collector: DirectReplayCollector,
        selector: ScheduledEpsilonGreedyBDQActionSelector,
    ) -> None:
        _boundary_observation(
            checkpoint_path,
            trace_path,
            summary_path,
            controller,
            collector,
            selector,
            contract,
            stage_name,
        )

    trace = execute_update_gate_worker(
        executable,
        worker_output,
        worker_index,
        contract,
        gate_contract=stage_contract,
        contract_path=CONTRACT_PATH,
        trace_file_name=TRACE_FILE_NAME,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        task_name=f"{TASK_NAME} {stage_name}",
        record_update_hashes=True,
        record_target_hashes=True,
        base_port=BASE_WORKER_PORT,
        timeout_wait=300,
        progress_interval=1_000,
        checkpoint_path=checkpoint_path,
        checkpoint_callback=save_boundary,
        trace_metadata={"stage": stage_name},
        boundary_callback=validate_prefix,
        prefix_boundary_transition_count=int(
            contract["continuation_prefix"]["transition_count"]
        ),
    )
    _validate_trace(trace, result_schema, contract, stage_name)
    if not checkpoint_path.is_file() or not summary_path.is_file():
        raise LLAPIContractError(f"{TASK_NAME} worker omitted checkpoint evidence.")
    print(f"trace={trace_path}")
    print(f"checkpoint={checkpoint_path}")
    print(f"summary={summary_path}")
    return trace


def _run_restorer(
    checkpoint_path: Path,
    summary_path: Path,
    contract: Dict[str, Any],
    stage_name: str,
) -> int:
    configure_torch(contract["determinism"], f"{TASK_NAME} restorer")
    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=BDQOptimizationSettings(),
        controller_seed=51001,
        exploration_seed=61001,
        schedule=_schedule(contract),
    )
    stage = contract["stages"][stage_name]
    boundary = loaded.verification
    expected_count = int(stage["final_clean_boundary"]["decision_count"])
    if boundary["decision_count"] != expected_count:
        raise LLAPIContractError(f"{TASK_NAME} restorer boundary count drifted.")
    if boundary["optimizer_update_count"] != int(
        stage["final_clean_boundary"]["optimizer_update_count"]
    ) or boundary["target_sync_count"] != int(
        stage["final_clean_boundary"]["target_sync_count"]
    ):
        raise LLAPIContractError(f"{TASK_NAME} restorer optimizer boundary drifted.")
    state_digest = checkpoint_state_sha256(
        loaded.controller, loaded.collector, loaded.selector
    )
    next_update = None
    post_selection = None
    if stage_name == "pilot":
        next_update, next_sample = _drive_next_update(
            loaded.controller, loaded.selector, loaded.collector
        )
    else:
        next_sample, post_selection = _synthetic_post_boundary_selection(
            loaded.controller, loaded.selector
        )
    _write_json(
        {
            "boundary": boundary,
            "boundary_state_sha256": state_digest,
            "next_replay_sample": next_sample,
            "bounded_optimizer_result": next_update,
            "synthetic_post_boundary_selection": post_selection,
            "loaded_without_unity": True,
        },
        summary_path,
    )
    print(f"summary={summary_path}")
    return 0


def _validate_pilot_result(path: Path, contract: Dict[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    result = _read_json(path)
    result_schema = _read_json(RESULT_SCHEMA_PATH)
    Draft202012Validator(result_schema).validate(result)
    if result["stage"] != "pilot" or result["contract_sha256"] != sha256_file(
        CONTRACT_PATH
    ):
        raise LLAPIContractError(
            "Synchronization requires a passing pilot result from this contract."
        )
    if not result["exact_trace_equality"] or not result[
        "checkpoint_differential"
    ]["same_checkpoint_bytes"]:
        raise LLAPIContractError("Synchronization pilot gate did not pass.")
    if result["canonical_trace_sha256"] != canonical_json_sha256(
        result["canonical_trace"]
    ):
        raise LLAPIContractError(
            "Synchronization pilot canonical trace hash does not match its trace."
        )
    _validate_stage_registration(contract, "pilot")
    _validate_trace(result["canonical_trace"], result_schema, contract, "pilot")


def _result_from_attempts(
    output_directory: Path,
    contract: Dict[str, Any],
    result_schema: Dict[str, Any],
    stage_name: str,
    traces: Sequence[Dict[str, Any]],
    trace_paths: Sequence[Path],
    summaries: Sequence[Dict[str, Any]],
    restored_summaries: Sequence[Dict[str, Any]],
) -> Path:
    if len(traces) != 2 or len(trace_paths) != 2 or len(summaries) != 2:
        raise LLAPIContractError(f"{TASK_NAME} requires two independent attempts.")
    if traces[0] != traces[1] or trace_paths[0].read_bytes() != trace_paths[1].read_bytes():
        raise LLAPIContractError(f"{TASK_NAME} fresh traces are not byte-identical.")
    if summaries[0] != summaries[1]:
        raise LLAPIContractError(f"{TASK_NAME} checkpoint summaries differ.")
    if any(summary["loaded_without_unity"] for summary in summaries):
        raise LLAPIContractError(f"{TASK_NAME} live summaries were not Unity-backed.")
    if any(not summary["loaded_without_unity"] for summary in restored_summaries):
        raise LLAPIContractError(f"{TASK_NAME} restore summaries used Unity.")
    checkpoints = [trace_paths[index].parent / CHECKPOINT_FILE_NAME for index in range(2)]
    checkpoint_hashes = [sha256_file(path) for path in checkpoints]
    checkpoint_bytes = [path.stat().st_size for path in checkpoints]
    if checkpoint_hashes[0] != checkpoint_hashes[1] or checkpoint_bytes[0] != checkpoint_bytes[1]:
        raise LLAPIContractError(f"{TASK_NAME} checkpoint bytes differ across attempts.")
    if len(restored_summaries) != 2 or restored_summaries[0] != restored_summaries[1]:
        raise LLAPIContractError(f"{TASK_NAME} restored summaries differ.")
    reference = summaries[0]
    restored = restored_summaries[0]
    if reference["boundary"] != restored["boundary"]:
        raise LLAPIContractError(f"{TASK_NAME} restored boundary differs.")
    if reference["boundary_state_sha256"] != restored["boundary_state_sha256"]:
        raise LLAPIContractError(f"{TASK_NAME} restored checkpoint state differs.")
    if reference["next_replay_sample"] != restored["next_replay_sample"]:
        raise LLAPIContractError(f"{TASK_NAME} restored replay sample differs.")
    if reference["bounded_optimizer_result"] != restored["bounded_optimizer_result"]:
        raise LLAPIContractError(f"{TASK_NAME} restored bounded update differs.")
    if reference["synthetic_post_boundary_selection"] != restored[
        "synthetic_post_boundary_selection"
    ]:
        raise LLAPIContractError(f"{TASK_NAME} restored synthetic selection differs.")
    attempts = [
        {
            "attempt_index": index + 1,
            "player_copy": f"run-{index + 1}",
            "trace_sha256": sha256_file(trace_paths[index]),
            "trace_bytes": trace_paths[index].stat().st_size,
            "checkpoint_sha256": checkpoint_hashes[index],
            "checkpoint_bytes": checkpoint_bytes[index],
            "checkpoint_state_sha256": summaries[index]["boundary_state_sha256"],
        }
        for index in range(2)
    ]
    post_selection = reference["synthetic_post_boundary_selection"]
    if stage_name == "pilot":
        post_selection_record = {
            "policy": "stop_before_live_action; synthetic_selection_only",
            "live_action_selected": False,
            "synthetic_selection_required": False,
            "synthetic_selection": None,
        }
    else:
        if post_selection is None or not post_selection["legal"]:
            raise LLAPIContractError(f"{TASK_NAME} omitted legal post-sync selection.")
        post_selection_record = {
            "policy": "stop_before_live_action; synthetic_selection_only",
            "live_action_selected": False,
            "synthetic_selection_required": True,
            "synthetic_selection": post_selection,
        }
    _validate_post_boundary_selection(stage_name, post_selection_record)
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "stage": stage_name,
        "fresh_process_count": 2,
        "exact_trace_equality": True,
        "canonical_trace_sha256": canonical_json_sha256(traces[0]),
        "canonical_trace": traces[0],
        "attempts": attempts,
        "checkpoint_differential": {
            "same_checkpoint_bytes": True,
            "same_checkpoint_state": True,
            "checkpoint_sha256": checkpoint_hashes[0],
            "checkpoint_state_sha256": summaries[0]["boundary_state_sha256"],
        },
        "restoration_differential": {
            "same_boundary_state": True,
            "same_next_replay_sample": True,
            "same_bounded_result": True,
            "loaded_without_unity": True,
            "reference": reference,
            "restored": restored,
        },
        "post_boundary_selection": post_selection_record,
    }
    Draft202012Validator(result_schema).validate(result)
    result_path = output_directory / RESULT_FILE_NAME
    _write_json(result, result_path)
    return result_path


def _validate_post_boundary_selection(
    stage_name: str,
    selection: Dict[str, Any],
) -> None:
    if selection.get("policy") != "stop_before_live_action; synthetic_selection_only":
        raise LLAPIContractError(f"{TASK_NAME} post-boundary policy drifted.")
    if selection.get("live_action_selected") is not False:
        raise LLAPIContractError(
            f"{TASK_NAME} discarded a post-boundary live action."
        )
    if stage_name == "pilot":
        if selection.get("synthetic_selection_required") is not False:
            raise LLAPIContractError(
                f"{TASK_NAME} pilot post-boundary selection policy drifted."
            )
        if selection.get("synthetic_selection") is not None:
            raise LLAPIContractError(
                f"{TASK_NAME} pilot emitted an unexpected synthetic selection."
            )
        return
    if stage_name != "synchronization":
        raise ValueError(f"Unknown R3R stage: {stage_name}.")
    synthetic_selection = selection.get("synthetic_selection")
    if (
        selection.get("synthetic_selection_required") is not True
        or not isinstance(synthetic_selection, dict)
        or synthetic_selection.get("legal") is not True
    ):
        raise LLAPIContractError(
            f"{TASK_NAME} omitted legal post-sync selection."
        )


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.mode == "restorer":
        if (
            arguments.env is not None
            or arguments.output is not None
            or arguments.worker_output is not None
            or arguments.worker_index is not None
            or arguments.pilot_result is not None
            or arguments.checkpoint is None
            or arguments.summary is None
        ):
            raise ValueError(
                "Restorer mode requires only --mode, --stage, --checkpoint, and --summary."
            )
        return "restorer"
    if arguments.mode is not None:
        raise ValueError("Unknown R3R worker mode.")
    if arguments.worker_output is not None:
        if (
            arguments.env is None
            or arguments.output is not None
            or arguments.checkpoint is not None
            or arguments.summary is not None
            or arguments.worker_index is None
        ):
            raise ValueError(
                "Worker mode requires --env, --stage, --worker-output, and "
                "--worker-index, plus --pilot-result for synchronization."
            )
        if arguments.stage == "synchronization" and arguments.pilot_result is None:
            raise ValueError(
                "Synchronization worker mode requires --pilot-result."
            )
        if arguments.stage == "pilot" and arguments.pilot_result is not None:
            raise ValueError("Pilot worker mode does not accept --pilot-result.")
        return "worker"
    if (
        arguments.env is None
        or arguments.output is None
        or arguments.worker_index is not None
        or arguments.checkpoint is not None
        or arguments.summary is not None
    ):
        raise ValueError("Parent mode requires --env, --stage, and --output.")
    if arguments.stage == "synchronization" and arguments.pilot_result is None:
        raise ValueError("Synchronization parent mode requires --pilot-result.")
    if arguments.stage == "pilot" and arguments.pilot_result is not None:
        raise ValueError("Pilot parent mode does not accept --pilot-result.")
    return "parent"


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded R3R BDQ continuation pilot or first target-sync gate."
        )
    )
    parser.add_argument("--env", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--stage", choices=["pilot", "synchronization"], default="pilot"
    )
    parser.add_argument("--pilot-result", type=Path)
    parser.add_argument("--checkpoint", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--summary", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--mode", choices=["restorer"], help=argparse.SUPPRESS
    )
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    contract = _read_json(CONTRACT_PATH)
    result_schema = validate_contract(contract)
    _validate_stage_registration(contract, arguments.stage)

    if mode == "restorer":
        assert arguments.checkpoint is not None
        assert arguments.summary is not None
        return _run_restorer(
            arguments.checkpoint.resolve(),
            arguments.summary.resolve(),
            contract,
            arguments.stage,
        )

    if mode == "worker":
        assert arguments.env is not None
        assert arguments.worker_output is not None
        assert arguments.worker_index is not None
        executable = arguments.env.resolve()
        if not executable.is_file():
            raise FileNotFoundError(executable)
        if arguments.stage == "synchronization":
            assert arguments.pilot_result is not None
            _validate_pilot_result(arguments.pilot_result.resolve(), contract)
        _validate_worker_player_copy(
            executable,
            arguments.worker_output,
            arguments.worker_index,
            contract["player_execution"]["required_siblings"],
        )
        _run_live_worker(
            executable,
            arguments.worker_output.resolve(),
            arguments.worker_index,
            contract,
            result_schema,
            arguments.stage,
        )
        return 0

    assert arguments.env is not None
    assert arguments.output is not None
    if arguments.stage == "synchronization":
        assert arguments.pilot_result is not None
        _validate_pilot_result(arguments.pilot_result.resolve(), contract)
    source_executable = arguments.env.resolve()
    if not source_executable.is_file():
        raise FileNotFoundError(source_executable)
    output_directory = arguments.output.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(f"{TASK_NAME} output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)

    traces: list[Dict[str, Any]] = []
    trace_paths: list[Path] = []
    summaries: list[Dict[str, Any]] = []
    for index in range(2):
        copy_root = output_directory / "player-copies" / f"run-{index + 1}"
        copied_executable = copy_complete_player(
            source_executable,
            copy_root,
            required_siblings=contract["player_execution"]["required_siblings"],
        )
        worker_arguments = [f"--stage={arguments.stage}"]
        if arguments.stage == "synchronization":
            assert arguments.pilot_result is not None
            worker_arguments.append(
                f"--pilot-result={arguments.pilot_result.resolve()}"
            )
        trace, trace_path = run_fresh_worker_process(
            runner_path=Path(__file__),
            executable=copied_executable,
            output_directory=output_directory,
            worker_index=index,
            contract=contract,
            trace_file_name=TRACE_FILE_NAME,
            task_name=f"{TASK_NAME} {arguments.stage}",
            announce=True,
            repo_root=HERE.parents[1],
            timeout_seconds=(
                SYNCHRONIZATION_WORKER_TIMEOUT_SECONDS
                if arguments.stage == "synchronization"
                else PILOT_WORKER_TIMEOUT_SECONDS
            ),
            worker_arguments=worker_arguments,
        )
        _validate_trace(trace, result_schema, contract, arguments.stage)
        traces.append(trace)
        trace_paths.append(trace_path)
        summaries.append(_read_json(trace_path.parent / CHECKPOINT_SUMMARY_FILE_NAME))

    restored_summaries: list[Dict[str, Any]] = []
    for index, trace_path in enumerate(trace_paths):
        checkpoint_path = trace_path.parent / CHECKPOINT_FILE_NAME
        summary_path = output_directory / f"restored-{index + 1}.json"
        run_fresh_python_process(
            runner_path=Path(__file__),
            arguments=[
                "--mode=restorer",
                f"--stage={arguments.stage}",
                f"--checkpoint={checkpoint_path}",
                f"--summary={summary_path}",
            ],
            output_directory=output_directory,
            log_name=f"restorer-{index + 1}.log",
            task_name=f"{TASK_NAME} {arguments.stage} restorer",
            contract=contract,
            repo_root=HERE.parents[1],
            timeout_seconds=(
                SYNCHRONIZATION_WORKER_TIMEOUT_SECONDS
                if arguments.stage == "synchronization"
                else PILOT_WORKER_TIMEOUT_SECONDS
            ),
        )
        restored_summaries.append(_read_json(summary_path))

    result_path = _result_from_attempts(
        output_directory,
        contract,
        result_schema,
        arguments.stage,
        traces,
        trace_paths,
        summaries,
        restored_summaries,
    )
    print(f"result={result_path}")
    print(f"stage={arguments.stage}")
    print("fresh_processes=2")
    print(f"transitions={traces[0]['cutoff']['transition_limit']}")
    print(f"optimizer_updates={traces[0]['optimization']['optimizer_update_count']}")
    print(f"target_synchronizations={traces[0]['optimization']['target_sync_count']}")
    print("exact_trace_equality=pass")
    print("clean_boundary=pass")
    print("checkpoint_restore=pass")
    if arguments.stage == "synchronization":
        print("synthetic_post_sync_selection=pass")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LLAPIContractError,
        ValueError,
        FileNotFoundError,
        FileExistsError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"error={error}", file=sys.stderr)
        raise SystemExit(2) from error
