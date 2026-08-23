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

import numpy as np
import torch
from jsonschema import Draft202012Validator
from mlagents_envs.base_env import ActionTuple
from mlagents_envs.environment import UnityEnvironment


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    BASIC_BEHAVIOR_NAME,
    BDQOptimizationSettings,
    BDQOptimizerController,
    BasicTruncationMaskSideChannel,
    DirectReplayCollector,
    LLAPIContractError,
    ReplayTransition,
    SeededEpsilonGreedyBDQActionSelector,
    joint_indices_from_branches,
    network_sha256,
    observation_sha256,
    read_action_masks,
    validate_basic_behavior_spec,
    validate_observation,
)


ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
CONTRACT_PATH = HERE / "bdq-epsilon-collection-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-epsilon-collection-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-epsilon-collection-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
TRACE_FILE_NAME = "r3e-epsilon-collection-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-epsilon-collection-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-epsilon-collection-smoke-result.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _masks_to_json(masks: Sequence[np.ndarray]) -> list[list[bool]]:
    return [[bool(value) for value in branch] for branch in masks]


def _transition_to_json(
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
        "action_masks": _masks_to_json(transition.action_masks),
        "next_action_masks": _masks_to_json(transition.next_action_masks),
        "terminated": transition.terminated,
        "truncated": transition.truncated,
    }


def _record_transition(
    collector: DirectReplayCollector,
    agent_id: int,
    reward: float,
    next_observation: np.ndarray,
    next_action_masks: Sequence[np.ndarray],
    *,
    terminated: bool,
    truncated: bool,
    transitions: list[Dict[str, Any]],
    episode_index: int,
    episode_decision_index: int,
) -> None:
    transition, result = collector.complete(
        agent_id,
        reward,
        next_observation,
        next_action_masks,
        terminated=terminated,
        truncated=truncated,
    )
    if result.updated or result.target_synced:
        raise LLAPIContractError(
            "R3E opened a learning gate before replay warmup."
        )
    transitions.append(
        _transition_to_json(
            transition,
            len(transitions),
            episode_index,
            episode_decision_index,
        )
    )


