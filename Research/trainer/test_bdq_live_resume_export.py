from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.acceptance import canonical_json_sha256  # noqa: E402
from quickdraw_bdq.llapi import LLAPIContractError  # noqa: E402
from quickdraw_bdq.provenance import (  # noqa: E402
    directory_file_manifest,
    process_creation_marker,
    sha256_file,
)
from quickdraw_bdq.replay import ReplayBuffer, ReplayTransition  # noqa: E402
import run_bdq_live_resume_export_smoke as runner  # noqa: E402
from run_bdq_live_resume_export_smoke import (  # noqa: E402
    CONTRACT_PATH,
    CONTRACT_SCHEMA_PATH,
    RESULT_SCHEMA_PATH,
    _mask_pattern_indices,
    _masked_actions,
    validate_contract,
    validate_observation_batch,
    validate_result,
)


HASH = "a" * 64


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contract() -> dict[str, Any]:
    return _read(CONTRACT_PATH)


def _identity(pid: int, marker: int) -> dict[str, Any]:
    return {
        "pid": pid,
        "creation_marker": {
            "kind": "windows_filetime_100ns_since_1601",
            "value": marker,
        },
        "executable_sha256": HASH,
    }


def _valid_result(contract: dict[str, Any]) -> dict[str, Any]:
    observation_hash = "1" * 64
    next_observation_hash = "2" * 64
    action_hash = "3" * 64
    output_hash = "4" * 64
    masks = [[False, True, False], [False, True]]
    replay = {
        "capacity": 100000,
        "size": 49997,
        "cursor": 49997,
        "unique_frame_count": 10,
        "frame_reference_count": 399976,
        "frame_payload_bytes": 1,
        "metadata_payload_bytes": 1,
        "accounted_storage_bytes": 2,
        "max_accounted_storage_bytes": 4294967296,
        "remaining_accounted_storage_bytes": 4294967294,
        "legacy_observation_payload_bytes": 1,
        "legacy_capacity_observation_payload_bytes": 1,
    }
    live_resume = {
        "schema_version": "quickdraw.r3s-live-resume-attempt.v1",
        "start_boundary": copy.deepcopy(contract["live_handoff"]["start_boundary"]),
        "existing_decision": {
            "behavior_id": "QuickDrawResearchBasic?team=0",
            "agent_id": 0,
            "observation_sha256": observation_hash,
            "action_masks": masks,
        },
        "selected_action": [0, 0],
        "transition": {
            "index": 49996,
            "episode_index": 4,
            "episode_decision_index": 12,
            "observation_sha256": observation_hash,
            "next_observation_sha256": next_observation_hash,
            "observation_shape": [84, 84, 4],
            "action": [0, 0],
            "reward": 0.0,
            "action_masks": masks,
            "next_action_masks": masks,
            "terminated": False,
            "truncated": False,
        },
        "final_boundary": {
            **copy.deepcopy(contract["live_handoff"]["final_boundary"]),
            "online_network_sha256": contract["export"]["source_network_sha256"],
            "target_network_sha256": contract["export"]["source_network_sha256"],
            "checkpoint_state_sha256": "5" * 64,
            "checkpoint_sha256": "6" * 64,
            "replay": replay,
        },
        "post_resume_observation": {
            "sha256": next_observation_hash,
            "file_sha256": "7" * 64,
            "action_masks": masks,
        },
        "optimizer_updated": False,
        "target_synchronized": False,
        "held_decision_agent_ids": [0],
        "terminal_agent_ids": [],
    }
    canonical = {
        "r3r_trace_sha256": contract["accepted_r3r"]["trace"]["sha256"],
        "r3r_checkpoint_sha256": contract["accepted_r3r"]["checkpoint"]["sha256"],
        "r3r_checkpoint_state_sha256": contract["accepted_r3r"]["checkpoint"][
            "state_sha256"
        ],
        "handoff": {
            "protocol": contract["live_handoff"]["protocol"],
            "event_sequence": copy.deepcopy(
                contract["live_handoff"]["canonical_event_sequence"]
            ),
            "environment_counters": {
                key: contract["live_handoff"]["environment_counters"][key]
                for key in (
                    "launches",
                    "resets_before_handoff",
                    "steps_before_handoff",
                    "resumed_actions",
                    "steps_after_handoff",
                )
            },
            "behavior_id": "QuickDrawResearchBasic?team=0",
            "agent_id": 0,
            "same_player_process": True,
            "same_player_copy": True,
            "fresh_trainer_process": True,
            "reset_during_handoff": False,
            "relaunch_during_handoff": False,
            "extra_environment_step": False,
            "discarded_decision": False,
        },
        "live_resume": live_resume,
    }

    attempts = []
    for attempt_index in (1, 2):
        attempts.append(
            {
                "schema_version": "quickdraw.r3s-attempt.v1",
                "attempt_index": attempt_index,
                "canonical_sha256": canonical_json_sha256(canonical),
                "canonical": copy.deepcopy(canonical),
                "provenance": {
                    "initial_trainer_identity": _identity(attempt_index * 10, 100),
                    "restored_trainer_identity": _identity(
                        attempt_index * 10 + 1, 101
                    ),
                    "player_identity_before": _identity(
                        attempt_index * 10 + 2, 102
                    ),
                    "player_identity_after": _identity(
                        attempt_index * 10 + 2, 102
                    ),
                    "player_copy": "player-copy",
                    "player_launch_command": ["player.exe"],
                    "restored_trainer_command": ["python.exe", "runner.py"],
                    "loopback_host": "127.0.0.1",
                    "loopback_port": 5100 + attempt_index,
                    "restored_trainer_log": "restored.log",
                    "player_manifest_sha256": contract["player"][
                        "source_manifest_sha256"
                    ],
                    "player_manifest_path": "manifest.json",
                    "r3r_trace_path": "trace.json",
                    "r3r_checkpoint_path": "checkpoint.json",
                    "player_process_stopped_after_attempt": True,
                },
            }
        )

    graph = {
        "ir_version": 8,
        "opsets": [{"domain": "", "version": contract["export"]["opset"]}],
        "inputs": [
            {
                "name": "observations",
                "element_type": 1,
                "shape": ["N", 84, 84, 4],
            }
        ],
        "outputs": [
            {
                "name": "branch_0_q_values",
                "element_type": 1,
                "shape": ["N", 3],
            },
            {
                "name": "branch_1_q_values",
                "element_type": 1,
                "shape": ["N", 2],
            },
        ],
    }
    inference_attempts = []
    for index in (1, 2):
        inference_attempts.append(
            {
                "schema_version": "quickdraw.bdq-onnx-parity-worker.v1",
                "process_identity": _identity(100 + index, 200 + index),
                "onnx_sha256": "8" * 64,
                "corpus_sha256": "9" * 64,
                "output_file_sha256": str(index) * 64,
                "canonical_outputs_sha256": output_hash,
                "actions_sha256": action_hash,
                "maximum_absolute_difference": 0.0,
                "single_item_maximum_absolute_difference": 0.0,
                "all_outputs_finite": True,
                "all_actions_match": True,
                "single_and_batched_inference": True,
                "input_shape": [64, 84, 84, 4],
                "output_shapes": [[64, 3], [64, 2]],
                "output_dtype": "float32",
            }
        )
    return {
        "schema_version": "quickdraw.bdq-live-resume-export-result.v1",
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "status": "accepted",
        "starting_boundary": copy.deepcopy(contract["accepted_r3r"]),
        "live_resume": {
            "fresh_attempt_count": 2,
            "exact_canonical_match": True,
            "canonical_attempt_sha256": attempts[0]["canonical_sha256"],
            "attempts": attempts,
        },
        "export_parity": {
            "export_metadata": {
                "schema_version": "quickdraw.bdq-onnx-export.v1",
                "source_network_sha256_before": contract["export"][
                    "source_network_sha256"
                ],
                "source_network_sha256_after": contract["export"][
                    "source_network_sha256"
                ],
                "onnx_sha256": "8" * 64,
                "onnx_bytes": 1,
                "exporter": contract["export"]["exporter"],
                "torch_version": contract["runtime"]["torch"],
                "onnx_version": contract["export_dependencies"]["onnx"],
                "onnxruntime_version": contract["export_dependencies"][
                    "onnxruntime"
                ],
                "opset": contract["export"]["opset"],
                "graph": graph,
            },
            "corpus": {
                "schema_version": contract["export"]["parity_corpus"][
                    "schema_version"
                ],
                "selection_rule": contract["export"]["parity_corpus"][
                    "selection_rule"
                ],
                "count": 64,
                "accepted_checkpoint_indices": list(range(63)),
                "post_resume_attempts": [1, 2],
                "mask_patterns": [[False, True, False, False, True]],
                "observation_minimum": 0.0,
                "observation_maximum": 1.0,
                "corpus_file_sha256": "9" * 64,
                "corpus_content_sha256": "b" * 64,
                "python_q_values_sha256": "c" * 64,
                "python_actions_sha256": action_hash,
            },
            "fresh_inference_process_count": 2,
            "exact_repeat_outputs": True,
            "inference": copy.deepcopy(inference_attempts[0]),
            "inference_attempts": inference_attempts,
        },
        "claim_boundary": {
            "live_unity_process_continuity": True,
            "exported_inference_software_parity": True,
            "policy_effectiveness": False,
            "convergence": False,
            "held_out_evaluation": False,
        },
    }


