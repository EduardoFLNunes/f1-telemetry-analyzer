"""A volta do modelo como referencia do app (pedido 51; ADR 0032).

A volta de referencia do app e a melhor volta valida de uma linha do projeto que
atingiu a meta do ADR 0031, dirigida no jogo pela IA na linha do projeto. Ela
nao e a gravacao: e um arquivo derivado dela (`ml.scripts.volta_do_modelo`), com
a grade de 2 m da geometria oficial (o tempo, a posicao, a velocidade, a marcha
e os pedais) e os alvos por microssetor no formato das referencias do modelo do
coach.

Este modulo so le o arquivo. Ele nao importa o `ml`, como o tracado otimo
(`optimal_line`): o backend empacotado le um JSON pequeno e mais nada.

Onde o arquivo fica: `data/reference_models/<pista>.volta_do_modelo.json`, fora
do git, como o modelo do coach. O instalador o leva para a pasta de recursos, e o
backend o procura na pasta do repositorio, na pasta de dados e na pasta de
recursos, nessa ordem (ADR 0032, Consequencias).

O formato dos pedais e o comando do controlador da IA, e nao a tecnica de um
piloto (ADR 0032, item 5): o arquivo leva os pedais para o desenho, e nenhum
leitor daqui os julga.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

FORMATO = "volta-do-modelo/1"
KIND = "volta_do_modelo"
LABEL = "volta de referência"
SEM_VOLTA_DO_MODELO = "A volta de referência desta pista ainda não foi gerada pelo modelo"


def caminho(raiz: Path, pista: str) -> Path:
    """Ao lado do modelo do coach, com o mesmo saneamento do nome."""
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in (pista or "unknown"))
    return Path(raiz) / "data" / "reference_models" / f"{safe}.volta_do_modelo.json"


def ler(arquivo: Path) -> Optional[Dict[str, Any]]:
    """O arquivo, se existir e for do formato; senao None (um arquivo ruim nao derruba o app)."""
    arquivo = Path(arquivo)
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        logger.warning("Volta do modelo ilegivel em %s: %s", arquivo, erro)
        return None
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO:
        logger.warning("Volta do modelo em %s sem o formato %s", arquivo, FORMATO)
        return None
    dados["_arquivo"] = str(arquivo)
    return dados


def encontrar(raizes: Iterable[Optional[Path]], pista: str) -> Optional[Dict[str, Any]]:
    """A primeira volta do modelo da pista, nas raizes em ordem."""
    for raiz in raizes:
        if raiz is None:
            continue
        dados = ler(caminho(Path(raiz), pista))
        if dados is not None:
            return dados
    return None


def referencia(dados: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A referencia `volta_do_modelo` no formato de `DriverReferenceModel.references`."""
    ref = dados.get("referencia") if isinstance(dados, dict) else None
    if not isinstance(ref, dict) or not ref.get("sectors"):
        return None
    out = dict(ref)
    out["kind"] = KIND
    out["label"] = LABEL
    out.setdefault("lap_id", dados.get("lap_id"))
    out.setdefault("carro", dados.get("carro"))
    out["geometry_id"] = dados.get("geometry_id")
    out["origem"] = "volta do modelo (ADR 0032)"
    out["marca"] = dados.get("marca")
    out["arquivo"] = dados.get("_arquivo")
    return out


def anexar(modelo: Any, dados: Optional[Dict[str, Any]]) -> bool:
    """Poe a volta do modelo no modelo do coach, se ele ainda nao a tiver e a geometria for a mesma.

    O `atualizar_coach` ja grava a referencia no modelo; isto cobre o modelo
    gravado antes da 0.8.0, que o app instalado le da pasta do repositorio.
    """
    if modelo is None or dados is None:
        return False
    refs = getattr(modelo, "references", None)
    if refs is None or refs.get(KIND):
        return False
    geometria = getattr(modelo, "geometry_id", None)
    if geometria and dados.get("geometry_id") and geometria != dados.get("geometry_id"):
        logger.warning("Volta do modelo em outra geometria (%s, o modelo e %s): fora", dados.get("geometry_id"), geometria)
        return False
    ref = referencia(dados)
    if ref is None:
        return False
    refs[KIND] = ref
    return True


def _numeros(valores: Optional[List[Any]], casas: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for v in valores or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(round(f, casas) if f == f else None)
    return out


def como_volta_do_store(dados: Dict[str, Any]) -> Dict[str, Any]:
    """A grade no formato de `LeitorDoStore.ler_volta`: o fantasma, o radio e a tela Volta leem igual."""
    grade = dados.get("grade") or {}
    origem = dados.get("origem") or {}
    n = int(grade.get("pontos") or len(grade.get("elapsed_s") or []))
    comprimento = float(grade.get("comprimento_m") or 0.0)
    return {
        "disponivel": True,
        "lapId": dados.get("lap_id"),
        "gravacao": origem.get("sessao"),
        "sequencia": origem.get("sequencia"),
        "voltaDoJogo": origem.get("volta_do_jogo"),
        "replayLapId": None,
        "tempoS": dados.get("tempo_s"),
        "origem": KIND,
        "voltaDoModelo": True,
        "rotulo": "Volta de referência",
        "marca": dados.get("marca"),
        "carro": dados.get("carro"),
        "geometryId": dados.get("geometry_id"),
        "pontosDaGrade": n,
        "comprimentoM": comprimento,
        "passoM": comprimento / n if n else None,
        "gridIndex": list(range(n)),
        "elapsedS": _numeros(grade.get("elapsed_s"), 6),
        "velocidadeKmh": _numeros(grade.get("speed_kmh"), 3),
        "acelerador": _numeros(grade.get("throttle"), 4),
        "freio": _numeros(grade.get("brake"), 4),
        "lateralM": _numeros(grade.get("lateral"), 4),
        "marcha": _numeros(grade.get("gear"), 0),
    }
