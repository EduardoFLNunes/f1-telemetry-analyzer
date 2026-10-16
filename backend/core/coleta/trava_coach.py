"""A trava de execucao do `atualizar_coach` (pedido 32, Parte B).

Uma rodada por vez, venha ela do terminal ou do botao do app: o comando cria
`data/ml/atualizar_coach.lock` no repositorio antes do passo 1 e apaga no fim,
mesmo quando para numa trava. O arquivo diz quem roda (processo e inicio).

Uma trava cujo processo ja nao existe (o comando foi morto, o PC desligou) e
velha: a proxima rodada a substitui e diz isso. A trava nao muda nada do que o
comando le ou grava; ela so impede duas rodadas ao mesmo tempo.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

NOME_DA_TRAVA = "atualizar_coach.lock"


def caminho_da_trava(repositorio: Path) -> Path:
    return Path(repositorio) / "data" / "ml" / NOME_DA_TRAVA


def processo_vivo(pid: int) -> bool:
    """O processo existe? Sem `os.kill(pid, 0)`, que no Windows encerraria o processo."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            codigo = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return False
            return codigo.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def ler_trava(repositorio: Path) -> Optional[Dict[str, Any]]:
    """O conteudo da trava, com `ativa` (o processo ainda roda); None sem trava."""
    caminho = caminho_da_trava(repositorio)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        # Acabou de ser criada e ainda esta sendo escrita: conta como ativa por alguns segundos.
        try:
            recente = (datetime.now().timestamp() - caminho.stat().st_mtime) < 10
        except OSError:
            recente = False
        return {"pid": 0, "ativa": recente, "arquivo": str(caminho)}
    pid = int(dados.get("pid") or 0)
    return {**dados, "pid": pid, "ativa": processo_vivo(pid), "arquivo": str(caminho)}


class TravaOcupada(RuntimeError):
    def __init__(self, info: Dict[str, Any]):
        self.info = info
        super().__init__(mensagem_de_ocupada(info))


def mensagem_de_ocupada(info: Dict[str, Any]) -> str:
    inicio = str(info.get("inicio") or "")[11:19] or "horario desconhecido"
    origem = info.get("origem") or "terminal"
    return (f"PARADO: outra rodada do atualizar_coach esta em andamento "
            f"(processo {info.get('pid')}, desde {inicio}, pelo {origem}).")


class TravaDeExecucao:
    """`with TravaDeExecucao(repo):` segura a trava durante a rodada."""

    def __init__(self, repositorio: Path, origem: Optional[str] = None):
        self.caminho = caminho_da_trava(repositorio)
        self.repositorio = Path(repositorio)
        self.origem = origem or os.environ.get("AT_COACH_RODADA_ORIGEM") or "terminal"
        self.substituiu: Optional[Dict[str, Any]] = None
        self._minha = False

    def __enter__(self) -> "TravaDeExecucao":
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conteudo = json.dumps({"pid": os.getpid(), "inicio": datetime.now().isoformat(timespec="seconds"),
                               "origem": self.origem}, ensure_ascii=False)
        for _ in range(2):
            try:
                fd = os.open(str(self.caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                info = ler_trava(self.repositorio) or {}
                if info.get("ativa"):
                    raise TravaOcupada(info)
                # Velha: o processo dela nao existe mais.
                self.substituiu = info
                try:
                    self.caminho.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(conteudo)
            self._minha = True
            return self
        raise TravaOcupada(ler_trava(self.repositorio) or {})

    def __exit__(self, *exc) -> None:
        if not self._minha:
            return
        try:
            info = json.loads(self.caminho.read_text(encoding="utf-8"))
            if int(info.get("pid") or 0) == os.getpid():
                self.caminho.unlink()
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        self._minha = False
