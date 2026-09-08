from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.acceptance import copy_complete_player  # noqa: E402
from quickdraw_bdq.llapi import LLAPIContractError  # noqa: E402
from quickdraw_bdq.replay import ReplayTransition  # noqa: E402
from quickdraw_bdq.update_gate import (  # noqa: E402
    _complete_gate_transition,
    _validate_replay_storage,
    _validate_target_hash_relationships,
)
import quickdraw_bdq.update_gate as update_gate  # noqa: E402
from run_bdq_long_horizon_smoke import (  # noqa: E402
    CONTRACT_PATH,
    CONTRACT_SCHEMA_PATH,
    RESULT_SCHEMA_PATH,
    _execution_mode,
    _expected_update_decisions,
    _validate_pilot_result,
    _validate_prefix_boundary,
    _stage_contract,
    _validate_post_boundary_selection,
    _validate_worker_player_copy,
    canonical_json_sha256,
    parse_arguments,
    validate_contract,
)
import run_bdq_long_horizon_smoke as long_horizon_runner  # noqa: E402
from quickdraw_bdq import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
    DirectReplayCollector,
    LinearEpsilonSchedule,
    ScheduledEpsilonGreedyBDQActionSelector,
    load_controller_checkpoint,
    save_controller_checkpoint,
)
from quickdraw_bdq.trajectory_validation import (  # noqa: E402
    validate_transition_prefix,
)


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_r3r_contract_schema_and_registered_boundaries_are_exact() -> None:
    contract = _contract()
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    validate_contract(contract)

    assert _expected_update_decisions(contract["stages"]["pilot"])[-1] == 13_996
    assert len(_expected_update_decisions(contract["stages"]["pilot"])) == 1_000
    assert _expected_update_decisions(contract["stages"]["synchronization"])[-1] == 49_996
    assert len(_expected_update_decisions(contract["stages"]["synchronization"])) == 10_000


def test_r3r_continuation_prefix_validator_rejects_transition_drift() -> None:
    transitions = [
        {"index": 0, "value": 1},
        {"index": 1, "value": 2},
    ]
    prefix = {
        "transition_count": 2,
        "canonical_transitions_sha256": canonical_json_sha256(transitions),
    }
    for candidate in (
        transitions[:1],
        list(reversed(transitions)),
        [{"index": 0, "value": 9}, transitions[1]],
    ):
        with pytest.raises(LLAPIContractError, match="canonical R3Q accepted prefix"):
            validate_transition_prefix(
                candidate,
                prefix,
                task_name="R3R test",
                base_name="R3Q accepted",
            )


def test_r3r_contract_rejects_sync_schedule_or_target_policy_drift() -> None:
    contract = _contract()
    contract["stages"]["synchronization"]["optimization"][
        "expected_update_decision_schedule"
    ]["last_decision"] = 13_996
    with pytest.raises(LLAPIContractError, match="self-inconsistent"):
        validate_contract(contract)

    contract = _contract()
    contract["stages"]["synchronization"]["final_clean_boundary"][
        "target_equals_online"
    ] = False
    with pytest.raises(LLAPIContractError, match="sync equality policy drifted"):
        validate_contract(contract)


@pytest.mark.parametrize(
    ("value", "expected_exception", "message"),
    [
        ([], LLAPIContractError, "synchronization event list drifted"),
        ([9_999], LLAPIContractError, "synchronization event list drifted"),
        ([10_000, 10_000], ValidationError, None),
    ],
)
def test_r3r_contract_rejects_missing_early_or_repeated_sync(
    value: list[int], expected_exception: type[Exception], message: str | None
) -> None:
    contract = _contract()
    contract["stages"]["synchronization"]["optimization"][
        "expected_target_sync_update_counts"
    ] = value
    with pytest.raises(expected_exception, match=message):
        validate_contract(contract)