def _recompute_attempt_hashes(result: dict[str, Any]) -> None:
    for attempt in result["live_resume"]["attempts"]:
        attempt["canonical_sha256"] = canonical_json_sha256(attempt["canonical"])
    result["live_resume"]["canonical_attempt_sha256"] = result["live_resume"][
        "attempts"
    ][0]["canonical_sha256"]


def _validate_without_artifacts(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any], contract: dict[str, Any]
) -> None:
    monkeypatch.setattr(runner, "_validate_result_artifacts", lambda *args: None)
    validate_result(result, _read(RESULT_SCHEMA_PATH), contract, artifact_root=ROOT)


def test_r3s_contract_schemas_bind_the_registered_boundary() -> None:
    contract = _contract()
    contract_schema = _read(CONTRACT_SCHEMA_PATH)
    result_schema = _read(RESULT_SCHEMA_PATH)
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    validate_contract(contract)

    assert contract["live_handoff"]["start_boundary"]["transition_count"] == 49996
    assert contract["live_handoff"]["final_boundary"]["transition_count"] == 49997
    assert contract["export"]["opset"] == 17
    assert contract["export"]["parity_corpus"]["count"] == 64
    assert contract["export"]["maximum_absolute_difference"] == 1e-5


def test_r3s_contract_rejects_a_stale_r3r_result_hash() -> None:
    contract = _contract()
    contract["accepted_r3r"]["result"]["sha256"] = HASH
    with pytest.raises(LLAPIContractError, match="Hash binding drifted"):
        validate_contract(contract)


