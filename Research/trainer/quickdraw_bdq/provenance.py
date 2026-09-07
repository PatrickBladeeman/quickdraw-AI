"""Dependency-light raw-file hashing and registered CPU runtime identity.

Structured JSON, observation, network, checkpoint-state, and replay-sample
hashing protocols retain their own owners and serialization rules.
"""

from __future__ import annotations

import hashlib
import sys
from importlib.metadata import version
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_contract() -> dict[str, str]:
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }
