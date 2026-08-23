"""Graficos de telemetria contra a distancia na pista.

O eixo e sempre `s`, nunca o tempo. Duas voltas plotadas contra o tempo nao se
sobrepoem em lugar nenhum -- o mesmo instante e um ponto de pista diferente em
cada uma. Contra a distancia, a diferenca vertical entre as curvas e a diferenca
de pilotagem no mesmo pedaco de asfalto, que e a unica leitura util.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..track.corners import Corner
from ..track.geometry import TrackGeometry

BACKGROUND = "#15161a"
FOREGROUND = "#e6e6ea"
GRID = "#2c2e36"


def _style(ax: plt.Axes, ylabel: str) -> None:
    ax.set_facecolor(BACKGROUND)
    ax.tick_params(colors=FOREGROUND, labelsize=8)
    ax.set_ylabel(ylabel, color=FOREGROUND, fontsize=9)
    ax.grid(color=GRID, linewidth=0.6)
    for spine in ax.spines.values():
        spine.set_color(GRID)


def _mark_corners(ax: plt.Axes, corners: Optional[Sequence[Corner]]) -> None:
    for corner in corners or []:
        ax.axvspan(corner.start_s, corner.end_s, color="#ffffff", alpha=0.05, zorder=0)
        ax.axvline(corner.apex_s, color="#ffd166", alpha=0.35, linewidth=0.8, zorder=1)


def plot_lap_comparison(
    track: TrackGeometry,
    lap: pd.DataFrame,
    reference: pd.DataFrame,
    path: Path,
    corners: Optional[Sequence[Corner]] = None,
    lap_label: str = "volta",
    reference_label: str = "referencia",
    title: Optional[str] = None,
) -> Path:
    """Velocidade, pedais e posicao lateral das duas voltas, contra a distancia."""
    figure, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    figure.patch.set_facecolor(BACKGROUND)

    channels = (
        ("speed_kmh", "velocidade (km/h)"),
        ("brake", "freio"),
        ("throttle", "acelerador"),
        ("lateral", "posicao lateral (m)"),
    )
    for ax, (column, label) in zip(axes, channels):
        _mark_corners(ax, corners)
        if column in reference.columns:
            ax.plot(track.s, reference[column], color="#ffd166", linewidth=1.2, label=reference_label)
        if column in lap.columns:
            ax.plot(track.s, lap[column], color="#06d6a0", linewidth=1.2, label=lap_label)
        _style(ax, label)

    # A faixa util da pista entra no painel de posicao lateral: sem ela, "3 m a
    # esquerda" nao diz se sobrou pista ou se o carro estava na zebra.
    low, high = track.corridor()
    axes[3].plot(track.s, high, color="#8a8a93", linewidth=0.7, linestyle="--")
    axes[3].plot(track.s, low, color="#8a8a93", linewidth=0.7, linestyle="--")

    axes[0].legend(loc="lower right", fontsize=8, facecolor=BACKGROUND, labelcolor=FOREGROUND)
    axes[-1].set_xlabel("distancia na pista (m)", color=FOREGROUND, fontsize=9)
    figure.suptitle(title or "comparacao por distancia", color=FOREGROUND, fontsize=11)
    figure.tight_layout()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130, facecolor=BACKGROUND)
    plt.close(figure)
    return path


def plot_time_delta(
    track: TrackGeometry,
    lap_elapsed: np.ndarray,
    reference_elapsed: np.ndarray,
    path: Path,
    corners: Optional[Sequence[Corner]] = None,
    title: Optional[str] = None,
) -> Path:
    """Delta acumulado ao longo da volta.

    A inclinacao e o que interessa, e nao o valor: onde a linha sobe, o tempo
    esta sendo perdido *ali*. Um patamar alto so quer dizer que ja se perdeu
    antes.
    """
    delta = np.asarray(lap_elapsed, dtype=float) - np.asarray(reference_elapsed, dtype=float)
    figure, ax = plt.subplots(figsize=(14, 4))
    figure.patch.set_facecolor(BACKGROUND)
    _mark_corners(ax, corners)
    ax.axhline(0.0, color="#8a8a93", linewidth=0.8)
    ax.fill_between(track.s, 0.0, delta, where=delta > 0, color="#ef476f", alpha=0.5)
    ax.fill_between(track.s, 0.0, delta, where=delta < 0, color="#06d6a0", alpha=0.5)
    ax.plot(track.s, delta, color=FOREGROUND, linewidth=1.0)
    _style(ax, "delta acumulado (s)")
    ax.set_xlabel("distancia na pista (m)", color=FOREGROUND, fontsize=9)
    ax.set_title(title or "onde o tempo foi", color=FOREGROUND, fontsize=11)
    figure.tight_layout()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130, facecolor=BACKGROUND)
    plt.close(figure)
    return path


def plot_evolution_history(history: Sequence[dict], path: Path) -> Path:
    """Custo e diversidade ao longo das geracoes.

    A diversidade e o que diz se a busca ainda esta procurando: quando ela cai a
    zero, a populacao virou copias do mesmo individuo e as geracoes seguintes
    nao vao achar nada.
    """
    frame = pd.DataFrame(list(history))
    figure, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    figure.patch.set_facecolor(BACKGROUND)

    axes[0].plot(frame["generation"], frame["best_cost"], color="#06d6a0", label="melhor")
    axes[0].plot(frame["generation"], frame["mean_cost"], color="#ffd166", label="medio")
    _style(axes[0], "custo (s)")
    axes[0].legend(fontsize=8, facecolor=BACKGROUND, labelcolor=FOREGROUND)

    axes[1].plot(frame["generation"], frame["diversity_m"], color="#118ab2")
    _style(axes[1], "diversidade (m)")
    axes[1].set_xlabel("geracao", color=FOREGROUND, fontsize=9)

    figure.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130, facecolor=BACKGROUND)
    plt.close(figure)
    return path
