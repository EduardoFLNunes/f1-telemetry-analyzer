"""Startup gate for Assetto Corsa shared-memory access.

The Windows shared-memory pages are owned by the running simulator. Opening
them before Assetto Corsa creates them can interfere with simulator startup on
some systems. Python's Windows mmap API may create a named mapping when it does
not exist yet, so this module probes existing pages with OpenFileMappingW first.
"""

from __future__ import annotations

import os
import threading
import time
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


if os.name == "nt":
    class _ACStaticProbe(ctypes.Structure):
        _pack_ = 4
        _fields_ = [
            ("smVersion", ctypes.c_wchar * 15),
            ("acVersion", ctypes.c_wchar * 15),
            ("numberOfSessions", ctypes.c_int),
            ("numCars", ctypes.c_int),
            ("carModel", ctypes.c_wchar * 33),
            ("track", ctypes.c_wchar * 33),
            ("playerName", ctypes.c_wchar * 33),
        ]


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


def _read_static_mapping(alias: str) -> Dict[str, Any]:
    if os.name != "nt":
        return {"exists": False, "error": "unsupported_platform"}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.OpenFileMappingW.restype = ctypes.c_void_p
    kernel32.MapViewOfFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_size_t,
    ]
    kernel32.MapViewOfFile.restype = ctypes.c_void_p
    kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    kernel32.UnmapViewOfFile.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, alias)
    if not handle:
        return {"exists": False, "error": f"open_failed:{ctypes.get_last_error()}"}

    view = kernel32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, ctypes.sizeof(_ACStaticProbe))
    if not view:
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        return {"exists": True, "error": f"map_failed:{error}"}

    try:
        data = _ACStaticProbe.from_address(view)
        return {
            "exists": True,
            "error": None,
            "alias": alias,
            "smVersion": str(data.smVersion).rstrip("\x00").strip(),
            "acVersion": str(data.acVersion).rstrip("\x00").strip(),
            "carModel": str(data.carModel).rstrip("\x00").strip(),
            "track": str(data.track).rstrip("\x00").strip(),
            "playerName": str(data.playerName).rstrip("\x00").strip(),
            "numberOfSessions": int(data.numberOfSessions),
            "numCars": int(data.numCars),
        }
    finally:
        kernel32.UnmapViewOfFile(view)
        kernel32.CloseHandle(handle)


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


def shared_memory_static_status() -> Dict[str, Any]:
    checked_aliases = list(_page_aliases("acpmf_static"))
    snapshots = [_read_static_mapping(alias) for alias in checked_aliases]
    snapshot = next((item for item in snapshots if item.get("exists") and not item.get("error")), None)

    if not snapshot:
        existing_error = next((item.get("error") for item in snapshots if item.get("exists")), None)
        return {
            "checked": True,
            "ready": False,
            "aliases": checked_aliases,
            "reason": existing_error or "static_page_missing",
        }

    track = str(snapshot.get("track") or "").strip()
    car_model = str(snapshot.get("carModel") or "").strip()
    ready = bool(track and car_model)
    return {
        "checked": True,
        "ready": ready,
        "reason": None if ready else "static_page_has_no_session_data",
        "alias": snapshot.get("alias"),
        "track": track,
        "carModel": car_model,
        "smVersion": snapshot.get("smVersion"),
        "acVersion": snapshot.get("acVersion"),
        "numberOfSessions": snapshot.get("numberOfSessions"),
        "numCars": snapshot.get("numCars"),
    }


def _compute_shared_memory_gate_status() -> Dict[str, Any]:
    enabled = shared_memory_process_gate_enabled()
    process_names = assetto_corsa_process_names()
    process_running = assetto_corsa_process_running(process_names) if enabled else True
    pages_status = shared_memory_pages_status() if enabled else {
        "checked": False,
        "required": list(assetto_corsa_shared_memory_pages()),
        "available": {},
        "missing": [],
        "ready": True,
    }
    static_status = {"checked": False, "ready": not enabled}
    reason = None

    if enabled and not process_running:
        allowed = False
        reason = (
            "stale_assetto_corsa_shared_memory_without_process"
            if pages_status.get("available")
            else "waiting_for_assetto_corsa_process"
        )
    elif enabled:
        if not pages_status.get("ready"):
            allowed = False
            reason = "waiting_for_assetto_corsa_shared_memory_pages"
        else:
            static_status = shared_memory_static_status()
            allowed = bool(static_status.get("ready"))
            if not allowed:
                reason = "waiting_for_assetto_corsa_static_data"
    else:
        allowed = True

    return {
        "enabled": enabled,
        "allowed": allowed,
        "processRunning": process_running,
        "processNames": list(process_names),
        "pages": pages_status,
        "static": static_status,
        "reason": reason,
    }


_GATE_CACHE_TTL_ENV = "AT_GATE_STATUS_TTL_SECONDS"
_DEFAULT_GATE_CACHE_TTL = 1.0

_gate_cache_lock = threading.Lock()
_gate_cache_value: Dict[str, Any] | None = None
_gate_cache_at: float = 0.0


def _gate_cache_ttl() -> float:
    raw = os.environ.get(_GATE_CACHE_TTL_ENV)
    if raw is None:
        return _DEFAULT_GATE_CACHE_TTL
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return _DEFAULT_GATE_CACHE_TTL


def reset_gate_status_cache() -> None:
    """Drop the memoized gate status. Tests use this between scenarios."""
    global _gate_cache_value, _gate_cache_at
    with _gate_cache_lock:
        _gate_cache_value = None
        _gate_cache_at = 0.0


def shared_memory_gate_status(*, force_refresh: bool = False) -> Dict[str, Any]:
    """Gate status, memoized for a short TTL.

    Probing the game process shells out to `tasklist`, which costs tens to
    hundreds of milliseconds. This is called from request handlers that the
    desktop UI polls every few seconds, and those handlers are async, so an
    uncached probe blocks the event loop and can stall every other endpoint --
    including /api/health, which is what Electron waits on at startup. The gate
    state does not change faster than the TTL in practice.
    """
    global _gate_cache_value, _gate_cache_at
    ttl = _gate_cache_ttl()
    if not force_refresh and ttl > 0.0:
        with _gate_cache_lock:
            cached = _gate_cache_value
            cached_at = _gate_cache_at
        if cached is not None and (time.monotonic() - cached_at) < ttl:
            return dict(cached)

    status = _compute_shared_memory_gate_status()
    with _gate_cache_lock:
        _gate_cache_value = status
        _gate_cache_at = time.monotonic()
    return dict(status)


def shared_memory_access_allowed() -> bool:
    return bool(shared_memory_gate_status()["allowed"])


__all__ = [
    "assetto_corsa_process_names",
    "assetto_corsa_process_running",
    "assetto_corsa_shared_memory_pages",
    "reset_gate_status_cache",
    "shared_memory_access_allowed",
    "shared_memory_gate_status",
    "shared_memory_pages_status",
    "shared_memory_static_status",
    "shared_memory_process_gate_enabled",
]
