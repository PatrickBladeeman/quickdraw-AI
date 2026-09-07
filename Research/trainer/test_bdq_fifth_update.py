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
from run_bdq_fifth_update_smoke import validate_contract


CONTRACT_PATH = HERE / "bdq-fifth-update-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-fifth-update-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    ROOT
    / "Research"
    / "schemas"
    / "bdq-fifth-update-smoke-result.schema.json"
)
PYPROJECT_PATH = HERE / "pyproject.toml"
PROJECT_SETTINGS_PATH = ROOT / "ProjectSettings" / "ProjectSettings.asset"


def test_r3o_contract_schemas_binding_runtime_and_boundaries_are_exact() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    binding = contract["base_fourth_update_contract"]
    assert sha256_file(ROOT / binding["path"]) == binding["sha256"]
    storage_binding = contract["base_replay_storage_contract"]
    assert sha256_file(ROOT / storage_binding["path"]) == storage_binding["sha256"]
    assert contract["runtime"] == runtime_contract()
    assert pyproject["project"]["name"] == contract["package"]["distribution"]
    assert pyproject["project"]["version"] == contract["package"]["version"]
    assert "entry-points" not in pyproject["project"]
    assert contract["player_execution"] == {
        "project_settings_path": "ProjectSettings/ProjectSettings.asset",
        "run_in_background": True,
        "no_graphics": False,
        "standalone_player_arguments": [],
    }
    assert "  runInBackground: 1" in PROJECT_SETTINGS_PATH.read_text(
        encoding="utf-8"
    ).splitlines()

    settings = BDQOptimizationSettings()
    optimization = contract["optimization"]
    assert _registered_settings(settings) == {
        key: optimization[key] for key in _registered_settings(settings)
    }
    assert optimization["expected_update_decisions"] == [
        10_000,
        10_004,
        10_008,
        10_012,
        10_016,
    ]
    assert optimization["expected_optimizer_updates"] == 5
    assert optimization["expected_target_synchronizations"] == 0
    assert contract["collection"]["transition_limit"] == 10_016
    assert contract["r3m_prefix"]["transition_count"] == 10_012
    assert contract["fifth_update_boundary"]["new_transition_count"] == 4
    assert (
        contract["fifth_update_boundary"]["select_action_after_fifth_update"]
        is False
    )

    schedule = LinearEpsilonSchedule()
    assert [
        schedule.epsilon_at(count)
        for count in (10_012, 10_013, 10_014, 10_015)
    ] == [
        0.999892,
        0.999883,
        0.999874,
        0.999865,
    ]
    assert contract["epsilon_schedule"]["selection_count"] == 10_016
    assert contract["epsilon_schedule"]["decay_selection_count"] == 15
    assert contract["epsilon_schedule"][
        "last_selection_completed_transition_count"
    ] == 10_015
    assert "scheduled_epsilon_handoff" not in contract
    assert validate_contract(contract) == result_schema
