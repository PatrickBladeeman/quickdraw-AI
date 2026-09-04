"""Shared live-Unity update-gate execution and trace validation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import torch
from jsonschema import Draft202012Validator
from mlagents_envs.base_env import ActionTuple
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.engine_configuration_channel import (
    EngineConfigurationChannel,
)


from .action_space import greedy_actions
from .exploration import LinearEpsilonSchedule
from .llapi import (
    BASIC_BEHAVIOR_NAME,
    BasicTruncationMaskSideChannel,
    DirectReplayCollector,
    LLAPIContractError,
    ScheduledEpsilonGreedyBDQActionSelector,
    SeededEpsilonGreedyBDQActionSelector,
    network_sha256,
    observation_sha256,
    read_action_masks,
    validate_action_masks,
    validate_basic_behavior_spec,
    validate_observation,
)
from .optimizer import (
    BDQOptimizationSettings,
    BDQOptimizerController,
    OptimizationStepResult,
)
from .acceptance import (
    action_tuple_counts as _action_tuple_counts,
    episode_record as _episode_record,
    masks_to_json as _masks_to_json,
    registered_settings as _registered_settings,
    sha256_file,
    transition_to_json as _transition_to_json,
)


WATCH_BASE_PORT = 5004
WATCH_PROGRESS_INTERVAL = 100
WATCH_TARGET_FRAME_RATE = 60
WATCH_TIME_SCALE = 1.0


def configure_torch(
    determinism: Dict[str, Any],
    task_name: str = "R3F",
) -> None:
    torch.set_num_threads(int(determinism["torch_num_threads"]))
    torch.set_num_interop_threads(int(determinism["torch_num_interop_threads"]))
    torch.use_deterministic_algorithms(bool(determinism["deterministic_algorithms"]))
    if torch.get_num_threads() != int(determinism["torch_num_threads"]):
        raise LLAPIContractError(
            f"PyTorch intra-op thread count differs from {task_name}."
        )
    if torch.get_num_interop_threads() != int(
        determinism["torch_num_interop_threads"]
    ):
        raise LLAPIContractError(
            f"PyTorch inter-op thread count differs from {task_name}."
        )
    if torch.are_deterministic_algorithms_enabled() is not bool(
        determinism["deterministic_algorithms"]
    ):
        raise LLAPIContractError(
            f"PyTorch deterministic mode differs from {task_name}."
        )


def _optimization_event(
    result: OptimizationStepResult,
    *,
    task_name: str = "R3F",
) -> Dict[str, Any]:
    if result.loss is None or result.mean_absolute_td_error is None:
        raise LLAPIContractError(
            f"{task_name} optimizer update omitted required metrics."
        )
    if not math.isfinite(result.loss):
        raise LLAPIContractError(f"{task_name} optimizer loss is not finite.")
    if not math.isfinite(result.mean_absolute_td_error):
        raise LLAPIContractError(
            f"{task_name} mean absolute TD error is not finite."
        )
    return {
        "decision_count": result.decision_count,
        "replay_size": result.replay_size,
        "optimizer_update_count": result.optimizer_update_count,
        "target_sync_count": result.target_sync_count,
        "updated": result.updated,
        "target_synced": result.target_synced,
        "loss": result.loss,
        "mean_absolute_td_error": result.mean_absolute_td_error,
    }


def _complete_gate_transition(
    collector: DirectReplayCollector,
    agent_id: int,
    reward: float,
    next_observation: np.ndarray,
    next_action_masks: Sequence[np.ndarray],
    *,
    terminated: bool,
    truncated: bool,
    transitions: list[Dict[str, Any]],
    optimization_events: list[Dict[str, Any]],
    episode_index: int,
    episode_decision_index: int,
    expected_update_decisions: Sequence[int],
    task_name: str,
) -> OptimizationStepResult:
    transition, result = collector.complete(
        agent_id,
        reward,
        next_observation,
        next_action_masks,
        terminated=terminated,
        truncated=truncated,
    )
    transitions.append(
        _transition_to_json(
            transition,
            len(transitions),
            episode_index,
            episode_decision_index,
        )
    )
    expected_updates = frozenset(int(value) for value in expected_update_decisions)
    if result.target_synced:
        raise LLAPIContractError(f"{task_name} synchronized the target network.")
    if result.updated:
        if result.decision_count not in expected_updates:
            raise LLAPIContractError(
                f"{task_name} optimizer update opened at the wrong decision."
            )
        optimization_events.append(_optimization_event(result, task_name=task_name))
    elif result.decision_count in expected_updates:
        raise LLAPIContractError(
            f"{task_name} missed a registered optimizer update."
        )
    return result


def _select_post_update_greedy_action(
    controller: BDQOptimizerController,
    observation: np.ndarray,
    action_masks: Sequence[np.ndarray],
    *,
    handoff_contract: Dict[str, Any],
    optimization_events: Sequence[Dict[str, Any]],
    target_before_sha256: str,
    episode_index: int,
    episode_decision_index: int,
) -> tuple[np.ndarray, Dict[str, Any]]:
    """Select one live greedy action and bind it to the post-update networks."""

    selection_after = int(handoff_contract["selection_after_decision_count"])
    required_updates = int(handoff_contract["required_optimizer_update_count"])
    if controller.decision_count != selection_after:
        raise LLAPIContractError(
            "Post-update greedy selection opened at the wrong decision."
        )
    if controller.optimizer_update_count != required_updates:
        raise LLAPIContractError(
            "Post-update greedy selection observed the wrong optimizer count."
        )
    if controller.target_sync_count != 0:
        raise LLAPIContractError(
            "Post-update greedy selection observed a target synchronization."
        )
    if len(optimization_events) != required_updates:
        raise LLAPIContractError(
            "Post-update greedy selection is not bound to every prior update."
        )

    validated_observation = validate_observation(
        observation,
        "post-update greedy observation",
    )
    validated_masks = validate_action_masks(
        action_masks,
        "post-update greedy action_masks",
    )
    online_sha256 = network_sha256(controller.online_network)
    target_sha256 = network_sha256(controller.target_network)
    if online_sha256 != optimization_events[-1]["online_after_sha256"]:
        raise LLAPIContractError(
            "Post-update greedy selection did not use the latest online network."
        )
    if target_sha256 != target_before_sha256:
        raise LLAPIContractError(
            "Post-update greedy comparison target changed before synchronization."
        )

    observation_tensor = torch.as_tensor(
        validated_observation[None, ...],
        dtype=torch.float32,
    )
    mask_tensors = tuple(
        torch.tensor(mask[None, ...], dtype=torch.bool)
        for mask in validated_masks
    )
    controller.online_network.eval()
    controller.target_network.eval()
    with torch.no_grad():
        online_q = controller.online_network(observation_tensor)
        target_q = controller.target_network(observation_tensor)
        selected = greedy_actions(online_q, mask_tensors)

    online_values = [
        [float(value) for value in branch[0].cpu().tolist()]
        for branch in online_q
    ]
    target_values = [
        [float(value) for value in branch[0].cpu().tolist()]
        for branch in target_q
    ]
    maximum_delta = max(
        abs(online_value - target_value)
        for online_branch, target_branch in zip(online_values, target_values)
        for online_value, target_value in zip(online_branch, target_branch)
    )
    if not math.isfinite(maximum_delta) or maximum_delta <= 0.0:
        raise LLAPIContractError(
            "Post-update online Q-values did not diverge from the frozen target."
        )

    action = selected[0].to(dtype=torch.int64).cpu().numpy()
    if any(
        bool(validated_masks[branch][int(branch_action)])
        for branch, branch_action in enumerate(action)
    ):
        raise LLAPIContractError(
            "Post-update greedy selection chose an unavailable action."
        )
    evidence = {
        "selection_after_decision_count": controller.decision_count,
        "transition_index": controller.decision_count,
        "episode_index": episode_index,
        "episode_decision_index": episode_decision_index,
        "epsilon": float(handoff_contract["epsilon"]),
        "optimizer_update_count": controller.optimizer_update_count,
        "target_sync_count": controller.target_sync_count,
        "online_sha256": online_sha256,
        "target_sha256": target_sha256,
        "observation_sha256": observation_sha256(validated_observation),
        "action_masks": _masks_to_json(validated_masks),
        "online_q_values": online_values,
        "target_q_values": target_values,
        "max_absolute_q_delta": maximum_delta,
        "selected_action": [int(value) for value in action],
        "selected_action_legal": True,
        "masked_argmax_verified": True,
    }
    return action, evidence


def _select_scheduled_epsilon_handoff_action(
    controller: BDQOptimizerController,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    observation: np.ndarray,
    action_masks: Sequence[np.ndarray],
    *,
    handoff_contract: Dict[str, Any],
    optimization_events: Sequence[Dict[str, Any]],
    target_before_sha256: str,
    episode_index: int,
    episode_decision_index: int,
) -> tuple[np.ndarray, Dict[str, Any]]:
    """Select one live scheduled action after the registered optimizer prefix."""

    selection_after = int(handoff_contract["selection_after_decision_count"])
    required_updates = int(handoff_contract["required_optimizer_update_count"])
    if controller.decision_count != selection_after:
        raise LLAPIContractError(
            "Scheduled epsilon selection opened at the wrong decision."
        )
    if controller.optimizer_update_count != required_updates:
        raise LLAPIContractError(
            "Scheduled epsilon selection observed the wrong optimizer count."
        )
    if controller.target_sync_count != 0:
        raise LLAPIContractError(
            "Scheduled epsilon selection observed a target synchronization."
        )
    if len(optimization_events) != required_updates:
        raise LLAPIContractError(
            "Scheduled epsilon selection is not bound to every prior update."
        )

    epsilon = selector.schedule.epsilon_at(controller.decision_count)
    if not math.isclose(
        epsilon,
        float(handoff_contract["epsilon"]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise LLAPIContractError(
            "Scheduled epsilon selection used the wrong epsilon."
        )
    validated_observation = validate_observation(
        observation,
        "scheduled epsilon handoff observation",
    )
    validated_masks = validate_action_masks(
        action_masks,
        "scheduled epsilon handoff action_masks",
    )
    online_sha256 = network_sha256(controller.online_network)
    target_sha256 = network_sha256(controller.target_network)
    if online_sha256 != optimization_events[-1]["online_after_sha256"]:
        raise LLAPIContractError(
            "Scheduled epsilon selection did not use the latest online network."
        )
    if target_sha256 != target_before_sha256:
        raise LLAPIContractError(
            "Scheduled epsilon selection observed a changed target network."
        )

    action = selector.select(
        validated_observation,
        validated_masks,
        completed_transition_count=controller.decision_count,
    )
    if any(
        bool(validated_masks[branch][int(branch_action)])
        for branch, branch_action in enumerate(action)
    ):
        raise LLAPIContractError(
            "Scheduled epsilon selection chose an unavailable action."
        )
    masks_json = _masks_to_json(validated_masks)
    action_json = [int(value) for value in action]
    expected_masks = handoff_contract.get("expected_action_masks")
    if expected_masks is not None and masks_json != expected_masks:
        raise LLAPIContractError(
            "Scheduled epsilon selection observed unexpected action masks."
        )
    expected_action = handoff_contract.get("expected_selected_action")
    if expected_action is not None and action_json != expected_action:
        raise LLAPIContractError(
            "Scheduled epsilon selection differs from its registered action."
        )
    observation_hash = observation_sha256(validated_observation)
    expected_observation_hash = handoff_contract.get(
        "expected_observation_sha256"
    )
    if (
        expected_observation_hash is not None
        and observation_hash != expected_observation_hash
    ):
        raise LLAPIContractError(
            "Scheduled epsilon selection observed the wrong live state."
        )
    evidence = {
        "selection_after_decision_count": controller.decision_count,
        "transition_index": controller.decision_count,
        "selection_ordinal": controller.decision_count,
        "episode_index": episode_index,
        "episode_decision_index": episode_decision_index,
        "completed_transition_count_source": handoff_contract[
            "completed_transition_count_source"
        ],
        "epsilon": epsilon,
        "optimizer_update_count": controller.optimizer_update_count,
        "target_sync_count": controller.target_sync_count,
        "online_sha256": online_sha256,
        "target_sha256": target_sha256,
        "observation_sha256": observation_hash,
        "action_masks": masks_json,
        "selected_action": action_json,
        "selected_action_legal": True,
    }
    return action, evidence


def _emit_watch_progress(
    result: OptimizationStepResult,
    transition: Dict[str, Any],
    *,
    transition_limit: int,
    episode_index: int,
    episode_decision_index: int,
    progress_interval: int,
) -> None:
    if (
        progress_interval <= 0
        or (
            result.decision_count % progress_interval != 0
            and not result.updated
        )
    ):
        return
    action = json.dumps(transition["action"], separators=(",", ":"))
    print(
        "watch_progress "
        f"transition={result.decision_count}/{transition_limit} "
        f"episode={episode_index + 1} "
        f"episode_decision={episode_decision_index + 1} "
        f"action={action} "
        f"reward={float(transition['reward']):.6g} "
        f"replay_size={result.replay_size} "
        f"optimizer_updates={result.optimizer_update_count} "
        f"target_syncs={result.target_sync_count}",
        flush=True,
    )


def _environment_side_channels(
    truncation_side_channel: BasicTruncationMaskSideChannel,
    *,
    watch: bool,
) -> list[Any]:
    channels: list[Any] = [truncation_side_channel]
    if watch:
        engine_configuration = EngineConfigurationChannel()
        engine_configuration.set_configuration_parameters(
            time_scale=WATCH_TIME_SCALE,
            target_frame_rate=WATCH_TARGET_FRAME_RATE,
        )
        channels.append(engine_configuration)
    return channels


def execute_update_gate_worker(
    executable: Path | None,
    worker_output: Path,
    worker_index: int,
    contract: Dict[str, Any],
    *,
    contract_path: Path,
    trace_file_name: str,
    trace_schema_version: str,
    task_name: str,
    record_update_hashes: bool,
    base_port: int = 5045,
    timeout_wait: int = 120,
    watch: bool = False,
    progress_interval: int = 0,
) -> Dict[str, Any]:
    worker_output.mkdir(parents=True, exist_ok=False)
    collection = contract["collection"]
    optimization = contract["optimization"]
    determinism = contract["determinism"]
    settings = BDQOptimizationSettings()
    if _registered_settings(settings) != {
        key: optimization[key] for key in _registered_settings(settings)
    }:
        raise LLAPIContractError(
            f"Production optimizer settings differ from {task_name}."
        )
    transition_limit = int(collection["transition_limit"])
    expected_first_update = int(optimization["expected_first_update_decision"])
    expected_update_count = int(optimization["expected_optimizer_updates"])
    expected_update_decisions = tuple(
        expected_first_update
        + index * settings.optimizer_update_interval_decisions
        for index in range(expected_update_count)
    )
    if expected_first_update != settings.replay_warmup_decisions:
        raise LLAPIContractError(
            f"{task_name} first update differs from production replay warmup."
        )
    if not expected_update_decisions or expected_update_decisions[-1] > (
        transition_limit
    ):
        raise LLAPIContractError(
            f"{task_name} cutoff precedes its final registered optimizer update."
        )
    registered_update_decisions = optimization.get("expected_update_decisions")
    if registered_update_decisions is not None and tuple(
        int(value) for value in registered_update_decisions
    ) != expected_update_decisions:
        raise LLAPIContractError(
            f"{task_name} registered update decisions differ from its schedule."
        )
    greedy_handoff_contract = contract.get("post_update_greedy_handoff")
    scheduled_handoff_contract = contract.get("scheduled_epsilon_handoff")
    schedule_contract = contract.get("epsilon_schedule")
    if (
        greedy_handoff_contract is not None
        and scheduled_handoff_contract is not None
    ):
        raise LLAPIContractError(
            f"{task_name} cannot register two policy handoffs."
        )
    continuation_handoff_contract = (
        greedy_handoff_contract or scheduled_handoff_contract
    )
    if continuation_handoff_contract is None:
        if expected_update_decisions[-1] != transition_limit:
            raise LLAPIContractError(
                f"{task_name} cutoff is not its final registered optimizer update."
            )
    else:
        selection_after = int(
            continuation_handoff_contract["selection_after_decision_count"]
        )
        if selection_after != expected_update_decisions[-1]:
            raise LLAPIContractError(
                f"{task_name} policy handoff does not follow its final update."
            )
        if transition_limit != selection_after + 1:
            raise LLAPIContractError(
                f"{task_name} must complete exactly one policy handoff transition."
            )
    configure_torch(determinism, task_name)

    side_channel = BasicTruncationMaskSideChannel()
    side_channels = _environment_side_channels(side_channel, watch=watch)
    policy_seed = int(collection["policy_seed"])
    controller = BDQOptimizerController(policy_seed, settings)
    collector = DirectReplayCollector(controller)
    fixed_selector: SeededEpsilonGreedyBDQActionSelector | None = None
    scheduled_selector: ScheduledEpsilonGreedyBDQActionSelector | None = None
    schedule_sample_counts: tuple[int, ...] = ()
    if schedule_contract is None:
        fixed_selector = SeededEpsilonGreedyBDQActionSelector(
            controller.online_network,
            epsilon=float(collection["epsilon"]),
            seed=int(collection["exploration_seed"]),
        )
    else:
        schedule = LinearEpsilonSchedule(
            replay_warmup_decisions=int(
                schedule_contract["replay_warmup_decisions"]
            ),
            decay_decisions=int(schedule_contract["decay_decisions"]),
            initial_epsilon=float(schedule_contract["initial_epsilon"]),
            final_epsilon=float(schedule_contract["final_epsilon"]),
        )
        scheduled_selector = ScheduledEpsilonGreedyBDQActionSelector(
            controller.online_network,
            schedule=schedule,
            seed=int(collection["exploration_seed"]),
        )
        schedule_sample_counts = tuple(
            int(value)
            for value in schedule_contract[
                "trace_sample_completed_transition_counts"
            ]
        )
    online_before = network_sha256(controller.online_network)
    target_before = network_sha256(controller.target_network)
    if online_before != target_before:
        raise LLAPIContractError(
            f"{task_name} target did not begin as an online-network copy."
        )

    transitions: list[Dict[str, Any]] = []
    episodes: list[Dict[str, Any]] = []
    truncation_events: list[Dict[str, Any]] = []
    optimization_events: list[Dict[str, Any]] = []
    post_update_greedy_handoff: Dict[str, Any] | None = None
    scheduled_epsilon_handoff: Dict[str, Any] | None = None
    seeded_random_selection_count = 0
    scheduled_selection_count = 0
    observed_epsilon_samples: list[Dict[str, Any]] = []
    active_episode_index = 0
    episode_decision_index = 0
    episode_start_index = 0
    episode_return = 0.0
    ended_on_unity_boundary = False
    maximum_iterations = transition_limit + transition_limit // 300 + 20
    environment: UnityEnvironment | None = None

    try:
        environment_options: Dict[str, Any] = {
            "file_name": str(executable) if executable is not None else None,
            "worker_id": worker_index,
            "base_port": base_port,
            "seed": int(collection["scenario_seed"]),
            "side_channels": side_channels,
            "no_graphics": False,
            "timeout_wait": timeout_wait,
        }
        if executable is not None:
            environment_options["log_folder"] = str(worker_output / "player-log")
        environment = UnityEnvironment(**environment_options)
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
                raise LLAPIContractError(
                    f"{task_name} permits one Basic agent only."
                )
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
                optimization_result = _complete_gate_transition(
                    collector,
                    agent_id,
                    reward,
                    next_observation,
                    next_action_masks,
                    terminated=not interrupted,
                    truncated=interrupted,
                    transitions=transitions,
                    optimization_events=optimization_events,
                    episode_index=active_episode_index,
                    episode_decision_index=episode_decision_index,
                    expected_update_decisions=expected_update_decisions,
                    task_name=task_name,
                )
                if optimization_result.updated and record_update_hashes:
                    optimization_events[-1]["online_after_sha256"] = network_sha256(
                        controller.online_network
                    )
                if progress_interval > 0:
                    _emit_watch_progress(
                        optimization_result,
                        transitions[-1],
                        transition_limit=transition_limit,
                        episode_index=active_episode_index,
                        episode_decision_index=episode_decision_index,
                        progress_interval=progress_interval,
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
                raise LLAPIContractError(
                    f"{task_name} exceeded its exact transition limit."
                )
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
                    optimization_result = _complete_gate_transition(
                        collector,
                        agent_id,
                        float(decision_steps.reward[decision_row]),
                        observation,
                        action_masks,
                        terminated=False,
                        truncated=False,
                        transitions=transitions,
                        optimization_events=optimization_events,
                        episode_index=active_episode_index,
                        episode_decision_index=episode_decision_index,
                        expected_update_decisions=expected_update_decisions,
                        task_name=task_name,
                    )
                    if optimization_result.updated and record_update_hashes:
                        optimization_events[-1][
                            "online_after_sha256"
                        ] = network_sha256(controller.online_network)
                    if progress_interval > 0:
                        _emit_watch_progress(
                            optimization_result,
                            transitions[-1],
                            transition_limit=transition_limit,
                            episode_index=active_episode_index,
                            episode_decision_index=episode_decision_index,
                            progress_interval=progress_interval,
                        )
                    episode_return += float(decision_steps.reward[decision_row])
                    episode_decision_index += 1
                    if len(transitions) == transition_limit:
                        reached_limit = True
                        break
                if (
                    greedy_handoff_contract is not None
                    and controller.decision_count
                    == int(
                        greedy_handoff_contract[
                            "selection_after_decision_count"
                        ]
                    )
                ):
                    if post_update_greedy_handoff is not None:
                        raise LLAPIContractError(
                            f"{task_name} repeated its post-update greedy handoff."
                        )
                    action, post_update_greedy_handoff = (
                        _select_post_update_greedy_action(
                            controller,
                            observation,
                            action_masks,
                            handoff_contract=greedy_handoff_contract,
                            optimization_events=optimization_events,
                            target_before_sha256=target_before,
                            episode_index=active_episode_index,
                            episode_decision_index=episode_decision_index,
                        )
                    )
                elif scheduled_selector is not None:
                    completed_transition_count = controller.decision_count
                    epsilon = scheduled_selector.schedule.epsilon_at(
                        completed_transition_count
                    )
                    if completed_transition_count in schedule_sample_counts:
                        observed_epsilon_samples.append(
                            {
                                "completed_transition_count": (
                                    completed_transition_count
                                ),
                                "epsilon": epsilon,
                            }
                        )
                    if (
                        scheduled_handoff_contract is not None
                        and completed_transition_count
                        == int(
                            scheduled_handoff_contract[
                                "selection_after_decision_count"
                            ]
                        )
                    ):
                        if scheduled_epsilon_handoff is not None:
                            raise LLAPIContractError(
                                f"{task_name} repeated its scheduled handoff."
                            )
                        action, scheduled_epsilon_handoff = (
                            _select_scheduled_epsilon_handoff_action(
                                controller,
                                scheduled_selector,
                                observation,
                                action_masks,
                                handoff_contract=scheduled_handoff_contract,
                                optimization_events=optimization_events,
                                target_before_sha256=target_before,
                                episode_index=active_episode_index,
                                episode_decision_index=episode_decision_index,
                            )
                        )
                    else:
                        action = scheduled_selector.select(
                            observation,
                            action_masks,
                            completed_transition_count=(
                                completed_transition_count
                            ),
                        )
                    scheduled_selection_count += 1
                else:
                    assert fixed_selector is not None
                    action = fixed_selector.select(observation, action_masks)
                    seeded_random_selection_count += 1
                collector.begin(agent_id, observation, action, action_masks)
                actions[decision_row] = action

            if len(transitions) > transition_limit:
                raise LLAPIContractError(
                    f"{task_name} exceeded its exact transition limit."
                )
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
            raise LLAPIContractError(
                f"{task_name} collection exceeded its iteration bound."
            )

        if len(transitions) != transition_limit:
            raise LLAPIContractError(
                f"{task_name} collected {len(transitions)} transitions, "
                f"expected {transition_limit}."
            )
        if collector.pending_agent_ids:
            raise LLAPIContractError(
                f"Pending decisions remain at cutoff: {collector.pending_agent_ids}."
            )
        if greedy_handoff_contract is not None:
            if post_update_greedy_handoff is None:
                raise LLAPIContractError(
                    f"{task_name} omitted its post-update greedy handoff."
                )
            handoff_index = int(post_update_greedy_handoff["transition_index"])
            if handoff_index >= len(transitions):
                raise LLAPIContractError(
                    f"{task_name} did not complete its greedy handoff transition."
                )
            handoff_transition = transitions[handoff_index]
            if handoff_transition["action"] != post_update_greedy_handoff[
                "selected_action"
            ]:
                raise LLAPIContractError(
                    f"{task_name} greedy handoff action differs from replay."
                )
            if handoff_transition["observation_sha256"] != (
                post_update_greedy_handoff["observation_sha256"]
            ):
                raise LLAPIContractError(
                    f"{task_name} greedy handoff observation differs from replay."
                )
            if handoff_transition["action_masks"] != post_update_greedy_handoff[
                "action_masks"
            ]:
                raise LLAPIContractError(
                    f"{task_name} greedy handoff masks differ from replay."
                )
        if scheduled_handoff_contract is not None:
            if scheduled_epsilon_handoff is None:
                raise LLAPIContractError(
                    f"{task_name} omitted its scheduled epsilon handoff."
                )
            handoff_index = int(scheduled_epsilon_handoff["transition_index"])
            if handoff_index >= len(transitions):
                raise LLAPIContractError(
                    f"{task_name} did not complete its scheduled handoff transition."
                )
            handoff_transition = transitions[handoff_index]
            if handoff_transition["action"] != scheduled_epsilon_handoff[
                "selected_action"
            ]:
                raise LLAPIContractError(
                    f"{task_name} scheduled handoff action differs from replay."
                )
            if handoff_transition["observation_sha256"] != (
                scheduled_epsilon_handoff["observation_sha256"]
            ):
                raise LLAPIContractError(
                    f"{task_name} scheduled handoff observation differs from replay."
                )
            if handoff_transition["action_masks"] != scheduled_epsilon_handoff[
                "action_masks"
            ]:
                raise LLAPIContractError(
                    f"{task_name} scheduled handoff masks differ from replay."
                )
        side_channel.assert_empty()
        completed_episode_count = sum(
            1 for episode in episodes if episode["unity_episode_ended"]
        )
        if completed_episode_count < int(collection["minimum_completed_episodes"]):
            raise LLAPIContractError(
                f"{task_name} did not collect across an episode reset."
            )

        online_after = network_sha256(controller.online_network)
        target_after = network_sha256(controller.target_network)
        if controller.optimizer_update_count != int(
            optimization["expected_optimizer_updates"]
        ):
            raise LLAPIContractError(
                f"{task_name} optimizer update count differs from contract."
            )
        if controller.target_sync_count != int(
            optimization["expected_target_synchronizations"]
        ):
            raise LLAPIContractError(
                f"{task_name} target-sync count differs from contract."
            )
        if len(optimization_events) != controller.optimizer_update_count:
            raise LLAPIContractError(
                f"{task_name} optimizer events do not match its updates."
            )
        if online_before == online_after:
            raise LLAPIContractError(f"{task_name} online weights did not change.")
        if target_before != target_after:
            raise LLAPIContractError(
                f"{task_name} target weights changed before synchronization."
            )
        if online_after == target_after:
            raise LLAPIContractError(
                f"{task_name} online network still equals its frozen target."
            )

        action_tuple_counts = _action_tuple_counts(transitions)
        unique_action_tuple_count = sum(count > 0 for count in action_tuple_counts)
        if unique_action_tuple_count < int(collection["minimum_unique_action_tuples"]):
            raise LLAPIContractError(
                f"{task_name} did not collect every Basic action tuple."
            )

        selector_trace: Dict[str, Any]
        if scheduled_selector is not None:
            assert schedule_contract is not None
            expected_scheduled_selection_count = int(
                schedule_contract["selection_count"]
            )
            if scheduled_selection_count != expected_scheduled_selection_count:
                raise LLAPIContractError(
                    f"{task_name} scheduled selector count differs from contract."
                )
            post_update_greedy_selection_count = int(
                post_update_greedy_handoff is not None
            )
            if (
                scheduled_selection_count + post_update_greedy_selection_count
                != transition_limit
            ):
                raise LLAPIContractError(
                    f"{task_name} selector counts differ from cutoff."
                )
            if [
                sample["completed_transition_count"]
                for sample in observed_epsilon_samples
            ] != list(schedule_sample_counts):
                raise LLAPIContractError(
                    f"{task_name} omitted a registered epsilon sample."
                )
            selector_trace = {
                "name": collection["selector"],
                "epsilon_decay_enabled": collection["epsilon_decay_enabled"],
                "exploration_seed": scheduled_selector.seed,
                "selection_count": scheduled_selection_count,
                "full_exploration_selection_count": min(
                    scheduled_selection_count,
                    scheduled_selector.schedule.replay_warmup_decisions + 1,
                ),
                "decay_selection_count": max(
                    0,
                    scheduled_selection_count
                    - scheduled_selector.schedule.replay_warmup_decisions
                    - 1,
                ),
                "first_decay_completed_transition_count": (
                    scheduled_selector.schedule.replay_warmup_decisions + 1
                ),
                "completed_transition_count_source": (
                    schedule_contract[
                        "completed_transition_count_source"
                    ]
                ),
                "first_selection_completed_transition_count": 0,
                "last_selection_completed_transition_count": (
                    scheduled_selection_count - 1
                ),
                "epsilon_samples": observed_epsilon_samples,
                "action_tuple_counts": action_tuple_counts,
                "unique_action_tuple_count": unique_action_tuple_count,
            }
            if greedy_handoff_contract is not None:
                selector_trace["selection_count"] = sum(action_tuple_counts)
                selector_trace["scheduled_selection_count"] = (
                    scheduled_selection_count
                )
                selector_trace["post_update_greedy_selection_count"] = (
                    post_update_greedy_selection_count
                )
        elif greedy_handoff_contract is None:
            assert fixed_selector is not None
            selector_trace = {
                "name": collection["selector"],
                "epsilon": fixed_selector.epsilon,
                "epsilon_decay_enabled": collection["epsilon_decay_enabled"],
                "exploration_seed": fixed_selector.seed,
                "selection_count": sum(action_tuple_counts),
                "action_tuple_counts": action_tuple_counts,
                "unique_action_tuple_count": unique_action_tuple_count,
            }
        else:
            assert fixed_selector is not None
            selector_trace = {
                "name": collection["selector"],
                "epsilon_prefix": fixed_selector.epsilon,
                "epsilon_decay_enabled": collection["epsilon_decay_enabled"],
                "exploration_seed": fixed_selector.seed,
                "selection_count": sum(action_tuple_counts),
                "seeded_random_selection_count": seeded_random_selection_count,
                "post_update_greedy_selection_count": 1,
                "action_tuple_counts": action_tuple_counts,
                "unique_action_tuple_count": unique_action_tuple_count,
            }

        trace = {
            "schema_version": trace_schema_version,
            "contract_sha256": sha256_file(contract_path),
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
            "selector": selector_trace,
            "execution_determinism": {
                "torch_num_threads": torch.get_num_threads(),
                "torch_num_interop_threads": torch.get_num_interop_threads(),
                "deterministic_algorithms": (
                    torch.are_deterministic_algorithms_enabled()
                ),
            },
            "episodes": episodes,
            "completed_episode_count": completed_episode_count,
            "episode_reset_count": completed_episode_count,
            "truncation_events": truncation_events,
            "transitions": transitions,
            "replay": {
                "decision_count": controller.decision_count,
                "size": len(controller.replay),
                "capacity": settings.replay_capacity,
                "warmup_decisions": settings.replay_warmup_decisions,
                "below_warmup": (
                    controller.decision_count < settings.replay_warmup_decisions
                ),
                "at_warmup": (
                    controller.decision_count == settings.replay_warmup_decisions
                ),
            },
            "cutoff": {
                "transition_limit": transition_limit,
                "pending_agent_ids": list(collector.pending_agent_ids),
                "pending_decision_count": len(collector.pending_agent_ids),
                "active_episode_index": active_episode_index,
                "ended_on_unity_boundary": ended_on_unity_boundary,
            },
            "optimization": {
                "optimizer_update_count": controller.optimizer_update_count,
                "target_sync_count": controller.target_sync_count,
                "update_events": optimization_events,
                "online_before_sha256": online_before,
                "online_after_sha256": online_after,
                "target_before_sha256": target_before,
                "target_after_sha256": target_after,
                "online_weights_changed": online_before != online_after,
                "target_weights_unchanged": target_before == target_after,
            },
        }
        if post_update_greedy_handoff is not None:
            trace["post_update_greedy_handoff"] = post_update_greedy_handoff
        if scheduled_epsilon_handoff is not None:
            trace["scheduled_epsilon_handoff"] = scheduled_epsilon_handoff
        trace_path = worker_output / trace_file_name
        trace_path.write_text(
            json.dumps(trace, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return trace
    finally:
        if environment is not None:
            environment.close()


def validate_update_gate_trace(
    trace: Dict[str, Any],
    result_schema: Dict[str, Any],
    *,
    contract_path: Path,
    task_name: str,
    require_update_hashes: bool,
) -> None:
    trace_schema = {
        **result_schema["$defs"]["trace"],
        "$defs": result_schema["$defs"],
    }
    Draft202012Validator(trace_schema).validate(trace)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    collection = contract["collection"]
    optimization_contract = contract["optimization"]
    transition_limit = int(collection["transition_limit"])
    if trace["contract_sha256"] != sha256_file(contract_path):
        raise LLAPIContractError(f"Trace contract hash differs from {task_name}.")

    transitions = trace["transitions"]
    episodes = trace["episodes"]
    if len(transitions) != transition_limit:
        raise LLAPIContractError(
            f"{task_name} trace does not contain exactly "
            f"{transition_limit:,} transitions."
        )
    if [item["index"] for item in transitions] != list(range(transition_limit)):
        raise LLAPIContractError(
            f"{task_name} transition indices are not contiguous."
        )
    if [item["episode_index"] for item in episodes] != list(range(len(episodes))):
        raise LLAPIContractError(f"{task_name} episode indices are not contiguous.")
    if trace["replay"] != {
        "decision_count": transition_limit,
        "size": transition_limit,
        "capacity": int(optimization_contract["replay_capacity"]),
        "warmup_decisions": int(optimization_contract["replay_warmup_decisions"]),
        "below_warmup": False,
        "at_warmup": (
            transition_limit
            == int(optimization_contract["replay_warmup_decisions"])
        ),
    }:
        raise LLAPIContractError(
            f"{task_name} replay counters differ from its contract."
        )
    if trace["cutoff"]["pending_agent_ids"] or trace["cutoff"][
        "pending_decision_count"
    ] != 0:
        raise LLAPIContractError(
            f"{task_name} cutoff retained a pending decision."
        )

    next_start = 0
    for episode in episodes:
        if episode["transition_start_index"] != next_start:
            raise LLAPIContractError(
                f"{task_name} episode spans are not contiguous."
            )
        stop = next_start + episode["transition_count"]
        episode_transitions = transitions[next_start:stop]
        if len(episode_transitions) != episode["transition_count"]:
            raise LLAPIContractError(
                f"{task_name} episode transition span is incomplete."
            )
        if any(
            item["episode_index"] != episode["episode_index"]
            for item in episode_transitions
        ):
            raise LLAPIContractError(
                f"{task_name} assigned a transition to the wrong episode."
            )
        if [item["episode_decision_index"] for item in episode_transitions] != list(
            range(len(episode_transitions))
        ):
            raise LLAPIContractError(
                f"{task_name} episode decisions are not contiguous."
            )
        if not math.isclose(
            sum(item["reward"] for item in episode_transitions),
            episode["return"],
            rel_tol=0.0,
            abs_tol=1e-7,
        ):
            raise LLAPIContractError(
                f"{task_name} episode return differs from its rewards."
            )
        for current, following in zip(episode_transitions, episode_transitions[1:]):
            if current["next_observation_sha256"] != following[
                "observation_sha256"
            ]:
                raise LLAPIContractError(
                    f"{task_name} consecutive observations do not join."
                )
            if current["next_action_masks"] != following["action_masks"]:
                raise LLAPIContractError(
                    f"{task_name} consecutive action masks do not join."
                )
            if current["terminated"] or current["truncated"]:
                raise LLAPIContractError(
                    f"{task_name} has a nonfinal episode end flag."
                )
        final = episode_transitions[-1]
        if episode["end_kind"] == "terminal":
            if not final["terminated"] or final["truncated"]:
                raise LLAPIContractError(
                    f"{task_name} terminal episode flags are incorrect."
                )
            if final["next_action_masks"] != [
                [False, False, False],
                [False, False],
            ]:
                raise LLAPIContractError(
                    f"{task_name} terminal sentinel mask is incorrect."
                )
        elif episode["end_kind"] == "truncated":
            if final["terminated"] or not final["truncated"]:
                raise LLAPIContractError(
                    f"{task_name} truncation flags are incorrect."
                )
        elif final["terminated"] or final["truncated"]:
            raise LLAPIContractError(
                f"{task_name} cutoff was marked as an episode end."
            )
        next_start = stop
    if next_start != transition_limit:
        raise LLAPIContractError(
            f"{task_name} episode spans do not cover every transition."
        )

    for item in transitions:
        if item["terminated"] and item["truncated"]:
            raise LLAPIContractError(
                f"{task_name} transition has conflicting end flags."
            )
        for branch, action in enumerate(item["action"]):
            if item["action_masks"][branch][action]:
                raise LLAPIContractError(
                    f"{task_name} selected an unavailable action."
                )

    completed_episode_count = sum(
        1 for episode in episodes if episode["unity_episode_ended"]
    )
    if completed_episode_count != trace["completed_episode_count"]:
        raise LLAPIContractError(
            f"{task_name} completed-episode count is inconsistent."
        )
    if trace["episode_reset_count"] != completed_episode_count:
        raise LLAPIContractError(f"{task_name} reset count is inconsistent.")
    if completed_episode_count < int(collection["minimum_completed_episodes"]):
        raise LLAPIContractError(f"{task_name} did not cross an episode reset.")
    if episodes[-1]["end_kind"] == "collection_cutoff":
        if trace["cutoff"]["ended_on_unity_boundary"]:
            raise LLAPIContractError(
                f"{task_name} cutoff boundary record is inconsistent."
            )
    elif not trace["cutoff"]["ended_on_unity_boundary"]:
        raise LLAPIContractError(
            f"{task_name} cutoff omitted its Unity episode boundary."
        )

    truncations = {
        episode["episode_index"]: episode
        for episode in episodes
        if episode["end_kind"] == "truncated"
    }
    if len(trace["truncation_events"]) != len(truncations):
        raise LLAPIContractError(
            f"{task_name} truncation events do not match episode ends."
        )
    for event in trace["truncation_events"]:
        episode = truncations.get(event["episode_index"])
        if episode is None or episode["transition_count"] != event["decision_count"]:
            raise LLAPIContractError(
                f"{task_name} truncation event is not correlated."
            )
        final_index = episode["transition_start_index"] + episode[
            "transition_count"
        ] - 1
        if transitions[final_index]["next_action_masks"] != event[
            "next_action_masks"
        ]:
            raise LLAPIContractError(
                f"{task_name} truncation replay mask differs from Unity."
            )

    counts = _action_tuple_counts(transitions)
    selector = trace["selector"]
    if selector["selection_count"] != transition_limit:
        raise LLAPIContractError(
            f"{task_name} action count differs from transition count."
        )
    if selector["action_tuple_counts"] != counts:
        raise LLAPIContractError(f"{task_name} action histogram is inconsistent.")
    unique_count = sum(count > 0 for count in counts)
    if selector["unique_action_tuple_count"] != unique_count:
        raise LLAPIContractError(
            f"{task_name} unique-action count is inconsistent."
        )
    if unique_count != int(collection["minimum_unique_action_tuples"]):
        raise LLAPIContractError(
            f"{task_name} did not exercise all six action tuples."
        )

    optimization = trace["optimization"]
    if optimization["optimizer_update_count"] != int(
        optimization_contract["expected_optimizer_updates"]
    ):
        raise LLAPIContractError(
            f"{task_name} update count differs from its contract."
        )
    if optimization["target_sync_count"] != int(
        optimization_contract["expected_target_synchronizations"]
    ):
        raise LLAPIContractError(
            f"{task_name} target-sync count differs from its contract."
        )
    events = optimization["update_events"]
    expected_event_count = int(optimization_contract["expected_optimizer_updates"])
    if len(events) != expected_event_count:
        raise LLAPIContractError(
            f"{task_name} optimizer-event count differs from its contract."
        )
    first_update = int(optimization_contract["expected_first_update_decision"])
    update_interval = int(
        optimization_contract["optimizer_update_interval_decisions"]
    )
    expected_update_decisions = [
        first_update + index * update_interval
        for index in range(expected_event_count)
    ]
    if optimization_contract.get(
        "expected_update_decisions",
        expected_update_decisions,
    ) != expected_update_decisions:
        raise LLAPIContractError(
            f"{task_name} contract update decisions differ from its schedule."
        )
    if [event["decision_count"] for event in events] != expected_update_decisions:
        raise LLAPIContractError(
            f"{task_name} optimizer events are at the wrong decisions."
        )
    if [event["optimizer_update_count"] for event in events] != list(
        range(1, expected_event_count + 1)
    ):
        raise LLAPIContractError(
            f"{task_name} optimizer-event counters are not contiguous."
        )
    if any(event["replay_size"] != event["decision_count"] for event in events):
        raise LLAPIContractError(
            f"{task_name} optimizer-event replay sizes are inconsistent."
        )
    for event in events:
        if not math.isfinite(event["loss"]):
            raise LLAPIContractError(f"{task_name} loss is not finite.")
        if not math.isfinite(event["mean_absolute_td_error"]):
            raise LLAPIContractError(
                f"{task_name} mean absolute TD error is not finite."
            )
    if optimization["online_before_sha256"] != optimization[
        "target_before_sha256"
    ]:
        raise LLAPIContractError(f"{task_name} networks did not begin equal.")
    if optimization["online_before_sha256"] == optimization["online_after_sha256"]:
        raise LLAPIContractError(f"{task_name} online weights did not change.")
    if optimization["target_before_sha256"] != optimization["target_after_sha256"]:
        raise LLAPIContractError(f"{task_name} target weights changed.")
    if optimization["online_after_sha256"] == optimization["target_after_sha256"]:
        raise LLAPIContractError(
            f"{task_name} online and target networks did not diverge."
        )
    if require_update_hashes:
        update_hashes = [event["online_after_sha256"] for event in events]
        previous_hashes = [optimization["online_before_sha256"], *update_hashes[:-1]]
        if any(
            previous_hash == update_hash
            for previous_hash, update_hash in zip(previous_hashes, update_hashes)
        ):
            raise LLAPIContractError(
                f"{task_name} online weights did not change after every update."
            )
        if update_hashes[-1] != optimization["online_after_sha256"]:
            raise LLAPIContractError(
                f"{task_name} final update hash differs from its online network."
            )
