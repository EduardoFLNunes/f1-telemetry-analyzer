"""Evolucao do piloto, sessao a sessao (peca B, primeira versao; pedido 16).

As regras foram registradas antes da primeira rodada, em
`docs/store_v2_e_evolucao.md` (secao 1.4):

* **voltas** -- do store v2, `humano`, equipamento `atual`, com o relogio
  conferido e sem `relogio_suspeito`;
* **sessao** -- as gravacoes do mesmo dia;
* **referencia** -- a volta da IA do coach (`volta_ia`);
* **unidades** -- as 14 curvas de `detect_corners`, cada uma com o trecho que
  vai do meio da reta anterior ao meio da seguinte; os 14 trechos cobrem a
  volta, e a soma das perdas e a diferenca de tempo de volta;
* **diferenca consistente** -- o intervalo de 90% (bootstrap) da perda mediana
  para a IA nao inclui zero; com menos de 5 voltas na sessao, "poucos dados".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..data.origin import CURRENT_EQUIPMENT, HUMAN
from ..track.corners import Corner
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors, split_times
from .lap_vs_reference import BRAKE_ONSET, _signed_distance, _window

MIN_LAPS = 5
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_LEVEL = 0.90
BOOTSTRAP_SEED = 20261004
STABILITY_SESSIONS = 3
STABILITY_LIMIT_S = 0.5
TOP_CORNERS = 3

CONSISTENT = "diferenca_consistente"
NOT_CONSISTENT = "sem_diferenca_consistente"
FEW_DATA = "poucos_dados"


# ------------------------------------------------------------ voltas ---

def driver_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """As voltas que falam do piloto de hoje: humano, equipamento atual, relogio conferido e nao suspeito."""
    mask = (
        (laps["origem"] == HUMAN)
        & (laps["equipamento"] == CURRENT_EQUIPMENT)
        & laps["relogio_verificado"].fillna(False).astype(bool)
        & ~laps["relogio_suspeito"].fillna(True).astype(bool)
    )
    if "valid" in laps.columns:
        mask &= laps["valid"].astype(bool)
    return laps[mask]


def session_of(session_id: str) -> str:
    """A sessao e o dia: `2026-10-04_03-21-52_vhe_interlagos` -> `2026-10-04`."""
    return str(session_id)[:10]


# ------------------------------------------------------------ trechos ---

def _midpoint(a: float, b: float, length: float) -> float:
    return float(np.mod(a + np.mod(b - a, length) / 2.0, length))


@dataclass(frozen=True)
class Segment:
    corner: Corner
    start_s: float
    end_s: float


def corner_segments(track: TrackGeometry, corners: Sequence[Corner]) -> List[Segment]:
    """Um trecho por curva, do meio da reta anterior ao meio da seguinte; juntos cobrem a volta."""
    out = []
    count = len(corners)
    for k, corner in enumerate(corners):
        previous, following = corners[k - 1], corners[(k + 1) % count]
        out.append(Segment(
            corner=corner,
            start_s=_midpoint(previous.end_s, corner.start_s, track.length),
            end_s=_midpoint(corner.end_s, following.start_s, track.length),
        ))
    return out


def time_at(elapsed: np.ndarray, total: float, track: TrackGeometry, s_value: float) -> float:
    """Tempo da volta no ponto `s` (o relogio vai de 0 em s = 0 ao periodo na linha)."""
    xs = np.append(track.s, track.length)
    ys = np.append(np.asarray(elapsed, dtype=float), float(total))
    return float(np.interp(np.mod(s_value, track.length), xs, ys))


def segment_time(elapsed: np.ndarray, total: float, track: TrackGeometry, segment: Segment) -> float:
    """Tempo do trecho; o que cruza a linha soma o fim e o comeco da mesma volta."""
    start = time_at(elapsed, total, track, segment.start_s)
    end = time_at(elapsed, total, track, segment.end_s)
    return float(np.mod(end - start, total))


def braking_point(brake: np.ndarray, track: TrackGeometry, start_s: float, apex_s: float) -> Optional[float]:
    """Primeiro ponto, do inicio do trecho ao apice, em que o freio passa de < 0,15 para >= 0,15."""
    indices = _window(track, start_s, apex_s)
    on = np.nan_to_num(np.asarray(brake, dtype=float)[indices]) >= BRAKE_ONSET
    rising = np.flatnonzero(on[1:] & ~on[:-1]) + 1
    return float(track.s[indices[rising[0]]]) if rising.size else None


def lap_corner_features(
    lap: pd.DataFrame, lap_total: float, ref: pd.DataFrame, ref_total: float,
    track: TrackGeometry, segments: Sequence[Segment],
) -> List[Dict[str, Optional[float]]]:
    """Por curva: perda para a IA, frenagem, lateral no apice e minima, volta menos IA."""
    lap_elapsed, ref_elapsed = lap["elapsed_s"].to_numpy(dtype=float), ref["elapsed_s"].to_numpy(dtype=float)
    lap_speed, ref_speed = lap["speed_kmh"].to_numpy(dtype=float), ref["speed_kmh"].to_numpy(dtype=float)
    lap_lateral, ref_lateral = lap["lateral"].to_numpy(dtype=float), ref["lateral"].to_numpy(dtype=float)
    out = []
    for segment in segments:
        corner = segment.corner
        lap_brake = braking_point(lap["brake"].to_numpy(dtype=float), track, segment.start_s, corner.apex_s)
        ref_brake = braking_point(ref["brake"].to_numpy(dtype=float), track, segment.start_s, corner.apex_s)
        inside = _window(track, corner.start_s, corner.end_s)
        apex = int(track.index_of(corner.apex_s))
        out.append({
            "perda_s": segment_time(lap_elapsed, lap_total, track, segment)
            - segment_time(ref_elapsed, ref_total, track, segment),
            "ia_freia": ref_brake is not None,
            "frenagem_vs_ia_m": (
                _signed_distance(track, lap_brake, ref_brake) if lap_brake is not None and ref_brake is not None
                else None
            ),
            "lateral_apice_vs_ia_m": float(lap_lateral[apex] - ref_lateral[apex]),
            "velocidade_minima_vs_ia_kmh": float(np.nanmin(lap_speed[inside]) - np.nanmin(ref_speed[inside])),
        })
    return out


# --------------------------------------------------------- estatistica ---

def bootstrap_median_interval(values: Sequence[float], resamples: int = BOOTSTRAP_RESAMPLES,
                              level: float = BOOTSTRAP_LEVEL, seed: int = BOOTSTRAP_SEED) -> Tuple[float, float]:
    """Intervalo percentil da mediana, reamostrando as voltas com reposicao."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    medians = np.median(values[rng.integers(0, values.size, size=(resamples, values.size))], axis=1)
    tail = (1.0 - level) / 2.0 * 100.0
    return float(np.percentile(medians, tail)), float(np.percentile(medians, 100.0 - tail))


