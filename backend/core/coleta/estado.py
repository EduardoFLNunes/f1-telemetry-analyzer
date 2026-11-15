"""O que a aba mostra antes de pilotar: disco, carro e pista, e o coach (pedido 28, Parte D.1)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from ..assisted_analysis.official_geometry import geometry_path
from ..assisted_analysis.reference_model import DriverReferenceModel, model_path
from .configuracao import CHOICE_LABELS, COACH_OFF, AppConfig
from .requisitos import CARRO_ESPERADO, ESPACO_AMARELO_GB, ESPACO_VERMELHO_GB, PISTA_ESPERADA

GB = 1024 ** 3
STORE_V2_META = Path("data") / "ml" / "laps_grid_v2_meta.json"
_tempos_do_store: Dict[str, Any] = {"chave": None, "tempos": {}}


_melhor_do_store: Dict[str, Any] = {}


def tempos_do_store(raiz: Optional[Path]) -> Dict[str, float]:
    """`lap_time_s` de cada volta do store v2 (pedido 31, A.3: uma fonte para cada numero).

    O hero e a tela Volta mostram o mesmo tempo para a mesma volta: o do store v2
    e do relatorio de evolucao, e nao o do modelo do coach, que mede a volta a
    sua maneira (1 ms de diferenca). Guardado pela data do arquivo.
    """
    if raiz is None:
        return {}
    arquivo = Path(raiz) / STORE_V2_META
    try:
        info = arquivo.stat()
    except OSError:
        return {}
    chave = (str(arquivo), info.st_mtime, info.st_size)
    if _tempos_do_store["chave"] != chave:
        try:
            meta = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        _tempos_do_store["tempos"] = {
            str(v.get("lap_id")): float(v["lap_time_s"]) for v in meta.get("laps") or []
            if v.get("lap_id") and v.get("lap_time_s") is not None
        }
        _tempos_do_store["chave"] = chave
    return _tempos_do_store["tempos"]


def melhor_do_store(raiz: Optional[Path], pista: Optional[str], carro: Optional[str]) -> Optional[float]:
    """Pedido 45 (C.1): a melhor volta humana de todas as sessoes do store, para o carro e a pista; None
    sem o carro (as voltas antigas nao dizem qual era) ou sem voltas dele. So leitura."""
    if raiz is None or not pista or not carro:
        return None
    arquivo = Path(raiz) / STORE_V2_META
    try:
        info = arquivo.stat()
    except OSError:
        return None
    chave = (str(arquivo), info.st_mtime, info.st_size, pista, carro)
    if _melhor_do_store.get("chave") != chave:
        try:
            meta = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        tempos = [float(v["lap_time_s"]) for v in meta.get("laps") or []
                  if v.get("track") == pista and v.get("carModel") == carro and v.get("origem") == "humano"
                  and v.get("lap_time_s") is not None]
        _melhor_do_store.update(chave=chave, tempo=min(tempos) if tempos else None)
    return _melhor_do_store.get("tempo")


def volta_no_store(raiz: Optional[Path], sessao: Optional[str], tempo_s: Optional[float]) -> Optional[Dict[str, Any]]:
    """Pedido 45 (E.6): a volta da sessao ja no store, pelo tempo (os numeros so cruzam pelo tempo, +-0,15 s),
    com o numero do jogo (`game_lap_number`). None enquanto a sessao nao entrou no store."""
    if raiz is None or not sessao or tempo_s is None:
        return None
    arquivo = Path(raiz) / STORE_V2_META
    try:
        meta = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    candidatas = [v for v in meta.get("laps") or [] if v.get("session_id") == sessao and v.get("lap_time_s") is not None
                  and abs(float(v["lap_time_s"]) - float(tempo_s)) <= 0.15]
    if not candidatas:
        return None
    v = min(candidatas, key=lambda x: abs(float(x["lap_time_s"]) - float(tempo_s)))
    return {"lapId": v.get("lap_id"), "numero": v.get("game_lap_number")}


def numeros_do_store(raiz: Optional[Path]) -> Dict[str, int]:
    """Pedido 45 (B.2): o numero do jogo de cada volta do store, para a tela Volta mostrar o mesmo
    numero do radio. O id do store (`#NNNN`) e a ordem no arquivo, e nao o numero da volta."""
    if raiz is None:
        return {}
    try:
        meta = json.loads((Path(raiz) / STORE_V2_META).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(v["lap_id"]): int(v["game_lap_number"]) for v in meta.get("laps") or []
            if v.get("lap_id") and v.get("game_lap_number") is not None}


def espaco_em_disco(pasta: Path) -> Dict[str, Any]:
    """Espaco livre no disco da pasta (ou da primeira pasta acima dela que existir)."""
    alvo = Path(pasta)
    while not alvo.exists() and alvo.parent != alvo:
        alvo = alvo.parent
    try:
        uso = shutil.disk_usage(alvo)
    except OSError as error:
        return {"pasta": str(pasta), "livreGb": None, "totalGb": None, "nivel": "desconhecido", "erro": str(error)}
    livre = uso.free / GB
    nivel = "vermelho" if livre < ESPACO_VERMELHO_GB else "amarelo" if livre < ESPACO_AMARELO_GB else "ok"
    return {
        "pasta": str(pasta),
        "disco": str(Path(alvo).anchor or alvo),
        "livreGb": round(livre, 2),
        "totalGb": round(uso.total / GB, 2),
        "nivel": nivel,
        "limites": {"amareloGb": ESPACO_AMARELO_GB, "vermelhoGb": ESPACO_VERMELHO_GB},
    }


def carro_e_pista(carro: Optional[str], pista: Optional[str]) -> Dict[str, Any]:
    avisos = []
    if carro and carro != CARRO_ESPERADO:
        avisos.append(f"O carro detectado é {carro}, não o {CARRO_ESPERADO}.")
    if pista and not str(pista).startswith(PISTA_ESPERADA):
        avisos.append(f"A pista detectada é {pista}, não {PISTA_ESPERADA}. O ML só lê Interlagos.")
    return {
        "carro": carro or None,
        "pista": pista or None,
        "carroEsperado": CARRO_ESPERADO,
        "pistaEsperada": PISTA_ESPERADA,
        "carroBate": None if not carro else carro == CARRO_ESPERADO,
        "pistaBate": None if not pista else str(pista).startswith(PISTA_ESPERADA),
        "avisos": avisos,
    }


def estado_do_coach(service: Any, config: AppConfig, pista: str = PISTA_ESPERADA) -> Dict[str, Any]:
    """A referencia escolhida, se o modelo e a geometria foram achados, se o `geometry_id` bate.

    Le pelo mesmo servico que alimenta o coach ao vivo, e diz por que ele fica
    calado quando fica.
    """
    escolha, fonte = config.reference()
    raiz = config.coach_root()
    arquivo_modelo = model_path(raiz, pista) if raiz else None
    arquivo_geometria = geometry_path(raiz, pista) if raiz else None
    # O modelo e lido mesmo com o coach desligado, so para dizer o que tem nele.
    modelo = DriverReferenceModel.load(arquivo_modelo) if arquivo_modelo else None
    geometria = service._official_geometry(pista)  # noqa: SLF001
    ativo_modelo = service._reference_model(pista)  # noqa: SLF001

    motivo = None
    if escolha == COACH_OFF:
        motivo = "o coach está desligado na configuração"
    elif raiz is None:
        motivo = "o caminho do repositório não está configurado"
    elif not raiz.is_dir():
        motivo = f"a pasta {raiz} não existe"
    elif modelo is None:
        motivo = f"o modelo não foi encontrado em {arquivo_modelo}"
    elif not modelo.targets:
        motivo = "o modelo não tem microssetores"
    elif modelo.geometry_id and geometria is None:
        motivo = f"a geometria oficial não foi encontrada em {arquivo_geometria}"
    elif modelo.geometry_id and geometria is not None and geometria.geometry_id != modelo.geometry_id:
        motivo = (f"o modelo foi medido na geometria {modelo.geometry_id}, "
                  f"e a geometria do repositório é {geometria.geometry_id}")
    elif ativo_modelo is None or not getattr(ativo_modelo, "has_reference", False):
        motivo = f"o modelo não tem a referência {CHOICE_LABELS.get(escolha, escolha)}"

    referencias = {}
    if modelo is not None:
        for kind, ref in (modelo.references or {}).items():
            referencias[kind] = {"volta": ref.get("lap_id"), "tempoS": ref.get("lap_seconds"),
                                 "tempoStoreS": tempos_do_store(raiz).get(str(ref.get("lap_id"))),
                                 "carro": ref.get("carro")}
    return {
        "ativo": motivo is None,
        "motivoCalado": motivo,
        "referencia": escolha,
        "referenciaRotulo": CHOICE_LABELS.get(escolha, escolha),
        "referenciaFonte": fonte,
        "repositorio": str(raiz) if raiz else None,
        "modelo": {
            "arquivo": str(arquivo_modelo) if arquivo_modelo else None,
            "encontrado": modelo is not None,
            "construidoEm": getattr(modelo, "built_at", None),
            "voltasSuas": getattr(modelo, "lap_count", None),
            "geometryId": getattr(modelo, "geometry_id", None),
            "referencias": referencias,
        },
        "geometria": {
            "arquivo": str(arquivo_geometria) if arquivo_geometria else None,
            "encontrada": geometria is not None,
            "geometryId": getattr(geometria, "geometry_id", None),
        },
        "geometryIdBate": (None if modelo is None or geometria is None or not modelo.geometry_id
                           else geometria.geometry_id == modelo.geometry_id),
    }
