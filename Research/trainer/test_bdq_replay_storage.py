from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pytest
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from quickdraw_bdq import (  # noqa: E402
    REPLAY_MAX_ACCOUNTED_BYTES,
    LLAPIContractError,
    ReplayBatch,
    ReplayBuffer,
    ReplayTransition,
)
from validate_bdq_replay_storage_regression import (  # noqa: E402
    validate_contract as validate_storage_contract,
    validate_regression_evidence,
)


CONTRACT_PATH = HERE / "bdq-replay-storage-contract-v1.json"
SCHEMA_PATH = (
    ROOT / "Research" / "schemas" / "bdq-replay-storage-contract.schema.json"
)
R3M_CONTRACT_PATH = HERE / "bdq-fourth-update-contract-v1.json"
BASIC_CONTRACT_PATH = ROOT / "Research" / "basic" / "basic-contract-v1.json"
OBSERVATION_SHAPE = (84, 84, 4)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def frame(index: int) -> np.ndarray:
    valid_float32_bits = np.asarray(
        [
            0x00000000,
            0x80000000,
            0x3EAAAAAB,
            0x3F000001,
            0x3F7FFFFF,
        ],
        dtype=np.uint32,
    )
    positions = np.arange(84 * 84, dtype=np.uint32)
    selected = valid_float32_bits[(positions + index) % len(valid_float32_bits)]
    result = selected.view(np.float32).reshape((84, 84)).copy()
    result[0, 0] = np.float32(index / 1000.0)
    return result


def observation(first_frame: int) -> np.ndarray:
    return np.stack(
        [frame(first_frame + offset) for offset in range(4)],
        axis=2,
    )


def masks(index: int) -> tuple[np.ndarray, np.ndarray]:
    movement = np.zeros(3, dtype=np.bool_)
    combat = np.zeros(2, dtype=np.bool_)
    movement[(index + 1) % 3] = True
    combat[(index + 1) % 2] = True
    return movement, combat


def transition(index: int) -> ReplayTransition:
    action_masks = masks(index)
    action = np.asarray([index % 3, index % 2], dtype=np.int64)
    return ReplayTransition(
        observation=observation(index),
        action=action,
        reward=float(index) + 0.25,
        next_observation=observation(index + 1),
        action_masks=action_masks,
        next_action_masks=masks(index + 2),
        terminated=index in {1, 6},
        truncated=index == 3,
    )


def constant_transition(value: float, reward: float) -> ReplayTransition:
    value_array = np.full(OBSERVATION_SHAPE, value, dtype=np.float32)
    return ReplayTransition(
        observation=value_array,
        action=np.asarray([0, 0], dtype=np.int64),
        reward=reward,
        next_observation=value_array,
        action_masks=(
            np.zeros(3, dtype=np.bool_),
            np.zeros(2, dtype=np.bool_),
        ),
        next_action_masks=(
            np.zeros(3, dtype=np.bool_),
            np.zeros(2, dtype=np.bool_),
        ),
        terminated=False,
        truncated=False,
    )


class LegacyReplayOracle:
    """R3A's retained-transition implementation, kept only as a test oracle."""

    def __init__(self, capacity: int, seed: int) -> None:
        self.capacity = capacity
        self._storage: list[ReplayTransition | None] = [None] * capacity
        self._next_index = 0
        self._size = 0
        self._random = np.random.default_rng(seed)

    def add(self, item: ReplayTransition) -> None:
        self._storage[self._next_index] = item
        self._next_index = (self._next_index + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size: int) -> ReplayBatch:
        indices = self._random.choice(
            self._size,
            size=batch_size,
            replace=False,
        )
        selected = [self._storage[int(index)] for index in indices]
        assert all(item is not None for item in selected)
        concrete = [item for item in selected if item is not None]
        return ReplayBatch(
            observations=np.stack([item.observation for item in concrete]),
            actions=np.stack([item.action for item in concrete]),
            rewards=np.asarray([item.reward for item in concrete], dtype=np.float32),
            next_observations=np.stack(
                [item.next_observation for item in concrete]
            ),
            action_masks=tuple(
                np.stack([item.action_masks[branch] for item in concrete])
                for branch in range(2)
            ),
            next_action_masks=tuple(
                np.stack([item.next_action_masks[branch] for item in concrete])
                for branch in range(2)
            ),
            terminated=np.asarray(
                [item.terminated for item in concrete],
                dtype=np.bool_,
            ),
            truncated=np.asarray(
                [item.truncated for item in concrete],
                dtype=np.bool_,
            ),
            indices=np.asarray(indices, dtype=np.int64),
        )


