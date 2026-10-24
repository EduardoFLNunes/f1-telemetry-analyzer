"""A validacao da M1: os passos, os casos, a malha aberta e as metricas do ADR 0022 (pedido 37, Parte E).

Registrado antes de construir (`docs/modelo_fisico_m1.md`, 1.7):

* **os casos:** inicios a cada 0,1 s (2 passos) em todos os trechos da sessao de
  teste, desde que o trecho tenha pelo menos 1,0 s (20 passos) depois do inicio;
* **o erro:** em cada horizonte, o erro de `vx`, `vy` e `r`, cada um dividido
  pelo desvio-padrao da grandeza nas sessoes de treino; o combinado e a raiz da
  media dos quadrados, sobre os casos e as 3 grandezas;
* **skill** = 1 - erro do modelo / erro da referencia;
* **o IC 95%** do skill contra R1: bootstrap agrupado por volta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from . import convencoes as C
from .correcao import Z90, regimes
from .dados import DT, G

ESTADO = ("vx", "vy", "r")
ENTRADA = ("steer", "T", "B")
HORIZONTES = {"0,25 s": 5, "0,5 s": 10, "1,0 s": 20}
H_PRINCIPAL = 10
H_MAX = 20
A_CADA = 2
FAIXAS_KMH = ((0.0, 100.0, "abaixo de 100 km/h"), (100.0, 160.0, "100 a 160 km/h"),
              (160.0, 220.0, "160 a 220 km/h"), (220.0, 1e9, "acima de 220 km/h"))


@dataclass
class Passos:
    """Pares (k, k+1) dentro de um trecho: o estado, a entrada do passo e o estado seguinte."""

    S0: np.ndarray
    U: np.ndarray
    S1: np.ndarray
    regime: np.ndarray
    lap: np.ndarray
    session: np.ndarray

    def __len__(self) -> int:
        return int(self.S0.shape[0])


def _estado(frame: pd.DataFrame) -> np.ndarray:
    return frame[list(ESTADO)].to_numpy(dtype=float)


def _entrada(frame: pd.DataFrame) -> np.ndarray:
    return frame[list(ENTRADA)].to_numpy(dtype=float)


def _grupos(frame: pd.DataFrame):
    return frame.groupby("trecho", sort=False).indices.values()


def passos(frame: pd.DataFrame) -> Passos:
    """Todos os passos de um quadro na convencao do modelo (ordenado por trecho e `k`)."""
    S, U = _estado(frame), _entrada(frame)
    reg = regimes(frame["B"].to_numpy(dtype=float), frame["a_y"].to_numpy(dtype=float),
                  frame["T"].to_numpy(dtype=float), frame["a_x"].to_numpy(dtype=float))
    first, second = [], []
    for index in _grupos(frame):
        index = np.sort(index)
        if index.size >= 2:
            first.append(index[:-1])
            second.append(index[1:])
    a, b = np.concatenate(first), np.concatenate(second)
    good = np.isfinite(S[a]).all(1) & np.isfinite(S[b]).all(1) & np.isfinite(U[a]).all(1) & np.isfinite(U[b]).all(1)
    a, b = a[good], b[good]
    return Passos(S0=S[a], U=0.5 * (U[a] + U[b]), S1=S[b], regime=reg[a],
                  lap=frame["lap_id"].to_numpy()[a], session=frame["session_id"].to_numpy()[a])


@dataclass
class Casos:
    """Inicios de previsao, com o caminho gravado ate `H_MAX` passos."""

    S0: np.ndarray        # (n, 3)
    U: np.ndarray         # (n, H, 3) entrada de cada passo
    S: np.ndarray         # (n, H+1, 3) estado gravado
    P: np.ndarray         # (n, H+1, 2) posicao gravada no referencial do inicio
    regime: np.ndarray
    lap: np.ndarray
    session: np.ndarray
    vx_kmh: np.ndarray
    pneu: np.ndarray
    trecho: np.ndarray
    k0: np.ndarray
    s0: np.ndarray

    def __len__(self) -> int:
        return int(self.S0.shape[0])

    def filtrar(self, mask: np.ndarray) -> "Casos":
        return Casos(**{k: v[mask] for k, v in self.__dict__.items()})


def casos(frame: pd.DataFrame, conv: C.Convencoes, a_cada: int = A_CADA, horizonte: int = H_MAX) -> Casos:
    """Os casos de um quadro: inicios a cada `a_cada` passos, com `horizonte` passos pela frente no trecho."""
    S, U = _estado(frame), _entrada(frame)
    reg = regimes(frame["B"].to_numpy(dtype=float), frame["a_y"].to_numpy(dtype=float),
                  frame["T"].to_numpy(dtype=float), frame["a_x"].to_numpy(dtype=float))
    xz = frame[["x", "z"]].to_numpy(dtype=float)
    heading = frame["heading"].to_numpy(dtype=float)
    starts = []
    for index in _grupos(frame):
        index = np.sort(index)
        for j in range(0, index.size - horizonte, a_cada):
            starts.append(index[j:j + horizonte + 1])
    if not starts:
        raise ValueError("nenhum trecho tem o horizonte inteiro")
    path = np.asarray(starts)                       # (n, H+1)
    states = S[path]
    inputs = 0.5 * (U[path[:, :-1]] + U[path[:, 1:]])
    good = np.isfinite(states).all((1, 2)) & np.isfinite(inputs).all((1, 2))
    path, states, inputs = path[good], states[good], inputs[good]
    front, left = C.eixos(heading[path[:, 0]], conv.forma_heading, conv.s_esquerda)
    disp = xz[path] - xz[path[:, :1]]
    P = np.stack([np.einsum("nhk,nk->nh", disp, front), np.einsum("nhk,nk->nh", disp, left)], axis=-1)
    start = path[:, 0]
    return Casos(S0=states[:, 0], U=inputs, S=states, P=P, regime=reg[start],
                 lap=frame["lap_id"].to_numpy()[start], session=frame["session_id"].to_numpy()[start],
                 vx_kmh=S[start, 0] * 3.6, pneu=frame["tyre_core_temp"].to_numpy(dtype=float)[start],
                 trecho=frame["trecho"].to_numpy()[start], k0=frame["k"].to_numpy()[start],
                 s0=frame["s"].to_numpy(dtype=float)[start])


# ------------------------------------------------------------ metricas ---

def erro_quadrado(pred: np.ndarray, true: np.ndarray, sigma: np.ndarray, h: int) -> np.ndarray:
    """Soma, nas 3 grandezas, do erro normalizado ao quadrado em cada caso, no passo `h`. (n,)"""
    return np.sum(((pred[:, h] - true[:, h]) / sigma) ** 2, axis=1)


def erro_combinado(pred: np.ndarray, true: np.ndarray, sigma: np.ndarray, h: int,
                   mask: Optional[np.ndarray] = None) -> float:
    sq = erro_quadrado(pred, true, sigma, h)
    if mask is not None:
        sq = sq[mask]
    return float(np.sqrt(np.mean(sq) / 3.0)) if sq.size else float("nan")


def skill(e_model: float, e_ref: float) -> float:
    return float(1.0 - e_model / e_ref) if e_ref > 0 else float("nan")


def bootstrap_skill(sq_model: np.ndarray, sq_ref: np.ndarray, lap: np.ndarray, n: int = 2000,
                    seed: int = 37) -> Dict[str, float]:
    """IC 95% do skill, reamostrando voltas inteiras."""
    laps, inverse = np.unique(lap, return_inverse=True)
    sum_m = np.bincount(inverse, weights=sq_model, minlength=laps.size)
    sum_r = np.bincount(inverse, weights=sq_ref, minlength=laps.size)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, laps.size, size=(n, laps.size))
    weights = np.apply_along_axis(np.bincount, 1, draws, minlength=laps.size)
    skills = 1.0 - np.sqrt(weights @ sum_m) / np.sqrt(weights @ sum_r)
    return {"p2_5": float(np.percentile(skills, 2.5)), "p97_5": float(np.percentile(skills, 97.5)),
            "voltas": int(laps.size), "reamostragens": int(n)}


def por_grandeza(pred: np.ndarray, true: np.ndarray, h: int, mask: Optional[np.ndarray] = None) -> Dict[str, Dict[str, float]]:
    """Erro quadratico medio (raiz) e vies de cada grandeza, nas unidades dela."""
    err = pred[:, h] - true[:, h]
    if mask is not None:
        err = err[mask]
    out = {}
    for q, name in enumerate(ESTADO):
        out[name] = {"rmse": float(np.sqrt(np.mean(err[:, q] ** 2))), "vies": float(np.mean(err[:, q]))}
    return out


def erro_posicao(pred_pos: np.ndarray, true_pos: np.ndarray, h: int, mask: Optional[np.ndarray] = None) -> Dict[str, float]:
    d = np.hypot(*(pred_pos[:, h] - true_pos[:, h]).T)
    if mask is not None:
        d = d[mask]
    return {"media_m": float(np.mean(d)), "mediana_m": float(np.median(d)), "p90_m": float(np.percentile(d, 90))}


def cobertura(residuo: np.ndarray, media: np.ndarray, desvio: np.ndarray) -> np.ndarray:
    """Dentro do intervalo de 90% (media +- 1,645 desvio)? (n, 3) booleano."""
    return np.abs(residuo - media) <= Z90 * desvio


def faixa_de_velocidade(vx_kmh: np.ndarray) -> np.ndarray:
    out = np.full(vx_kmh.shape, "", dtype=object)
    for low, high, name in FAIXAS_KMH:
        out[(vx_kmh >= low) & (vx_kmh < high)] = name
    return out