def test_r3s_result_runs_generic_schema_validation_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    result = _valid_result(contract)
    del result["export_parity"]["inference"]["output_dtype"]
    monkeypatch.setattr(
        runner,
        "_validate_result_artifacts",
        lambda *args: pytest.fail("artifact checks ran before schema validation"),
    )
    with pytest.raises(ValidationError):
        validate_result(result, _read(RESULT_SCHEMA_PATH), contract, artifact_root=ROOT)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["live_resume"]["attempts"][0]["canonical"].update(
                {"r3r_trace_sha256": HASH}
            ),
            "canonical live attempts differ",
        ),
        (
            lambda value: [
                attempt["canonical"]["live_resume"]["start_boundary"].update(
                    {"decision_count": 49995}
                )
                for attempt in value["live_resume"]["attempts"]
            ],
            "live starting boundary drifted",
        ),
        (
            lambda value: [
                attempt["canonical"]["live_resume"]["final_boundary"].update(
                    {"decision_count": 49998}
                )
                for attempt in value["live_resume"]["attempts"]
            ],
            "live final decision_count drifted",
        ),
        (
            lambda value: [
                attempt["canonical"]["live_resume"]["final_boundary"][
                    "replay"
                ].update({"size": 49998})
                for attempt in value["live_resume"]["attempts"]
            ],
            "final replay state drifted",
        ),
        (
            lambda value: [
                attempt["canonical"]["live_resume"]["final_boundary"].update(
                    {"online_network_sha256": HASH}
                )
                for attempt in value["live_resume"]["attempts"]
            ],
            "network changed after live resume",
        ),
        (
            lambda value: [
                attempt["canonical"]["live_resume"].update(
                    {"selected_action": [1, 0]}
                )
                for attempt in value["live_resume"]["attempts"]
            ],
            "live action was masked",
        ),
        (
            lambda value: [
                attempt["canonical"]["live_resume"]["transition"].update(
                    {"observation_sha256": HASH}
                )
                for attempt in value["live_resume"]["attempts"]
            ],
            "transition boundary data drifted",
        ),
        (
            lambda value: [
                attempt["canonical"]["handoff"].update(
                    {"event_sequence": list(reversed(attempt["canonical"]["handoff"]["event_sequence"]))}
                )
                for attempt in value["live_resume"]["attempts"]
            ],
            "handoff event sequence drifted",
        ),
    ],
)
def test_r3s_result_rejects_canonical_live_drift(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], Any],
    message: str,
) -> None:
    contract = _contract()
    result = _valid_result(contract)
    mutate(result)
    _recompute_attempt_hashes(result)
    with pytest.raises(LLAPIContractError, match=message):
        _validate_without_artifacts(monkeypatch, result, contract)


