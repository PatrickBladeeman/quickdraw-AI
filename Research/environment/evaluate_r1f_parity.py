from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import onnxruntime as ort
from jsonschema import Draft202012Validator, FormatChecker

from r1f_fixed_policy import parameter_specification, sha256_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "Research" / "schemas" / "backend-parity-result.schema.json"
RUN_MANIFEST_SCHEMA_PATH = REPO_ROOT / "Research" / "schemas" / "run-manifest.schema.json"
POLICY_PATH = Path(__file__).with_name("r1f_fixed_policy.py")
PREPARER_PATH = Path(__file__).with_name("prepare_r1f_policy.py")
RUNNER_PATH = REPO_ROOT / "Research" / "smoke" / "run_smoke.py"
CPU_ADDITIONS_LOCK_PATH = Path(__file__).with_name("requirements-r1f-parity-lock.txt")
SUPPORT_LOCK_PATH = Path(__file__).with_name(
    "requirements-rocm-py311-support-lock.txt"
)
DEFAULT_PROCEDURE_PATH = Path(__file__).with_name("amd-parity-procedure-v1.json")
DEFAULT_CONTRACT_PATH = Path(__file__).with_name("backend-parity-contract-v1.json")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def path_hash(path: Path) -> Dict[str, str]:
    return {"path": repo_relative(path), "sha256": sha256_file(path)}


def measured_transitions(trace: Mapping[str, Any], episode_id: int) -> List[Dict[str, Any]]:
    matching = [
        episode for episode in trace["episodes"] if int(episode["episode_id"]) == episode_id
    ]
    if len(matching) != 1:
        raise RuntimeError(f"Trace has {len(matching)} copies of episode {episode_id}.")
    return matching[0]["transitions"]


def transition_without_logits(transition: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in transition.items()
        if key not in {"episode_id", "policy_logits"}
    }


