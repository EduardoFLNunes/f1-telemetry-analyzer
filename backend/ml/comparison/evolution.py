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

Emenda de 05/10 (secao 1.6): sessao deixa de ser o dia do nome da gravacao.
Gravacoes separadas por mais de 3 h sem gravar sao sessoes diferentes, e a
sessao leva a data em que terminou (`group_sessions`): a sessao de 04/10 23:51
a 05/10 00:31 e a de 05/10, e nao se junta a da madrugada de 04/10.

Emenda de 04/10 (pedido 17, secao 1.5): o inicio da frenagem de uma curva e
procurado do apice da curva anterior ate o apice dela. Do comeco do trecho,
a frenagem da C10 (Bico de Pato), que comeca depois do apice da C09 e antes
do trecho da C10, nao aparecia.
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
SESSION_GAP_H = 3.0
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


def group_sessions(periods: Dict[str, Dict[str, object]], gap_h: float = SESSION_GAP_H) -> Dict[str, str]:
    """Gravacao -> sessao (emenda de 05/10).

    `periods[gravacao] = {"inicio": ISO, "duracao_s": s}`. Uma pausa de mais de
    `gap_h` horas entre o fim de uma gravacao e o inicio da seguinte abre uma
    sessao nova. A chave da sessao e a data em que ela terminou; se duas
    sessoes terminam no mesmo dia, a segunda ganha `-2` (a terceira, `-3`).
    """
    from datetime import datetime, timedelta

    spans = []
    for recording, period in periods.items():
        start = datetime.fromisoformat(str(period["inicio"]))
        end = start + timedelta(seconds=float(period.get("duracao_s") or 0.0))
        spans.append((start, end, recording))
    spans.sort()
    groups: List[List[tuple]] = []
    for span in spans:
        if groups and (span[0] - max(e for _, e, _ in groups[-1])) <= timedelta(hours=gap_h):
            groups[-1].append(span)
        else:
            groups.append([span])
    out: Dict[str, str] = {}
    used: Dict[str, int] = {}
    for group in groups:
        day = max(e for _, e, _ in group).date().isoformat()
        used[day] = used.get(day, 0) + 1
        key = day if used[day] == 1 else f"{day}-{used[day]}"
        for _, _, recording in group:
            out[recording] = key
    return out


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
    """Primeiro ponto, de `start_s` ao apice, em que o freio passa de < 0,15 para >= 0,15.

    `start_s` e o apice da curva anterior (emenda de 04/10, pedido 17).
    """
    indices = _window(track, start_s, apex_s)
    # O ponto anterior a janela entra so para ver a subida no primeiro ponto dela:
    # uma freada que comeca exatamente em `start_s` esta dentro da janela.
    extended = np.concatenate([[(indices[0] - 1) % track.size], indices])
    on = np.nan_to_num(np.asarray(brake, dtype=float)[extended]) >= BRAKE_ONSET
    rising = np.flatnonzero(on[1:] & ~on[:-1])
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
    for k, segment in enumerate(segments):
        corner = segment.corner
        search_from = segments[k - 1].corner.apex_s
        lap_brake = braking_point(lap["brake"].to_numpy(dtype=float), track, search_from, corner.apex_s)
        ref_brake = braking_point(ref["brake"].to_numpy(dtype=float), track, search_from, corner.apex_s)
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


# ------------------------------------------------------------ tecnica ---
#
# Pedido 18 (secao 1.7): medidas descritivas. Nada daqui entra na situacao das
# curvas, nos criterios ou no coach; o bloco `tecnica` so le o store.

STEER_SHARE = 0.25
TYRE_COLUMNS = ("tyre_core_temp_fl", "tyre_core_temp_fr", "tyre_core_temp_rl", "tyre_core_temp_rr")
BRAKE_TEMP_COLUMNS = ("brake_temp_fl", "brake_temp_fr", "brake_temp_rl", "brake_temp_rr")
CAUSE_NOTE = "A correlacao nao separa causa: o pneu esquenta e o piloto melhora ao mesmo tempo."


