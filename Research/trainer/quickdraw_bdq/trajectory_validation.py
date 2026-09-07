"""Relational checks shared by the registered trajectory contracts and traces.

Callers validate the frozen schemas first. The ordinal field mapping below is
explicit because historical JSON names are part of those frozen contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .acceptance import canonical_json_sha256, registered_settings
from .exploration import LinearEpsilonSchedule
from .llapi import LLAPIContractError
from .optimizer import BDQOptimizationSettings


UPDATE_PREFIX_FIELDS = (
    (
        "online_after_first_update_sha256",
        "first_update_loss",
        "first_update_mean_absolute_td_error",
    ),
    (
        "online_after_second_update_sha256",
        "second_update_loss",
        "second_update_mean_absolute_td_error",
    ),
    (
        "online_after_third_update_sha256",
        "third_update_loss",
        "third_update_mean_absolute_td_error",
    ),
    (
        "online_after_fourth_update_sha256",
        "fourth_update_loss",
        "fourth_update_mean_absolute_td_error",
    ),
)


def validate_inherited_fields(
    current: dict[str, Any],
    base: dict[str, Any],
    keys: Sequence[str],
    *,
    context: str,
    base_name: str,
) -> None:
    for key in keys:
        if current[key] != base[key]:
            raise LLAPIContractError(f"{context} {key} differs from {base_name}.")


def validate_player_execution(
    player_execution: dict[str, Any],
    *,
    repo_root: Path,
    task_name: str,
) -> None:
    project_settings = (
        repo_root / player_execution["project_settings_path"]
    ).read_text(encoding="utf-8")
    expected_background_setting = (
        "  runInBackground: 1"
        if player_execution["run_in_background"]
        else "  runInBackground: 0"
    )
    if expected_background_setting not in project_settings.splitlines():
        raise LLAPIContractError(
            f"{task_name}'s standalone-player background setting has drifted."
        )
    if player_execution["no_graphics"]:
        raise LLAPIContractError(f"{task_name} visual observations require graphics.")
    if player_execution["standalone_player_arguments"]:
        raise LLAPIContractError(
            f"{task_name} must not alter visual observations with player arguments."
        )


def validate_scheduled_optimization(
    contract: dict[str, Any],
    base_contract: dict[str, Any],
    *,
    task_name: str,
    base_name: str,
    update_count: int,
) -> None:
    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    if registered_settings(settings) != {
        key: optimization[key] for key in registered_settings(settings)
    }:
        raise LLAPIContractError(
            f"{task_name} differs from production optimizer defaults."
        )
    expected_updates = [
        settings.replay_warmup_decisions
        + index * settings.optimizer_update_interval_decisions
        for index in range(update_count)
    ]
    if optimization["expected_update_decisions"] != expected_updates:
        raise LLAPIContractError(
            f"{task_name} update decisions differ from its schedule."
        )
    if optimization["expected_optimizer_updates"] != len(expected_updates):
        raise LLAPIContractError(
            f"{task_name} must stop after optimizer update {update_count}."
        )
    if optimization["expected_target_synchronizations"] != 0:
        raise LLAPIContractError(
            f"{task_name} must not synchronize the target network."
        )
    collection = contract["collection"]
    if collection["transition_limit"] != expected_updates[-1]:
        raise LLAPIContractError(
            f"{task_name} cutoff must equal optimizer update {update_count}."
        )
    if collection["scheduled_transition_count"] != collection["transition_limit"]:
        raise LLAPIContractError(f"{task_name} must schedule every collected action.")
    validate_inherited_fields(
        collection,
        base_contract["collection"],
        ("scenario_seed", "policy_seed", "exploration_seed", "selector"),
        context=f"{task_name} collection",
        base_name=base_name,
    )


def validate_continuous_schedule(
    contract: dict[str, Any],
    base_contract: dict[str, Any],
    *,
    task_name: str,
    base_name: str,
    update_count: int,
) -> None:
    schedule_contract = contract["epsilon_schedule"]
    validate_inherited_fields(
        schedule_contract,
        base_contract["epsilon_schedule"],
        (
            "class",
            "selector_class",
            "completed_transition_count_source",
            "replay_warmup_decisions",
            "decay_decisions",
            "initial_epsilon",
            "final_epsilon",
            "continuous_selector_rng_from_completed_count_zero",
        ),
        context=f"{task_name} epsilon schedule",
        base_name=base_name,
    )
    schedule = LinearEpsilonSchedule(
        replay_warmup_decisions=schedule_contract["replay_warmup_decisions"],
        decay_decisions=schedule_contract["decay_decisions"],
        initial_epsilon=schedule_contract["initial_epsilon"],
        final_epsilon=schedule_contract["final_epsilon"],
    )
    expected_epsilons = [
        schedule.epsilon_at(count)
        for count in schedule_contract["trace_sample_completed_transition_counts"]
    ]
    if schedule_contract["trace_sample_epsilons"] != expected_epsilons:
        raise LLAPIContractError(
            f"{task_name} epsilon samples differ from its schedule."
        )
    cutoff = contract["collection"]["transition_limit"]
    if schedule_contract["selection_count"] != cutoff:
        raise LLAPIContractError(f"{task_name} selector count differs from its cutoff.")
    if (
        schedule_contract["full_exploration_selection_count"]
        != schedule.replay_warmup_decisions + 1
    ):
        raise LLAPIContractError(f"{task_name} full-exploration count drifted.")
    if (
        schedule_contract["decay_selection_count"]
        != cutoff - schedule_contract["full_exploration_selection_count"]
    ):
        raise LLAPIContractError(f"{task_name} decay-selection count drifted.")
    if schedule_contract["last_selection_completed_transition_count"] != cutoff - 1:
        raise LLAPIContractError(
            f"{task_name} selected an action after update {update_count}."
        )


def validate_continuation_boundary(
    boundary: dict[str, Any],
    prefix: dict[str, Any],
    collection: dict[str, Any],
    *,
    task_name: str,
    base_name: str,
    update_count: int,
    continuation_description: str,
    post_update_action_key: str,
) -> None:
    if boundary["continuation_after_transition_count"] != prefix["transition_count"]:
        raise LLAPIContractError(
            f"{task_name} continuation does not begin after {base_name}."
        )
    if (
        boundary["new_transition_count"]
        != collection["transition_limit"] - prefix["transition_count"]
    ):
        raise LLAPIContractError(
            f"{task_name} continuation is not exactly {continuation_description} transitions."
        )
    if (
        boundary["first_new_selection_completed_transition_count"]
        != prefix["transition_count"]
    ):
        raise LLAPIContractError(f"{task_name} first new selection is not contiguous.")
    if (
        boundary["last_new_selection_completed_transition_count"]
        != collection["transition_limit"] - 1
    ):
        raise LLAPIContractError(f"{task_name} last new selection count drifted.")
    if boundary["completion_decision_count"] != collection["transition_limit"]:
        raise LLAPIContractError(
            f"{task_name} completion count differs from its cutoff."
        )
    if boundary["optimizer_update_count_before_continuation"] != update_count - 1:
        raise LLAPIContractError(
            f"{task_name} does not continue after {base_name} update {update_count - 1}."
        )
    if boundary["optimizer_update_count_after_completion"] != update_count:
        raise LLAPIContractError(
            f"{task_name} completion is not optimizer update {update_count}."
        )
    if boundary["target_sync_count_after_completion"] != 0:
        raise LLAPIContractError(
            f"{task_name} boundary includes a target synchronization."
        )
    if boundary[post_update_action_key]:
        raise LLAPIContractError(f"{task_name} must stop before a post-update action.")


def validate_transition_prefix(
    transitions: Sequence[dict[str, Any]],
    prefix: dict[str, Any],
    *,
    task_name: str,
    base_name: str,
) -> int:
    count = int(prefix["transition_count"])
    if (
        canonical_json_sha256(transitions[:count])
        != prefix["canonical_transitions_sha256"]
    ):
        raise LLAPIContractError(
            f"{task_name} did not preserve the canonical {base_name} prefix."
        )
    return count


def prefix_update_values(
    prefix: dict[str, Any],
    update_count: int,
) -> tuple[tuple[str, float, float], ...]:
    # Direct indexing deliberately rejects a missing field or unknown ordinal.
    return tuple(
        (prefix[hash_key], prefix[loss_key], prefix[td_key])
        for hash_key, loss_key, td_key in (
            UPDATE_PREFIX_FIELDS[i] for i in range(update_count)
        )
    )


def validate_prefix_updates(
    events: Sequence[dict[str, Any]],
    expected: Sequence[tuple[str, float, float]],
    *,
    task_name: str,
    base_name: str,
) -> None:
    # The composed schema/update validator has already enforced count and order.
    for event, (online_hash, loss, td_error) in zip(events, expected):
        if event["online_after_sha256"] != online_hash:
            raise LLAPIContractError(
                f"{task_name} changed an {base_name} post-update online hash."
            )
        if event["loss"] != loss or event["mean_absolute_td_error"] != td_error:
            raise LLAPIContractError(
                f"{task_name} changed an {base_name} optimizer metric."
            )


def validate_frozen_target(
    optimization: dict[str, Any],
    prefix: dict[str, Any],
    *,
    task_name: str,
    base_name: str,
) -> None:
    if (
        optimization["target_before_sha256"] != prefix["frozen_target_sha256"]
        or optimization["target_after_sha256"] != prefix["frozen_target_sha256"]
    ):
        raise LLAPIContractError(
            f"{task_name} changed the frozen {base_name} target network."
        )


def validate_scheduled_selector(
    selector: dict[str, Any],
    schedule_contract: dict[str, Any],
    *,
    task_name: str,
) -> None:
    expected_samples = [
        {"completed_transition_count": count, "epsilon": epsilon}
        for count, epsilon in zip(
            schedule_contract["trace_sample_completed_transition_counts"],
            schedule_contract["trace_sample_epsilons"],
        )
    ]
    if selector["epsilon_samples"] != expected_samples:
        raise LLAPIContractError(f"{task_name} trace epsilon samples drifted.")
    for key in (
        "selection_count",
        "full_exploration_selection_count",
        "decay_selection_count",
        "first_decay_completed_transition_count",
        "last_selection_completed_transition_count",
    ):
        if selector[key] != schedule_contract[key]:
            raise LLAPIContractError(f"{task_name} selector {key} drifted.")
    if (
        selector["completed_transition_count_source"]
        != schedule_contract["completed_transition_count_source"]
    ):
        raise LLAPIContractError(f"{task_name} selector counter source drifted.")


def validate_scheduled_update_trace(
    trace: dict[str, Any],
    prefix: dict[str, Any],
    schedule_contract: dict[str, Any],
    *,
    task_name: str,
    base_name: str,
    update_count: int,
) -> None:
    validate_transition_prefix(
        trace["transitions"], prefix, task_name=task_name, base_name=base_name
    )
    optimization = trace["optimization"]
    events = optimization["update_events"]
    expected = prefix_update_values(prefix, update_count - 1)
    validate_prefix_updates(
        events[: update_count - 1], expected, task_name=task_name, base_name=base_name
    )
    final_update = events[update_count - 1]
    if final_update["online_after_sha256"] == expected[-1][0]:
        raise LLAPIContractError(
            f"{task_name} update {update_count} did not change the online network."
        )
    if optimization["online_after_sha256"] != final_update["online_after_sha256"]:
        raise LLAPIContractError(
            f"{task_name} final online hash differs from update {update_count}."
        )
    validate_frozen_target(
        optimization, prefix, task_name=task_name, base_name=base_name
    )
    validate_scheduled_selector(
        trace["selector"], schedule_contract, task_name=task_name
    )
    if (
        trace["selector"]["last_selection_completed_transition_count"]
        >= trace["replay"]["decision_count"]
    ):
        raise LLAPIContractError(
            f"{task_name} selected an action after update {update_count}."
        )
