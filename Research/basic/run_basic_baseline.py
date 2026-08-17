from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from jsonschema import Draft202012Validator
from mlagents_envs.base_env import ActionTuple
from mlagents_envs.environment import UnityEnvironment


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = (REPO_ROOT / "Artifacts" / "Experiments").resolve()
CONTRACT_PATH = Path(__file__).with_name("basic-contract-v1.json")
SCHEMA_PATH = (
    REPO_ROOT / "Research" / "schemas" / "basic-baseline-trace.schema.json"
)
TRACE_SCHEMA_VERSION = "quickdraw.basic-baseline-trace.v1"
EPISODE_SCHEMA_VERSION = "quickdraw.basic-episode.v1"
TARGET_SAMPLER = "quickdraw.basic-target-slot.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(value: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(value, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()


def sample_target_slot(scenario_seed: int, episode_index: int) -> int:
    if scenario_seed < 0 or episode_index < 0:
        raise ValueError("Scenario seed and episode index must be non-negative.")
    mask = 0xFFFFFFFF
    value = scenario_seed & mask
    value ^= (((episode_index + 1) & mask) * 0x9E3779B9) & mask
    value ^= value >> 16
    value = (value * 0x7FEB352D) & mask
    value ^= value >> 15
    value = (value * 0x846CA68B) & mask
    value ^= value >> 16
    return int(value % 9) - 4


def read_action_masks(decision_steps: Any, index: int) -> List[List[bool]]:
    if decision_steps.action_mask is None:
        raise RuntimeError("Research_Basic did not return discrete action masks.")
    masks = [
        [bool(value) for value in branch[index].tolist()]
        for branch in decision_steps.action_mask
    ]
    if [len(branch) for branch in masks] != [3, 2]:
        raise RuntimeError(f"Unexpected action-mask branches: {masks}")
    return masks


def available_actions(mask: Sequence[bool]) -> List[int]:
    result = [index for index, unavailable in enumerate(mask) if not unavailable]
    if not result:
        raise RuntimeError("An action branch has no mechanically available action.")
    return result


class BasicPolicy:
    policy_id: str
    kind: str
    seed: int

    def act(
        self,
        observation: np.ndarray,
        action_mask: Sequence[Sequence[bool]],
    ) -> Tuple[int, int]:
        raise NotImplementedError


class RandomVisualPolicy(BasicPolicy):
    policy_id = "random-visual-v1"
    kind = "random"

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._random = np.random.default_rng(seed)

    def act(
        self,
        observation: np.ndarray,
        action_mask: Sequence[Sequence[bool]],
    ) -> Tuple[int, int]:
        del observation
        movement = int(self._random.choice(available_actions(action_mask[0])))
        combat = int(self._random.choice(available_actions(action_mask[1])))
        return movement, combat


class ScriptedVisualPolicy(BasicPolicy):
    policy_id = "scripted-visual-v1"
    kind = "scripted"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def act(
        self,
        observation: np.ndarray,
        action_mask: Sequence[Sequence[bool]],
    ) -> Tuple[int, int]:
        if observation.shape != (84, 84, 4):
            raise RuntimeError(f"Unexpected visual observation shape {observation.shape}.")
        latest = observation[:, :, -1]
        target_pixels = np.argwhere(latest >= 0.7)
        if target_pixels.size == 0:
            raise RuntimeError("The scripted visual policy could not see the target.")

        centroid_x = float(target_pixels[:, 1].mean())
        center_x = (latest.shape[1] - 1) / 2.0
        if abs(centroid_x - center_x) <= 1.25:
            action = (0, 1)
        elif centroid_x < center_x:
            action = (1, 0)
        else:
            action = (2, 0)

        if action_mask[0][action[0]] or action_mask[1][action[1]]:
            raise RuntimeError(
                f"Scripted visual policy selected masked action {action} from "
                f"{action_mask}."
            )
        return action


def create_policy(kind: str, contract: Dict[str, Any]) -> BasicPolicy:
    policy_contract = contract["policies"][kind]
    seed = int(policy_contract["policy_seed"])
    if kind == "random":
        return RandomVisualPolicy(seed)
    if kind == "scripted":
        return ScriptedVisualPolicy(seed)
    raise ValueError(f"Unsupported Basic policy {kind}.")


def semantic_action(action: Tuple[int, int]) -> Dict[str, str]:
    return {
        "movement": ("Stay", "Left", "Right")[action[0]],
        "combat": ("Idle", "Shoot")[action[1]],
        "utility": "Idle",
    }


