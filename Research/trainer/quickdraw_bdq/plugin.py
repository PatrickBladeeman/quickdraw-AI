"""Frozen ML-Agents trainer-plugin seam for later R3 integration."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version


@dataclass(frozen=True)
class TrainerPluginBoundary:
    entry_point_group: str = "mlagents.trainer_type"
    entry_point_name: str = "quickdraw_bdq"
    trainer_type: str = "quickdraw_bdq"
    future_registration_callable: str = (
        "quickdraw_bdq.plugin:register_trainer_types"
    )
    registration_status: str = "foundation_only_not_registered"


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
