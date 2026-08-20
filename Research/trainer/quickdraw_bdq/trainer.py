"""Concrete ML-Agents trainer shell for the bounded R3B optimizer smoke."""

from __future__ import annotations

from typing import NoReturn

from mlagents.trainers.behavior_id_utils import BehaviorIdentifiers
from mlagents.trainers.policy import Policy
from mlagents.trainers.settings import TrainerSettings
from mlagents.trainers.trainer import Trainer
from mlagents_envs.base_env import BehaviorSpec

from .optimizer import BDQOptimizerController
from .settings import QuickDrawBDQSettings


TRAINER_NAME = "quickdraw_bdq"


class R3BRolloutUnavailableError(RuntimeError):
    """Raised when code attempts rollout behavior outside the approved R3B slice."""


class QuickDrawBDQTrainer(Trainer):
    """Factory-compatible trainer shell with rollout deliberately unavailable."""

    def __init__(
        self,
        behavior_name: str,
        reward_buff_cap: int,
        trainer_settings: TrainerSettings,
        training: bool,
        load: bool,
        seed: int,
        artifact_path: str,
    ) -> None:
        if load:
            raise R3BRolloutUnavailableError(
                "R3B does not implement checkpoint loading or resume."
            )
        if trainer_settings.trainer_type != TRAINER_NAME:
            raise ValueError(f"trainer_type must be {TRAINER_NAME}.")
        if not isinstance(trainer_settings.hyperparameters, QuickDrawBDQSettings):
            raise TypeError(
                "quickdraw_bdq requires QuickDrawBDQSettings hyperparameters."
            )

        super().__init__(
            behavior_name,
            trainer_settings,
            training,
            load,
            artifact_path,
            reward_buff_cap,
        )
        self.seed = seed
        self._optimizer_controller = BDQOptimizerController(
            seed,
            trainer_settings.hyperparameters.to_optimization_settings(),
        )

    @property
    def optimizer_controller(self) -> BDQOptimizerController:
        return self._optimizer_controller

    @staticmethod
    def get_trainer_name() -> str:
        return TRAINER_NAME

    @staticmethod
    def _rollout_unavailable(operation: str) -> NoReturn:
        raise R3BRolloutUnavailableError(
            f"{operation} requires a later Unity rollout slice; R3B is synthetic only."
        )

    def save_model(self) -> None:
        self._rollout_unavailable("Model saving")

    def end_episode(self) -> None:
        self._rollout_unavailable("Episode handling")

    def create_policy(
        self,
        parsed_behavior_id: BehaviorIdentifiers,
        behavior_spec: BehaviorSpec,
    ) -> Policy:
        self._rollout_unavailable("Policy creation")

    def add_policy(
        self,
        parsed_behavior_id: BehaviorIdentifiers,
        policy: Policy,
    ) -> None:
        self._rollout_unavailable("Policy registration")

    def advance(self) -> None:
        self._rollout_unavailable("Trajectory advancement")