def begin_transition(
    decision_index: int,
    observation: np.ndarray,
    action_mask: List[List[bool]],
    action: Tuple[int, int],
) -> Dict[str, Any]:
    if observation.dtype != np.float32:
        raise RuntimeError(f"Observation dtype was {observation.dtype}, expected float32.")
    if not np.all(np.isfinite(observation)):
        raise RuntimeError("Observation contains a non-finite value.")
    minimum = float(np.min(observation))
    maximum = float(np.max(observation))
    if minimum < 0.0 or maximum > 1.0:
        raise RuntimeError(
            f"Observation range [{minimum}, {maximum}] is outside [0, 1]."
        )
    latest = observation[:, :, -1]
    return {
        "decision_index": decision_index,
        "observation_sha256": sha256_array(observation),
        "latest_frame_sha256": sha256_array(latest),
        "latest_frame_range": [round(minimum, 7), round(maximum, 7)],
        "action_mask": action_mask,
        "action": [action[0], action[1]],
        "semantic_action": semantic_action(action),
    }


def validate_reset_stack(observation: np.ndarray) -> str:
    if observation.shape != (84, 84, 4):
        raise RuntimeError(f"Unexpected reset observation shape {observation.shape}.")
    first = observation[:, :, 0]
    for channel in range(1, observation.shape[2]):
        if not np.array_equal(first, observation[:, :, channel]):
            raise RuntimeError(
                "Initial visual stack contains a stale frame instead of four "
                "copies of the post-reset frame."
            )
    return sha256_array(first)


def finish_transition(
    transition: Dict[str, Any],
    reward: float,
    cumulative_reward: float,
    terminal: bool,
    interrupted: bool,
) -> None:
    transition["reward"] = round(float(reward), 7)
    transition["cumulative_reward"] = round(float(cumulative_reward), 7)
    transition["terminal"] = terminal
    transition["interrupted"] = interrupted


