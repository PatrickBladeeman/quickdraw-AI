from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from run_basic_baseline import (
    RandomVisualPolicy,
    ScriptedVisualPolicy,
    create_policy,
    sample_target_slot,
    semantic_action,
    validate_reset_stack,
)


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def test_target_sampler_is_stable_and_bounded() -> None:
    first = [sample_target_slot(31001, index) for index in range(12)]
    second = [sample_target_slot(31001, index) for index in range(12)]
    assert first == second
    assert first == [2, -4, -2, -4, -2, 1, 0, 0, 2, 2, -2, -4]
    assert all(-4 <= slot <= 4 for slot in first)


def test_scripted_policy_uses_latest_frame_direction_and_center() -> None:
    policy = ScriptedVisualPolicy(41002)
    masks = [[False, False, False], [False, False]]

    left = np.zeros((84, 84, 4), dtype=np.float32)
    left[40:44, 20:23, -1] = 1.0
    assert policy.act(left, masks) == (1, 0)

    right = np.zeros((84, 84, 4), dtype=np.float32)
    right[40:44, 60:63, -1] = 1.0
    assert policy.act(right, masks) == (2, 0)

    centered = np.zeros((84, 84, 4), dtype=np.float32)
    centered[40:44, 40:44, -1] = 1.0
    assert policy.act(centered, masks) == (0, 1)


def test_scripted_policy_fails_closed_without_visual_target() -> None:
    policy = ScriptedVisualPolicy(41002)
    observation = np.zeros((84, 84, 4), dtype=np.float32)
    try:
        policy.act(observation, [[False] * 3, [False] * 2])
    except RuntimeError as error:
        assert "could not see the target" in str(error)
    else:
        raise AssertionError("Missing target did not fail closed.")


def test_random_policy_is_seeded_and_respects_masks() -> None:
    first = RandomVisualPolicy(41001)
    second = RandomVisualPolicy(41001)
    observation = np.zeros((84, 84, 4), dtype=np.float32)
    masks = [[False, True, False], [False, False]]
    first_actions = [first.act(observation, masks) for _ in range(20)]
    second_actions = [second.act(observation, masks) for _ in range(20)]
    assert first_actions == second_actions
    assert all(action[0] != 1 for action in first_actions)


def test_both_baselines_share_the_action_interface_and_episode_schema() -> None:
    contract = json.loads((HERE / "basic-contract-v1.json").read_text("utf-8"))
    assert isinstance(create_policy("random", contract), RandomVisualPolicy)
    assert isinstance(create_policy("scripted", contract), ScriptedVisualPolicy)
    assert semantic_action((2, 1)) == {
        "movement": "Right",
        "combat": "Shoot",
        "utility": "Idle",
    }

    schema = json.loads(
        (
            REPO_ROOT
            / "Research"
            / "schemas"
            / "basic-baseline-trace.schema.json"
        ).read_text("utf-8")
    )
    Draft202012Validator.check_schema(schema)
    episode_schema = schema["$defs"]["episode"]
    assert episode_schema["properties"]["policy_id"] == {
        "type": "string",
        "minLength": 1,
    }


def test_runtime_reset_stack_validation_rejects_a_stale_channel() -> None:
    observation = np.ones((84, 84, 4), dtype=np.float32)
    assert len(validate_reset_stack(observation)) == 64
    observation[0, 0, 2] = 0.0
    try:
        validate_reset_stack(observation)
    except RuntimeError as error:
        assert "stale frame" in str(error)
    else:
        raise AssertionError("A stale reset channel was accepted.")
