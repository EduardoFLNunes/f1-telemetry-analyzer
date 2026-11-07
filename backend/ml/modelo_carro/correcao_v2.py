"""A amostra da correcao e o "nao conclusivo" da M1 v2 (pedido 46; ADR 0028, itens 6 e 7).

* **a amostra:** `N` passos na proporcao de cada regime nas sessoes de treino,
  `round(N * fracao)` pelo metodo dos maiores restos, semente 46. O Processo
  Gaussiano e o da v1 (`correcao.Correcao`), sem mudanca;
* **o "nao conclusivo":** a distancia media aos 10 vizinhos mais proximos nas 6
  entradas padronizadas, entre os passos de treino; o corte e o percentil 99
  nos casos de treino, sem os vizinhos da mesma volta.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy.spatial import cKDTree

from .correcao import REGIMES

N_AMOSTRA = 6000
SEMENTE = 46
K_VIZINHOS = 10
PERCENTIL_CORTE = 99.0


def cotas(regime: np.ndarray, total: int) -> Dict[str, int]:
    """Quantos passos de cada regime: a proporcao do treino, pelos maiores restos."""
    counts = {name: int(np.sum(regime == name)) for name in REGIMES}
    size = sum(counts.values())
    total = min(int(total), size)
    exact = {name: total * counts[name] / size for name in REGIMES}
    floor = {name: min(int(np.floor(v)), counts[name]) for name, v in exact.items()}
    left = total - sum(floor.values())
    order = sorted(REGIMES, key=lambda name: (exact[name] - np.floor(exact[name])), reverse=True)
    for name in order:
        if left <= 0:
            break
        if floor[name] < counts[name]:
            floor[name] += 1
            left -= 1
    return floor


def subconjunto(regime: np.ndarray, total: int = N_AMOSTRA, seed: int = SEMENTE) -> Tuple[np.ndarray, Dict[str, int]]:
    """Os indices sorteados, sem reposicao, na proporcao dos regimes."""
    rng = np.random.default_rng(seed)
    quota = cotas(regime, total)
    picked = []
    for name in REGIMES:
        pool = np.flatnonzero(regime == name)
        if quota[name]:
            picked.append(np.sort(rng.choice(pool, size=quota[name], replace=False)))
    return np.concatenate(picked), quota


class Vizinhanca:
    """O indice de "fora dos dados" de um caso: a distancia media aos k vizinhos de treino."""

    def __init__(self, X_train: np.ndarray, laps: np.ndarray, k: int = K_VIZINHOS):
        self.mean_ = X_train.mean(axis=0)
        self.scale_ = X_train.std(axis=0)
        self.scale_[self.scale_ == 0] = 1.0
        self.Z = (X_train - self.mean_) / self.scale_
        self.laps = np.asarray(laps)
        self.k = int(k)
        self.tree = cKDTree(self.Z)

    def _z(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=float) - self.mean_) / self.scale_

    def indice(self, X: np.ndarray) -> np.ndarray:
        """Para casos de outra sessao: todos os passos de treino sao vizinhos possiveis."""
        d, _ = self.tree.query(self._z(X), k=self.k)
        return d.mean(axis=1)

    def indice_sem_a_volta(self, X: np.ndarray, laps: np.ndarray) -> np.ndarray:
        """Para casos de treino: os vizinhos da mesma volta sao excluidos."""
        Z = self._z(X)
        laps = np.asarray(laps)
        out = np.empty(Z.shape[0])
        for lap in np.unique(laps):
            rows = np.flatnonzero(laps == lap)
            keep = self.laps != lap
            tree = cKDTree(self.Z[keep])
            d, _ = tree.query(Z[rows], k=self.k)
            out[rows] = d.mean(axis=1)
        return out
