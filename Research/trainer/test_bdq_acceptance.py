from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quickdraw_bdq.provenance import runtime_contract  # noqa: E402
from quickdraw_bdq.acceptance import (  # noqa: E402
    canonical_json_sha256,
    comparison_execution_mode,
    load_bound_contract,
    run_fresh_python_process,
    run_fresh_worker_process,
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
    alias = tmp_path / "alias.json"
    os.link(first, alias)
    with pytest.raises(ValueError, match="two distinct trace files"):
        validate_distinct_trace_paths(first, alias, task_name="TEST")
    for left, right in ((first, tmp_path / "missing"), (tmp_path / "missing", second)):
        with pytest.raises(FileNotFoundError):
            validate_distinct_trace_paths(left, right, task_name="TEST")


@pytest.mark.parametrize(
    "overrides",
    [
        {"output": Path("out"), "first_trace": Path("first")},
        {"output": Path("out"), "second_trace": Path("second")},
        {
            "output": Path("out"),
            "first_trace": Path("first"),
            "second_trace": Path("second"),
            "env": Path("player"),
        },
        {"first_trace": Path("first"), "second_trace": Path("second")},
    ],
)
def test_comparison_mode_rejects_incomplete_or_mixed_inputs(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="Trace-comparison mode"):
        comparison_execution_mode(_arguments(**overrides))


def test_canonical_json_sha256_ignores_object_key_order() -> None:
    assert canonical_json_sha256({"b": 2, "a": 1}) == canonical_json_sha256(
        {"a": 1, "b": 2}
    )


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
        captured["options"] = kwargs
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
    assert captured["options"]["timeout"] == 1800
    assert captured["options"]["cwd"] == tmp_path
    assert captured["options"]["stderr"] == subprocess.STDOUT
    assert captured["options"]["stdout"] == subprocess.PIPE
    assert captured["options"]["text"] is True
    assert captured["options"]["check"] is False
    assert captured["command"] == [
        sys.executable,
        "-B",
        str((tmp_path / "runner.py").resolve()),
        f"--env={tmp_path / 'player.exe'}",
        f"--worker-output={output_directory / 'run-1'}",
        "--worker-index=0",
    ]
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


@pytest.mark.parametrize("mismatch", ["bytes", "objects"])
def test_result_writer_requires_object_and_byte_equality(
    tmp_path: Path, mismatch: str
) -> None:
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

    second = dict(trace)
    if mismatch == "bytes":
        second_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    else:
        second["value"] = 2
    with pytest.raises(LLAPIContractError, match="traces differ"):
        write_two_process_result(
            first=trace,
            first_path=first_path,
            second=second,
            second_path=second_path,
            output_directory=tmp_path / "other-result",
            result_schema=_result_schema(),
            result_schema_version="test-result.v1",
            contract_path=contract_path,
            task_name="TEST",
            validate_trace=lambda value, schema: None,
        )


def test_fresh_process_preserves_timeout_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timeout = subprocess.TimeoutExpired(["worker"], 7, output="partial output")

    def expire(*args: Any, **kwargs: Any) -> None:
        assert kwargs["timeout"] == 7
        raise timeout

    monkeypatch.setattr("quickdraw_bdq.acceptance.subprocess.run", expire)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        run_fresh_python_process(
            runner_path=tmp_path / "worker.py",
            arguments=[],
            output_directory=tmp_path,
            log_name="worker.log",
            task_name="TEST",
            contract=None,
            timeout_seconds=7,
        )
    assert caught.value is timeout
    assert not (tmp_path / "worker.log").exists()


def test_bound_contract_validates_bytes_before_loading_and_checks_schema(
    tmp_path: Path,
) -> None:
    import hashlib

    path = tmp_path / "base.json"
    payload = b'{"schema_version":"base.v1"}'
    path.write_bytes(payload)
    binding = {
        "path": "base.json",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "schema_version": "base.v1",
    }
    assert load_bound_contract(
        binding, repo_root=tmp_path, schema_error="schema drift"
    ) == {"schema_version": "base.v1"}
    binding["schema_version"] = "base.v2"
    with pytest.raises(LLAPIContractError, match="schema drift"):
        load_bound_contract(binding, repo_root=tmp_path, schema_error="schema drift")
    path.write_bytes(b"{")
    with pytest.raises(LLAPIContractError, match="Contract binding drifted"):
        load_bound_contract(binding, repo_root=tmp_path, schema_error="schema drift")
    binding["sha256"] = hashlib.sha256(b"{").hexdigest()
    with pytest.raises(json.JSONDecodeError):
        load_bound_contract(binding, repo_root=tmp_path, schema_error="schema drift")


@pytest.mark.parametrize("size", [0, 1, 1024 * 1024 - 1, 1024 * 1024, 1024 * 1024 + 1])
def test_raw_file_hash_matches_independent_whole_byte_oracle(
    tmp_path: Path,
    size: int,
) -> None:
    import hashlib
    from quickdraw_bdq.provenance import sha256_file

    # Includes non-text bytes and exercises both sides of the streaming boundary.
    payload = (bytes(range(256)) * (size // 256 + 1))[:size]
    path = tmp_path / "raw.bin"
    path.write_bytes(payload)
    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()
    with pytest.raises(FileNotFoundError):
        sha256_file(tmp_path / "missing.bin")


def test_runtime_identity_uses_exact_package_metadata_and_field_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from quickdraw_bdq import provenance

    packages = {"mlagents-envs": "1.1.0", "numpy": "1.23.5", "torch": "2.12.0+cpu"}
    requested = []

    def package_version(name: str) -> str:
        requested.append(name)
        return packages[name]

    monkeypatch.setattr(provenance, "sys", SimpleNamespace(version_info=(3, 11, 13)))
    monkeypatch.setattr(provenance, "version", package_version)
    assert provenance.runtime_contract() == {
        "python": "3.11.13",
        "mlagents_envs": "1.1.0",
        "numpy": "1.23.5",
        "torch": "2.12.0+cpu",
        "device": "cpu",
    }
    assert requested == ["mlagents-envs", "numpy", "torch"]
    del packages["numpy"]
    with pytest.raises(KeyError, match="numpy"):
        provenance.runtime_contract()
