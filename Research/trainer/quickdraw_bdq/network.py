"""Registered visual encoder and dueling branch heads for Research_Basic."""

from __future__ import annotations

from typing import Tuple

import torch
from torch import nn

from .action_space import BRANCH_SIZES


OBSERVATION_SHAPE: Tuple[int, int, int] = (84, 84, 4)


class DuelingBranchingQNetwork(nn.Module):
    """Nature-style visual encoder with one mean-centered head per action branch."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(4, 32, kernel_size=8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(64 * 7 * 7, 512),
            nn.ReLU(),
        )
        self.value_head = nn.Linear(512, 1)
        self.advantage_heads = nn.ModuleList(
            nn.Linear(512, branch_size) for branch_size in BRANCH_SIZES
        )

    @staticmethod
    def _validate_observations(observations: torch.Tensor) -> None:
        if observations.ndim != 4 or tuple(observations.shape[1:]) != OBSERVATION_SHAPE:
            raise ValueError("Observations must have shape [batch, 84, 84, 4].")
        if observations.shape[0] <= 0:
            raise ValueError("Observations require a non-empty batch.")
        if observations.dtype != torch.float32:
            raise TypeError("Observations must use float32 dtype.")
        if not torch.isfinite(observations).all():
            raise ValueError("Observations contain a non-finite value.")
        if (observations < 0.0).any() or (observations > 1.0).any():
            raise ValueError("Observations must remain within [0, 1].")

    def forward_components(
        self,
        observations: torch.Tensor,
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, ...]]:
        """Return scalar values and raw per-branch advantages."""

        self._validate_observations(observations)
        chw = observations.permute(0, 3, 1, 2).contiguous()
        representation = self.encoder(chw)
        value = self.value_head(representation)
        advantages = tuple(head(representation) for head in self.advantage_heads)
        return value, advantages

    def forward(self, observations: torch.Tensor) -> Tuple[torch.Tensor, ...]:
        value, advantages = self.forward_components(observations)
        return tuple(
            value + advantage - advantage.mean(dim=1, keepdim=True)
            for advantage in advantages
        )
