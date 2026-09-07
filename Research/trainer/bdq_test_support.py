"""Small synthetic fixtures; expected values never come from production builders."""

from __future__ import annotations

from typing import Any, NamedTuple, Sequence

import numpy as np

from quickdraw_bdq import (
    BDQOptimizationSettings,
    BDQOptimizerController,
    DirectReplayCollector,
    network_sha256,
)
from quickdraw_bdq.update_gate import _complete_gate_transition


class ExpectedUpdate(NamedTuple):
    decision_count: int
    online_sha256: str
    loss: float
    mean_absolute_td_error: float


# Independent accepted values from R3K/R3M/R3O, in update order.
REGISTERED_UPDATES = (
    ExpectedUpdate(
        10_000,
        "7dd2365b5e219af10aeb4fabb5191df873762fcea6765cb50f83d41525279c8e",
        0.01628389209508896,
        0.06243317946791649,
    ),
    ExpectedUpdate(
        10_004,
        "6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471",
        0.014819225296378136,
        0.06711231172084808,
    ),
    ExpectedUpdate(
        10_008,
        "4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b",
        0.008735351264476776,
        0.06769348680973053,
    ),
    ExpectedUpdate(
        10_012,
        "a8356df1531b99a42966578c6fd784cd384c8bcd3d3c3092124df13b2587268f",
        0.0085072573274374,
        0.06249994412064552,
    ),
    ExpectedUpdate(
        10_016,
        "8275fed953fb594fea0e88c50da15a862e1db6a3e296dd953dd10e048c2c3cbe",
        0.00121649622451514,
        0.03924498334527016,
    ),
)
FROZEN_TARGET = "b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb"


def update_events(expected: Sequence[ExpectedUpdate]) -> list[dict[str, Any]]:
    return [
        {
            "decision_count": update.decision_count,
            "replay_size": update.decision_count,
            "optimizer_update_count": index,
            "target_sync_count": 0,
            "updated": True,
            "target_synced": False,
            "loss": update.loss,
            "mean_absolute_td_error": update.mean_absolute_td_error,
            "online_after_sha256": update.online_sha256,
        }
        for index, update in enumerate(expected, start=1)
    ]


def scheduled_selector(schedule: dict[str, Any]) -> dict[str, Any]:
    """Copy explicit selector expectations from a frozen contract into a fixture."""
    return {
        **{
            key: schedule[key]
            for key in (
                "selection_count",
                "full_exploration_selection_count",
                "decay_selection_count",
                "first_decay_completed_transition_count",
                "last_selection_completed_transition_count",
                "completed_transition_count_source",
            )
        },
        "epsilon_samples": [
            {"completed_transition_count": count, "epsilon": epsilon}
            for count, epsilon in zip(
                schedule["trace_sample_completed_transition_counts"],
                schedule["trace_sample_epsilons"],
            )
        ],
    }


def synthetic_task_trace(
    expected_updates: Sequence[ExpectedUpdate],
    selector: dict[str, Any],
    *,
    decision_count: int,
    target_sha256: str,
) -> dict[str, Any]:
    """Task-validator unit fixture, deliberately without a full transition trace."""
    return {
        "transitions": [],
        "optimization": {
            "update_events": update_events(expected_updates),
            "online_after_sha256": expected_updates[-1].online_sha256,
            "target_before_sha256": target_sha256,
            "target_after_sha256": target_sha256,
        },
        "selector": selector,
        "replay": {"decision_count": decision_count},
    }


def handoff_controller(
    expected_update_decisions: tuple[int, ...],
    rewards: Sequence[float],
    *,
    task_name: str,
) -> tuple[BDQOptimizerController, list[dict[str, Any]], str]:
    """Small handoff scaffolding, separate from registered acceptance workloads."""
    settings = BDQOptimizationSettings(
        replay_capacity=8,
        replay_warmup_decisions=2,
        batch_size=2,
        optimizer_update_interval_decisions=2,
        hard_target_sync_interval_optimizer_updates=10_000,
    )
    controller = BDQOptimizerController(seed=51001, settings=settings)
    collector = DirectReplayCollector(controller)
    transitions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    target_before = network_sha256(controller.target_network)
    for index, reward in enumerate(rewards):
        masks = (np.zeros(3, dtype=np.bool_), np.zeros(2, dtype=np.bool_))
        collector.begin(
            0,
            np.full((84, 84, 4), index / 10.0, dtype=np.float32),
            np.asarray([index % 3, index % 2], dtype=np.int64),
            masks,
        )
        result = _complete_gate_transition(
            collector,
            0,
            float(reward),
            np.full((84, 84, 4), (index + 1) / 10.0, dtype=np.float32),
            masks,
            terminated=False,
            truncated=False,
            transitions=transitions,
            optimization_events=events,
            episode_index=0,
            episode_decision_index=index,
            expected_update_decisions=expected_update_decisions,
            task_name=task_name,
        )
        if result.updated:
            events[-1]["online_after_sha256"] = network_sha256(
                controller.online_network
            )
    assert controller.decision_count == len(rewards)
    assert controller.optimizer_update_count == len(expected_update_decisions)
    assert controller.target_sync_count == 0
    assert len(events) == len(expected_update_decisions)
    assert collector.pending_agent_ids == ()
    return controller, events, target_before
