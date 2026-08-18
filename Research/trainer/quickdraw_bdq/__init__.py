"""Pure-Python foundations for QuickDraw's Branching Double DQN trainer."""

from .action_space import (
    BRANCH_SIZES,
    COMBAT_NAMES,
    MOVEMENT_NAMES,
    branches_from_joint_indices,
    epsilon_greedy_actions,
    gather_branch_values,
    greedy_actions,
    joint_indices_from_branches,
    masked_q_values,
)
from .network import DuelingBranchingQNetwork
from .plugin import TrainerPluginBoundary, validate_installed_plugin_api
from .replay import ReplayBatch, ReplayBuffer, ReplayTransition, TorchReplayBatch
from .targets import branch_double_dqn_targets, mean_branch_huber_loss

__all__ = [
    "BRANCH_SIZES",
    "COMBAT_NAMES",
    "MOVEMENT_NAMES",
    "DuelingBranchingQNetwork",
    "ReplayBatch",
    "ReplayBuffer",
    "ReplayTransition",
    "TorchReplayBatch",
    "TrainerPluginBoundary",
    "branch_double_dqn_targets",
    "branches_from_joint_indices",
    "epsilon_greedy_actions",
    "gather_branch_values",
    "greedy_actions",
    "joint_indices_from_branches",
    "masked_q_values",
    "mean_branch_huber_loss",
    "validate_installed_plugin_api",
]
