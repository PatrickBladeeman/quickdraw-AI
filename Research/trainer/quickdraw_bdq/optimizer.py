"""Deterministic BDQ optimizer scheduling shared by synthetic and LLAPI tests."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import torch

from .action_space import gather_branch_values
from .network import DuelingBranchingQNetwork
from .replay import ReplayBuffer, ReplayTransition
from .targets import branch_double_dqn_targets, mean_branch_huber_loss


@dataclass(frozen=True)
class BDQOptimizationSettings:
    replay_capacity: int = 100_000
    replay_warmup_decisions: int = 10_000
    batch_size: int = 64
    gamma: float = 0.99
    learning_rate: float = 1.0e-4
    optimizer_update_interval_decisions: int = 4
    hard_target_sync_interval_optimizer_updates: int = 10_000
    device: str = "cpu"

    def __post_init__(self) -> None:
        integer_fields = {
            "replay_capacity": self.replay_capacity,
            "replay_warmup_decisions": self.replay_warmup_decisions,
            "batch_size": self.batch_size,
            "optimizer_update_interval_decisions": (
                self.optimizer_update_interval_decisions
            ),
            "hard_target_sync_interval_optimizer_updates": (
                self.hard_target_sync_interval_optimizer_updates
            ),
        }
        for name, value in integer_fields.items():
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")

        if self.replay_capacity < self.replay_warmup_decisions:
            raise ValueError("Replay capacity must be at least the warmup size.")
        if self.replay_warmup_decisions < self.batch_size:
            raise ValueError("Replay warmup must be at least the batch size.")
        if not math.isfinite(self.gamma) or not 0.0 <= self.gamma <= 1.0:
            raise ValueError("Gamma must be finite and within [0, 1].")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0.0:
            raise ValueError("Learning rate must be finite and positive.")
        if self.device != "cpu":
            raise ValueError("The current optimizer contract permits the CPU device only.")


@dataclass(frozen=True)
class OptimizationStepResult:
    decision_count: int
    replay_size: int
    optimizer_update_count: int
    target_sync_count: int
    updated: bool
    target_synced: bool
    loss: float | None
    mean_absolute_td_error: float | None


class BDQOptimizerController:
    """Own online/target networks, replay, Adam, and registered update counters."""

    def __init__(
        self,
        seed: int,
        settings: BDQOptimizationSettings | None = None,
    ) -> None:
        if type(seed) is not int or seed < 0:
            raise ValueError("Optimizer seed must be a non-negative integer.")

        self.seed = seed
        self.settings = settings or BDQOptimizationSettings()
        self._device = torch.device(self.settings.device)

        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self._online_network = DuelingBranchingQNetwork().to(self._device)
        self._target_network = copy.deepcopy(self._online_network).to(self._device)
        self._target_network.eval()
        for parameter in self._target_network.parameters():
            parameter.requires_grad_(False)

        self._optimizer = torch.optim.Adam(
            self._online_network.parameters(),
            lr=self.settings.learning_rate,
        )
        self._replay = ReplayBuffer(self.settings.replay_capacity, seed)
        self._decision_count = 0
        self._optimizer_update_count = 0
        self._target_sync_count = 0

    @property
    def online_network(self) -> DuelingBranchingQNetwork:
        return self._online_network

    @property
    def target_network(self) -> DuelingBranchingQNetwork:
        return self._target_network

    @property
    def replay(self) -> ReplayBuffer:
        return self._replay

    @property
    def decision_count(self) -> int:
        return self._decision_count

    @property
    def optimizer_update_count(self) -> int:
        return self._optimizer_update_count

    @property
    def target_sync_count(self) -> int:
        return self._target_sync_count

    def record_transition(
        self,
        transition: ReplayTransition,
    ) -> OptimizationStepResult:
        """Store one decision transition and run one update when its gate opens."""

        self._replay.add(transition)
        self._decision_count += 1
        if not self._is_update_due():
            return self._result(updated=False, target_synced=False)
        return self._optimize_once()

    def _is_update_due(self) -> bool:
        return (
            self._decision_count >= self.settings.replay_warmup_decisions
            and len(self._replay) >= self.settings.replay_warmup_decisions
            and self._decision_count
            % self.settings.optimizer_update_interval_decisions
            == 0
        )

    def _optimize_once(self) -> OptimizationStepResult:
        batch = self._replay.sample(self.settings.batch_size).to_torch(self._device)
        self._online_network.train()
        current_q = self._online_network(batch.observations)

        with torch.no_grad():
            online_next_q = self._online_network(batch.next_observations)
            target_next_q = self._target_network(batch.next_observations)
            targets = branch_double_dqn_targets(
                batch.rewards,
                batch.terminated,
                batch.truncated,
                online_next_q,
                target_next_q,
                batch.next_action_masks,
                gamma=self.settings.gamma,
            )
            selected = gather_branch_values(current_q, batch.actions)
            mean_absolute_td_error = torch.mean(torch.abs(targets - selected))

        loss = mean_branch_huber_loss(current_q, batch.actions, targets)
        self._optimizer.zero_grad(set_to_none=True)
        loss.backward()
        self._optimizer.step()
        self._optimizer_update_count += 1

        target_synced = (
            self._optimizer_update_count
            % self.settings.hard_target_sync_interval_optimizer_updates
            == 0
        )
        if target_synced:
            self._target_network.load_state_dict(self._online_network.state_dict())
            self._target_sync_count += 1

        return self._result(
            updated=True,
            target_synced=target_synced,
            loss=float(loss.detach().item()),
            mean_absolute_td_error=float(mean_absolute_td_error.item()),
        )

    def _result(
        self,
        updated: bool,
        target_synced: bool,
        loss: float | None = None,
        mean_absolute_td_error: float | None = None,
    ) -> OptimizationStepResult:
        return OptimizationStepResult(
            decision_count=self._decision_count,
            replay_size=len(self._replay),
            optimizer_update_count=self._optimizer_update_count,
            target_sync_count=self._target_sync_count,
            updated=updated,
            target_synced=target_synced,
            loss=loss,
            mean_absolute_td_error=mean_absolute_td_error,
        )
