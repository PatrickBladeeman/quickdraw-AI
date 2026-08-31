"""Deterministic BDQ optimizer scheduling shared by synthetic and LLAPI tests."""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass

import torch

from .action_space import gather_branch_values
from .network import DuelingBranchingQNetwork
from .replay import ReplayBuffer, ReplayTransition
from .targets import branch_double_dqn_targets, mean_branch_huber_loss


CONTROLLER_CHECKPOINT_STATE_VERSION = "quickdraw.bdq-controller-checkpoint-state.v1"


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

    def export_checkpoint_state(self) -> dict:
        """Return an exact raw snapshot of the controller's persistent state."""

        return {
            "state_version": CONTROLLER_CHECKPOINT_STATE_VERSION,
            "seed": self.seed,
            "settings": asdict(self.settings),
            "decision_count": int(self._decision_count),
            "optimizer_update_count": int(self._optimizer_update_count),
            "target_sync_count": int(self._target_sync_count),
            "online_state_dict": {
                name: value.detach().cpu().clone()
                for name, value in self._online_network.state_dict().items()
            },
            "target_state_dict": {
                name: value.detach().cpu().clone()
                for name, value in self._target_network.state_dict().items()
            },
            "optimizer_state_dict": copy.deepcopy(
                self._optimizer.state_dict()
            ),
        }

    def load_checkpoint_state(self, state: dict) -> None:
        """Validate a snapshot fully, then apply it to this fresh controller.

        Apply this to a newly constructed controller whose seed and settings
        already match. Network, optimizer, and counter payloads are validated
        before any parameter is mutated.
        """

        if not isinstance(state, dict):
            raise ValueError("Controller checkpoint state must be a mapping.")
        required = {
            "state_version",
            "seed",
            "settings",
            "decision_count",
            "optimizer_update_count",
            "target_sync_count",
            "online_state_dict",
            "target_state_dict",
            "optimizer_state_dict",
        }
        missing = sorted(required - set(state))
        if missing:
            raise ValueError(f"Controller checkpoint state is incomplete: {missing}.")
        if state["state_version"] != CONTROLLER_CHECKPOINT_STATE_VERSION:
            raise ValueError("Controller checkpoint state version is incompatible.")
        if type(state["seed"]) is not int or state["seed"] != self.seed:
            raise ValueError("Controller checkpoint seed is incompatible.")
        if state["settings"] != asdict(self.settings):
            raise ValueError("Controller checkpoint settings are incompatible.")
        for key in (
            "decision_count",
            "optimizer_update_count",
            "target_sync_count",
        ):
            if type(state[key]) is not int or state[key] < 0:
                raise ValueError(f"Controller checkpoint {key} is invalid.")

        def _validated_network_state(
            value: dict,
            name: str,
            network: DuelingBranchingQNetwork,
        ) -> dict:
            if not isinstance(value, dict):
                raise ValueError(f"Controller checkpoint {name} is not a mapping.")
            reference = network.state_dict()
            if value.keys() != reference.keys():
                raise ValueError(f"Controller checkpoint {name} keys are wrong.")
            for parameter_name, tensor in value.items():
                if not isinstance(tensor, torch.Tensor):
                    raise ValueError(
                        f"Controller checkpoint {name} entry is not a tensor."
                    )
                expected = reference[parameter_name]
                if (
                    tensor.device.type != "cpu"
                    or tensor.dtype != expected.dtype
                    or tuple(tensor.shape) != tuple(expected.shape)
                ):
                    raise ValueError(
                        f"Controller checkpoint {name} entry {parameter_name} "
                        "is incompatible."
                    )
            return value

        online_state_dict = _validated_network_state(
            state["online_state_dict"],
            "online_state_dict",
            self._online_network,
        )
        target_state_dict = _validated_network_state(
            state["target_state_dict"],
            "target_state_dict",
            self._target_network,
        )

        optimizer_state_dict = state["optimizer_state_dict"]
        if not isinstance(optimizer_state_dict, dict) or set(
            optimizer_state_dict
        ) != {"state", "param_groups"}:
            raise ValueError("Controller checkpoint optimizer payload is malformed.")
        current_optimizer_state = self._optimizer.state_dict()
        if not isinstance(optimizer_state_dict["state"], dict):
            raise ValueError("Controller checkpoint optimizer state is malformed.")
        parameter_ids = [
            parameter_id
            for group in current_optimizer_state["param_groups"]
            for parameter_id in group["params"]
        ]
        if state["optimizer_update_count"] > 0 and set(
            optimizer_state_dict["state"]
        ) != set(parameter_ids):
            raise ValueError(
                "Controller checkpoint optimizer state is incomplete."
            )
        if state["optimizer_update_count"] == 0 and optimizer_state_dict[
            "state"
        ]:
            raise ValueError(
                "Controller checkpoint optimizer state is inconsistent."
            )
        for parameter_id, entry in optimizer_state_dict["state"].items():
            if type(parameter_id) is not int or parameter_id not in parameter_ids:
                raise ValueError(
                    "Controller checkpoint optimizer parameter id is unknown."
                )
            if not isinstance(entry, dict) or set(entry) != {
                "step",
                "exp_avg",
                "exp_avg_sq",
            }:
                raise ValueError(
                    "Controller checkpoint optimizer state entry is malformed."
                )
            expected_shape = tuple(
                self._online_network.parameters()
            )[parameter_id].shape
            for key in ("exp_avg", "exp_avg_sq"):
                tensor = entry[key]
                if (
                    not isinstance(tensor, torch.Tensor)
                    or tensor.device.type != "cpu"
                    or tensor.dtype != torch.float32
                    or tuple(tensor.shape) != expected_shape
                ):
                    raise ValueError(
                        f"Controller checkpoint optimizer {key} is incompatible."
                    )
            step = entry["step"]
            if (
                not isinstance(step, torch.Tensor)
                or step.device.type != "cpu"
                or step.dtype != torch.float32
                or step.dim() != 0
            ):
                raise ValueError(
                    "Controller checkpoint optimizer step is incompatible."
                )
            step_value = float(step.item())
            if (
                not math.isfinite(step_value)
                or not 0.0 <= step_value <= float(state["optimizer_update_count"])
            ):
                raise ValueError(
                    "Controller checkpoint optimizer step is out of range."
                )
        if len(optimizer_state_dict["param_groups"]) != len(
            current_optimizer_state["param_groups"]
        ):
            raise ValueError(
                "Controller checkpoint optimizer groups are incompatible."
            )
        for group, current_group in zip(
            optimizer_state_dict["param_groups"],
            current_optimizer_state["param_groups"],
        ):
            if not isinstance(group, dict) or group.get("params") != current_group[
                "params"
            ]:
                raise ValueError(
                    "Controller checkpoint optimizer group parameters are wrong."
                )
            if {
                key: value
                for key, value in group.items()
                if key != "params"
            } != {
                key: value
                for key, value in current_group.items()
                if key != "params"
            }:
                raise ValueError(
                    "Controller checkpoint optimizer group hyperparameters "
                    "are incompatible."
                )

        self._online_network.load_state_dict(online_state_dict, strict=True)
        self._target_network.load_state_dict(target_state_dict, strict=True)
        self._optimizer.load_state_dict(optimizer_state_dict)
        self._decision_count = state["decision_count"]
        self._optimizer_update_count = state["optimizer_update_count"]
        self._target_sync_count = state["target_sync_count"]

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