def test_r3s_result_rejects_player_process_identity_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract()
    result = _valid_result(contract)
    result["live_resume"]["attempts"][0]["provenance"][
        "player_identity_after"
    ]["creation_marker"]["value"] += 1
    with pytest.raises(LLAPIContractError, match="player PID/start marker changed"):
        _validate_without_artifacts(monkeypatch, result, contract)


@pytest.mark.parametrize("held_ids", [[], [0]])
def test_r3s_result_accepts_terminal_with_optional_next_decision(
    monkeypatch: pytest.MonkeyPatch, held_ids: list[int]
) -> None:
    contract = _contract()
    result = _valid_result(contract)
    for attempt in result["live_resume"]["attempts"]:
        live = attempt["canonical"]["live_resume"]
        live["transition"]["terminated"] = True
        live["held_decision_agent_ids"] = held_ids
        live["terminal_agent_ids"] = [0]
    _recompute_attempt_hashes(result)
    _validate_without_artifacts(monkeypatch, result, contract)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["export_parity"]["export_metadata"].update(
                {"opset": 16}
            ),
            "export metadata or interface drifted",
        ),
        (
            lambda value: value["export_parity"]["corpus"].update(
                {"selection_rule": "different"}
            ),
            "parity corpus metadata drifted",
        ),
        (
            lambda value: [
                value["export_parity"][key].update(
                    {"maximum_absolute_difference": 2e-5}
                )
                for key in ("inference",)
            ]
            + [
                value["export_parity"]["inference_attempts"][0].update(
                    {"maximum_absolute_difference": 2e-5}
                )
            ],
            "ONNX parity requirement failed",
        ),
        (
            lambda value: value["export_parity"]["inference_attempts"][1].update(
                {"canonical_outputs_sha256": HASH}
            ),
            "repeat inference drifted",
        ),
        (
            lambda value: value["export_parity"]["inference_attempts"][1][
                "process_identity"
            ].update(
                copy.deepcopy(
                    value["export_parity"]["inference_attempts"][0][
                        "process_identity"
                    ]
                )
            ),
            "were not fresh processes",
        ),
    ],
)
def test_r3s_result_rejects_export_drift(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, Any]], Any],
    message: str,
) -> None:
    contract = _contract()
    result = _valid_result(contract)
    mutation(result)
    with pytest.raises(LLAPIContractError, match=message):
        _validate_without_artifacts(monkeypatch, result, contract)


def test_r3s_result_rejects_missing_retained_artifacts(tmp_path: Path) -> None:
    contract = _contract()
    with pytest.raises(FileNotFoundError):
        validate_result(
            _valid_result(contract),
            _read(RESULT_SCHEMA_PATH),
            contract,
            artifact_root=tmp_path,
        )


def test_r3s_masked_argmax_is_legal_and_uses_lowest_index_ties() -> None:
    q_values = (
        np.asarray([[1.0, 9.0, 1.0]], dtype=np.float32),
        np.asarray([[2.0, 2.0]], dtype=np.float32),
    )
    masks = (
        np.asarray([[False, True, False]], dtype=np.bool_),
        np.asarray([[False, False]], dtype=np.bool_),
    )
    assert _masked_actions(q_values, masks).tolist() == [[0, 0]]
    masks[1][0, 0] = True
    assert _masked_actions(q_values, masks).tolist() == [[0, 1]]
    masks[1][0, 1] = True
    with pytest.raises(LLAPIContractError, match="masks every action"):
        _masked_actions(q_values, masks)