def exact_transition_sequence(transitions: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [transition_without_logits(transition) for transition in transitions]


def logits_array(transitions: Sequence[Mapping[str, Any]]) -> np.ndarray:
    rows: List[List[float]] = []
    for transition in transitions:
        logits = transition.get("policy_logits")
        if not isinstance(logits, list) or [len(branch) for branch in logits] != [3, 2]:
            raise RuntimeError("A parity transition has missing or malformed policy logits.")
        rows.append([float(value) for branch in logits for value in branch])
    result = np.asarray(rows, dtype=np.float32)
    if result.ndim != 2 or result.shape[1] != 5:
        raise RuntimeError(f"Policy logits have shape {result.shape}, expected (N, 5).")
    return result


def masked_actions(
    logits: np.ndarray,
    transitions: Sequence[Mapping[str, Any]],
) -> List[List[int]]:
    actions: List[List[int]] = []
    for row, transition in zip(logits, transitions):
        masks = transition["action_masks"]
        movement = row[:3].copy()
        submit = row[3:].copy()
        movement[np.asarray(masks[0], dtype=bool)] = -np.inf
        submit[np.asarray(masks[1], dtype=bool)] = -np.inf
        actions.append([int(np.argmax(movement)), int(np.argmax(submit))])
    return actions


def maximum_absolute_difference(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise RuntimeError(f"Logit shapes differ: {left.shape} versus {right.shape}.")
    if not bool(np.isfinite(left).all()) or not bool(np.isfinite(right).all()):
        return math.inf
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def validate_run(
    run_directory: Path,
    expected_backend: str,
    contract: Mapping[str, Any],
    contract_sha256: str,
    checkpoint_path: Path,
    onnx_path: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    trace_path = run_directory / "trace.json"
    manifest_path = run_directory / "run-manifest.json"
    trace = load_json(trace_path)
    manifest = load_json(manifest_path)
    if trace.get("trace_format") != contract["trace_format"]:
        raise RuntimeError(f"{trace_path} has the wrong trace format.")
    if trace.get("base_seed") != contract["scenario_base_seed"]:
        raise RuntimeError(f"{trace_path} has the wrong registered base seed.")
    if manifest["backend"]["selected"] != expected_backend:
        raise RuntimeError(f"{manifest_path} has the wrong selected backend.")
    if manifest["performance"]["decision_count"] != contract["measurement"]["decision_count"]:
        raise RuntimeError(f"{manifest_path} has the wrong decision count.")
    if manifest["hashes"]["configuration"] != contract_sha256:
        raise RuntimeError(f"{manifest_path} has the wrong parity-contract hash.")
    if manifest["hashes"]["policy"] != sha256_file(checkpoint_path):
        raise RuntimeError(f"{manifest_path} has the wrong checkpoint hash.")
    if manifest["hashes"]["model"] != sha256_file(onnx_path):
        raise RuntimeError(f"{manifest_path} has the wrong ONNX hash.")
    if manifest["seeds"]["policy_initialization"] != contract["policy"]["seed"]:
        raise RuntimeError(f"{manifest_path} has the wrong policy seed.")
    policy = trace.get("policy")
    if not isinstance(policy, dict):
        raise RuntimeError(f"{trace_path} is missing fixed-policy metadata.")
    if policy.get("backend") != expected_backend:
        raise RuntimeError(f"{trace_path} has the wrong policy backend.")
    if manifest["software"]["python"]["packages"]["torch"] != policy.get("torch_version"):
        raise RuntimeError(f"{manifest_path} and {trace_path} disagree on PyTorch.")
    if policy.get("checkpoint_sha256") != sha256_file(checkpoint_path):
        raise RuntimeError(f"{trace_path} has the wrong checkpoint hash.")
    if policy.get("onnx_sha256") != sha256_file(onnx_path):
        raise RuntimeError(f"{trace_path} has the wrong ONNX hash.")
    if policy.get("parameters") != parameter_specification():
        raise RuntimeError(f"{trace_path} has the wrong parameter specification.")
    if expected_backend == "rocm" and policy.get("device_name") != contract["policy"]["expected_rocm_device"]:
        raise RuntimeError(f"{trace_path} did not select the registered ROCm adapter.")
    return trace, manifest


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the frozen R1F parity gate.")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--onnx", required=True, type=Path)
    parser.add_argument("--cpu-run", required=True, type=Path, action="append")
    parser.add_argument("--rocm-run", required=True, type=Path, action="append")
    parser.add_argument("--registered-trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--procedure", type=Path, default=DEFAULT_PROCEDURE_PATH)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument(
        "--background-load-note",
        default="No intentional foreground workload; ordinary Windows background services remained enabled.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if len(arguments.cpu_run) != 2 or len(arguments.rocm_run) != 2:
        raise ValueError("R1F requires exactly two CPU and two ROCm runs.")

    checkpoint_path = arguments.checkpoint.resolve()
    onnx_path = arguments.onnx.resolve()
    procedure_path = arguments.procedure.resolve()
    contract_path = arguments.contract.resolve()
    registered_trace_path = arguments.registered_trace.resolve()
    output_path = arguments.output.resolve()
    procedure = load_json(procedure_path)
    contract = load_json(contract_path)
    tolerance = float(procedure["correctness_gates"]["float32_max_abs_tolerance"])
    measured_episode_id = int(contract["measurement"]["episode_id"])
    warmup_episode_id = int(contract["measurement"]["warmup_episode_id"])

    run_order: List[Tuple[str, Path]] = [
        ("cpu", arguments.cpu_run[0].resolve()),
        ("rocm", arguments.rocm_run[0].resolve()),
        ("cpu", arguments.cpu_run[1].resolve()),
        ("rocm", arguments.rocm_run[1].resolve()),
    ]
    traces: Dict[str, List[Dict[str, Any]]] = {"cpu": [], "rocm": []}
    manifests: Dict[str, List[Dict[str, Any]]] = {"cpu": [], "rocm": []}
    for backend, run_directory in run_order:
        trace, manifest = validate_run(
            run_directory,
            backend,
            contract,
            sha256_file(contract_path),
            checkpoint_path,
            onnx_path,
        )
        traces[backend].append(trace)
        manifests[backend].append(manifest)

    measured = {
        backend: [
            measured_transitions(trace, measured_episode_id)
            for trace in traces[backend]
        ]
        for backend in ("cpu", "rocm")
    }
    warmup = {
        backend: [
            measured_transitions(trace, warmup_episode_id)
            for trace in traces[backend]
        ]
        for backend in ("cpu", "rocm")
    }
    expected_count = int(contract["measurement"]["decision_count"])
    expected_warmup = int(contract["measurement"]["warmup_decision_count"])
    counts_passed = all(
        len(sequence) == expected_count
        for backend in measured.values()
        for sequence in backend
    ) and all(
        len(sequence) == expected_warmup
        for backend in warmup.values()
        for sequence in backend
    )

    reference_trace = load_json(registered_trace_path)
    reference_transitions = reference_trace["episodes"][0]["transitions"]
    reference_core = exact_transition_sequence(reference_transitions)
    all_measured_core = [
        exact_transition_sequence(sequence)
        for backend in ("cpu", "rocm")
        for sequence in measured[backend]
    ]
    exact_measured_trace = all(sequence == all_measured_core[0] for sequence in all_measured_core)
    registered_trace_match = all(sequence == reference_core for sequence in all_measured_core)
    all_warmup_core = [
        exact_transition_sequence(sequence)
        for backend in ("cpu", "rocm")
        for sequence in warmup[backend]
    ]
    exact_warmup_trace = all(sequence == all_warmup_core[0] for sequence in all_warmup_core)

    logits = {
        backend: [logits_array(sequence) for sequence in measured[backend]]
        for backend in ("cpu", "rocm")
    }
    finite_logits = all(
        bool(np.isfinite(values).all())
        for backend in logits.values()
        for values in backend
    )
    cpu_repeat_max_abs = maximum_absolute_difference(logits["cpu"][0], logits["cpu"][1])
    rocm_repeat_max_abs = maximum_absolute_difference(logits["rocm"][0], logits["rocm"][1])
    cpu_rocm_max_abs = max(
        maximum_absolute_difference(logits["cpu"][0], candidate)
        for candidate in logits["rocm"]
    )

    observations = np.asarray(
        [transition["observation"] for transition in measured["cpu"][0]],
        dtype=np.float32,
    )
    session = ort.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )
    movement_logits, submit_logits = session.run(
        ["movement_logits", "submit_logits"], {"observations": observations}
    )
    onnx_logits = np.concatenate((movement_logits, submit_logits), axis=1).astype(
        np.float32, copy=False
    )
    onnx_cpu_max_abs = maximum_absolute_difference(onnx_logits, logits["cpu"][0])

    expected_actions = [transition["action"] for transition in measured["cpu"][0]]
    recorded_actions_match = all(
        [transition["action"] for transition in sequence] == expected_actions
        for backend in ("cpu", "rocm")
        for sequence in measured[backend]
    )
    pytorch_argmax_match = all(
        masked_actions(values, sequence) == expected_actions
        for backend in ("cpu", "rocm")
        for values, sequence in zip(logits[backend], measured[backend])
    )
    onnx_actions_match = masked_actions(onnx_logits, measured["cpu"][0]) == expected_actions

    state_hashes = {
        trace["policy"]["state_dict_sha256"]
        for backend in traces.values()
        for trace in backend
    }
    checkpoint_reload_exact = len(state_hashes) == 1
    exact_outcome_fields = all(
        [
            (
                transition["reward"],
                transition["terminal"],
                transition["interrupted"],
            )
            for transition in sequence
        ]
        == [
            (
                transition["reward"],
                transition["terminal"],
                transition["interrupted"],
            )
            for transition in measured["cpu"][0]
        ]
        for backend in ("cpu", "rocm")
        for sequence in measured[backend]
    )
    seeded_returns = [
        round(sum(float(transition["reward"]) for transition in sequence), 7)
        for backend in ("cpu", "rocm")
        for sequence in measured[backend]
    ]
    seeded_return_exact = len(set(seeded_returns)) == 1

    correctness_checks = {
        "decision_counts": counts_passed,
        "registered_observation_trace": registered_trace_match,
        "cross_backend_trace": exact_measured_trace,
        "warmup_trace": exact_warmup_trace,
        "action_masks_and_actions": recorded_actions_match,
        "pytorch_masked_argmax": pytorch_argmax_match,
        "terminal_and_interrupted": exact_outcome_fields,
        "seeded_return": seeded_return_exact,
        "checkpoint_reload": checkpoint_reload_exact,
        "finite_logits": finite_logits,
        "cpu_repeat_logits": cpu_repeat_max_abs <= tolerance,
        "rocm_repeat_logits": rocm_repeat_max_abs <= tolerance,
        "cpu_rocm_logits": cpu_rocm_max_abs <= tolerance,
        "onnx_cpu_logits": onnx_cpu_max_abs <= tolerance,
        "onnx_actions": onnx_actions_match,
    }
    correctness_passed = all(correctness_checks.values())

    rates = {
        backend: [float(manifest["performance"]["decisions_per_second"]) for manifest in manifests[backend]]
        for backend in ("cpu", "rocm")
    }
    medians = {backend: statistics.median(values) for backend, values in rates.items()}
    throughput_passed = medians["rocm"] > medians["cpu"]
    accepted = correctness_passed and throughput_passed
    status = "accepted" if accepted else "rejected"
    selected_backend = "rocm" if accepted else "cpu"

    result: Dict[str, Any] = {
        "schema_version": "quickdraw.amd-backend-parity-result.v1",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "procedure": {"path": repo_relative(procedure_path), "sha256": sha256_file(procedure_path)},
        "contract": {"path": repo_relative(contract_path), "sha256": sha256_file(contract_path)},
        "implementation": {
            "fixed_policy": path_hash(POLICY_PATH),
            "fixture_preparer": path_hash(PREPARER_PATH),
            "parity_evaluator": path_hash(Path(__file__)),
            "smoke_runner": path_hash(RUNNER_PATH),
            "result_schema": path_hash(SCHEMA_PATH),
            "run_manifest_schema": path_hash(RUN_MANIFEST_SCHEMA_PATH),
            "cpu_additions_lock": path_hash(CPU_ADDITIONS_LOCK_PATH),
            "python_support_lock": path_hash(SUPPORT_LOCK_PATH),
        },
        "fixture": {
            "policy_seed": int(contract["policy"]["seed"]),
            "checkpoint_path": repo_relative(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "state_dict_sha256": next(iter(state_hashes)),
            "onnx_path": repo_relative(onnx_path),
            "onnx_sha256": sha256_file(onnx_path),
            "parameters": parameter_specification(),
            "training_performed": False,
        },
        "runs": {
            "ordering": [
                {"backend": backend, "path": repo_relative(path)}
                for backend, path in run_order
            ],
            "background_load_note": arguments.background_load_note,
            "cpu_decisions_per_second": rates["cpu"],
            "rocm_decisions_per_second": rates["rocm"],
        },
        "correctness": {
            "passed": correctness_passed,
            "checks": correctness_checks,
            "float32_max_abs_tolerance": tolerance,
            "maximum_absolute_differences": {
                "cpu_repeat": cpu_repeat_max_abs,
                "rocm_repeat": rocm_repeat_max_abs,
                "cpu_rocm": cpu_rocm_max_abs,
                "onnx_cpu": onnx_cpu_max_abs,
            },
            "seeded_returns": seeded_returns,
            "registered_trace": {
                "path": repo_relative(registered_trace_path),
                "sha256": sha256_file(registered_trace_path),
            },
        },
        "throughput": {
            "passed": throughput_passed,
            "decision_count_per_run": expected_count,
            "warmup_decisions": expected_warmup,
            "cpu_median_decisions_per_second": medians["cpu"],
            "rocm_median_decisions_per_second": medians["rocm"],
            "rocm_to_cpu_ratio": medians["rocm"] / medians["cpu"],
            "rule": "ROCm median decisions per second must be strictly greater than CPU median after every correctness gate passes.",
        },
        "decision": {
            "candidate_backend": "rocm",
            "selected_backend": selected_backend,
            "backend_accepted": accepted,
            "cpu_reference_retained": not accepted,
            "no_partial_acceptance": True,
            "reason": (
                "ROCm passed every correctness gate and had strictly higher median throughput."
                if accepted
                else (
                    "ROCm failed one or more correctness gates; CPU remains selected."
                    if not correctness_passed
                    else "ROCm did not exceed CPU median throughput; CPU remains selected."
                )
            ),
        },
        "qualifications": [
            "The runs use batch-size-one synchronous inference in the Research_Smoke LLAPI fixture.",
            "This result does not establish training throughput or larger-model performance.",
            "No trainer, replay buffer, learned weights, combat system, or LLM runtime was exercised.",
        ],
    }

    schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"result={output_path}")
    print(f"status={status}")
    print(f"correctness={'pass' if correctness_passed else 'fail'}")
    print(f"throughput={'pass' if throughput_passed else 'fail'}")
    print(f"selected_backend={selected_backend}")
    return 0 if correctness_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
