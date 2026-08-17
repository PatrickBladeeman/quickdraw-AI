from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_ROOT = REPO_ROOT / "Research" / "environment"
SCHEMA_ROOT = REPO_ROOT / "Research" / "schemas"
CONTRACT_PATH = (
    ENVIRONMENT_ROOT / "mlagents-rocm-compatibility-contract-v1.json"
)
RESULT_PATH = (
    ENVIRONMENT_ROOT / "rocm-mlagents-compatibility-result-v1.json"
)
RESULT_SCHEMA_PATH = SCHEMA_ROOT / "rocm-mlagents-compatibility.schema.json"
SUPPORT_LOCK_PATH = (
    ENVIRONMENT_ROOT / "requirements-rocm-py311-support-lock.txt"
)
CPU_LOCK_PATH = ENVIRONMENT_ROOT / "requirements-lock.txt"
BUILDER_PATH = ENVIRONMENT_ROOT / "build_mlagents_py311_overlay.py"
PREPARER_PATH = ENVIRONMENT_ROOT / "prepare_rocm_mlagents_py311.py"
PROBE_PATH = ENVIRONMENT_ROOT / "probe_rocm_mlagents_compatibility.py"
SMOKE_RUNNER_PATH = REPO_ROOT / "Research" / "smoke" / "run_smoke.py"
MANIFEST_SCHEMA_PATH = SCHEMA_ROOT / "run-manifest.schema.json"
PARITY_PATH = ENVIRONMENT_ROOT / "amd-parity-procedure-v1.json"
PARITY_RESULT_PATH = ENVIRONMENT_ROOT / "amd-backend-parity-result-v1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_curated_result_validates_and_hashes_exact_inputs() -> None:
    schema = read_json(RESULT_SCHEMA_PATH)
    result = read_json(RESULT_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(result)

    paths = {
        "contract_sha256": CONTRACT_PATH,
        "support_lock_sha256": SUPPORT_LOCK_PATH,
        "builder_sha256": BUILDER_PATH,
        "preparer_sha256": PREPARER_PATH,
        "probe_sha256": PROBE_PATH,
        "result_schema_sha256": RESULT_SCHEMA_PATH,
        "manifest_schema_sha256": MANIFEST_SCHEMA_PATH,
        "cpu_lock_sha256": CPU_LOCK_PATH,
    }
    for field, path in paths.items():
        assert result["inputs"][field] == sha256_file(path)
    # R1E records the historical runner it executed. R1F extends that runner
    # without rewriting the already-curated R1E evidence hash.
    assert result["inputs"]["smoke_runner_sha256"] == (
        "99c833672fb1b3b9cc941f7ccf3815d771813574b6c678d6da5cedb4e9e2074f"
    )


def test_compatibility_is_conditional_and_never_accepts_rocm() -> None:
    result = read_json(RESULT_PATH)
    assert result["decision"] == {
        "backend_acceptance": "not_accepted",
        "cpu_reference_retained": True,
        "full_parity_executed": False,
        "status": "conditional_go",
    }
    assert result["software"]["packages"]["mlagents"] == "1.1.0"
    assert result["software"]["python_version"] == "3.11.13"
    assert result["rocm"]["selected_device"]["name"] == (
        "AMD Radeon RX 7900 XT"
    )
    assert result["communicator"]["traces_identical"] is True


def test_overlay_is_metadata_only_and_sources_are_registered() -> None:
    contract = read_json(CONTRACT_PATH)
    overlay = contract["metadata_overlay"]
    exception = contract["transitive_metadata_exception"]
    assert overlay["runtime_code_changes"] is False
    assert overlay["requires_python_after"] == ">=3.10.1,<3.12"
    assert overlay["selected_grpcio"] == "1.53.2"
    assert len(overlay["overlay_wheels"]) == 2
    assert exception["package"] == "PettingZoo"
    assert exception["runtime_code_changes"] is False
    assert contract["official_support"]["gpu_listed_exactly"] is True


def test_cpu_and_multisource_locks_remain_separate() -> None:
    cpu_lock = CPU_LOCK_PATH.read_text(encoding="utf-8")
    support_lock = SUPPORT_LOCK_PATH.read_text(encoding="utf-8")
    assert "torch==2.2.1+cpu" in cpu_lock
    assert "rocm" not in cpu_lock.lower()
    assert "grpcio==1.53.2" in support_lock
    assert "numpy==1.23.5" in support_lock
    assert "mlagents==" not in support_lock.lower()
    assert "torch==" not in support_lock.lower()
    assert sha256_file(CPU_LOCK_PATH) != sha256_file(SUPPORT_LOCK_PATH)


def test_official_rocm_support_and_executed_parity_boundary_are_synchronized() -> None:
    contract = read_json(CONTRACT_PATH)
    parity = read_json(PARITY_PATH)
    parity_result = read_json(PARITY_RESULT_PATH)
    support = contract["official_support"]
    assert support["gpu_listed_exactly"] is True
    assert support["matrix_release"] == "7.14.0"
    assert parity["status"] == "executed_accepted"
    assert parity["execution"]["outcome"] == "accepted"
    assert parity["candidate_preconditions"]["primary_backend"] == "rocm"
    assert parity["candidate_preconditions"]["compatibility_contract"] == (
        "Research/environment/mlagents-rocm-compatibility-contract-v1.json"
    )
    assert parity["decision"]["no_partial_acceptance"] is True
    assert parity_result["status"] == "accepted"
    assert parity_result["decision"]["selected_backend"] == "rocm"


def test_run_manifest_schema_registers_both_python_environments() -> None:
    schema = read_json(MANIFEST_SCHEMA_PATH)
    versions = schema["properties"]["software"]["properties"]["python"]
    versions = versions["properties"]["version"]["enum"]
    assert versions == ["3.10.12", "3.11.13"]
    selected_backends = schema["properties"]["backend"]["properties"]
    assert selected_backends["selected"]["enum"] == [
        "cpu",
        "rocm",
        "cuda",
        "other",
    ]
    assert "directml" not in SMOKE_RUNNER_PATH.read_text(encoding="utf-8").lower()