def _loaded_with_replay_masks(
    branch_0_masks: np.ndarray, branch_1_masks: np.ndarray
) -> SimpleNamespace:
    replay = SimpleNamespace(
        export_checkpoint_state=lambda: {
            "size": int(branch_0_masks.shape[0]),
            "action_masks": (branch_0_masks, branch_1_masks),
        }
    )
    return SimpleNamespace(controller=SimpleNamespace(replay=replay))


def test_r3s_parity_corpus_rejects_mask_pattern_overflow() -> None:
    loaded = _loaded_with_replay_masks(
        np.asarray([[False, False, False], [True, False, False]], dtype=np.bool_),
        np.asarray([[False, False], [False, False]], dtype=np.bool_),
    )
    with pytest.raises(LLAPIContractError, match="too small for mask coverage"):
        _mask_pattern_indices(loaded, 1)


def test_r3s_parity_corpus_rejects_missing_checkpoint_rows() -> None:
    loaded = _loaded_with_replay_masks(
        np.zeros((2, 3), dtype=np.bool_),
        np.zeros((2, 2), dtype=np.bool_),
    )
    with pytest.raises(LLAPIContractError, match="omitted checkpoint rows"):
        _mask_pattern_indices(loaded, 3)


@pytest.mark.parametrize(
    "value",
    [
        np.zeros((84, 84, 4), dtype=np.float32),
        np.zeros((1, 84, 84, 4), dtype=np.float64),
        np.full((1, 84, 84, 4), np.nan, dtype=np.float32),
        np.full((1, 84, 84, 4), 1.01, dtype=np.float32),
    ],
)
def test_r3s_observation_batch_rejects_interface_drift(value: np.ndarray) -> None:
    with pytest.raises(LLAPIContractError):
        validate_observation_batch(value)


def test_explicit_replay_batch_preserves_order_and_rng_state() -> None:
    replay = ReplayBuffer(capacity=4, seed=13)
    masks = (
        np.asarray([False, False, False], dtype=np.bool_),
        np.asarray([False, False], dtype=np.bool_),
    )
    for index in range(3):
        observation = np.full((84, 84, 4), index / 10.0, dtype=np.float32)
        next_observation = np.full(
            (84, 84, 4), (index + 1) / 10.0, dtype=np.float32
        )
        replay.add(
            ReplayTransition(
                observation=observation,
                action=np.asarray([index % 3, index % 2], dtype=np.int64),
                reward=float(index),
                next_observation=next_observation,
                action_masks=masks,
                next_action_masks=masks,
                terminated=False,
                truncated=False,
            )
        )
    rng_before = copy.deepcopy(
        replay.export_checkpoint_state()["replay_bit_generator_state"]
    )
    batch = replay.batch_at_indices([2, 0])
    rng_after = replay.export_checkpoint_state()["replay_bit_generator_state"]
    assert batch.indices.tolist() == [2, 0]
    assert batch.rewards.tolist() == [2.0, 0.0]
    assert np.array_equal(batch.observations[0], np.full((84, 84, 4), 0.2, dtype=np.float32))
    assert rng_before == rng_after
    with pytest.raises(IndexError, match="outside the live buffer"):
        replay.batch_at_indices([3])
    with pytest.raises(TypeError, match="integer dtype"):
        replay.batch_at_indices([1.0])


def test_directory_manifest_is_copy_path_independent(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "asset.bin").write_bytes(b"asset")
    (second / "asset.bin").write_bytes(b"asset")
    assert directory_file_manifest(first) == directory_file_manifest(second)


@pytest.mark.skipif(sys.platform != "win32", reason="R3S is a Windows Unity gate")
def test_process_creation_marker_is_stable_for_the_live_process() -> None:
    first = process_creation_marker(os.getpid())
    second = process_creation_marker(os.getpid())
    assert first == second
    assert first["kind"] == "windows_filetime_100ns_since_1601"
    assert first["value"] > 0