def test_r3r_contract_rejects_sync_event_identity_drift() -> None:
    contract = _contract()
    contract["stages"]["synchronization"]["target_sync_events"][0][
        "optimizer_update_count"
    ] = 9_999
    with pytest.raises(ValidationError):
        validate_contract(contract)


def test_r3r_stage_view_registers_every_update_epsilon_sample() -> None:
    contract = _contract()
    stage = _stage_contract(contract, "pilot")
    decisions = _expected_update_decisions(contract["stages"]["pilot"])
    counts = stage["epsilon_schedule"]["trace_sample_completed_transition_counts"]
    assert counts == [0, *(decision - 1 for decision in decisions)]
    assert len(counts) == 1_001
    assert stage["optimization"]["expected_target_sync_update_counts"] == []

    sync_stage = _stage_contract(contract, "synchronization")
    assert len(
        sync_stage["epsilon_schedule"]["trace_sample_completed_transition_counts"]
    ) == 10_001
    assert sync_stage["optimization"]["expected_target_sync_update_counts"] == [10_000]


def test_r3r_cli_requires_a_passing_pilot_before_sync() -> None:
    parent = parse_arguments(
        ["--env", "player.exe", "--output", "out", "--stage", "pilot"]
    )
    assert _execution_mode(parent) == "parent"
    with pytest.raises(ValueError, match="Pilot parent mode does not accept"):
        _execution_mode(
            parse_arguments(
                [
                    "--env",
                    "player.exe",
                    "--output",
                    "out",
                    "--stage",
                    "pilot",
                    "--pilot-result",
                    "pilot.json",
                ]
            )
        )
    with pytest.raises(ValueError, match="requires --pilot-result"):
        _execution_mode(
            parse_arguments(
                [
                    "--env",
                    "player.exe",
                    "--output",
                    "out",
                    "--stage",
                    "synchronization",
                ]
            )
        )
    restorer = parse_arguments(
        [
            "--mode",
            "restorer",
            "--stage",
            "synchronization",
            "--checkpoint",
            "checkpoint.json",
            "--summary",
            "summary.json",
        ]
    )
    assert _execution_mode(restorer) == "restorer"
    with pytest.raises(ValueError, match="Synchronization worker mode requires"):
        _execution_mode(
            parse_arguments(
                [
                    "--env",
                    "player.exe",
                    "--stage",
                    "synchronization",
                    "--worker-output",
                    "worker",
                    "--worker-index",
                    "0",
                ]
            )
        )
    with pytest.raises(ValueError, match="Pilot worker mode does not accept"):
        _execution_mode(
            parse_arguments(
                [
                    "--env",
                    "player.exe",
                    "--stage",
                    "pilot",
                    "--pilot-result",
                    "pilot.json",
                    "--worker-output",
                    "worker",
                    "--worker-index",
                    "0",
                ]
            )
        )


def test_r3r_sync_rejects_a_fabricated_pilot_trace_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoopValidator:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def validate(self, _value: Any) -> None:
            pass

    result = {
        "stage": "pilot",
        "contract_sha256": "c" * 64,
        "exact_trace_equality": True,
        "canonical_trace_sha256": "d" * 64,
        "canonical_trace": {"stage": "pilot"},
        "checkpoint_differential": {"same_checkpoint_bytes": True},
    }
    result_path = tmp_path / "pilot-result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    monkeypatch.setattr(long_horizon_runner, "Draft202012Validator", NoopValidator)
    monkeypatch.setattr(long_horizon_runner, "sha256_file", lambda _path: "c" * 64)

    with pytest.raises(LLAPIContractError, match="canonical trace hash"):
        _validate_pilot_result(result_path, _contract())


