from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quickdraw_bdq.acceptance import (  # noqa: E402
    canonical_json_sha256,
    comparison_execution_mode,
    run_fresh_worker_process,
    runtime_contract,
    standard_execution_mode,
    validate_distinct_trace_paths,
    validate_runtime_and_package,
    validate_schema_pair,
    write_two_process_result,
)
from quickdraw_bdq.llapi import LLAPIContractError  # noqa: E402


def _arguments(**overrides: Any) -> argparse.Namespace:
    values = {
        "env": None,
        "output": None,
        "worker_output": None,
        "worker_index": None,
        "first_trace": None,
        "second_trace": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _result_schema() -> dict[str, Any]:
    properties = {
        "schema_version": {"type": "string"},
        "contract_sha256": {"type": "string"},
        "fresh_process_count": {"const": 2},
        "exact_trace_equality": {"const": True},
        "canonical_trace_sha256": {"type": "string"},
        "canonical_trace": {"type": "object"},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": list(properties),
        "properties": properties,
        "additionalProperties": False,
    }


def test_schema_pair_validates_both_schemas_and_contract(tmp_path: Path) -> None:
    contract_schema_path = tmp_path / "contract.schema.json"
    result_schema_path = tmp_path / "result.schema.json"
    contract_schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"const": 1}},
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    result_schema_path.write_text(json.dumps(_result_schema()), encoding="utf-8")

    assert validate_schema_pair(
        {"value": 1}, contract_schema_path, result_schema_path
    ) == _result_schema()
    with pytest.raises(ValidationError):
        validate_schema_pair(
            {"value": 2}, contract_schema_path, result_schema_path
        )


def test_runtime_and_package_validation_fails_closed(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        '[project]\nname = "quickdraw-test"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    contract = {
        "runtime": runtime_contract(),
        "package": {"distribution": "quickdraw-test", "version": "1.0.0"},
    }

    validate_runtime_and_package(
        contract, "TEST", pyproject_path=pyproject_path
    )
    contract["runtime"] = {**contract["runtime"], "device": "gpu"}
    with pytest.raises(LLAPIContractError, match="active runtime"):
        validate_runtime_and_package(
            contract, "TEST", pyproject_path=pyproject_path
        )


def test_execution_modes_preserve_historical_boundaries() -> None:
    assert standard_execution_mode(_arguments(output=Path("out"))) == "parent"
    assert standard_execution_mode(
        _arguments(worker_output=Path("worker"), worker_index=0)
    ) == "worker"
    with pytest.raises(ValueError, match="Parent mode"):
        standard_execution_mode(_arguments())
    with pytest.raises(ValueError, match="Worker mode"):
        standard_execution_mode(_arguments(worker_output=Path("worker")))

    assert comparison_execution_mode(
        _arguments(env=Path("player"), output=Path("out"))
    ) == "parent"
    assert comparison_execution_mode(
        _arguments(
            output=Path("out"),
            first_trace=Path("first"),
            second_trace=Path("second"),
        )
    ) == "compare"


def test_distinct_trace_paths_reject_aliases(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    validate_distinct_trace_paths(first, second, task_name="TEST")
    with pytest.raises(ValueError, match="two distinct trace files"):
        validate_distinct_trace_paths(first, first, task_name="TEST")


def test_fresh_worker_sets_deterministic_environment_and_loads_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_directory = tmp_path / "output"
    trace_path = output_directory / "run-1" / "trace.json"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text('{"ok": true}\n', encoding="utf-8")
    captured: dict[str, Any] = {}

    def completed_run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout="worker output\n")

    monkeypatch.setattr("quickdraw_bdq.acceptance.subprocess.run", completed_run)
    trace, returned_path = run_fresh_worker_process(
        runner_path=tmp_path / "runner.py",
        executable=tmp_path / "player.exe",
        output_directory=output_directory,
        worker_index=0,
        contract={"determinism": {"torch_num_threads": 1}},
        trace_file_name="trace.json",
        task_name="TEST",
        announce=True,
        repo_root=tmp_path,
    )

    assert trace == {"ok": True}
    assert returned_path == trace_path
    assert captured["environment"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert captured["environment"]["OMP_NUM_THREADS"] == "1"
    assert captured["environment"]["MKL_NUM_THREADS"] == "1"
    assert capsys.readouterr().out.splitlines() == [
        "worker_1=starting",
        "worker_1=complete",
    ]
    assert (output_directory / "worker-1.log").read_text(encoding="utf-8") == (
        "worker output\n"
    )


@pytest.mark.parametrize(
    ("return_code", "write_trace", "message"),
    [
        (7, True, "failed with exit code 7"),
        (0, False, "omitted"),
    ],
)
def test_fresh_worker_fails_on_process_error_or_missing_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    return_code: int,
    write_trace: bool,
    message: str,
) -> None:
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    if write_trace:
        trace_path = output_directory / "run-1" / "trace.json"
        trace_path.parent.mkdir(parents=True)
        trace_path.write_text("{}\n", encoding="utf-8")

    def completed_run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, return_code, stdout="log\n")

    monkeypatch.setattr("quickdraw_bdq.acceptance.subprocess.run", completed_run)
    with pytest.raises(RuntimeError, match=message):
        run_fresh_worker_process(
            runner_path=tmp_path / "runner.py",
            executable=tmp_path / "player.exe",
            output_directory=output_directory,
            worker_index=0,
            contract=None,
            trace_file_name="trace.json",
            task_name="TEST",
            announce=False,
            repo_root=tmp_path,
        )
    assert (output_directory / "worker-1.log").read_text(encoding="utf-8") == (
        "log\n"
    )


def test_result_writer_requires_object_and_byte_equality(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.json"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    output_directory = tmp_path / "result"
    trace = {"value": 1}
    payload = json.dumps(trace, sort_keys=True) + "\n"
    contract_path.write_text("{}\n", encoding="utf-8")
    first_path.write_text(payload, encoding="utf-8")
    second_path.write_text(payload, encoding="utf-8")

    result_path = write_two_process_result(
        first=trace,
        first_path=first_path,
        second=dict(trace),
        second_path=second_path,
        output_directory=output_directory,
        result_schema=_result_schema(),
        result_schema_version="test-result.v1",
        contract_path=contract_path,
        task_name="TEST",
        validate_trace=lambda value, schema: None,
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["canonical_trace_sha256"] == canonical_json_sha256(trace)
    assert result["canonical_trace"] == trace

    second_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(LLAPIContractError, match="traces differ"):
        write_two_process_result(
            first=trace,
            first_path=first_path,
            second=dict(trace),
            second_path=second_path,
            output_directory=tmp_path / "other-result",
            result_schema=_result_schema(),
            result_schema_version="test-result.v1",
            contract_path=contract_path,
            task_name="TEST",
            validate_trace=lambda value, schema: None,
        )
