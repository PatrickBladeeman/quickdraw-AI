from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable

import pytest
from jsonschema.exceptions import ValidationError

import run_bdq_third_update_smoke as third
import run_bdq_fourth_update_smoke as fourth
import run_bdq_fifth_update_smoke as fifth
from bdq_test_support import (
    FROZEN_TARGET,
    REGISTERED_UPDATES,
    scheduled_selector,
    synthetic_task_trace,
)
from quickdraw_bdq import LLAPIContractError
from quickdraw_bdq.trajectory_validation import validate_transition_prefix


@dataclass(frozen=True)
class ScheduledCase:
    runner: ModuleType
    prefix_key: str
    boundary_key: str
    post_update_action_key: str
    cutoff: int
    update_count: int


@pytest.fixture(
    params=[
        pytest.param(
            ScheduledCase(
                third,
                "r3j_prefix",
                "third_update_boundary",
                "select_action_after_third_update",
                10_008,
                3,
            ),
            id="R3K-update-3",
        ),
        pytest.param(
            ScheduledCase(
                fourth,
                "r3k_prefix",
                "fourth_update_boundary",
                "select_action_after_fourth_update",
                10_012,
                4,
            ),
            id="R3M-update-4",
        ),
        pytest.param(
            ScheduledCase(
                fifth,
                "r3m_prefix",
                "fifth_update_boundary",
                "select_action_after_fifth_update",
                10_016,
                5,
            ),
            id="R3O-update-5",
        ),
    ]
)
def scheduled_case(request: pytest.FixtureRequest) -> ScheduledCase:
    return request.param


