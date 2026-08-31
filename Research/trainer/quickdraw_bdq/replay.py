"""Deterministic replay primitives for the R3A trainer foundation."""

from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

import numpy as np
import torch

from .action_space import BRANCH_SIZES
from .network import OBSERVATION_SHAPE


REPLAY_MAX_ACCOUNTED_BYTES = 4 * 1024**3
REPLAY_FRAME_ACCOUNTING_OVERHEAD_BYTES = 1024
REPLAY_METADATA_ARRAY_ACCOUNTING_OVERHEAD_BYTES = 256
REPLAY_FIXED_ACCOUNTING_OVERHEAD_BYTES = 64 * 1024
REPLAY_CHECKPOINT_STATE_VERSION = "quickdraw.bdq-replay-checkpoint-state.v1"

_FRAME_SHAPE = OBSERVATION_SHAPE[:2]
_STACK_COUNT = OBSERVATION_SHAPE[2]
_FRAME_PAYLOAD_BYTES = int(np.prod(_FRAME_SHAPE)) * np.dtype(np.float32).itemsize
_OBSERVATION_PAYLOAD_BYTES = int(np.prod(OBSERVATION_SHAPE)) * (
    np.dtype(np.float32).itemsize
)
_FRAME_REFERENCES_PER_TRANSITION = _STACK_COUNT * 2
_METADATA_ARRAY_COUNT = 10
_METADATA_PAYLOAD_BYTES_PER_TRANSITION = (
    _FRAME_REFERENCES_PER_TRANSITION * np.dtype(np.uint64).itemsize
    + len(BRANCH_SIZES) * np.dtype(np.int64).itemsize
    + np.dtype(np.float32).itemsize
    + sum(BRANCH_SIZES) * 2 * np.dtype(np.bool_).itemsize
    + 2 * np.dtype(np.bool_).itemsize
)


