"""Desenho da pista e de trajetorias sobre ela.

Matplotlib, e nao o renderizador do frontend: estas figuras servem para checar o
pipeline (a geometria fechou? a volta caiu dentro dos limites? o tracado
otimizado respeita a pista?), nao para o usuario final. O mapa que o usuario ve
continua sendo o do app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

from ..track.geometry import TrackGeometry


def _edges(track: TrackGeometry) -> Tuple[np.ndarray, np.ndarray]:
    left = track.points + track.normal * track.width_left[:, None]
    right = track.points - track.normal * track.width_right[:, None]
    return left, right


def _close(points: np.ndarray) -> np.ndarray:
    return np.vstack([points, points[:1]])


def draw_track(
    track: TrackGeometry,
    ax: Optional[plt.Axes] = None,
    asphalt: str = "#2b2b2f",
    edge: str = "#8a8a93",
) -> plt.Axes:
    """Asfalto preenchido entre as duas bordas, com a centerline por cima."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 11))
    left, right = _edges(track)
    ring = np.vstack([_close(left), _close(right)[::-1]])
    ax.fill(ring[:, 0], ring[:, 1], color=asphalt, zorder=0)
    for side in (left, right):
        closed = _close(side)
        ax.plot(closed[:, 0], closed[:, 1], color=edge, linewidth=0.8, zorder=1)
    ax.set_aspect("equal")
    ax.set_xlabel("world X (m)")
    ax.set_ylabel("world Z (m)")
    return ax


def plot_curvature_map(
    track: TrackGeometry,
    path: Path,
    title: Optional[str] = None,
    mark_every_m: float = 500.0,
) -> Path:
    """Mapa da pista com a centerline colorida pela curvatura.

    Serve de conferencia da geometria: uma curva que aparece como listra fina de
    cor forte no meio de uma reta e defeito de reconstrucao, nao curva.
    """
    fig, ax = plt.subplots(figsize=(9, 12))
    draw_track(track, ax=ax)

    points = _close(track.points).reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    limit = float(np.percentile(np.abs(track.curvature), 98)) or 1e-3
    collection = LineCollection(
        segments, cmap="coolwarm", norm=plt.Normalize(-limit, limit), linewidth=2.4
    )
    collection.set_array(track.curvature)
    ax.add_collection(collection)
    bar = fig.colorbar(collection, ax=ax, shrink=0.55, pad=0.02)
    bar.set_label("curvatura (1/m) — vermelho: esquerda, azul: direita")

    step = max(int(round(mark_every_m / track.step)), 1)
    for index in range(0, track.size, step):
        ax.plot(track.x[index], track.z[index], "o", color="#ffd166", markersize=4, zorder=3)
        ax.annotate(
            f"{track.s[index]:.0f}",
            (track.x[index], track.z[index]),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=7,
            color="#ffd166",
        )
    ax.plot(track.x[0], track.z[0], "s", color="#06d6a0", markersize=9, zorder=4, label="s = 0")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(title or f"{track.name} — {track.length:.0f} m, grade de {track.step:.1f} m")
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_trajectories(
    track: TrackGeometry,
    trajectories: Sequence[Tuple[str, np.ndarray, np.ndarray]],
    path: Path,
    title: Optional[str] = None,
    colours: Optional[Iterable[str]] = None,
) -> Path:
    """Uma ou mais trajetorias (s, L) desenhadas sobre a pista."""
    fig, ax = plt.subplots(figsize=(9, 12))
    draw_track(track, ax=ax)
    palette = list(colours or ["#06d6a0", "#ef476f", "#ffd166", "#118ab2", "#a78bfa"])
    for index, (label, s_values, lateral) in enumerate(trajectories):
        world = track.to_world(s_values, lateral)
        world = np.vstack([world, world[:1]])
        ax.plot(
            world[:, 0],
            world[:, 1],
            linewidth=1.8,
            color=palette[index % len(palette)],
            label=label,
            zorder=3,
        )
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(title or track.name)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
