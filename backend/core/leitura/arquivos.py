"""As telas Sessoes, Volta e Evolucao leem o que o `atualizar_coach` ja gravou (pedido 30).

Nada aqui calcula um numero novo. Cada funcao le um arquivo que ja existe na
pasta do repositorio configurada na Coleta de dados (pedido 28) e o devolve
como esta, ou recortado:

* `data/ml/evolucao/resumo.json` e `sessao_*.json` -- o relatorio de evolucao;
* `data/ml/laps_grid_v2.parquet` e o meta -- as linhas de uma volta no store v2;
* `data/reference_models/vhe_interlagos.json` -- o modelo do coach, para saber
  qual volta e cada referencia;
* `data/reference_models/vhe_interlagos.geometry.json` -- a geometria oficial
  exportada (linha central, normais e bordas dos 60 microsetores).

A altitude e as larguras do relevo nao estao na geometria exportada. Elas vem
do mesmo carregador que o ML usa (`ml.track.geometry.load_geometry`), lendo o
cache da pista do repositorio, e so entram se o `geometry_id` for o mesmo.
"""

from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

PISTA = "vhe_interlagos"
CACHE_DA_PISTA = "vhe_interlagos_gp_kn5_surface_interval_geometry.json"
STORE_V2 = "laps_grid_v2.parquet"
STORE_V2_META = "laps_grid_v2_meta.json"
COLUNAS_DA_VOLTA = ("grid_index", "elapsed_s", "speed_kmh", "throttle", "brake", "lateral")

SESSAO = re.compile(r"^\d{4}-\d{2}-\d{2}(-\d+)?$")
VOLTA = re.compile(r"^[A-Za-z0-9_.-]+#\d{4}$")


