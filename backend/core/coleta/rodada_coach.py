"""O botao "Atualizar coach e relatorio" (pedido 32, Parte B.3).

Roda o mesmo `tools/atualizar_coach.py`, incremental, com o Python e a pasta do
repositorio configurado na Coleta: o backend empacotado nao tem tudo o que o
comando usa, e o codigo continua num caminho so. O botao nao muda o comando,
os criterios nem as travas.

* **Ligado** quando o repositorio esta configurado (com o Python dele), nada
  esta sendo gravado e nenhuma rodada esta em andamento: nem pelo app, nem
  pelo terminal (a trava de execucao, `core.coleta.trava_coach`).
* **Durante:** os 7 passos, um a um, lidos da saida do comando, e o log
  inteiro num arquivo em `<pasta de dados>/data/coach_rodadas/`.
* **No fim:** as sessoes lidas, as voltas de cada uma no store v2, as
  referencias antes e depois e a contagem oficial da M1. Depois de uma rodada
  completa, o coach ao vivo recarrega o modelo.
* **Parada numa trava** (`PARADO: ...`): a mensagem do comando, como ele a
  escreveu; o servico nao tenta de novo sozinho.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .oficial import contagem_oficial
from .trava_coach import ler_trava, mensagem_de_ocupada

PASSOS = (
    ("1", "Inventário novo"),
    ("2", "Anotações de 04/10 e de sessão inteira"),
    ("3", "Sessões novas sem anotação"),
    ("4", "Backup e treino do modelo do coach"),
    ("5", "Resumo do coach"),
    ("6", "Store v2, com as checagens"),
    ("7", "Relatório de evolução"),
)
_PASSO = re.compile(r"^(\d)/7 ")
_TAMBEM = re.compile(r" (\d)/7 ")
_SESSAO_LIDA = re.compile(r"^\[(\d+)/(\d+)\] (\S+): (\d+) voltas(?P<cache> \(cache\))?\s*$")
LINHAS_GUARDADAS = 400


def comando_padrao(repositorio: Path) -> Optional[List[str]]:
    """O Python do repositorio e o comando; None quando o Python dele nao existe."""
    python = Path(repositorio) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    script = Path(repositorio) / "backend" / "tools" / "atualizar_coach.py"
    if not python.exists() or not script.exists():
        return None
    return [str(python), str(script)]


def _referencias(repositorio: Path) -> Dict[str, Any]:
    try:
        dados = json.loads((Path(repositorio) / "data" / "ml" / "origem" / "atualizar_coach.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dados.get("referencias") or {}


def _voltas_no_store(repositorio: Path, sessoes: Sequence[str]) -> Dict[str, int]:
    try:
        meta = json.loads((Path(repositorio) / "data" / "ml" / "laps_grid_v2_meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    contagem: Dict[str, int] = {s: 0 for s in sessoes}
    for volta in meta.get("laps") or []:
        sid = volta.get("session_id")
        if sid in contagem:
            contagem[sid] += 1
    return contagem


class RodadaDoCoach:
    def __init__(
        self,
        repositorio: Callable[[], Optional[Path]],
        gravando: Callable[[], bool],
        pasta_de_logs: Path,
        recarregar_coach: Callable[[], None],
        comando: Callable[[Path], Optional[List[str]]] = comando_padrao,
    ):
        self._repositorio = repositorio
        self._gravando = gravando
        self.pasta_de_logs = Path(pasta_de_logs)
        self._recarregar = recarregar_coach
        self._comando = comando
        self._lock = threading.Lock()
        self._processo: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._rodada: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------ estado ---

    def motivos_para_desligar(self) -> List[str]:
        motivos = []
        repo = self._repositorio()
        if repo is None:
            motivos.append("o repositório não está configurado (aba Coleta de dados)")
        elif self._comando(repo) is None:
            motivos.append(f"o repositório configurado não tem o Python dele (.venv) ou o tools/atualizar_coach.py: {repo}")
        if self._gravando():
            motivos.append("uma sessão está sendo gravada; espere ela terminar")
        if self.em_andamento():
            motivos.append("uma rodada do app está em andamento")
        elif repo is not None:
            trava = ler_trava(repo)
            if trava and trava.get("ativa"):
                motivos.append(mensagem_de_ocupada(trava).replace("PARADO: ", ""))
        return motivos

    def em_andamento(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def estado(self) -> Dict[str, Any]:
        motivos = self.motivos_para_desligar()
        with self._lock:
            rodada = json.loads(json.dumps(self._rodada)) if self._rodada else None
        return {"ligado": not motivos, "motivos": motivos, "emAndamento": self.em_andamento(), "rodada": rodada,
                "passos": [{"id": p, "nome": n} for p, n in PASSOS]}

    # ------------------------------------------------------------ rodada ---

    def iniciar(self) -> Dict[str, Any]:
        motivos = self.motivos_para_desligar()
        if motivos:
            raise RuntimeError("; ".join(motivos))
        repo = self._repositorio()
        assert repo is not None
        comando = self._comando(repo)
        assert comando is not None
        inicio = datetime.now()
        self.pasta_de_logs.mkdir(parents=True, exist_ok=True)
        log = self.pasta_de_logs / f"atualizar_coach_{inicio.strftime('%Y-%m-%d_%H-%M-%S')}.log"
        with self._lock:
            self._rodada = {
                "situacao": "rodando",
                "inicio": inicio.isoformat(timespec="seconds"),
                "fim": None,
                "repositorio": str(repo),
                "comando": comando,
                "log": str(log),
                "passos": {p: "pendente" for p, _ in PASSOS},
                "passoAtual": None,
                "linhas": [],
                "sessoesLidas": [],
                "mensagemDeParada": None,
                "codigo": None,
                "resumo": None,
                "referenciasAntes": _referencias(repo),
                "coachRecarregado": False,
            }
            self._thread = threading.Thread(target=self._rodar, args=(repo, comando, log), daemon=True,
                                            name="atualizar-coach")
            self._thread.start()
        return self.estado()

    def _rodar(self, repo: Path, comando: List[str], log: Path) -> None:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "AT_COACH_RODADA_ORIGEM": "app"}
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        codigo: Optional[int] = None
        try:
            with log.open("w", encoding="utf-8", newline="\n") as saida:
                processo = subprocess.Popen(
                    comando, cwd=str(Path(repo) / "backend"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", env=env, creationflags=flags,
                )
                with self._lock:
                    self._processo = processo
                assert processo.stdout is not None
                for linha in processo.stdout:
                    saida.write(linha)
                    saida.flush()
                    self._linha(linha.rstrip("\r\n"))
                codigo = processo.wait()
        except OSError as erro:
            self._linha(f"PARADO: o comando nao abriu: {erro}")
            codigo = -1
        self._fechar(repo, codigo)

    def _linha(self, linha: str) -> None:
        with self._lock:
            r = self._rodada
            if r is None:
                return
            r["linhas"].append(linha)
            del r["linhas"][:-LINHAS_GUARDADAS]
            passo = _PASSO.match(linha)
            if passo:
                ids = [passo.group(1)] + _TAMBEM.findall(linha)
                for p, estado in r["passos"].items():
                    if estado == "rodando":
                        r["passos"][p] = "feito"
                for p in ids:
                    if p in r["passos"]:
                        r["passos"][p] = "rodando"
                r["passoAtual"] = ids[-1]
            lida = _SESSAO_LIDA.match(linha)
            if lida and not lida.group("cache") and r.get("passoAtual") == "1":
                r["sessoesLidas"].append({"sessao": lida.group(3), "voltas": int(lida.group(4))})
            if linha.startswith("PARADO:") and not r["mensagemDeParada"]:
                r["mensagemDeParada"] = linha

    def _fechar(self, repo: Path, codigo: Optional[int]) -> None:
        with self._lock:
            r = self._rodada
            assert r is not None
            r["codigo"] = codigo
            r["fim"] = datetime.now().isoformat(timespec="seconds")
            parada = r["mensagemDeParada"]
            if codigo == 0 and not parada:
                r["situacao"] = "concluida"
                for p in r["passos"]:
                    r["passos"][p] = "feito"
            else:
                r["situacao"] = "parada" if parada else "falhou"
                for p, estado in r["passos"].items():
                    if estado == "rodando":
                        r["passos"][p] = "parado"
            sessoes = [s["sessao"] for s in r["sessoesLidas"]]
            antes = r["referenciasAntes"]
        resumo = None
        if codigo == 0 and not parada:
            store = _voltas_no_store(repo, sessoes)
            resumo = {
                "sessoesLidas": [{"sessao": s, "voltasNoStore": store.get(s, 0)} for s in sessoes],
                "referenciasAntes": antes,
                "referenciasDepois": _referencias(repo),
                "m1": contagem_oficial(repo),
            }
        recarregado = False
        if codigo == 0 and not parada:
            try:
                self._recarregar()
                recarregado = True
            except Exception as erro:  # o modelo novo ja esta no disco; o coach o le na proxima abertura
                self._linha(f"aviso: o coach ao vivo nao recarregou o modelo: {erro}")
        with self._lock:
            self._rodada["resumo"] = resumo
            self._rodada["coachRecarregado"] = recarregado
            self._processo = None