def consistency(losses: Sequence[float], min_laps: int = MIN_LAPS) -> Dict[str, object]:
    """A situacao de uma curva na sessao: consistente (e de que lado), nao consistente ou poucos dados."""
    losses = np.asarray([v for v in losses if v is not None and np.isfinite(v)], dtype=float)
    if losses.size < min_laps:
        return {"situacao": FEW_DATA, "lado": None, "intervalo_90_s": None}
    low, high = bootstrap_median_interval(losses)
    if low > 0.0:
        side = "perde"
    elif high < 0.0:
        side = "ganha"
    else:
        side = None
    return {
        "situacao": CONSISTENT if side else NOT_CONSISTENT,
        "lado": side,
        "intervalo_90_s": [round(low, 4), round(high, 4)],
    }


def spread(values: Sequence[Optional[float]], digits: int = 4) -> Optional[Dict[str, float]]:
    """Mediana e intervalo interquartil dos valores que existem."""
    values = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if values.size == 0:
        return None
    p25, median, p75 = np.percentile(values, [25, 50, 75])
    return {"mediana": round(float(median), digits), "p25": round(float(p25), digits),
            "p75": round(float(p75), digits), "iqr": round(float(p75 - p25), digits), "voltas": int(values.size)}


def trend(values: Sequence[float]) -> Optional[float]:
    """Inclinacao da reta de minimos quadrados, por sessao. None com menos de 2 sessoes."""
    values = np.asarray(values, dtype=float)
    if values.size < 2:
        return None
    return float(np.polyfit(np.arange(values.size, dtype=float), values, 1)[0])


def stability(medians: Sequence[float], sessions: int = STABILITY_SESSIONS,
              limit_s: float = STABILITY_LIMIT_S) -> Dict[str, object]:
    """Criterio do ADR 0015: a mediana das ultimas 3 sessoes varia menos de 0,5 s."""
    medians = [float(m) for m in medians]
    if len(medians) < sessions:
        return {"limite_s": limit_s, "sessoes_necessarias": sessions, "sessoes_disponiveis": len(medians),
                "amplitude_s": None, "estabilizou": None,
                "situacao": f"ainda nao avaliavel: {len(medians)} de {sessions} sessoes"}
    last = medians[-sessions:]
    amplitude = max(last) - min(last)
    return {"limite_s": limit_s, "sessoes_necessarias": sessions, "sessoes_disponiveis": len(medians),
            "amplitude_s": round(amplitude, 3), "estabilizou": bool(amplitude < limit_s),
            "situacao": "estabilizou" if amplitude < limit_s else "ainda variando"}


# ------------------------------------------------------------ sessao ---

