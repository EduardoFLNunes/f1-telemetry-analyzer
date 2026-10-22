"""O replay da curva (pedido 36, Parte E): o que o engenheiro mostra quando fala de uma curva.

Para uma curva citada pelo radio (uma analise das voltas ou uma frase do coach com causa):

* **as duas linhas:** a sua volta e a volta de referencia, na geometria oficial (centro +
  normal x lateral, o mesmo tracado da tela Volta), da entrada a saida da curva, com o
  tempo de cada uma desde a mesma entrada e o pedal (o da tela Volta: 2 = freio, 1 =
  acelerador cheio, 0 = parcial). Os dois carros andam cada um no seu proprio tempo: a
  diferenca aparece sozinha, no quanto a referencia abre;
* **as duas freadas** (a regra do relatorio de evolucao, `braking_point`) e a distancia
  entre elas;
* **as duas minimas,** no ponto de cada uma, com o valor;
* **o tracado:** no ponto da minima da referencia, as duas posicoes e a distancia, com o
  lado por extenso (ADR 0003: positivo = mais a esquerda);
* **o tempo perdido na curva** (o trecho do relatorio de evolucao, a mesma perda da analise).

Sempre "voce" e "IA (referencia)", a diferenca medida contra uma volta real (ADR 0012).
So le as grades que o radio ja tem (a volta ao vivo e a referencia do store); nada de
fisica nova.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

ANTES_DA_FREADA_M = 50.0     # a entrada: um pouco antes da primeira freada (ou do inicio da curva)
DEPOIS_DA_CURVA_M = 60.0     # a saida: um pouco depois do fim da curva
LIMIAR_DO_FREIO = 0.15       # o pedal, como a tela Volta (Fantasma.tsx)
ACELERADOR_CHEIO = 0.9


def _pedal(freio: np.ndarray, acelerador: np.ndarray) -> np.ndarray:
    p = np.zeros(freio.size, dtype=int)
    p[np.nan_to_num(acelerador) >= ACELERADOR_CHEIO] = 1
    p[np.nan_to_num(freio) >= LIMIAR_DO_FREIO] = 2
    return p


def _posicoes(track: Any, lateral: np.ndarray, indices: np.ndarray) -> np.ndarray:
    x, z = np.asarray(track.x, dtype=float), np.asarray(track.z, dtype=float)
    normal = np.asarray(track.normal, dtype=float)
    lat = np.nan_to_num(lateral[indices])
    return np.column_stack([x[indices] + normal[indices, 0] * lat, z[indices] + normal[indices, 1] * lat])


def _tempos(elapsed: np.ndarray, indices: np.ndarray, total: float) -> np.ndarray:
    """O tempo desde a entrada da curva, ao longo da janela (com a volta da linha, se a janela cruzar o s = 0)."""
    t = np.asarray(elapsed, dtype=float)[indices].copy()
    for k in range(1, t.size):
        if t[k] < t[k - 1]:
            t[k:] += total
    return t - t[0]


def cobertura_na_curva(linhas_grade: Dict[str, np.ndarray], indices: Sequence[int]) -> float:
    """Fracao dos pontos da janela com o relogio medido (antes de interpolar)."""
    el = linhas_grade.get("elapsed")
    if el is None:
        return 0.0
    vals = [el[i] for i in indices]
    return sum(1 for v in vals if v is not None and v == v) / max(len(vals), 1)


def janela_da_curva(pista: Any, codigo: str, volta: Dict[str, np.ndarray], ref: Dict[str, np.ndarray]):
    """O segmento da curva e os indices da grade da entrada a saida; None se a curva nao existe."""
    from ml.comparison.evolution import braking_point
    from ml.comparison.lap_vs_reference import _window

    track = pista.track
    for k, seg in enumerate(pista.segmentos):
        if seg.corner.label[:3] != codigo:
            continue
        corner = seg.corner
        anterior = pista.segmentos[k - 1].corner.apex_s
        freada_v = braking_point(volta["freio"], track, anterior, corner.apex_s)
        freada_r = braking_point(ref["freio"], track, anterior, corner.apex_s)
        L = float(track.length)
        # a entrada: o que vier primeiro (contando para tras a partir do apice) entre o inicio da curva e as freadas
        recuos = [(corner.apex_s - s) % L for s in (corner.start_s, freada_v, freada_r) if s is not None]
        inicio = (corner.apex_s - max(recuos) - ANTES_DA_FREADA_M) % L
        fim = (corner.end_s + DEPOIS_DA_CURVA_M) % L
        return seg, k, _window(track, inicio, fim), freada_v, freada_r
    return None


def dados_da_curva(pista: Any, codigo: str, volta: Dict[str, np.ndarray], volta_total: float,
                   ref: Dict[str, np.ndarray], ref_total: float, numero_da_volta: Optional[int],
                   tipo: Optional[str]) -> Optional[Dict[str, Any]]:
    """O replay de uma curva: as duas linhas com o tempo e o pedal, as freadas, as minimas,
    o tracado e a perda. `volta` e `ref` sao grades completas (`analise.grade`)."""
    from ml.comparison.evolution import segment_time
    from ml.comparison.lap_vs_reference import _signed_distance, _window

    janela = janela_da_curva(pista, codigo, volta, ref)
    if janela is None:
        return None
    seg, _, indices, freada_v, freada_r = janela
    track = pista.track
    corner = seg.corner
    pos_v, pos_r = _posicoes(track, volta["lateral"], indices), _posicoes(track, ref["lateral"], indices)
    t_v, t_r = _tempos(volta["elapsed"], indices, volta_total), _tempos(ref["elapsed"], indices, ref_total)
    ped_v = _pedal(volta["freio"][indices], volta["acelerador"][indices])
    ped_r = _pedal(ref["freio"][indices], ref["acelerador"][indices])

    def linha(pos, t, ped):
        return [[round(float(a), 2), round(float(b), 2), round(float(c), 3), int(d)] for (a, b), c, d in zip(pos, t, ped)]

    def ponto(s: Optional[float], lateral: np.ndarray) -> Optional[Dict[str, Any]]:
        if s is None:
            return None
        i = np.array([int(track.index_of(s))])
        p = _posicoes(track, lateral, i)[0]
        return {"x": round(float(p[0]), 2), "z": round(float(p[1]), 2), "s": round(float(s), 1)}

    dentro = _window(track, corner.start_s, corner.end_s)
    i_v = int(dentro[int(np.nanargmin(volta["velocidade"][dentro]))])
    i_r = int(dentro[int(np.nanargmin(ref["velocidade"][dentro]))])
    mv, mr = _posicoes(track, volta["lateral"], np.array([i_v])), _posicoes(track, ref["lateral"], np.array([i_r]))
    # o tracado: no ponto da minima da referencia, a sua posicao e a dela
    tv = _posicoes(track, volta["lateral"], np.array([i_r]))[0]
    dif_lateral = float(np.nan_to_num(volta["lateral"][i_r]) - np.nan_to_num(ref["lateral"][i_r]))
    perda = segment_time(volta["elapsed"], volta_total, track, seg) - segment_time(ref["elapsed"], ref_total, track, seg)
    return {
        "curva": codigo,
        "lado": "esquerda" if corner.label.endswith("esq") else "direita",
        "volta": numero_da_volta,
        "referencia": tipo,
        "rotuloDaReferencia": "IA (referência)" if tipo == "volta_ia" else "sua melhor (referência)",
        "perdaS": round(float(perda), 3),
        "linhas": {"voce": linha(pos_v, t_v, ped_v), "referencia": linha(pos_r, t_r, ped_r)},
        "duracaoS": round(float(max(t_v[-1], t_r[-1])), 3),
        "freadas": {
            "voce": ponto(freada_v, volta["lateral"]),
            "referencia": ponto(freada_r, ref["lateral"]),
            # positivo = voce freou depois da referencia; negativo = antes
            "distanciaM": round(float(_signed_distance(track, freada_v, freada_r)), 1)
            if freada_v is not None and freada_r is not None else None,
        },
        "minimas": {
            "voce": {"x": round(float(mv[0, 0]), 2), "z": round(float(mv[0, 1]), 2),
                     "kmh": round(float(volta["velocidade"][i_v]), 1)},
            "referencia": {"x": round(float(mr[0, 0]), 2), "z": round(float(mr[0, 1]), 2),
                           "kmh": round(float(ref["velocidade"][i_r]), 1)},
        },
        "tracado": {
            "voce": [round(float(tv[0]), 2), round(float(tv[1]), 2)],
            "referencia": [round(float(mr[0, 0]), 2), round(float(mr[0, 1]), 2)],
            "distanciaM": round(abs(dif_lateral), 2),
            "lado": "esquerda" if dif_lateral > 0 else "direita",
        },
    }


def volta_mais_perto_da_mediana(voltas: Sequence[Dict[str, Any]], curva: Dict[str, Any]) -> Optional[int]:
    """Na analise, a volta das 3 cuja perda na curva fica mais perto da mediana (o indice em `voltas`).

    `curva["perdas"]` vem na ordem das voltas analisadas."""
    perdas = list(curva.get("perdas") or [])
    if not perdas or len(perdas) != len(voltas):
        return None
    mediana = float(curva.get("perdaMedianaS", np.median(perdas)))
    return int(min(range(len(perdas)), key=lambda i: (abs(perdas[i] - mediana), i)))


def replay_da_analise(pista: Any, voltas: Sequence[Dict[str, Any]], analise: Dict[str, Any],
                      ref: Dict[str, np.ndarray], ref_total: float, tipo: Optional[str]) -> List[Dict[str, Any]]:
    """Uma curva por curva citada na analise, cada uma com a volta mais perto da mediana.

    `voltas`: as 3 voltas analisadas, cada uma com `grade` e `tempoS`."""
    out = []
    for curva in analise.get("curvas") or []:
        i = volta_mais_perto_da_mediana(voltas, curva)
        if i is None or voltas[i].get("grade") is None:
            continue
        d = dados_da_curva(pista, curva["curva"], voltas[i]["grade"], float(voltas[i]["tempoS"]), ref, ref_total,
                           voltas[i].get("volta"), tipo)
        if d is not None:
            out.append(d)
    return out
