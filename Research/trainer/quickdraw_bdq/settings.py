"""ML-Agents hyperparameter settings for the registered R3B plugin."""

from __future__ import annotations

import attr
from mlagents.trainers.settings import OffPolicyHyperparamSettings, ScheduleType

from .optimizer import BDQOptimizationSettings


@attr.s(auto_attribs=True)
class QuickDrawBDQSettings(OffPolicyHyperparamSettings):
    batch_size: int = 64
    buffer_size: int = 100_000
    buffer_init_steps: int = 10_000
    learning_rate: float = 1.0e-4
    learning_rate_schedule: ScheduleType = ScheduleType.CONSTANT
    steps_per_update: float = 4.0
    save_replay_buffer: bool = False
    reward_signal_steps_per_update: float = 4.0
    gamma: float = 0.99
    hard_target_sync_interval_optimizer_updates: int = 10_000
    epsilon_start: float = 1.0
    epsilon_end: float = 0.1
    exploratory_evaluation_epsilon: float = 0.05
    final_evaluation_epsilon: float = 0.0

    def to_optimization_settings(self) -> BDQOptimizationSettings:
        if not float(self.steps_per_update).is_integer():
            raise ValueError("steps_per_update must be a positive whole number.")
        return BDQOptimizationSettings(
            replay_capacity=self.buffer_size,
            replay_warmup_decisions=self.buffer_init_steps,
            batch_size=self.batch_size,
            gamma=self.gamma,
            learning_rate=self.learning_rate,
            optimizer_update_interval_decisions=int(self.steps_per_update),
            hard_target_sync_interval_optimizer_updates=(
                self.hard_target_sync_interval_optimizer_updates
            ),
        )
