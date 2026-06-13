"""Desktop backend runner for the Electron packaging flow."""

from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from pathlib import Path

import uvicorn


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _backend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _int_env(name: str, fallback: int) -> int:
    try:
        return int(os.environ.get(name, str(fallback)))
    except ValueError:
        logging.warning("Invalid %s value; falling back to %s", name, fallback)
        return fallback


def main() -> None:
    multiprocessing.freeze_support()
    backend_dir = _backend_dir()
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    resource_root = Path(
        os.environ.get("AT_BACKEND_RESOURCE_ROOT")
        or os.environ.get("AT_BACKEND_REPO_ROOT")
        or (Path.cwd() if getattr(sys, "frozen", False) else backend_dir.parent)
    ).resolve()
    runtime_root = Path(
        os.environ.get("AT_BACKEND_RUNTIME_ROOT")
        or os.environ.get("AT_BACKEND_REPO_ROOT")
        or resource_root
    ).resolve()
    os.environ.setdefault("AT_BACKEND_RESOURCE_ROOT", str(resource_root))
    os.environ.setdefault("AT_BACKEND_RUNTIME_ROOT", str(runtime_root))
    os.environ.setdefault("AT_BACKEND_REPO_ROOT", str(resource_root))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    host = os.environ.get("AT_BACKEND_HOST", DEFAULT_HOST)
    port = _int_env("AT_BACKEND_PORT", DEFAULT_PORT)
    log_level = os.environ.get("AT_BACKEND_LOG_LEVEL", "info")

    logging.getLogger(__name__).info(
        "Starting desktop backend runner on %s:%s from %s resource=%s runtime=%s",
        host,
        port,
        backend_dir,
        resource_root,
        runtime_root,
    )
    from main import app as fastapi_app

    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
        access_log=True,
    )


if __name__ == "__main__":
    main()
