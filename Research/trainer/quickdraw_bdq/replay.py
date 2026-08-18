"""Deterministic replay primitives for the R3A trainer foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
import torch

from .action_space import BRANCH_SIZES
from .network import OBSERVATION_SHAPE


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


class ReplayBuffer:
    """Fixed-capacity ring buffer with a private seeded NumPy generator."""

    def __init__(self, capacity: int, seed: int) -> None:
        if capacity <= 0:
            raise ValueError("Replay capacity must be positive.")
        if seed < 0:
            raise ValueError("Replay seed must be non-negative.")
        self.capacity = capacity
        self.seed = seed
        self._storage: List[ReplayTransition | None] = [None] * capacity
        self._next_index = 0
        self._size = 0
        self._random = np.random.default_rng(seed)

    def __len__(self) -> int:
        return self._size

    def add(self, transition: ReplayTransition) -> None:
        if not isinstance(transition, ReplayTransition):
            raise TypeError("ReplayBuffer accepts ReplayTransition instances only.")
        self._storage[self._next_index] = transition
        self._next_index = (self._next_index + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size: int) -> ReplayBatch:
        if batch_size <= 0:
            raise ValueError("Batch size must be positive.")
        if batch_size > self._size:
            raise ValueError("Cannot sample more transitions than replay contains.")
        indices = self._random.choice(self._size, size=batch_size, replace=False)
        transitions = [self._storage[int(index)] for index in indices]
        if any(transition is None for transition in transitions):
            raise RuntimeError("Replay storage contains an uninitialized slot.")
        concrete = [transition for transition in transitions if transition is not None]
        return ReplayBatch(
            observations=np.stack([item.observation for item in concrete]),
            actions=np.stack([item.action for item in concrete]),
            rewards=np.asarray([item.reward for item in concrete], dtype=np.float32),
            next_observations=np.stack(
                [item.next_observation for item in concrete]
            ),
            action_masks=tuple(
                np.stack([item.action_masks[branch] for item in concrete])
                for branch in range(len(BRANCH_SIZES))
            ),
            next_action_masks=tuple(
                np.stack([item.next_action_masks[branch] for item in concrete])
                for branch in range(len(BRANCH_SIZES))
            ),
            terminated=np.asarray(
                [item.terminated for item in concrete],
                dtype=np.bool_,
            ),
            truncated=np.asarray(
                [item.truncated for item in concrete],
                dtype=np.bool_,
            ),
            indices=np.asarray(indices, dtype=np.int64),
        )
