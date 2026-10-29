"""A correcao aprendida da M1: um Processo Gaussiano no residuo da fisica (pedido 37, Parte D).

Registrado antes de construir (`docs/modelo_fisico_m1.md`, 1.5 e 1.6):

* **o alvo:** o estado gravado em `k+1` menos o que a fisica preve a partir do
  estado gravado em `k`, um Processo Gaussiano por grandeza (`vx`, `vy`, `r`);
* **as entradas (6):** `vx`, `vy`, `r` e a entrada do passo (`steer`, `T`, `B`),
  padronizadas pelo subconjunto de treino. Nada que identifique a volta, a
  sessao ou o ponto da pista (ADR 0017, item 1);
* **o nucleo:** `Constante x RBF (um comprimento por variavel) + Ruido branco`,
  `normalize_y=True`, hiperparametros pela verossimilhanca, sem reinicios;
* **o subconjunto:** 2.000 passos das sessoes de treino, 400 por regime, semente 37;
* **"fora dos dados":** o desvio-padrao sem o ruido dividido pelo do sinal, o
  maior das 3 grandezas. 0 e "visto no treino", 1 e "nada parecido".
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

N_POR_REGIME = 400
SEMENTE = 37
Z90 = 1.6448536269514722
BLOCO = 4000
GRANDEZAS = ("vx", "vy", "r")
REGIMES = ("freio e volante juntos", "freada", "curva", "tracao", "reta")


def regimes(B: np.ndarray, a_y: np.ndarray, T: np.ndarray, a_x: np.ndarray, g: float = 9.80665) -> np.ndarray:
    """O regime de cada ponto, pela regra da secao 1.5."""
    B, a_y, T, a_x = (np.asarray(v, dtype=float) for v in (B, a_y, T, a_x))
    braking = B >= 0.1
    cornering = np.abs(a_y) >= 0.5 * g
    out = np.full(B.shape, "reta", dtype=object)
    out[~braking & ~cornering & (T >= 0.5) & (a_x >= 0.3 * g)] = "tracao"
    out[~braking & cornering] = "curva"
    out[braking & ~cornering] = "freada"
    out[braking & cornering] = "freio e volante juntos"
    return out


def subconjunto(regime: np.ndarray, por_regime: int = N_POR_REGIME, seed: int = SEMENTE) -> Tuple[np.ndarray, Dict[str, int]]:
    """Os indices sorteados: `por_regime` de cada regime (ou todos, se houver menos)."""
    rng = np.random.default_rng(seed)
    picked, counts = [], {}
    for name in REGIMES:
        pool = np.flatnonzero(regime == name)
        take = pool if pool.size <= por_regime else rng.choice(pool, size=por_regime, replace=False)
        picked.append(np.sort(take))
        counts[name] = int(take.size)
    return np.concatenate(picked), counts


def nucleo(dim: int = 6):
    return (ConstantKernel(1.0, (1e-3, 1e3)) * RBF(np.ones(dim), (1e-2, 1e2))
            + WhiteKernel(0.1, (1e-6, 10.0)))


class Correcao:
    """Tres Processos Gaussianos, um por grandeza, sobre as mesmas 6 entradas."""

    def __init__(self):
        self.models: List[GaussianProcessRegressor] = []
        self.mean_: Optional[np.ndarray] = None
        self.scale_: Optional[np.ndarray] = None
        self.info: Dict[str, object] = {}

    def ajustar(self, X: np.ndarray, R: np.ndarray) -> "Correcao":
        self.mean_ = X.mean(axis=0)
        self.scale_ = X.std(axis=0)
        self.scale_[self.scale_ == 0] = 1.0
        Z = (X - self.mean_) / self.scale_
        self.models, hyper = [], {}
        for q, name in enumerate(GRANDEZAS):
            started = time.time()
            gp = GaussianProcessRegressor(kernel=nucleo(X.shape[1]), normalize_y=True,
                                          n_restarts_optimizer=0, random_state=SEMENTE)
            gp.fit(Z, R[:, q])
            self.models.append(gp)
            k = gp.kernel_
            hyper[name] = {"constante": float(k.k1.k1.constant_value),
                           "comprimentos": [float(v) for v in np.atleast_1d(k.k1.k2.length_scale)],
                           "ruido": float(k.k2.noise_level), "y_media": float(gp._y_train_mean),
                           "y_desvio": float(gp._y_train_std),
                           "log_verossimilhanca": float(gp.log_marginal_likelihood_value_),
                           "tempo_s": round(time.time() - started, 1)}
        self.info = {"amostras": int(X.shape[0]), "hiperparametros": hyper,
                     "entradas_media": self.mean_.tolist(), "entradas_desvio": self.scale_.tolist()}
        return self

    def prever(self, state: np.ndarray, u: np.ndarray, com_desvio: bool = True
               ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """(media (n, 3), desvio com o ruido (n, 3), indice de fora dos dados (n,)); sem desvio, os dois None."""
        X = np.column_stack([state, u])
        Z = (X - self.mean_) / self.scale_
        n = Z.shape[0]
        mean = np.empty((n, 3))
        std = np.empty((n, 3)) if com_desvio else None
        ratio = np.empty((n, 3)) if com_desvio else None
        for q, gp in enumerate(self.models):
            k = gp.kernel_
            y_sd = float(gp._y_train_std)
            noise = float(k.k2.noise_level) * y_sd ** 2
            signal = float(k.k1.k1.constant_value) * y_sd ** 2
            for a in range(0, n, BLOCO):
                b = min(a + BLOCO, n)
                if com_desvio:
                    m, s = gp.predict(Z[a:b], return_std=True)
                    std[a:b, q] = s
                    latent = np.maximum(s ** 2 - noise, 0.0)
                    ratio[a:b, q] = np.sqrt(latent / signal)
                else:
                    m = gp.predict(Z[a:b])
                mean[a:b, q] = m
        index = ratio.max(axis=1) if com_desvio else None
        return mean, std, index
