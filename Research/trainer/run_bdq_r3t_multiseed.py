"""Run the contract-bound R3T Basic BDQ multi-seed lineage campaign.

R3T is deliberately a thin campaign boundary.  The live collection and BDQ
optimization path remains ``quickdraw_bdq.update_gate``; this module owns only
the registered five-run mapping, run-owned player copies, learning-curve
observation, checkpoint cadence, fresh-Python restore, and artifact audits.
"""

from __future__ import annotations

import argparse
import copy
import csv
import dataclasses
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq.acceptance import (  # noqa: E402
    ARTIFACT_ROOT,
    canonical_json_sha256,
    copy_complete_player,
    load_bound_contract,
    registered_settings,
    run_fresh_python_process,
    validate_runtime_and_package,
)
from quickdraw_bdq.checkpoint import (  # noqa: E402
    CHECKPOINT_SCHEMA_VERSION,
    checkpoint_state_sha256,
    load_controller_checkpoint,
    save_controller_checkpoint,
)
from quickdraw_bdq.exploration import LinearEpsilonSchedule  # noqa: E402
from quickdraw_bdq.llapi import (  # noqa: E402
    BASIC_BEHAVIOR_NAME,
    LLAPIContractError,
    ScheduledEpsilonGreedyBDQActionSelector,
)
from quickdraw_bdq.optimizer import (  # noqa: E402
    BDQOptimizationSettings,
    BDQOptimizerController,
)
from quickdraw_bdq.provenance import (  # noqa: E402
    directory_file_manifest,
    sha256_file,
)
from quickdraw_bdq.trajectory_validation import (  # noqa: E402
    validate_player_execution,
    validate_scheduled_selector,
)
from quickdraw_bdq.update_gate import (  # noqa: E402
    configure_torch,
    execute_update_gate_worker,
    validate_update_gate_trace,
)


CONTRACT_PATH = HERE / "bdq-r3t-basic-multiseed-contract-v1.json"
CONTRACT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-r3t-basic-multiseed-contract.schema.json"
)
RESULT_SCHEMA_PATH = (
    HERE.parent / "schemas" / "bdq-r3t-basic-multiseed-result.schema.json"
)
CHECKPOINT_SCHEMA_PATH = HERE.parent / "schemas" / "bdq-checkpoint.schema.json"
PYPROJECT_PATH = HERE / "pyproject.toml"

TRACE_FILE_NAME = "trace.json"
METRICS_FILE_NAME = "metrics.json"
RUN_RESULT_FILE_NAME = "result.json"
RESTORE_FILE_NAME = "restore.json"
MANIFEST_FILE_NAME = "manifest.json"
TRACE_SCHEMA_VERSION = "quickdraw.bdq-r3t-basic-multiseed-trace.v1"
METRICS_SCHEMA_VERSION = "quickdraw.bdq-r3t-basic-multiseed-metrics.v1"
DENOMINATOR_DEFINITION = (
    "observed_episode_count is completed episodes plus one active prefix when "
    "the sampled update has not ended that episode."
)
RESTORE_SCHEMA_VERSION = "quickdraw.bdq-r3t-basic-multiseed-restore.v1"
RUN_RESULT_SCHEMA_VERSION = "quickdraw.bdq-r3t-basic-multiseed-run-result.v1"
RESULT_SCHEMA_VERSION = "quickdraw.bdq-r3t-basic-multiseed-result.v1"
TASK_NAME = "R3T"
WORKER_TIMEOUT_SECONDS = 14_400
BASE_WORKER_PORT = 5_045


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LLAPIContractError(f"JSON root is not an object: {path}.")
    return value


