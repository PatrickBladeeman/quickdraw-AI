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
from .llapi import (
    BASIC_BEHAVIOR_NAME,
    BasicTruncationMaskSideChannel,
    DirectReplayCollector,
    GreedyBDQActionSelector,
    LLAPIContractError,
    PendingDecision,
    TruncationMaskEvent,
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
from .replay import ReplayBatch, ReplayBuffer, ReplayTransition, TorchReplayBatch
from .targets import branch_double_dqn_targets, mean_branch_huber_loss

__all__ = [
    "BRANCH_SIZES",
    "COMBAT_NAMES",
    "MOVEMENT_NAMES",
    "DuelingBranchingQNetwork",
    "BDQOptimizationSettings",
    "BDQOptimizerController",
    "OptimizationStepResult",
    "ReplayBatch",
    "ReplayBuffer",
    "ReplayTransition",
    "TorchReplayBatch",
    "BASIC_BEHAVIOR_NAME",
    "BasicTruncationMaskSideChannel",
    "DirectReplayCollector",
    "GreedyBDQActionSelector",
    "LLAPIContractError",
    "PendingDecision",
    "TruncationMaskEvent",
    "branch_double_dqn_targets",
    "branches_from_joint_indices",
    "epsilon_greedy_actions",
    "gather_branch_values",
    "greedy_actions",
    "joint_indices_from_branches",
    "masked_q_values",
    "mean_branch_huber_loss",
    "network_sha256",
    "observation_sha256",
    "read_action_masks",
    "validate_action_masks",
    "validate_basic_behavior_spec",
    "validate_observation",
]
