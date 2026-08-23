"""Direct ML-Agents LLAPI collection primitives for the Basic BDQ environment."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

import numpy as np
import torch
from mlagents_envs.base_env import BehaviorSpec, DecisionSteps
from mlagents_envs.side_channel.incoming_message import IncomingMessage
from mlagents_envs.side_channel.side_channel import SideChannel

from .action_space import BRANCH_SIZES, epsilon_greedy_actions, greedy_actions
from .network import DuelingBranchingQNetwork, OBSERVATION_SHAPE
from .optimizer import BDQOptimizerController, OptimizationStepResult
from .replay import ReplayTransition


BASIC_BEHAVIOR_NAME = "QuickDrawResearchBasic"
TRUNCATION_MASK_SCHEMA_VERSION = "quickdraw.basic-truncation-mask.v1"
TRUNCATION_MASK_MESSAGE_TYPE = "truncation_mask"
TRUNCATION_MASK_CHANNEL_UUID = "0541088f-93b9-4299-8c9e-af7431da553a"
DECISION_LIMIT_REASON = "decision_limit"
DECISION_LIMIT = 300
SCENARIO_SEED = 31001
MINIMUM_SLOT = -4
MAXIMUM_SLOT = 4


class LLAPIContractError(RuntimeError):
    """Raised when live LLAPI data differs from the direct-collection contract."""


def validate_observation(value: np.ndarray, name: str) -> np.ndarray:
    observation = np.asarray(value)
    if observation.shape != OBSERVATION_SHAPE:
        raise LLAPIContractError(
            f"{name} must have shape {OBSERVATION_SHAPE}, got {observation.shape}."
        )
    if observation.dtype != np.float32:
        raise LLAPIContractError(f"{name} must use float32 dtype.")
    if not np.isfinite(observation).all():
        raise LLAPIContractError(f"{name} contains a non-finite value.")
    if float(observation.min()) < 0.0 or float(observation.max()) > 1.0:
        raise LLAPIContractError(f"{name} must remain within [0, 1].")
    return observation


def observation_sha256(value: np.ndarray) -> str:
    observation = validate_observation(value, "observation")
    contiguous = np.ascontiguousarray(observation, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()


def validate_action_masks(
    value: Sequence[np.ndarray] | Sequence[Sequence[bool]] | None,
    name: str,
) -> Tuple[np.ndarray, ...]:
    if value is None or len(value) != len(BRANCH_SIZES):
        raise LLAPIContractError(f"{name} must contain two branches.")

    result = []
    for branch, (raw_mask, branch_size) in enumerate(zip(value, BRANCH_SIZES)):
        mask = np.asarray(raw_mask)
        if mask.dtype != np.bool_:
            raise LLAPIContractError(
                f"{name} branch {branch} must use bool dtype."
            )
        if mask.shape != (branch_size,):
            raise LLAPIContractError(
                f"{name} branch {branch} must have shape [{branch_size}]."
            )
        if mask.all():
            raise LLAPIContractError(f"{name} branch {branch} masks every action.")
        copied = np.array(mask, dtype=np.bool_, copy=True)
        copied.setflags(write=False)
        result.append(copied)
    return tuple(result)


def read_action_masks(
    decision_steps: DecisionSteps,
    row: int,
) -> Tuple[np.ndarray, ...]:
    if decision_steps.action_mask is None:
        raise LLAPIContractError("Basic DecisionSteps omitted discrete action masks.")
    if row < 0 or row >= len(decision_steps):
        raise LLAPIContractError(f"DecisionSteps row {row} is out of range.")
    return validate_action_masks(
        [branch[row] for branch in decision_steps.action_mask],
        "decision action_masks",
    )


def validate_basic_behavior_spec(behavior_spec: BehaviorSpec) -> None:
    if len(behavior_spec.observation_specs) != 1:
        raise LLAPIContractError(
            "Direct BDQ collection requires one observation and no privileged input."
        )
    if tuple(behavior_spec.observation_specs[0].shape) != OBSERVATION_SHAPE:
        raise LLAPIContractError(
            f"Direct BDQ collection requires HWC shape {OBSERVATION_SHAPE}."
        )
    action_spec = behavior_spec.action_spec
    if action_spec.continuous_size != 0:
        raise LLAPIContractError("Direct BDQ collection forbids continuous actions.")
    if tuple(action_spec.discrete_branches) != BRANCH_SIZES:
        raise LLAPIContractError(
            f"Direct BDQ collection requires discrete branches {BRANCH_SIZES}."
        )


def network_sha256(network: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in network.state_dict().items():
        array = np.ascontiguousarray(value.detach().cpu().numpy())
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(json.dumps(list(array.shape), separators=(",", ":")).encode())
        digest.update(b"\0")
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


class GreedyBDQActionSelector:
    """Select legal branch actions directly from the unchanged online network."""

    def __init__(self, online_network: DuelingBranchingQNetwork) -> None:
        self._online_network = online_network

    def select(
        self,
        observation: np.ndarray,
        action_masks: Sequence[np.ndarray],
    ) -> np.ndarray:
        validated_observation = validate_observation(observation, "policy observation")
        validated_masks = validate_action_masks(action_masks, "policy action_masks")
        self._online_network.eval()
        with torch.no_grad():
            q_values = self._online_network(
                torch.as_tensor(validated_observation[None, ...], dtype=torch.float32)
            )
            selected = greedy_actions(
                q_values,
                tuple(
                    torch.tensor(mask[None, ...], dtype=torch.bool)
                    for mask in validated_masks
                ),
            )
        return selected[0].to(dtype=torch.int64).cpu().numpy()


class SeededEpsilonGreedyBDQActionSelector:
    """Select legal branch actions with one fixed epsilon and RNG seed."""

    def __init__(
        self,
        online_network: DuelingBranchingQNetwork,
        *,
        epsilon: float,
        seed: int,
    ) -> None:
        if isinstance(epsilon, bool) or not isinstance(epsilon, (int, float)):
            raise ValueError("Epsilon must be a real number within [0, 1].")
        if not 0.0 <= float(epsilon) <= 1.0:
            raise ValueError("Epsilon must be within [0, 1].")
        if type(seed) is not int or seed < 0:
            raise ValueError("Exploration seed must be a non-negative integer.")
        self._online_network = online_network
        self._epsilon = float(epsilon)
        self._seed = seed
        self._generator = torch.Generator(device="cpu").manual_seed(seed)

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @property
    def seed(self) -> int:
        return self._seed

    def select(
        self,
        observation: np.ndarray,
        action_masks: Sequence[np.ndarray],
    ) -> np.ndarray:
        validated_observation = validate_observation(observation, "policy observation")
        validated_masks = validate_action_masks(action_masks, "policy action_masks")
        self._online_network.eval()
        with torch.no_grad():
            q_values = self._online_network(
                torch.as_tensor(validated_observation[None, ...], dtype=torch.float32)
            )
            selected = epsilon_greedy_actions(
                q_values,
                tuple(
                    torch.tensor(mask[None, ...], dtype=torch.bool)
                    for mask in validated_masks
                ),
                self._epsilon,
                self._generator,
            )
        return selected[0].to(dtype=torch.int64).cpu().numpy()


@dataclass(frozen=True)
class PendingDecision:
    observation: np.ndarray
    action: np.ndarray
    action_masks: Tuple[np.ndarray, ...]

    @classmethod
    def create(
        cls,
        observation: np.ndarray,
        action: np.ndarray,
        action_masks: Sequence[np.ndarray],
    ) -> "PendingDecision":
        validated_observation = validate_observation(observation, "observation")
        copied_observation = np.array(
            validated_observation,
            dtype=np.float32,
            copy=True,
        )
        copied_observation.setflags(write=False)
        masks = validate_action_masks(action_masks, "action_masks")
        action_array = np.asarray(action)
        if action_array.shape != (len(BRANCH_SIZES),):
            raise LLAPIContractError("action must have shape [2].")
        if not np.issubdtype(action_array.dtype, np.integer):
            raise LLAPIContractError("action must use an integer dtype.")
        copied_action = np.array(action_array, dtype=np.int64, copy=True)
        for branch, branch_size in enumerate(BRANCH_SIZES):
            selected = int(copied_action[branch])
            if selected < 0 or selected >= branch_size:
                raise LLAPIContractError(
                    f"action branch {branch} contains an invalid index."
                )
            if masks[branch][selected]:
                raise LLAPIContractError(
                    f"action branch {branch} selected an unavailable action."
                )
        copied_action.setflags(write=False)
        return cls(copied_observation, copied_action, masks)


class DirectReplayCollector:
    """Hold one pending decision per agent and complete it on the next LLAPI step."""

    def __init__(self, optimizer_controller: BDQOptimizerController) -> None:
        self._optimizer_controller = optimizer_controller
        self._pending: Dict[int, PendingDecision] = {}

    @property
    def pending_agent_ids(self) -> Tuple[int, ...]:
        return tuple(sorted(self._pending))

    def begin(
        self,
        agent_id: int,
        observation: np.ndarray,
        action: np.ndarray,
        action_masks: Sequence[np.ndarray],
    ) -> None:
        if type(agent_id) is not int or agent_id < 0:
            raise LLAPIContractError("agent_id must be a non-negative integer.")
        if agent_id in self._pending:
            raise LLAPIContractError(f"Agent {agent_id} already has a pending decision.")
        self._pending[agent_id] = PendingDecision.create(
            observation,
            action,
            action_masks,
        )

    def complete(
        self,
        agent_id: int,
        reward: float,
        next_observation: np.ndarray,
        next_action_masks: Sequence[np.ndarray],
        *,
        terminated: bool,
        truncated: bool,
    ) -> Tuple[ReplayTransition, OptimizationStepResult]:
        pending = self._pending.pop(agent_id, None)
        if pending is None:
            raise LLAPIContractError(f"Agent {agent_id} has no pending decision.")
        transition = ReplayTransition(
            observation=pending.observation,
            action=pending.action,
            reward=reward,
            next_observation=next_observation,
            action_masks=pending.action_masks,
            next_action_masks=tuple(next_action_masks),
            terminated=terminated,
            truncated=truncated,
        )
        result = self._optimizer_controller.record_transition(transition)
        return transition, result


@dataclass(frozen=True)
class TruncationMaskEvent:
    scenario_seed: int
    episode_index: int
    decision_count: int
    reason: str
    position_slot: int
    action_masks: Tuple[np.ndarray, ...]


class BasicTruncationMaskSideChannel(SideChannel):
    """Receive the authoritative continuation mask for one interrupted Basic state."""

    _FIELDS = {
        "schema_version",
        "message_type",
        "scenario_seed",
        "episode_index",
        "decision_count",
        "reason",
        "position_slot",
        "movement_unavailable",
        "combat_unavailable",
    }

    def __init__(self) -> None:
        super().__init__(uuid.UUID(TRUNCATION_MASK_CHANNEL_UUID))
        self._events: Dict[Tuple[int, int], TruncationMaskEvent] = {}

    def on_message_received(self, message: IncomingMessage) -> None:
        self.accept_json(message.read_string())

    def accept_json(self, raw_json: str) -> None:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as error:
            raise LLAPIContractError("Truncation-mask message is not valid JSON.") from error
        if not isinstance(payload, dict) or set(payload) != self._FIELDS:
            fields = sorted(payload) if isinstance(payload, dict) else []
            raise LLAPIContractError(
                f"Unexpected truncation-mask message fields: {fields}."
            )
        if payload["schema_version"] != TRUNCATION_MASK_SCHEMA_VERSION:
            raise LLAPIContractError("Unexpected truncation-mask schema version.")
        if payload["message_type"] != TRUNCATION_MASK_MESSAGE_TYPE:
            raise LLAPIContractError("Unexpected truncation-mask message type.")
        if payload["reason"] != DECISION_LIMIT_REASON:
            raise LLAPIContractError("Unexpected truncation reason.")

        integer_fields = (
            "scenario_seed",
            "episode_index",
            "decision_count",
            "position_slot",
        )
        if any(type(payload[field]) is not int for field in integer_fields):
            raise LLAPIContractError("Truncation-mask integer fields must be integers.")
        if payload["scenario_seed"] != SCENARIO_SEED:
            raise LLAPIContractError("Unexpected truncation-mask scenario seed.")
        if payload["episode_index"] < 0:
            raise LLAPIContractError("Truncation-mask episode index must be non-negative.")
        if payload["decision_count"] != DECISION_LIMIT:
            raise LLAPIContractError("Truncation mask arrived at the wrong decision count.")
        if not MINIMUM_SLOT <= payload["position_slot"] <= MAXIMUM_SLOT:
            raise LLAPIContractError("Truncation-mask position slot is out of range.")

        masks = validate_action_masks(
            (
                payload["movement_unavailable"],
                payload["combat_unavailable"],
            ),
            "truncation next_action_masks",
        )
        expected_movement = np.asarray(
            [
                False,
                payload["position_slot"] == MINIMUM_SLOT,
                payload["position_slot"] == MAXIMUM_SLOT,
            ],
            dtype=np.bool_,
        )
        if not np.array_equal(masks[0], expected_movement):
            raise LLAPIContractError(
                "Truncation movement mask disagrees with its reported final slot."
            )
        if masks[1].any():
            raise LLAPIContractError("Basic truncation combat actions must remain available.")

        event = TruncationMaskEvent(
            scenario_seed=payload["scenario_seed"],
            episode_index=payload["episode_index"],
            decision_count=payload["decision_count"],
            reason=payload["reason"],
            position_slot=payload["position_slot"],
            action_masks=masks,
        )
        key = (event.episode_index, event.decision_count)
        if key in self._events:
            raise LLAPIContractError(f"Duplicate truncation-mask event {key}.")
        self._events[key] = event

    def take(self, episode_index: int, decision_count: int) -> TruncationMaskEvent:
        key = (episode_index, decision_count)
        event = self._events.pop(key, None)
        if event is None:
            raise LLAPIContractError(f"Missing authoritative truncation mask {key}.")
        return event

    def assert_empty(self) -> None:
        if self._events:
            raise LLAPIContractError(
                f"Unused truncation-mask events remain: {sorted(self._events)}."
            )
