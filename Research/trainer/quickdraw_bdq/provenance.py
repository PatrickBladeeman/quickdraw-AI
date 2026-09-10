"""Dependency-light raw-file hashing and registered CPU runtime identity.

Structured JSON, observation, network, checkpoint-state, and replay-sample
hashing protocols retain their own owners and serialization rules.
"""

from __future__ import annotations

import ctypes
import hashlib
import sys
from ctypes import wintypes
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_file_manifest(root: Path) -> Dict[str, Any]:
    """Return a path-independent, content-addressed manifest for one directory."""

    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise FileNotFoundError(resolved_root)
    files = []
    total_bytes = 0
    for path in sorted(
        (candidate for candidate in resolved_root.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(resolved_root).as_posix(),
    ):
        size = path.stat().st_size
        total_bytes += size
        files.append(
            {
                "path": path.relative_to(resolved_root).as_posix(),
                "bytes": size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }


def process_creation_marker(pid: int) -> Dict[str, Any]:
    """Return an OS-owned process creation marker suitable for PID reuse checks."""

    if type(pid) is not int or pid <= 0:
        raise ValueError("Process PID must be a positive integer.")
    if sys.platform != "win32":
        raise RuntimeError("R3S process creation markers require Windows.")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ProcessLookupError(pid)
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
        value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        return {
            "kind": "windows_filetime_100ns_since_1601",
            "value": value,
        }
    finally:
        kernel32.CloseHandle(handle)


def runtime_contract() -> dict[str, str]:
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "mlagents_envs": version("mlagents-envs"),
        "numpy": version("numpy"),
        "torch": version("torch"),
        "device": "cpu",
    }