def execute_trace(
    executable: Path,
    policy: BasicPolicy,
    contract: Dict[str, Any],
    output_directory: Path,
    episode_count: int,
) -> Dict[str, Any]:
    scenario_seed = int(contract["scenario_seed"])
    player_log_directory = output_directory / "player-log"
    player_log_directory.mkdir(parents=True, exist_ok=True)
    environment = UnityEnvironment(
        file_name=str(executable),
        seed=scenario_seed,
        no_graphics=False,
        timeout_wait=120,
        log_folder=str(player_log_directory),
    )

    episodes: List[Dict[str, Any]] = []
    pending: Dict[int, Dict[str, Any]] = {}
    active_episode_index = 0
    maximum_iterations = episode_count * (int(contract["episode_end"]["decision_limit"]) + 2)
    iterations = 0

    try:
        environment.reset()
        behavior_names = list(environment.behavior_specs)
        if len(behavior_names) != 1:
            raise RuntimeError(f"Expected one behavior, found {behavior_names}.")
        behavior_name = behavior_names[0]
        if not behavior_name.startswith(contract["behavior_name"]):
            raise RuntimeError(f"Unexpected behavior name {behavior_name}.")
        behavior_spec = environment.behavior_specs[behavior_name]
        observation_shapes = [
            list(spec.shape) for spec in behavior_spec.observation_specs
        ]
        action_branches = list(behavior_spec.action_spec.discrete_branches)
        if observation_shapes != [contract["observation"]["shape"]]:
            raise RuntimeError(f"Unexpected observation shapes {observation_shapes}.")
        if action_branches != contract["actions"]["discrete_branches"]:
            raise RuntimeError(f"Unexpected action branches {action_branches}.")

        current_episode: Dict[str, Any] | None = None
        cumulative_reward = 0.0
        while len(episodes) < episode_count:
            iterations += 1
            if iterations > maximum_iterations:
                raise RuntimeError("Basic baseline exceeded its contract-derived bound.")

            decision_steps, terminal_steps = environment.get_steps(behavior_name)
            for terminal_index, raw_agent_id in enumerate(terminal_steps.agent_id):
                agent_id = int(raw_agent_id)
                transition = pending.pop(agent_id, None)
                if transition is None or current_episode is None:
                    raise RuntimeError(f"Missing pending terminal transition for {agent_id}.")
                reward = float(terminal_steps.reward[terminal_index])
                cumulative_reward += reward
                interrupted = bool(terminal_steps.interrupted[terminal_index])
                finish_transition(
                    transition,
                    reward,
                    cumulative_reward,
                    True,
                    interrupted,
                )
                current_episode["transitions"].append(transition)
                current_episode["decision_count"] = len(current_episode["transitions"])
                current_episode["return"] = round(cumulative_reward, 7)
                current_episode["shots_fired"] = sum(
                    item["action"][1] == 1 for item in current_episode["transitions"]
                )
                success = not interrupted
                current_episode["success"] = success
                current_episode["misses"] = (
                    current_episode["shots_fired"] - (1 if success else 0)
                )
                current_episode["end_kind"] = (
                    "truncated" if interrupted else "terminal"
                )
                current_episode["reason"] = (
                    contract["episode_end"]["truncation_reason"]
                    if interrupted
                    else contract["episode_end"]["terminal_reason"]
                )
                current_episode["interrupted"] = interrupted
                if success and transition["action"][1] != 1:
                    raise RuntimeError("A terminal hit ended without a Shoot action.")
                if interrupted and current_episode["decision_count"] != 300:
                    raise RuntimeError("Decision-limit truncation did not occur at 300.")
                if policy.kind == "scripted":
                    expected_decisions = abs(current_episode["target_slot"]) + 1
                    if current_episode["decision_count"] != expected_decisions:
                        raise RuntimeError(
                            "Scripted result disagrees with the registered target slot: "
                            f"{current_episode}."
                        )
                    if current_episode["shots_fired"] != 1 or current_episode["misses"] != 0:
                        raise RuntimeError(
                            "Scripted visual baseline did not produce one aligned hit."
                        )
                episodes.append(current_episode)
                current_episode = None
                cumulative_reward = 0.0
                active_episode_index += 1

            if len(episodes) >= episode_count:
                break

            for decision_index, raw_agent_id in enumerate(decision_steps.agent_id):
                agent_id = int(raw_agent_id)
                observation = decision_steps.obs[0][decision_index]
                if agent_id in pending:
                    if current_episode is None:
                        raise RuntimeError("A nonterminal transition has no active episode.")
                    transition = pending.pop(agent_id)
                    reward = float(decision_steps.reward[decision_index])
                    cumulative_reward += reward
                    finish_transition(
                        transition,
                        reward,
                        cumulative_reward,
                        False,
                        False,
                    )
                    current_episode["transitions"].append(transition)

                if current_episode is None:
                    current_episode = {
                        "schema_version": EPISODE_SCHEMA_VERSION,
                        "episode_index": active_episode_index,
                        "scenario_seed": scenario_seed,
                        "target_slot": sample_target_slot(
                            scenario_seed,
                            active_episode_index,
                        ),
                        "policy_id": policy.policy_id,
                        "initial_frame_sha256": validate_reset_stack(observation),
                        "reset_stack_filled": True,
                        "transitions": [],
                    }

                action_mask = read_action_masks(decision_steps, decision_index)
                action = policy.act(observation, action_mask)
                if action_mask[0][action[0]] or action_mask[1][action[1]]:
                    raise RuntimeError(
                        f"Policy selected masked action {action} from {action_mask}."
                    )
                pending[agent_id] = begin_transition(
                    len(current_episode["transitions"]),
                    observation,
                    action_mask,
                    action,
                )

            if len(decision_steps) > 0:
                actions = np.zeros((len(decision_steps), 2), dtype=np.int32)
                for decision_index, raw_agent_id in enumerate(decision_steps.agent_id):
                    actions[decision_index] = pending[int(raw_agent_id)]["action"]
                environment.set_actions(
                    behavior_name,
                    ActionTuple(discrete=actions),
                )
            environment.step()

        if pending:
            raise RuntimeError(f"Unfinished transitions remain: {sorted(pending)}")

        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "behavior": {
                "name": contract["behavior_name"],
                "observation_shape": observation_shapes[0],
                "wire_layout": contract["observation"]["wire_layout"],
                "discrete_branches": action_branches,
            },
            "policy": {
                "policy_id": policy.policy_id,
                "kind": policy.kind,
                "seed": policy.seed,
                "visual_input_only": True,
            },
            "scenario": {
                "seed": scenario_seed,
                "target_sampler": TARGET_SAMPLER,
                "episode_count": episode_count,
            },
            "episodes": episodes,
        }
    finally:
        environment.close()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a deterministic Research_Basic random or scripted LLAPI baseline."
    )
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--policy", required=True, choices=("random", "scripted"))
    parser.add_argument("--episodes", type=int)
    parser.add_argument("--compare-to", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    executable = arguments.env.resolve()
    output_directory = arguments.output.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if ARTIFACT_ROOT not in output_directory.parents:
        raise ValueError(f"Output must be below {ARTIFACT_ROOT}.")

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    episode_count = (
        int(arguments.episodes)
        if arguments.episodes is not None
        else int(contract["episode_count"])
    )
    if episode_count <= 0:
        raise ValueError("Episode count must be positive.")
    output_directory.mkdir(parents=True, exist_ok=True)
    policy = create_policy(arguments.policy, contract)
    trace = execute_trace(
        executable,
        policy,
        contract,
        output_directory,
        episode_count,
    )

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(trace)
    trace_path = output_directory / "trace.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if arguments.compare_to is not None:
        reference = json.loads(arguments.compare_to.read_text(encoding="utf-8"))
        if trace != reference:
            raise RuntimeError(
                f"Canonical Basic trace differs from {arguments.compare_to}."
            )

    successes = sum(episode["success"] for episode in trace["episodes"])
    print(f"trace={trace_path}")
    print(f"policy={policy.policy_id}")
    print(f"episodes={episode_count}")
    print(f"successes={successes}")
    print(
        "comparison="
        + ("pass" if arguments.compare_to is not None else "reference-captured")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
