"""O medidor calibrado por trecho (pedido 50; ADR 0031, item 5).

O simulador quase-estacionario ordena mal as linhas em alguns trechos: no
pedido 47 ele previa a C10 1,0 s mais rapida nas linhas geradas, e no jogo elas
perderam 0,3 s ali. A busca vai para onde o medidor mais erra.

A correcao e uma **escala por trecho, pela origem**, sobre a diferenca contra a
linha base (o C0):

    dJ_k(X) ~ beta_k * dS_k(X)

com `dJ` a diferenca no jogo (mediana da linha menos a do C0) e `dS` a
diferenca no simulador. `beta_k` sai por minimos quadrados nas linhas de
treino e fica em [0, 2]: com tres linhas por ajuste, uma escala negativa
inverteria a fisica com pouco dado, e 0 so tira o trecho da ordenacao.

A escolha entre os medidores e pela correlacao de Spearman entre a diferenca
prevista e a do jogo, por microssetor, nas linhas deixadas de fora.
"""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

import numpy as np

BETA_MIN = 0.0
BETA_MAX = 2.0
SOMA_MINIMA = 1e-9


def ajustar_beta(dJ: Mapping[str, np.ndarray], dS: Mapping[str, np.ndarray], linhas: Sequence[str]) -> np.ndarray:
    """`dJ[X]` e `dS[X]`: (trechos,). Devolve beta (trechos,) ajustado so com as `linhas` dadas."""
    J = np.array([np.asarray(dJ[x], float) for x in linhas])
    S = np.array([np.asarray(dS[x], float) for x in linhas])
    num = np.sum(J * S, axis=0)
    den = np.sum(S * S, axis=0)
    beta = np.where(den > SOMA_MINIMA, num / np.where(den > SOMA_MINIMA, den, 1.0), 1.0)
    return np.clip(beta, BETA_MIN, BETA_MAX)


def pesos_por_passo(beta: np.ndarray, trecho_do_passo: np.ndarray) -> np.ndarray:
    """O beta do trecho de cada passo da grade."""
    return np.asarray(beta, float)[np.asarray(trecho_do_passo, int)]


def diferenca_por_grupo(passos_x: np.ndarray, passos_base: np.ndarray, grupo_do_passo: np.ndarray, grupos: int,
                        pesos: np.ndarray = None) -> np.ndarray:
    """Soma, por grupo (trecho ou microssetor), de peso * (tempo do passo da linha - do da base)."""
    d = np.asarray(passos_x, float) - np.asarray(passos_base, float)
    if pesos is not None:
        d = d * np.asarray(pesos, float)
    return np.bincount(np.asarray(grupo_do_passo, int), weights=d, minlength=grupos)


def deixar_uma_de_fora(dJ_trecho: Mapping[str, np.ndarray], dS_trecho: Mapping[str, np.ndarray],
                       linhas: Sequence[str]) -> Dict[str, np.ndarray]:
    """{X: beta ajustado com as outras linhas}."""
    return {x: ajustar_beta(dJ_trecho, dS_trecho, [y for y in linhas if y != x]) for x in linhas}


def spearman_juntos(previsto: Mapping[str, np.ndarray], jogo: Mapping[str, np.ndarray], linhas: Sequence[str]) -> Dict[str, object]:
    """O Spearman dos pares (linha, microssetor) juntos, e o de cada linha."""
    from scipy.stats import spearmanr

    p = np.concatenate([np.asarray(previsto[x], float) for x in linhas])
    j = np.concatenate([np.asarray(jogo[x], float) for x in linhas])
    rho, pv = spearmanr(p, j)
    por_linha = {}
    for x in linhas:
        r, q = spearmanr(np.asarray(previsto[x], float), np.asarray(jogo[x], float))
        por_linha[x] = {"rho": float(r), "p": float(q)}
    return {"rho": float(rho), "p": float(pv), "pares": int(len(p)), "por_linha": por_linha}


def escolher(candidatos: Mapping[str, Mapping[str, object]]) -> str:
    """O candidato de maior rho (o primeiro, no empate exato)."""
    return max(candidatos, key=lambda k: (float(candidatos[k]["rho"]), -list(candidatos).index(k)))