def _immutable_observation(value: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != OBSERVATION_SHAPE:
        raise ValueError(f"{name} must have shape {OBSERVATION_SHAPE}.")
    if array.dtype != np.float32:
        raise TypeError(f"{name} must use float32 dtype.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains a non-finite value.")
    if float(array.min()) < 0.0 or float(array.max()) > 1.0:
        raise ValueError(f"{name} must remain within [0, 1].")
    result = np.array(array, dtype=np.float32, copy=True)
    result.setflags(write=False)
    return result


def _immutable_action(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != (len(BRANCH_SIZES),):
        raise ValueError("action must have shape [2].")
    if not np.issubdtype(array.dtype, np.integer):
        raise TypeError("action must use an integer dtype.")
    result = np.array(array, dtype=np.int64, copy=True)
    for branch, branch_size in enumerate(BRANCH_SIZES):
        if result[branch] < 0 or result[branch] >= branch_size:
            raise ValueError(f"action branch {branch} contains an invalid index.")
    result.setflags(write=False)
    return result


def _immutable_masks(
    value: Sequence[np.ndarray],
    name: str,
) -> Tuple[np.ndarray, ...]:
    if len(value) != len(BRANCH_SIZES):
        raise ValueError(f"{name} must contain two branches.")
    result = []
    for branch, (mask, branch_size) in enumerate(zip(value, BRANCH_SIZES)):
        array = np.asarray(mask)
        if array.dtype != np.bool_:
            raise TypeError(f"{name} branch {branch} must use bool dtype.")
        if array.shape != (branch_size,):
            raise ValueError(
                f"{name} branch {branch} must have shape [{branch_size}]."
            )
        if array.all():
            raise ValueError(f"{name} branch {branch} masks every action.")
        copied = np.array(array, dtype=np.bool_, copy=True)
        copied.setflags(write=False)
        result.append(copied)
    return tuple(result)


@dataclass(frozen=True)
class ReplayTransition:
    observation: np.ndarray
    action: np.ndarray
    reward: float
    next_observation: np.ndarray
    action_masks: Tuple[np.ndarray, ...]
    next_action_masks: Tuple[np.ndarray, ...]
    terminated: bool
    truncated: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation",
            _immutable_observation(self.observation, "observation"),
        )
        object.__setattr__(self, "action", _immutable_action(self.action))
        if not np.isfinite(self.reward):
            raise ValueError("reward must be finite.")
        object.__setattr__(self, "reward", float(self.reward))
        object.__setattr__(
            self,
            "next_observation",
            _immutable_observation(self.next_observation, "next_observation"),
        )
        masks = _immutable_masks(self.action_masks, "action_masks")
        next_masks = _immutable_masks(self.next_action_masks, "next_action_masks")
        object.__setattr__(self, "action_masks", masks)
        object.__setattr__(self, "next_action_masks", next_masks)
        if not isinstance(self.terminated, (bool, np.bool_)):
            raise TypeError("terminated must be boolean.")
        if not isinstance(self.truncated, (bool, np.bool_)):
            raise TypeError("truncated must be boolean.")
        object.__setattr__(self, "terminated", bool(self.terminated))
        object.__setattr__(self, "truncated", bool(self.truncated))
        if self.terminated and self.truncated:
            raise ValueError("A transition cannot be both terminated and truncated.")
        for branch, action in enumerate(self.action):
            if masks[branch][action]:
                raise ValueError(f"Selected action in branch {branch} is masked.")


@dataclass(frozen=True)
class TorchReplayBatch:
    observations: torch.Tensor
    actions: torch.Tensor
    rewards: torch.Tensor
    next_observations: torch.Tensor
    action_masks: Tuple[torch.Tensor, ...]
    next_action_masks: Tuple[torch.Tensor, ...]
    terminated: torch.Tensor
    truncated: torch.Tensor
    indices: torch.Tensor


@dataclass(frozen=True)
class ReplayBatch:
    observations: np.ndarray
    actions: np.ndarray
    rewards: np.ndarray
    next_observations: np.ndarray
    action_masks: Tuple[np.ndarray, ...]
    next_action_masks: Tuple[np.ndarray, ...]
    terminated: np.ndarray
    truncated: np.ndarray
    indices: np.ndarray

    def to_torch(self, device: torch.device | str = "cpu") -> TorchReplayBatch:
        return TorchReplayBatch(
            observations=torch.as_tensor(self.observations, device=device),
            actions=torch.as_tensor(self.actions, device=device),
            rewards=torch.as_tensor(self.rewards, device=device),
            next_observations=torch.as_tensor(self.next_observations, device=device),
            action_masks=tuple(
                torch.as_tensor(mask, device=device) for mask in self.action_masks
            ),
            next_action_masks=tuple(
                torch.as_tensor(mask, device=device) for mask in self.next_action_masks
            ),
            terminated=torch.as_tensor(self.terminated, device=device),
            truncated=torch.as_tensor(self.truncated, device=device),
            indices=torch.as_tensor(self.indices, device=device),
        )


@dataclass(frozen=True)
class ReplayStorageMetrics:
    """Conservative durable-storage accounting for one replay buffer."""

    capacity: int
    size: int
    unique_frame_count: int
    frame_reference_count: int
    frame_payload_bytes: int
    metadata_payload_bytes: int
    accounted_storage_bytes: int
    max_accounted_storage_bytes: int
    remaining_accounted_storage_bytes: int
    legacy_observation_payload_bytes: int
    legacy_capacity_observation_payload_bytes: int

    def as_dict(self) -> dict[str, int]:
        return {
            "capacity": self.capacity,
            "size": self.size,
            "unique_frame_count": self.unique_frame_count,
            "frame_reference_count": self.frame_reference_count,
            "frame_payload_bytes": self.frame_payload_bytes,
            "metadata_payload_bytes": self.metadata_payload_bytes,
            "accounted_storage_bytes": self.accounted_storage_bytes,
            "max_accounted_storage_bytes": self.max_accounted_storage_bytes,
            "remaining_accounted_storage_bytes": (
                self.remaining_accounted_storage_bytes
            ),
            "legacy_observation_payload_bytes": (
                self.legacy_observation_payload_bytes
            ),
            "legacy_capacity_observation_payload_bytes": (
                self.legacy_capacity_observation_payload_bytes
            ),
        }


class ReplayBuffer:
    """Seeded ring buffer with lossless content-addressed float32 frames."""

    def __init__(
        self,
        capacity: int,
        seed: int,
        *,
        max_accounted_bytes: int = REPLAY_MAX_ACCOUNTED_BYTES,
    ) -> None:
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("Replay capacity must be positive.")
        if type(seed) is not int or seed < 0:
            raise ValueError("Replay seed must be non-negative.")
        if type(max_accounted_bytes) is not int or max_accounted_bytes <= 0:
            raise ValueError("Replay storage budget must be a positive integer.")
        self.capacity = capacity
        self.seed = seed
        self.max_accounted_bytes = max_accounted_bytes

        self._observation_frame_ids = np.empty(
            (capacity, _STACK_COUNT),
            dtype=np.uint64,
        )
        self._next_observation_frame_ids = np.empty(
            (capacity, _STACK_COUNT),
            dtype=np.uint64,
        )
        self._actions = np.empty((capacity, len(BRANCH_SIZES)), dtype=np.int64)
        self._rewards = np.empty(capacity, dtype=np.float32)
        self._action_masks = tuple(
            np.empty((capacity, branch_size), dtype=np.bool_)
            for branch_size in BRANCH_SIZES
        )
        self._next_action_masks = tuple(
            np.empty((capacity, branch_size), dtype=np.bool_)
            for branch_size in BRANCH_SIZES
        )
        self._terminated = np.empty(capacity, dtype=np.bool_)
        self._truncated = np.empty(capacity, dtype=np.bool_)

        self._frame_id_by_bytes: dict[bytes, int] = {}
        self._frame_bytes_by_id: dict[int, bytes] = {}
        self._frame_refcounts: dict[int, int] = {}
        self._next_frame_id = 0
        self._next_index = 0
        self._size = 0
        self._random = np.random.default_rng(seed)

        if self._metadata_accounted_bytes() > self.max_accounted_bytes:
            raise ValueError(
                "Replay metadata exceeds the configured storage budget."
            )

    def __len__(self) -> int:
        return self._size

    @property
    def cursor(self) -> int:
        """Return the next ring write position."""
        return int(self._next_index)

    @property
    def storage_metrics(self) -> ReplayStorageMetrics:
        unique_frame_count = len(self._frame_bytes_by_id)
        accounted = self._accounted_bytes_for_unique_frames(unique_frame_count)
        return ReplayStorageMetrics(
            capacity=self.capacity,
            size=self._size,
            unique_frame_count=unique_frame_count,
            frame_reference_count=self._size * _FRAME_REFERENCES_PER_TRANSITION,
            frame_payload_bytes=unique_frame_count * _FRAME_PAYLOAD_BYTES,
            metadata_payload_bytes=self._metadata_payload_bytes(),
            accounted_storage_bytes=accounted,
            max_accounted_storage_bytes=self.max_accounted_bytes,
            remaining_accounted_storage_bytes=(
                self.max_accounted_bytes - accounted
            ),
            legacy_observation_payload_bytes=(
                self._size * _OBSERVATION_PAYLOAD_BYTES * 2
            ),
            legacy_capacity_observation_payload_bytes=(
                self.capacity * _OBSERVATION_PAYLOAD_BYTES * 2
            ),
        )

    @classmethod
    def projected_accounted_bytes(
        cls,
        capacity: int,
        unique_frame_count: int,
    ) -> int:
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("Replay capacity must be positive.")
        if type(unique_frame_count) is not int or unique_frame_count < 0:
            raise ValueError("Unique frame count must be a non-negative integer.")
        return (
            capacity * _METADATA_PAYLOAD_BYTES_PER_TRANSITION
            + _METADATA_ARRAY_COUNT
            * REPLAY_METADATA_ARRAY_ACCOUNTING_OVERHEAD_BYTES
            + REPLAY_FIXED_ACCOUNTING_OVERHEAD_BYTES
            + unique_frame_count
            * (_FRAME_PAYLOAD_BYTES + REPLAY_FRAME_ACCOUNTING_OVERHEAD_BYTES)
        )

    def add(self, transition: ReplayTransition) -> None:
        if not isinstance(transition, ReplayTransition):
            raise TypeError("ReplayBuffer accepts ReplayTransition instances only.")

        old_frame_ids: list[int] = []
        if self._size == self.capacity:
            old_frame_ids = [
                int(value)
                for value in self._observation_frame_ids[self._next_index]
            ] + [
                int(value)
                for value in self._next_observation_frame_ids[self._next_index]
            ]

        acquired_frame_ids: list[int] = []
        try:
            observation_frame_ids = self._acquire_observation_frames(
                transition.observation,
                acquired_frame_ids,
            )
            next_observation_frame_ids = self._acquire_observation_frames(
                transition.next_observation,
                acquired_frame_ids,
            )
            projected_unique_frame_count = self._projected_unique_frame_count(
                old_frame_ids
            )
            projected_bytes = self._accounted_bytes_for_unique_frames(
                projected_unique_frame_count
            )
            if projected_bytes > self.max_accounted_bytes:
                raise MemoryError(
                    "Replay storage budget exceeded: projected "
                    f"{projected_bytes} bytes is above "
                    f"{self.max_accounted_bytes} bytes."
                )
        except Exception:
            for frame_id in reversed(acquired_frame_ids):
                self._release_frame(frame_id)
            raise

        for frame_id in old_frame_ids:
            self._release_frame(frame_id)

        self._observation_frame_ids[self._next_index] = observation_frame_ids
        self._next_observation_frame_ids[self._next_index] = (
            next_observation_frame_ids
        )
        self._actions[self._next_index] = transition.action
        self._rewards[self._next_index] = transition.reward
        for branch in range(len(BRANCH_SIZES)):
            self._action_masks[branch][self._next_index] = (
                transition.action_masks[branch]
            )
            self._next_action_masks[branch][self._next_index] = (
                transition.next_action_masks[branch]
            )
        self._terminated[self._next_index] = transition.terminated
        self._truncated[self._next_index] = transition.truncated
        self._next_index = (self._next_index + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size: int) -> ReplayBatch:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("Batch size must be positive.")
        if batch_size > self._size:
            raise ValueError("Cannot sample more transitions than replay contains.")
        indices = self._random.choice(self._size, size=batch_size, replace=False)
        return ReplayBatch(
            observations=self._reconstruct_observations(
                self._observation_frame_ids[indices]
            ),
            actions=np.array(self._actions[indices], dtype=np.int64, copy=True),
            rewards=np.array(self._rewards[indices], dtype=np.float32, copy=True),
            next_observations=self._reconstruct_observations(
                self._next_observation_frame_ids[indices]
            ),
            action_masks=tuple(
                np.array(mask[indices], dtype=np.bool_, copy=True)
                for mask in self._action_masks
            ),
            next_action_masks=tuple(
                np.array(mask[indices], dtype=np.bool_, copy=True)
                for mask in self._next_action_masks
            ),
            terminated=np.array(
                self._terminated[indices],
                dtype=np.bool_,
                copy=True,
            ),
            truncated=np.array(
                self._truncated[indices],
                dtype=np.bool_,
                copy=True,
            ),
            indices=np.asarray(indices, dtype=np.int64),
        )

    def export_checkpoint_state(self) -> Dict[str, Any]:
        """Return an exact raw snapshot of the live buffer state.

        The snapshot holds only live ring rows, live frames, the sampling
        bit-generator state, and the durable accounting metrics. The unwritten
        tail of a partially filled buffer is intentionally excluded.
        """

        rows = self._size
        return {
            "state_version": REPLAY_CHECKPOINT_STATE_VERSION,
            "capacity": self.capacity,
            "seed": self.seed,
            "max_accounted_bytes": self.max_accounted_bytes,
            "next_frame_id": int(self._next_frame_id),
            "cursor": int(self._next_index),
            "size": int(self._size),
            "frame_bytes_by_id": {
                int(frame_id): bytes(frame_bytes)
                for frame_id, frame_bytes in self._frame_bytes_by_id.items()
            },
            "frame_refcounts": {
                int(frame_id): int(count)
                for frame_id, count in self._frame_refcounts.items()
            },
            "observation_frame_ids": np.array(
                self._observation_frame_ids[:rows], copy=True
            ),
            "next_observation_frame_ids": np.array(
                self._next_observation_frame_ids[:rows], copy=True
            ),
            "actions": np.array(self._actions[:rows], copy=True),
            "rewards": np.array(self._rewards[:rows], copy=True),
            "action_masks": tuple(
                np.array(mask[:rows], copy=True)
                for mask in self._action_masks
            ),
            "next_action_masks": tuple(
                np.array(mask[:rows], copy=True)
                for mask in self._next_action_masks
            ),
            "terminated": np.array(self._terminated[:rows], copy=True),
            "truncated": np.array(self._truncated[:rows], copy=True),
            "replay_bit_generator_state": copy.deepcopy(
                self._random.bit_generator.state
            ),
            "storage_metrics": self.storage_metrics.as_dict(),
        }

    def import_checkpoint_state(self, state: Dict[str, Any]) -> None:
        """Validate a snapshot fully, then replace this buffer's live state.

        Apply this to a freshly constructed buffer whose capacity, seed, and
        storage budget match the snapshot. Every structural, accounting, and
        interning invariant is validated before any mutation.
        """

        if not isinstance(state, dict):
            raise ValueError("Replay checkpoint state must be a mapping.")
        required = {
            "state_version",
            "capacity",
            "seed",
            "max_accounted_bytes",
            "next_frame_id",
            "cursor",
            "size",
            "frame_bytes_by_id",
            "frame_refcounts",
            "observation_frame_ids",
            "next_observation_frame_ids",
            "actions",
            "rewards",
            "action_masks",
            "next_action_masks",
            "terminated",
            "truncated",
            "replay_bit_generator_state",
            "storage_metrics",
        }
        missing = sorted(required - set(state))
        if missing:
            raise ValueError(f"Replay checkpoint state is incomplete: {missing}.")
        if state["state_version"] != REPLAY_CHECKPOINT_STATE_VERSION:
            raise ValueError("Replay checkpoint state version is incompatible.")
        for key in ("capacity", "seed", "max_accounted_bytes"):
            if type(state[key]) is not int or state[key] != getattr(self, key):
                raise ValueError(f"Replay checkpoint {key} is incompatible.")

        size = state["size"]
        cursor = state["cursor"]
        next_frame_id = state["next_frame_id"]
        if type(size) is not int or not 0 <= size <= self.capacity:
            raise ValueError("Replay checkpoint size is out of range.")
        if type(cursor) is not int or not 0 <= cursor < self.capacity:
            raise ValueError("Replay checkpoint cursor is out of range.")
        if size < self.capacity and cursor != size:
            raise ValueError("Replay checkpoint cursor disagrees with its size.")
        if type(next_frame_id) is not int or next_frame_id < 0:
            raise ValueError("Replay checkpoint frame-id counter is invalid.")

        frame_bytes_by_id = state["frame_bytes_by_id"]
        frame_refcounts = state["frame_refcounts"]
        if not isinstance(frame_bytes_by_id, dict) or not isinstance(
            frame_refcounts, dict
        ):
            raise ValueError("Replay checkpoint frame stores must be mappings.")
        if set(frame_refcounts) != set(frame_bytes_by_id):
            raise ValueError("Replay checkpoint frame refcounts are incomplete.")
        bytes_by_frame: Dict[int, bytes] = {}
        for frame_id, frame_bytes in frame_bytes_by_id.items():
            if type(frame_id) is not int or not 0 <= frame_id < next_frame_id:
                raise ValueError("Replay checkpoint frame id is out of range.")
            if not isinstance(frame_bytes, (bytes, bytearray)):
                raise ValueError("Replay checkpoint frame payload is not bytes.")
            if len(frame_bytes) != _FRAME_PAYLOAD_BYTES:
                raise ValueError("Replay checkpoint frame payload size is wrong.")
            if frame_id in bytes_by_frame:
                raise ValueError("Replay checkpoint frame ids are not unique.")
            bytes_by_frame[frame_id] = bytes(frame_bytes)
            count = frame_refcounts[frame_id]
            if type(count) is not int or count < 1:
                raise ValueError("Replay checkpoint frame refcount is invalid.")
        if next_frame_id < len(bytes_by_frame):
            raise ValueError("Replay checkpoint frame-id counter is inconsistent.")

        def _validated_column(
            value: Any,
            name: str,
            dtype: np.dtype,
            shape: Tuple[int, ...],
        ) -> np.ndarray:
            if not isinstance(value, np.ndarray):
                raise ValueError(f"Replay checkpoint {name} is not an array.")
            if value.dtype != dtype or tuple(value.shape) != shape:
                raise ValueError(
                    f"Replay checkpoint {name} dtype or shape is wrong."
                )
            return np.array(value, dtype=dtype, copy=True)

        observation_frame_ids = _validated_column(
            state["observation_frame_ids"],
            "observation_frame_ids",
            np.dtype(np.uint64),
            (size, _STACK_COUNT),
        )
        next_observation_frame_ids = _validated_column(
            state["next_observation_frame_ids"],
            "next_observation_frame_ids",
            np.dtype(np.uint64),
            (size, _STACK_COUNT),
        )
        actions = _validated_column(
            state["actions"],
            "actions",
            np.dtype(np.int64),
            (size, len(BRANCH_SIZES)),
        )
        if size and (
            (actions < 0).any()
            or any(
                (actions[:, branch] >= branch_size).any()
                for branch, branch_size in enumerate(BRANCH_SIZES)
            )
        ):
            raise ValueError("Replay checkpoint actions are out of range.")
        rewards = _validated_column(
            state["rewards"],
            "rewards",
            np.dtype(np.float32),
            (size,),
        )
        if size and not np.isfinite(rewards).all():
            raise ValueError("Replay checkpoint rewards are not finite.")

        def _validated_masks(value: Any, name: str) -> Tuple[np.ndarray, ...]:
            if not isinstance(value, (tuple, list)) or len(value) != len(
                BRANCH_SIZES
            ):
                raise ValueError(f"Replay checkpoint {name} has wrong branches.")
            validated = tuple(
                _validated_column(
                    mask,
                    f"{name} branch {branch}",
                    np.dtype(np.bool_),
                    (size, branch_size),
                )
                for branch, (mask, branch_size) in enumerate(
                    zip(value, BRANCH_SIZES)
                )
            )
            if size and any(mask.all(axis=1).any() for mask in validated):
                raise ValueError(f"Replay checkpoint {name} masks every action.")
            return validated

        action_masks = _validated_masks(state["action_masks"], "action_masks")
        next_action_masks = _validated_masks(
            state["next_action_masks"], "next_action_masks"
        )
        if size:
            rows = np.arange(size)
            for branch in range(len(BRANCH_SIZES)):
                if action_masks[branch][rows, actions[:, branch]].any():
                    raise ValueError(
                        "Replay checkpoint actions are masked by their own row."
                    )
        terminated = _validated_column(
            state["terminated"],
            "terminated",
            np.dtype(np.bool_),
            (size,),
        )
        truncated = _validated_column(
            state["truncated"],
            "truncated",
            np.dtype(np.bool_),
            (size,),
        )
        if size and (terminated & truncated).any():
            raise ValueError(
                "Replay checkpoint rows are both terminated and truncated."
            )

        referenced: Dict[int, int] = {}
        for column in (observation_frame_ids, next_observation_frame_ids):
            for frame_id in column.reshape(-1):
                key = int(frame_id)
                if key not in bytes_by_frame:
                    raise ValueError(
                        "Replay checkpoint references a missing frame."
                    )
                referenced[key] = referenced.get(key, 0) + 1
        if referenced != {int(k): int(v) for k, v in frame_refcounts.items()}:
            raise ValueError(
                "Replay checkpoint frame refcounts disagree with its rows."
            )

        interned_bytes: Dict[bytes, int] = {}
        for frame_id, frame_bytes in bytes_by_frame.items():
            if frame_bytes in interned_bytes:
                raise ValueError(
                    "Replay checkpoint frames are not content-unique."
                )
            interned_bytes[frame_bytes] = frame_id

        bit_generator_state = state["replay_bit_generator_state"]
        if not isinstance(bit_generator_state, dict):
            raise ValueError("Replay checkpoint RNG state is not a mapping.")
        if bit_generator_state.get("bit_generator") != type(
            self._random.bit_generator
        ).__name__:
            raise ValueError(
                "Replay checkpoint RNG bit generator is incompatible."
            )
        if set(bit_generator_state) != {
            "bit_generator",
            "state",
            "has_uint32",
            "uinteger",
        }:
            raise ValueError(
                "Replay checkpoint RNG state fields are wrong."
            )
        inner_state = bit_generator_state["state"]
        if not isinstance(inner_state, dict) or set(inner_state) != {
            "state",
            "inc",
        }:
            raise ValueError(
                "Replay checkpoint RNG inner state is malformed."
            )
        for key, value in inner_state.items():
            if type(value) is not int or value < 0:
                raise ValueError(
                    "Replay checkpoint RNG inner state is invalid."
                )
        for key in ("has_uint32", "uinteger"):
            value = bit_generator_state[key]
            if type(value) is not int or value < 0:
                raise ValueError(
                    "Replay checkpoint RNG buffering state is invalid."
                )

        metrics = state["storage_metrics"]
        if not isinstance(metrics, dict):
            raise ValueError("Replay checkpoint storage metrics are missing.")
        unique_frame_count = len(bytes_by_frame)
        expected_metrics = ReplayStorageMetrics(
            capacity=self.capacity,
            size=size,
            unique_frame_count=unique_frame_count,
            frame_reference_count=size * _FRAME_REFERENCES_PER_TRANSITION,
            frame_payload_bytes=unique_frame_count * _FRAME_PAYLOAD_BYTES,
            metadata_payload_bytes=(
                self.capacity * _METADATA_PAYLOAD_BYTES_PER_TRANSITION
            ),
            accounted_storage_bytes=ReplayBuffer.projected_accounted_bytes(
                self.capacity, unique_frame_count
            ),
            max_accounted_storage_bytes=self.max_accounted_bytes,
            remaining_accounted_storage_bytes=(
                self.max_accounted_bytes
                - ReplayBuffer.projected_accounted_bytes(
                    self.capacity, unique_frame_count
                )
            ),
            legacy_observation_payload_bytes=(
                size * _OBSERVATION_PAYLOAD_BYTES * 2
            ),
            legacy_capacity_observation_payload_bytes=(
                self.capacity * _OBSERVATION_PAYLOAD_BYTES * 2
            ),
        )
        if metrics != expected_metrics.as_dict():
            raise ValueError(
                "Replay checkpoint storage metrics disagree with its state."
            )

        self._observation_frame_ids[:size] = observation_frame_ids
        self._next_observation_frame_ids[:size] = next_observation_frame_ids
        self._actions[:size] = actions
        self._rewards[:size] = rewards
        for branch in range(len(BRANCH_SIZES)):
            self._action_masks[branch][:size] = action_masks[branch]
            self._next_action_masks[branch][:size] = next_action_masks[branch]
        self._terminated[:size] = terminated
        self._truncated[:size] = truncated
        self._frame_bytes_by_id = bytes_by_frame
        self._frame_id_by_bytes = interned_bytes
        self._frame_refcounts = {
            int(k): int(v) for k, v in frame_refcounts.items()
        }
        self._next_frame_id = next_frame_id
        self._next_index = cursor
        self._size = size
        self._random.bit_generator.state = copy.deepcopy(bit_generator_state)
        if self.storage_metrics.as_dict() != metrics:
            raise RuntimeError(
                "Restored replay accounting failed its post-restore audit."
            )

    def _metadata_arrays(self) -> tuple[np.ndarray, ...]:
        return (
            self._observation_frame_ids,
            self._next_observation_frame_ids,
            self._actions,
            self._rewards,
            *self._action_masks,
            *self._next_action_masks,
            self._terminated,
            self._truncated,
        )

    def _metadata_payload_bytes(self) -> int:
        return sum(array.nbytes for array in self._metadata_arrays())

    def _metadata_accounted_bytes(self) -> int:
        return (
            self._metadata_payload_bytes()
            + len(self._metadata_arrays())
            * REPLAY_METADATA_ARRAY_ACCOUNTING_OVERHEAD_BYTES
            + REPLAY_FIXED_ACCOUNTING_OVERHEAD_BYTES
        )

    def _accounted_bytes_for_unique_frames(self, unique_frame_count: int) -> int:
        return self._metadata_accounted_bytes() + unique_frame_count * (
            _FRAME_PAYLOAD_BYTES + REPLAY_FRAME_ACCOUNTING_OVERHEAD_BYTES
        )

    def _acquire_observation_frames(
        self,
        observation: np.ndarray,
        acquired_frame_ids: list[int],
    ) -> np.ndarray:
        frame_ids = np.empty(_STACK_COUNT, dtype=np.uint64)
        for frame_index in range(_STACK_COUNT):
            frame_id = self._acquire_frame(observation[:, :, frame_index])
            acquired_frame_ids.append(frame_id)
            frame_ids[frame_index] = frame_id
        return frame_ids

    def _acquire_frame(self, frame: np.ndarray) -> int:
        frame_bytes = np.ascontiguousarray(frame, dtype=np.float32).tobytes(
            order="C"
        )
        frame_id = self._frame_id_by_bytes.get(frame_bytes)
        if frame_id is not None:
            self._frame_refcounts[frame_id] += 1
            return frame_id

        frame_id = self._next_frame_id
        self._next_frame_id += 1
        self._frame_id_by_bytes[frame_bytes] = frame_id
        self._frame_bytes_by_id[frame_id] = frame_bytes
        self._frame_refcounts[frame_id] = 1
        return frame_id

    def _release_frame(self, frame_id: int) -> None:
        refcount = self._frame_refcounts.get(frame_id)
        if refcount is None or refcount <= 0:
            raise RuntimeError("Replay frame reference accounting is corrupt.")
        if refcount > 1:
            self._frame_refcounts[frame_id] = refcount - 1
            return

        frame_bytes = self._frame_bytes_by_id.pop(frame_id)
        self._frame_refcounts.pop(frame_id)
        removed_frame_id = self._frame_id_by_bytes.pop(frame_bytes, None)
        if removed_frame_id != frame_id:
            raise RuntimeError("Replay frame interning index is corrupt.")

    def _projected_unique_frame_count(self, old_frame_ids: Sequence[int]) -> int:
        old_counts: dict[int, int] = {}
        for frame_id in old_frame_ids:
            old_counts[frame_id] = old_counts.get(frame_id, 0) + 1
        reclaimable = sum(
            self._frame_refcounts.get(frame_id) == old_count
            for frame_id, old_count in old_counts.items()
        )
        return len(self._frame_bytes_by_id) - reclaimable

    def _reconstruct_observations(self, frame_ids: np.ndarray) -> np.ndarray:
        observations = np.empty(
            (len(frame_ids), *OBSERVATION_SHAPE),
            dtype=np.float32,
        )
        for row, observation_frame_ids in enumerate(frame_ids):
            for frame_index, raw_frame_id in enumerate(observation_frame_ids):
                frame_id = int(raw_frame_id)
                frame_bytes = self._frame_bytes_by_id.get(frame_id)
                if frame_bytes is None:
                    raise RuntimeError(
                        f"Replay frame {frame_id} is missing from storage."
                    )
                observations[row, :, :, frame_index] = np.frombuffer(
                    frame_bytes,
                    dtype=np.float32,
                ).reshape(_FRAME_SHAPE)
        return observations
