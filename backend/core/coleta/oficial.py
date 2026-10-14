"""A contagem oficial da M1, lida do store v2 (pedido 28, Parte D.3).

A regra e a da secao 6 de `docs/modelo_fisico_m0.md`, a mesma da previa da aba
(`core.coleta.conferencia.veredito_m1`), aplicada ao store v2 que o
`atualizar_coach` refaz:

* uma sessao e humana quando todas as voltas dela no store tem `origem` igual a
  `humano` (o rotulo final do store, venha ele do indicador ou de anotacao);
* ela conta quando a guinada e as velocidades no referencial do carro estao em
  pelo menos 95% dos pontos da grade das voltas dela no store.

So le `data/ml/laps_grid_v2.parquet` (as colunas da regra) e o meta. O nome dos
arquivos e o de `ml.data.store_v2`, que nao e importado aqui porque puxa o
torch; um teste confere os nomes.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .requisitos import COLUNAS_M1, NOME_M1, PREENCHIMENTO_M1, SESSOES_M1

STORE_V2_FILENAME = "laps_grid_v2.parquet"
STORE_V2_METADATA = "laps_grid_v2_meta.json"
HUMANO = "humano"

_cache: Dict[Tuple[str, float, int, float], Dict[str, Any]] = {}
_lock = threading.Lock()


def _arquivos(repositorio: Path) -> Tuple[Path, Path]:
    pasta = Path(repositorio) / "data" / "ml"
    return pasta / STORE_V2_FILENAME, pasta / STORE_V2_METADATA


def contagem_oficial(repositorio: Optional[Path]) -> Dict[str, Any]:
    if repositorio is None:
        return {"disponivel": False, "motivo": "o caminho do repositório não está configurado"}
    parquet, meta_path = _arquivos(repositorio)
    if not parquet.exists() or not meta_path.exists():
        return {"disponivel": False, "motivo": f"store v2 não encontrado em {parquet.parent}"}
    info, info_meta = parquet.stat(), meta_path.stat()
    chave = (str(parquet), info.st_mtime, info.st_size, info_meta.st_mtime)
    with _lock:
        if chave in _cache:
            return dict(_cache[chave])
    resultado = _contar(parquet, meta_path)
    with _lock:
        _cache.clear()
        _cache[chave] = resultado
    return dict(resultado)


def _contar(parquet: Path, meta_path: Path) -> Dict[str, Any]:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    voltas = pd.DataFrame(meta.get("laps") or [])
    grade = int(meta.get("grid_size") or 0)
    if voltas.empty or not grade:
        return {"disponivel": False, "motivo": "o store v2 não tem voltas"}
    colunas = [c for c in COLUNAS_M1 if c in (meta.get("columns") or [])]
    frame = pd.read_parquet(parquet, columns=["lap_id", *colunas])
    preenchidos = frame.groupby("lap_id")[colunas].count() if colunas else pd.DataFrame(index=voltas["lap_id"])

    sessoes = []
    for session_id, grupo in voltas.groupby("session_id", sort=True):
        ids = grupo["lap_id"].tolist()
        origens = grupo["origem"].fillna("desconhecida").tolist() if "origem" in grupo else []
        fontes = sorted({str(f) for f in grupo.get("origem_fonte", pd.Series(dtype=object)).dropna()})
        humana = bool(origens) and all(o == HUMANO for o in origens)
        if not any(o == HUMANO for o in origens):
            continue
        total = len(ids) * grade
        preenchimento = {}
        for coluna in COLUNAS_M1:
            if coluna in preenchidos.columns:
                preenchimento[coluna] = float(preenchidos.reindex(ids)[coluna].fillna(0).sum()) / total
            else:
                preenchimento[coluna] = 0.0
        faltando = [c for c in COLUNAS_M1 if preenchimento[c] < PREENCHIMENTO_M1]
        motivos = []
        if not humana:
            motivos.append("tem voltas que não são suas no store")
        if faltando:
            motivos.append("abaixo de 95%: " + ", ".join(NOME_M1[c] for c in faltando))
        sessoes.append({
            "sessao": session_id,
            "voltasNoStore": len(ids),
            "origens": {o: origens.count(o) for o in sorted(set(origens))},
            "fontesDaOrigem": fontes,
            "humana": humana,
            "preenchimentoGrade": {k: round(v, 4) for k, v in preenchimento.items()},
            "conta": humana and not faltando,
            "motivos": motivos,
        })
    contam = [s for s in sessoes if s["conta"]]
    return {
        "disponivel": True,
        "n": len(contam),
        "meta": SESSOES_M1,
        "texto": f"{len(contam)} de {SESSOES_M1}",
        "sessoesQueContam": [s["sessao"] for s in contam],
        "sessoesComVoltasSuas": sessoes,
        "store": {
            "arquivo": str(parquet),
            "construidoEm": meta.get("construido_em"),
            "commit": meta.get("commit"),
            "esquema": meta.get("esquema"),
            "voltas": int(len(voltas)),
        },
        "regra": "sessões com todas as voltas do store como suas (origem humano) e a guinada e as velocidades "
                 "no referencial do carro em pelo menos 95% dos pontos da grade",
    }
