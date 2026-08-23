"""Comparacao visual entre a volta real, a prevista e o tracado otimizado.

As tres trajetorias tem origens diferentes e isso e o que torna a comparacao
delicada:

* a **volta real** foi cronometrada -- o tempo dela e medido;
* a **volta prevista** e a saida da LSTM geradora consultada com perda zero, e o
  tempo dela seria uma previsao da propria rede;
* o **tracado otimizado** nunca foi dirigido, entao o tempo dele so pode ser
  simulado.

Comparar tempo medido com tempo previsto com tempo simulado e comparar tres
relogios. Por isso os graficos de tempo passam as tres trajetorias pelo **mesmo
simulador**: a diferenca que sobra e diferenca de tracado, que e a pergunta. O
tempo medido da volta real aparece separado, como aferricao do vies do modelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..track.corners import Corner
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors
from .telemetry_plots import BACKGROUND, FOREGROUND, GRID, _style
from .track_plots import draw_track


@dataclass
class TrajectorySeries:
    """Uma trajetoria pronta para desenhar, com tudo que a descreve."""

    label: str
    lateral: np.ndarray
    colour: str
    speed_kmh: Optional[np.ndarray] = None      # perfil proprio, se houver
    elapsed_s: Optional[np.ndarray] = None      # relogio simulado, na grade
    splits: Optional[np.ndarray] = None         # tempo por microsetor, simulado
    lap_time_s: Optional[float] = None
    measured_time_s: Optional[float] = None     # so a volta real tem
    linestyle: str = "-"
    width: float = 1.8


def _legend(ax: plt.Axes, **kwargs) -> None:
    ax.legend(
        facecolor=BACKGROUND,
        edgecolor=GRID,
        labelcolor=FOREGROUND,
        fontsize=8,
        **kwargs,
    )


# ------------------------------------------------------------- mapa XY ------

def plot_track_map(
    track: TrackGeometry,
    series: Sequence[TrajectorySeries],
    path: Path,
    corners: Optional[Sequence[Corner]] = None,
    insets: Sequence[float] = (),
    title: Optional[str] = None,
) -> Path:
    """Mapa XY de Interlagos com as trajetorias sobrepostas.

    `insets` recebe distancias em metros; cada uma vira um recorte ampliado ao
    lado do mapa. No mapa inteiro as tres linhas ficam a menos de um milimetro
    umas das outras -- a pista tem 4334 m de comprimento e 14 m de largura, e
    numa figura de uma pagina esses 14 m sao a espessura de um traco. Sem
    ampliar algum trecho, o mapa mostra o formato da pista e nada mais.
    """
    columns = 1 + (1 if insets else 0)
    figure = plt.figure(figsize=(9 + 5 * (columns - 1), 12))
    figure.patch.set_facecolor(BACKGROUND)
    grid = figure.add_gridspec(max(len(insets), 1), columns, width_ratios=[3, 2][:columns])

    ax = figure.add_subplot(grid[:, 0])
    draw_track(track, ax=ax)
    for item in series:
        world = track.to_world(track.s, item.lateral)
        world = np.vstack([world, world[:1]])
        ax.plot(
            world[:, 0],
            world[:, 1],
            color=item.colour,
            linewidth=item.width,
            linestyle=item.linestyle,
            label=item.label,
            zorder=3,
        )

    for corner in corners or []:
        # O rotulo vai para **fora** da curva, e nao para um deslocamento fixo
        # em pixels: por fora e onde sempre ha espaco vazio, e por dentro o
        # texto caia em cima do asfalto e das proprias linhas.
        index = int(track.index_of(corner.apex_s))
        outward = -corner.direction * (track.width()[index] / 2.0 + 26.0)
        point = track.to_world(np.array([corner.apex_s]), np.array([outward]))[0]
        ax.annotate(
            corner.label,
            point,
            fontsize=7,
            color="#8a8a93",
            ha="center",
            va="center",
        )

    ax.set_facecolor(BACKGROUND)
    ax.tick_params(colors=FOREGROUND, labelsize=8)
    ax.set_xlabel("world X (m)", color=FOREGROUND, fontsize=9)
    ax.set_ylabel("world Z (m)", color=FOREGROUND, fontsize=9)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    _legend(ax, loc="upper right")

    for position, centre_s in enumerate(insets):
        zoom = figure.add_subplot(grid[position, 1])
        draw_track(track, ax=zoom)
        for item in series:
            world = track.to_world(track.s, item.lateral)
            zoom.plot(
                world[:, 0], world[:, 1], color=item.colour, linewidth=2.4,
                linestyle=item.linestyle, zorder=3,
            )
        focus = track.to_world(np.array([centre_s]), np.array([0.0]))[0]
        # Apertado de proposito: em 70 m o recorte capturava o trecho paralelo
        # da pista e mostrava duas fitas de asfalto desconexas.
        span = 45.0
        zoom.set_xlim(focus[0] - span, focus[0] + span)
        zoom.set_ylim(focus[1] - span, focus[1] + span)
        zoom.set_facecolor(BACKGROUND)
        zoom.set_xticks([])
        zoom.set_yticks([])
        for spine in zoom.spines.values():
            spine.set_color(GRID)
        inside = [c for c in (corners or []) if c.contains(centre_s, track.length)]
        label = f"s = {centre_s:.0f} m"
        if inside:
            label = f"{inside[0].label} · {label}"
        zoom.set_title(label, color=FOREGROUND, fontsize=9)

    figure.suptitle(title or "Interlagos — traçados comparados", color=FOREGROUND, fontsize=12)
    figure.tight_layout()
    return _save(figure, path)


# ------------------------------------------------- diferenca por microsetor --

def plot_microsector_delta(
    track: TrackGeometry,
    sectors: Microsectors,
    series: Sequence[TrajectorySeries],
    baseline: TrajectorySeries,
    path: Path,
    corners: Optional[Sequence[Corner]] = None,
    title: Optional[str] = None,
) -> Path:
    """Diferenca de tempo por microsetor contra a trajetoria de referencia.

    Barras para cima sao tempo perdido; para baixo, ganho. O painel de baixo
    acumula: a **inclinacao** dele e onde o tempo esta sendo feito, e o valor
    final e a diferenca da volta inteira.
    """
    others = [item for item in series if item is not baseline]
    figure, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True, height_ratios=[2, 1])
    figure.patch.set_facecolor(BACKGROUND)

    centres = 0.5 * (sectors.edges_s[:-1] + sectors.edges_s[1:])
    width = (sectors.edges_s[1] - sectors.edges_s[0]) / (len(others) + 1)

    for shift, item in enumerate(others):
        delta = np.asarray(item.splits, dtype=float) - np.asarray(baseline.splits, dtype=float)
        axes[0].bar(
            centres + (shift - (len(others) - 1) / 2) * width,
            delta,
            width=width,
            color=item.colour,
            label=f"{item.label} ({delta.sum():+.3f} s)",
            zorder=3,
        )

    axes[0].axhline(0.0, color=FOREGROUND, linewidth=0.9)
    _style(axes[0], "Δ por microsetor (s)")
    _legend(axes[0], loc="upper left")
    axes[0].set_title(
        title or f"diferença contra {baseline.label}", color=FOREGROUND, fontsize=11
    )

    for item in others:
        delta = np.asarray(item.splits, dtype=float) - np.asarray(baseline.splits, dtype=float)
        axes[1].plot(
            sectors.edges_s[1:], np.cumsum(delta), color=item.colour, linewidth=1.6
        )
    axes[1].axhline(0.0, color=FOREGROUND, linewidth=0.9)
    _style(axes[1], "Δ acumulado (s)")
    axes[1].set_xlabel("distância na pista (m)", color=FOREGROUND, fontsize=9)

    for ax in axes:
        for corner in corners or []:
            ax.axvspan(corner.start_s, corner.end_s, color="#ffffff", alpha=0.05, zorder=0)

    figure.tight_layout()
    return _save(figure, path)


# ------------------------------------------------------ perfis por distancia --

def plot_profiles(
    track: TrackGeometry,
    series: Sequence[TrajectorySeries],
    path: Path,
    corners: Optional[Sequence[Corner]] = None,
    title: Optional[str] = None,
) -> Path:
    """Velocidade e posição lateral das trajetórias, contra a distância."""
    figure, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    figure.patch.set_facecolor(BACKGROUND)

    for item in series:
        if item.speed_kmh is not None:
            axes[0].plot(
                track.s, item.speed_kmh, color=item.colour, linewidth=item.width,
                linestyle=item.linestyle, label=item.label,
            )
        axes[1].plot(
            track.s, item.lateral, color=item.colour, linewidth=item.width,
            linestyle=item.linestyle, label=item.label,
        )

    low, high = track.corridor()
    axes[1].plot(track.s, high, color="#8a8a93", linewidth=0.7, linestyle="--")
    axes[1].plot(track.s, low, color="#8a8a93", linewidth=0.7, linestyle="--")
    axes[1].fill_between(track.s, low, high, color="#ffffff", alpha=0.04, zorder=0)

    _style(axes[0], "velocidade (km/h)")
    _style(axes[1], "posição lateral (m)")
    axes[1].set_xlabel("distância na pista (m)", color=FOREGROUND, fontsize=9)
    _legend(axes[0], loc="lower right")

    for ax in axes:
        for corner in corners or []:
            ax.axvspan(corner.start_s, corner.end_s, color="#ffffff", alpha=0.06, zorder=0)

    figure.suptitle(title or "perfis por distância", color=FOREGROUND, fontsize=12)
    figure.tight_layout()
    return _save(figure, path)


# ------------------------------------------------------- separacao lateral ---

def plot_lateral_separation(
    track: TrackGeometry,
    series: Sequence[TrajectorySeries],
    baseline: TrajectorySeries,
    path: Path,
    corners: Optional[Sequence[Corner]] = None,
    title: Optional[str] = None,
) -> Path:
    """O quanto cada trajetória se afasta da referência, em metros de pista.

    Existe porque no mapa XY as três linhas se sobrepõem: a diferença entre elas
    é de metros, e a pista tem quilômetros. Aqui a diferença é o próprio eixo.
    """
    figure, ax = plt.subplots(figsize=(14, 4.5))
    figure.patch.set_facecolor(BACKGROUND)

    for item in series:
        if item is baseline:
            continue
        separation = item.lateral - baseline.lateral
        ax.plot(track.s, separation, color=item.colour, linewidth=1.6, label=item.label)
        ax.fill_between(track.s, 0.0, separation, color=item.colour, alpha=0.18)

    ax.axhline(0.0, color=FOREGROUND, linewidth=0.9)
    _style(ax, f"afastamento de {baseline.label} (m)")
    ax.set_xlabel("distância na pista (m)", color=FOREGROUND, fontsize=9)
    _legend(ax, loc="upper right")
    for corner in corners or []:
        ax.axvspan(corner.start_s, corner.end_s, color="#ffffff", alpha=0.05, zorder=0)

    ax.set_title(title or "onde as linhas divergem", color=FOREGROUND, fontsize=11)
    figure.tight_layout()
    return _save(figure, path)


def _save(figure: plt.Figure, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130, facecolor=BACKGROUND)
    plt.close(figure)
    return path