def assert_array_bit_equal(actual: np.ndarray, expected: np.ndarray) -> None:
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert actual.flags.c_contiguous == expected.flags.c_contiguous
    assert actual.tobytes(order="C") == expected.tobytes(order="C")


def assert_batches_bit_equal(actual: ReplayBatch, expected: ReplayBatch) -> None:
    for name in (
        "indices",
        "observations",
        "actions",
        "rewards",
        "next_observations",
        "terminated",
        "truncated",
    ):
        assert_array_bit_equal(getattr(actual, name), getattr(expected, name))
    for actual_masks, expected_masks in (
        (actual.action_masks, expected.action_masks),
        (actual.next_action_masks, expected.next_action_masks),
    ):
        assert len(actual_masks) == len(expected_masks) == 2
        for actual_mask, expected_mask in zip(actual_masks, expected_masks):
            assert_array_bit_equal(actual_mask, expected_mask)


def test_contract_schema_binding_and_capacity_accounting_are_exact() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    r3m_contract = json.loads(R3M_CONTRACT_PATH.read_text(encoding="utf-8"))
    basic_contract = json.loads(BASIC_CONTRACT_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(contract)
    binding = contract["base_fourth_update_contract"]
    assert binding["sha256"] == sha256_file(R3M_CONTRACT_PATH)
    assert binding["schema_version"] == r3m_contract["schema_version"]

    budget = contract["memory_budget"]
    assert REPLAY_MAX_ACCOUNTED_BYTES == budget["max_accounted_storage_bytes"]
    assert ReplayBuffer.projected_accounted_bytes(100_000, 0) == budget[
        "metadata_accounted_bytes_at_capacity"
    ]
    assert ReplayBuffer.projected_accounted_bytes(100_000, 81) == budget[
        "registered_basic_projection_accounted_bytes"
    ]
    assert ReplayBuffer.projected_accounted_bytes(100_000, 100_004) == budget[
        "conservative_sequential_projection_accounted_bytes"
    ]
    assert budget["conservative_sequential_projection_accounted_bytes"] < (
        REPLAY_MAX_ACCOUNTED_BYTES
    )
    slot_count = (
        basic_contract["geometry"]["maximum_slot"]
        - basic_contract["geometry"]["minimum_slot"]
        + 1
    )
    assert slot_count**2 == budget[
        "registered_basic_distinct_render_states_upper_bound"
    ]
    assert contract["legacy_storage"][
        "capacity_observation_payload_bytes"
    ] == 22_579_200_000


def test_compact_batches_are_bit_exact_to_the_legacy_oracle_after_wrap() -> None:
    compact = ReplayBuffer(capacity=5, seed=62001)
    legacy = LegacyReplayOracle(capacity=5, seed=62001)
    for index in range(7):
        item = transition(index)
        compact.add(item)
        legacy.add(item)

    first_compact = compact.sample(4)
    first_legacy = legacy.sample(4)
    assert first_compact.indices.tolist() == [2, 1, 4, 0]
    assert_batches_bit_equal(first_compact, first_legacy)

    second_compact = compact.sample(4)
    second_legacy = legacy.sample(4)
    assert second_compact.indices.tolist() == [1, 3, 4, 0]
    assert_batches_bit_equal(second_compact, second_legacy)

    torch_batch = first_compact.to_torch()
    assert tuple(torch_batch.observations.shape) == (4, 84, 84, 4)
    assert str(torch_batch.observations.dtype) == "torch.float32"
    assert str(torch_batch.actions.dtype) == "torch.int64"


def test_frame_interning_reclaims_orphans_and_owns_exact_input_bytes() -> None:
    replay = ReplayBuffer(capacity=2, seed=1)
    first = transition(0)
    first_expected = first.observation.tobytes(order="C")
    replay.add(first)
    assert replay.storage_metrics.unique_frame_count == 5
    assert replay.storage_metrics.frame_reference_count == 8

    first.observation.setflags(write=True)
    first.observation.fill(np.float32(0.75))
    sampled = replay.sample(1)
    assert sampled.observations.tobytes(order="C") == first_expected

    replay.add(transition(1))
    assert replay.storage_metrics.unique_frame_count == 6
    assert replay.storage_metrics.frame_reference_count == 16

    replay.add(transition(10))
    assert len(replay) == 2
    assert replay.storage_metrics.unique_frame_count == 10
    assert replay.storage_metrics.frame_reference_count == 16


def test_budget_rejection_is_atomic_and_actionable() -> None:
    one_frame_budget = ReplayBuffer.projected_accounted_bytes(2, 1)
    replay = ReplayBuffer(
        capacity=2,
        seed=2,
        max_accounted_bytes=one_frame_budget,
    )
    replay.add(constant_transition(0.25, 1.0))
    before = replay.storage_metrics

    with pytest.raises(MemoryError, match="storage budget exceeded"):
        replay.add(transition(20))

    assert replay.storage_metrics == before
    replay.add(constant_transition(0.25, 2.0))
    assert len(replay) == 2
    assert replay.storage_metrics.unique_frame_count == 1
    assert sorted(replay.sample(2).rewards.tolist()) == [1.0, 2.0]


def test_full_ring_reclaims_before_applying_the_steady_state_budget() -> None:
    one_frame_budget = ReplayBuffer.projected_accounted_bytes(1, 1)
    replay = ReplayBuffer(
        capacity=1,
        seed=3,
        max_accounted_bytes=one_frame_budget,
    )
    replay.add(constant_transition(0.25, 1.0))
    replay.add(constant_transition(0.5, 2.0))

    assert len(replay) == 1
    assert replay.storage_metrics.unique_frame_count == 1
    assert replay.storage_metrics.accounted_storage_bytes == one_frame_budget
    assert replay.sample(1).rewards.tolist() == [2.0]


@pytest.mark.parametrize(
    ("capacity", "seed", "budget", "message"),
    [
        (True, 1, REPLAY_MAX_ACCOUNTED_BYTES, "capacity"),
        (1, True, REPLAY_MAX_ACCOUNTED_BYTES, "seed"),
        (1, 1, True, "budget"),
        (1, 1, 1, "metadata"),
    ],
)
def test_storage_configuration_rejects_invalid_values(
    capacity: object,
    seed: object,
    budget: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ReplayBuffer(  # type: ignore[arg-type]
            capacity,
            seed,
            max_accounted_bytes=budget,
        )


def test_registered_production_sample_index_hashes_are_frozen() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = contract["equivalence"]["production_sample_index_sha256"]
    generator = np.random.default_rng(51001)
    draws: list[list[int]] = []
    observed = []
    for item in expected:
        indices = generator.choice(
            item["replay_size"],
            size=64,
            replace=False,
        ).tolist()
        draws.append(indices)
        observed.append(
            {
                "replay_size": item["replay_size"],
                "sha256": canonical_json_sha256(indices),
            }
        )
    assert observed == expected
    assert canonical_json_sha256(draws) == contract["equivalence"][
        "combined_production_sample_indices_sha256"
    ]


def test_r3m_hash_baseline_is_complete_without_ignored_artifacts() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    regression = contract["r3m_regression"]
    assert regression["update_decisions"] == [10_000, 10_004, 10_008, 10_012]
    assert len(regression["update_losses"]) == 4
    assert len(regression["update_mean_absolute_td_errors"]) == 4
    assert len(regression["online_hashes_after_updates"]) == 4
    assert regression["optimizer_update_count"] == 4
    assert regression["target_sync_count"] == 0
    assert regression["transition_count"] == 10_012
    assert regression["conservative_accounted_storage_upper_bound_bytes"] < (
        REPLAY_MAX_ACCOUNTED_BYTES
    )


def test_regression_validator_accepts_only_the_frozen_r3m_evidence() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result_schema = validate_storage_contract(contract)
    assert result_schema["$id"].endswith(
        "bdq-fourth-update-smoke-result.schema.json"
    )

    evidence = {
        key: value
        for key, value in contract["r3m_regression"].items()
        if key not in {"fresh_process_count", "comparison"}
    }
    validate_regression_evidence(evidence, contract)

    drifted = dict(evidence)
    drifted["transition_count"] += 1
    with pytest.raises(LLAPIContractError, match="transition_count"):
        validate_regression_evidence(drifted, contract)