def _episode_record(
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


def _action_tuple_counts(transitions: Sequence[Dict[str, Any]]) -> list[int]:
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


def execute_worker(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    worker_output.mkdir(parents=True, exist_ok=False)
    collection = contract["collection"]
    transition_limit = int(collection["transition_limit"])
    settings = BDQOptimizationSettings()
    if transition_limit >= settings.replay_warmup_decisions:
        raise LLAPIContractError("R3E must remain strictly below replay warmup.")
    if settings.replay_warmup_decisions != int(
        collection["replay_warmup_decisions"]
    ):
        raise LLAPIContractError("Optimizer warmup differs from the R3E contract.")

    side_channel = BasicTruncationMaskSideChannel()
    policy_seed = int(collection["policy_seed"])
    controller = BDQOptimizerController(policy_seed, settings)
    collector = DirectReplayCollector(controller)
    selector = SeededEpsilonGreedyBDQActionSelector(
        controller.online_network,
        epsilon=float(collection["epsilon"]),
        seed=int(collection["exploration_seed"]),
    )
    online_before = network_sha256(controller.online_network)
    target_before = network_sha256(controller.target_network)
    transitions: list[Dict[str, Any]] = []
    episodes: list[Dict[str, Any]] = []
    truncation_events: list[Dict[str, Any]] = []
    active_episode_index = 0
    episode_decision_index = 0
    episode_start_index = 0
    episode_return = 0.0
    ended_on_unity_boundary = False
    maximum_iterations = transition_limit + transition_limit // 300 + 20
    environment: UnityEnvironment | None = None

    try:
        environment = UnityEnvironment(
            file_name=str(executable),
            worker_id=worker_index,
            base_port=5045,
            seed=int(collection["scenario_seed"]),
            side_channels=[side_channel],
            no_graphics=False,
            timeout_wait=120,
            log_folder=str(worker_output / "player-log"),
        )
        environment.reset()
        behavior_names = list(environment.behavior_specs)
        expected_behavior_id = f"{BASIC_BEHAVIOR_NAME}?team=0"
        if behavior_names != [expected_behavior_id]:
            raise LLAPIContractError(
                f"Expected behavior {BASIC_BEHAVIOR_NAME}, got {behavior_names}."
            )
        behavior_id = behavior_names[0]
        behavior_spec = environment.behavior_specs[behavior_id]
        validate_basic_behavior_spec(behavior_spec)

        for _ in range(maximum_iterations):
            decision_steps, terminal_steps = environment.get_steps(behavior_id)
            if len(decision_steps) > 1 or len(terminal_steps) > 1:
                raise LLAPIContractError("R3E permits one Basic agent only.")
            if len(decision_steps) == 1 and len(terminal_steps) == 1:
                if int(decision_steps.agent_id[0]) != int(terminal_steps.agent_id[0]):
                    raise LLAPIContractError(
                        "A terminal/new-decision handoff must belong to one agent."
                    )

            for terminal_row, raw_agent_id in enumerate(terminal_steps.agent_id):
                agent_id = int(raw_agent_id)
                next_observation = validate_observation(
                    terminal_steps.obs[0][terminal_row],
                    "terminal next_observation",
                )
                reward = float(terminal_steps.reward[terminal_row])
                interrupted = bool(terminal_steps.interrupted[terminal_row])
                completed_decision_count = episode_decision_index + 1
                if interrupted:
                    event = side_channel.take(
                        active_episode_index,
                        completed_decision_count,
                    )
                    next_action_masks = event.action_masks
                    truncation_events.append(
                        {
                            "episode_index": event.episode_index,
                            "decision_count": event.decision_count,
                            "reason": event.reason,
                            "position_slot": event.position_slot,
                            "next_action_masks": _masks_to_json(event.action_masks),
                        }
                    )
                else:
                    next_action_masks = tuple(
                        np.zeros(branch_size, dtype=np.bool_)
                        for branch_size in (3, 2)
                    )
                _record_transition(
                    collector,
                    agent_id,
                    reward,
                    next_observation,
                    next_action_masks,
                    terminated=not interrupted,
                    truncated=interrupted,
                    transitions=transitions,
                    episode_index=active_episode_index,
                    episode_decision_index=episode_decision_index,
                )
                episode_return += reward
                episode_decision_index += 1
                episodes.append(
                    _episode_record(
                        episode_index=active_episode_index,
                        transition_start_index=episode_start_index,
                        transition_count=episode_decision_index,
                        episode_return=episode_return,
                        end_kind="truncated" if interrupted else "terminal",
                    )
                )
                active_episode_index += 1
                episode_decision_index = 0
                episode_start_index = len(transitions)
                episode_return = 0.0
                if len(transitions) == transition_limit:
                    ended_on_unity_boundary = True

            if len(transitions) > transition_limit:
                raise LLAPIContractError("R3E exceeded its exact transition limit.")
            if len(transitions) == transition_limit:
                break

            actions = np.zeros((len(decision_steps), 2), dtype=np.int32)
            reached_limit = False
            for decision_row, raw_agent_id in enumerate(decision_steps.agent_id):
                agent_id = int(raw_agent_id)
                observation = validate_observation(
                    decision_steps.obs[0][decision_row],
                    "decision observation",
                )
                action_masks = read_action_masks(decision_steps, decision_row)
                if agent_id in collector.pending_agent_ids:
                    _record_transition(
                        collector,
                        agent_id,
                        float(decision_steps.reward[decision_row]),
                        observation,
                        action_masks,
                        terminated=False,
                        truncated=False,
                        transitions=transitions,
                        episode_index=active_episode_index,
                        episode_decision_index=episode_decision_index,
                    )
                    episode_return += float(decision_steps.reward[decision_row])
                    episode_decision_index += 1
                    if len(transitions) == transition_limit:
                        reached_limit = True
                        break
                action = selector.select(observation, action_masks)
                collector.begin(agent_id, observation, action, action_masks)
                actions[decision_row] = action

            if len(transitions) > transition_limit:
                raise LLAPIContractError("R3E exceeded its exact transition limit.")
            if reached_limit:
                episodes.append(
                    _episode_record(
                        episode_index=active_episode_index,
                        transition_start_index=episode_start_index,
                        transition_count=episode_decision_index,
                        episode_return=episode_return,
                        end_kind="collection_cutoff",
                    )
                )
                break

            if len(decision_steps) > 0:
                environment.set_actions(
                    behavior_id,
                    ActionTuple(discrete=actions),
                )
            environment.step()
        else:
            raise LLAPIContractError("R3E collection exceeded its iteration bound.")

        if len(transitions) != transition_limit:
            raise LLAPIContractError(
                f"R3E collected {len(transitions)} transitions, "
                f"expected {transition_limit}."
            )
        if collector.pending_agent_ids:
            raise LLAPIContractError(
                f"Pending decisions remain at cutoff: {collector.pending_agent_ids}."
            )
        side_channel.assert_empty()
        completed_episode_count = sum(
            1 for episode in episodes if episode["unity_episode_ended"]
        )
        if completed_episode_count < int(collection["minimum_completed_episodes"]):
            raise LLAPIContractError("R3E did not collect across an episode reset.")

        online_after = network_sha256(controller.online_network)
        target_after = network_sha256(controller.target_network)
        if controller.optimizer_update_count != 0 or controller.target_sync_count != 0:
            raise LLAPIContractError("R3E performed a learning operation.")
        if online_before != online_after or target_before != target_after:
            raise LLAPIContractError("R3E changed network weights.")
        action_tuple_counts = _action_tuple_counts(transitions)
        unique_action_tuple_count = sum(count > 0 for count in action_tuple_counts)
        if unique_action_tuple_count < int(collection["minimum_unique_action_tuples"]):
            raise LLAPIContractError("R3E did not collect varied action tuples.")

        trace = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "behavior": {
                "name": BASIC_BEHAVIOR_NAME,
                "observation_shape": [84, 84, 4],
                "wire_layout": "HWC",
                "dtype": "float32",
                "discrete_branches": [3, 2],
                "privileged_observation_count": 0,
            },
            "scenario_seed": int(collection["scenario_seed"]),
            "policy_seed": policy_seed,
            "selector": {
                "name": collection["selector"],
                "epsilon": selector.epsilon,
                "epsilon_decay_enabled": collection["epsilon_decay_enabled"],
                "exploration_seed": selector.seed,
                "exploration_unit": collection["exploration_unit"],
                "random_generator": collection["random_generator"],
                "selection_count": sum(action_tuple_counts),
                "action_tuple_counts": action_tuple_counts,
                "unique_action_tuple_count": unique_action_tuple_count,
            },
            "episodes": episodes,
            "completed_episode_count": completed_episode_count,
            "episode_reset_count": completed_episode_count,
            "truncation_events": truncation_events,
            "transitions": transitions,
            "replay": {
                "decision_count": controller.decision_count,
                "size": len(controller.replay),
                "warmup_decisions": settings.replay_warmup_decisions,
                "below_warmup": controller.decision_count
                < settings.replay_warmup_decisions,
            },
            "cutoff": {
                "transition_limit": transition_limit,
                "pending_agent_ids": list(collector.pending_agent_ids),
                "pending_decision_count": len(collector.pending_agent_ids),
                "active_episode_index": active_episode_index,
                "ended_on_unity_boundary": ended_on_unity_boundary,
            },
            "learning_guard": {
                "optimizer_update_count": controller.optimizer_update_count,
                "target_sync_count": controller.target_sync_count,
                "online_before_sha256": online_before,
                "online_after_sha256": online_after,
                "target_before_sha256": target_before,
                "target_after_sha256": target_after,
                "online_weights_unchanged": online_before == online_after,
                "target_weights_unchanged": target_before == target_after,
            },
        }
        trace_path = worker_output / TRACE_FILE_NAME
        trace_path.write_text(
            json.dumps(trace, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return trace
    finally:
        if environment is not None:
            environment.close()


def validate_trace(trace: Dict[str, Any], result_schema: Dict[str, Any]) -> None:
    trace_schema = {
        **result_schema["$defs"]["trace"],
        "$defs": result_schema["$defs"],
    }
    Draft202012Validator(trace_schema).validate(trace)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    collection = contract["collection"]
    if trace["contract_sha256"] != sha256_file(CONTRACT_PATH):
        raise LLAPIContractError("Trace contract hash differs from R3E.")
    transitions = trace["transitions"]
    episodes = trace["episodes"]
    transition_limit = int(collection["transition_limit"])
    if len(transitions) != transition_limit:
        raise LLAPIContractError(
            "R3E trace does not contain exactly 1,000 transitions."
        )
    if [item["index"] for item in transitions] != list(range(transition_limit)):
        raise LLAPIContractError("R3E transition indices are not contiguous.")
    if [item["episode_index"] for item in episodes] != list(range(len(episodes))):
        raise LLAPIContractError("R3E episode indices are not contiguous.")
    if trace["replay"] != {
        "decision_count": transition_limit,
        "size": transition_limit,
        "warmup_decisions": int(collection["replay_warmup_decisions"]),
        "below_warmup": True,
    }:
        raise LLAPIContractError("R3E replay counters differ from its contract.")
    if trace["cutoff"]["pending_agent_ids"] or trace["cutoff"][
        "pending_decision_count"
    ] != 0:
        raise LLAPIContractError("R3E cutoff retained a pending decision.")

    next_start = 0
    for episode in episodes:
        if episode["transition_start_index"] != next_start:
            raise LLAPIContractError("R3E episode spans are not contiguous.")
        stop = next_start + episode["transition_count"]
        episode_transitions = transitions[next_start:stop]
        if len(episode_transitions) != episode["transition_count"]:
            raise LLAPIContractError("R3E episode transition span is incomplete.")
        if any(
            item["episode_index"] != episode["episode_index"]
            for item in episode_transitions
        ):
            raise LLAPIContractError("R3E assigned a transition to the wrong episode.")
        if [item["episode_decision_index"] for item in episode_transitions] != list(
            range(len(episode_transitions))
        ):
            raise LLAPIContractError("R3E episode decision indices are not contiguous.")
        if not math.isclose(
            sum(item["reward"] for item in episode_transitions),
            episode["return"],
            rel_tol=0.0,
            abs_tol=1e-7,
        ):
            raise LLAPIContractError("R3E episode return differs from its rewards.")
        for current, following in zip(episode_transitions, episode_transitions[1:]):
            if current["next_observation_sha256"] != following[
                "observation_sha256"
            ]:
                raise LLAPIContractError("R3E consecutive observations do not join.")
            if current["next_action_masks"] != following["action_masks"]:
                raise LLAPIContractError("R3E consecutive action masks do not join.")
            if current["terminated"] or current["truncated"]:
                raise LLAPIContractError("R3E has a nonfinal episode end flag.")
        final = episode_transitions[-1]
        if episode["end_kind"] == "terminal":
            if not final["terminated"] or final["truncated"]:
                raise LLAPIContractError("R3E terminal episode flags are incorrect.")
            if final["next_action_masks"] != [
                [False, False, False],
                [False, False],
            ]:
                raise LLAPIContractError("R3E terminal sentinel mask is incorrect.")
        elif episode["end_kind"] == "truncated":
            if final["terminated"] or not final["truncated"]:
                raise LLAPIContractError("R3E truncation flags are incorrect.")
        elif final["terminated"] or final["truncated"]:
            raise LLAPIContractError(
                "R3E collection cutoff was marked as an episode end."
            )
        next_start = stop
    if next_start != transition_limit:
        raise LLAPIContractError("R3E episode spans do not cover every transition.")

    for item in transitions:
        if item["terminated"] and item["truncated"]:
            raise LLAPIContractError("R3E transition has conflicting end flags.")
        for branch, action in enumerate(item["action"]):
            if item["action_masks"][branch][action]:
                raise LLAPIContractError("R3E selected an unavailable action.")

    completed_episode_count = sum(
        1 for episode in episodes if episode["unity_episode_ended"]
    )
    if completed_episode_count != trace["completed_episode_count"]:
        raise LLAPIContractError("R3E completed-episode count is inconsistent.")
    if trace["episode_reset_count"] != completed_episode_count:
        raise LLAPIContractError("R3E reset count is inconsistent.")
    if completed_episode_count < int(collection["minimum_completed_episodes"]):
        raise LLAPIContractError("R3E did not cross an episode reset.")
    if episodes[-1]["end_kind"] == "collection_cutoff":
        if trace["cutoff"]["ended_on_unity_boundary"]:
            raise LLAPIContractError("R3E cutoff boundary record is inconsistent.")
    elif not trace["cutoff"]["ended_on_unity_boundary"]:
        raise LLAPIContractError("R3E cutoff omitted its Unity episode boundary.")

    truncations = {
        episode["episode_index"]: episode
        for episode in episodes
        if episode["end_kind"] == "truncated"
    }
    if len(trace["truncation_events"]) != len(truncations):
        raise LLAPIContractError("R3E truncation events do not match episode ends.")
    for event in trace["truncation_events"]:
        episode = truncations.get(event["episode_index"])
        if episode is None or episode["transition_count"] != event["decision_count"]:
            raise LLAPIContractError("R3E truncation event is not correlated.")
        final_index = episode["transition_start_index"] + episode[
            "transition_count"
        ] - 1
        if transitions[final_index]["next_action_masks"] != event[
            "next_action_masks"
        ]:
            raise LLAPIContractError("R3E truncation replay mask differs from Unity.")

    counts = _action_tuple_counts(transitions)
    selector = trace["selector"]
    if selector["selection_count"] != transition_limit:
        raise LLAPIContractError("R3E action count differs from transition count.")
    if selector["action_tuple_counts"] != counts:
        raise LLAPIContractError("R3E action histogram is inconsistent.")
    unique_count = sum(count > 0 for count in counts)
    if selector["unique_action_tuple_count"] != unique_count:
        raise LLAPIContractError("R3E unique-action count is inconsistent.")
    if unique_count < int(collection["minimum_unique_action_tuples"]):
        raise LLAPIContractError("R3E action collection is not varied.")

    guard = trace["learning_guard"]
    if guard["optimizer_update_count"] != 0 or guard["target_sync_count"] != 0:
        raise LLAPIContractError("R3E trace contains a learning operation.")
    if guard["online_before_sha256"] != guard["online_after_sha256"]:
        raise LLAPIContractError("R3E online weights changed.")
    if guard["target_before_sha256"] != guard["target_after_sha256"]:
        raise LLAPIContractError("R3E target weights changed.")


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_llapi_contract"]
    if sha256_file(REPO_ROOT / binding["path"]) != binding["sha256"]:
        raise LLAPIContractError(f"Contract binding drifted: {binding['path']}.")
    runtime = contract["runtime"]
    if runtime != {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }:
        raise LLAPIContractError("The active runtime differs from R3E.")
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError("The R3E package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError("The R3E package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point returned.")
    settings = BDQOptimizationSettings()
    collection = contract["collection"]
    if settings.replay_warmup_decisions != collection["replay_warmup_decisions"]:
        raise LLAPIContractError("R3E warmup differs from optimizer defaults.")
    if collection["transition_limit"] >= settings.replay_warmup_decisions:
        raise LLAPIContractError("R3E is not below replay warmup.")
    return result_schema


def run_fresh_worker(
    executable: Path,
    output_directory: Path,
    worker_index: int,
) -> tuple[Dict[str, Any], Path]:
    worker_output = output_directory / f"run-{worker_index + 1}"
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
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=process_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=600,
        check=False,
    )
    log_path = output_directory / f"worker-{worker_index + 1}.log"
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Fresh R3E worker {worker_index + 1} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )
    trace_path = worker_output / TRACE_FILE_NAME
    if not trace_path.is_file():
        raise RuntimeError(f"Fresh R3E worker omitted {trace_path}.")
    return json.loads(trace_path.read_text(encoding="utf-8")), trace_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run seeded epsilon-greedy Basic collection twice."
    )
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    executable = arguments.env.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result_schema = validate_contract(contract)

    if arguments.worker_output is not None:
        if arguments.worker_index is None or arguments.output is not None:
            raise ValueError("Worker mode requires only worker output and index.")
        trace = execute_worker(
            executable,
            arguments.worker_output.resolve(),
            arguments.worker_index,
            contract,
        )
        validate_trace(trace, result_schema)
        print(f"trace={arguments.worker_output.resolve() / TRACE_FILE_NAME}")
        return 0

    if arguments.output is None or arguments.worker_index is not None:
        raise ValueError("Parent mode requires --output and no worker index.")
    output_directory = arguments.output.resolve()
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")
    if output_directory.exists():
        raise FileExistsError(f"R3E output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)

    first, first_path = run_fresh_worker(executable, output_directory, 0)
    second, second_path = run_fresh_worker(executable, output_directory, 1)
    validate_trace(first, result_schema)
    validate_trace(second, result_schema)
    if first != second or first_path.read_bytes() != second_path.read_bytes():
        raise LLAPIContractError(
            f"Fresh R3E traces differ: {first_path} versus {second_path}."
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
    print(f"result={result_path}")
    print("fresh_processes=2")
    print("transitions=1000")
    print(f"completed_episodes={first['completed_episode_count']}")
    print(f"episode_resets={first['episode_reset_count']}")
    print(f"unique_action_tuples={first['selector']['unique_action_tuple_count']}")
    print("pending_decisions=0")
    print("optimizer_updates=0")
    print("target_synchronizations=0")
    print("exact_trace_equality=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
