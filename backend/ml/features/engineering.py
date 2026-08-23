"""Atributos por ponto de pista, a partir de uma volta ja na grade.

Tres familias, e a separacao entre elas importa para o modelo:

* **pista** — curvatura, largura, elevacao. Iguais em toda volta. Dizem onde o
  carro esta, e nao o que o piloto fez.
* **pilotagem** — velocidade, pedais, volante, marcha, dinamica. Mudam a cada
  volta. Sao o que o modelo tem de aprender a relacionar com tempo.
* **desempenho** — quanto esta volta perdeu para a melhor do piloto, neste
  microsetor e nesta volta.

A terceira familia e a que impede o modelo de virar uma media. Uma rede treinada
so com pista+pilotagem para prever "a linha" aprende a linha *tipica*, que e a
media das voltas boas e ruins. Recebendo tambem o quanto a volta perdeu, ela
aprende a relacao entre pilotagem e desempenho -- e ai da para pedir a ela a
pilotagem correspondente a perda zero, que nao e a media de nada.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..track.corners import Corner, corner_index_map
from ..track.geometry import TrackGeometry, _closed_derivative, _smoothing_window
from ..track.microsectors import Microsectors, split_times
from ..track.trajectory import curvature as trajectory_curvature
from ..track.trajectory import lateral_derivative

# Atributos de pista: nao dependem da volta.
TRACK_FEATURES = (
    "curvature",
    "curvature_abs",
    "curvature_rate",
    "track_width",
    "elevation_slope",
    "corner_flag",
    "distance_to_apex",
)

# Atributos de pilotagem: e o que a volta trouxe.
DRIVING_FEATURES = (
    "speed_kmh",
    "throttle",
    "brake",
    "steering",
    "gear",
    "rpm",
    "lateral_g",
    "longitudinal_g",
    "lateral",
    "lateral_rate",
    "path_curvature",
    "distance_to_left_edge",
    "distance_to_right_edge",
    "wheel_slip",
)

# Atributos de desempenho: a condicao sob a qual o modelo e consultado.
PERFORMANCE_FEATURES = (
    "sector_loss_s",
    "lap_loss_s",
)

FEATURE_COLUMNS = TRACK_FEATURES + DRIVING_FEATURES + PERFORMANCE_FEATURES

# Alvos que o modelo aprende a produzir.
TARGET_COLUMNS = ("lateral", "speed_kmh", "brake", "throttle")


def _rate(values: np.ndarray, track: TrackGeometry) -> np.ndarray:
    window = _smoothing_window(12.0, track.step)
    return _closed_derivative(np.asarray(values, dtype=float), track.step, window, order=3)


def track_features(
    track: TrackGeometry, corners: Optional[Sequence[Corner]] = None
) -> pd.DataFrame:
    """Atributos que dependem so da pista. Calculados uma vez e reusados."""
    data: Dict[str, np.ndarray] = {
        "curvature": track.curvature,
        "curvature_abs": np.abs(track.curvature),
        "curvature_rate": _rate(track.curvature, track),
        "track_width": track.width(),
        "elevation_slope": _rate(track.elevation, track),
    }

    if corners:
        index_map = corner_index_map(track, list(corners))
        data["corner_flag"] = (index_map >= 0).astype(float)
        # Distancia assinada ate o apice da curva mais proxima a frente: e o que
        # da ao modelo a nocao de "falta tanto para o ponto de tangencia", que e
        # o que governa frenagem e entrada.
        apexes = np.array([corner.apex_s for corner in corners], dtype=float)
        forward = np.mod(apexes[None, :] - track.s[:, None], track.length)
        data["distance_to_apex"] = forward.min(axis=1)
    else:
        data["corner_flag"] = np.zeros(track.size)
        data["distance_to_apex"] = np.zeros(track.size)

    frame = pd.DataFrame(data)
    frame.index.name = "grid_index"
    return frame


def lap_features(
    grid: pd.DataFrame,
    track: TrackGeometry,
    sectors: Microsectors,
    corners: Optional[Sequence[Corner]] = None,
    best_splits: Optional[np.ndarray] = None,
    best_lap_time: Optional[float] = None,
    cached_track_features: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Volta na grade -> volta com atributos.

    `best_splits` e `best_lap_time` sao a referencia do piloto. Sem eles as
    colunas de desempenho saem zeradas, que e o certo para uma volta nova sendo
    avaliada em tempo real -- ela ainda nao tem com o que se comparar.
    """
    out = grid.copy()
    base = cached_track_features if cached_track_features is not None else track_features(track, corners)
    for column in base.columns:
        out[column] = base[column].to_numpy()

    lateral = out["lateral"].to_numpy(dtype=float)
    out["lateral_rate"] = lateral_derivative(track, lateral)
    out["path_curvature"] = trajectory_curvature(track, lateral)
    # Quanto sobra de pista de cada lado. A distancia ate a borda e o que
    # distingue "usou a pista toda" de "sobrou meio metro", e e a mesma medida
    # que o algoritmo evolutivo usa como restricao.
    out["distance_to_left_edge"] = out["width_left"].to_numpy(dtype=float) - lateral
    out["distance_to_right_edge"] = out["width_right"].to_numpy(dtype=float) + lateral

    elapsed = out["elapsed_s"].to_numpy(dtype=float)
    lap_time = (
        float(out["lap_time_s"].iloc[0])
        if "lap_time_s" in out.columns
        else float(np.nanmax(elapsed) - np.nanmin(elapsed))
    )
    splits = split_times(elapsed, sectors, track, total=lap_time)
    out["sector_time_s"] = splits[sectors.index]

    if best_splits is not None:
        loss = splits - np.asarray(best_splits, dtype=float)
        out["sector_loss_s"] = loss[sectors.index]
    else:
        out["sector_loss_s"] = 0.0

    out["lap_time_s_total"] = lap_time
    out["lap_loss_s"] = lap_time - float(best_lap_time) if best_lap_time else 0.0

    for column in FEATURE_COLUMNS:
        if column not in out.columns:
            out[column] = 0.0
    return out


def feature_matrix(frame: pd.DataFrame, columns: Sequence[str] = FEATURE_COLUMNS) -> np.ndarray:
    """(grid, n_features) pronto para o modelo, sem NaN."""
    matrix = frame.reindex(columns=list(columns)).to_numpy(dtype=float)
    return np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)


def build_feature_frames(
    store,
    track: TrackGeometry,
    sectors: Microsectors,
    corners: Optional[Sequence[Corner]] = None,
    reference=None,
    lap_ids: Optional[Sequence[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """Monta a tabela de atributos de cada volta do store.

    Os atributos de pista sao calculados uma vez e reaproveitados: sao iguais em
    toda volta, e recalcula-los 128 vezes custa mais do que todo o resto junto.
    """
    cached = track_features(track, corners)
    best_splits = reference.best_splits if reference is not None else None
    best_time = reference.best_lap_time if reference is not None else None

    wanted = list(lap_ids) if lap_ids is not None else list(store.lap_ids)
    frames: Dict[str, pd.DataFrame] = {}
    for lap_id in wanted:
        grid = store.lap(lap_id)
        # O store guarda so o que nao da para recalcular; a geometria volta a
        # entrar aqui porque `lap_features` precisa da largura da pista.
        grid = grid.assign(
            s=track.s,
            curvature=track.curvature,
            width_left=track.width_left,
            width_right=track.width_right,
            elevation=track.elevation,
        )
        frames[lap_id] = lap_features(
            grid,
            track,
            sectors,
            corners=corners,
            best_splits=best_splits,
            best_lap_time=best_time,
            cached_track_features=cached,
        )
    return frames
