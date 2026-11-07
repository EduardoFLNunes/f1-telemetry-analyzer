"""As figuras da M1 v2 (pedido 46, Partes B.3 e C.3).

* **a curva do pneu:** a forca lateral por carga contra o angulo de deriva, nas
  cargas de uma roda parada, a 150 km/h e a 270 km/h, com os pontos das sessoes
  de treino (por eixo: a forca lateral do eixo tirada de `a_y` e da derivada da
  guinada, dividida pela carga do eixo);
* **a C01 e a C10:** as mesmas regras de inicio da v1 (`figuras.achar_inicio`),
  com a M1 v2, a fisica v2, a M1 v1, a fisica v1, R0 e o gravado, e a faixa de
  5% a 95% da M1 v2 (200 caminhos, semente 46).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from . import correcao as K
from . import figuras as FG
from . import fisica as F
from . import fisica_v2 as F2
from . import validacao as V
from .dados import DT, G

SEMENTE = 46
CAMINHOS = 200


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def pontos_dos_eixos(frame: pd.DataFrame, p: F2.ParametrosV2) -> Dict[str, np.ndarray]:
    """Angulo de deriva e forca lateral por carga de cada eixo, nas amostras de treino com `vx` >= 15 m/s."""
    vx = frame["vx"].to_numpy(dtype=float)
    vy = frame["vy"].to_numpy(dtype=float)
    r = frame["r"].to_numpy(dtype=float)
    a_y = frame["a_y"].to_numpy(dtype=float)
    a_x = frame["a_x"].to_numpy(dtype=float)
    steer = frame["steer"].to_numpy(dtype=float)
    rdot = np.full(r.shape, np.nan)
    for idx in frame.groupby("trecho", sort=False).indices.values():
        idx = np.sort(idx)
        if idx.size >= 3:
            rdot[idx] = np.gradient(r[idx], DT)
    sel = (vx >= 15.0) & np.isfinite(rdot) & (frame["B"].to_numpy(dtype=float) < 0.05)
    n_f, n_r = F2.cargas_por_eixo(vx, a_x, p)
    fyf = (p.b * a_y + p.k2 * rdot) / p.L
    fyr = (p.a * a_y - p.k2 * rdot) / p.L
    delta = -p.k_delta * steer
    af = delta - np.arctan2(vy + p.a * r, vx)
    ar = -np.arctan2(vy - p.b * r, vx)
    return {"alpha_f": af[sel], "y_f": fyf[sel] / n_f[sel], "alpha_r": ar[sel], "y_r": fyr[sel] / n_r[sel],
            "vx": vx[sel]}


def curva_do_pneu(p: F2.ParametrosV2, frame: pd.DataFrame, path: Path, titulo: str) -> Dict[str, object]:
    plt = _plt()
    pts = pontos_dos_eixos(frame, p)
    rng = np.random.default_rng(SEMENTE)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    alpha = np.radians(np.linspace(-16, 16, 801))
    loads = [("parado (g/4)", G / 4.0), ("150 km/h", None), ("270 km/h", None)]
    for ax, axle, key_a, key_y in ((axes[0], "eixo dianteiro", "alpha_f", "y_f"), (axes[1], "eixo traseiro", "alpha_r", "y_r")):
        n_pts = pts[key_a].size
        pick = rng.choice(n_pts, size=min(6000, n_pts), replace=False)
        sc = ax.scatter(np.degrees(pts[key_a][pick]), pts[key_y][pick], s=2, c=pts["vx"][pick] * 3.6, cmap="viridis",
                        alpha=0.35, label="treino (forca do eixo / carga do eixo)")
        for label, n in loads:
            if n is None:
                v = float(label.split()[0]) / 3.6
                nf, nr = F2.cargas_por_eixo(np.array([v]), np.zeros(1), p)
                n = float((nf if axle == "eixo dianteiro" else nr)[0] / 2.0)
            nn = np.full_like(alpha, n)
            D = F2.mu_de(nn, p) * nn
            ax.plot(np.degrees(alpha), F2.forca_lateral(alpha, nn, D, p) / nn, lw=2, label=f"pneu v2, carga de {label}")
        ax.axvline(np.degrees(p.alpha_pico), color="#999", lw=0.8, ls=":")
        ax.axvline(-np.degrees(p.alpha_pico), color="#999", lw=0.8, ls=":")
        ax.set_title(axle)
        ax.set_xlabel("angulo de deriva (graus)")
        ax.set_xlim(-16, 16)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("forca lateral / carga")
    axes[0].legend(fontsize=7, loc="lower right")
    fig.colorbar(sc, ax=axes, label="vx (km/h)", shrink=0.8)
    fig.suptitle(titulo, fontsize=10)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return {"arquivo": str(path), "pontos": int(pts["alpha_f"].size),
            "alpha_pico_graus": float(np.degrees(p.alpha_pico)), "f": p.f, "q": p.q, "mu_ref": p.mu_ref}


def _monte_carlo_v2(state0, U, p, corr, n=CAMINHOS, seed=SEMENTE):
    rng = np.random.default_rng(seed)
    x = np.repeat(state0, n, axis=0)
    out = np.empty((n, U.shape[1] + 1, 3))
    out[:, 0] = x
    for k in range(U.shape[1]):
        u = np.repeat(U[:, k], n, axis=0)
        mean, std, _ = corr.prever(x, u)
        x = F2.passo(x, u, p) + mean + std * rng.standard_normal(mean.shape)
        out[:, k + 1] = x
    return out


def correcao_v1(train: pd.DataFrame, p1: F.Parametros) -> K.Correcao:
    """A correcao da v1 refeita na rodada (400 por regime, semente 37), so para a figura."""
    P = V.passos(train)
    idx, _ = K.subconjunto(P.regime)
    X = np.column_stack([P.S0[idx], P.U[idx]])
    R = P.S1[idx] - F.passo(P.S0[idx], P.U[idx], p1)
    return K.Correcao().ajustar(X, R)


def figuras_c01_c10(modelos, corners, length: float, prefix: Path) -> Dict[str, object]:
    p, p1, corr, sigma, frame, train = modelos
    corr1 = correcao_v1(train, p1)
    out = {}
    for tipo, label, titulo in (("freada", "C01", "A freada da C01 (S do Senna)"),
                                ("curva", "C10", "A curva lenta, a C10 (Bico de Pato)")):
        start = FG.achar_inicio(frame, corners[label], length, tipo)
        if start is None:
            out[label] = {"erro": "nenhuma volta cobre o caso"}
            continue
        out[label] = desenhar(frame, start, p, p1, corr, corr1, titulo, Path(str(prefix) + f"_figura_{label.lower()}_v2.png"))
    return out


def desenhar(frame, start, p, p1, corr, corr1, titulo, path) -> Dict[str, object]:
    plt = _plt()
    S0, U, S = FG.caso(frame, start)
    r0 = F.persistencia(S0, V.H_MAX)
    f2 = F2.malha_aberta(S0, U, p)
    m2 = F2.malha_aberta(S0, U, p, corr)
    f1, _ = F.malha_aberta(S0, U, p1)
    m1, _ = F.malha_aberta(S0, U, p1, corr1)
    mc = _monte_carlo_v2(S0, U, p, corr)
    lo, hi = np.percentile(mc, [5, 95], axis=0)
    t = np.arange(V.H_MAX + 1) * DT
    tu = (np.arange(V.H_MAX) + 0.5) * DT
    labels = [("vx (km/h)", 3.6), ("vy no centro de massa (m/s)", 1.0), ("guinada r (rad/s)", 1.0)]
    fig, axes = plt.subplots(4, 1, figsize=(7.5, 10), sharex=True)
    for q, (label, scale) in enumerate(labels):
        ax = axes[q]
        ax.fill_between(t, lo[:, q] * scale, hi[:, q] * scale, color="#4C78A8", alpha=0.18, label="M1 v2, faixa de 5% a 95%")
        ax.plot(t, S[0, :, q] * scale, color="black", lw=2.2, label="gravado")
        ax.plot(t, m2[0, :, q] * scale, color="#4C78A8", lw=1.8, label="M1 v2 (física v2 + correção)")
        ax.plot(t, f2[0, :, q] * scale, color="#4C78A8", lw=1.2, ls="--", label="física v2 (R1)")
        ax.plot(t, m1[0, :, q] * scale, color="#E45756", lw=1.5, label="M1 v1")
        ax.plot(t, f1[0, :, q] * scale, color="#E45756", lw=1.1, ls="--", label="física v1")
        ax.plot(t, r0[0, :, q] * scale, color="#999999", lw=1.2, ls=":", label="R0 (persistência)")
        ax.set_ylabel(label)
        ax.axvline(0.5, color="#cccccc", lw=0.8)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7, loc="best")
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
        errs[name] = {model: (pred[0, h] - S[0, h]).tolist()
                      for model, pred in (("M1 v2", m2), ("fisica v2", f2), ("M1 v1", m1), ("fisica v1", f1), ("R0", r0))}
    return {"arquivo": str(path), "volta": str(row["lap_id"]), "s_m": float(row["s"]), "vx_kmh": float(row["vx"] * 3.6),
            "erros_vx_vy_r": errs}
