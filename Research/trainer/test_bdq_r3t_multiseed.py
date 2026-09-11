from __future__ import annotations

import copy
import json
import shutil
import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_bdq_r3t_multiseed as r3t  # noqa: E402
from quickdraw_bdq import LLAPIContractError  # noqa: E402
import quickdraw_bdq.update_gate as update_gate  # noqa: E402


@pytest.fixture
def contract() -> dict:
    return json.loads(r3t.CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def contract_schema() -> dict:
    return json.loads(r3t.CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def result_schema() -> dict:
    return json.loads(r3t.RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_r3t_contract_and_result_schema_are_valid(
    contract: dict, contract_schema: dict, result_schema: dict
) -> None:
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    r3t.validate_contract(contract)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["campaign"]["seed_mapping"][0].__setitem__(
            "policy_initialization_seed", 51002
        ),
        lambda value: value["collection"].__setitem__("transition_limit", 49_997),
        lambda value: value["optimization"].__setitem__("learning_rate", 0.0002),
        lambda value: value["checkpoint"].__setitem__("save_update_counts", [2500]),
        lambda value: value["learning_curve"].__setitem__(
            "interval_updates", 50
        ),
        lambda value: value["player_execution"]["runtime_mutated_files"][0].__setitem__(
            "path", "QuickDrawResearchBasic_Data/unregistered.json"
        ),
        lambda value: value["artifact_layout"].__setitem__(
            "root", "Artifacts/Experiments/other"
        ),
    ],
)
def test_r3t_contract_schema_rejects_boundary_drift(
    contract: dict, contract_schema: dict, mutate
) -> None:
    mutate(contract)
    with pytest.raises(ValidationError):
        Draft202012Validator(contract_schema).validate(contract)


def test_r3t_contract_rejects_player_hash_drift(
    contract: dict,
) -> None:
    contract["player_execution"]["source_manifest_sha256"] = "0" * 64
    with pytest.raises(LLAPIContractError, match="source player manifest"):
        r3t.validate_contract(contract)


def test_r3t_contract_rejects_runtime_drift(contract: dict) -> None:
    contract["runtime"]["torch"] = "2.11.0+cpu"
    with pytest.raises(ValidationError):
        r3t.validate_contract(contract)


def test_r3t_mapping_is_explicit_and_not_name_derived(contract: dict) -> None:
    mapping = r3t._mapping_for_run(contract, "seed-51003")
    assert mapping["policy_initialization_seed"] == 51003
    assert mapping["replay_sampling_seed"] == 51003
    assert mapping["exploration_seed"] == 61001
    assert mapping["scenario_seed"] == 31001
    with pytest.raises(LLAPIContractError, match="no unique registered mapping"):
        r3t._mapping_for_run(contract, "seed-51006")


def test_r3t_selector_validation_binds_observed_epsilon_values(
    contract: dict,
) -> None:
    schedule = contract["epsilon_schedule"]
    selector = {
        "epsilon_samples": [
            {
                "completed_transition_count": count,
                "epsilon": epsilon,
            }
            for count, epsilon in zip(
                schedule["trace_sample_completed_transition_counts"],
                schedule["trace_sample_epsilons"],
            )
        ],
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
    }
    r3t.validate_scheduled_selector(selector, schedule, task_name="R3T test")
    selector["epsilon_samples"][2]["epsilon"] += 0.000001
    with pytest.raises(LLAPIContractError, match="epsilon samples drifted"):
        r3t.validate_scheduled_selector(selector, schedule, task_name="R3T test")


def test_r3t_episode_metrics_use_explicit_active_prefix_denominator() -> None:
    values = r3t._episode_metrics(
        {
            "episodes": [
                {
                    "unity_episode_ended": True,
                    "return": 1.5,
                    "end_kind": "terminal",
                }
            ],
            "active_episode_return": -0.25,
        },
        {"terminated": False, "truncated": False},
    )
    assert values["completed_episode_count"] == 1
    assert values["observed_episode_count"] == 2
    assert values["denominators"] == {"observed_episode_count": 2}
    assert values["mean_episode_return"] == pytest.approx(0.625)
    assert values["success_count"] == 1
    assert values["success_rate"] == pytest.approx(0.5)


def test_r3t_canonicalization_excludes_volatile_fields() -> None:
    first = {"stable": {"value": 1}, "update_duration_seconds": 1.0}
    second = {
        "stable": {"value": 1},
        "update_duration_seconds": 99.0,
        "process_leak_audit": {"before": 1, "after": 2},
        "player_runtime_mutations": [{"observed_sha256": "a" * 64}],
    }
    assert r3t._canonical_digest(first) == r3t._canonical_digest(second)


def test_r3t_campaign_canonicalization_excludes_serialized_timing_metadata() -> None:
    first = {
        "runs": [
            {
                "canonical_trace_sha256": "b" * 64,
                "canonical_metrics_sha256": "c" * 64,
                "trace": {"bytes": 10, "sha256": "d" * 64, "path": "runs/a/trace.json"},
                "metrics": {"bytes": 20, "sha256": "e" * 64, "path": "runs/a/metrics.json"},
            }
        ]
    }
    second = {
        "runs": [
            {
                "canonical_trace_sha256": "b" * 64,
                "canonical_metrics_sha256": "c" * 64,
                "trace": {"bytes": 99, "sha256": "f" * 64, "path": "runs/a/trace.json"},
                "metrics": {"bytes": 88, "sha256": "a" * 64, "path": "runs/a/metrics.json"},
            }
        ]
    }
    assert r3t._canonicalize_campaign_result(first) == r3t._canonicalize_campaign_result(second)


def test_r3t_allows_only_registered_runtime_player_sidecar(
    contract: dict, tmp_path: Path
) -> None:
    source_root = tmp_path / "source"
    timer_path = (
        source_root
        / "QuickDrawResearchBasic_Data"
        / "ML-Agents"
        / "Timers"
        / "Research_Basic_timers.json"
    )
    timer_path.parent.mkdir(parents=True)
    (source_root / "QuickDrawResearchBasic.exe").write_bytes(b"executable")
    (source_root / "UnityPlayer.dll").write_bytes(b"unity")
    timer_path.write_text('{"before": true}\n', encoding="utf-8")
    source_identity = r3t._manifest_identity(source_root)
    source = {
        "executable": source_root / "QuickDrawResearchBasic.exe",
        "manifest": source_identity["manifest"],
        "manifest_sha256": source_identity["manifest_sha256"],
        "file_count": source_identity["file_count"],
        "total_bytes": source_identity["total_bytes"],
        "executable_sha256": r3t.sha256_file(
            source_root / "QuickDrawResearchBasic.exe"
        ),
    }
    player_root = tmp_path / "copy"
    shutil.copytree(source_root, player_root)
    copied_executable = player_root / "QuickDrawResearchBasic.exe"
    r3t._validate_player_copy(
        contract, source, copied_executable, player_root
    )

    copied_timer = player_root / timer_path.relative_to(source_root)
    copied_timer.write_text('{"after": true}\n', encoding="utf-8")
    observed = r3t._validate_player_copy(
        contract,
        source,
        copied_executable,
        player_root,
        allow_runtime_mutations=True,
    )
    mutations = r3t._runtime_player_mutations(
        contract, source, observed["manifest"]
    )
    assert [entry["path"] for entry in mutations] == [
        "QuickDrawResearchBasic_Data/ML-Agents/Timers/Research_Basic_timers.json"
    ]
    assert mutations[0]["source_bytes"] != mutations[0]["observed_bytes"]

    (player_root / "UnityPlayer.dll").write_bytes(b"tampered")
    with pytest.raises(LLAPIContractError, match="outside registered runtime sidecars"):
        r3t._validate_player_copy(
            contract,
            source,
            copied_executable,
            player_root,
            allow_runtime_mutations=True,
        )


def test_r3t_manifest_keeps_repository_contract_path_outside_artifact_root(
    contract: dict, tmp_path: Path
) -> None:
    manifest = r3t._manifest(
        contract,
        {
            "path": contract["player_execution"]["source_executable"],
            "manifest_sha256": contract["player_execution"]["source_manifest_sha256"],
            "file_count": contract["player_execution"]["source_file_count"],
            "total_bytes": contract["player_execution"]["source_total_bytes"],
            "executable_sha256": contract["player_execution"]["executable_sha256"],
        },
        tmp_path,
    )
    assert manifest["contract_path"] == (
        "Research/trainer/bdq-r3t-basic-multiseed-contract-v1.json"
    )


def test_r3t_campaign_root_allows_only_empty_existing_directory(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    r3t._prepare_fresh_campaign_root(empty)
    r3t._prepare_fresh_campaign_root(empty)
    (empty / "prior.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must be fresh"):
        r3t._prepare_fresh_campaign_root(empty)


def test_r3t_cli_modes_reject_unregistered_overrides() -> None:
    parent = r3t.parse_arguments(["--env", "player.exe", "--output", "out"])
    assert r3t._execution_mode(parent) == "parent"
    worker = r3t.parse_arguments(
        [
            "--mode=worker",
            "--env=player.exe",
            "--worker-output=run",
            "--worker-index=0",
            "--run-id=seed-51001",
        ]
    )
    assert r3t._execution_mode(worker) == "worker"
    with pytest.raises(SystemExit):
        r3t.parse_arguments(
            ["--env", "player.exe", "--output", "out", "--seed", "51001"]
        )


def test_r3t_result_schema_rejects_missing_lineage(result_schema: dict) -> None:
    bad = {
        "schema_version": r3t.RESULT_SCHEMA_VERSION,
        "status": "accepted",
        "task": "R3T",
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(result_schema).validate(bad)


def _lineage_validator_fixture(contract: dict) -> tuple[dict, dict, dict]:
    registered = copy.deepcopy(contract)
    registered["checkpoint"]["save_update_counts"] = []
    mapping = r3t._mapping_for_run(registered, "seed-51001")
    curve = []
    events = []
    q_summary = {
        name: [
            {"mean": 0.0, "minimum": -1.0, "maximum": 1.0},
            {"mean": 0.0, "minimum": -1.0, "maximum": 1.0},
        ]
        for name in ("current", "online_next", "target_next")
    }
    for update_count in range(1, 10_001):
        decision_count = r3t._expected_checkpoint_decision(update_count)
        event = {
            "decision_count": decision_count,
            "optimizer_update_count": update_count,
            "target_sync_count": 1 if update_count == 10_000 else 0,
            "loss": 0.0,
            "mean_absolute_td_error": 0.0,
            "online_after_sha256": "1" * 64,
            "target_after_sha256": "2" * 64,
        }
        events.append(event)
        if update_count % 100 == 0:
            curve.append(
                {
                    **event,
                    "replay_size": decision_count,
                    "sampled_indices": list(range(64)),
                    "q_value_summary": q_summary,
                    "checkpoint_state_sha256": "3" * 64,
                    "update_duration_seconds": 0.0,
                    "completed_episode_count": 0,
                    "observed_episode_count": 1,
                    "completed_episode_return_sum": 0.0,
                    "active_episode_ended": False,
                    "active_episode_prefix_return": 0.0,
                    "mean_episode_return": 0.0,
                    "success_count": 0,
                    "success_rate": 0.0,
                    "denominators": {"observed_episode_count": 1},
                }
            )
    trace = {
        "lineage": {"learning_curve": curve, "checkpoint_records": []},
        "optimization": {"update_events": events},
    }
    metrics = {
        "contract_sha256": r3t.sha256_file(r3t.CONTRACT_PATH),
        "run_id": mapping["run_id"],
        "policy_seed": mapping["policy_initialization_seed"],
        "return_definition": registered["learning_curve"]["return_definition"],
        "success_definition": registered["learning_curve"]["success_definition"],
        "denominator_definition": r3t.DENOMINATOR_DEFINITION,
        "learning_curve": copy.deepcopy(curve),
    }
    return registered, trace, metrics


def test_r3t_lineage_validator_rejects_counter_drift(contract: dict) -> None:
    registered, trace, metrics = _lineage_validator_fixture(contract)
    trace["lineage"]["learning_curve"][0]["decision_count"] += 1
    metrics["learning_curve"][0]["decision_count"] += 1
    with pytest.raises(LLAPIContractError, match="decision boundary drifted"):
        r3t._validate_lineage(
            trace, metrics, registered, r3t._mapping_for_run(registered, "seed-51001"), Path(".")
        )


def test_r3t_lineage_validator_rejects_replay_sample_drift(contract: dict) -> None:
    registered, trace, metrics = _lineage_validator_fixture(contract)
    trace["lineage"]["learning_curve"][0]["sampled_indices"][1] = 0
    metrics["learning_curve"][0]["sampled_indices"][1] = 0
    with pytest.raises(LLAPIContractError, match="replay sample is not exact"):
        r3t._validate_lineage(
            trace, metrics, registered, r3t._mapping_for_run(registered, "seed-51001"), Path(".")
        )


def test_r3t_lineage_validator_rejects_metrics_drift(contract: dict) -> None:
    registered, trace, metrics = _lineage_validator_fixture(contract)
    metrics["learning_curve"][0]["loss"] = 1.0
    with pytest.raises(LLAPIContractError, match="metrics and trace learning curves differ"):
        r3t._validate_lineage(
            trace, metrics, registered, r3t._mapping_for_run(registered, "seed-51001"), Path(".")
        )


def test_r3t_lineage_validator_checks_checkpoint_artifact_and_boundary(
    contract: dict, tmp_path: Path
) -> None:
    registered, trace, metrics = _lineage_validator_fixture(contract)
    registered["checkpoint"]["save_update_counts"] = [2500]
    mapping = r3t._mapping_for_run(registered, "seed-51001")
    update_count = 2500
    decision_count = r3t._expected_checkpoint_decision(update_count)
    boundary = {
        "schema_version": r3t.CHECKPOINT_SCHEMA_VERSION,
        "controller_seed": mapping["policy_initialization_seed"],
        "exploration_seed": mapping["exploration_seed"],
        "decision_count": decision_count,
        "optimizer_update_count": update_count,
        "target_sync_count": 0,
        "online_network_sha256": "1" * 64,
        "target_network_sha256": "2" * 64,
        "replay": {
            "capacity": registered["optimization"]["replay_capacity"],
            "size": decision_count,
            "unique_frame_count": decision_count,
            "frame_reference_count": decision_count * 8,
            "frame_payload_bytes": 1,
            "metadata_payload_bytes": 1,
            "accounted_storage_bytes": 1,
            "max_accounted_storage_bytes": 2,
            "remaining_accounted_storage_bytes": 1,
            "legacy_observation_payload_bytes": 0,
            "legacy_capacity_observation_payload_bytes": 0,
            "cursor": decision_count,
        },
        "pending_agent_ids": [],
    }
    checkpoint = {
        "schema_version": r3t.CHECKPOINT_SCHEMA_VERSION,
        "contract_sha256": registered["base_checkpoint_contract"]["sha256"],
        "identity": {
            "package": {
                "distribution": registered["package"]["distribution"],
                "version": registered["package"]["version"],
            },
            "runtime": copy.deepcopy(registered["runtime"]),
            "settings": r3t.dataclasses.asdict(r3t.BDQOptimizationSettings()),
            "seeds": {
                "controller_seed": mapping["policy_initialization_seed"],
                "exploration_seed": mapping["exploration_seed"],
            },
        },
        "state": {
            "controller": {},
            "selector": {},
            "replay": {},
            "verification": boundary,
        },
        "state_sha256": "3" * 64,
    }
    checkpoint_path = (
        tmp_path
        / "runs"
        / mapping["run_id"]
        / "checkpoints"
        / "update-02500.json"
    )
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    record = {
        "optimizer_update_count": update_count,
        "decision_count": decision_count,
        "path": r3t._artifact_relative(checkpoint_path, tmp_path),
        "sha256": r3t.sha256_file(checkpoint_path),
        "bytes": checkpoint_path.stat().st_size,
        "state_sha256": checkpoint["state_sha256"],
        "boundary": copy.deepcopy(boundary),
    }
    trace["lineage"]["checkpoint_records"] = [record]
    r3t._validate_lineage(trace, metrics, registered, mapping, tmp_path)

    record["sha256"] = "0" * 64
    with pytest.raises(LLAPIContractError, match="artifact checksum drifted"):
        r3t._validate_lineage(trace, metrics, registered, mapping, tmp_path)


def test_r3t_restore_rejects_checkpoint_path_drift(
    contract: dict, tmp_path: Path
) -> None:
    mapping = r3t._mapping_for_run(contract, "seed-51001")
    with pytest.raises(LLAPIContractError, match="restore path"):
        r3t._restore_payload(contract, mapping, tmp_path / "wrong.json", tmp_path)


def test_r3t_provenance_validator_rejects_source_drift(
    contract: dict, tmp_path: Path
) -> None:
    mapping = r3t._mapping_for_run(contract, "seed-51001")
    player = {
        key: contract["player_execution"][key]
        for key in (
            "source_executable",
            "source_manifest_sha256",
            "source_file_count",
            "source_total_bytes",
            "executable_sha256",
        )
    }
    player["source_manifest_sha256"] = "0" * 64
    with pytest.raises(LLAPIContractError, match="source provenance"):
        r3t._validate_trace_player_provenance(
            {"provenance": {"player": player}}, contract, mapping, tmp_path
        )


def test_r3t_rejected_result_records_spawned_process_counts(
    contract: dict, result_schema: dict
) -> None:
    mapping = r3t._mapping_for_run(contract, "seed-51001")
    rejected = [
        {
            "run_id": mapping["run_id"],
            "run_ordinal": mapping["ordinal"],
            "policy_seed": mapping["policy_initialization_seed"],
            "status": "rejected",
            "error": "worker failed",
            "retained_output": f"runs/{mapping['run_id']}",
        }
    ]
    result = r3t._build_campaign_result(
        contract,
        "a" * 64,
        [],
        rejected,
        fresh_training_process_count=1,
        fresh_restore_process_count=0,
    )
    r3t._validate_campaign_result(result, result_schema, contract, "a" * 64)
    assert result["fresh_training_process_count"] == 1
    assert result["fresh_restore_process_count"] == 0


def test_r3t_rejected_attempt_retains_audit_and_stable_error_path(
    contract: dict, result_schema: dict, tmp_path: Path
) -> None:
    mapping = r3t._mapping_for_run(contract, "seed-51001")
    root = tmp_path / "campaign"
    root.mkdir()
    audit = {
        "platform": "Windows",
        "executable_name": "QuickDrawResearchBasic.exe",
        "before_matching_process_count": 0,
        "after_matching_process_count": 1,
        "new_matching_process_count": 1,
        "passed": False,
    }
    path = r3t._write_rejected_attempt(
        root,
        mapping,
        RuntimeError(f"worker log: {r3t.REPO_ROOT / 'logs' / 'worker.log'}"),
        process_leak_audit=audit,
    )
    rejected = json.loads(path.read_text(encoding="utf-8"))
    assert rejected["process_leak_audit"] == audit
    assert str(r3t.REPO_ROOT) not in rejected["error"]
    result = r3t._build_campaign_result(
        contract,
        "a" * 64,
        [],
        [rejected],
        fresh_training_process_count=1,
        fresh_restore_process_count=0,
    )
    r3t._validate_campaign_result(result, result_schema, contract, "a" * 64)


def test_update_gate_wires_observer_and_profiling_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Settings:
        replay_capacity = 10
        replay_warmup_decisions = 1
        batch_size = 1
        gamma = 0.99
        learning_rate = 0.001
        optimizer_update_interval_decisions = 1
        hard_target_sync_interval_optimizer_updates = 100

    contract = {
        "collection": {
            "scenario_seed": 3,
            "selector": "seeded_scheduled_branch_epsilon_greedy",
            "epsilon_decay_enabled": True,
            "scheduled_transition_count": 1,
            "transition_limit": 1,
            "minimum_completed_episodes": 1,
            "minimum_unique_action_tuples": 1,
            "require_no_pending_decision_at_cutoff": True,
            "clean_stop": "test",
            "policy_seed": 7,
            "exploration_seed": 8,
        },
        "optimization": {
            "replay_capacity": 10,
            "replay_warmup_decisions": 1,
            "batch_size": 1,
            "gamma": 0.99,
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "optimizer_update_interval_decisions": 1,
            "hard_target_sync_interval_optimizer_updates": 100,
            "expected_first_update_decision": 1,
            "expected_update_decision_schedule": {
                "first_decision": 1,
                "interval_decisions": 1,
                "optimizer_update_count": 1,
                "last_decision": 1,
            },
            "expected_update_decisions": [1],
            "expected_optimizer_updates": 1,
            "expected_target_synchronizations": 0,
            "expected_target_sync_update_counts": [],
        },
        "epsilon_schedule": {
            "completed_transition_count_source": "test controller decision count",
            "replay_warmup_decisions": 1,
            "decay_decisions": 1,
            "initial_epsilon": 1.0,
            "final_epsilon": 0.1,
            "trace_sample_completed_transition_counts": [],
            "selection_count": 1,
        },
        "determinism": {
            "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
            "deterministic_algorithms": True,
        },
    }
    monkeypatch.setattr(update_gate, "BDQOptimizationSettings", Settings)
    monkeypatch.setattr(update_gate, "configure_torch", lambda *args: None)
    controller_box: list[SimpleNamespace] = []

    class Replay:
        def __len__(self) -> int:
            return controller_box[0].decision_count

    class Controller:
        def __init__(self, seed: int, settings: Settings) -> None:
            self.seed = seed
            self.settings = settings
            self.decision_count = 0
            self.optimizer_update_count = 0
            self.target_sync_count = 0
            self.online_network = object()
            self.target_network = object()
            self.replay = Replay()
            self.online_changed = False
            controller_box.append(self)

    monkeypatch.setattr(update_gate, "BDQOptimizerController", Controller)

    class Collector:
        def __init__(self, controller: Any) -> None:
            self.pending_agent_ids: list[int] = []

        def begin(
            self,
            agent_id: int,
            observation: Any,
            action: Any,
            action_masks: Any,
        ) -> None:
            self.pending_agent_ids.append(agent_id)

    monkeypatch.setattr(update_gate, "DirectReplayCollector", Collector)

    class Schedule:
        replay_warmup_decisions = 1

        def epsilon_at(self, _completed_transition_count: int) -> float:
            return 1.0

    class Selector:
        def __init__(self, network: Any, schedule: Any, seed: int) -> None:
            self.schedule = schedule
            self.seed = seed

        def select(self, observation: Any, action_masks: Any, *, completed_transition_count: int) -> np.ndarray:
            return np.asarray([0, 0], dtype=np.int32)

    monkeypatch.setattr(update_gate, "ScheduledEpsilonGreedyBDQActionSelector", Selector)
    monkeypatch.setattr(
        update_gate,
        "LinearEpsilonSchedule",
        lambda **kwargs: Schedule(),
    )
    monkeypatch.setattr(update_gate, "validate_basic_behavior_spec", lambda spec: None)
    monkeypatch.setattr(
        update_gate,
        "validate_observation",
        lambda observation, label: np.zeros((84, 84, 4), dtype=np.float32),
    )
    monkeypatch.setattr(
        update_gate,
        "read_action_masks",
        lambda steps, row: (
            np.zeros(3, dtype=np.bool_),
            np.zeros(2, dtype=np.bool_),
        ),
    )
    def fake_network_sha256(network: Any) -> str:
        controller = controller_box[0]
        if network is controller.target_network:
            return "target"
        return "online-after" if controller.online_changed else "target"

    monkeypatch.setattr(update_gate, "network_sha256", fake_network_sha256)

    def fake_complete(
        collector: Collector,
        agent_id: int,
        reward: float,
        next_observation: Any,
        next_action_masks: Any,
        *,
        terminated: bool,
        truncated: bool,
        transitions: list[dict[str, Any]],
        optimization_events: list[dict[str, Any]],
        episode_index: int,
        episode_decision_index: int,
        expected_update_decisions: Any,
        task_name: str,
        allowed_target_sync_updates: Any,
    ) -> Any:
        controller = controller_box[0]
        collector.pending_agent_ids.remove(agent_id)
        controller.decision_count += 1
        controller.optimizer_update_count += 1
        controller.online_changed = True
        transition = {
            "action": [0, 0],
            "terminated": terminated,
            "truncated": truncated,
        }
        transitions.append(transition)
        result = SimpleNamespace(
            decision_count=1,
            replay_size=1,
            optimizer_update_count=1,
            target_sync_count=0,
            updated=True,
            target_synced=False,
            loss=0.25,
            mean_absolute_td_error=0.5,
        )
        optimization_events.append(update_gate._optimization_event(result))
        return result

    monkeypatch.setattr(update_gate, "_complete_gate_transition", fake_complete)
    captured_options: list[dict[str, Any]] = []

    class Steps:
        def __init__(self, *, terminal: bool = False, empty: bool = False) -> None:
            self.agent_id = np.asarray([], dtype=np.int32) if empty else np.asarray([1], dtype=np.int32)
            self.obs = [np.zeros((0 if empty else 1, 84, 84, 4), dtype=np.float32)]
            self.reward = np.asarray([], dtype=np.float32) if empty else np.asarray([1.0], dtype=np.float32)
            self.interrupted = np.asarray([], dtype=np.bool_) if empty else np.asarray([False], dtype=np.bool_)

        def __len__(self) -> int:
            return len(self.agent_id)

    class Environment:
        def __init__(self, **options: Any) -> None:
            captured_options.append(options)
            self.behavior_specs = {"QuickDrawResearchBasic?team=0": object()}
            self.phase = 0
            self.closed = False

        def reset(self) -> None:
            pass

        def get_steps(self, behavior_id: str) -> tuple[Steps, Steps]:
            if self.phase == 0:
                return Steps(), Steps(empty=True)
            return Steps(empty=True), Steps(terminal=True)

        def set_actions(self, behavior_id: str, actions: Any) -> None:
            pass

        def step(self) -> None:
            self.phase = 1

        def close(self) -> None:
            self.closed = True

    observed: list[tuple[Any, ...]] = []
    worker_output = tmp_path / "worker"
    contract_path = tmp_path / "contract.json"
    contract_path.write_text("{}\n", encoding="utf-8")
    trace = update_gate.execute_update_gate_worker(
        tmp_path / "player.exe",
        worker_output,
        0,
        contract,
        contract_path=contract_path,
        trace_file_name="trace.json",
        trace_schema_version="test.v1",
        task_name="R3T observer test",
        record_update_hashes=True,
        environment_factory=Environment,
        profiling_output_directory="profile",
        update_observer=lambda *args: observed.append(args),
    )

    assert trace["optimization"]["optimizer_update_count"] == 1
    assert len(observed) == 1
    assert observed[0][3].optimizer_update_count == 1
    assert captured_options[0]["log_folder"] == str(worker_output / "profile")


@pytest.mark.parametrize(
    "profiling_output_directory",
    [r"C:temp", r"\temp", r"/temp", r"C:\temp"],
)
def test_profiling_output_rejects_windows_rooted_and_drive_relative_paths(
    tmp_path: Path, profiling_output_directory: str
) -> None:
    worker_output = tmp_path / "worker"
    worker_output.mkdir()
    with pytest.raises(LLAPIContractError, match="safe relative path"):
        update_gate._profiling_output_path(
            worker_output,
            profiling_output_directory,
            "R3T profiling path test",
        )
