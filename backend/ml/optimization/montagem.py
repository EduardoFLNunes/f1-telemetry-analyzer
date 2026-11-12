"""A montagem por trecho da L1 (pedido 50; ADR 0031, item 7).

Em cada trecho do ADR 0030 entra a linha escolhida (a mais rapida no jogo entre
a C2, a C3 e a C4). Entre dois trechos com linhas diferentes, a emenda fica na
reta do trecho seguinte, do inicio dele ao inicio da curva dele (no trecho da
chegada, ate o fim), no ponto em que as duas linhas mais se aproximam. Na
janela da emenda, a lateral passa de uma linha para a outra por um polinomio de
grau 5 com a primeira e a segunda derivadas nulas nas pontas.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

import numpy as np

JANELA_DA_EMENDA_M = 40.0
JANELA_MINIMA_M = 10.0


def suave(x: np.ndarray) -> np.ndarray:
    """0 -> 1 com a primeira e a segunda derivadas nulas em 0 e em 1: 10x^3 - 15x^4 + 6x^5."""
    x = np.clip(np.asarray(x, float), 0.0, 1.0)
    return x ** 3 * (10.0 - 15.0 * x + 6.0 * x * x)


def montar(track_s: np.ndarray, comprimento: float, trechos, escolha: Sequence[str],
           laterais: Mapping[str, np.ndarray]) -> Dict[str, object]:
    """A lateral montada na grade, com as emendas.

    `trechos`: os do ADR 0030 (com `inicio_s`, `fim_s`, `entrada_s`, `tem_curva`), em ordem.
    `escolha[k]`: o nome da linha do trecho k. `laterais[nome]`: a lateral na grade.
    """
    s = np.asarray(track_s, float)
    passo = float(np.median(np.diff(s)))
    K = len(trechos)
    if len(escolha) != K:
        raise ValueError("uma escolha por trecho")
    out = np.empty_like(s)
    for k, t in enumerate(trechos):
        m = (s >= t.inicio_s - 1e-9) & (s < t.fim_s - 1e-9)
        out[m] = np.asarray(laterais[escolha[k]], float)[m]
    emendas: List[Dict[str, object]] = []
    for k in range(K):
        a, b = escolha[k], escolha[(k + 1) % K]
        if a == b:
            continue
        seguinte = trechos[(k + 1) % K]
        fim_da_reta = seguinte.entrada_s if seguinte.tem_curva else seguinte.fim_s
        reta = float(fim_da_reta - seguinte.inicio_s)
        janela = max(min(JANELA_DA_EMENDA_M, reta), JANELA_MINIMA_M)
        meia = 0.5 * janela
        lo, hi = seguinte.inicio_s + meia, fim_da_reta - meia
        if hi < lo:
            lo = hi = seguinte.inicio_s + 0.5 * reta
        cand = np.flatnonzero((s >= lo - 1e-9) & (s <= hi + 1e-9))
        if cand.size == 0:
            cand = np.array([int(np.argmin(np.abs(s - 0.5 * (lo + hi))))])
        LA, LB = np.asarray(laterais[a], float), np.asarray(laterais[b], float)
        centro_i = int(cand[np.argmin(np.abs(LA[cand] - LB[cand]))])
        centro = float(s[centro_i])
        # A janela [centro - meia, centro + meia]; antes dela vale A, depois B (dentro do trecho seguinte).
        d = s - centro
        d = np.where(d > comprimento / 2, d - comprimento, np.where(d < -comprimento / 2, d + comprimento, d))
        na = (d >= -meia) & (d <= meia)
        w = suave((d[na] + meia) / janela)
        out[na] = (1.0 - w) * LA[na] + w * LB[na]
        antes = (d < -meia) & (s >= seguinte.inicio_s - 1e-9) & (s < seguinte.inicio_s + reta + passo)
        out[antes] = LA[antes]
        emendas.append({"de": a, "para": b, "entre": f"{trechos[k].nome}/{seguinte.nome}", "centro_s": centro,
                        "janela_m": janela, "distancia_entre_as_linhas_no_centro_m": float(abs(LA[centro_i] - LB[centro_i])),
                        "reta_m": reta})
    return {"lateral": out, "emendas": emendas}


def escolher_por_trecho(medianas: Mapping[str, Sequence[float]], candidatas: Sequence[str]) -> List[str]:
    """Em cada trecho, a candidata de menor mediana (o primeiro nome, no empate exato)."""
    K = len(next(iter(medianas.values())))
    return [min(candidatas, key=lambda x: (float(medianas[x][k]), list(candidatas).index(x))) for k in range(K)]
