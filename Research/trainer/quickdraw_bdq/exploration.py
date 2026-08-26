"""Deterministic exploration schedules for QuickDraw BDQ training."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LinearEpsilonSchedule:
    """Derive training epsilon from the completed-transition count only."""

    replay_warmup_decisions: int = 10_000
    decay_decisions: int = 100_000
    initial_epsilon: float = 1.0
    final_epsilon: float = 0.1

    def __post_init__(self) -> None:
        if (
            type(self.replay_warmup_decisions) is not int
            or self.replay_warmup_decisions < 0
        ):
            raise ValueError(
                "replay_warmup_decisions must be a non-negative integer."
            )
        if type(self.decay_decisions) is not int or self.decay_decisions <= 0:
            raise ValueError("decay_decisions must be a positive integer.")

        epsilon_values = {
            "initial_epsilon": self.initial_epsilon,
            "final_epsilon": self.final_epsilon,
        }
        for name, value in epsilon_values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite real number.")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be a finite real number.")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be within [0, 1].")
        if float(self.final_epsilon) >= float(self.initial_epsilon):
            raise ValueError("final_epsilon must be lower than initial_epsilon.")

    @property
    def decay_start_completed_transitions(self) -> int:
        return self.replay_warmup_decisions

    @property
    def decay_end_completed_transitions(self) -> int:
        return self.replay_warmup_decisions + self.decay_decisions

    def epsilon_at(self, completed_transition_count: int) -> float:
        """Return clamped linear epsilon for one completed-transition count."""

        if type(completed_transition_count) is not int:
            raise ValueError(
                "completed_transition_count must be a non-negative integer."
            )
        if completed_transition_count < 0:
            raise ValueError(
                "completed_transition_count must be a non-negative integer."
            )
        if completed_transition_count <= self.replay_warmup_decisions:
            return float(self.initial_epsilon)
        if completed_transition_count >= self.decay_end_completed_transitions:
            return float(self.final_epsilon)

        decay_progress = (
            completed_transition_count - self.replay_warmup_decisions
        ) / self.decay_decisions
        return float(
            self.initial_epsilon
            + (self.final_epsilon - self.initial_epsilon) * decay_progress
        )
