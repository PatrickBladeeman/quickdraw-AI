from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    REPLAY_MAX_ACCOUNTED_BYTES,
    LLAPIContractError,
    ReplayBuffer,
)
from quickdraw_bdq.acceptance import (  # noqa: E402
    canonical_json_sha256,
    runtime_contract,
    sha256_file,
)
from run_bdq_fourth_update_smoke import (  # noqa: E402
    CONTRACT_PATH as R3M_CONTRACT_PATH,
    validate_contract as validate_r3m_contract,
    validate_trace as validate_r3m_trace,
)


CONTRACT_PATH = HERE / "bdq-replay-storage-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    REPO_ROOT
    / "Research"
    / "schemas"
    / "bdq-replay-storage-contract.schema.json"
)


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(contract)

    binding = contract["base_fourth_update_contract"]
    bound_path = REPO_ROOT / binding["path"]
    if bound_path != R3M_CONTRACT_PATH:
        raise LLAPIContractError("R3N does not bind the active R3M contract.")
    if sha256_file(bound_path) != binding["sha256"]:
        raise LLAPIContractError("R3N's R3M contract hash has drifted.")
    base_contract = json.loads(bound_path.read_text(encoding="utf-8"))
    if base_contract["schema_version"] != binding["schema_version"]:
        raise LLAPIContractError("R3N's R3M schema binding has drifted.")
    if contract["runtime"] != runtime_contract():
        raise LLAPIContractError("The active runtime differs from R3N.")
    if contract["runtime"] != base_contract["runtime"]:
        raise LLAPIContractError("R3N runtime differs from R3M.")
    if contract["package"] != base_contract["package"]:
        raise LLAPIContractError("R3N package boundary differs from R3M.")

    budget = contract["memory_budget"]
    if budget["max_accounted_storage_bytes"] != REPLAY_MAX_ACCOUNTED_BYTES:
        raise LLAPIContractError("R3N's replay storage ceiling has drifted.")
    projections = (
        (0, "metadata_accounted_bytes_at_capacity"),
        (81, "registered_basic_projection_accounted_bytes"),
        (100_004, "conservative_sequential_projection_accounted_bytes"),
    )
    for unique_frames, key in projections:
        observed = ReplayBuffer.projected_accounted_bytes(100_000, unique_frames)
        if observed != budget[key]:
            raise LLAPIContractError(f"R3N memory projection {key} has drifted.")
    if budget["conservative_sequential_projection_accounted_bytes"] >= (
        REPLAY_MAX_ACCOUNTED_BYTES
    ):
        raise LLAPIContractError("R3N's registered projection exceeds its budget.")

    return validate_r3m_contract(base_contract)


def build_regression_evidence(
    trace: Dict[str, Any],
    trace_path: Path,
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    transitions = trace["transitions"]
    update_events = trace["optimization"]["update_events"]
    unique_stack_hashes = {
        value
        for transition in transitions
        for value in (
            transition["observation_sha256"],
            transition["next_observation_sha256"],
        )
    }
    conservative_unique_frames = len(unique_stack_hashes) * 4
    capacity = contract["public_replay_interface"]["capacity"]
    return {
        "serialized_trace_sha256": sha256_file(trace_path),
        "canonical_trace_sha256": canonical_json_sha256(trace),
        "all_transitions_sha256": canonical_json_sha256(transitions),
        "tail_four_transitions_sha256": canonical_json_sha256(transitions[-4:]),
        "update_events_sha256": canonical_json_sha256(update_events),
        "unique_full_stack_count": len(unique_stack_hashes),
        "conservative_unique_frame_upper_bound": conservative_unique_frames,
        "conservative_frame_payload_upper_bound_bytes": (
            conservative_unique_frames * 84 * 84 * 4
        ),
        "conservative_accounted_storage_upper_bound_bytes": (
            ReplayBuffer.projected_accounted_bytes(
                capacity,
                conservative_unique_frames,
            )
        ),
        "update_decisions": [event["decision_count"] for event in update_events],
        "update_losses": [event["loss"] for event in update_events],
        "update_mean_absolute_td_errors": [
            event["mean_absolute_td_error"] for event in update_events
        ],
        "online_hashes_after_updates": [
            event["online_after_sha256"] for event in update_events
        ],
        "target_hash": trace["optimization"]["target_after_sha256"],
        "target_sync_count": trace["optimization"]["target_sync_count"],
        "optimizer_update_count": trace["optimization"][
            "optimizer_update_count"
        ],
        "transition_count": len(transitions),
    }


def validate_regression_evidence(
    evidence: Dict[str, Any],
    contract: Dict[str, Any],
) -> None:
    expected = {
        key: value
        for key, value in contract["r3m_regression"].items()
        if key not in {"fresh_process_count", "comparison"}
    }
    if evidence != expected:
        changed = sorted(
            key
            for key in set(evidence) | set(expected)
            if evidence.get(key) != expected.get(key)
        )
        raise LLAPIContractError(
            "R3N changed frozen R3M evidence fields: " + ", ".join(changed)
        )
    if evidence["conservative_accounted_storage_upper_bound_bytes"] >= (
        contract["memory_budget"]["max_accounted_storage_bytes"]
    ):
        raise LLAPIContractError("R3N live replay evidence exceeds its budget.")


def validate_live_regression(
    trace_path: Path,
    contract: Dict[str, Any],
    r3m_result_schema: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_trace_path = trace_path.resolve()
    if not resolved_trace_path.is_file():
        raise FileNotFoundError(resolved_trace_path)
    trace = json.loads(resolved_trace_path.read_text(encoding="utf-8"))
    validate_r3m_trace(trace, r3m_result_schema)
    evidence = build_regression_evidence(trace, resolved_trace_path, contract)
    validate_regression_evidence(evidence, contract)
    return evidence


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one fresh post-R3N R3M trace against the frozen pre-R3N "
            "trace and replay-memory evidence."
        )
    )
    parser.add_argument("--trace", required=True, type=Path)
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    r3m_result_schema = validate_contract(contract)
    evidence = validate_live_regression(
        arguments.trace,
        contract,
        r3m_result_schema,
    )
    print(f"trace={arguments.trace.resolve()}")
    print(f"serialized_trace_sha256={evidence['serialized_trace_sha256']}")
    print(f"canonical_trace_sha256={evidence['canonical_trace_sha256']}")
    print(f"transitions={evidence['transition_count']}")
    print(f"optimizer_updates={evidence['optimizer_update_count']}")
    print(f"target_synchronizations={evidence['target_sync_count']}")
    print(f"unique_full_stacks={evidence['unique_full_stack_count']}")
    print(
        "conservative_unique_frames="
        f"{evidence['conservative_unique_frame_upper_bound']}"
    )
    print(
        "conservative_accounted_storage_bytes="
        f"{evidence['conservative_accounted_storage_upper_bound_bytes']}"
    )
    print("lossless_replay_equivalence=pass")
    print("replay_memory_budget=pass")
    print("r3m_regression=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
