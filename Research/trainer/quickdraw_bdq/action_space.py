"""Basic action-branch mapping, masking, and selection primitives."""

from __future__ import annotations

from typing import Sequence, Tuple

import torch


BRANCH_SIZES: Tuple[int, int] = (3, 2)
MOVEMENT_NAMES: Tuple[str, ...] = ("Stay", "Left", "Right")
COMBAT_NAMES: Tuple[str, ...] = ("Idle", "Shoot")


def _validate_q_values(q_values: Sequence[torch.Tensor]) -> Tuple[int, torch.device]:
    if len(q_values) != len(BRANCH_SIZES):
        raise ValueError(f"Expected {len(BRANCH_SIZES)} Q branches.")

    batch_size = -1
    device: torch.device | None = None
    for branch, (values, branch_size) in enumerate(zip(q_values, BRANCH_SIZES)):
        if values.ndim != 2 or values.shape[1] != branch_size:
            raise ValueError(
                f"Q branch {branch} must have shape [batch, {branch_size}]."
            )
        if values.dtype != torch.float32:
            raise TypeError(f"Q branch {branch} must use float32 dtype.")
        if not torch.isfinite(values).all():
            raise ValueError(f"Q branch {branch} contains a non-finite value.")
        if batch_size < 0:
            batch_size = values.shape[0]
            device = values.device
        elif values.shape[0] != batch_size or values.device != device:
            raise ValueError("All Q branches must share batch size and device.")

    if batch_size <= 0 or device is None:
        raise ValueError("Q branches require a non-empty batch.")
    return batch_size, device


def _validated_masks(
    masks: Sequence[torch.Tensor],
    batch_size: int,
    device: torch.device,
) -> Tuple[torch.Tensor, ...]:
    if len(masks) != len(BRANCH_SIZES):
        raise ValueError(f"Expected {len(BRANCH_SIZES)} action-mask branches.")

    validated = []
    for branch, (mask, branch_size) in enumerate(zip(masks, BRANCH_SIZES)):
        if mask.dtype != torch.bool:
            raise TypeError(f"Action-mask branch {branch} must have bool dtype.")
        if mask.shape != (batch_size, branch_size):
            raise ValueError(
                f"Action-mask branch {branch} must have shape "
                f"[{batch_size}, {branch_size}]."
            )
        if mask.device != device:
            raise ValueError("Action masks and Q values must share a device.")
        if mask.all(dim=1).any():
            raise ValueError(f"Action-mask branch {branch} masks every action.")
        validated.append(mask)
    return tuple(validated)


def masked_q_values(
    q_values: Sequence[torch.Tensor],
    unavailable_masks: Sequence[torch.Tensor],
) -> Tuple[torch.Tensor, ...]:
    """Return branch Q-values with mechanically unavailable actions set to -inf."""

    batch_size, device = _validate_q_values(q_values)
    masks = _validated_masks(unavailable_masks, batch_size, device)
    return tuple(
        values.masked_fill(mask, float("-inf"))
        for values, mask in zip(q_values, masks)
    )


def greedy_actions(
    q_values: Sequence[torch.Tensor],
    unavailable_masks: Sequence[torch.Tensor],
) -> torch.Tensor:
    """Select one legal greedy action per branch, returning shape [batch, 2]."""

    masked = masked_q_values(q_values, unavailable_masks)
    return torch.stack([values.argmax(dim=1) for values in masked], dim=1)


def epsilon_greedy_actions(
    q_values: Sequence[torch.Tensor],
    unavailable_masks: Sequence[torch.Tensor],
    epsilon: float,
    generator: torch.Generator,
) -> torch.Tensor:
    """Select deterministic seeded epsilon-greedy actions from legal choices only."""

    if not 0.0 <= epsilon <= 1.0:
        raise ValueError("Epsilon must be within [0, 1].")

    batch_size, device = _validate_q_values(q_values)
    masks = _validated_masks(unavailable_masks, batch_size, device)
    actions = greedy_actions(q_values, masks)

    for row in range(batch_size):
        for branch, mask in enumerate(masks):
            explore = torch.rand((), generator=generator, device=device) < epsilon
            if not bool(explore.item()):
                continue
            available = torch.nonzero(~mask[row], as_tuple=False).flatten()
            choice = torch.randint(
                available.numel(),
                (),
                generator=generator,
                device=device,
            )
            actions[row, branch] = available[choice]
    return actions


def _validate_actions(actions: torch.Tensor, batch_size: int | None = None) -> None:
    if actions.ndim != 2 or actions.shape[1] != len(BRANCH_SIZES):
        raise ValueError("Actions must have shape [batch, 2].")
    if batch_size is not None and actions.shape[0] != batch_size:
        raise ValueError("Action batch size does not match Q-value batch size.")
    if actions.dtype not in (torch.int32, torch.int64):
        raise TypeError("Actions must use an integer dtype.")
    for branch, branch_size in enumerate(BRANCH_SIZES):
        branch_actions = actions[:, branch]
        if ((branch_actions < 0) | (branch_actions >= branch_size)).any():
            raise ValueError(f"Action branch {branch} contains an invalid index.")


def joint_indices_from_branches(actions: torch.Tensor) -> torch.Tensor:
    """Map [movement, combat] to row-major joint indices 0 through 5."""

    _validate_actions(actions)
    return actions[:, 0] * BRANCH_SIZES[1] + actions[:, 1]


def branches_from_joint_indices(joint_indices: torch.Tensor) -> torch.Tensor:
    """Map row-major joint indices 0 through 5 back to [movement, combat]."""

    if joint_indices.ndim != 1:
        raise ValueError("Joint indices must have shape [batch].")
    if joint_indices.dtype not in (torch.int32, torch.int64):
        raise TypeError("Joint indices must use an integer dtype.")
    joint_size = BRANCH_SIZES[0] * BRANCH_SIZES[1]
    if ((joint_indices < 0) | (joint_indices >= joint_size)).any():
        raise ValueError("Joint action index is outside [0, 5].")
    movement = torch.div(joint_indices, BRANCH_SIZES[1], rounding_mode="floor")
    combat = joint_indices.remainder(BRANCH_SIZES[1])
    return torch.stack((movement, combat), dim=1)


def gather_branch_values(
    q_values: Sequence[torch.Tensor],
    actions: torch.Tensor,
) -> torch.Tensor:
    """Gather selected Q-values into a tensor with shape [batch, 2]."""

    batch_size, device = _validate_q_values(q_values)
    _validate_actions(actions, batch_size)
    if actions.device != device:
        raise ValueError("Actions and Q values must share a device.")
    return torch.stack(
        [
            values.gather(1, actions[:, branch].long().unsqueeze(1)).squeeze(1)
            for branch, values in enumerate(q_values)
        ],
        dim=1,
    )
