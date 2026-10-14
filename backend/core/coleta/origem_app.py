"""Qual app gravou a sessao: a versao e o commit (pedido 28, Parte C.4).

No app instalado, o Electron passa o carimbo do build (`build-info.json`) nas
variaveis `AT_APP_*`. Rodando do codigo-fonte, o backend pergunta ao git do
repositorio, e diz se a arvore tinha mudancas nao commitadas.

Vai para o `metadata.json` de cada sessao nova (`appVersion`, `appCommit`,
`appCommitDirty`, `appPackaged`), ao lado dos campos que ja existiam.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

_cache: Optional[Dict[str, Any]] = None


def _flag(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    return value.strip().lower() in ("1", "true", "yes", "on")


def _git(args, cwd: Path) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def app_identity(repo_root: Path, refresh: bool = False) -> Dict[str, Any]:
    """{"versao", "commit", "commitCurto", "arvoreSuja", "empacotado", "fonte", "construidoEm"}."""
    global _cache
    if _cache is not None and not refresh:
        return dict(_cache)
    version = os.environ.get("AT_APP_VERSION")
    commit = os.environ.get("AT_APP_COMMIT")
    if version or commit:
        identity = {
            "versao": version or None,
            "commit": commit or None,
            "arvoreSuja": _flag(os.environ.get("AT_APP_BUILD_DIRTY")),
            "empacotado": bool(_flag(os.environ.get("AT_APP_PACKAGED"))),
            "fonte": "build-info",
            "construidoEm": os.environ.get("AT_APP_BUILT_AT") or None,
        }
    else:
        root = Path(repo_root)
        version = None
        try:
            version = json.loads((root / "desktop" / "package.json").read_text(encoding="utf-8")).get("version")
        except (OSError, json.JSONDecodeError):
            pass
        status = _git(["status", "--porcelain"], root)
        identity = {
            "versao": version,
            "commit": _git(["rev-parse", "HEAD"], root),
            "arvoreSuja": None if status is None else bool(status),
            "empacotado": False,
            "fonte": "git",
            "construidoEm": None,
        }
    identity["commitCurto"] = identity["commit"][:7] if identity.get("commit") else None
    _cache = identity
    return dict(identity)


def metadata_fields(repo_root: Path) -> Dict[str, Any]:
    """Os campos novos do `metadata.json`."""
    identity = app_identity(repo_root)
    return {
        "appVersion": identity["versao"],
        "appCommit": identity["commit"],
        "appCommitDirty": identity["arvoreSuja"],
        "appPackaged": identity["empacotado"],
    }
