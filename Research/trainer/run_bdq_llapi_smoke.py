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
    GreedyBDQActionSelector,
    LLAPIContractError,
    ReplayTransition,
    network_sha256,
    observation_sha256,
    read_action_masks,
    validate_basic_behavior_spec,
    validate_observation,
)


ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
CONTRACT_PATH = HERE / "bdq-llapi-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-llapi-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "bdq-llapi-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
TRACE_FILE_NAME = "r3d-llapi-trace.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-llapi-trace.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-llapi-smoke-result.v1"


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
            "The bounded LLAPI collection smoke opened a learning gate."
        )
    transitions.append(
        _transition_to_json(
            transition,
            len(transitions),
            episode_index,
            episode_decision_index,
        )
    )


def execute_worker(
    executable: Path,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    worker_output.mkdir(parents=True, exist_ok=False)
    side_channel = BasicTruncationMaskSideChannel()
    policy_seed = int(contract["collection"]["policy_seed"])
    controller = BDQOptimizerController(policy_seed, BDQOptimizationSettings())
    collector = DirectReplayCollector(controller)
    greedy_selector = GreedyBDQActionSelector(controller.online_network)
    online_before = network_sha256(controller.online_network)
    target_before = network_sha256(controller.target_network)
    transitions: list[Dict[str, Any]] = []
    episodes: list[Dict[str, Any]] = []
    truncation_events: list[Dict[str, Any]] = []
    active_episode_index = 0
    episode_decision_index = 0
    episode_start_index = 0
    episode_return = 0.0
    maximum_iterations = 2 * (
        int(contract["truncation_mask_channel"]["decision_count"]) + 5
    )
    environment: UnityEnvironment | None = None

    try:
        environment = UnityEnvironment(
            file_name=str(executable),
            worker_id=worker_index,
            base_port=5035,
            seed=int(contract["collection"]["scenario_seed"]),
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
            decision_steps, terminal_steps = environment.get_steps(
                behavior_id
            )
            if len(decision_steps) > 1 or len(terminal_steps) > 1:
                raise LLAPIContractError(
                    "The Basic LLAPI smoke permits one agent only."
                )
            if len(decision_steps) == 1 and len(terminal_steps) == 1:
                if int(decision_steps.agent_id[0]) != int(terminal_steps.agent_id[0]):
                    raise LLAPIContractError(
                        "A terminal/new-decision handoff must belong to the same agent."
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

                expected = contract["collection"]["episodes"][active_episode_index]
                expected_interrupted = expected["expected_end"] == "truncated"
                if interrupted != expected_interrupted:
                    raise LLAPIContractError(
                        f"Episode {active_episode_index} ended as "
                        f"{'truncated' if interrupted else 'terminal'}, expected "
                        f"{expected['expected_end']}."
                    )
                if interrupted and episode_decision_index != expected[
                    "expected_decision_count"
                ]:
                    raise LLAPIContractError(
                        "Decision-limit episode ended at the wrong decision count."
                    )
                if (
                    not interrupted
                    and episode_decision_index > expected["expected_max_decision_count"]
                ):
                    raise LLAPIContractError(
                        "Greedy terminal episode exceeded its decision bound."
                    )

                episodes.append(
                    {
                        "episode_index": active_episode_index,
                        "selector": expected["selector"],
                        "transition_start_index": episode_start_index,
                        "transition_count": episode_decision_index,
                        "return": float(episode_return),
                        "end_kind": "truncated" if interrupted else "terminal",
                        "reason": "decision_limit" if interrupted else "target_hit",
                        "interrupted": interrupted,
                    }
                )
                active_episode_index += 1
                episode_decision_index = 0
                episode_start_index = len(transitions)
                episode_return = 0.0

            if len(episodes) == len(contract["collection"]["episodes"]):
                break

            actions = np.zeros((len(decision_steps), 2), dtype=np.int32)
            for decision_row, raw_agent_id in enumerate(decision_steps.agent_id):
                agent_id = int(raw_agent_id)
                observation = validate_observation(
                    decision_steps.obs[0][decision_row],
                    "decision observation",
                )
                action_masks = read_action_masks(decision_steps, decision_row)
                if agent_id in collector.pending_agent_ids:
                    reward = float(decision_steps.reward[decision_row])
                    _record_transition(
                        collector,
                        agent_id,
                        reward,
                        observation,
                        action_masks,
                        terminated=False,
                        truncated=False,
                        transitions=transitions,
                        episode_index=active_episode_index,
                        episode_decision_index=episode_decision_index,
                    )
                    episode_return += reward
                    episode_decision_index += 1

                selector = contract["collection"]["episodes"][active_episode_index][
                    "selector"
                ]
                if selector == "online_network_masked_greedy":
                    action = greedy_selector.select(observation, action_masks)
                elif selector == "fixed_left_then_stay_idle":
                    movement = 0 if action_masks[0][1] else 1
                    action = np.asarray([movement, 0], dtype=np.int64)
                else:
                    raise LLAPIContractError(f"Unexpected selector {selector}.")
                collector.begin(agent_id, observation, action, action_masks)
                actions[decision_row] = action

            if len(decision_steps) > 0:
                environment.set_actions(
                    behavior_id,
                    ActionTuple(discrete=actions),
                )
            environment.step()
        else:
            raise LLAPIContractError("LLAPI collection exceeded its contract bound.")

        if collector.pending_agent_ids:
            raise LLAPIContractError(
                f"Pending decisions remain: {collector.pending_agent_ids}."
            )
        side_channel.assert_empty()
        online_after = network_sha256(controller.online_network)
        target_after = network_sha256(controller.target_network)
        if controller.optimizer_update_count != 0 or controller.target_sync_count != 0:
            raise LLAPIContractError("LLAPI collection performed a learning operation.")
        if online_before != online_after or target_before != target_after:
            raise LLAPIContractError("LLAPI collection changed network weights.")

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
            "policy_seed": policy_seed,
            "episodes": episodes,
            "truncation_events": truncation_events,
            "transitions": transitions,
            "replay": {
                "decision_count": controller.decision_count,
                "size": len(controller.replay),
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
    if trace["contract_sha256"] != sha256_file(CONTRACT_PATH):
        raise LLAPIContractError("Trace contract hash differs from the active contract.")
    transitions = trace["transitions"]
    episodes = trace["episodes"]
    if [item["episode_index"] for item in episodes] != [0, 1]:
        raise LLAPIContractError("Episode indices are not exactly [0, 1].")
    if [item["index"] for item in transitions] != list(range(len(transitions))):
        raise LLAPIContractError("Transition indices are not contiguous.")
    if trace["replay"] != {
        "decision_count": len(transitions),
        "size": len(transitions),
    }:
        raise LLAPIContractError("Replay counters differ from the LLAPI trace size.")

    for episode in episodes:
        start = episode["transition_start_index"]
        stop = start + episode["transition_count"]
        episode_transitions = transitions[start:stop]
        if len(episode_transitions) != episode["transition_count"]:
            raise LLAPIContractError("Episode transition span is incomplete.")
        if any(
            item["episode_index"] != episode["episode_index"]
            for item in episode_transitions
        ):
            raise LLAPIContractError("A transition is assigned to the wrong episode.")
        if not math.isclose(
            sum(item["reward"] for item in episode_transitions),
            episode["return"],
            rel_tol=0.0,
            abs_tol=1e-7,
        ):
            raise LLAPIContractError("Episode return differs from transition rewards.")
        if [item["episode_decision_index"] for item in episode_transitions] != list(
            range(len(episode_transitions))
        ):
            raise LLAPIContractError("Episode decision indices are not contiguous.")
        for current, following in zip(episode_transitions, episode_transitions[1:]):
            if current["next_observation_sha256"] != following[
                "observation_sha256"
            ]:
                raise LLAPIContractError("Consecutive LLAPI observations do not join.")
            if current["next_action_masks"] != following["action_masks"]:
                raise LLAPIContractError("Consecutive LLAPI action masks do not join.")
            if current["terminated"] or current["truncated"]:
                raise LLAPIContractError("A nonfinal transition has an end flag.")
        final = episode_transitions[-1]
        if final["terminated"] != (episode["end_kind"] == "terminal"):
            raise LLAPIContractError("Episode terminal flag disagrees with its record.")
        if final["truncated"] != (episode["end_kind"] == "truncated"):
            raise LLAPIContractError("Episode truncation flag disagrees with its record.")

    for item in transitions:
        if item["terminated"] and item["truncated"]:
            raise LLAPIContractError("A transition has conflicting end flags.")
        for branch, action in enumerate(item["action"]):
            if item["action_masks"][branch][action]:
                raise LLAPIContractError("A transition selected an unavailable action.")

    if any(
        (
            episodes[0]["selector"] != "online_network_masked_greedy",
            episodes[0]["transition_start_index"] != 0,
            episodes[0]["end_kind"] != "terminal",
            episodes[0]["reason"] != "target_hit",
            episodes[0]["interrupted"],
        )
    ):
        raise LLAPIContractError(
            "The first LLAPI episode did not prove greedy terminal collection."
        )
    if episodes[0]["transition_count"] > 5:
        raise LLAPIContractError("The greedy terminal episode exceeded five decisions.")
    terminal_transition = transitions[episodes[0]["transition_count"] - 1]
    if terminal_transition["next_action_masks"] != [
        [False, False, False],
        [False, False],
    ]:
        raise LLAPIContractError("The true terminal did not use the sentinel mask.")
    if episodes[1] != {
        "episode_index": 1,
        "selector": "fixed_left_then_stay_idle",
        "transition_start_index": episodes[1]["transition_start_index"],
        "transition_count": 300,
        "return": episodes[1]["return"],
        "end_kind": "truncated",
        "reason": "decision_limit",
        "interrupted": True,
    }:
        raise LLAPIContractError("The second LLAPI episode is not the exact truncation proof.")
    if episodes[1]["transition_start_index"] != episodes[0]["transition_count"]:
        raise LLAPIContractError("Episode transition spans are not contiguous.")
    second_start = episodes[1]["transition_start_index"]
    second_transitions = transitions[second_start:]
    expected_actions = [[1, 0]] * 4 + [[0, 0]] * 296
    if [item["action"] for item in second_transitions] != expected_actions:
        raise LLAPIContractError(
            "The truncation proof did not move left four times and then idle."
        )
    event = trace["truncation_events"][0]
    if event["position_slot"] != -4 or event["next_action_masks"] != [
        [False, True, False],
        [False, False],
    ]:
        raise LLAPIContractError(
            "The live truncation event did not prove the left-boundary mask."
        )
    if transitions[-1]["next_action_masks"] != event["next_action_masks"]:
        raise LLAPIContractError("Final replay mask differs from the Unity side-channel mask.")

    guard = trace["learning_guard"]
    if guard["online_before_sha256"] != guard["online_after_sha256"]:
        raise LLAPIContractError("Online weights changed during collection.")
    if guard["target_before_sha256"] != guard["target_after_sha256"]:
        raise LLAPIContractError("Target weights changed during collection.")


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    bindings = (
        contract["base_environment_contract"],
        contract["base_foundation_contract"],
        contract["base_optimizer_contract"],
    )
    for binding in bindings:
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
        raise LLAPIContractError("The active runtime differs from the LLAPI contract.")
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != contract["package"]["distribution"]:
        raise LLAPIContractError("The LLAPI package name has drifted.")
    if pyproject["project"]["version"] != contract["package"]["version"]:
        raise LLAPIContractError("The LLAPI package version has drifted.")
    if "entry-points" in pyproject["project"]:
        raise LLAPIContractError("The retired trainer entry point is still registered.")
    for relative_path in contract["retired_trajectory_scaffolding"]:
        if (REPO_ROOT / relative_path).exists():
            raise LLAPIContractError(
                f"Retired trajectory scaffolding still exists: {relative_path}."
            )
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
        timeout=360,
        check=False,
    )
    log_path = output_directory / f"worker-{worker_index + 1}.log"
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Fresh LLAPI worker {worker_index + 1} failed with exit code "
            f"{completed.returncode}; see {log_path}."
        )
    trace_path = worker_output / TRACE_FILE_NAME
    if not trace_path.is_file():
        raise RuntimeError(f"Fresh LLAPI worker omitted {trace_path}.")
    return json.loads(trace_path.read_text(encoding="utf-8")), trace_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the direct Basic BDQ LLAPI replay smoke twice."
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
        raise FileExistsError(f"LLAPI output must be fresh: {output_directory}.")
    output_directory.mkdir(parents=True)

    first, first_path = run_fresh_worker(executable, output_directory, 0)
    second, second_path = run_fresh_worker(executable, output_directory, 1)
    validate_trace(first, result_schema)
    validate_trace(second, result_schema)
    if first != second or first_path.read_bytes() != second_path.read_bytes():
        raise LLAPIContractError(
            f"Fresh LLAPI traces differ: {first_path} versus {second_path}."
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
    print("episodes_per_process=2")
    print(f"transitions={len(first['transitions'])}")
    print("terminal_episodes=1")
    print("truncated_episodes=1")
    print("optimizer_updates=0")
    print("exact_trace_equality=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