def _ler_json(caminho: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _numeros(valores, casas: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for v in valores:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(round(f, casas) if f == f else None)
    return out


# ------------------------------------------------------------ evolucao ---

def pasta_da_evolucao(raiz: Path) -> Path:
    return Path(raiz) / "data" / "ml" / "evolucao"


def ler_resumo(raiz: Optional[Path]) -> Dict[str, Any]:
    """O `resumo.json` como esta, e as sessoes que tem arquivo."""
    if raiz is None:
        return {"disponivel": False, "motivo": "o repositório não está configurado na Coleta de dados"}
    pasta = pasta_da_evolucao(raiz)
    resumo = _ler_json(pasta / "resumo.json")
    if resumo is None:
        return {"disponivel": False, "motivo": f"o relatório de evolução não foi encontrado em {pasta}",
                "pasta": str(pasta)}
    sessoes = sorted(p.stem[len("sessao_"):] for p in pasta.glob("sessao_*.json") if SESSAO.match(p.stem[len("sessao_"):]))
    return {"disponivel": True, "pasta": str(pasta), "arquivosDeSessao": sessoes, "resumo": resumo}


def ler_sessao(raiz: Optional[Path], sessao: str) -> Dict[str, Any]:
    """O `sessao_<sessao>.json` como esta."""
    if not SESSAO.match(str(sessao or "")):
        return {"disponivel": False, "motivo": f"nome de sessão inválido: {sessao!r}"}
    if raiz is None:
        return {"disponivel": False, "motivo": "o repositório não está configurado na Coleta de dados"}
    caminho = pasta_da_evolucao(raiz) / f"sessao_{sessao}.json"
    dados = _ler_json(caminho)
    if dados is None:
        return {"disponivel": False, "motivo": f"a sessão {sessao} não está no relatório de evolução",
                "arquivo": str(caminho)}
    return {"disponivel": True, "arquivo": str(caminho), "sessao": dados}


# ------------------------------------------------------- referencias ---

def ler_referencias(raiz: Optional[Path], pista: str = PISTA) -> Dict[str, Any]:
    """Qual volta e cada referencia do coach, lido do modelo do repositorio."""
    if raiz is None:
        return {"disponivel": False, "motivo": "o repositório não está configurado na Coleta de dados"}
    caminho = Path(raiz) / "data" / "reference_models" / f"{pista}.json"
    modelo = _ler_json(caminho)
    if modelo is None:
        return {"disponivel": False, "motivo": f"o modelo do coach não foi encontrado em {caminho}", "arquivo": str(caminho)}
    referencias = {}
    for tipo, ref in (modelo.get("references") or {}).items():
        if isinstance(ref, dict):
            referencias[tipo] = {"volta": ref.get("lap_id"), "tempoS": ref.get("lap_seconds"), "carro": ref.get("carro")}
    return {
        "disponivel": True,
        "arquivo": str(caminho),
        "geometryId": modelo.get("geometry_id"),
        "construidoEm": modelo.get("built_at"),
        "voltasSuas": modelo.get("lap_count"),
        "referencias": referencias,
    }


# ------------------------------------------------------------ store v2 ---

class LeitorDoStore:
    """Linhas de uma volta do store v2, com as ultimas voltas lidas guardadas.

    O parquet tem todas as voltas (cerca de 330 MB); o filtro por `lap_id` le
    uma volta em cerca de 1 s. As ultimas `capacidade` voltas ficam em memoria,
    invalidadas quando o arquivo muda.
    """

    def __init__(self, capacidade: int = 24) -> None:
        self.capacidade = capacidade
        self._voltas: "OrderedDict[tuple, Dict[str, Any]]" = OrderedDict()
        self._metas: Dict[tuple, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _assinatura(caminho: Path) -> tuple:
        info = caminho.stat()
        return (str(caminho), info.st_mtime, info.st_size)

    def _meta(self, raiz: Path) -> Optional[Dict[str, Any]]:
        caminho = Path(raiz) / "data" / "ml" / STORE_V2_META
        try:
            chave = self._assinatura(caminho)
        except OSError:
            return None
        with self._lock:
            if chave in self._metas:
                return self._metas[chave]
        meta = _ler_json(caminho)
        if meta is None:
            return None
        resumo = {
            "geometry_id": meta.get("geometry_id"),
            "grid_size": meta.get("grid_size"),
            "track_length": meta.get("track_length"),
            "aprovado": meta.get("aprovado"),
            "voltas": {lap["lap_id"]: lap for lap in meta.get("laps") or [] if isinstance(lap, dict) and lap.get("lap_id")},
        }
        with self._lock:
            self._metas = {chave: resumo}
        return resumo

    def ler_volta(self, raiz: Optional[Path], lap_id: str) -> Dict[str, Any]:
        if not VOLTA.match(str(lap_id or "")):
            return {"disponivel": False, "motivo": f"id de volta inválido: {lap_id!r}"}
        if raiz is None:
            return {"disponivel": False, "motivo": "o repositório não está configurado na Coleta de dados"}
        parquet = Path(raiz) / "data" / "ml" / STORE_V2
        meta = self._meta(raiz)
        if meta is None or not parquet.exists():
            return {"disponivel": False, "motivo": f"o store v2 não foi encontrado em {parquet.parent}"}
        info = meta["voltas"].get(lap_id)
        if info is None:
            return {"disponivel": False, "motivo": f"a volta {lap_id} não está no store v2"}
        chave = (*self._assinatura(parquet), lap_id)
        with self._lock:
            if chave in self._voltas:
                self._voltas.move_to_end(chave)
                return self._voltas[chave]

        import pyarrow.parquet as pq

        tabela = pq.read_table(parquet, columns=["lap_id", *COLUNAS_DA_VOLTA], filters=[("lap_id", "==", lap_id)])
        linhas = tabela.drop(["lap_id"]).to_pydict()
        ordem = sorted(range(len(linhas["grid_index"])), key=lambda i: linhas["grid_index"][i])
        coluna = lambda nome: [linhas[nome][i] for i in ordem]  # noqa: E731
        grade = int(meta.get("grid_size") or 0)
        comprimento = float(meta.get("track_length") or 0.0)
        resposta = {
            "disponivel": True,
            "lapId": lap_id,
            "gravacao": info.get("session_id"),
            "sequencia": info.get("sequence"),
            "voltaDoJogo": info.get("game_lap_number"),
            "replayLapId": info.get("replay_lap_id"),
            "tempoS": info.get("lap_time_s"),
            "origem": info.get("origem"),
            "carro": info.get("carModel"),
            "geometryId": meta.get("geometry_id"),
            "pontosDaGrade": grade,
            "comprimentoM": comprimento,
            "passoM": comprimento / grade if grade else None,
            "gridIndex": [int(v) for v in coluna("grid_index")],
            "elapsedS": _numeros(coluna("elapsed_s"), 6),
            "velocidadeKmh": _numeros(coluna("speed_kmh"), 3),
            "acelerador": _numeros(coluna("throttle"), 4),
            "freio": _numeros(coluna("brake"), 4),
            "lateralM": _numeros(coluna("lateral"), 4),
        }
        with self._lock:
            self._voltas[chave] = resposta
            while len(self._voltas) > self.capacidade:
                self._voltas.popitem(last=False)
        return resposta


# ----------------------------------------------------------- geometria ---

_geometrias: Dict[tuple, Dict[str, Any]] = {}
_geometrias_lock = threading.Lock()


def ler_geometria(raiz: Optional[Path], pista: str = PISTA) -> Dict[str, Any]:
    """A geometria oficial exportada e, do carregador do ML, a altitude e as larguras."""
    if raiz is None:
        return {"disponivel": False, "motivo": "o repositório não está configurado na Coleta de dados"}
    exportada = Path(raiz) / "data" / "reference_models" / f"{pista}.geometry.json"
    cache = Path(raiz) / "data" / "cache" / "tracks" / CACHE_DA_PISTA
    try:
        chave = (str(exportada), exportada.stat().st_mtime, str(cache), cache.stat().st_mtime if cache.exists() else None)
    except OSError:
        return {"disponivel": False, "motivo": f"a geometria oficial não foi encontrada em {exportada}"}
    with _geometrias_lock:
        if chave in _geometrias:
            return _geometrias[chave]
    dados = _ler_json(exportada)
    if dados is None or not dados.get("geometry_id"):
        return {"disponivel": False, "motivo": f"a geometria oficial em {exportada} não pôde ser lida"}
    resposta: Dict[str, Any] = {
        "disponivel": True,
        "arquivo": str(exportada),
        "geometryId": dados["geometry_id"],
        "comprimentoM": dados.get("track_length"),
        "passoM": dados.get("step"),
        "x": _numeros(dados.get("x") or [], 3),
        "z": _numeros(dados.get("z") or [], 3),
        "normalX": _numeros(dados.get("normal_x") or [], 5),
        "normalZ": _numeros(dados.get("normal_z") or [], 5),
        "ladoDaNormal": dados.get("normal_side"),
        "bordasDosMicrossetores": _numeros(dados.get("microsector_edges") or [], 3),
        "elevacaoM": None,
        "larguraEsquerdaM": None,
        "larguraDireitaM": None,
        "relevo": None,
    }
    try:
        from ml.track.geometry import load_geometry

        trilha = load_geometry(cache)
        if trilha.geometry_id != dados["geometry_id"] or trilha.size != len(resposta["x"]):
            resposta["relevo"] = (f"o cache da pista ({trilha.geometry_id}) não é a geometria oficial "
                                  f"({dados['geometry_id']}); sem altitude e larguras")
        else:
            resposta["elevacaoM"] = _numeros(trilha.elevation, 3)
            resposta["larguraEsquerdaM"] = _numeros(trilha.width_left, 3)
            resposta["larguraDireitaM"] = _numeros(trilha.width_right, 3)
            resposta["relevo"] = f"altitude e larguras de {cache}"
    except (OSError, ValueError, KeyError) as erro:
        resposta["relevo"] = f"sem altitude e larguras: {erro}"
    with _geometrias_lock:
        _geometrias.clear()
        _geometrias[chave] = resposta
    return resposta