def session_report(
    session: str, laps: pd.DataFrame, lap_grids: Dict[str, pd.DataFrame], ref: pd.DataFrame,
    ref_total: float, track: TrackGeometry, segments: Sequence[Segment], sectors: Microsectors,
) -> Dict[str, object]:
    """O JSON de uma sessao (formato em `docs/store_v2_e_evolucao.md`)."""
    laps = laps.sort_values(["session_id", "sequence"])
    times = laps["lap_time_s"].to_numpy(dtype=float)
    per_lap = {}
    for lap_id, total in zip(laps["lap_id"], times):
        per_lap[lap_id] = lap_corner_features(lap_grids[lap_id], float(total), ref, ref_total, track, segments)

    corners = []
    for k, segment in enumerate(segments):
        rows = [per_lap[lap_id][k] for lap_id in laps["lap_id"]]
        losses = [r["perda_s"] for r in rows]
        corner = segment.corner
        ai_brakes = bool(rows and rows[0]["ia_freia"])
        loss_spread = spread(losses)
        corners.append({
            "curva": corner.label,
            "indice": k + 1,
            "trecho_m": [round(segment.start_s, 1), round(segment.end_s, 1)],
            "curva_m": [round(corner.start_s, 1), round(corner.end_s, 1)],
            "apice_m": round(corner.apex_s, 1),
            "perda_para_ia_s": loss_spread,
            **consistency(losses),
            "ia_freia": ai_brakes,
            "frenagem_vs_ia_m": spread([r["frenagem_vs_ia_m"] for r in rows], 1) if ai_brakes else None,
            "lateral_apice_vs_ia_m": spread([r["lateral_apice_vs_ia_m"] for r in rows], 2),
            "velocidade_minima_vs_ia_kmh": (
                {"mediana": round(float(np.median([r["velocidade_minima_vs_ia_kmh"] for r in rows])), 1)}
                if rows else None
            ),
            "por_volta": [
                {"volta": lap_id, **{key: (None if value is None else round(float(value), 4))
                                     for key, value in per_lap[lap_id][k].items() if key != "ia_freia"}}
                for lap_id in laps["lap_id"]
            ],
        })

    ref_splits = split_times(ref["elapsed_s"].to_numpy(dtype=float), sectors, track, total=ref_total)
    sector_losses = np.array([
        split_times(lap_grids[lap_id]["elapsed_s"].to_numpy(dtype=float), sectors, track, total=float(total))
        - ref_splits
        for lap_id, total in zip(laps["lap_id"], times)
    ])
    best, median = float(times.min()), float(np.median(times))
    return {
        "formato": "evolucao-sessao/1",
        "sessao": session,
        "gravacoes": sorted(laps["session_id"].unique().tolist()),
        "resumo": {
            "voltas": int(times.size),
            "melhor_s": round(best, 3),
            "mediana_s": round(median, 3),
            "desvio_s": round(float(np.std(times, ddof=1)), 3) if times.size > 1 else None,
            "volta_da_ia_s": round(ref_total, 3),
            "mediana_menos_ia_s": round(median - ref_total, 3),
            "melhor_menos_ia_s": round(best - ref_total, 3),
            "poucos_dados": bool(times.size < MIN_LAPS),
        },
        "voltas": [
            {"volta": lap_id, "gravacao": sid, "tempo_s": round(float(t), 3)}
            for lap_id, sid, t in zip(laps["lap_id"], laps["session_id"], times)
        ],
        "curvas": corners,
        "microsetores": [
            {"microsetor": i, "perda_mediana_s": round(float(np.median(sector_losses[:, i])), 4),
             "p25_s": round(float(np.percentile(sector_losses[:, i], 25)), 4),
             "p75_s": round(float(np.percentile(sector_losses[:, i], 75)), 4)}
            for i in range(sector_losses.shape[1])
        ],
    }


def summary_report(sessions: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """O JSON de resumo: a serie das sessoes, a tendencia e o criterio do ADR 0015."""
    ordered = sorted(sessions, key=lambda r: r["sessao"])
    medians = [r["resumo"]["mediana_s"] for r in ordered]
    latest = ordered[-1] if ordered else None
    top = []
    if latest:
        ranked = sorted(latest["curvas"], key=lambda c: -(c["perda_para_ia_s"] or {}).get("mediana", float("-inf")))
        for corner in ranked[:TOP_CORNERS]:
            series = []
            for report in ordered:
                match = next(c for c in report["curvas"] if c["curva"] == corner["curva"])
                series.append({"sessao": report["sessao"],
                               "perda_mediana_s": (match["perda_para_ia_s"] or {}).get("mediana"),
                               "situacao": match["situacao"]})
            values = [p["perda_mediana_s"] for p in series if p["perda_mediana_s"] is not None]
            top.append({"curva": corner["curva"], "serie": series,
                        "tendencia_s_por_sessao": None if trend(values) is None else round(trend(values), 4)})
    slope = trend(medians)
    return {
        "formato": "evolucao-resumo/1",
        "sessoes": [
            {"sessao": r["sessao"], **{k: r["resumo"][k] for k in (
                "voltas", "melhor_s", "mediana_s", "desvio_s", "mediana_menos_ia_s", "melhor_menos_ia_s", "poucos_dados")},
             "curvas_com_diferenca_consistente": [c["curva"] for c in r["curvas"] if c["situacao"] == CONSISTENT]}
            for r in ordered
        ],
        "tendencia_mediana_s_por_sessao": None if slope is None else round(slope, 4),
        "curvas_de_maior_perda": top,
        "criterio_adr_0015": stability(medians),
    }
