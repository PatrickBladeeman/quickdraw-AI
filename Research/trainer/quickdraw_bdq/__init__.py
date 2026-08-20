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
from .optimizer import (
    BDQOptimizationSettings,
    BDQOptimizerController,
    OptimizationStepResult,
)
from .plugin import (
    RegisteredTrainerPluginBoundary,
    TrainerPluginBoundary,
    register_trainer_types,
    validate_installed_plugin_api,
    validate_registered_plugin_api,
)
from .replay import ReplayBatch, ReplayBuffer, ReplayTransition, TorchReplayBatch
from .settings import QuickDrawBDQSettings
from .targets import branch_double_dqn_targets, mean_branch_huber_loss
from .trainer import QuickDrawBDQTrainer, R3BRolloutUnavailableError

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
    "QuickDrawBDQSettings",
    "QuickDrawBDQTrainer",
    "R3BRolloutUnavailableError",
    "RegisteredTrainerPluginBoundary",
    "TrainerPluginBoundary",
    "branch_double_dqn_targets",
    "branches_from_joint_indices",
    "epsilon_greedy_actions",
    "gather_branch_values",
    "greedy_actions",
    "joint_indices_from_branches",
    "masked_q_values",
    "mean_branch_huber_loss",
    "register_trainer_types",
    "validate_installed_plugin_api",
    "validate_registered_plugin_api",
]
