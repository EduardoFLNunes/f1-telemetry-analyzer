"""O que o minimapa do app do jogo baixa do backend (pedido 35, Parte E; ADR 0021, item 5).

Uma vez, quando o app abre ou a referencia muda (`versao`):

* **a pista tratada:** o contorno do asfalto do cache da pista (`asphaltSurface.loops`,
  a mesma camada que o mapa do app e o mapa aproximado desenham), simplificado: os
  lacos com pelo menos `AREA_MINIMA_M2` (o contorno de fora, o buraco do miolo, as areas
  de escape e dos boxes) e cada laco pelo Douglas-Peucker com `TOLERANCIA_M` (363
  pontos em 12 lacos em Interlagos). As camadas do cache estao em (x, -z); aqui viram
  (x, z). Sem o cache, ficam as duas bordas da geometria oficial (centro mais e menos a
  largura), e `pista.origem` diz isso;
* **a linha do s = 0,** da geometria oficial, so como marca;
* **a volta de referencia escolhida na Coleta:** a posicao (centro + normal x lateral,
  a mesma conta da tela Volta), o tempo desde o s = 0 e o pedal, em todos os pontos da
  grade do store (2 m). O pedal e o da tela Volta: 2 = freio (0,15 ou mais), 1 =
  acelerador (0,9 ou mais), 0 = parcial ou sem pedal. O mapa aproximado do jogo pinta o
  tracado do fantasma com ele (pedido 35, depois do teste no jogo);
* **o alinhamento dos relogios:** o cronometro do jogo zera na linha do jogo, a
  `linhaDoJogoM` depois do s = 0 (pedido 33; a medida do store, pedido 34). O tempo da
  referencia nesse ponto (`tempoNaLinhaDoJogoS`) e somado ao cronometro do jogo para
  achar o fantasma: tempo da referencia = cronometro do jogo + tempoNaLinhaDoJogoS;
* **as curvas da ultima analise,** com a posicao do apice;
* **o nome das 14 curvas,** na mesma posicao da tela Volta (`rotuloDaCurva`): do lado de
  fora, a largura da pista mais 9 m do apice.

A posicao do carro nao vem daqui: o app le do proprio jogo, a cada quadro.
As coordenadas sao as do mundo do jogo (x, z), as mesmas da projecao do coach.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PONTOS_DA_BORDA = 300           # so sem o cache: as bordas da geometria oficial
AREA_MINIMA_M2 = 1000.0         # os lacos menores (ilhas de poucos metros) ficam de fora
TOLERANCIA_M = 2.0              # meio pixel no minimapa (cerca de 0,25 px por metro)
PONTOS_DA_REFERENCIA = 2200     # todos os pontos da grade do store (2.167 em Interlagos)
FOLGA_DO_ROTULO_M = 9.0         # o nome da curva, de fora, como na tela Volta
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


def _pedais(referencia: Dict[str, Any], n: int) -> np.ndarray:
    """O pedal de cada ponto, como na tela Volta: 2 = freio, 1 = acelerador cheio, 0 = parcial."""
    def serie(nome: str) -> np.ndarray:
        v = referencia.get(nome) or []
        a = np.array([np.nan if x is None else float(x) for x in v], dtype=float)
        return a if a.size == n else np.full(n, np.nan)

    freio, acelerador = serie("freio"), serie("acelerador")
    pedal = np.zeros(n, dtype=int)
    pedal[np.nan_to_num(acelerador, nan=0.0) >= 0.9] = 1
    pedal[np.nan_to_num(freio, nan=0.0) >= 0.15] = 2
    return pedal


def rotulos_das_curvas(track: Any, segmentos: List[Any]) -> List[Dict[str, Any]]:
    """Onde vai o nome de cada curva: do lado de fora, a largura mais `FOLGA_DO_ROTULO_M` do apice."""
    x, z = np.asarray(track.x, dtype=float), np.asarray(track.z, dtype=float)
    normal = np.asarray(track.normal, dtype=float)
    wl, wr = np.asarray(track.width_left, dtype=float), np.asarray(track.width_right, dtype=float)
    out = []
    for seg in segmentos:
        corner = seg.corner
        codigo, _, lado = corner.label.partition("-")
        i = int(track.index_of(corner.apex_s))
        fora = -1.0 if lado.startswith("esq") else 1.0   # a normal aponta para a esquerda (ADR 0003)
        w = (wl[i] if fora > 0 else wr[i]) + FOLGA_DO_ROTULO_M
        out.append({"curva": codigo, "lado": "esquerda" if fora < 0 else "direita",
                    "x": round(float(x[i] + fora * w * normal[i, 0]), 2),
                    "z": round(float(z[i] + fora * w * normal[i, 1]), 2)})
    return out


def _douglas_peucker(p: np.ndarray, tol: float) -> np.ndarray:
    if len(p) < 3:
        return p
    a, b = p[0], p[-1]
    ab = b - a
    n = float(np.hypot(*ab))
    d = np.abs(ab[0] * (p[:, 1] - a[1]) - ab[1] * (p[:, 0] - a[0])) / n if n > 0 else np.hypot(*(p - a).T)
    i = int(np.argmax(d))
    if d[i] <= tol:
        return np.vstack([a, b])
    return np.vstack([_douglas_peucker(p[:i + 1], tol)[:-1], _douglas_peucker(p[i:], tol)])


def _simplificar_laco(p: np.ndarray, tol: float) -> np.ndarray:
    """Um laco fechado: partido no ponto mais longe do primeiro, cada metade pelo Douglas-Peucker."""
    i = int(np.argmax(np.hypot(*(p - p[0]).T)))
    return np.vstack([_douglas_peucker(p[:i + 1], tol)[:-1], _douglas_peucker(np.vstack([p[i:], p[:1]]), tol)[:-1]])


def _area(p: np.ndarray) -> float:
    return 0.5 * abs(float(np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1))))


_CONTORNO: Dict[str, Any] = {}


def contorno_do_asfalto(repositorio: Optional[Path]) -> Optional[List[List[List[float]]]]:
    """O contorno do asfalto tratado do cache da pista, simplificado, em (x, z); None sem o cache.

    Lido de novo so quando o arquivo muda (o backend do repositorio regrava o cache ao abrir)."""
    from .janelas import CACHE_DA_PISTA

    if repositorio is None:
        return None
    cache = Path(repositorio) / "data" / "cache" / "tracks" / CACHE_DA_PISTA
    try:
        chave = f"{cache}|{cache.stat().st_mtime_ns}"
    except OSError:
        return None
    if _CONTORNO.get("chave") != chave:
        try:
            dados = json.loads(cache.read_text(encoding="utf-8"))
            lacos = [np.asarray(l["points"], dtype=float) for l in dados["asphaltSurface"]["loops"]
                     if len(l.get("points") or []) >= 3]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        contornos = []
        for laco in lacos:
            if _area(laco) < AREA_MINIMA_M2:
                continue
            s = _simplificar_laco(laco, TOLERANCIA_M)
            # (x, -z) do mapa -> (x, z) do mundo
            contornos.append([[round(float(px), 2), round(float(-py), 2)] for px, py in s])
        _CONTORNO.update(chave=chave, contornos=contornos)
    return _CONTORNO["contornos"]


def montar(track: Any, segmentos: List[Any], referencia: Optional[Dict[str, Any]], tipo: Optional[str],
           analise: Optional[Dict[str, Any]], linha_m: float,
           contornos: Optional[List[List[List[float]]]] = None) -> Dict[str, Any]:
    x, z = np.asarray(track.x, dtype=float), np.asarray(track.z, dtype=float)
    normal = np.asarray(track.normal, dtype=float)
    wl, wr = np.asarray(track.width_left, dtype=float), np.asarray(track.width_right, dtype=float)
    if contornos:
        pista = {"origem": "asfalto tratado do cache", "contornos": contornos}
    else:
        # Sem o cache: as duas bordas da geometria oficial, como dois contornos.
        k = _decimar(int(track.size), PONTOS_DA_BORDA)
        esquerda = np.column_stack([x[k] + normal[k, 0] * wl[k], z[k] + normal[k, 1] * wl[k]])
        direita = np.column_stack([x[k] - normal[k, 0] * wr[k], z[k] - normal[k, 1] * wr[k]])
        pista = {"origem": "geometria oficial (sem o cache da pista)",
                 "contornos": [np.round(esquerda, 2).tolist(), np.round(direita, 2).tolist()]}
    # A marca da linha do s = 0, de uma borda a outra da geometria oficial.
    linha = [[round(float(x[0] + normal[0, 0] * wl[0]), 2), round(float(z[0] + normal[0, 1] * wl[0]), 2)],
             [round(float(x[0] - normal[0, 0] * wr[0]), 2), round(float(z[0] - normal[0, 1] * wr[0]), 2)]]
    out: Dict[str, Any] = {
        "disponivel": True,
        "comprimentoM": round(float(track.length), 2),
        "pista": pista,
        "linhaDoS0": linha,
        "linhaDoJogoM": round(float(linha_m), 3),
        "referencia": None,
        "curvasDaAnalise": [],
        "curvas": rotulos_das_curvas(track, segmentos),
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
            pedal = _pedais(referencia, el.size)
            total = float(referencia.get("tempoS") or el[-1])
            na_linha = float(np.interp(linha_m, np.asarray(track.s, dtype=float), el))
            out["referencia"] = {
                "tipo": tipo,
                "lapId": referencia.get("lapId"),
                "tempoS": round(total, 3),
                "tempoNaLinhaDoJogoS": round(na_linha, 4),
                # [x, z, tempo desde o s = 0, pedal]
                "pontos": [[round(float(a), 2), round(float(b), 2), round(float(c), 3), int(d)]
                           for a, b, c, d in zip(px[r], pz[r], el[r], pedal[r])],
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