@pytest.fixture
def task_trace_unit(
    scheduled_case: ScheduledCase,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Only milestone relational assertions; full composed traces are replayed separately."""
    runner = scheduled_case.runner
    contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = runner.validate_contract(contract)
    trace = synthetic_task_trace(
        REGISTERED_UPDATES[: scheduled_case.update_count],
        scheduled_selector(contract["epsilon_schedule"]),
        decision_count=scheduled_case.cutoff,
        target_sha256=FROZEN_TARGET,
    )
    monkeypatch.setattr(
        runner, "validate_update_gate_trace", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "quickdraw_bdq.trajectory_validation.canonical_json_sha256",
        lambda value: contract[scheduled_case.prefix_key][
            "canonical_transitions_sha256"
        ],
    )
    return trace, schema


@pytest.mark.parametrize(
    "runner,binding_key",
    [
        pytest.param(third, "base_scheduled_handoff_contract", id="R3K-R3J-binding"),
        pytest.param(fourth, "base_third_update_contract", id="R3M-R3K-binding"),
        pytest.param(fifth, "base_fourth_update_contract", id="R3O-R3M-binding"),
        pytest.param(fifth, "base_replay_storage_contract", id="R3O-R3N-binding"),
    ],
)
def test_contract_rejects_drifted_binding(runner: ModuleType, binding_key: str) -> None:
    contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))
    contract[binding_key]["sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        runner.validate_contract(contract)


@pytest.mark.parametrize(
    "field", ["cutoff", "missing-update", "selector-count", "post-update-action"]
)
def test_contract_schema_rejects_boundary_drift(
    scheduled_case: ScheduledCase, field: str
) -> None:
    contract = json.loads(
        scheduled_case.runner.CONTRACT_PATH.read_text(encoding="utf-8")
    )
    if field == "cutoff":
        contract["collection"]["transition_limit"] = scheduled_case.cutoff + 1
    elif field == "missing-update":
        contract["optimization"]["expected_update_decisions"].pop()
    elif field == "selector-count":
        contract["epsilon_schedule"]["selection_count"] = 3
    else:
        contract[scheduled_case.boundary_key][
            scheduled_case.post_update_action_key
        ] = True
    with pytest.raises(ValidationError):
        scheduled_case.runner.validate_contract(contract)


def test_result_schema_freezes_no_handoff_cutoff(scheduled_case: ScheduledCase) -> None:
    schema = json.loads(
        scheduled_case.runner.RESULT_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    trace = schema["$defs"]["trace"]
    selector = trace["properties"]["selector"]["properties"]
    assert trace["properties"]["transitions"]["minItems"] == scheduled_case.cutoff
    assert trace["properties"]["transitions"]["maxItems"] == scheduled_case.cutoff
    assert trace["properties"]["optimization"]["properties"][
        "optimizer_update_count"
    ] == {"const": scheduled_case.update_count}
    assert selector["selection_count"] == {"const": scheduled_case.cutoff}
    assert selector["last_selection_completed_transition_count"] == {
        "const": scheduled_case.cutoff - 1
    }
    assert "scheduled_epsilon_handoff" not in trace["required"]
    assert "scheduled_epsilon_handoff" not in trace["properties"]


def test_task_trace_unit_preserves_prefix_and_final_update(
    scheduled_case: ScheduledCase,
    task_trace_unit: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    scheduled_case.runner.validate_trace(*task_trace_unit)


@pytest.mark.parametrize(
    "mutate,message",
    [
        pytest.param(
            lambda t: t["optimization"]["update_events"][0].__setitem__("loss", 1.0),
            "optimizer metric",
            id="prior-loss",
        ),
        pytest.param(
            lambda t: t["optimization"]["update_events"][1].__setitem__(
                "mean_absolute_td_error", 1.0
            ),
            "optimizer metric",
            id="prior-td-error",
        ),
        pytest.param(
            lambda t: t["optimization"]["update_events"][0].__setitem__(
                "online_after_sha256", "0" * 64
            ),
            "post-update online hash",
            id="prior-online-hash",
        ),
        pytest.param(
            lambda t: t["optimization"]["update_events"][-1].__setitem__(
                "online_after_sha256",
                t["optimization"]["update_events"][-2]["online_after_sha256"],
            ),
            "did not change",
            id="final-update-unchanged",
        ),
        pytest.param(
            lambda t: t["optimization"].__setitem__("online_after_sha256", "2" * 64),
            "final online hash",
            id="final-online-mismatch",
        ),
        pytest.param(
            lambda t: t["optimization"].__setitem__("target_after_sha256", "2" * 64),
            "frozen",
            id="target-change",
        ),
        pytest.param(
            lambda t: t["selector"]["epsilon_samples"][0].__setitem__("epsilon", 0.5),
            "epsilon samples",
            id="epsilon-sample",
        ),
        pytest.param(
            lambda t: t["selector"].__setitem__("selection_count", 3),
            "selector selection_count",
            id="selector-counter",
        ),
        pytest.param(
            lambda t: t["selector"].__setitem__(
                "completed_transition_count_source", "frames"
            ),
            "counter source",
            id="selector-clock",
        ),
        pytest.param(
            lambda t: t["replay"].__setitem__(
                "decision_count",
                t["selector"]["last_selection_completed_transition_count"],
            ),
            "selected an action after update",
            id="post-boundary-action",
        ),
    ],
)
def test_task_trace_unit_rejects_drift(
    scheduled_case: ScheduledCase,
    task_trace_unit: tuple[dict[str, Any], dict[str, Any]],
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    trace, schema = task_trace_unit
    mutate(trace)
    with pytest.raises(LLAPIContractError, match=message):
        scheduled_case.runner.validate_trace(trace, schema)


def test_transition_prefix_hash_covers_exact_ordered_prior_rows() -> None:
    prior = [{"index": 0, "value": 1}, {"index": 1, "value": 2}]
    # Independent canonical-JSON oracle; do not call the production hash builder.
    digest = hashlib.sha256(
        json.dumps(prior, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    prefix = {"transition_count": 2, "canonical_transitions_sha256": digest}
    validate_transition_prefix(
        [*prior, {"tail": 3}], prefix, task_name="TEST", base_name="PRIOR"
    )
    for changed in [
        prior[:1],
        list(reversed(prior)),
        [{"index": 0, "value": 9}, prior[1]],
    ]:
        with pytest.raises(LLAPIContractError, match="canonical PRIOR prefix"):
            validate_transition_prefix(
                changed, prefix, task_name="TEST", base_name="PRIOR"
            )
