"""Process gate for Assetto Corsa shared-memory access.

The Windows shared-memory pages are owned by the running simulator. Opening
them before the race process exists can interfere with Assetto Corsa startup on
some systems, so the backend checks the process first and only then touches
the mmap pages.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, Iterable, Tuple


DEFAULT_ASSETTO_PROCESS_NAMES: Tuple[str, ...] = ("acs.exe", "AssettoCorsa.exe")
GATE_ENV = "ASSETTO_SHARED_MEMORY_WAIT_FOR_PROCESS"
PROCESS_NAMES_ENV = "ASSETTO_CORSA_PROCESS_NAMES"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _split_process_names(raw: str | None) -> Tuple[str, ...]:
    if not raw:
        return DEFAULT_ASSETTO_PROCESS_NAMES
    names = tuple(
        item.strip()
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    )
    return names or DEFAULT_ASSETTO_PROCESS_NAMES


def assetto_corsa_process_names() -> Tuple[str, ...]:
    return _split_process_names(os.getenv(PROCESS_NAMES_ENV))


def shared_memory_process_gate_enabled() -> bool:
    return _env_bool(GATE_ENV, os.name == "nt")


def assetto_corsa_process_running(process_names: Iterable[str] | None = None) -> bool:
    names = tuple(process_names or assetto_corsa_process_names())
    if os.name != "nt":
        return False

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for process_name in names:
        try:
            completed = subprocess.run(
                [
                    "tasklist",
                    "/FI",
                    f"IMAGENAME eq {process_name}",
                    "/NH",
                    "/FO",
                    "CSV",
                ],
                capture_output=True,
                text=True,
                check=False,
                creationflags=creationflags,
                timeout=2.0,
            )
        except Exception:
            continue

        output = (completed.stdout or "").lower()
        if completed.returncode == 0 and f'"{process_name.lower()}"' in output:
            return True
    return False


def shared_memory_gate_status() -> Dict[str, Any]:
    enabled = shared_memory_process_gate_enabled()
    process_names = assetto_corsa_process_names()
    process_running = assetto_corsa_process_running(process_names) if enabled else True
    allowed = (not enabled) or process_running
    reason = None if allowed else "waiting_for_assetto_corsa_process"
    return {
        "enabled": enabled,
        "allowed": allowed,
        "processRunning": process_running,
        "processNames": list(process_names),
        "reason": reason,
    }


def shared_memory_access_allowed() -> bool:
    return bool(shared_memory_gate_status()["allowed"])


__all__ = [
    "assetto_corsa_process_names",
    "assetto_corsa_process_running",
    "shared_memory_access_allowed",
    "shared_memory_gate_status",
    "shared_memory_process_gate_enabled",
]
