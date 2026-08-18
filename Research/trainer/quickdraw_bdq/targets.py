"""Double-DQN target construction and the registered averaged branch loss."""

from __future__ import annotations

from typing import Sequence

import torch
from torch.nn import functional as functional

from .action_space import gather_branch_values, greedy_actions


def branch_double_dqn_targets(
    rewards: torch.Tensor,
    terminated: torch.Tensor,
    truncated: torch.Tensor,
    online_next_q: Sequence[torch.Tensor],
    target_next_q: Sequence[torch.Tensor],
    next_action_masks: Sequence[torch.Tensor],
    gamma: float,
) -> torch.Tensor:
    """Build per-branch targets using online selection and target evaluation.

    True terminals do not bootstrap. Registered time-limit truncations do bootstrap
    from their final observation and legal next-action mask.
    """

    if rewards.ndim != 1 or rewards.shape[0] <= 0:
        raise ValueError("Rewards must have shape [batch].")
    if rewards.dtype != torch.float32 or not torch.isfinite(rewards).all():
        raise ValueError("Rewards must be finite float32 values.")
    if terminated.shape != rewards.shape or terminated.dtype != torch.bool:
        raise ValueError("Terminated flags must be bool with shape [batch].")
    if truncated.shape != rewards.shape or truncated.dtype != torch.bool:
        raise ValueError("Truncated flags must be bool with shape [batch].")
    if (terminated & truncated).any():
        raise ValueError("A transition cannot be both terminated and truncated.")
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("Gamma must be within [0, 1].")

    with torch.no_grad():
        selected_actions = greedy_actions(online_next_q, next_action_masks)
        evaluated_next = gather_branch_values(target_next_q, selected_actions)
        if evaluated_next.shape[0] != rewards.shape[0]:
            raise ValueError("Reward and next-Q batch sizes must match.")
        bootstrap = (~terminated).to(dtype=rewards.dtype).unsqueeze(1)
        return rewards.unsqueeze(1) + gamma * bootstrap * evaluated_next


def mean_branch_huber_loss(
    current_q: Sequence[torch.Tensor],
    actions: torch.Tensor,
    targets: torch.Tensor,
) -> torch.Tensor:
    """Average Huber loss uniformly over batch items and action branches."""

    selected = gather_branch_values(current_q, actions)
    if targets.shape != selected.shape:
        raise ValueError("Targets must have shape [batch, 2].")
    if targets.dtype != torch.float32 or not torch.isfinite(targets).all():
        raise ValueError("Targets must be finite float32 values.")
    return functional.smooth_l1_loss(selected, targets, reduction="mean", beta=1.0)
