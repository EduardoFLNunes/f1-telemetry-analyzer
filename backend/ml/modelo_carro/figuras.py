"""As figuras da M1: o previsto contra o gravado numa freada (C01) e numa curva lenta (C10).

Registrado antes de construir (`docs/modelo_fisico_m1.md`, 1.7): na rodada em que
a sessao `2026-10-21_20-30-54` e a de teste, na primeira volta valida em que o
trecho cobre o caso,

* **a freada da C01:** inicio 0,2 s antes do primeiro passo com freio >= 0,5
  entre 250 m antes do comeco da C01 e o apice dela;
* **a curva lenta, a C10:** inicio 0,5 s antes do passo de menor `vx` dentro da C10;
* horizonte de 1,0 s; a M1, R1, R0 e o gravado; a faixa de 5% a 95% da M1 por
  Monte Carlo (200 caminhos, cada passo sorteado da previsao do Processo
  Gaussiano com o ruido), semente 37.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from . import fisica as F
from . import validacao as V
from .dados import DT

CAMINHOS = 200
SEMENTE = 37
ANTES_DA_FREADA = 4      # 0,2 s
ANTES_DO_MINIMO = 10     # 0,5 s


def _volta_ordem(lap_id: str) -> int:
    return int(str(lap_id).split("#")[1])


def _cabe(frame: pd.DataFrame, start: int, horizon: int = V.H_MAX) -> bool:
    end = start + horizon
    if start < 0 or end >= len(frame):
        return False
    trecho = frame["trecho"].to_numpy()
    k = frame["k"].to_numpy()
    return bool(trecho[start] == trecho[end] and k[end] - k[start] == horizon)


def achar_inicio(frame: pd.DataFrame, corner, length: float, tipo: str) -> Optional[int]:
    """A posicao (no quadro) do inicio do caso, pela regra registrada, ou None."""
    s = frame["s"].to_numpy(dtype=float)
    for lap in sorted(frame["lap_id"].unique(), key=_volta_ordem):
        rows = np.flatnonzero(frame["lap_id"].to_numpy() == lap)
        if tipo == "freada":
            low = corner.start_s - 250.0
            inside = np.mod(s[rows] - low, length) <= np.mod(corner.apex_s - low, length)
            hit = rows[inside & (frame["B"].to_numpy(dtype=float)[rows] >= 0.5)]
            if hit.size == 0:
                continue
            start = int(hit[0]) - ANTES_DA_FREADA
        else:
            span = np.mod(corner.end_s - corner.start_s, length)
            inside = rows[np.mod(s[rows] - corner.start_s, length) <= span]
            if inside.size == 0:
                continue
            start = int(inside[np.argmin(frame["vx"].to_numpy(dtype=float)[inside])]) - ANTES_DO_MINIMO
        if _cabe(frame, start):
            return start
    return None


def caso(frame: pd.DataFrame, start: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(estado inicial (1, 3), entradas (1, H, 3), estado gravado (1, H+1, 3)) de um inicio."""
    path = np.arange(start, start + V.H_MAX + 1)
    S = frame[list(V.ESTADO)].to_numpy(dtype=float)[path]
    U = frame[list(V.ENTRADA)].to_numpy(dtype=float)[path]
    inputs = 0.5 * (U[:-1] + U[1:])
    return S[:1], inputs[None], S[None]


def monte_carlo(state0: np.ndarray, U: np.ndarray, p, corr, n: int = CAMINHOS, seed: int = SEMENTE) -> np.ndarray:
    """Os caminhos da M1 com o ruido da previsao a cada passo. (n, H+1, 3)."""
    rng = np.random.default_rng(seed)
    x = np.repeat(state0, n, axis=0)
    out = np.empty((n, U.shape[1] + 1, 3))
    out[:, 0] = x
    for k in range(U.shape[1]):
        u = np.repeat(U[:, k], n, axis=0)
        mean, std, _ = corr.prever(x, u)
        x = F.passo(x, u, p) + mean + std * rng.standard_normal(mean.shape)
        out[:, k + 1] = x
    return out


def desenhar(frame: pd.DataFrame, start: int, p, corr, titulo: str, path) -> Dict[str, object]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    S0, U, S = caso(frame, start)
    r0 = F.persistencia(S0, V.H_MAX)
    r1, _ = F.malha_aberta(S0, U, p)
    m1, _ = F.malha_aberta(S0, U, p, corr)
    mc = monte_carlo(S0, U, p, corr)
    lo, hi = np.percentile(mc, [5, 95], axis=0)
    t = np.arange(V.H_MAX + 1) * DT
    tu = (np.arange(V.H_MAX) + 0.5) * DT
    labels = [("vx (km/h)", 3.6), ("vy no centro de massa (m/s)", 1.0), ("guinada r (rad/s)", 1.0)]
    fig, axes = plt.subplots(4, 1, figsize=(7.5, 9.5), sharex=True)
    for q, (label, scale) in enumerate(labels):
        ax = axes[q]
        ax.fill_between(t, lo[:, q] * scale, hi[:, q] * scale, color="#4C78A8", alpha=0.2, label="M1, faixa de 5% a 95%")
        ax.plot(t, S[0, :, q] * scale, color="black", lw=2, label="gravado")
        ax.plot(t, m1[0, :, q] * scale, color="#4C78A8", lw=1.8, label="M1 (física + correção)")
        ax.plot(t, r1[0, :, q] * scale, color="#E45756", lw=1.4, ls="--", label="R1 (só a física)")
        ax.plot(t, r0[0, :, q] * scale, color="#999999", lw=1.2, ls=":", label="R0 (persistência)")
        ax.set_ylabel(label)
        ax.axvline(0.5, color="#cccccc", lw=0.8)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, loc="best")
    ax = axes[3]
    ax.plot(tu, U[0, :, 0], label="volante (positivo à direita)", color="#72B7B2")
    ax.plot(tu, U[0, :, 1], label="acelerador", color="#54A24B")
    ax.plot(tu, U[0, :, 2], label="freio", color="#F58518")
    ax.set_ylabel("entradas")
    ax.set_xlabel("tempo desde o início da previsão (s)")
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.3)
    row = frame.iloc[start]
    fig.suptitle(f"{titulo}\n{row['lap_id']}, s = {row['s']:.0f} m, início a {row['vx'] * 3.6:.0f} km/h", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    errs = {}
    for name, h in V.HORIZONTES.items():
        errs[name] = {model: (pred[0, h] - S[0, h]).tolist() for model, pred in (("M1", m1), ("R1", r1), ("R0", r0))}
    return {"arquivo": str(path), "volta": str(row["lap_id"]), "s_m": float(row["s"]), "vx_kmh": float(row["vx"] * 3.6),
            "erros_vx_vy_r": errs}
