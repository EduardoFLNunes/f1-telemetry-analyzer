"""As fases de cada curva, fixas para todas as voltas (secao 1.3).

frenagem [b_k, a_k), entrada [a_k, m1_k), meio [m1_k, m2_k), saida [m2_k, e_k)
e reta seguinte [e_k, b_(k+1)). A geometria (a curvatura da centerline) da a
entrada, o meio e a saida; o pedal das voltas rotuladas, uma vez, da o inicio da
frenagem. Juntas, as 70 fases cobrem a volta.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..comparison.evolution import Segment, corner_segments
from ..comparison.lap_vs_reference import _signed_distance
from ..track.corners import Corner
from ..track.geometry import TrackGeometry

PHASES = ("frenagem", "entrada", "meio", "saida", "reta")
MID_SHARE = 0.6            # o meio: |curvatura| >= 0,6 x a maior da curva
MID_MIN_M = 10.0
EDGE_MIN_M = 4.0           # o que sobra, no minimo, para a entrada e para a saida
BRAKE_MARGIN_M = 10.0
SLOW_KMH = 120.0           # Krause e Bentley, carro com carga aerodinamica
FAST_KMH = 180.0           # escolha registrada (1.3)


def window(track: TrackGeometry, start_s: float, end_s: float) -> np.ndarray:
    """Indices da grade de `start_s` (incluido) a `end_s` (excluido); vazio se forem iguais."""
    # As duas pontas pelo mesmo `index_of`: o fim de uma fase e o comeco da
    # seguinte caem no mesmo ponto, e as 70 fases somam a volta sem sobra.
    start, end = int(track.index_of(start_s)), int(track.index_of(end_s))
    if np.mod(end_s - start_s, track.length) < track.step / 2.0 or start == end:
        return np.array([], dtype=int)
    return (start + np.arange(int(np.mod(end - start, track.size)))) % track.size


def ahead(track: TrackGeometry, a: float, b: float) -> float:
    """Metros de `a` ate `b`, andando para a frente (0 a L)."""
    return float(np.mod(b - a, track.length))


def corner_type(min_speed_kmh: float) -> str:
    if min_speed_kmh < SLOW_KMH:
        return "lenta"
    if min_speed_kmh < FAST_KMH:
        return "media"
    return "rapida"


@dataclass
class CornerPhases:
    k: int
    curva: str
    direcao: int
    a: float
    apice: float
    e: float
    m1: float
    m2: float
    b: float
    b_seguinte: float
    trecho: tuple
    tipo: str
    minima_ia_kmh: float
    reta_m: float
    peso: float
    sem_frenagem: bool

    def bounds(self) -> Dict[str, tuple]:
        return {"frenagem": (self.b, self.a), "entrada": (self.a, self.m1), "meio": (self.m1, self.m2),
                "saida": (self.m2, self.e), "reta": (self.e, self.b_seguinte)}

    def to_dict(self) -> Dict[str, object]:
        out = asdict(self)
        out["trecho"] = list(self.trecho)
        return out


def middle(track: TrackGeometry, corner: Corner) -> tuple:
    """(m1, m2): o trecho em volta do apice com |curvatura| >= 0,6 x a maior, com as folgas de 1.3."""
    idx = window(track, corner.start_s, corner.end_s)
    curv = np.abs(track.curvature[idx])
    peak = int(np.argmax(curv))
    strong = curv >= MID_SHARE * curv[peak]
    lo = hi = peak
    while lo > 0 and strong[lo - 1]:
        lo -= 1
    while hi < idx.size - 1 and strong[hi + 1]:
        hi += 1
    step = track.step
    need = int(np.ceil(MID_MIN_M / step))
    while (hi - lo + 1) < need and (lo > 0 or hi < idx.size - 1):
        if lo > 0:
            lo -= 1
        if (hi - lo + 1) < need and hi < idx.size - 1:
            hi += 1
    edge = int(np.ceil(EDGE_MIN_M / step))
    lo = max(lo, min(edge, idx.size - 1))
    hi = min(hi, max(idx.size - 1 - edge, lo))
    m1 = float(np.mod(corner.start_s + lo * step, track.length))
    m2 = float(np.mod(corner.start_s + (hi + 1) * step, track.length))
    return m1, m2


def braking_start(track: TrackGeometry, corner: Corner, previous: Corner,
                  ai_onsets: Sequence[Optional[float]], driver_onsets: Sequence[Optional[float]]) -> tuple:
    """(b_k, sem_frenagem): a regra de 1.3, em metros antes de a_k, limitada a [e_(k-1), a_k]."""
    def before(values):
        return [_signed_distance(track, corner.start_s, v) for v in values if v is not None]

    ai_d, drv_d = before(ai_onsets), before(driver_onsets)
    ai_brakes = len(ai_d) * 2 > len(ai_onsets) if len(ai_onsets) else False
    drv_brakes = len(drv_d) * 2 > len(driver_onsets) if len(driver_onsets) else False
    if not ai_brakes and not drv_brakes:
        return float(corner.start_s), True
    candidates = []
    if ai_d:
        candidates.append(float(np.median(ai_d)))
    if drv_d:
        candidates.append(float(np.percentile(drv_d, 90)))
    offset = max(candidates) + BRAKE_MARGIN_M
    gap = ahead(track, previous.end_s, corner.start_s)
    offset = float(np.clip(offset, 0.0, gap))
    return float(np.mod(corner.start_s - offset, track.length)), False


def build_phases(track: TrackGeometry, corners: Sequence[Corner], ai_min_speed: Sequence[float],
                 ai_onsets: Sequence[Sequence[Optional[float]]],
                 driver_onsets: Sequence[Sequence[Optional[float]]]) -> List[CornerPhases]:
    """As fases das 14 curvas. `ai_min_speed[k]` e a minima da volta da IA do coach na curva k."""
    segments: List[Segment] = corner_segments(track, corners)
    count = len(corners)
    starts = []
    for k, corner in enumerate(corners):
        starts.append(braking_start(track, corner, corners[k - 1], ai_onsets[k], driver_onsets[k]))
    out = []
    straights = []
    for k, corner in enumerate(corners):
        nxt = starts[(k + 1) % count][0]
        straights.append(ahead(track, corner.end_s, nxt))
    mean_straight = float(np.mean(straights))
    for k, corner in enumerate(corners):
        m1, m2 = middle(track, corner)
        out.append(CornerPhases(
            k=k, curva=corner.label, direcao=int(corner.direction), a=float(corner.start_s),
            apice=float(corner.apex_s), e=float(corner.end_s), m1=m1, m2=m2, b=starts[k][0],
            b_seguinte=starts[(k + 1) % count][0],
            trecho=(float(segments[k].start_s), float(segments[k].end_s)),
            tipo=corner_type(float(ai_min_speed[k])), minima_ia_kmh=float(ai_min_speed[k]),
            reta_m=straights[k], peso=straights[k] / mean_straight, sem_frenagem=starts[k][1],
        ))
    return out


def check_partition(track: TrackGeometry, phases: Sequence[CornerPhases]) -> float:
    """Soma dos comprimentos das 70 fases, em metros: tem de ser o comprimento da volta."""
    total = 0.0
    for cp in phases:
        for start, end in cp.bounds().values():
            total += ahead(track, start, end) if np.mod(end - start, track.length) > 1e-9 else 0.0
    return total
