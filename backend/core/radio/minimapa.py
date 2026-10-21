"""O que o minimapa do app do jogo baixa do backend (pedido 35, Parte E; ADR 0021, item 5).

Uma vez, quando o app abre ou a referencia muda (`versao`):

* **a pista tratada:** as duas bordas do asfalto da geometria oficial (centro mais e
  menos a largura, pela normal), simplificadas para `PONTOS_DA_BORDA` pontos cada;
* **a volta de referencia escolhida na Coleta:** a posicao (centro + normal x lateral,
  a mesma conta da tela Volta) e o tempo desde o s = 0, em `PONTOS_DA_REFERENCIA` pontos;
* **o alinhamento dos relogios:** o cronometro do jogo zera na linha do jogo, a
  `linhaDoJogoM` depois do s = 0 (pedido 33; a medida do store, pedido 34). O tempo da
  referencia nesse ponto (`tempoNaLinhaDoJogoS`) e somado ao cronometro do jogo para
  achar o fantasma: tempo da referencia = cronometro do jogo + tempoNaLinhaDoJogoS;
* **as curvas da ultima analise,** com a posicao do apice.

A posicao do carro nao vem daqui: o app le do proprio jogo, a cada quadro.
As coordenadas sao as do mundo do jogo (x, z), as mesmas da projecao do coach.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PONTOS_DA_BORDA = 300
PONTOS_DA_REFERENCIA = 400
LINHA_DO_JOGO_REGISTRADA_M = 1.463   # pedido 33; vale a medida do store, se houver


def _decimar(n: int, alvo: int) -> np.ndarray:
    passo = max(1, int(math.ceil(n / alvo)))
    return np.arange(0, n, passo)


def linha_do_jogo_m(repositorio: Optional[Path]) -> float:
    """A distancia do s = 0 a linha do jogo medida no store v2 (pedido 34), ou a registrada."""
    try:
        meta = json.loads((Path(repositorio) / "data" / "ml" / "laps_grid_v2_meta.json").read_text(encoding="utf-8"))
        valor = meta["checagens"]["principal_periodo"]["linha_do_jogo_m"]
        return float(valor) if valor is not None else LINHA_DO_JOGO_REGISTRADA_M
    except Exception:
        return LINHA_DO_JOGO_REGISTRADA_M


def montar(track: Any, segmentos: List[Any], referencia: Optional[Dict[str, Any]], tipo: Optional[str],
           analise: Optional[Dict[str, Any]], linha_m: float) -> Dict[str, Any]:
    x, z = np.asarray(track.x, dtype=float), np.asarray(track.z, dtype=float)
    normal = np.asarray(track.normal, dtype=float)
    wl, wr = np.asarray(track.width_left, dtype=float), np.asarray(track.width_right, dtype=float)
    k = _decimar(int(track.size), PONTOS_DA_BORDA)
    esquerda = np.column_stack([x[k] + normal[k, 0] * wl[k], z[k] + normal[k, 1] * wl[k]])
    direita = np.column_stack([x[k] - normal[k, 0] * wr[k], z[k] - normal[k, 1] * wr[k]])
    out: Dict[str, Any] = {
        "disponivel": True,
        "comprimentoM": round(float(track.length), 2),
        "pista": {"esquerda": np.round(esquerda, 2).tolist(), "direita": np.round(direita, 2).tolist()},
        "linhaDoJogoM": round(float(linha_m), 3),
        "referencia": None,
        "curvasDaAnalise": [],
    }
    if referencia and referencia.get("disponivel", True) and referencia.get("elapsedS"):
        el = np.array([np.nan if v is None else float(v) for v in referencia["elapsedS"]], dtype=float)
        lat = np.array([np.nan if v is None else float(v) for v in referencia.get("lateralM") or []], dtype=float)
        if el.size == track.size and lat.size == track.size and np.isfinite(el).sum() > track.size // 2:
            idx = np.arange(el.size)
            ok = np.isfinite(el)
            el = np.interp(idx, idx[ok], el[ok])
            lat = np.interp(idx, idx[np.isfinite(lat)], lat[np.isfinite(lat)])
            px, pz = x + normal[:, 0] * lat, z + normal[:, 1] * lat
            r = _decimar(el.size, PONTOS_DA_REFERENCIA)
            total = float(referencia.get("tempoS") or el[-1])
            na_linha = float(np.interp(linha_m, np.asarray(track.s, dtype=float), el))
            out["referencia"] = {
                "tipo": tipo,
                "lapId": referencia.get("lapId"),
                "tempoS": round(total, 3),
                "tempoNaLinhaDoJogoS": round(na_linha, 4),
                # [x, z, tempo desde o s = 0]
                "pontos": np.round(np.column_stack([px[r], pz[r], el[r]]), 3).tolist(),
            }
    codigos = {seg.corner.label[:3]: seg.corner for seg in segmentos}
    for c in (analise or {}).get("curvas") or []:
        corner = codigos.get(c.get("curva"))
        if corner is None:
            continue
        i = int(track.index_of(corner.apex_s))
        out["curvasDaAnalise"].append({"curva": c["curva"], "x": round(float(x[i]), 2), "z": round(float(z[i]), 2),
                                       "perdaMedianaS": c.get("perdaMedianaS")})
    voltas = (analise or {}).get("voltas") or []
    ref = out["referencia"] or {}
    out["versao"] = f"{tipo}|{ref.get('lapId')}|{'-'.join(str(v) for v in voltas)}"
    return out