def test_r3r_sync_revalidates_the_pilot_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoopValidator:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def validate(self, _value: Any) -> None:
            pass

    trace = {"stage": "pilot"}
    result = {
        "stage": "pilot",
        "contract_sha256": "c" * 64,
        "exact_trace_equality": True,
        "canonical_trace_sha256": canonical_json_sha256(trace),
        "canonical_trace": trace,
        "checkpoint_differential": {"same_checkpoint_bytes": True},
    }
    result_path = tmp_path / "pilot-result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    monkeypatch.setattr(long_horizon_runner, "Draft202012Validator", NoopValidator)
    monkeypatch.setattr(long_horizon_runner, "sha256_file", lambda _path: "c" * 64)
    monkeypatch.setattr(
        long_horizon_runner,
        "_validate_stage_registration",
        lambda *_args: None,
    )

    def reject_trace(*_args: Any, **_kwargs: Any) -> None:
        raise LLAPIContractError("pilot trace invalid")

    monkeypatch.setattr(long_horizon_runner, "_validate_trace", reject_trace)
    with pytest.raises(LLAPIContractError, match="pilot trace invalid"):
        _validate_pilot_result(result_path, _contract())


def test_complete_player_copy_requires_fresh_complete_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    executable = source / "QuickDrawResearchBasic.exe"
    executable.write_bytes(b"player")
    (source / "QuickDrawResearchBasic_Data").mkdir()
    (source / "UnityPlayer.dll").write_bytes(b"unity")
    (source / "sibling.txt").write_text("all siblings", encoding="utf-8")

    destination = tmp_path / "copy"
    copied = copy_complete_player(
        executable,
        destination,
        required_siblings=["QuickDrawResearchBasic_Data", "UnityPlayer.dll"],
    )
    assert copied == destination / executable.name
    assert copied.read_bytes() == b"player"
    assert (destination / "sibling.txt").read_text(encoding="utf-8") == "all siblings"
    with pytest.raises(FileExistsError, match="must be fresh"):
        copy_complete_player(executable, destination)
    with pytest.raises(ValueError, match="direct child"):
        copy_complete_player(executable, tmp_path / "nested-copy", required_siblings=["a/b"])
    with pytest.raises(ValueError, match="direct child"):
        copy_complete_player(executable, tmp_path / "parent-copy", required_siblings=[".."])
    with pytest.raises(ValueError, match="inside its source"):
        copy_complete_player(executable, source / "nested-copy")


def _save_clean_r3r_checkpoint(path: Path) -> None:
    settings = BDQOptimizationSettings()
    controller = BDQOptimizerController(seed=51001, settings=settings)
    collector = DirectReplayCollector(controller)
    selector = ScheduledEpsilonGreedyBDQActionSelector(
        controller.online_network,
        schedule=LinearEpsilonSchedule(),
        seed=61001,
    )
    save_controller_checkpoint(path, controller, collector, selector)