def _column(frame: pd.DataFrame, name: str) -> Optional[np.ndarray]:
    if name not in frame.columns:
        return None
    values = frame[name].to_numpy(dtype=float)
    return values if np.isfinite(values).any() else None


def steer_values(frame: pd.DataFrame) -> Optional[np.ndarray]:
    """O volante bruto (`steer_angle`); `steering` onde ele nao existir."""
    raw = _column(frame, "steer_angle")
    return raw if raw is not None else _column(frame, "steering")


def grip_usage(frame: pd.DataFrame, track: TrackGeometry, segment: Segment) -> Optional[float]:
    """p95 da aceleracao combinada, sqrt(g lateral^2 + g longitudinal^2), no trecho da curva."""
    lat, lon = _column(frame, "lateral_g"), _column(frame, "longitudinal_g")
    if lat is None or lon is None:
        return None
    window = _window(track, segment.start_s, segment.end_s)
    combined = np.hypot(lat[window], lon[window])
    combined = combined[np.isfinite(combined)]
    return float(np.percentile(combined, 95)) if combined.size else None


def brake_and_steer_m(frame: pd.DataFrame, track: TrackGeometry, previous_apex_s: float,
                      corner: Corner) -> Optional[float]:
    """Metros, do apice anterior ao apice, com freio >= 0,15 e volante >= 25% do maior da volta na curva."""
    brake, steer = _column(frame, "brake"), steer_values(frame)
    if brake is None or steer is None:
        return None
    steer = np.abs(steer)
    largest = np.nanmax(steer[_window(track, corner.start_s, corner.end_s)])
    if not np.isfinite(largest) or largest <= 0.0:
        return None
    window = _window(track, previous_apex_s, corner.apex_s)
    both = (np.nan_to_num(brake[window]) >= BRAKE_ONSET) & (np.nan_to_num(steer[window]) >= STEER_SHARE * largest)
    return float(both.sum() * track.step)


def chained_braking(brake: np.ndarray, track: TrackGeometry, previous_apex_s: float, apex_s: float) -> Optional[bool]:
    """A sequencia de freio que contem o maior freio da janela comeca antes do apice anterior?

    None quando nao ha freio de 0,15 ou mais na janela (sem frenagem).
    """
    window = _window(track, previous_apex_s, apex_s)
    values = np.nan_to_num(np.asarray(brake, dtype=float))
    inside = values[window]
    if inside.max() < BRAKE_ONSET:
        return None
    start = int(np.argmax(inside))
    while start > 0 and inside[start - 1] >= BRAKE_ONSET:
        start -= 1
    if start > 0:
        return False
    return bool(values[(window[0] - 1) % track.size] >= BRAKE_ONSET)


def brake_temp_max(frame: pd.DataFrame, track: TrackGeometry, previous_apex_s: float, apex_s: float) -> Optional[float]:
    """A maior temperatura de freio nos pontos da janela com freio >= 0,15. None sem o canal."""
    temps = [_column(frame, c) for c in BRAKE_TEMP_COLUMNS]
    brake = _column(frame, "brake")
    if brake is None or all(t is None for t in temps):
        return None
    window = _window(track, previous_apex_s, apex_s)
    braking = window[np.nan_to_num(brake[window]) >= BRAKE_ONSET]
    values = np.concatenate([t[braking] for t in temps if t is not None]) if braking.size else np.array([])
    values = values[np.isfinite(values)]
    return float(values.max()) if values.size else None


def tyre_temperatures(frame: pd.DataFrame) -> Optional[Dict[str, float]]:
    """Media dos 4 pneus em s = 0 e ao longo da volta, e da dianteira e da traseira ao longo da volta."""
    columns = [_column(frame, c) for c in TYRE_COLUMNS]
    if any(c is None for c in columns):
        return None
    stack = np.vstack(columns)
    return {
        "media_s0_c": round(float(np.nanmean(stack[:, 0])), 2),
        "media_volta_c": round(float(np.nanmean(stack)), 2),
        "dianteira_c": round(float(np.nanmean(stack[:2])), 2),
        "traseira_c": round(float(np.nanmean(stack[2:])), 2),
    }


