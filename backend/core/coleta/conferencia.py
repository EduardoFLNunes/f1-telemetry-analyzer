"""A conferencia de uma sessao gravada, volta a volta e no fim (pedido 28, Parte D.3).

Cada volta passa pelas mesmas funcoes do pipeline do ML, na mesma ordem do
store v2 (`ml.data.store_v2.materialize_session`):

    flatten -> corte pelo cronometro -> clean_lap -> align_lap -> evaluate_lap
            -> resample_lap(line_clock=True) -> portao do box

O corte em voltas e o de `ml.data.recordings.iter_laps`, feito aos poucos: a
leitura continua de onde parou, porque durante a sessao o arquivo cresce. Um
teste confere que o corte daqui e o de `iter_laps` dao as mesmas voltas.

**O veredito da sessao e uma previa** da regra da M1 (docs/modelo_fisico_m0.md,
secao 6):

* sessao humana: o indicador de IA desligado em todas as voltas
  (`ml.data.origin.lap_origin` igual a `humano` em todas);
* os canais obrigatorios (guinada e velocidades no referencial do carro) em pelo
  menos 95% dos pontos da grade das voltas validas (validas pelos portoes e fora
  do box, como o store v2 seleciona).

A contagem oficial continua no store v2, refeito pelo `atualizar_coach`
(`core.coleta.oficial`).

O resultado e gravado em `<pasta de dados>/data/verificacoes/<sessao>.json`,
fora da pasta de gravacoes. A gravacao e so lida.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ml import config as ml_config
from ml.data.origin import AI, HUMAN, MIXED, UNKNOWN, lap_origin
from ml.data.recordings import _is_new_lap
from ml.data.samples import flatten
from ml.preprocessing.alignment import align_lap
from ml.preprocessing.cleaning import clean_lap
from ml.preprocessing.quality import evaluate_lap
from ml.preprocessing.resampling import lap_time_from_grid, resample_lap
from ml.track.geometry import TrackGeometry, load_geometry
from ml.track.microsectors import Microsectors, build_microsectors

from .requisitos import (
    COLUNAS_M1,
    GRUPOS,
    NOME_M1,
    PISTA_ESPERADA,
    PREENCHIMENTO_M1,
    REQUISITOS,
    colunas_store,
    valor_componente,
)

logger = logging.getLogger(__name__)

FORMATO = "coleta-verificacao/1"
PASTA_VERIFICACOES = Path("data") / "verificacoes"
PLAYER_STREAM = "player.jsonl"
METADATA = "metadata.json"
MIN_AMOSTRAS = 2               # iter_laps(min_samples=2), como o store v2
BLOCO_DE_LEITURA = 8 << 20     # le no maximo 8 MB por vez

ORIGEM_ROTULO = {HUMAN: "você", AI: "IA", MIXED: "misturada", UNKNOWN: "sem indicador"}


def formatar_tempo(segundos: Optional[float]) -> Optional[str]:
    """M:SS,mmm."""
    if segundos is None or not np.isfinite(segundos) or segundos < 0:
        return None
    minutos = int(segundos // 60)
    resto = segundos - minutos * 60
    texto = f"{resto:06.3f}".replace(".", ",")
    return f"{minutos}:{texto}"


def pit_lap(grid: pd.DataFrame, sectors: Microsectors, lateral_m: float = 10.0, speed_kmh: float = 90.0) -> bool:
    """Copia de `ml.data.ai_detector.pit_lap` (pedido 12).

    O detector importa `ml.validation`, que puxa o torch; o backend empacotado
    nao leva o torch. Um teste confere que as duas dao o mesmo resultado.
    """
    near_line = np.isin(sectors.index, [0, 1, 2, 3, sectors.count - 3, sectors.count - 2, sectors.count - 1])
    lateral = np.abs(grid["lateral"].to_numpy(dtype=float))[near_line]
    speed = grid["speed_kmh"].to_numpy(dtype=float)[near_line]
    return bool(np.nanmax(lateral) > lateral_m and np.nanmin(speed) < speed_kmh)


# ------------------------------------------------------------ geometria ---

@dataclass
class Geometria:
    track: TrackGeometry
    sectors: Microsectors
    arquivo: Path
    origem: str

    def to_api(self) -> Dict[str, Any]:
        return {"geometryId": self.track.geometry_id, "arquivo": str(self.arquivo), "origem": self.origem,
                "pontos": int(self.track.size), "comprimentoM": round(float(self.track.length), 2)}


_geometrias: Dict[Tuple[str, float, int], Geometria] = {}
_geometrias_lock = threading.Lock()


def candidatos_de_geometria(repositorio: Optional[Path], pasta_de_dados: Optional[Path]) -> List[Tuple[Path, str]]:
    """O cache de Interlagos do repositorio (o do ML) e, sem ele, o da pasta de dados do app."""
    nome = ml_config.INTERLAGOS_GEOMETRY_FILE
    out = []
    if repositorio is not None:
        out.append((Path(repositorio) / "data" / "cache" / "tracks" / nome, "repositório"))
    if pasta_de_dados is not None:
        out.append((Path(pasta_de_dados) / "data" / "cache" / "tracks" / nome, "pasta de dados do app"))
    return out


def carregar_geometria(candidatos: Sequence[Tuple[Path, str]]) -> Optional[Geometria]:
    for arquivo, origem in candidatos:
        try:
            info = arquivo.stat()
        except OSError:
            continue
        chave = (str(arquivo), info.st_mtime, info.st_size)
        with _geometrias_lock:
            if chave not in _geometrias:
                track = load_geometry(arquivo)
                _geometrias[chave] = Geometria(track, build_microsectors(track), arquivo, origem)
            return _geometrias[chave]
    return None


# --------------------------------------------------------------- volta ---

def _presente(item, amostra: Mapping[str, Any], envelope: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    return all(valor_componente(item, c, amostra, envelope, metadata) is not None for c in item.componentes)


ITENS_POR_LINHA = tuple(r for r in REQUISITOS if r.fonte != "metadata")
ITENS_DE_METADATA = tuple(r for r in REQUISITOS if r.fonte == "metadata")
COLUNAS_DA_GRADE = tuple(c for c in colunas_store() if c not in ("lap_time_s", "elapsed_s", "lateral", "x", "z"))


def avaliar_volta(frame: pd.DataFrame, geometria: Geometria) -> Dict[str, Any]:
    """Uma volta crua (linhas do `flatten`) pelos portoes e pela grade, como no store v2."""
    out: Dict[str, Any] = {"valida": False, "motivos": [], "box": None, "tempoS": None,
                           "duracaoS": None, "grade": {}, "pontosDaGrade": int(geometria.track.size)}
    cleaned, _ = clean_lap(frame)
    if cleaned.empty or len(cleaned) < 4:
        out["motivos"] = ["amostras insuficientes após a limpeza"]
        return out
    aligned, alignment = align_lap(cleaned, geometria.track)
    quality = evaluate_lap(aligned, geometria.track, alignment)
    duracao = quality.metrics.get("duration_s")
    out["duracaoS"] = float(duracao) if duracao is not None and np.isfinite(duracao) else None
    out["taxaHz"] = float(quality.metrics["sample_hz"]) if np.isfinite(quality.metrics.get("sample_hz", np.nan)) else None
    out["motivos"] = list(quality.reasons)
    out["valida"] = bool(quality.valid)
    if not quality.valid:
        return out
    grid = resample_lap(aligned, geometria.track, line_clock=True)
    out["box"] = pit_lap(grid, geometria.sectors)
    tempo = lap_time_from_grid(grid)
    out["tempoS"] = float(tempo) if tempo is not None and np.isfinite(tempo) else None
    for coluna in COLUNAS_DA_GRADE:
        valores = grid[coluna].to_numpy(dtype=float) if coluna in grid.columns else np.array([])
        out["grade"][coluna] = int(np.isfinite(valores).sum())
    return out


# -------------------------------------------------------------- sessao ---

def _juntar(nomes: List[str]) -> str:
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _nomes_dos_canais(colunas: List[str]) -> List[str]:
    nomes = []
    if "velocity_long" in colunas and "velocity_lat" in colunas:
        resto = [c for c in colunas if c not in ("velocity_long", "velocity_lat")]
        nomes = [NOME_M1[c] for c in resto] + ["as velocidades no referencial do carro"]
    else:
        nomes = [NOME_M1[c] for c in colunas]
    return nomes


def _voltas_texto(voltas: List[Dict[str, Any]]) -> str:
    return _juntar([f"#{v['sequencia']:04d}" for v in voltas])


def veredito_m1(voltas: List[Dict[str, Any]], pontos_da_grade: int, final: bool) -> Dict[str, Any]:
    """A previa da regra da M1 sobre as voltas conferidas."""
    validas = [v for v in voltas if v["valida"] and not v["box"]]
    preenchimento: Dict[str, Optional[float]] = {}
    for coluna in COLUNAS_M1 + tuple(c for c in COLUNAS_DA_GRADE if c.startswith("brake_temp")):
        total = len(validas) * pontos_da_grade
        preenchimento[coluna] = (sum(v["grade"].get(coluna, 0) for v in validas) / total) if total else None

    ia = [v for v in voltas if v["origem"] in (AI, MIXED)]
    sem_indicador = [v for v in voltas if v["origem"] == UNKNOWN]
    humana = bool(voltas) and all(v["origem"] == HUMAN for v in voltas)
    ausentes = [c for c in COLUNAS_M1 if validas and (preenchimento[c] or 0.0) == 0.0]
    parciais = [c for c in COLUNAS_M1 if validas and 0.0 < (preenchimento[c] or 0.0) < PREENCHIMENTO_M1]

    falta: List[str] = []
    if ausentes:
        nomes = _nomes_dos_canais(ausentes)
        falta.append(("faltam " if len(nomes) > 1 or "velocidades" in nomes[0] else "falta ") + _juntar(nomes))
    for coluna in parciais:
        falta.append(f"{NOME_M1[coluna]} está em {preenchimento[coluna]:.0%} dos pontos (mínimo de {PREENCHIMENTO_M1:.0%})")
    if ia:
        falta.append(f"há volta com a IA no volante ({_voltas_texto(ia)})")
    if sem_indicador:
        if len(sem_indicador) == len(voltas):
            falta.append("o indicador de IA não foi gravado")
        else:
            falta.append(f"o indicador de IA falta em parte das amostras ({_voltas_texto(sem_indicador)})")
    if not voltas:
        falta.append("nenhuma volta gravada")
    elif not validas:
        falta.append("nenhuma volta válida pelos portões de qualidade")

    conta = humana and bool(validas) and not ausentes and not parciais
    if conta:
        texto = "Conta para a M1."
    else:
        texto = "Não conta para a M1: " + "; ".join(falta) + "."
    if not final:
        texto = "Até agora: " + texto[0].lower() + texto[1:]
    return {
        "conta": conta,
        "final": final,
        "texto": texto,
        "falta": falta,
        "humana": humana,
        "voltas": len(voltas),
        "voltasValidas": len(validas),
        "voltasComIA": [v["sequencia"] for v in ia],
        "voltasSemIndicador": [v["sequencia"] for v in sem_indicador],
        "preenchimentoGrade": {k: (round(v, 4) if v is not None else None) for k, v in preenchimento.items()},
        "limiar": PREENCHIMENTO_M1,
        "regra": "sessão humana (indicador de IA desligado em todas as voltas) com a guinada e as velocidades "
                 "no referencial do carro em pelo menos 95% dos pontos da grade das voltas válidas",
    }


class ConferenciaSessao:
    """Le uma sessao aos poucos e confere cada volta quando ela fecha."""

    def __init__(self, diretorio: Path, geometria: Optional[Geometria]):
        self.diretorio = Path(diretorio)
        self.session_id = self.diretorio.name
        self.geometria = geometria
        self.offset = 0
        self._resto = b""
        self.linhas = 0
        self.corrompidas = 0
        self.final = False
        self.metadata = self._ler_metadata()
        self.pista = (self.metadata.get("track") or None)
        self.voltas: List[Dict[str, Any]] = []
        self.segundos_de_conferencia = 0.0
        # O corte em voltas, espelho de `iter_laps`.
        self._rows: List[Dict[str, Any]] = []
        self._corrupt = 0
        self._lap_number: Optional[int] = None
        self._sequence = 0
        self._previous: Dict[str, Any] = {}
        self._presenca: Counter = Counter()
        self._linhas_da_volta = 0

    def _ler_metadata(self) -> Dict[str, Any]:
        try:
            return json.loads((self.diretorio / METADATA).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # ---------------------------------------------------------- leitura ---

    def ler(self, limite_bytes: Optional[int] = None) -> int:
        """Le o que o arquivo cresceu desde a ultima leitura. Devolve as linhas lidas."""
        caminho = self.diretorio / PLAYER_STREAM
        try:
            tamanho = caminho.stat().st_size
        except OSError:
            return 0
        if tamanho <= self.offset:
            return 0
        lidas = 0
        with caminho.open("rb") as handle:
            handle.seek(self.offset)
            while True:
                quanto = BLOCO_DE_LEITURA if limite_bytes is None else min(BLOCO_DE_LEITURA, limite_bytes)
                bloco = handle.read(quanto)
                if not bloco:
                    break
                self.offset += len(bloco)
                partes = (self._resto + bloco).split(b"\n")
                self._resto = partes.pop()
                for parte in partes:
                    self._linha(parte)
                    lidas += 1
                if limite_bytes is not None:
                    limite_bytes -= len(bloco)
                    if limite_bytes <= 0:
                        break
        self.linhas += lidas
        return lidas

    def concluir(self) -> None:
        """Fim da sessao: a ultima linha sem quebra e a ultima volta."""
        self.ler()
        if self._resto.strip():
            self._linha(self._resto)
            self.linhas += 1
        self._resto = b""
        self._fechar_volta()
        self.final = True
        self.metadata = self._ler_metadata()

    def _linha(self, bruta: bytes) -> None:
        texto = bruta.decode("utf-8", errors="replace")
        if not texto.strip():
            return
        try:
            envelope = json.loads(texto)
        except json.JSONDecodeError:
            self._corrupt += 1
            self.corrompidas += 1
            return
        if not isinstance(envelope, dict):
            self._corrupt += 1
            self.corrompidas += 1
            return
        row = flatten(envelope)
        if row.get("lap_number") is None:
            self._corrupt += 1
            self.corrompidas += 1
            return
        if self._previous and _is_new_lap(row, self._previous):
            self._fechar_volta()
            # Como em iter_laps: a ordem avanca a cada corte, entregue ou nao a volta.
            self._sequence += 1
            self._rows, self._corrupt = [], 0
            self._presenca = Counter()
            self._linhas_da_volta = 0
            self._lap_number = int(row["lap_number"])
        elif self._lap_number is None:
            self._lap_number = int(row["lap_number"])
        self._rows.append(row)
        self._previous = row
        amostra = envelope.get("sample") if isinstance(envelope.get("sample"), Mapping) else envelope
        self._linhas_da_volta += 1
        for item in ITENS_POR_LINHA:
            if _presente(item, amostra, envelope, self.metadata):
                self._presenca[item.id] += 1

    def _fechar_volta(self) -> None:
        if self._lap_number is None or len(self._rows) < MIN_AMOSTRAS:
            return
        inicio = time.perf_counter()
        frame = pd.DataFrame(self._rows)
        lap_id = f"{self.session_id}#{self._sequence:04d}"
        flags = frame["ai_controlled"].tolist() if "ai_controlled" in frame.columns else [None] * len(frame)
        origem = lap_origin(flags)
        n = max(self._linhas_da_volta, 1)
        itens = {item.id: round(self._presenca[item.id] / n, 4) for item in ITENS_POR_LINHA}
        for item in ITENS_DE_METADATA:
            itens[item.id] = 1.0 if all(valor_componente(item, c, {}, None, self.metadata) is not None
                                         for c in item.componentes) else 0.0
        grupos = {}
        for gid, _ in GRUPOS:
            do_grupo = [(r.id, itens[r.id]) for r in REQUISITOS if r.grupo == gid]
            if do_grupo:
                pior_id, pior_valor = min(do_grupo, key=lambda par: par[1])
                grupos[gid] = {"minimo": pior_valor, "piorItem": pior_id}
        volta = {
            "lapId": lap_id,
            "sequencia": self._sequence,
            "voltaDoJogo": int(self._lap_number),
            "amostras": int(len(frame)),
            "linhasCorrompidas": int(self._corrupt),
            "origem": origem,
            "origemRotulo": ORIGEM_ROTULO.get(origem, origem),
            "preenchimentoItens": itens,
            "preenchimentoGrupos": grupos,
        }
        if self.geometria is None:
            volta.update({"valida": False, "motivos": ["sem a geometria de Interlagos para conferir"], "box": None,
                          "tempoS": None, "duracaoS": None, "grade": {}, "pontosDaGrade": 0})
        elif not str(self.pista or PISTA_ESPERADA).startswith(PISTA_ESPERADA):
            volta.update({"valida": False, "motivos": [f"pista {self.pista}: o ML só lê Interlagos"], "box": None,
                          "tempoS": None, "duracaoS": None, "grade": {}, "pontosDaGrade": 0})
        else:
            try:
                volta.update(avaliar_volta(frame, self.geometria))
            except Exception as error:  # uma volta estranha nao derruba a conferencia
                logger.warning("Conferencia da volta %s falhou: %s", lap_id, error)
                volta.update({"valida": False, "motivos": [f"erro na conferência: {error}"], "box": None,
                              "tempoS": None, "duracaoS": None, "grade": {}, "pontosDaGrade": 0})
        volta["tempo"] = formatar_tempo(volta.get("tempoS"))
        volta["duracao"] = formatar_tempo(volta.get("duracaoS"))
        volta["entraNoStore"] = bool(volta["valida"] and not volta["box"])
        if volta["box"]:
            volta["motivos"] = list(volta["motivos"]) + ["passou pelo box"]
        self.voltas.append(volta)
        self.segundos_de_conferencia += time.perf_counter() - inicio

    # --------------------------------------------------------- resultado ---

    def veredito(self) -> Dict[str, Any]:
        pontos = int(self.geometria.track.size) if self.geometria is not None else 0
        return veredito_m1(self.voltas, pontos, self.final)

    def to_api(self) -> Dict[str, Any]:
        meta = self.metadata.get("metadata") if isinstance(self.metadata.get("metadata"), Mapping) else {}
        return {
            "formato": FORMATO,
            "sessao": self.session_id,
            "pasta": str(self.diretorio),
            "final": self.final,
            "atualizadoEm": datetime.now().isoformat(timespec="seconds"),
            "pista": self.pista,
            "gravacao": {
                "carModel": meta.get("carModel"),
                "appVersion": meta.get("appVersion"),
                "appCommit": meta.get("appCommit"),
                "inicio": self.metadata.get("startedAt"),
                "fim": self.metadata.get("endedAt"),
            },
            "geometria": self.geometria.to_api() if self.geometria is not None else None,
            "leitura": {"linhas": self.linhas, "corrompidas": self.corrompidas, "bytes": self.offset,
                        "segundosDeConferencia": round(self.segundos_de_conferencia, 2)},
            "voltaAberta": None if self.final else {
                "sequencia": self._sequence, "voltaDoJogo": self._lap_number, "amostras": len(self._rows)},
            "voltas": self.voltas,
            "veredito": self.veredito(),
        }


def conferir_sessao(diretorio: Path, geometria: Optional[Geometria]) -> ConferenciaSessao:
    """A sessao inteira de uma vez (sessao ja gravada)."""
    conferencia = ConferenciaSessao(diretorio, geometria)
    conferencia.concluir()
    return conferencia


def gravar(resultado: Dict[str, Any], pasta: Path) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{resultado['sessao']}.json"
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    os.replace(temporario, destino)
    return destino


# ------------------------------------------------------------- servico ---

class ServicoConferencia:
    """A conferencia da sessao que esta sendo gravada, e das que ja foram, sob pedido.

    `tick()` roda num thread a cada poucos segundos: le o que a gravacao em
    andamento cresceu, confere a volta que fechou e, quando a gravacao para,
    fecha a ultima volta e grava o resultado final. Sessoes ja gravadas sao
    conferidas sob pedido (`solicitar`), num thread cada.
    """

    def __init__(self, pasta_de_dados: Path, pasta_de_gravacoes: Path,
                 repositorio: Callable[[], Optional[Path]],
                 estado_da_gravacao: Callable[[], Mapping[str, Any]]):
        self.pasta_de_dados = Path(pasta_de_dados)
        self.pasta_de_gravacoes = Path(pasta_de_gravacoes)
        self.pasta = self.pasta_de_dados / PASTA_VERIFICACOES
        self.repositorio = repositorio
        self.estado_da_gravacao = estado_da_gravacao
        self._lock = threading.RLock()
        self._ao_vivo: Optional[ConferenciaSessao] = None
        self._voltas_gravadas = 0
        self._trabalhos: Dict[str, Dict[str, Any]] = {}

    # -------------------------------------------------------- caminhos ---

    def geometria(self) -> Optional[Geometria]:
        try:
            return carregar_geometria(candidatos_de_geometria(self.repositorio(), self.pasta_de_dados))
        except Exception as error:
            logger.warning("Geometria da conferencia indisponivel: %s", error)
            return None

    def pastas_de_gravacao(self) -> List[Tuple[Path, str]]:
        out = [(self.pasta_de_gravacoes, "pasta de dados do app")]
        repositorio = self.repositorio()
        if repositorio is not None:
            pasta = Path(repositorio) / "data" / "recordings"
            if pasta.resolve() != self.pasta_de_gravacoes.resolve():
                out.append((pasta, "repositório"))
        return out

    def achar_sessao(self, session_id: str) -> Optional[Path]:
        if not session_id or "/" in session_id or "\\" in session_id or session_id.startswith("."):
            return None
        for pasta, _ in self.pastas_de_gravacao():
            candidato = pasta / session_id
            if (candidato / PLAYER_STREAM).exists():
                return candidato
        return None

    # --------------------------------------------------------- ao vivo ---

    def tick(self) -> None:
        estado = dict(self.estado_da_gravacao() or {})
        gravando = bool(estado.get("recording"))
        diretorio = estado.get("directory")
        with self._lock:
            atual = self._ao_vivo
            if atual is not None and (not gravando or not diretorio or Path(diretorio) != atual.diretorio):
                if not atual.final:
                    atual.concluir()
                    self._gravar(atual)
                atual = None
                self._ao_vivo = None
            if gravando and diretorio:
                if atual is None:
                    atual = ConferenciaSessao(Path(diretorio), self.geometria())
                    self._ao_vivo = atual
                    self._voltas_gravadas = 0
                atual.ler()
                if len(atual.voltas) != self._voltas_gravadas:
                    self._voltas_gravadas = len(atual.voltas)
                    self._gravar(atual)

    def finalizar(self) -> None:
        """O backend vai fechar: conclui a sessao em andamento, se houver."""
        with self._lock:
            atual = self._ao_vivo
            if atual is not None and not atual.final:
                atual.concluir()
                self._gravar(atual)
            self._ao_vivo = None

    def sessao_atual(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            atual = self._ao_vivo
            return atual.to_api() if atual is not None else None

    # ----------------------------------------------------- sob pedido ---

    def solicitar(self, session_id: str) -> Dict[str, Any]:
        diretorio = self.achar_sessao(session_id)
        if diretorio is None:
            return {"estado": "nao_encontrada", "sessao": session_id}
        with self._lock:
            if self._ao_vivo is not None and self._ao_vivo.session_id == session_id:
                return {"estado": "gravando", "sessao": session_id}
            trabalho = self._trabalhos.get(session_id)
            if trabalho is not None and trabalho["estado"] == "conferindo":
                return dict(trabalho, conferencia=None)
            trabalho = {"estado": "conferindo", "sessao": session_id, "inicio": time.time(), "erro": None,
                        "conferencia": None}
            self._trabalhos[session_id] = trabalho

        def rodar():
            try:
                conferencia = ConferenciaSessao(diretorio, self.geometria())
                trabalho["conferencia"] = conferencia
                conferencia.concluir()
                self._gravar(conferencia)
                trabalho["estado"] = "pronta"
            except Exception as error:  # pragma: no cover - relatado na aba
                logger.exception("Conferencia de %s falhou", session_id)
                trabalho["estado"] = "erro"
                trabalho["erro"] = str(error)

        threading.Thread(target=rodar, name=f"conferencia-{session_id}", daemon=True).start()
        return {"estado": "conferindo", "sessao": session_id}

    def estado(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            if self._ao_vivo is not None and self._ao_vivo.session_id == session_id:
                return {"estado": "gravando", "sessao": session_id, "resultado": self._ao_vivo.to_api()}
            trabalho = self._trabalhos.get(session_id)
        if trabalho is not None and trabalho["estado"] == "conferindo":
            conferencia = trabalho.get("conferencia")
            progresso = None
            if conferencia is not None:
                try:
                    total = (conferencia.diretorio / PLAYER_STREAM).stat().st_size
                    progresso = round(conferencia.offset / total, 4) if total else None
                except OSError:
                    pass
            return {"estado": "conferindo", "sessao": session_id, "progresso": progresso}
        if trabalho is not None and trabalho["estado"] == "erro":
            return {"estado": "erro", "sessao": session_id, "erro": trabalho["erro"]}
        salvo = self.ler_salvo(session_id)
        if salvo is not None:
            return {"estado": "pronta", "sessao": session_id, "resultado": salvo}
        return {"estado": "nao_conferida", "sessao": session_id}

    # -------------------------------------------------------- arquivos ---

    def _gravar(self, conferencia: ConferenciaSessao) -> None:
        try:
            gravar(conferencia.to_api(), self.pasta)
        except OSError as error:
            logger.warning("Nao foi possivel gravar a conferencia de %s: %s", conferencia.session_id, error)

    def ler_salvo(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not session_id or "/" in session_id or "\\" in session_id or session_id.startswith("."):
            return None
        try:
            return json.loads((self.pasta / f"{session_id}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def listar(self) -> List[Dict[str, Any]]:
        out = []
        if not self.pasta.exists():
            return out
        for arquivo in sorted(self.pasta.glob("*.json"), reverse=True):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            veredito = dados.get("veredito") or {}
            out.append({
                "sessao": dados.get("sessao"),
                "final": dados.get("final"),
                "atualizadoEm": dados.get("atualizadoEm"),
                "voltas": veredito.get("voltas"),
                "voltasValidas": veredito.get("voltasValidas"),
                "conta": veredito.get("conta"),
                "texto": veredito.get("texto"),
            })
        return out

    def pendentes(self) -> List[str]:
        """Conferencias gravadas pela metade (o app fechou durante a sessao)."""
        return [item["sessao"] for item in self.listar() if item.get("final") is False and item.get("sessao")]

    def concluir_pendentes(self) -> None:
        for session_id in self.pendentes():
            self.solicitar(session_id)