def test_r3r_checkpoint_rejects_dirty_controller_state(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    _save_clean_r3r_checkpoint(checkpoint_path)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["state"]["controller"]["decision_count"] = 1
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LLAPIContractError, match="state hash mismatch"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=BDQOptimizationSettings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3r_checkpoint_rejects_selector_rng_drift(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    _save_clean_r3r_checkpoint(checkpoint_path)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    generator_state = checkpoint["state"]["selector"]["generator_state"]
    data = generator_state["data"]
    generator_state["data"] = ("A" if data[0] != "A" else "B") + data[1:]
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LLAPIContractError, match="state hash mismatch"):
        load_controller_checkpoint(
            checkpoint_path,
            settings=BDQOptimizationSettings(),
            controller_seed=51001,
            exploration_seed=61001,
            schedule=LinearEpsilonSchedule(),
        )


def test_r3r_worker_mode_requires_its_complete_run_owned_copy(tmp_path: Path) -> None:
    output = tmp_path / "output"
    worker_output = output / "run-1"
    player_copy = output / "player-copies" / "run-1"
    player_copy.mkdir(parents=True)
    executable = player_copy / "QuickDrawResearchBasic.exe"
    executable.write_bytes(b"player")
    (player_copy / "QuickDrawResearchBasic_Data").mkdir()
    (player_copy / "UnityPlayer.dll").write_bytes(b"unity")

    _validate_worker_player_copy(
        executable,
        worker_output,
        0,
        ["QuickDrawResearchBasic_Data", "UnityPlayer.dll"],
    )
    with pytest.raises(LLAPIContractError, match="run-owned complete player copy"):
        _validate_worker_player_copy(
            executable,
            worker_output,
            1,
            ["QuickDrawResearchBasic_Data", "UnityPlayer.dll"],
        )
    (player_copy / "UnityPlayer.dll").unlink()
    with pytest.raises(LLAPIContractError, match="omitted UnityPlayer.dll"):
        _validate_worker_player_copy(
            executable,
            worker_output,
            0,
            ["QuickDrawResearchBasic_Data", "UnityPlayer.dll"],
        )


def test_complete_gate_transition_keeps_sync_opt_in() -> None:
    class FakeCollector:
        pending_agent_ids = ()

        def complete(self, *args: Any, **kwargs: Any) -> tuple[Any, Any]:
            del args, kwargs
            transition = ReplayTransition(
                observation=np.zeros((84, 84, 4), dtype=np.float32),
                action=np.asarray([0, 0], dtype=np.int64),
                reward=0.0,
                next_observation=np.zeros((84, 84, 4), dtype=np.float32),
                action_masks=(
                    np.zeros(3, dtype=np.bool_),
                    np.zeros(2, dtype=np.bool_),
                ),
                next_action_masks=(
                    np.zeros(3, dtype=np.bool_),
                    np.zeros(2, dtype=np.bool_),
                ),
                terminated=False,
                truncated=False,
            )
            from quickdraw_bdq.optimizer import OptimizationStepResult

            return transition, OptimizationStepResult(
                decision_count=49_996,
                replay_size=49_996,
                optimizer_update_count=10_000,
                target_sync_count=1,
                updated=True,
                target_synced=True,
                loss=0.1,
                mean_absolute_td_error=0.2,
            )

    kwargs = {
        "transitions": [],
        "optimization_events": [],
        "episode_index": 0,
        "episode_decision_index": 0,
        "expected_update_decisions": [49_996],
        "task_name": "R3R test",
    }
    with pytest.raises(LLAPIContractError, match="synchronized"):
        _complete_gate_transition(
            FakeCollector(), 0, 0.0, np.zeros((84, 84, 4), dtype=np.float32),
            (np.zeros(3, dtype=np.bool_), np.zeros(2, dtype=np.bool_)),
            terminated=False, truncated=False, **kwargs
        )
    result = _complete_gate_transition(
        FakeCollector(), 0, 0.0, np.zeros((84, 84, 4), dtype=np.float32),
        (np.zeros(3, dtype=np.bool_), np.zeros(2, dtype=np.bool_)),
        terminated=False, truncated=False,
        allowed_target_sync_updates=[10_000], **kwargs
    )
    assert result.target_synced is True


def _target_event(
    *,
    target_before: str,
    target_after: str,
    online_before: str,
    online_after: str,
    target_synced: bool,
    optimizer_update_count: int,
    target_sync_count: int,
) -> dict[str, Any]:
    return {
        "decision_count": 49_996 if target_synced else 10_000,
        "optimizer_update_count": optimizer_update_count,
        "target_sync_count": target_sync_count,
        "target_synced": target_synced,
        "online_before_sha256": online_before,
        "online_after_sha256": online_after,
        "target_before_sha256": target_before,
        "target_after_sha256": target_after,
        "epsilon_sample": {"completed_transition_count": 9_999, "epsilon": 1.0},
    }


def test_r3r_target_history_validator_rejects_sync_and_target_drift() -> None:
    frozen = "a" * 64
    updated = "b" * 64
    event = _target_event(
        target_before=frozen,
        target_after=updated,
        online_before=frozen,
        online_after=updated,
        target_synced=True,
        optimizer_update_count=10_000,
        target_sync_count=1,
    )
    sync_event = {
        key: event[key]
        for key in (
            "decision_count",
            "optimizer_update_count",
            "target_sync_count",
            "online_before_sha256",
            "online_after_sha256",
            "target_before_sha256",
            "target_after_sha256",
        )
    }
    optimization = {
        "online_before_sha256": frozen,
        "online_after_sha256": updated,
        "target_before_sha256": frozen,
        "target_after_sha256": updated,
        "target_sync_events": [sync_event],
        "update_epsilon_samples": [event["epsilon_sample"]],
    }
    _validate_target_hash_relationships(
        optimization,
        [event],
        expected_sync_count=1,
        registered_sync_updates=[10_000],
        task_name="R3R test",
        require_target_hashes=True,
    )

    for mutation, message in (
        ({"online_before_sha256": "c" * 64}, "online network drifted"),
        ({"target_before_sha256": "c" * 64}, "target drifted before"),
        ({"optimizer_update_count": 9_999}, "unregistered update"),
    ):
        invalid_event = {**event, **mutation}
        with pytest.raises(LLAPIContractError, match=message):
            _validate_target_hash_relationships(
                optimization,
                [invalid_event],
                expected_sync_count=1,
                registered_sync_updates=[10_000],
                task_name="R3R test",
                require_target_hashes=True,
            )

    with pytest.raises(LLAPIContractError, match="event trace differs"):
        _validate_target_hash_relationships(
            {**optimization, "target_sync_events": []},
            [event],
            expected_sync_count=1,
            registered_sync_updates=[10_000],
            task_name="R3R test",
            require_target_hashes=True,
        )

    no_sync_event = _target_event(
        target_before=frozen,
        target_after="c" * 64,
        online_before=frozen,
        online_after=updated,
        target_synced=False,
        optimizer_update_count=1,
        target_sync_count=0,
    )
    with pytest.raises(LLAPIContractError, match="without a synchronization"):
        _validate_target_hash_relationships(
            {
                "online_before_sha256": frozen,
                "online_after_sha256": updated,
                "target_before_sha256": frozen,
                "target_after_sha256": "c" * 64,
                "target_sync_events": [],
                "update_epsilon_samples": [no_sync_event["epsilon_sample"]],
            },
            [no_sync_event],
            expected_sync_count=0,
            registered_sync_updates=[],
            task_name="R3R test",
            require_target_hashes=True,
        )

    with pytest.raises(LLAPIContractError, match="target did not equal online"):
        _validate_target_hash_relationships(
            {**optimization, "online_after_sha256": frozen},
            [event],
            expected_sync_count=1,
            registered_sync_updates=[10_000],
            task_name="R3R test",
            require_target_hashes=True,
        )
    with pytest.raises(LLAPIContractError, match="final target hash differs"):
        _validate_target_hash_relationships(
            {**optimization, "target_after_sha256": frozen},
            [event],
            expected_sync_count=1,
            registered_sync_updates=[10_000],
            task_name="R3R test",
            require_target_hashes=True,
        )


def _composed_validator_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = "a" * 64
    updated = "b" * 64
    epsilon_sample = {"completed_transition_count": 0, "epsilon": 1.0}
    event = {
        "decision_count": 1,
        "replay_size": 1,
        "optimizer_update_count": 1,
        "target_sync_count": 1,
        "target_synced": True,
        "loss": 0.1,
        "mean_absolute_td_error": 0.2,
        "online_before_sha256": frozen,
        "online_after_sha256": updated,
        "target_before_sha256": frozen,
        "target_after_sha256": updated,
        "epsilon_sample": epsilon_sample,
    }
    transition = {
        "index": 0,
        "episode_index": 0,
        "episode_decision_index": 0,
        "observation_sha256": frozen,
        "next_observation_sha256": updated,
        "action": [0, 0],
        "reward": 0.0,
        "action_masks": [[False, False, False], [False, False]],
        "next_action_masks": [[False, False, False], [False, False]],
        "terminated": False,
        "truncated": False,
    }
    contract = {
        "collection": {
            "transition_limit": 1,
            "minimum_completed_episodes": 0,
            "minimum_unique_action_tuples": 1,
        },
        "optimization": {
            "replay_capacity": 8,
            "replay_warmup_decisions": 0,
            "expected_optimizer_updates": 1,
            "expected_target_synchronizations": 1,
            "expected_target_sync_update_counts": [1],
            "expected_first_update_decision": 1,
            "optimizer_update_interval_decisions": 1,
        },
    }
    trace = {
        "contract_sha256": "c" * 64,
        "transitions": [transition],
        "episodes": [
            {
                "episode_index": 0,
                "transition_start_index": 0,
                "transition_count": 1,
                "return": 0.0,
                "end_kind": "collection_cutoff",
                "unity_episode_ended": False,
            }
        ],
        "completed_episode_count": 0,
        "episode_reset_count": 0,
        "truncation_events": [],
        "cutoff": {
            "pending_agent_ids": [],
            "pending_decision_count": 0,
            "ended_on_unity_boundary": False,
        },
        "replay": {
            "decision_count": 1,
            "size": 1,
            "capacity": 8,
            "warmup_decisions": 0,
            "below_warmup": False,
            "at_warmup": False,
        },
        "selector": {
            "selection_count": 1,
            "action_tuple_counts": [1, 0, 0, 0, 0, 0],
            "unique_action_tuple_count": 1,
        },
        "optimization": {
            "optimizer_update_count": 1,
            "target_sync_count": 1,
            "online_before_sha256": frozen,
            "online_after_sha256": updated,
            "target_before_sha256": frozen,
            "target_after_sha256": updated,
            "update_events": [event],
            "target_sync_events": [
                {
                    key: event[key]
                    for key in (
                        "decision_count",
                        "optimizer_update_count",
                        "target_sync_count",
                        "online_before_sha256",
                        "online_after_sha256",
                        "target_before_sha256",
                        "target_after_sha256",
                    )
                }
            ],
            "update_epsilon_samples": [epsilon_sample],
        },
    }
    return contract, trace


def test_r3r_composed_validator_rejects_sync_opt_in_and_update_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract, trace = _composed_validator_fixture()

    class NoopValidator:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def validate(self, _value: Any) -> None:
            pass

    monkeypatch.setattr(update_gate, "Draft202012Validator", NoopValidator)
    monkeypatch.setattr(update_gate, "sha256_file", lambda _path: "c" * 64)
    common = {
        "result_schema": {"$defs": {"trace": {}}},
        "contract_path": Path("contract.json"),
        "task_name": "R3R composed test",
        "require_update_hashes": False,
        "contract": contract,
        "require_target_hashes": True,
    }
    with pytest.raises(LLAPIContractError, match="not enabled"):
        update_gate.validate_update_gate_trace(
            trace,
            allow_target_synchronization=False,
            expected_target_sync_updates=[1],
            **common,
        )
    with pytest.raises(LLAPIContractError, match="target-sync events differ"):
        update_gate.validate_update_gate_trace(
            trace,
            allow_target_synchronization=True,
            expected_target_sync_updates=[2],
            **common,
        )
    drifted = json.loads(json.dumps(trace))
    drifted["optimization"]["optimizer_update_count"] = 2
    with pytest.raises(LLAPIContractError, match="update count differs"):
        update_gate.validate_update_gate_trace(
            drifted,
            allow_target_synchronization=True,
            expected_target_sync_updates=[1],
            **common,
        )
    pending = json.loads(json.dumps(trace))
    pending["cutoff"]["pending_agent_ids"] = [7]
    with pytest.raises(LLAPIContractError, match="pending decision"):
        update_gate.validate_update_gate_trace(
            pending,
            allow_target_synchronization=True,
            expected_target_sync_updates=[1],
            **common,
        )


def test_r3r_result_rejects_a_discarded_post_boundary_action() -> None:
    selection = {
        "policy": "stop_before_live_action; synthetic_selection_only",
        "live_action_selected": False,
        "synthetic_selection_required": False,
        "synthetic_selection": None,
    }
    with pytest.raises(LLAPIContractError, match="discarded a post-boundary live action"):
        _validate_post_boundary_selection(
            "pilot",
            {**selection, "live_action_selected": True},
        )

    valid_sync_selection = {
        **selection,
        "synthetic_selection_required": True,
        "synthetic_selection": {"legal": True},
    }
    _validate_post_boundary_selection("synchronization", valid_sync_selection)
    for invalid_sync_selection in (
        {**valid_sync_selection, "synthetic_selection_required": False},
        {**valid_sync_selection, "synthetic_selection": None},
        {**valid_sync_selection, "synthetic_selection": {"legal": False}},
    ):
        with pytest.raises(
            LLAPIContractError, match="omitted legal post-sync selection"
        ):
            _validate_post_boundary_selection(
                "synchronization", invalid_sync_selection
            )


def test_r3r_prefix_boundary_rejects_checkpoint_state_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    prefix = contract["continuation_prefix"]
    controller = SimpleNamespace(
        decision_count=prefix["decision_count"],
        optimizer_update_count=prefix["optimizer_update_count"],
        target_sync_count=prefix["target_sync_count"],
        online_network=object(),
        target_network=object(),
    )
    collector = SimpleNamespace(pending_agent_ids=[])
    selector = object()
    summary = {
        "schema_version": "quickdraw.bdq-checkpoint.v1",
        "controller_seed": 51001,
        "exploration_seed": 61001,
        "decision_count": prefix["decision_count"],
        "optimizer_update_count": prefix["optimizer_update_count"],
        "target_sync_count": prefix["target_sync_count"],
        "online_network_sha256": prefix["online_network_sha256"],
        "target_network_sha256": prefix["target_network_sha256"],
        "pending_agent_ids": [],
    }
    monkeypatch.setattr(
        long_horizon_runner,
        "validate_transition_prefix",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        long_horizon_runner,
        "boundary_summary",
        lambda *_args: summary,
    )
    monkeypatch.setattr(
        long_horizon_runner,
        "network_sha256",
        lambda network: (
            prefix["online_network_sha256"]
            if network is controller.online_network
            else prefix["target_network_sha256"]
        ),
    )
    monkeypatch.setattr(
        long_horizon_runner,
        "checkpoint_state_sha256",
        lambda *_args: "d" * 64,
    )
    with pytest.raises(LLAPIContractError, match="checkpoint state drifted"):
        _validate_prefix_boundary(
            controller,
            collector,
            selector,
            [],
            contract,
        )


def test_r3r_replay_storage_validator_rejects_accounting_drift() -> None:
    expected = {
        "decision_count": 4,
        "size": 4,
        "capacity": 100,
        "warmup_decisions": 4,
        "below_warmup": False,
        "at_warmup": True,
    }
    storage = {
        "capacity": 100,
        "size": 4,
        "frame_reference_count": 32,
        "accounted_storage_bytes": 10,
        "remaining_accounted_storage_bytes": 90,
        "max_accounted_storage_bytes": 100,
    }
    _validate_replay_storage(
        {**expected, "storage": storage}, expected, 4, task_name="R3R test"
    )
    with pytest.raises(LLAPIContractError, match="storage accounting"):
        _validate_replay_storage(
            {**expected, "storage": {**storage, "accounted_storage_bytes": 11}},
            expected,
            4,
            task_name="R3R test",
        )
