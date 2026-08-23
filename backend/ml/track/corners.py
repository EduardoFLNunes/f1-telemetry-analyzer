"""Deteccao de curvas a partir da curvatura da centerline.

Microsetor e um corte regular: serve para comparar tempo. Curva e um corte
fisico: e o que permite falar em ponto de frenagem, ponto de tangencia,
velocidade minima e velocidade de saida -- as grandezas que o enunciado pede e
que so existem em relacao a uma curva, nao a um retangulo de 72 m.

As duas coexistem porque respondem perguntas diferentes, e a curva e derivada da
pista (sempre a mesma) e nao da volta (que muda a cada tentativa).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .geometry import TrackGeometry

# Curvatura acima da qual o trecho conta como curva. 1/200 m: numa reta de
# verdade a centerline reconstruida fica bem abaixo disso, e a curva mais aberta
# de Interlagos (a Curva do Sol) fica acima.
CORNER_CURVATURE_THRESHOLD = 1.0 / 200.0

# Trecho curvo mais curto que isto e ruido de reconstrucao que sobrou.
MIN_CORNER_LENGTH_M = 25.0

# Duas curvas separadas por menos que isto sao a mesma curva com um ponto de
# inflexao no meio -- desde que virem para o mesmo lado.
MERGE_GAP_M = 30.0


@dataclass(frozen=True)
class Corner:
    """Uma curva da pista, medida na centerline."""

    index: int
    start_s: float
    apex_s: float
    end_s: float
    direction: int            # +1 esquerda, -1 direita
    min_radius_m: float
    mean_radius_m: float
    length_m: float

    @property
    def label(self) -> str:
        side = "esq" if self.direction > 0 else "dir"
        return f"C{self.index + 1:02d}-{side}"

    def contains(self, s_value: float, track_length: float) -> bool:
        span = np.mod(self.end_s - self.start_s, track_length)
        offset = np.mod(float(s_value) - self.start_s, track_length)
        return bool(offset <= span)


def _runs(mask: np.ndarray) -> List[tuple]:
    """Trechos contiguos de True, tratando a pista como fechada."""
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]])
    edges = np.diff(padded.astype(int))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    runs = list(zip(starts.tolist(), ends.tolist()))
    # Se a pista comeca e termina em curva, e a mesma curva cortada pela linha.
    if len(runs) > 1 and mask[0] and mask[-1]:
        first, last = runs[0], runs[-1]
        runs = runs[1:-1] + [(last[0], first[1] + mask.size)]
    return runs


def detect_corners(
    track: TrackGeometry,
    threshold: float = CORNER_CURVATURE_THRESHOLD,
    min_length_m: float = MIN_CORNER_LENGTH_M,
    merge_gap_m: float = MERGE_GAP_M,
) -> List[Corner]:
    """Curvas da pista, em ordem de distancia."""
    curvature = track.curvature
    size = track.size

    corners: List[Corner] = []
    for direction in (1, -1):
        mask = (curvature * direction) > threshold
        for start, end in _runs(mask):
            indices = np.arange(start, end) % size
            if indices.size * track.step < min_length_m:
                continue
            corners.append((direction, indices))

    # Junta trechos do mesmo sentido separados por um vao curto: a Curva do Sol
    # sai da deteccao em dois pedacos porque a curvatura afrouxa no meio dela.
    corners.sort(key=lambda item: track.s[item[1][0]])
    merged: List[tuple] = []
    for direction, indices in corners:
        if merged:
            previous_direction, previous_indices = merged[-1]
            gap = (indices[0] - previous_indices[-1]) % size
            if previous_direction == direction and gap * track.step <= merge_gap_m:
                merged[-1] = (
                    direction,
                    np.concatenate(
                        [previous_indices, np.arange(previous_indices[-1] + 1, previous_indices[-1] + 1 + gap) % size, indices]
                    ),
                )
                continue
        merged.append((direction, indices))

    out: List[Corner] = []
    for position, (direction, indices) in enumerate(merged):
        local = np.abs(curvature[indices])
        apex = int(indices[int(np.argmax(local))])
        peak = float(local.max())
        mean = float(local.mean())
        out.append(
            Corner(
                index=position,
                start_s=float(track.s[indices[0]]),
                apex_s=float(track.s[apex]),
                end_s=float(track.s[indices[-1]]),
                direction=int(direction),
                min_radius_m=float(1.0 / peak) if peak > 0 else float("inf"),
                mean_radius_m=float(1.0 / mean) if mean > 0 else float("inf"),
                length_m=float(indices.size * track.step),
            )
        )
    return out


def corner_index_map(track: TrackGeometry, corners: List[Corner]) -> np.ndarray:
    """Vetor da grade com o indice da curva em cada ponto, -1 nas retas."""
    out = np.full(track.size, -1, dtype=int)
    for corner in corners:
        start = track.index_of(corner.start_s)
        span = int(round(corner.length_m / track.step))
        indices = (np.arange(start, start + span)) % track.size
        out[indices] = corner.index
    return out