def _summary(values: Sequence[Optional[float]], digits: int = 3) -> Dict[str, object]:
    present = [v for v in values if v is not None]
    return {"mediana": round(float(np.median(present)), digits) if present else None,
            "voltas": len(present), "sem_canal": len(values) - len(present)}


def _rounded(value):
    return round(value, 3) if isinstance(value, float) else value


def technique_report(laps: pd.DataFrame, lap_grids: Dict[str, pd.DataFrame], ref: pd.DataFrame,
                     track: TrackGeometry, segments: Sequence[Segment]) -> Dict[str, object]:
    """O bloco `tecnica` de uma sessao (formato em `docs/store_v2_e_evolucao.md`)."""
    laps = laps.sort_values(["session_id", "sequence"])
    lap_ids = list(laps["lap_id"])
    corners = []
    for k, segment in enumerate(segments):
        corner, previous_apex = segment.corner, segments[k - 1].corner.apex_s

        def measure(grid: pd.DataFrame) -> Dict[str, object]:
            brake = _column(grid, "brake")
            return {
                "uso_da_aderencia_g": grip_usage(grid, track, segment),
                "freio_e_volante_m": brake_and_steer_m(grid, track, previous_apex, corner),
                "emendada": None if brake is None else chained_braking(brake, track, previous_apex, corner.apex_s),
                "freio_max_c": brake_temp_max(grid, track, previous_apex, corner.apex_s),
            }

        rows = [{"volta": lap_id, **measure(lap_grids[lap_id])} for lap_id in lap_ids]
        ai = measure(ref)
        grip = _summary([r["uso_da_aderencia_g"] for r in rows])
        chained = [r["emendada"] for r in rows]
        brake_temps = _summary([r["freio_max_c"] for r in rows], 1)
        ai_grip = ai["uso_da_aderencia_g"]
        corners.append({
            "curva": corner.label,
            "uso_da_aderencia": {
                **grip,
                "ia_g": None if ai_grip is None else round(ai_grip, 3),
                "razao_contra_ia": round(grip["mediana"] / ai_grip, 3) if grip["mediana"] is not None and ai_grip else None,
            },
            "freio_e_volante_juntos": {**_summary([r["freio_e_volante_m"] for r in rows], 1),
                                       "ia_m": None if ai["freio_e_volante_m"] is None else round(ai["freio_e_volante_m"], 1)},
            "freada_emendada": {
                "voltas_emendadas": sum(1 for c in chained if c is True),
                "voltas_com_frenagem": sum(1 for c in chained if c is not None),
                "voltas_sem_frenagem": sum(1 for c in chained if c is None),
                "ia": "sem frenagem" if ai["emendada"] is None else ("emendada" if ai["emendada"] else "nao emendada"),
            },
            "temperatura_freio_max_c": brake_temps if brake_temps["voltas"] else None,
            "por_volta": [{key: _rounded(value) for key, value in r.items()} for r in rows],
        })

    tyres = []
    for lap_id, total in zip(lap_ids, laps["lap_time_s"]):
        temps = tyre_temperatures(lap_grids[lap_id])
        tyres.append({"volta": lap_id, "tempo_s": round(float(total), 3), **(temps or {})})
    with_temps = [t for t in tyres if "media_volta_c" in t]
    rho = None
    if len(with_temps) >= 3:
        series = pd.DataFrame(with_temps)
        value = series["media_volta_c"].corr(series["tempo_s"], method="spearman")
        rho = None if pd.isna(value) else round(float(value), 3)
    has_brakes = any(c["temperatura_freio_max_c"] for c in corners)
    return {
        "formato": "tecnica/1",
        "definicoes": "docs/store_v2_e_evolucao.md, secao 1.7",
        "voltas": len(lap_ids),
        "curvas": corners,
        "pneus": {"por_volta": tyres, "voltas": len(with_temps), "sem_canal": len(tyres) - len(with_temps),
                  "spearman_temperatura_tempo": rho, "nota": CAUSE_NOTE},
        "freios": {"canal": has_brakes,
                   "nota": None if has_brakes else "As gravacoes desta sessao nao tem a temperatura dos freios."},
    }
