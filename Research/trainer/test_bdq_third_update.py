from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.provenance import runtime_contract, sha256_file  # noqa: E402
from quickdraw_bdq import BDQOptimizationSettings, LinearEpsilonSchedule  # noqa: E402
from quickdraw_bdq.acceptance import (  # noqa: E402
    registered_settings as _registered_settings,
)
from run_bdq_third_update_smoke import validate_contract


CONTRACT_PATH = HERE / "bdq-third-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-third-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-third-update-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"


def test_r3k_contract_schemas_binding_runtime_and_boundaries_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_scheduled_handoff_contract"]
    assert sha256_file(ROOT / binding["path"]) == binding["sha256"]
    assert contract["runtime"] == runtime_contract()
    assert pyproject["project"]["name"] == contract["package"]["distribution"]
    assert pyproject["project"]["version"] == contract["package"]["version"]
    assert "entry-points" not in pyproject["project"]

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    assert _registered_settings(settings) == {
        key: optimization[key] for key in _registered_settings(settings)
    }
    assert optimization["expected_update_decisions"] == [10_000, 10_004, 10_008]
    assert optimization["expected_optimizer_updates"] == 3
    assert optimization["expected_target_synchronizations"] == 0
    assert contract["collection"]["transition_limit"] == 10_008
    assert contract["r3j_prefix"]["transition_count"] == 10_005
    assert contract["third_update_boundary"]["new_transition_count"] == 3
    assert (
        contract["third_update_boundary"]["select_action_after_third_update"]
        is False
    )

    schedule = LinearEpsilonSchedule()
    assert [schedule.epsilon_at(count) for count in (10_005, 10_006, 10_007)] == [
        0.999955,
        0.999946,
        0.999937,
    ]
    assert contract["epsilon_schedule"]["selection_count"] == 10_008
    assert contract["epsilon_schedule"]["decay_selection_count"] == 7
    assert contract["epsilon_schedule"][
        "last_selection_completed_transition_count"
    ] == 10_007
    assert "scheduled_epsilon_handoff" not in contract
    assert validate_contract(contract) == result_schema
