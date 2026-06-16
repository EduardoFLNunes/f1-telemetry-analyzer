"""Startup gate for Assetto Corsa shared-memory access.

The Windows shared-memory pages are owned by the running simulator. Opening
them before Assetto Corsa creates them can interfere with simulator startup on
some systems. Python's Windows mmap API may create a named mapping when it does
not exist yet, so this module probes existing pages with OpenFileMappingW first.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, Iterable, Tuple

if os.name == "nt":
    import ctypes


DEFAULT_ASSETTO_PROCESS_NAMES: Tuple[str, ...] = ("acs.exe", "AssettoCorsa.exe")
DEFAULT_SHARED_MEMORY_PAGES: Tuple[str, ...] = ("acpmf_physics", "acpmf_graphics", "acpmf_static")
GATE_ENV = "ASSETTO_SHARED_MEMORY_WAIT_FOR_PROCESS"
PROCESS_NAMES_ENV = "ASSETTO_CORSA_PROCESS_NAMES"
SHARED_MEMORY_PAGES_ENV = "ASSETTO_CORSA_SHARED_MEMORY_PAGES"
FILE_MAP_READ = 0x0004


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


def assetto_corsa_shared_memory_pages() -> Tuple[str, ...]:
    raw = os.getenv(SHARED_MEMORY_PAGES_ENV)
    if not raw:
        return DEFAULT_SHARED_MEMORY_PAGES
    pages = tuple(
        item.strip()
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    )
    return pages or DEFAULT_SHARED_MEMORY_PAGES


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


def _page_aliases(page_name: str) -> Tuple[str, ...]:
    lowered = page_name.lower()
    if lowered.startswith("local\\") or lowered.startswith("global\\"):
        return (page_name,)
    return (page_name, f"Local\\{page_name}")


def _open_file_mapping_exists(page_name: str) -> bool:
    if os.name != "nt":
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.OpenFileMappingW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, page_name)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def shared_memory_pages_status(page_names: Iterable[str] | None = None) -> Dict[str, Any]:
    pages = tuple(page_names or assetto_corsa_shared_memory_pages())
    available: Dict[str, str] = {}
    missing = []

    for page_name in pages:
        matched_alias = next(
            (alias for alias in _page_aliases(page_name) if _open_file_mapping_exists(alias)),
            None,
        )
        if matched_alias:
            available[page_name] = matched_alias
        else:
            missing.append(page_name)

    return {
        "checked": True,
        "required": list(pages),
        "available": available,
        "missing": missing,
        "ready": not missing,
    }


def shared_memory_gate_status() -> Dict[str, Any]:
    enabled = shared_memory_process_gate_enabled()
    process_names = assetto_corsa_process_names()
    process_running = assetto_corsa_process_running(process_names) if enabled else True
    pages_status = {
        "checked": False,
        "required": list(assetto_corsa_shared_memory_pages()),
        "available": {},
        "missing": [],
        "ready": not enabled,
    }
    reason = None

    if enabled and not process_running:
        allowed = False
        reason = "waiting_for_assetto_corsa_process"
    elif enabled:
        pages_status = shared_memory_pages_status()
        allowed = bool(pages_status["ready"])
        if not allowed:
            reason = "waiting_for_assetto_corsa_shared_memory_pages"
    else:
        allowed = True

    return {
        "enabled": enabled,
        "allowed": allowed,
        "processRunning": process_running,
        "processNames": list(process_names),
        "pages": pages_status,
        "reason": reason,
    }


def shared_memory_access_allowed() -> bool:
    return bool(shared_memory_gate_status()["allowed"])


__all__ = [
    "assetto_corsa_process_names",
    "assetto_corsa_process_running",
    "assetto_corsa_shared_memory_pages",
    "shared_memory_access_allowed",
    "shared_memory_gate_status",
    "shared_memory_pages_status",
    "shared_memory_process_gate_enabled",
]
