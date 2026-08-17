from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from jsonschema import Draft202012Validator

from r1f_fixed_policy import (
    POLICY_SEED,
    FixedPolicyDriver,
    create_checkpoint,
    deterministic_state_dict,
    parameter_specification,
    sha256_file,
    state_dict_sha256,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_name("backend-parity-contract-v1.json")
PROCEDURE_PATH = Path(__file__).with_name("amd-parity-procedure-v1.json")
RESULT_SCHEMA_PATH = ROOT / "Research" / "schemas" / "backend-parity-result.schema.json"
RESULT_PATH = Path(__file__).with_name("amd-backend-parity-result-v1.json")


def test_fixed_policy_state_is_seeded_and_canonical() -> None:
    first = deterministic_state_dict(POLICY_SEED)
    second = deterministic_state_dict(POLICY_SEED)
    different = deterministic_state_dict(POLICY_SEED + 1)

    assert list(first) == [item["name"] for item in parameter_specification()]
    assert state_dict_sha256(first) == state_dict_sha256(second)
    assert state_dict_sha256(first) != state_dict_sha256(different)
    assert all(tensor.dtype == torch.float32 for tensor in first.values())


def test_fixed_policy_checkpoint_reload_keeps_registered_actions(tmp_path: Path) -> None:
    checkpoint = tmp_path / "fixed-policy.pt"
    model = tmp_path / "fixed-policy.onnx"
    create_checkpoint(checkpoint, POLICY_SEED)
    model.write_bytes(b"hash-only test fixture")
    driver = FixedPolicyDriver(checkpoint, model, "cpu")

    observations = [
        np.asarray([0.0, 4.0, 0.0, 0.25], dtype=np.float32),
        np.asarray([4.0, 0.0, 0.5, 0.75], dtype=np.float32),
    ]
    masks = [
        [[False, True, False], [False, True]],
        [[False, False, True], [False, True]],
    ]
    for observation, action_mask in zip(observations, masks):
        movement, submit, logits = driver.act(observation, action_mask)
        assert [movement, submit] == [0, 0]
        assert [len(branch) for branch in logits] == [3, 2]
        assert np.isfinite(
            np.asarray([value for branch in logits for value in branch], dtype=np.float32)
        ).all()


def test_backend_parity_contract_matches_frozen_r1f_procedure() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    procedure = json.loads(PROCEDURE_PATH.read_text(encoding="utf-8"))
    assert contract["policy"]["seed"] == POLICY_SEED
    assert contract["scenario_base_seed"] == 21001
    assert contract["measurement"]["warmup_decision_count"] == procedure["throughput_gate"]["warmup_decisions"]
    assert contract["measurement"]["decision_count"] == procedure["throughput_gate"]["decision_count_per_run"]
    assert contract["comparison"]["runs_per_backend"] == procedure["throughput_gate"]["measured_runs_per_backend"]
    assert contract["comparison"]["logit_max_abs_tolerance"] == procedure["correctness_gates"]["float32_max_abs_tolerance"]
    assert [episode["role"] for episode in contract["episodes"]] == ["warmup", "measured"]
    assert contract["episodes"][0]["seed_offset"] == contract["episodes"][1]["seed_offset"] == 0


def test_backend_parity_result_schema_is_valid() -> None:
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(result)
    assert result["status"] == "accepted"
    assert result["correctness"]["passed"] is True
    assert result["throughput"]["passed"] is True
    assert result["decision"]["selected_backend"] == "rocm"
    assert result["procedure"]["sha256"] == sha256_file(PROCEDURE_PATH)
    assert result["contract"]["sha256"] == sha256_file(CONTRACT_PATH)