def _write_json(value: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_relative_text(value: str, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise LLAPIContractError(f"{label} must be a non-empty relative path.")
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise LLAPIContractError(f"{label} must be a safe relative path.")
    return path


def _repo_path(value: str, *, label: str) -> Path:
    relative = _validate_relative_text(value, label=label)
    candidate = (REPO_ROOT / relative).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as error:
        raise LLAPIContractError(f"{label} escaped the repository root.") from error
    return candidate


def _campaign_root(contract: Dict[str, Any]) -> Path:
    return _repo_path(contract["artifact_layout"]["root"], label="artifact root")


def _prepare_fresh_campaign_root(output: Path) -> None:
    """Allow only an absent or empty root; never overwrite prior artifacts."""
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(f"R3T output must be a fresh directory: {output}")
        try:
            next(output.iterdir())
        except StopIteration:
            return
        raise FileExistsError(f"R3T output must be fresh: {output}")
    output.mkdir(parents=True)


def _artifact_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise LLAPIContractError(
            f"Artifact path escaped the registered root: {path}."
        ) from error


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise LLAPIContractError(
            f"Repository artifact path escaped the repository root: {path}."
        ) from error


def _load_bound(
    contract: Dict[str, Any],
    name: str,
    *,
    schema_error: str,
) -> Dict[str, Any]:
    return load_bound_contract(
        contract[name],
        schema_error=schema_error,
        repo_root=REPO_ROOT,
    )


def _manifest_identity(root: Path) -> Dict[str, Any]:
    manifest = directory_file_manifest(root)
    return {
        "manifest": manifest,
        "manifest_sha256": canonical_json_sha256(manifest),
        "file_count": int(manifest["file_count"]),
        "total_bytes": int(manifest["total_bytes"]),
    }


def _source_player_identity(contract: Dict[str, Any]) -> Dict[str, Any]:
    player = contract["player_execution"]
    executable = _repo_path(
        player["source_executable"], label="source executable"
    )
    if not executable.is_file():
        raise FileNotFoundError(executable)
    identity = _manifest_identity(executable.parent)
    expected = {
        "manifest_sha256": player["source_manifest_sha256"],
        "file_count": int(player["source_file_count"]),
        "total_bytes": int(player["source_total_bytes"]),
    }
    if {
        key: identity[key] for key in expected
    } != expected:
        raise LLAPIContractError("R3T source player manifest differs from contract.")
    executable_sha256 = sha256_file(executable)
    if executable_sha256 != player["executable_sha256"]:
        raise LLAPIContractError("R3T source player executable hash differs from contract.")
    return {
        "path": player["source_executable"],
        "executable": executable,
        "manifest": identity["manifest"],
        "manifest_sha256": identity["manifest_sha256"],
        "file_count": identity["file_count"],
        "total_bytes": identity["total_bytes"],
        "executable_sha256": executable_sha256,
    }


def _mapping_for_run(
    contract: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    mappings = contract["campaign"]["seed_mapping"]
    matches = [mapping for mapping in mappings if mapping["run_id"] == run_id]
    if len(matches) != 1:
        raise LLAPIContractError(f"R3T has no unique registered mapping for {run_id}.")
    return copy.deepcopy(matches[0])


def _mapping_table(contract: Dict[str, Any]) -> list[Dict[str, Any]]:
    mappings = [copy.deepcopy(value) for value in contract["campaign"]["seed_mapping"]]
    expected_ids = [
        f"seed-{seed}" for seed in contract["campaign"]["policy_seeds"]
    ]
    if [mapping["run_id"] for mapping in mappings] != expected_ids:
        raise LLAPIContractError("R3T seed mapping order or coverage drifted.")
    for ordinal, mapping in enumerate(mappings, start=1):
        expected = {
            "ordinal": ordinal,
            "run_id": f"seed-{mapping['policy_initialization_seed']}",
            "policy_initialization_seed": int(
                contract["campaign"]["policy_seeds"][ordinal - 1]
            ),
            "replay_sampling_seed": int(
                contract["campaign"]["policy_seeds"][ordinal - 1]
            ),
            "exploration_seed": int(contract["campaign"]["exploration_seed"]),
            "scenario_seed": int(contract["campaign"]["scenario_seed"]),
        }
        if mapping != expected:
            raise LLAPIContractError(
                f"R3T seed mapping for ordinal {ordinal} differs from registration."
            )
    return mappings


def _validate_source_player(contract: Dict[str, Any]) -> Dict[str, Any]:
    player = contract["player_execution"]
    validate_player_execution(
        player,
        repo_root=REPO_ROOT,
        task_name=TASK_NAME,
    )
    source = _source_player_identity(contract)
    for sibling in player["required_siblings"]:
        if not (source["executable"].parent / sibling).exists():
            raise FileNotFoundError(source["executable"].parent / sibling)
    return source


def _validate_contract_relationships(contract: Dict[str, Any]) -> None:
    basic = _load_bound(
        contract,
        "base_basic_contract",
        schema_error="R3T Basic contract schema binding drifted.",
    )
    basic_schema = _repo_path(
        contract["base_basic_schema"]["path"], label="Basic schema"
    )
    if sha256_file(basic_schema) != contract["base_basic_schema"]["sha256"]:
        raise LLAPIContractError("R3T Basic schema hash binding drifted.")
    basic_schema_value = _read_json(basic_schema)
    Draft202012Validator.check_schema(basic_schema_value)
    if basic_schema_value.get("properties", {}).get("schema_version", {}).get(
        "const"
    ) != contract["base_basic_schema"]["schema_version"]:
        raise LLAPIContractError("R3T Basic schema version binding drifted.")

    foundation = _load_bound(
        contract,
        "base_bdq_foundation_contract",
        schema_error="R3T BDQ foundation schema binding drifted.",
    )
    r3o = _load_bound(
        contract,
        "base_r3o_contract",
        schema_error="R3T R3O schema binding drifted.",
    )
    r3s = _load_bound(
        contract,
        "base_r3s_contract",
        schema_error="R3T R3S schema binding drifted.",
    )
    r3r = load_bound_contract(
        r3s["base_r3r_contract"],
        schema_error="R3T nested R3R schema binding drifted.",
        repo_root=REPO_ROOT,
    )
    checkpoint = _load_bound(
        contract,
        "base_checkpoint_contract",
        schema_error="R3T checkpoint schema binding drifted.",
    )

    if basic["behavior_name"] != BASIC_BEHAVIOR_NAME or basic["scenario_seed"] != 31001:
        raise LLAPIContractError("R3T Basic environment identity drifted.")
    if basic["observation"]["shape"] != [84, 84, 4] or basic["observation"][
        "wire_layout"
    ] != "HWC" or basic["observation"]["dtype"] != "float32":
        raise LLAPIContractError("R3T Basic observation identity drifted.")
    if basic["actions"]["discrete_branches"] != [3, 2]:
        raise LLAPIContractError("R3T Basic action identity drifted.")
    if basic["episode_end"]["decision_limit"] != 300:
        raise LLAPIContractError("R3T Basic episode limit drifted.")

    basic_binding = contract["base_basic_contract"]
    if foundation["base_environment_contract"] != {
        **basic_binding,
        "behavior_name": BASIC_BEHAVIOR_NAME,
    }:
        raise LLAPIContractError("R3T foundation environment binding drifted.")
    foundation_runtime = foundation["runtime"]
    if {
        "python": foundation_runtime["python"],
        "mlagents_envs": foundation_runtime["mlagents_envs"],
        "numpy": foundation_runtime["numpy"],
        "torch": foundation_runtime["torch"],
        "device": foundation_runtime["r3a_device"],
    } != contract["runtime"]:
        raise LLAPIContractError("R3T foundation runtime drifted.")
    if foundation["observation"]["wire_shape"] != contract["transport"][
        "observation_shape"
    ] or foundation["observation"]["wire_layout"] != contract["transport"][
        "observation_layout"
    ]:
        raise LLAPIContractError("R3T foundation observation binding drifted.")
    if foundation["actions"]["branch_sizes"] != contract["transport"][
        "discrete_branches"
    ]:
        raise LLAPIContractError("R3T foundation action binding drifted.")
    if foundation["replay"]["capacity"] != contract["optimization"][
        "replay_capacity"
    ] or foundation["replay"]["warmup_decisions"] != contract["optimization"][
        "replay_warmup_decisions"
    ]:
        raise LLAPIContractError("R3T foundation replay binding drifted.")
    if foundation["double_dqn"]["gamma"] != contract["optimization"]["gamma"]:
        raise LLAPIContractError("R3T Double-DQN gamma binding drifted.")

    expected_package = {
        key: contract["package"][key]
        for key in ("distribution", "version", "metadata_path", "trainer_entry_points")
    }
    for base in (r3o, r3s, checkpoint):
        if base["runtime"] != contract["runtime"]:
            raise LLAPIContractError("R3T bound runtime differs from active runtime.")
        base_package = base["package"]
        if {
            key: base_package[key]
            for key in expected_package
        } != expected_package:
            raise LLAPIContractError("R3T bound package identity drifted.")
        if "metadata_sha256" in base_package and base_package["metadata_sha256"] != contract["package"]["metadata_sha256"]:
            raise LLAPIContractError("R3T bound package metadata hash drifted.")
    if r3o["transport"] != contract["transport"] or r3r["transport"] != contract[
        "transport"
    ]:
        raise LLAPIContractError("R3T transport identity differs from frozen BDQ work.")
    r3s_player = r3s["player"]
    player = contract["player_execution"]
    for key in (
        "source_executable",
        "required_siblings",
        "source_manifest_sha256",
        "source_file_count",
        "source_total_bytes",
        "executable_sha256",
        "copy_complete_player",
        "no_graphics",
    ):
        if key in r3s_player and r3s_player[key] != player[key]:
            raise LLAPIContractError(f"R3T player identity differs from R3S at {key}.")
    if checkpoint["checkpoint_boundary"]["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise LLAPIContractError("R3T checkpoint boundary schema drifted.")

    collection = contract["collection"]
    optimization = contract["optimization"]
    if collection["scenario_seed"] != contract["campaign"]["scenario_seed"]:
        raise LLAPIContractError("R3T collection scenario seed drifted.")
    if collection["transition_limit"] != contract["training_horizon"]["transition_count"]:
        raise LLAPIContractError("R3T collection horizon differs from registration.")
    settings = BDQOptimizationSettings()
    active_settings = registered_settings(settings)
    if {
        key: optimization[key] for key in active_settings
    } != active_settings:
        raise LLAPIContractError("R3T optimizer settings differ from production defaults.")
    expected_updates = [
        int(optimization["expected_first_update_decision"])
        + index * int(optimization["optimizer_update_interval_decisions"])
        for index in range(int(optimization["expected_optimizer_updates"]))
    ]
    schedule = optimization["expected_update_decision_schedule"]
    if expected_updates != [10000 + 4 * index for index in range(10000)]:
        raise LLAPIContractError("R3T optimizer update schedule is not registered.")
    if schedule != {
        "first_decision": 10000,
        "interval_decisions": 4,
        "optimizer_update_count": 10000,
        "last_decision": 49996,
    }:
        raise LLAPIContractError("R3T optimizer schedule summary drifted.")
    if expected_updates[-1] != collection["transition_limit"]:
        raise LLAPIContractError("R3T final update does not close the transition boundary.")
    if optimization["expected_target_sync_update_counts"] != [10000]:
        raise LLAPIContractError("R3T target-sync schedule drifted.")
    if contract["training_horizon"]["target_synchronization_count"] != 1:
        raise LLAPIContractError("R3T target-sync horizon drifted.")

    epsilon = contract["epsilon_schedule"]
    epsilon_schedule = _schedule(contract)
    expected_epsilon_samples = [
        epsilon_schedule.epsilon_at(int(count))
        for count in epsilon["trace_sample_completed_transition_counts"]
    ]
    if epsilon["trace_sample_epsilons"] != expected_epsilon_samples:
        raise LLAPIContractError("R3T epsilon samples differ from its schedule.")
    if epsilon["selection_count"] != collection["transition_limit"]:
        raise LLAPIContractError("R3T selector count differs from its cutoff.")
    if epsilon["full_exploration_selection_count"] != 10001 or epsilon[
        "decay_selection_count"
    ] != 39995:
        raise LLAPIContractError("R3T epsilon phase counts drifted.")

    if contract["checkpoint"]["save_update_counts"] != [2500, 5000, 7500, 10000]:
        raise LLAPIContractError("R3T checkpoint cadence drifted.")
    if contract["checkpoint"]["selection"]["selected_update_count"] != 10000:
        raise LLAPIContractError("R3T checkpoint selection drifted.")
    curve_contract = contract["learning_curve"]
    curve_update_grid = [
        int(curve_contract["first_update_count"])
        + index * int(curve_contract["interval_updates"])
        for index in range(int(curve_contract["sample_count"]))
    ]
    if any(
        int(update_count) not in curve_update_grid
        for update_count in contract["checkpoint"]["save_update_counts"]
    ):
        raise LLAPIContractError(
            "R3T checkpoint cadence is not represented on the learning-curve grid."
        )
    if contract["learning_curve"]["metric_fields"] != [
        "loss",
        "mean_absolute_td_error",
        "online_after_sha256",
        "target_after_sha256",
        "sampled_indices",
        "q_value_summary",
        "checkpoint_state_sha256",
        "update_duration_seconds",
        "completed_episode_count",
        "observed_episode_count",
        "completed_episode_return_sum",
        "active_episode_ended",
        "active_episode_prefix_return",
        "mean_episode_return",
        "success_count",
        "success_rate",
    ]:
        raise LLAPIContractError("R3T learning-curve field registration drifted.")
    if _campaign_root(contract) != (ARTIFACT_ROOT / "r3t-basic-multiseed").resolve():
        raise LLAPIContractError("R3T artifact root differs from its registered root.")
    if contract["process_leak_audit"]["platform"] != "Windows":
        raise LLAPIContractError("R3T process-leak platform is not Windows.")


def validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Validate schema and all frozen prerequisites before dependent artifacts."""

    contract_schema = _read_json(CONTRACT_SCHEMA_PATH)
    result_schema = _read_json(RESULT_SCHEMA_PATH)
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(contract_schema).validate(contract)
    validate_runtime_and_package(
        contract,
        TASK_NAME,
        pyproject_path=PYPROJECT_PATH,
    )
    if sha256_file(REPO_ROOT / contract["package"]["metadata_path"]) != contract[
        "package"
    ]["metadata_sha256"]:
        raise LLAPIContractError("R3T package metadata hash drifted.")
    _mapping_table(contract)
    _validate_source_player(contract)
    _validate_contract_relationships(contract)
    return result_schema


def _gate_contract(
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
) -> Dict[str, Any]:
    collection = copy.deepcopy(contract["collection"])
    collection.update(
        {
            "policy_seed": int(mapping["policy_initialization_seed"]),
            "exploration_seed": int(mapping["exploration_seed"]),
        }
    )
    return {
        "collection": collection,
        "optimization": copy.deepcopy(contract["optimization"]),
        "epsilon_schedule": copy.deepcopy(contract["epsilon_schedule"]),
        "determinism": copy.deepcopy(contract["determinism"]),
    }


def _validate_run_paths(
    contract: Dict[str, Any],
    run_id: str,
    worker_output: Path,
    executable: Path,
) -> tuple[Path, Path]:
    root = _campaign_root(contract)
    run_root = (root / "runs" / run_id).resolve()
    player_root = (root / "player-copies" / run_id).resolve()
    if worker_output.resolve() != run_root:
        raise LLAPIContractError("R3T worker output differs from its registered run path.")
    if executable.resolve().parent != player_root:
        raise LLAPIContractError("R3T worker executable is not run-owned.")
    if worker_output.exists():
        raise FileExistsError(f"R3T worker output must be fresh: {worker_output}")
    if not executable.is_file():
        raise FileNotFoundError(executable)
    return run_root, player_root


def _manifest_file_map(manifest: Dict[str, Any]) -> Dict[str, tuple[int, str]]:
    return {
        entry["path"]: (int(entry["bytes"]), entry["sha256"])
        for entry in manifest["files"]
    }


def _runtime_player_mutations(
    contract: Dict[str, Any],
    source: Dict[str, Any],
    observed_manifest: Dict[str, Any],
) -> list[Dict[str, Any]]:
    allowed = {
        entry["path"]: entry["reason"]
        for entry in contract["player_execution"]["runtime_mutated_files"]
    }
    source_files = _manifest_file_map(source["manifest"])
    observed_files = _manifest_file_map(observed_manifest)
    if set(source_files) != set(observed_files):
        missing = sorted(set(source_files) - set(observed_files))
        extra = sorted(set(observed_files) - set(source_files))
        raise LLAPIContractError(
            "R3T run-owned player file set changed after launch: "
            f"missing={missing}, extra={extra}."
        )
    changed = {
        path for path in source_files if source_files[path] != observed_files[path]
    }
    unexpected = sorted(changed - set(allowed))
    if unexpected:
        raise LLAPIContractError(
            "R3T run-owned player changed outside registered runtime sidecars: "
            f"{unexpected}."
        )
    return [
        {
            "path": path,
            "reason": allowed[path],
            "source_bytes": source_files[path][0],
            "source_sha256": source_files[path][1],
            "observed_bytes": observed_files[path][0],
            "observed_sha256": observed_files[path][1],
        }
        for path in sorted(changed)
    ]


def _validate_player_copy(
    contract: Dict[str, Any],
    source: Dict[str, Any],
    copied_executable: Path,
    player_root: Path,
    *,
    allow_runtime_mutations: bool = False,
) -> Dict[str, Any]:
    if copied_executable.resolve().parent != player_root.resolve():
        raise LLAPIContractError("R3T copied player path differs from its run mapping.")
    player = contract["player_execution"]
    for sibling in player["required_siblings"]:
        if not (player_root / sibling).exists():
            raise LLAPIContractError(f"R3T player copy omitted {sibling}.")
    identity = _manifest_identity(player_root)
    expected = {
        "manifest_sha256": source["manifest_sha256"],
        "file_count": source["file_count"],
        "total_bytes": source["total_bytes"],
    }
    if allow_runtime_mutations:
        _runtime_player_mutations(contract, source, identity["manifest"])
    elif {key: identity[key] for key in expected} != expected:
        raise LLAPIContractError("R3T run-owned player copy manifest differs from source.")
    executable_sha256 = sha256_file(copied_executable)
    if executable_sha256 != source["executable_sha256"]:
        raise LLAPIContractError("R3T run-owned player executable hash differs from source.")
    return {
        "manifest": identity["manifest"],
        "manifest_sha256": identity["manifest_sha256"],
        "file_count": identity["file_count"],
        "total_bytes": identity["total_bytes"],
        "executable_sha256": executable_sha256,
    }


def _tasklist_pids(executable_name: str) -> set[int]:
    if sys.platform != "win32":
        raise LLAPIContractError("R3T process-leak audit requires Windows.")
    completed = subprocess.run(
        [
            "tasklist",
            "/FO",
            "CSV",
            "/NH",
            "/FI",
            f"IMAGENAME eq {executable_name}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LLAPIContractError(
            f"R3T tasklist process audit failed with exit code {completed.returncode}."
        )
    result: set[int] = set()
    for row in csv.reader(completed.stdout.splitlines()):
        if len(row) < 2 or row[0].casefold() != executable_name.casefold():
            continue
        try:
            result.add(int(row[1].replace(",", "")))
        except ValueError as error:
            raise LLAPIContractError("R3T tasklist returned an invalid PID.") from error
    return result


def _process_audit(
    executable_name: str,
    before: set[int],
    after: set[int],
) -> Dict[str, Any]:
    new_pids = after - before
    return {
        "platform": "Windows",
        "executable_name": executable_name,
        "before_matching_process_count": len(before),
        "after_matching_process_count": len(after),
        "new_matching_process_count": len(new_pids),
        "passed": not new_pids,
    }


def _player_provenance(
    contract: Dict[str, Any],
    source: Dict[str, Any],
    copy_identity: Dict[str, Any],
    copied_executable: Path,
    root: Path,
) -> Dict[str, Any]:
    return {
        "source_executable": source["path"],
        "source_manifest_sha256": source["manifest_sha256"],
        "source_file_count": source["file_count"],
        "source_total_bytes": source["total_bytes"],
        "executable_sha256": source["executable_sha256"],
        "copy_executable": _artifact_relative(copied_executable, root),
        "copy_manifest_sha256": copy_identity["manifest_sha256"],
        "copy_file_count": copy_identity["file_count"],
        "copy_total_bytes": copy_identity["total_bytes"],
    }


def _trace_provenance(
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
    source: Dict[str, Any],
    copy_identity: Dict[str, Any],
    copied_executable: Path,
    root: Path,
) -> Dict[str, Any]:
    package = contract["package"]
    return {
        "runtime": copy.deepcopy(contract["runtime"]),
        "package": {
            "distribution": package["distribution"],
            "version": package["version"],
            "metadata_path": package["metadata_path"],
        },
        "player": _player_provenance(
            contract, source, copy_identity, copied_executable, root
        ),
        "scenario_seed": int(mapping["scenario_seed"]),
        "policy_initialization_seed": int(mapping["policy_initialization_seed"]),
        "replay_sampling_seed": int(mapping["replay_sampling_seed"]),
        "exploration_seed": int(mapping["exploration_seed"]),
    }


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize(item)
            for key, item in value.items()
            if key
            not in {
                "update_duration_seconds",
                "process_leak_audit",
                "player_runtime_mutations",
            }
        }
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _canonical_digest(value: Any) -> str:
    return canonical_json_sha256(_canonicalize(value))


def _canonicalize_campaign_result(value: Dict[str, Any]) -> Any:
    result = copy.deepcopy(value)
    for run in result.get("runs", []):
        for artifact_name in ("trace", "metrics"):
            artifact = run.get(artifact_name)
            if isinstance(artifact, dict):
                artifact.pop("bytes", None)
                artifact.pop("sha256", None)
    return _canonicalize(result)


def _trace_schema(result_schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **result_schema["$defs"]["trace"],
        "$defs": result_schema["$defs"],
    }


def _metrics_schema(result_schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "$ref": "#/$defs/metrics",
        "$defs": result_schema["$defs"],
    }


def _run_result_schema(result_schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "$ref": "#/$defs/run_result",
        "$defs": result_schema["$defs"],
    }


def _restore_schema(result_schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "$ref": "#/$defs/restore",
        "$defs": result_schema["$defs"],
    }


def _schedule(contract: Dict[str, Any]) -> LinearEpsilonSchedule:
    epsilon = contract["epsilon_schedule"]
    return LinearEpsilonSchedule(
        replay_warmup_decisions=int(epsilon["replay_warmup_decisions"]),
        decay_decisions=int(epsilon["decay_decisions"]),
        initial_epsilon=float(epsilon["initial_epsilon"]),
        final_epsilon=float(epsilon["final_epsilon"]),
    )


def _expected_checkpoint_decision(update_count: int) -> int:
    return 10_000 + (update_count - 1) * 4


def _episode_metrics(context: Dict[str, Any], transition: Dict[str, Any]) -> Dict[str, Any]:
    episodes = context["episodes"]
    active_ended = bool(transition["terminated"] or transition["truncated"])
    completed_episode_count = sum(
        1 for episode in episodes if episode["unity_episode_ended"]
    )
    completed_return_sum = float(
        sum(
            float(episode["return"])
            for episode in episodes
            if episode["unity_episode_ended"]
        )
    )
    active_prefix = 0.0 if active_ended else float(context["active_episode_return"])
    observed_episode_count = completed_episode_count + (0 if active_ended else 1)
    if observed_episode_count < 1:
        raise LLAPIContractError("R3T learning-curve denominator is empty.")
    success_count = sum(
        1
        for episode in episodes
        if episode["unity_episode_ended"] and episode["end_kind"] == "terminal"
    )
    mean_return = (completed_return_sum + active_prefix) / observed_episode_count
    success_rate = success_count / observed_episode_count
    values = {
        "completed_episode_count": completed_episode_count,
        "observed_episode_count": observed_episode_count,
        "completed_episode_return_sum": completed_return_sum,
        "active_episode_ended": active_ended,
        "active_episode_prefix_return": active_prefix,
        "mean_episode_return": mean_return,
        "success_count": success_count,
        "success_rate": success_rate,
        "denominators": {"observed_episode_count": observed_episode_count},
    }
    if not all(
        math.isfinite(float(values[key]))
        for key in (
            "completed_episode_return_sum",
            "active_episode_prefix_return",
            "mean_episode_return",
            "success_rate",
        )
    ):
        raise LLAPIContractError("R3T learning-curve episode metric is non-finite.")
    return values


def _record_update_observer(
    *,
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
    worker_output: Path,
    root: Path,
    lineage: Dict[str, Any],
    controller: BDQOptimizerController,
    collector: Any,
    selector: ScheduledEpsilonGreedyBDQActionSelector,
    result: Any,
    transition: Dict[str, Any],
    event: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    update_count = int(result.optimizer_update_count)
    curve = lineage["learning_curve"]
    if update_count % int(contract["learning_curve"]["interval_updates"]) != 0:
        return
    expected_update_count = int(contract["learning_curve"]["first_update_count"]) + (
        len(curve) * int(contract["learning_curve"]["interval_updates"])
    )
    if update_count != expected_update_count:
        raise LLAPIContractError("R3T learning-curve update samples are not contiguous.")
    telemetry = controller.last_update_telemetry
    if telemetry is None:
        raise LLAPIContractError("R3T optimizer omitted registered update telemetry.")
    sampled_indices = [int(value) for value in telemetry["sampled_indices"]]
    if len(sampled_indices) != controller.settings.batch_size or len(set(sampled_indices)) != len(sampled_indices):
        raise LLAPIContractError("R3T replay sample telemetry is not without replacement.")
    q_value_summary = copy.deepcopy(telemetry["q_value_summary"])
    state_digest = checkpoint_state_sha256(controller, collector, selector)
    checkpoint_records = lineage["checkpoint_records"]
    if update_count in contract["checkpoint"]["save_update_counts"]:
        expected_checkpoint_path = (
            worker_output
            / "checkpoints"
            / f"update-{update_count:05d}.json"
        )
        if expected_checkpoint_path.exists():
            raise FileExistsError(f"R3T checkpoint must be fresh: {expected_checkpoint_path}")
        boundary = save_controller_checkpoint(
            expected_checkpoint_path,
            controller,
            collector,
            selector,
        )
        checkpoint = _read_json(expected_checkpoint_path)
        if checkpoint["state_sha256"] != state_digest:
            raise LLAPIContractError("R3T checkpoint state hash differs from observer state.")
        if checkpoint["state"]["verification"] != boundary:
            raise LLAPIContractError("R3T checkpoint boundary verification differs from summary.")
        checkpoint_records.append(
            {
                "optimizer_update_count": update_count,
                "decision_count": int(result.decision_count),
                "path": _artifact_relative(expected_checkpoint_path, root),
                "sha256": sha256_file(expected_checkpoint_path),
                "bytes": expected_checkpoint_path.stat().st_size,
                "state_sha256": checkpoint["state_sha256"],
                "boundary": boundary,
            }
        )
    episode_metrics = _episode_metrics(context, transition)
    curve.append(
        {
            "optimizer_update_count": update_count,
            "decision_count": int(result.decision_count),
            "replay_size": int(result.replay_size),
            "target_sync_count": int(result.target_sync_count),
            "loss": float(event["loss"]),
            "mean_absolute_td_error": float(event["mean_absolute_td_error"]),
            "online_after_sha256": event["online_after_sha256"],
            "target_after_sha256": event["target_after_sha256"],
            "sampled_indices": sampled_indices,
            "q_value_summary": q_value_summary,
            "checkpoint_state_sha256": state_digest,
            "update_duration_seconds": float(context["duration_seconds"]),
            **episode_metrics,
        }
    )


def _validate_q_summary(summary: Dict[str, Any]) -> None:
    for name in ("current", "online_next", "target_next"):
        for branch in summary[name]:
            values = [float(branch[key]) for key in ("mean", "minimum", "maximum")]
            if not all(math.isfinite(value) for value in values):
                raise LLAPIContractError(f"R3T {name} Q summary is non-finite.")
            if branch["minimum"] > branch["maximum"] or not (
                branch["minimum"] <= branch["mean"] <= branch["maximum"]
            ):
                raise LLAPIContractError(f"R3T {name} Q summary ordering is invalid.")


def _validate_lineage(
    trace: Dict[str, Any],
    metrics: Dict[str, Any],
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
    root: Path,
) -> None:
    lineage = trace["lineage"]
    if metrics["learning_curve"] != lineage["learning_curve"]:
        raise LLAPIContractError("R3T metrics and trace learning curves differ.")
    expected_updates = list(range(100, 10_001, 100))
    curve = lineage["learning_curve"]
    if [item["optimizer_update_count"] for item in curve] != expected_updates:
        raise LLAPIContractError("R3T learning-curve update counts drifted.")
    events = trace["optimization"]["update_events"]
    for sample in curve:
        update_count = sample["optimizer_update_count"]
        event = events[update_count - 1]
        expected_decision = _expected_checkpoint_decision(update_count)
        if sample["decision_count"] != expected_decision or sample["replay_size"] != expected_decision:
            raise LLAPIContractError("R3T learning-curve decision boundary drifted.")
        for key in (
            "loss",
            "mean_absolute_td_error",
            "online_after_sha256",
            "target_after_sha256",
        ):
            if sample[key] != event[key]:
                raise LLAPIContractError(f"R3T learning-curve {key} differs from update event.")
        if sample["target_sync_count"] != event["target_sync_count"]:
            raise LLAPIContractError("R3T learning-curve target-sync count drifted.")
        if len(sample["sampled_indices"]) != 64 or len(set(sample["sampled_indices"])) != 64:
            raise LLAPIContractError("R3T learning-curve replay sample is not exact.")
        if sample["denominators"] != {
            "observed_episode_count": sample["observed_episode_count"]
        }:
            raise LLAPIContractError("R3T learning-curve denominator is not explicit.")
        expected_mean = (
            sample["completed_episode_return_sum"]
            + sample["active_episode_prefix_return"]
        ) / sample["observed_episode_count"]
        if not math.isclose(sample["mean_episode_return"], expected_mean, rel_tol=0.0, abs_tol=1e-7):
            raise LLAPIContractError("R3T learning-curve return aggregation drifted.")
        if sample["active_episode_ended"] and sample["active_episode_prefix_return"] != 0.0:
            raise LLAPIContractError("R3T ended episode retained an active prefix.")
        if sample["success_count"] > sample["completed_episode_count"] or sample["completed_episode_count"] > sample["observed_episode_count"]:
            raise LLAPIContractError("R3T learning-curve episode counts are invalid.")
        if not math.isclose(
            sample["success_rate"],
            sample["success_count"] / sample["observed_episode_count"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise LLAPIContractError("R3T learning-curve success denominator drifted.")
        _validate_q_summary(sample["q_value_summary"])
        if not math.isfinite(sample["update_duration_seconds"]):
            raise LLAPIContractError("R3T learning-curve timing is non-finite.")
    checkpoints = lineage["checkpoint_records"]
    expected_checkpoint_updates = contract["checkpoint"]["save_update_counts"]
    if [item["optimizer_update_count"] for item in checkpoints] != expected_checkpoint_updates:
        raise LLAPIContractError("R3T checkpoint cadence records drifted.")
    checkpoint_schema = _read_json(CHECKPOINT_SCHEMA_PATH)
    Draft202012Validator.check_schema(checkpoint_schema)
    checkpoint_validator = Draft202012Validator(checkpoint_schema)
    for record in checkpoints:
        update_count = int(record["optimizer_update_count"])
        expected_decision = _expected_checkpoint_decision(update_count)
        if record["decision_count"] != expected_decision:
            raise LLAPIContractError("R3T checkpoint decision boundary drifted.")
        checkpoint_path = (root / record["path"]).resolve()
        if _artifact_relative(checkpoint_path, root) != record["path"] or not checkpoint_path.is_file():
            raise LLAPIContractError("R3T checkpoint path is missing or outside the root.")
        if sha256_file(checkpoint_path) != record["sha256"] or checkpoint_path.stat().st_size != record["bytes"]:
            raise LLAPIContractError("R3T checkpoint artifact checksum drifted.")
        checkpoint = _read_json(checkpoint_path)
        checkpoint_validator.validate(checkpoint)
        if checkpoint["schema_version"] != CHECKPOINT_SCHEMA_VERSION or checkpoint["state_sha256"] != record["state_sha256"]:
            raise LLAPIContractError("R3T checkpoint identity drifted.")
        if checkpoint["contract_sha256"] != contract["base_checkpoint_contract"]["sha256"]:
            raise LLAPIContractError("R3T checkpoint contract identity drifted.")
        if checkpoint["identity"]["runtime"] != contract["runtime"]:
            raise LLAPIContractError("R3T checkpoint runtime identity drifted.")
        if checkpoint["identity"]["package"] != {
            "distribution": contract["package"]["distribution"],
            "version": contract["package"]["version"],
        }:
            raise LLAPIContractError("R3T checkpoint package identity drifted.")
        if checkpoint["identity"]["settings"] != dataclasses.asdict(BDQOptimizationSettings()):
            raise LLAPIContractError("R3T checkpoint settings identity drifted.")
        if checkpoint["identity"]["seeds"] != {
            "controller_seed": mapping["policy_initialization_seed"],
            "exploration_seed": mapping["exploration_seed"],
        }:
            raise LLAPIContractError("R3T checkpoint seed identity drifted.")
        if checkpoint["state"]["verification"] != record["boundary"]:
            raise LLAPIContractError("R3T checkpoint boundary record drifted.")
        sample = curve[update_count // 100 - 1]
        expected_sync_count = 1 if update_count == 10_000 else 0
        expected_boundary = {
            "controller_seed": mapping["policy_initialization_seed"],
            "exploration_seed": mapping["exploration_seed"],
            "decision_count": expected_decision,
            "optimizer_update_count": update_count,
            "target_sync_count": expected_sync_count,
            "pending_agent_ids": [],
        }
        if {
            key: record["boundary"][key] for key in expected_boundary
        } != expected_boundary:
            raise LLAPIContractError("R3T checkpoint boundary counters drifted.")
        boundary_replay = record["boundary"]["replay"]
        if boundary_replay["size"] != expected_decision or boundary_replay["cursor"] != expected_decision or boundary_replay["frame_reference_count"] != expected_decision * 8:
            raise LLAPIContractError("R3T checkpoint replay counters drifted.")
        if boundary_replay["accounted_storage_bytes"] + boundary_replay["remaining_accounted_storage_bytes"] != boundary_replay["max_accounted_storage_bytes"]:
            raise LLAPIContractError("R3T checkpoint storage accounting drifted.")
        if record["boundary"]["online_network_sha256"] != sample["online_after_sha256"] or record["boundary"]["target_network_sha256"] != sample["target_after_sha256"]:
            raise LLAPIContractError("R3T checkpoint network hashes drifted.")
        if sample["checkpoint_state_sha256"] != record["state_sha256"]:
            raise LLAPIContractError("R3T checkpoint-equivalent curve hash drifted.")
    if metrics["contract_sha256"] != sha256_file(CONTRACT_PATH):
        raise LLAPIContractError("R3T metrics contract hash drifted.")
    if metrics["run_id"] != mapping["run_id"] or metrics["policy_seed"] != mapping["policy_initialization_seed"]:
        raise LLAPIContractError("R3T metrics seed identity drifted.")
    curve_contract = contract["learning_curve"]
    if metrics["return_definition"] != curve_contract["return_definition"] or metrics["success_definition"] != curve_contract["success_definition"] or metrics["denominator_definition"] != DENOMINATOR_DEFINITION:
        raise LLAPIContractError("R3T metrics definitions drifted.")


def _validate_trace_player_provenance(
    trace: Dict[str, Any],
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
    root: Path,
) -> None:
    recorded = trace["provenance"]["player"]
    player = contract["player_execution"]
    source = _source_player_identity(contract)
    if recorded["source_executable"] != player["source_executable"]:
        raise LLAPIContractError("R3T trace source executable provenance drifted.")
    for key in (
        "source_manifest_sha256",
        "source_file_count",
        "source_total_bytes",
        "executable_sha256",
    ):
        if recorded[key] != player[key]:
            raise LLAPIContractError(f"R3T trace source provenance drifted at {key}.")
    copy_executable = (root / recorded["copy_executable"]).resolve()
    expected_copy_path = (
        root
        / "player-copies"
        / mapping["run_id"]
        / Path(player["source_executable"]).name
    ).resolve()
    if copy_executable != expected_copy_path or not copy_executable.is_file():
        raise LLAPIContractError("R3T trace copy executable provenance drifted.")
    copy_identity = _manifest_identity(copy_executable.parent)
    _runtime_player_mutations(contract, source, copy_identity["manifest"])
    if {
        "copy_manifest_sha256": source["manifest_sha256"],
        "copy_file_count": source["file_count"],
        "copy_total_bytes": source["total_bytes"],
    } != {
        "copy_manifest_sha256": recorded["copy_manifest_sha256"],
        "copy_file_count": recorded["copy_file_count"],
        "copy_total_bytes": recorded["copy_total_bytes"],
    }:
        raise LLAPIContractError("R3T trace copy manifest provenance drifted.")
    if sha256_file(copy_executable) != recorded["executable_sha256"]:
        raise LLAPIContractError("R3T trace copy executable hash drifted.")


def _validate_trace_and_metrics(
    trace: Dict[str, Any],
    metrics: Dict[str, Any],
    result_schema: Dict[str, Any],
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
    root: Path,
) -> None:
    Draft202012Validator(_trace_schema(result_schema)).validate(trace)
    Draft202012Validator(_metrics_schema(result_schema)).validate(metrics)
    gate_contract = _gate_contract(contract, mapping)
    validate_update_gate_trace(
        trace,
        result_schema,
        contract_path=CONTRACT_PATH,
        task_name=f"{TASK_NAME} {mapping['run_id']}",
        require_update_hashes=True,
        contract=gate_contract,
        allow_replay_storage=True,
        allow_target_synchronization=True,
        expected_target_sync_updates=(10000,),
        require_target_hashes=True,
    )
    validate_scheduled_selector(
        trace["selector"],
        gate_contract["epsilon_schedule"],
        task_name=f"{TASK_NAME} {mapping['run_id']}",
    )
    if trace["run_id"] != mapping["run_id"] or trace["run_ordinal"] != mapping["ordinal"]:
        raise LLAPIContractError("R3T trace run identity drifted.")
    if trace["policy_seed"] != mapping["policy_initialization_seed"] or trace["scenario_seed"] != mapping["scenario_seed"]:
        raise LLAPIContractError("R3T trace seed identity drifted.")
    provenance = trace["provenance"]
    if provenance["scenario_seed"] != mapping["scenario_seed"] or provenance["policy_initialization_seed"] != mapping["policy_initialization_seed"] or provenance["replay_sampling_seed"] != mapping["replay_sampling_seed"] or provenance["exploration_seed"] != mapping["exploration_seed"]:
        raise LLAPIContractError("R3T trace provenance seed mapping drifted.")
    _validate_trace_player_provenance(trace, contract, mapping, root)
    if trace["lineage"]["checkpoint_records"] and trace["lineage"]["checkpoint_records"][-1]["optimizer_update_count"] != 10000:
        raise LLAPIContractError("R3T selected checkpoint is not the final registered update.")
    _validate_lineage(trace, metrics, contract, mapping, root)


def _build_metrics(contract: Dict[str, Any], mapping: Dict[str, Any], lineage: Dict[str, Any]) -> Dict[str, Any]:
    curve_contract = contract["learning_curve"]
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "run_id": mapping["run_id"],
        "policy_seed": mapping["policy_initialization_seed"],
        "return_definition": curve_contract["return_definition"],
        "success_definition": curve_contract["success_definition"],
        "denominator_definition": DENOMINATOR_DEFINITION,
        "learning_curve": lineage["learning_curve"],
    }


def _run_worker(
    arguments: argparse.Namespace,
    contract: Dict[str, Any],
    result_schema: Dict[str, Any],
) -> int:
    if (
        arguments.run_id is None
        or arguments.env is None
        or arguments.worker_output is None
        or arguments.worker_index is None
    ):
        raise ValueError("R3T worker mode arguments are incomplete.")
    mapping = _mapping_for_run(contract, arguments.run_id)
    if int(arguments.worker_index) != int(mapping["ordinal"]) - 1:
        raise LLAPIContractError("R3T worker ordinal does not match the seed table.")
    root = _campaign_root(contract)
    worker_output, player_root = _validate_run_paths(
        contract,
        mapping["run_id"],
        arguments.worker_output.resolve(),
        arguments.env.resolve(),
    )
    copied_executable = arguments.env.resolve()
    source = _source_player_identity(contract)
    copy_identity = _validate_player_copy(contract, source, copied_executable, player_root)
    lineage: Dict[str, Any] = {"checkpoint_records": [], "learning_curve": []}
    provenance = _trace_provenance(
        contract, mapping, source, copy_identity, copied_executable, root
    )
    trace = execute_update_gate_worker(
        copied_executable,
        worker_output,
        int(arguments.worker_index),
        contract,
        gate_contract=_gate_contract(contract, mapping),
        contract_path=CONTRACT_PATH,
        trace_file_name=TRACE_FILE_NAME,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        task_name=f"{TASK_NAME} {mapping['run_id']}",
        record_update_hashes=True,
        record_target_hashes=True,
        base_port=BASE_WORKER_PORT + int(arguments.worker_index) * 4,
        timeout_wait=300,
        progress_interval=5_000,
        profiling_output_directory=contract["player_execution"]["profiling_output_directory"],
        trace_metadata={
            "run_id": mapping["run_id"],
            "run_ordinal": int(mapping["ordinal"]),
            "lineage": lineage,
            "provenance": provenance,
        },
        update_observer=lambda controller, collector, selector, result, transition, event, context: _record_update_observer(
            contract=contract,
            mapping=mapping,
            worker_output=worker_output,
            root=root,
            lineage=lineage,
            controller=controller,
            collector=collector,
            selector=selector,
            result=result,
            transition=transition,
            event=event,
            context=context,
        ),
    )
    _validate_player_copy(
        contract,
        source,
        copied_executable,
        player_root,
        allow_runtime_mutations=True,
    )
    metrics = _build_metrics(contract, mapping, lineage)
    metrics_path = worker_output / METRICS_FILE_NAME
    _write_json(metrics, metrics_path)
    _validate_trace_and_metrics(
        trace,
        metrics,
        result_schema,
        contract,
        mapping,
        root,
    )
    if _read_json(worker_output / TRACE_FILE_NAME) != trace:
        raise LLAPIContractError("R3T returned trace differs from its persisted trace.")
    print(f"trace={worker_output / TRACE_FILE_NAME}")
    print(f"metrics={metrics_path}")
    print(f"checkpoints={len(lineage['checkpoint_records'])}")
    print(f"transitions={trace['cutoff']['transition_limit']}")
    print(f"optimizer_updates={trace['optimization']['optimizer_update_count']}")
    print(f"target_synchronizations={trace['optimization']['target_sync_count']}")
    return 0


def _restore_payload(
    contract: Dict[str, Any],
    mapping: Dict[str, Any],
    checkpoint_path: Path,
    root: Path,
) -> Dict[str, Any]:
    configure_torch(contract["determinism"], f"{TASK_NAME} {mapping['run_id']} restorer")
    expected_path = (
        root
        / "runs"
        / mapping["run_id"]
        / "checkpoints"
        / "update-10000.json"
    ).resolve()
    if checkpoint_path.resolve() != expected_path:
        raise LLAPIContractError("R3T restore path is not the selected checkpoint.")
    loaded = load_controller_checkpoint(
        checkpoint_path,
        settings=BDQOptimizationSettings(),
        controller_seed=int(mapping["policy_initialization_seed"]),
        exploration_seed=int(mapping["exploration_seed"]),
        schedule=_schedule(contract),
    )
    boundary = loaded.verification
    expected_boundary = {
        "decision_count": 49_996,
        "optimizer_update_count": 10_000,
        "target_sync_count": 1,
        "pending_agent_ids": [],
    }
    if {key: boundary[key] for key in expected_boundary} != expected_boundary:
        raise LLAPIContractError("R3T restored checkpoint boundary drifted.")
    restored_state_digest = checkpoint_state_sha256(
        loaded.controller,
        loaded.collector,
        loaded.selector,
    )
    checkpoint = _read_json(checkpoint_path)
    if checkpoint["state_sha256"] != restored_state_digest:
        raise LLAPIContractError("R3T restored checkpoint state hash differs.")
    return {
        "schema_version": RESTORE_SCHEMA_VERSION,
        "run_id": mapping["run_id"],
        "checkpoint": {
            "path": _artifact_relative(checkpoint_path, root),
            "sha256": sha256_file(checkpoint_path),
            "bytes": checkpoint_path.stat().st_size,
        },
        "checkpoint_state_sha256": checkpoint["state_sha256"],
        "restored_state_sha256": restored_state_digest,
        "boundary": boundary,
        "loaded_without_unity": True,
        "parity": {
            "state_hash": True,
            "boundary": True,
            "settings": True,
            "replay": True,
            "selector_rng": True,
        },
    }


def _run_restore(
    arguments: argparse.Namespace,
    contract: Dict[str, Any],
    result_schema: Dict[str, Any],
) -> int:
    if (
        arguments.run_id is None
        or arguments.checkpoint is None
        or arguments.restore_output is None
    ):
        raise ValueError("R3T restore mode arguments are incomplete.")
    mapping = _mapping_for_run(contract, arguments.run_id)
    root = _campaign_root(contract)
    checkpoint_path = arguments.checkpoint.resolve()
    restore_output = arguments.restore_output.resolve()
    expected_restore_output = (
        root / "runs" / mapping["run_id"] / RESTORE_FILE_NAME
    ).resolve()
    if restore_output != expected_restore_output:
        raise LLAPIContractError("R3T restore output differs from its registered run path.")
    if restore_output.exists():
        raise FileExistsError(f"R3T restore output must be fresh: {restore_output}")
    payload = _restore_payload(contract, mapping, checkpoint_path, root)
    Draft202012Validator(_restore_schema(result_schema)).validate(payload)
    _write_json(payload, restore_output)
    print(f"restore={restore_output}")
    print("loaded_without_unity=true")
    print("checkpoint_restore=pass")
    return 0


def _manifest(
    contract: Dict[str, Any],
    source: Dict[str, Any],
    root: Path,
) -> Dict[str, Any]:
    player = contract["player_execution"]
    return {
        "schema_version": "quickdraw.bdq-r3t-basic-multiseed-manifest.v1",
        "task": TASK_NAME,
        "contract_path": _repo_relative(CONTRACT_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runtime": copy.deepcopy(contract["runtime"]),
        "package": copy.deepcopy(contract["package"]),
        "player": {
            "source_executable": source["path"],
            "project_settings_path": player["project_settings_path"],
            "required_siblings": copy.deepcopy(player["required_siblings"]),
            "source_manifest_sha256": source["manifest_sha256"],
            "source_file_count": source["file_count"],
            "source_total_bytes": source["total_bytes"],
            "executable_sha256": source["executable_sha256"],
            "profiling_output_directory": player["profiling_output_directory"],
            "runtime_mutated_files": copy.deepcopy(
                player["runtime_mutated_files"]
            ),
        },
        "campaign": copy.deepcopy(contract["campaign"]),
        "collection": copy.deepcopy(contract["collection"]),
        "optimization": copy.deepcopy(contract["optimization"]),
        "training_horizon": copy.deepcopy(contract["training_horizon"]),
        "checkpoint": copy.deepcopy(contract["checkpoint"]),
        "learning_curve": copy.deepcopy(contract["learning_curve"]),
        "artifact_layout": copy.deepcopy(contract["artifact_layout"]),
        "process_leak_audit": copy.deepcopy(contract["process_leak_audit"]),
        "canonicalization": {
            "excluded_fields": [
                "timestamps",
                "process identifiers",
                "player runtime sidecar contents",
                "absolute paths",
                "worker log paths",
                "wall-clock timing values",
                "serialized trace and metrics artifact bytes and hashes in campaign metadata",
            ],
            "implementation": "recursive JSON canonicalization with timing, process-audit, runtime-sidecar, and serialized trace/metrics artifact metadata fields excluded",
        },
        "commands": {
            "parent": [
                "python",
                "-B",
                "Research/trainer/run_bdq_r3t_multiseed.py",
                "--env",
                source["path"],
                "--output",
                contract["artifact_layout"]["root"],
            ],
            "worker": [
                "python",
                "-B",
                "Research/trainer/run_bdq_r3t_multiseed.py",
                "--mode=worker",
                "--env=player-copies/{run_id}/QuickDrawResearchBasic.exe",
                "--worker-output=runs/{run_id}",
                "--worker-index={ordinal_minus_one}",
                "--run-id={run_id}",
            ],
            "restore": [
                "python",
                "-B",
                "Research/trainer/run_bdq_r3t_multiseed.py",
                "--mode=restore",
                "--checkpoint=runs/{run_id}/checkpoints/update-10000.json",
                "--restore-output=runs/{run_id}/restore.json",
                "--run-id={run_id}",
            ],
            "working_directory": {
                "parent": "repository root",
                "worker": "registered campaign root",
                "restore": "registered campaign root",
            },
        },
    }


def _stable_error_text(error: BaseException, artifact_root: Path) -> str:
    text = f"{type(error).__name__}: {error}"
    replacements = (
        (artifact_root.resolve(), "<artifact-root>"),
        (REPO_ROOT.resolve(), "<repo-root>"),
    )
    for path, replacement in replacements:
        text = text.replace(str(path), replacement)
        text = text.replace(str(path).replace("\\", "/"), replacement)
    return text


def _write_rejected_attempt(
    root: Path,
    mapping: Dict[str, Any],
    error: BaseException,
    process_leak_audit: Dict[str, Any] | None = None,
) -> Path:
    retained_output = root / "runs" / mapping["run_id"]
    retained_output.mkdir(parents=True, exist_ok=True)
    path = root / "rejected" / f"{mapping['run_id']}.json"
    if path.exists():
        raise FileExistsError(f"R3T rejected-attempt record already exists: {path}")
    payload = {
        "run_id": mapping["run_id"],
        "run_ordinal": int(mapping["ordinal"]),
        "policy_seed": int(mapping["policy_initialization_seed"]),
        "status": "rejected",
        "error": _stable_error_text(error, root),
        "retained_output": _artifact_relative(retained_output, root),
    }
    if process_leak_audit is not None:
        payload["process_leak_audit"] = copy.deepcopy(process_leak_audit)
    _write_json(payload, path)
    return path


def _build_campaign_result(
    contract: Dict[str, Any],
    manifest_sha256: str,
    runs: Sequence[Dict[str, Any]],
    rejected: Sequence[Dict[str, Any]],
    fresh_training_process_count: int,
    fresh_restore_process_count: int,
) -> Dict[str, Any]:
    mappings = _mapping_table(contract)
    accepted = (
        len(runs) == len(mappings)
        and not rejected
        and [run["run_id"] for run in runs]
        == [mapping["run_id"] for mapping in mappings]
        and [run["policy_seed"] for run in runs]
        == [mapping["policy_initialization_seed"] for mapping in mappings]
    )
    result: Dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "accepted" if accepted else "rejected",
        "task": TASK_NAME,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "manifest_sha256": manifest_sha256,
        "run_count": len(mappings),
        "fresh_training_process_count": fresh_training_process_count,
        "fresh_restore_process_count": fresh_restore_process_count,
        "exact_seed_coverage": accepted,
        "all_runs_accepted": accepted,
        "runs": list(runs),
        "rejected_attempts": list(rejected),
        "claim_boundary": copy.deepcopy(contract["claim_boundary"]),
    }
    result["canonical_campaign_sha256"] = canonical_json_sha256(
        _canonicalize_campaign_result(result)
    )
    return result


def _validate_campaign_result(
    result: Dict[str, Any],
    result_schema: Dict[str, Any],
    contract: Dict[str, Any],
    manifest_sha256: str,
) -> None:
    Draft202012Validator(result_schema).validate(result)
    if result["contract_sha256"] != sha256_file(CONTRACT_PATH) or result[
        "manifest_sha256"
    ] != manifest_sha256:
        raise LLAPIContractError("R3T campaign result identity drifted.")
    if result["canonical_campaign_sha256"] != canonical_json_sha256(
        _canonicalize_campaign_result(
            {
                key: value
                for key, value in result.items()
                if key != "canonical_campaign_sha256"
            }
        )
    ):
        raise LLAPIContractError("R3T campaign canonical hash does not match result.")
    mappings = _mapping_table(contract)
    accepted = result["status"] == "accepted"
    if accepted:
        if not result["exact_seed_coverage"] or not result["all_runs_accepted"]:
            raise LLAPIContractError("R3T accepted result omitted exact seed coverage.")
        if result["rejected_attempts"] or len(result["runs"]) != len(mappings):
            raise LLAPIContractError("R3T accepted result contains incomplete runs.")
        if result["fresh_training_process_count"] != 5 or result[
            "fresh_restore_process_count"
        ] != 5:
            raise LLAPIContractError("R3T accepted process count is not five training and five restore processes.")
        for run, mapping in zip(result["runs"], mappings):
            if {
                run["run_id"],
                run["run_ordinal"],
                run["policy_seed"],
                run["scenario_seed"],
                run["exploration_seed"],
            } != {
                mapping["run_id"],
                mapping["ordinal"],
                mapping["policy_initialization_seed"],
                mapping["scenario_seed"],
                mapping["exploration_seed"],
            }:
                raise LLAPIContractError("R3T accepted run seed mapping drifted.")
    else:
        if result["exact_seed_coverage"] or result["all_runs_accepted"]:
            raise LLAPIContractError("R3T rejected result claims acceptance.")
        accepted_run_count = len(result["runs"])
        for field in (
            "fresh_training_process_count",
            "fresh_restore_process_count",
        ):
            count = result[field]
            if count < accepted_run_count or count > accepted_run_count + 1:
                raise LLAPIContractError(
                    f"R3T rejected result {field} does not match the bounded launch count."
                )


def _run_parent(
    arguments: argparse.Namespace,
    contract: Dict[str, Any],
    result_schema: Dict[str, Any],
) -> int:
    if arguments.env is None or arguments.output is None:
        raise ValueError("R3T parent mode arguments are incomplete.")
    root = _campaign_root(contract)
    output = arguments.output.resolve()
    if output != root:
        raise ValueError(f"R3T output must be the registered campaign root: {root}.")
    source = _source_player_identity(contract)
    if arguments.env.resolve() != source["executable"].resolve():
        raise ValueError("R3T --env must equal the contract-bound source executable.")
    _prepare_fresh_campaign_root(output)
    manifest = _manifest(contract, source, output)
    manifest_path = output / MANIFEST_FILE_NAME
    _write_json(manifest, manifest_path)
    manifest_sha256 = sha256_file(manifest_path)
    runs: list[Dict[str, Any]] = []
    rejected: list[Dict[str, Any]] = []
    fresh_training_process_count = 0
    fresh_restore_process_count = 0

    def mark_training_process_started() -> None:
        nonlocal fresh_training_process_count
        fresh_training_process_count += 1

    def mark_restore_process_started() -> None:
        nonlocal fresh_restore_process_count
        fresh_restore_process_count += 1

    mappings = _mapping_table(contract)
    (output / "runs").mkdir()
    (output / "player-copies").mkdir()
    (output / "logs").mkdir()
    current_mapping: Dict[str, Any] | None = None
    current_process_leak_audit: Dict[str, Any] | None = None
    try:
        for mapping in mappings:
            current_mapping = mapping
            current_process_leak_audit = None
            run_id = mapping["run_id"]
            run_root = output / "runs" / run_id
            player_root = output / "player-copies" / run_id
            copied_executable = copy_complete_player(
                source["executable"],
                player_root,
                required_siblings=contract["player_execution"]["required_siblings"],
            )
            copy_identity = _validate_player_copy(
                contract, source, copied_executable, player_root
            )
            before_pids = _tasklist_pids(copied_executable.name)
            worker_error: BaseException | None = None
            try:
                run_fresh_python_process(
                    runner_path=Path(__file__),
                    arguments=[
                        "--mode=worker",
                        f"--env={copied_executable}",
                        f"--worker-output={run_root}",
                        f"--worker-index={int(mapping['ordinal']) - 1}",
                        f"--run-id={run_id}",
                    ],
                    output_directory=output / "logs",
                    log_name=f"worker-{run_id}.log",
                    task_name=f"{TASK_NAME} {run_id}",
                    contract=contract,
                    repo_root=REPO_ROOT,
                    timeout_seconds=WORKER_TIMEOUT_SECONDS,
                    on_process_started=mark_training_process_started,
                )
            except BaseException as error:
                worker_error = error
            try:
                after_pids = _tasklist_pids(copied_executable.name)
                current_process_leak_audit = _process_audit(
                    copied_executable.name, before_pids, after_pids
                )
            except BaseException as audit_error:
                if worker_error is not None:
                    worker_error.add_note(
                        "R3T process-leak audit failed while preserving the worker failure: "
                        f"{type(audit_error).__name__}: {audit_error}"
                    )
                    raise worker_error from audit_error
                raise
            if worker_error is not None:
                raise worker_error
            audit = current_process_leak_audit
            if audit is None:
                raise LLAPIContractError("R3T worker process-leak audit was not recorded.")
            if not audit["passed"]:
                raise LLAPIContractError("R3T worker left a new matching Unity process.")
            post_copy_identity = _validate_player_copy(
                contract,
                source,
                copied_executable,
                player_root,
                allow_runtime_mutations=True,
            )
            player_runtime_mutations = _runtime_player_mutations(
                contract, source, post_copy_identity["manifest"]
            )
            trace_path = run_root / TRACE_FILE_NAME
            metrics_path = run_root / METRICS_FILE_NAME
            trace = _read_json(trace_path)
            metrics = _read_json(metrics_path)
            _validate_trace_and_metrics(
                trace,
                metrics,
                result_schema,
                contract,
                mapping,
                output,
            )
            selected = trace["lineage"]["checkpoint_records"][-1]
            restore_path = run_root / RESTORE_FILE_NAME
            run_fresh_python_process(
                runner_path=Path(__file__),
                arguments=[
                    "--mode=restore",
                    f"--checkpoint={output / selected['path']}",
                    f"--restore-output={restore_path}",
                    f"--run-id={run_id}",
                ],
                output_directory=output / "logs",
                log_name=f"restore-{run_id}.log",
                task_name=f"{TASK_NAME} {run_id} restorer",
                contract=contract,
                repo_root=REPO_ROOT,
                timeout_seconds=WORKER_TIMEOUT_SECONDS,
                on_process_started=mark_restore_process_started,
            )
            restore = _read_json(restore_path)
            Draft202012Validator(_restore_schema(result_schema)).validate(restore)
            if restore["run_id"] != run_id or restore["checkpoint"] != {
                "path": selected["path"],
                "sha256": selected["sha256"],
                "bytes": selected["bytes"],
            } or restore["checkpoint_state_sha256"] != selected["state_sha256"] or restore[
                "restored_state_sha256"
            ] != selected["state_sha256"] or restore["boundary"] != selected["boundary"]:
                raise LLAPIContractError("R3T fresh restore does not match selected checkpoint.")
            run_result = {
                "schema_version": RUN_RESULT_SCHEMA_VERSION,
                "status": "accepted",
                "task": TASK_NAME,
                "contract_sha256": sha256_file(CONTRACT_PATH),
                "run_id": run_id,
                "run_ordinal": int(mapping["ordinal"]),
                "policy_seed": int(mapping["policy_initialization_seed"]),
                "scenario_seed": int(mapping["scenario_seed"]),
                "exploration_seed": int(mapping["exploration_seed"]),
                "trace": {
                    "path": _artifact_relative(trace_path, output),
                    "sha256": sha256_file(trace_path),
                    "bytes": trace_path.stat().st_size,
                },
                "metrics": {
                    "path": _artifact_relative(metrics_path, output),
                    "sha256": sha256_file(metrics_path),
                    "bytes": metrics_path.stat().st_size,
                },
                "canonical_trace_sha256": _canonical_digest(trace),
                "canonical_metrics_sha256": _canonical_digest(metrics),
                "checkpoint_records": trace["lineage"]["checkpoint_records"],
                "selected_checkpoint": selected,
                "restore": restore,
                "process_leak_audit": audit,
                "player_runtime_mutations": player_runtime_mutations,
                "claim_boundary": copy.deepcopy(contract["claim_boundary"]),
            }
            Draft202012Validator(_run_result_schema(result_schema)).validate(run_result)
            _write_json(run_result, run_root / RUN_RESULT_FILE_NAME)
            runs.append(run_result)
            print(f"run={run_id} status=accepted", flush=True)
    except (Exception, KeyboardInterrupt) as error:
        if current_mapping is None:
            error.add_note("R3T failed before a run mapping was active; no rejected run record was written.")
        else:
            try:
                rejection_path = _write_rejected_attempt(
                    output,
                    current_mapping,
                    error,
                    process_leak_audit=current_process_leak_audit,
                )
                rejected.append(_read_json(rejection_path))
                result = _build_campaign_result(
                    contract,
                    manifest_sha256,
                    runs,
                    rejected,
                    fresh_training_process_count,
                    fresh_restore_process_count,
                )
                _validate_campaign_result(result, result_schema, contract, manifest_sha256)
                _write_json(result, output / "result.json")
            except Exception as retention_error:
                error.add_note(
                    "R3T could not retain its rejected-result record: "
                    f"{type(retention_error).__name__}: {retention_error}"
                )
        raise

    result = _build_campaign_result(
        contract,
        manifest_sha256,
        runs,
        rejected,
        fresh_training_process_count,
        fresh_restore_process_count,
    )
    _validate_campaign_result(result, result_schema, contract, manifest_sha256)
    _write_json(result, output / "result.json")
    print(f"result={output / 'result.json'}")
    print("status=accepted")
    print("fresh_training_processes=5")
    print("fresh_restore_processes=5")
    print("exact_seed_coverage=pass")
    print("complete_lineage=pass")
    print("checkpoint_restore=pass")
    return 0


def _execution_mode(arguments: argparse.Namespace) -> str:
    if arguments.mode == "worker":
        if (
            arguments.env is None
            or arguments.output is not None
            or arguments.worker_output is None
            or arguments.worker_index is None
            or arguments.run_id is None
            or arguments.checkpoint is not None
            or arguments.restore_output is not None
        ):
            raise ValueError(
                "R3T worker mode requires only --mode=worker, --env, "
                "--worker-output, --worker-index, and --run-id."
            )
        return "worker"
    if arguments.mode == "restore":
        if (
            arguments.env is not None
            or arguments.output is not None
            or arguments.worker_output is not None
            or arguments.worker_index is not None
            or arguments.run_id is None
            or arguments.checkpoint is None
            or arguments.restore_output is None
        ):
            raise ValueError(
                "R3T restore mode requires only --mode=restore, --checkpoint, "
                "--restore-output, and --run-id."
            )
        return "restore"
    if arguments.mode is not None:
        raise ValueError("Unknown R3T execution mode.")
    if (
        arguments.env is None
        or arguments.output is None
        or arguments.worker_output is not None
        or arguments.worker_index is not None
        or arguments.run_id is not None
        or arguments.checkpoint is not None
        or arguments.restore_output is not None
    ):
        raise ValueError("R3T parent mode requires only --env and --output.")
    return "parent"


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the contract-bound R3T Basic BDQ five-seed lineage campaign."
    )
    parser.add_argument("--env", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mode", choices=["worker", "restore"], help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--run-id", help=argparse.SUPPRESS)
    parser.add_argument("--checkpoint", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--restore-output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(arguments)


def main() -> int:
    arguments = parse_arguments()
    mode = _execution_mode(arguments)
    contract = _read_json(CONTRACT_PATH)
    result_schema = validate_contract(contract)
    if mode == "worker":
        return _run_worker(arguments, contract, result_schema)
    if mode == "restore":
        return _run_restore(arguments, contract, result_schema)
    return _run_parent(arguments, contract, result_schema)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LLAPIContractError,
        ValueError,
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"error={error}", file=sys.stderr)
        raise SystemExit(2) from error
