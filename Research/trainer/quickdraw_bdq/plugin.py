"""Versioned ML-Agents trainer-plugin boundaries for R3A and R3B."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from importlib.metadata import version
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class TrainerPluginBoundary:
    entry_point_group: str = "mlagents.trainer_type"
    entry_point_name: str = "quickdraw_bdq"
    trainer_type: str = "quickdraw_bdq"
    future_registration_callable: str = (
        "quickdraw_bdq.plugin:register_trainer_types"
    )
    registration_status: str = "foundation_only_not_registered"


@dataclass(frozen=True)
class RegisteredTrainerPluginBoundary:
    entry_point_group: str = "mlagents.trainer_type"
    entry_point_name: str = "quickdraw_bdq"
    entry_point_value: str = "quickdraw_bdq.plugin:register_trainer_types"
    trainer_type: str = "quickdraw_bdq"
    trainer_class: str = "quickdraw_bdq.trainer:QuickDrawBDQTrainer"
    settings_class: str = "quickdraw_bdq.settings:QuickDrawBDQSettings"
    distribution: str = "quickdraw-bdq-trainer"
    distribution_version: str = "0.2.0"
    registration_status: str = "registered_optimizer_smoke_rollout_unimplemented"


def validate_installed_plugin_api() -> TrainerPluginBoundary:
    """Fail if the installed ML-Agents package exposes a different plugin seam."""

    from mlagents.plugins import ML_AGENTS_TRAINER_TYPE

    boundary = TrainerPluginBoundary()
    if ML_AGENTS_TRAINER_TYPE != boundary.entry_point_group:
        raise RuntimeError(
            "Installed ML-Agents trainer entry-point group differs from the "
            "R3A contract."
        )
    if version("mlagents") != "1.1.0" or version("mlagents-envs") != "1.1.0":
        raise RuntimeError("R3A requires ML-Agents and ML-Agents Envs 1.1.0.")
    return boundary


def register_trainer_types() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return the exact trainer and settings mappings expected by ML-Agents 1.1."""

    from .settings import QuickDrawBDQSettings
    from .trainer import QuickDrawBDQTrainer

    return (
        {QuickDrawBDQTrainer.get_trainer_name(): QuickDrawBDQTrainer},
        {QuickDrawBDQTrainer.get_trainer_name(): QuickDrawBDQSettings},
    )


def validate_registered_plugin_api() -> RegisteredTrainerPluginBoundary:
    """Validate the installed editable distribution and its exact entry point."""

    validate_installed_plugin_api()
    boundary = RegisteredTrainerPluginBoundary()
    if version(boundary.distribution) != boundary.distribution_version:
        raise RuntimeError("Installed QuickDraw BDQ distribution version differs.")

    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        candidates = entry_points.select(group=boundary.entry_point_group)
    else:
        candidates = entry_points.get(boundary.entry_point_group, ())
    matches = [item for item in candidates if item.name == boundary.entry_point_name]
    if len(matches) != 1 or matches[0].value != boundary.entry_point_value:
        raise RuntimeError("Installed QuickDraw BDQ trainer entry point differs.")
    if matches[0].load() is not register_trainer_types:
        raise RuntimeError("Installed QuickDraw BDQ entry point loads the wrong callable.")
    return boundary
