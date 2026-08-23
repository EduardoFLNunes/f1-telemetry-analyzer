"""Comparacao entre a volta do jogador e o tracado de referencia.

Duas unidades de comparacao, porque as perguntas sao de naturezas diferentes:

* **microsetor** responde "onde eu perdi tempo" -- corte regular de ~72 m, o
  mesmo que o painel de analise assistida do app ja usa;
* **curva** responde "por que" -- ponto de frenagem, ponto de tangencia,
  velocidade minima e velocidade de saida so existem em relacao a uma curva.

Tudo e medido na grade da pista, entao "o jogador freou 12 m depois" e uma
diferenca de distancia de verdade, e nao uma diferenca de indice de amostra
entre duas voltas que tem numeros de amostras diferentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..track.corners import Corner
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors, split_times

# Pedal a partir do qual conta como "esta freando" / "esta acelerando". Nao e
# zero: o piloto encosta no freio antes de frear de verdade, e um limiar em zero
# marcaria o ponto de frenagem no roce.
BRAKE_ONSET = 0.15
THROTTLE_ONSET = 0.60

# Quanto antes da curva procurar o ponto de frenagem.
BRAKING_LOOKBACK_M = 250.0


@dataclass
class SectorComparison:
    """O que aconteceu num microsetor."""

    index: int
    label: str
    start_s: float
    end_s: float
    lap_time_s: float
    reference_time_s: float
    delta_s: float
    lateral_deviation_mean_m: float
    lateral_deviation_max_m: float
    speed_delta_mean_kmh: float
    speed_delta_min_kmh: float

    @property
    def lost_time(self) -> bool:
        return self.delta_s > 0


@dataclass
class CornerComparison:
    """O que aconteceu numa curva."""

    label: str
    start_s: float
    apex_s: float
    end_s: float
    braking_point_s: Optional[float]
    reference_braking_point_s: Optional[float]
    braking_delta_m: Optional[float]
    throttle_point_s: Optional[float]
    reference_throttle_point_s: Optional[float]
    throttle_delta_m: Optional[float]
    min_speed_kmh: float
    reference_min_speed_kmh: float
    min_speed_delta_kmh: float
    exit_speed_kmh: float
    reference_exit_speed_kmh: float
    exit_speed_delta_kmh: float
    apex_lateral_m: float
    reference_apex_lateral_m: float
    apex_lateral_delta_m: float

    def notes(self) -> List[str]:
        """Leitura em texto do que os numeros dizem."""
        out: List[str] = []
        if self.braking_delta_m is not None and abs(self.braking_delta_m) >= 5.0:
            side = "depois" if self.braking_delta_m > 0 else "antes"
            out.append(f"freou {abs(self.braking_delta_m):.0f} m {side} da referencia")
        if self.throttle_delta_m is not None and abs(self.throttle_delta_m) >= 5.0:
            side = "depois" if self.throttle_delta_m > 0 else "antes"
            out.append(f"acelerou {abs(self.throttle_delta_m):.0f} m {side}")
        if abs(self.min_speed_delta_kmh) >= 3.0:
            side = "acima" if self.min_speed_delta_kmh > 0 else "abaixo"
            out.append(f"velocidade minima {abs(self.min_speed_delta_kmh):.1f} km/h {side}")
        if abs(self.exit_speed_delta_kmh) >= 3.0:
            side = "acima" if self.exit_speed_delta_kmh > 0 else "abaixo"
            out.append(f"saida {abs(self.exit_speed_delta_kmh):.1f} km/h {side}")
        if abs(self.apex_lateral_delta_m) >= 1.0:
            out.append(f"tangencia {abs(self.apex_lateral_delta_m):.1f} m fora da referencia")
        return out


@dataclass
class LapComparison:
    lap_id: str
    lap_time_s: float
    reference_time_s: float
    sectors: List[SectorComparison] = field(default_factory=list)
    corners: List[CornerComparison] = field(default_factory=list)

    @property
    def delta_s(self) -> float:
        return self.lap_time_s - self.reference_time_s

    def worst_sectors(self, count: int = 5) -> List[SectorComparison]:
        return sorted(self.sectors, key=lambda item: -item.delta_s)[:count]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "microsetor": sector.label,
                    "delta_s": round(sector.delta_s, 3),
                    "desvio_med_m": round(sector.lateral_deviation_mean_m, 2),
                    "desvio_max_m": round(sector.lateral_deviation_max_m, 2),
                    "delta_v_med": round(sector.speed_delta_mean_kmh, 1),
                    "delta_v_min": round(sector.speed_delta_min_kmh, 1),
                }
                for sector in self.sectors
            ]
        )


def _first_crossing(
    values: np.ndarray, threshold: float, indices: np.ndarray, track: TrackGeometry
) -> Optional[float]:
    """Distancia do primeiro ponto da janela em que o canal passa do limiar."""
    selected = values[indices]
    above = np.where(selected >= threshold)[0]
    return float(track.s[indices[above[0]]]) if above.size else None


def _window(track: TrackGeometry, start_s: float, end_s: float) -> np.ndarray:
    """Indices da grade entre duas distancias, dando a volta se preciso."""
    start = int(track.index_of(start_s))
    span = int(round(np.mod(end_s - start_s, track.length) / track.step)) + 1
    return (start + np.arange(span)) % track.size


def _signed_distance(track: TrackGeometry, a: float, b: float) -> float:
    """`a - b` em metros de pista, no intervalo (-L/2, L/2]."""
    return float(np.mod(a - b + track.length / 2.0, track.length) - track.length / 2.0)


def compare_sectors(
    lap: pd.DataFrame,
    reference: pd.DataFrame,
    track: TrackGeometry,
    sectors: Microsectors,
    lap_total: Optional[float] = None,
    reference_total: Optional[float] = None,
) -> List[SectorComparison]:
    """Diferenca microsetor a microsetor."""
    lap_splits = split_times(lap["elapsed_s"].to_numpy(dtype=float), sectors, track, lap_total)
    reference_splits = split_times(
        reference["elapsed_s"].to_numpy(dtype=float), sectors, track, reference_total
    )

    deviation = lap["lateral"].to_numpy(dtype=float) - reference["lateral"].to_numpy(dtype=float)
    speed_delta = lap["speed_kmh"].to_numpy(dtype=float) - reference["speed_kmh"].to_numpy(dtype=float)

    out: List[SectorComparison] = []
    for index in range(sectors.count):
        mask = sectors.index == index
        out.append(
            SectorComparison(
                index=index,
                label=sectors.label(index),
                start_s=float(sectors.edges_s[index]),
                end_s=float(sectors.edges_s[index + 1]),
                lap_time_s=float(lap_splits[index]),
                reference_time_s=float(reference_splits[index]),
                delta_s=float(lap_splits[index] - reference_splits[index]),
                lateral_deviation_mean_m=float(np.mean(np.abs(deviation[mask]))),
                lateral_deviation_max_m=float(np.max(np.abs(deviation[mask]))),
                speed_delta_mean_kmh=float(np.mean(speed_delta[mask])),
                speed_delta_min_kmh=float(np.min(speed_delta[mask])),
            )
        )
    return out


def compare_corners(
    lap: pd.DataFrame,
    reference: pd.DataFrame,
    track: TrackGeometry,
    corners: Sequence[Corner],
) -> List[CornerComparison]:
    """Diferenca curva a curva: onde freou, onde acelerou, quanto carregou."""
    out: List[CornerComparison] = []
    for corner in corners:
        approach = _window(track, corner.start_s - BRAKING_LOOKBACK_M, corner.apex_s)
        inside = _window(track, corner.start_s, corner.end_s)
        exit_window = _window(track, corner.apex_s, corner.end_s)

        lap_brake = _first_crossing(lap["brake"].to_numpy(dtype=float), BRAKE_ONSET, approach, track)
        ref_brake = _first_crossing(
            reference["brake"].to_numpy(dtype=float), BRAKE_ONSET, approach, track
        )
        lap_throttle = _first_crossing(
            lap["throttle"].to_numpy(dtype=float), THROTTLE_ONSET, exit_window, track
        )
        ref_throttle = _first_crossing(
            reference["throttle"].to_numpy(dtype=float), THROTTLE_ONSET, exit_window, track
        )

        lap_speed = lap["speed_kmh"].to_numpy(dtype=float)
        ref_speed = reference["speed_kmh"].to_numpy(dtype=float)
        apex_index = int(track.index_of(corner.apex_s))

        out.append(
            CornerComparison(
                label=corner.label,
                start_s=corner.start_s,
                apex_s=corner.apex_s,
                end_s=corner.end_s,
                braking_point_s=lap_brake,
                reference_braking_point_s=ref_brake,
                braking_delta_m=(
                    _signed_distance(track, lap_brake, ref_brake)
                    if lap_brake is not None and ref_brake is not None
                    else None
                ),
                throttle_point_s=lap_throttle,
                reference_throttle_point_s=ref_throttle,
                throttle_delta_m=(
                    _signed_distance(track, lap_throttle, ref_throttle)
                    if lap_throttle is not None and ref_throttle is not None
                    else None
                ),
                min_speed_kmh=float(lap_speed[inside].min()),
                reference_min_speed_kmh=float(ref_speed[inside].min()),
                min_speed_delta_kmh=float(lap_speed[inside].min() - ref_speed[inside].min()),
                exit_speed_kmh=float(lap_speed[inside][-1]),
                reference_exit_speed_kmh=float(ref_speed[inside][-1]),
                exit_speed_delta_kmh=float(lap_speed[inside][-1] - ref_speed[inside][-1]),
                apex_lateral_m=float(lap["lateral"].to_numpy(dtype=float)[apex_index]),
                reference_apex_lateral_m=float(
                    reference["lateral"].to_numpy(dtype=float)[apex_index]
                ),
                apex_lateral_delta_m=float(
                    lap["lateral"].to_numpy(dtype=float)[apex_index]
                    - reference["lateral"].to_numpy(dtype=float)[apex_index]
                ),
            )
        )
    return out


def compare_lap(
    lap_id: str,
    lap: pd.DataFrame,
    reference: pd.DataFrame,
    track: TrackGeometry,
    sectors: Microsectors,
    corners: Sequence[Corner],
    lap_total: Optional[float] = None,
    reference_total: Optional[float] = None,
) -> LapComparison:
    """Comparacao completa entre uma volta e a referencia."""
    lap_time = float(lap_total or lap["elapsed_s"].max())
    reference_time = float(reference_total or reference["elapsed_s"].max())
    return LapComparison(
        lap_id=lap_id,
        lap_time_s=lap_time,
        reference_time_s=reference_time,
        sectors=compare_sectors(lap, reference, track, sectors, lap_time, reference_time),
        corners=compare_corners(lap, reference, track, corners),
    )
