from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import run_bdq_warmup_update_smoke as warmup
import run_bdq_two_update_smoke as two
import run_bdq_post_update_handoff_smoke as post
import run_bdq_scheduled_epsilon_handoff_smoke as scheduled
import run_bdq_third_update_smoke as third
import run_bdq_third_update_greedy_handoff_smoke as greedy
import run_bdq_fourth_update_smoke as fourth
import run_bdq_fifth_update_smoke as fifth
from quickdraw_bdq import trajectory_runner as trajectory


@pytest.mark.parametrize(
    "runner,task,label,cli,timeout,progress",
    [
        pytest.param(warmup, "R3F", "warmup-update", "warmup", 120, 0, id="R3F-watch"),
        pytest.param(two, "R3G", "two-update", "standard", 120, 0, id="R3G-update-2"),
        pytest.param(
            post,
            "R3H",
            "post-update-handoff",
            "standard",
            120,
            0,
            id="R3H-greedy-handoff",
        ),
        pytest.param(
            scheduled,
            "R3J",
            "scheduled-epsilon-handoff",
            "standard",
            120,
            0,
            id="R3J-scheduled-handoff",
        ),
        pytest.param(
            third, "R3K", "third-update", "standard", 120, 0, id="R3K-update-3"
        ),
        pytest.param(
            greedy,
            "R3L",
            "third-update-greedy-handoff",
            "comparison",
            120,
            0,
            id="R3L-diagnostic-greedy",
        ),
        pytest.param(
            fourth, "R3M", "fourth-update", "comparison", 300, 1_000, id="R3M-update-4"
        ),
        pytest.param(
            fifth, "R3O", "fifth-update", "comparison", 300, 1_000, id="R3O-update-5"
        ),
    ],
)
def test_entry_point_wires_identity_modes_and_worker_options(
    runner: ModuleType,
    task: str,
    label: str,
    cli: str,
    timeout: int,
    progress: int,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gate = runner.GATE
    assert gate.task_name == task
    assert gate.cli == cli
    assert gate.runner_path.resolve() == Path(runner.__file__).resolve()
    assert gate.contract_path.name == f"bdq-{label}-contract-v1.json"
    assert gate.trace_file_name == f"{task.lower()}-{label}-trace.json"
    assert gate.trace_schema_version == f"quickdraw.bdq-{label}-trace.v1"
    assert gate.result_schema_version == f"quickdraw.bdq-{label}-smoke-result.v1"
    assert runner.CONTRACT_SCHEMA_PATH.name == f"bdq-{label}-contract.schema.json"
    assert runner.RESULT_SCHEMA_PATH.name == f"bdq-{label}-smoke-result.schema.json"
    assert gate.announce_workers is (task != "R3F")

    parent = trajectory.parse_trajectory_arguments(
        gate, ["--env=player.exe", "--output=out"]
    )
    assert trajectory.trajectory_execution_mode(gate, parent) == (
        "acceptance" if cli == "warmup" else "parent"
    )
    if cli == "comparison":
        args = trajectory.parse_trajectory_arguments(
            gate, ["--output=out", "--first-trace=a", "--second-trace=b"]
        )
        assert trajectory.trajectory_execution_mode(gate, args) == "compare"
    else:
        with pytest.raises(SystemExit):
            trajectory.parse_trajectory_arguments(
                gate, ["--env=p", "--output=o", "--first-trace=a"]
            )
    if cli != "warmup":
        with pytest.raises(SystemExit):
            trajectory.parse_trajectory_arguments(
                gate, ["--env=p", "--output=o", "--watch"]
            )

    player = tmp_path / "player.exe"
    player.touch()
    calls: list[Any] = []
    marker = {"trace": task}

    def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((args, kwargs))
        return marker

    monkeypatch.setattr(trajectory, "execute_update_gate_worker", execute)
    monkeypatch.setattr(
        runner, "validate_contract", lambda c: calls.append("contract") or {}
    )
    monkeypatch.setattr(runner, "validate_trace", lambda t, s: calls.append((t, s)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(gate.runner_path),
            "--env",
            str(player),
            "--worker-output",
            str(tmp_path / "worker"),
            "--worker-index",
            "1",
        ],
    )
    assert runner.main() == 0
    assert calls[0] == "contract"
    assert calls[-1] == (marker, {})
    args, options = calls[1]
    assert args[:3] == (player.resolve(), (tmp_path / "worker").resolve(), 1)
    assert args[3] == json.loads(gate.contract_path.read_text(encoding="utf-8"))
    assert options == {
        "contract_path": gate.contract_path,
        "trace_file_name": gate.trace_file_name,
        "trace_schema_version": gate.trace_schema_version,
        "task_name": task,
        "record_update_hashes": task != "R3F",
        "base_port": 5045,
        "timeout_wait": timeout,
        "watch": False,
        "progress_interval": progress,
    }


@pytest.fixture
def gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> trajectory.TrajectoryGate:
    contract = tmp_path / "contract.json"
    contract.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(trajectory, "ARTIFACT_ROOT", tmp_path)
    return trajectory.TrajectoryGate(
        tmp_path / "runner.py",
        contract,
        "trace.json",
        "trace.v1",
        "result.v1",
        "TEST",
        "test",
    )


@pytest.mark.parametrize("invalid_output", ["root", "outside", "existing"])
def test_parent_rejects_nonfresh_or_outside_output_before_launch(
    gate: trajectory.TrajectoryGate,
    invalid_output: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    player = tmp_path / "player.exe"
    player.touch()
    existing = tmp_path / "existing"
    existing.mkdir()
    output = {"root": tmp_path, "outside": tmp_path.parent, "existing": existing}[
        invalid_output
    ]
    monkeypatch.setattr(
        trajectory,
        "run_fresh_worker_process",
        lambda **kwargs: pytest.fail("invalid output launched a worker"),
    )
    with pytest.raises(FileExistsError if invalid_output == "existing" else ValueError):
        trajectory.run_trajectory(
            gate,
            arguments=["--env", str(player), "--output", str(output)],
            validate_contract=lambda contract: {},
            validate_trace=lambda trace, schema: None,
            summarize=lambda trace: None,
        )


@pytest.mark.parametrize("cli", ["standard", "comparison"])
def test_parent_launches_ordered_fresh_workers_then_validates_and_writes(
    gate: trajectory.TrajectoryGate,
    cli: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gate = replace(gate, cli=cli)
    player = tmp_path / "player.exe"
    player.touch()
    order: list[Any] = []

    def worker(**kwargs: Any) -> tuple[dict[str, Any], Path]:
        index = kwargs["worker_index"]
        order.append(index)
        assert kwargs["runner_path"] == gate.runner_path
        assert kwargs["contract"] == {}
        path = kwargs["output_directory"] / f"run-{index + 1}" / gate.trace_file_name
        path.parent.mkdir()
        path.write_text('{"value": 1}\n', encoding="utf-8")
        return {"value": 1}, path

    monkeypatch.setattr(trajectory, "run_fresh_worker_process", worker)
    assert (
        trajectory.run_trajectory(
            gate,
            arguments=["--env", str(player), "--output", str(tmp_path / "out")],
            validate_contract=lambda c: order.append("contract") or {},
            validate_trace=lambda t, s: order.append("trace"),
            summarize=lambda t: order.append("summary"),
        )
        == 0
    )
    assert order == ["contract", 0, 1, "trace", "trace", "summary"]
    result = json.loads((tmp_path / "out/result.json").read_text(encoding="utf-8"))
    assert result["canonical_trace"] == {"value": 1}
    assert result["fresh_process_count"] == 2


def test_comparison_loads_complete_distinct_traces_without_workers(
    gate: trajectory.TrajectoryGate,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gate = replace(gate, cli="comparison")
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for path in (first, second):
        path.write_text('{"value": 1}\n', encoding="utf-8")
    monkeypatch.setattr(
        trajectory,
        "run_fresh_worker_process",
        lambda **kw: pytest.fail("comparison launched a worker"),
    )
    options = dict(
        validate_contract=lambda c: {},
        validate_trace=lambda t, s: None,
        summarize=lambda t: None,
    )
    args = [
        "--output",
        str(tmp_path / "out"),
        "--first-trace",
        str(first),
        "--second-trace",
        str(second),
    ]
    assert trajectory.run_trajectory(gate, arguments=args, **options) == 0
    with pytest.raises(FileExistsError, match="must be fresh"):
        trajectory.run_trajectory(gate, arguments=args, **options)
    args[1] = str(tmp_path / "retry")
    args[-1] = str(first)
    with pytest.raises(ValueError, match="distinct trace files"):
        trajectory.run_trajectory(gate, arguments=args, **options)
    second.write_text("{", encoding="utf-8")
    args[-1] = str(second)
    with pytest.raises(json.JSONDecodeError):
        trajectory.run_trajectory(gate, arguments=args, **options)
    assert not (tmp_path / "retry").exists()


@pytest.mark.parametrize(
    "cli,expected",
    [
        ("standard", FileNotFoundError),
        ("warmup", FileNotFoundError),
        ("comparison", RuntimeError),
    ],
)
def test_historical_validation_order_precedes_worker_launch(
    gate: trajectory.TrajectoryGate,
    cli: str,
    expected: type[Exception],
    tmp_path: Path,
) -> None:
    def bad_contract(contract: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("contract rejected")

    with pytest.raises(expected):
        trajectory.run_trajectory(
            replace(gate, cli=cli),
            arguments=[
                "--env",
                str(tmp_path / "missing"),
                "--output",
                str(tmp_path / "out"),
            ],
            validate_contract=bad_contract,
            validate_trace=lambda t, s: None,
            summarize=lambda t: None,
        )
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "standalone,interval", [(False, None), (False, 7), (True, None), (True, 7)]
)
def test_warmup_watch_keeps_diagnostic_options_and_never_writes_acceptance(
    gate: trajectory.TrajectoryGate,
    standalone: bool,
    interval: int | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gate = replace(gate, cli="warmup", task_name="R3F", record_update_hashes=False)
    args = ["--watch", "--output", str(tmp_path / "watch")]
    if standalone:
        player = tmp_path / "player.exe"
        player.touch()
        args += ["--env", str(player)]
    if interval is not None:
        args += ["--progress-interval", str(interval)]
    captured: dict[str, Any] = {}
    trace = {
        "optimization": {"update_events": [{"loss": 0.1}], "optimizer_update_count": 1},
        "replay": {"decision_count": 10_000},
        "completed_episode_count": 2,
    }

    def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return trace

    monkeypatch.setattr(trajectory, "execute_update_gate_worker", execute)
    monkeypatch.setattr(
        trajectory,
        "write_two_process_result",
        lambda **kw: pytest.fail("watch wrote acceptance"),
    )
    assert (
        trajectory.run_trajectory(
            gate,
            arguments=args,
            validate_contract=lambda c: {},
            validate_trace=lambda t, s: None,
            summarize=lambda t: pytest.fail("watch used the acceptance summary"),
        )
        == 0
    )
    assert captured["watch"] is True
    assert captured["record_update_hashes"] is False
    assert captured["base_port"] == 5004
    assert captured["timeout_wait"] == (120 if standalone else 300)
    assert captured["progress_interval"] == (100 if interval is None else interval)
    output = capsys.readouterr().out
    assert "watch_complete=true" in output and "acceptance_evidence=false" in output
    assert "time_scale=1" in output and "target_frame_rate=60" in output
    assert ("listening_port=5004" in output) is (not standalone)
