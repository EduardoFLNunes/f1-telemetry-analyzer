"""Cache por gravacao do `atualizar_coach` (pedido 25).

O passo 1 (inventario) e o passo 6 (store v2) leem cada sessao de forma
independente, e o resultado de uma sessao so muda se os arquivos dela mudam
ou se muda o codigo, a geometria ou os portoes que a leitura usa. Este modulo
guarda, por sessao, o que a leitura produziu, e diz quando uma sessao pode
sair do cache.

Regras, iguais para os dois caches:

* **chave global** -- formato do cache, `geometry_id`, os portoes
  (`config.DEFAULT_GATES`) e o sha256 de cada arquivo de codigo que muda a
  leitura (listas explicitas abaixo). Se ela muda, ou se o cache nao abre, o
  cache inteiro e apagado e tudo e lido de novo: nunca ha mistura de cache
  velho com cache novo;
* **por sessao** -- o tamanho e a data de modificacao (em ns) de cada arquivo
  que a leitura abre. Iguais: a sessao sai do cache. Diferentes, ou a sessao
  fora do cache: ela e lida de novo;
* **so leitura nas gravacoes** -- nada aqui escreve, move ou apaga gravacao, e
  nenhum cache fica na pasta do app instalado.

Cada sessao vira um arquivo `pickle` com as estruturas exatamente como o
caminho completo as monta (listas de dicionarios e blocos de DataFrame), para
os tipos das colunas sairem iguais quando as tabelas sao montadas.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import shutil
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .. import config
from .recordings import PLAYER_STREAM, SESSION_INDEX, SESSION_METADATA, Session

# Sobe quando o conteudo dos arquivos do cache muda de forma.
CACHE_FORMAT = 1
MANIFEST = "manifesto.json"
PICKLE_PROTOCOL = 4

# Os arquivos de cada sessao que a leitura abre.
# Passo 1: `list_sessions` le o `session-index.json` (a pista) e `iter_laps`, o stream.
INVENTORY_FILES = (PLAYER_STREAM, SESSION_INDEX)
# Passo 6: o stream e o `metadata.json` (o `carModel` gravado).
STORE_FILES = (PLAYER_STREAM, SESSION_METADATA)

# Codigo que muda a leitura de uma sessao no passo 1 (caminhos relativos a `backend/`).
# `tests/test_atualizar_coach_incremental.py` confere que todo modulo `ml` que a
# leitura importa esta aqui, e que todo `.py` de `ml/preprocessing` e `ml/track` entra.
INVENTORY_CODE = (
    "ml/__init__.py",
    "ml/config.py",
    "ml/preprocessing/__init__.py",
    "ml/preprocessing/alignment.py",
    "ml/preprocessing/cleaning.py",
    "ml/preprocessing/quality.py",
    "ml/preprocessing/resampling.py",
    "ml/preprocessing/splits.py",
    "ml/track/__init__.py",
    "ml/track/corners.py",
    "ml/track/geometry.py",
    "ml/track/microsectors.py",
    "ml/track/trajectory.py",
    "ml/data/__init__.py",
    "ml/data/inventory.py",
    "ml/data/lap_identity.py",
    "ml/data/origin.py",
    "ml/data/origin_signals.py",
    "ml/data/recordings.py",
    "ml/data/samples.py",
    "ml/data/session_cache.py",
    "ml/scripts/report_lap_origin.py",
)
# Passo 6: o do passo 1 mais a materializacao das voltas (store v2, `pit_lap`,
# colunas do store). A selecao, os rotulos e o `carModel` sao recalculados a
# cada rodada e nao entram.
STORE_CODE = INVENTORY_CODE + (
    "ml/data/ai_detector.py",
    "ml/data/lap_store.py",
    "ml/data/store_v2.py",
    "ml/scripts/build_lap_store_v2.py",
)

# A pasta do app instalado: nenhum cache e gravado nela.
INSTALLED_APP_FOLDER = "Automobilista Telemetria"


class CacheBroken(Exception):
    """O cache nao abre: um arquivo dele nao le ou nao bate com o manifesto."""


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def code_hashes(files: Sequence[str]) -> Dict[str, str]:
    """sha256 de cada arquivo de codigo da lista (relativo a `backend/`)."""
    root = backend_root()
    return {name: file_sha256(root / name) for name in files}


def gates_dict(gates: Any) -> Dict[str, Any]:
    return asdict(gates) if is_dataclass(gates) else {"repr": repr(gates)}


def global_key(geometry_id: str, gates: Any, code_files: Sequence[str]) -> Dict[str, Any]:
    return {
        "formato": CACHE_FORMAT,
        "geometry_id": str(geometry_id),
        "portoes": gates_dict(gates),
        "codigo": code_hashes(code_files),
    }


def key_difference(old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    """O que mudou na chave global, em palavras."""
    out = []
    if old.get("formato") != new.get("formato"):
        out.append(f"formato do cache {old.get('formato')} -> {new.get('formato')}")
    if old.get("geometry_id") != new.get("geometry_id"):
        out.append(f"geometria {old.get('geometry_id')} -> {new.get('geometry_id')}")
    if old.get("portoes") != new.get("portoes"):
        out.append("portoes de qualidade")
    old_code, new_code = old.get("codigo") or {}, new.get("codigo") or {}
    changed = sorted(n for n in set(old_code) | set(new_code) if old_code.get(n) != new_code.get(n))
    if changed:
        out.append("codigo: " + ", ".join(changed))
    return out


def fingerprint(session: Session, names: Iterable[str]) -> Dict[str, Optional[Dict[str, int]]]:
    """Tamanho e data de modificacao (ns) de cada arquivo da sessao; `None` se ele nao existe."""
    out: Dict[str, Optional[Dict[str, int]]] = {}
    for name in names:
        path = Path(session.directory) / name
        try:
            stat = path.stat()
        except FileNotFoundError:
            out[name] = None
            continue
        out[name] = {"bytes": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}
    return out


def ensure_not_installed_app(path: Path) -> None:
    """Para se `path` estiver na pasta do app instalado."""
    resolved = str(Path(path).resolve()).lower()
    installed = config.installed_app_recordings_root()
    if INSTALLED_APP_FOLDER.lower() in resolved:
        raise ValueError(f"{path} fica na pasta do app instalado; nenhum cache e gravado nela")
    if installed is not None:
        app_root = str(Path(installed).resolve().parent).lower()
        if resolved == app_root or resolved.startswith(app_root + os.sep):
            raise ValueError(f"{path} fica na pasta do app instalado; nenhum cache e gravado nela")


def _safe_name(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id)) + ".pkl"


class SessionCache:
    """Um cache: o manifesto e um arquivo por sessao.

    `prepare` decide se o cache vale (devolve o motivo da leitura completa, ou
    `None`); `load` devolve o conteudo de uma sessao se os arquivos dela nao
    mudaram; `store` grava uma sessao lida; `finish` grava o manifesto.
    """

    def __init__(self, directory: Path, key: Dict[str, Any]):
        ensure_not_installed_app(directory)
        self.directory = Path(directory)
        self.key = key
        self.sessions: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------ abrir ---

    def _read_manifest(self) -> Optional[Dict[str, Any]]:
        path = self.directory / MANIFEST
        if not path.exists():
            return None
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CacheBroken(f"o manifesto nao abre: {exc}") from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("sessoes"), dict):
            raise CacheBroken("o manifesto nao tem a lista de sessoes")
        return manifest

    def prepare(self, force_reason: Optional[str] = None) -> Optional[str]:
        """Decide o modo. Devolve o motivo da leitura completa (e limpa o cache), ou `None`.

        Cache vazio nao e motivo de limpeza: as sessoes so nao estao nele.
        """
        reason = force_reason
        if reason is None:
            try:
                manifest = self._read_manifest()
            except CacheBroken as exc:
                reason = f"o cache nao abre ({exc})"
                manifest = None
            if manifest is not None and reason is None:
                changes = key_difference(manifest.get("chave") or {}, self.key)
                if changes:
                    reason = "a chave global mudou: " + "; ".join(changes)
                else:
                    self.sessions = dict(manifest["sessoes"])
            elif manifest is None and reason is None:
                reason = None if not self.directory.exists() or not any(self.directory.iterdir()) else (
                    "o cache nao tem manifesto")
        if reason is not None:
            self.reset()
        return reason

    def reset(self) -> None:
        """Apaga o cache inteiro (so a pasta do cache)."""
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.sessions = {}

    # ------------------------------------------------------- por sessao ---

    @property
    def session_ids(self) -> List[str]:
        return sorted(self.sessions)

    def entry(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def matches(self, session_id: str, files: Dict[str, Any]) -> bool:
        entry = self.sessions.get(session_id)
        return entry is not None and entry.get("arquivos") == files

    def load(self, session_id: str, files: Dict[str, Any]) -> Optional[Any]:
        """O conteudo da sessao, se ela esta no cache com os mesmos arquivos; senao `None`.

        Um arquivo que nao abre, ou que nao bate com o manifesto, levanta
        `CacheBroken`: quem chama refaz tudo.
        """
        if not self.matches(session_id, files):
            return None
        entry = self.sessions[session_id]
        path = self.directory / entry["arquivo_cache"]
        try:
            with path.open("rb") as handle:
                stored = pickle.load(handle)
        except Exception as exc:  # noqa: BLE001 -- qualquer falha de leitura invalida o cache
            raise CacheBroken(f"{path.name} nao abre: {exc}") from exc
        if not isinstance(stored, dict) or stored.get("session_id") != session_id or stored.get("arquivos") != files:
            raise CacheBroken(f"{path.name} nao bate com o manifesto")
        return stored["conteudo"]

    def store(self, session: Session, files: Dict[str, Any], content: Any, **extra: Any) -> None:
        """Grava uma sessao lida. Primeiro o arquivo (por um temporario), o manifesto so no `finish`."""
        self.directory.mkdir(parents=True, exist_ok=True)
        name = _safe_name(session.session_id)
        target = self.directory / name
        temporary = target.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump({"session_id": session.session_id, "arquivos": files, "conteudo": content},
                        handle, protocol=PICKLE_PROTOCOL)
        os.replace(temporary, target)
        self.sessions[session.session_id] = {
            "pasta": str(Path(session.directory).parent),
            "arquivos": files,
            "arquivo_cache": name,
            **extra,
        }

    def update(self, session_id: str, **extra: Any) -> None:
        self.sessions[session_id].update(extra)

    def remove(self, session_id: str) -> None:
        entry = self.sessions.pop(session_id, None)
        if entry is not None:
            path = self.directory / entry["arquivo_cache"]
            if path.exists():
                path.unlink()

    def finish(self, run: Dict[str, Any]) -> Path:
        """Grava o manifesto, com a chave, as sessoes e o resumo da rodada."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / MANIFEST
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "formato": CACHE_FORMAT,
            "chave": self.key,
            "sessoes": {sid: self.sessions[sid] for sid in sorted(self.sessions)},
            "ultima_rodada": run,
        }, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
        return path


def forget_session(directory: Path, session_id: str) -> bool:
    """Tira uma sessao do cache (o arquivo dela e a linha do manifesto), sem tocar na gravacao.

    Serve para simular uma sessao nova (pedido 25, Parte D, rodada 3). Devolve
    se a sessao estava no cache.
    """
    directory = Path(directory)
    ensure_not_installed_app(directory)
    path = directory / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = manifest["sessoes"].pop(session_id, None)
    if entry is None:
        return False
    stored = directory / entry["arquivo_cache"]
    if stored.exists():
        stored.unlink()
    path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return True


def folder_size(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    return int(sum(item.stat().st_size for item in path.rglob("*") if item.is_file()))
