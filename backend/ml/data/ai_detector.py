"""Detector de volta da IA para as gravacoes antigas (pedido 13, ADR 0014/0015).

O indicador do jogo (`isAIControlled`) so diz quando a IA assume: depois do
primeiro Ctrl+C ele fica ligado ate a sessao do jogo reiniciar, mesmo com o
piloto ao volante (medido na sessao rotulada de 2026-10-04). E as gravacoes
antigas nem tem o campo. Por isso a origem das voltas antigas sai de sinais
medidos, calibrados so nas voltas rotuladas da sessao nova:

1. **A linha.** A referencia e a mediana, ponto a ponto da grade, da lateral
   das voltas da IA da sessao rotulada. Em cada microsetor mede-se a distancia
   lateral mediana ate ela. So contam os microsetores em que a propria IA se
   repete (nas retas e perto do box ela varia ate 2,5 m, e ali a linha nao diz
   nada). Um microsetor `parece IA` ate `lateral_ai_m`, `parece piloto` a
   partir de `lateral_human_m`.
2. **A frenagem.** Nas zonas em que a IA freia sempre no mesmo lugar, a
   distancia entre o inicio de frenagem da volta e o da IA. A mediana entre as
   zonas confirma a linha.
3. **O tempo de volta.** Rapido demais para o piloto, lento demais para a IA.
   Entre os dois limites o tempo nao vota e a linha decide.

A volta e `ia` quando todos os microsetores parecem IA; `humano` quando nenhum
trecho parece IA; `misturada` quando ha um trecho de cada. Um trecho e uma
sequencia de microsetores: uma volta do piloto passa as vezes a poucos
centimetros da linha da IA num microsetor isolado, por acaso, e a IA, quando
pilota, pilota trechos longos. Os sinais precisam concordar; quando nao
concordam, a volta fica `desconhecida`. Voltas com passagem pelo box ficam sem
rotulo.

Os limites estao em `LIMITS` e em `docs/detector_ia.md`, registrados antes de
o detector ser aplicado as voltas antigas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors
from ..validation.empirical import brake_onsets
from .origin import AI, HUMAN, MIXED, UNKNOWN

AI_LIKE = "ia"
HUMAN_LIKE = "humano"
UNDECIDED = "indefinido"
NOT_USED = "fora"

# Um inicio de frenagem da volta so e comparado com o da IA se estiver a ate
# esta distancia dele; sem nenhum, a distancia vale esta (longe).
BRAKE_MATCH_WINDOW_M = 60.0
# Zonas de frenagem da IA: inicios de varias voltas a menos disto entre si.
BRAKE_CLUSTER_GAP_M = 30.0
BRAKE_ZONE_SHARE = 0.5


@dataclass(frozen=True)
class DetectorLimits:
    """Limites do detector, escolhidos so com a sessao rotulada (pedido 13)."""

    lateral_ai_m: float                      # microsetor parece IA ate isto
    lateral_human_m: float                   # ... e parece piloto a partir disto
    ai_run: int                              # trecho da IA: microsetores seguidos que parecem IA
    human_run: int                           # trecho do piloto: microsetores seguidos que parecem piloto
    braking_ai_m: float                      # mediana da distancia ate a frenagem da IA, volta `ia`
    braking_human_m: float                   # ... volta `humano`
    informative_microsectors: Tuple[int, ...] = ()
    braking_zones_m: Tuple[float, ...] = ()
    time_ai_max_s: float = 88.0              # abaixo disto o tempo vota IA (ou misturada)
    time_human_min_s: float = 92.0           # acima disto o tempo vota piloto (ou misturada)


# Registrados em docs/detector_ia.md antes de olhar as voltas antigas. Saem de
# `python -m ml.scripts.detector_ia calibrar` na sessao rotulada de 2026-10-04:
# 13 voltas da IA, 11 do piloto e 2 misturadas, todas limpas.
LIMITS: Optional[DetectorLimits] = DetectorLimits(
    lateral_ai_m=0.25,
    lateral_human_m=0.30,
    ai_run=3,
    human_run=2,
    braking_ai_m=4.0,
    braking_human_m=8.0,
    # Onde a propria IA se repete (todas as 13 voltas a ate 0,25 m da referencia
    # feita sem elas). Fora: as retas e a regiao do box.
    informative_microsectors=(
        3, 4, 5, 6, 7, 8, 9, 10, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27, 28, 30,
        31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 49, 50, 51,
    ),
    # Zonas em que a IA repete o inicio de frenagem a ate 4 m em 90 % das voltas.
    braking_zones_m=(126.0, 248.0, 1206.0, 2016.0, 2200.0, 2360.0, 2622.0, 3122.1),
    time_ai_max_s=88.0,
    time_human_min_s=92.0,
)


@dataclass
class AIReference:
    lateral: np.ndarray                  # (grade,) mediana da lateral das voltas da IA
    braking_s: np.ndarray                # inicios de frenagem da IA (um por zona)
    lap_ids: List[str] = field(default_factory=list)


def _circular_gap(a: float, b: float, length: float) -> float:
    d = abs(a - b) % length
    return min(d, length - d)


def braking_zones(onsets: Sequence[np.ndarray], track: TrackGeometry, share: float = BRAKE_ZONE_SHARE) -> np.ndarray:
    """Zonas de frenagem comuns a varias voltas: mediana dos inicios de cada zona."""
    laps = len(onsets)
    pooled = np.sort(np.concatenate([np.asarray(o, dtype=float) for o in onsets])) if laps else np.array([])
    if pooled.size == 0:
        return pooled
    clusters: List[List[float]] = [[pooled[0]]]
    for value in pooled[1:]:
        if value - clusters[-1][-1] > BRAKE_CLUSTER_GAP_M:
            clusters.append([])
        clusters[-1].append(value)
    if len(clusters) > 1 and clusters[0][0] + track.length - clusters[-1][-1] <= BRAKE_CLUSTER_GAP_M:
        clusters[0] = [v - track.length for v in clusters.pop()] + clusters[0]
    zones = [np.median(c) % track.length for c in clusters if len(c) >= share * laps]
    return np.sort(np.asarray(zones, dtype=float))


def build_reference(grids: Mapping[str, pd.DataFrame], track: TrackGeometry) -> AIReference:
    """A linha da IA: mediana por ponto da grade das voltas dadas."""
    if not grids:
        raise ValueError("nenhuma volta da IA para a referencia")
    lateral = np.nanmedian(np.vstack([g["lateral"].to_numpy(dtype=float) for g in grids.values()]), axis=0)
    onsets = [brake_onsets(g["brake"].to_numpy(dtype=float), track) for g in grids.values()]
    return AIReference(lateral=lateral, braking_s=braking_zones(onsets, track), lap_ids=list(grids))


def zone_distances(grid: pd.DataFrame, zones: Sequence[float], track: TrackGeometry) -> np.ndarray:
    """Distancia do inicio de frenagem da volta mais perto de cada zona (limitada a janela)."""
    onsets = brake_onsets(grid["brake"].to_numpy(dtype=float), track)
    out = []
    for zone in zones:
        gaps = [_circular_gap(o, zone, track.length) for o in onsets]
        out.append(min(min(gaps) if gaps else BRAKE_MATCH_WINDOW_M, BRAKE_MATCH_WINDOW_M))
    return np.asarray(out, dtype=float)


def microsector_distances(
    grid: pd.DataFrame, reference: AIReference, track: TrackGeometry, sectors: Microsectors,
    zones: Optional[Sequence[float]] = None,
) -> pd.DataFrame:
    """Por microsetor: distancia lateral mediana ate a IA e distancia ate a frenagem da IA."""
    gap = np.abs(grid["lateral"].to_numpy(dtype=float) - reference.lateral)
    lateral = np.full(sectors.count, np.nan)
    for k in range(sectors.count):
        values = gap[sectors.index == k]
        values = values[np.isfinite(values)]
        if values.size:
            lateral[k] = float(np.median(values))
    braking = np.full(sectors.count, np.nan)
    zones = reference.braking_s if zones is None else np.asarray(zones, dtype=float)
    for zone, value in zip(zones, zone_distances(grid, zones, track)):
        k = int(sectors.of(zone))
        braking[k] = value if np.isnan(braking[k]) else max(braking[k], value)
    return pd.DataFrame({"microsetor": np.arange(sectors.count), "lateral_m": lateral, "frenagem_m": braking})


# ------------------------------------------------------------ calibracao ---

def informative_microsectors(ai_distances: Sequence[np.ndarray], limit_m: float) -> Tuple[int, ...]:
    """Microsetores em que toda volta da IA fica ate `limit_m` da referencia sem ela."""
    stacked = np.vstack([np.asarray(d, dtype=float) for d in ai_distances])
    return tuple(int(k) for k in np.flatnonzero(np.nanmax(stacked, axis=0) <= limit_m))


def reliable_zones(ai_zone_distances: np.ndarray, zones: Sequence[float], limit_m: float, share: float = 0.9) -> Tuple[float, ...]:
    """Zonas em que a IA freia a ate `limit_m` da referencia em pelo menos `share` das voltas."""
    d = np.asarray(ai_zone_distances, dtype=float)
    keep = np.mean(d <= limit_m, axis=0) >= share
    return tuple(round(float(z), 1) for z, ok in zip(zones, keep) if ok)


# ------------------------------------------------------------ decisao ---

def _longest_run(mask: Sequence[bool]) -> int:
    best = current = 0
    for value in mask:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def microsector_states(lateral_m: Sequence[float], limits: DetectorLimits) -> List[str]:
    """`ia`, `humano`, `indefinido` nos microsetores informativos; `fora` nos outros."""
    informative = set(limits.informative_microsectors)
    states = []
    for k, value in enumerate(lateral_m):
        if k not in informative:
            states.append(NOT_USED)
        elif not np.isfinite(value):
            states.append(UNDECIDED)
        elif value <= limits.lateral_ai_m:
            states.append(AI_LIKE)
        elif value >= limits.lateral_human_m:
            states.append(HUMAN_LIKE)
        else:
            states.append(UNDECIDED)
    return states


def line_label(states: Sequence[str], limits: DetectorLimits) -> str:
    """Origem pela linha, contando trechos (sequencias) nos microsetores informativos."""
    used = [s for s in states if s != NOT_USED]
    if not used:
        return UNKNOWN
    ai_run = _longest_run([s == AI_LIKE for s in used])
    human_run = _longest_run([s == HUMAN_LIKE for s in used])
    if all(s == AI_LIKE for s in used):
        return AI
    if ai_run < limits.ai_run and human_run >= limits.human_run:
        return HUMAN
    if ai_run >= limits.ai_run and human_run >= limits.human_run:
        return MIXED
    return UNKNOWN


def braking_agrees(line: str, median_m: float, limits: DetectorLimits) -> bool:
    """A frenagem confirma a linha? So vale para `ia` e `humano`."""
    if line == AI:
        return bool(np.isfinite(median_m) and median_m <= limits.braking_ai_m)
    if line == HUMAN:
        return bool(np.isfinite(median_m) and median_m >= limits.braking_human_m)
    return True


def time_votes(lap_time_s: float, limits: DetectorLimits) -> Tuple[str, ...]:
    """Origens compativeis com o tempo de volta.

    Rapida (abaixo do limite da IA): IA, ou misturada com um trecho curto do
    piloto (a volta 8 da sessao rotulada fechou em 86,1 s). Lenta (acima do
    limite do piloto): piloto, ou misturada. Entre os dois: o tempo nao vota.
    """
    if not np.isfinite(lap_time_s):
        return (AI, HUMAN, MIXED)
    if lap_time_s < limits.time_ai_max_s:
        return (AI, MIXED)
    if lap_time_s > limits.time_human_min_s:
        return (HUMAN, MIXED)
    return (AI, HUMAN, MIXED)


def pit_lap(grid: pd.DataFrame, sectors: Microsectors, lateral_m: float = 10.0, speed_kmh: float = 90.0) -> bool:
    """Passou pelo box: longe da pista e devagar perto da linha de chegada (pedido 12)."""
    near_line = np.isin(sectors.index, [0, 1, 2, 3, sectors.count - 3, sectors.count - 2, sectors.count - 1])
    lateral = np.abs(grid["lateral"].to_numpy(dtype=float))[near_line]
    speed = grid["speed_kmh"].to_numpy(dtype=float)[near_line]
    return bool(np.nanmax(lateral) > lateral_m and np.nanmin(speed) < speed_kmh)


def classify_lap(
    grid: pd.DataFrame,
    lap_time_s: float,
    reference: AIReference,
    track: TrackGeometry,
    sectors: Microsectors,
    limits: DetectorLimits,
) -> Dict[str, object]:
    """Tudo o que o detector diz de uma volta."""
    empty = {"linha": None, "frenagem_mediana_m": None, "microsetores_ia": None,
             "microsetores_humano": None, "trecho_ia": None, "trecho_humano": None}
    if pit_lap(grid, sectors):
        return {"origem_detector": UNKNOWN, "motivo": "box", **empty}
    distances = microsector_distances(grid, reference, track, sectors, zones=limits.braking_zones_m)
    states = microsector_states(distances["lateral_m"].to_numpy(dtype=float), limits)
    used = [s for s in states if s != NOT_USED]
    line = line_label(states, limits)
    braking = zone_distances(grid, limits.braking_zones_m, track)
    median = float(np.median(braking)) if braking.size else float("nan")
    details = {
        "linha": line,
        "frenagem_mediana_m": median,
        "microsetores_ia": int(sum(s == AI_LIKE for s in used)),
        "microsetores_humano": int(sum(s == HUMAN_LIKE for s in used)),
        "trecho_ia": _longest_run([s == AI_LIKE for s in used]),
        "trecho_humano": _longest_run([s == HUMAN_LIKE for s in used]),
    }
    if line == UNKNOWN:
        return {"origem_detector": UNKNOWN, "motivo": "linha indefinida", **details}
    if not braking_agrees(line, median, limits):
        return {"origem_detector": UNKNOWN, "motivo": f"linha diz {line}, frenagem discorda", **details}
    if line not in time_votes(lap_time_s, limits):
        return {"origem_detector": UNKNOWN, "motivo": f"linha diz {line}, tempo de {lap_time_s:.1f} s discorda", **details}
    return {"origem_detector": line, "motivo": "sinais concordam", **details}
