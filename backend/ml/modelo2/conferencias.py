"""As conferencias dos canais antes de qualquer detector (Parte B.3).

* o desvio do volante em linha reta;
* os sinais numa curva a esquerda e numa a direita;
* a unidade do volante e o entre-eixos (a razao volante / curvatura em baixa velocidade);
* o escorregamento: longitudinal, lateral ou combinado;
* o ABS: o ajuste gravado (`carState.abs`) e a oscilacao do escorregamento na frenagem forte.
"""

from __future__ import annotations

import json
from typing import Dict, List, Sequence

import numpy as np

from .detectores import Lap
from .fases import CornerPhases, window
from ..data.recordings import Session
from ..track.geometry import TrackGeometry


def _pool(laps: Sequence[Lap], names: Sequence[str]):
    blocks = {n: [] for n in names}
    for lap in laps:
        arrays = [lap.a(n) for n in names]
        if any(a is None for a in arrays):
            continue
        for n, a in zip(names, arrays):
            blocks[n].append(a)
    return {n: (np.concatenate(v) if v else np.array([])) for n, v in blocks.items()}


def steer_offset(laps: Sequence[Lap]) -> Dict[str, object]:
    out = {}
    for origem in ("humano", "ia"):
        p = _pool([l for l in laps if l.volta.origem == origem], ("steer", "lateral_g", "speed_kmh"))
        if not p["steer"].size:
            continue
        m = (np.abs(p["lateral_g"]) < 0.05) & (p["speed_kmh"] > 100)
        s = p["steer"][m]
        out[origem] = {"pontos": int(m.sum()), "media": float(np.mean(s)), "mediana": float(np.median(s)),
                       "p5": float(np.percentile(s, 5)), "p95": float(np.percentile(s, 95)),
                       "pico_tipico_nas_curvas": float(np.percentile(np.abs(p["steer"]), 99))}
    return out


def signs(laps: Sequence[Lap], track: TrackGeometry, phases: Sequence[CornerPhases]) -> List[Dict[str, object]]:
    """Por curva, perto do apice com |a_y| >= 0,5 g: o sinal do volante, da guinada, de a_y e de v_lat."""
    out = []
    for cp in phases:
        idx = window(track, cp.m1, cp.m2)
        vals = {"steer": [], "yaw_rate": [], "lateral_g": [], "velocity_lat": []}
        for lap in laps:
            lat = lap.a("lateral_g")
            if lat is None:
                continue
            m = np.abs(lat[idx]) >= 0.5
            for n in vals:
                a = lap.a(n)
                if a is not None:
                    vals[n].append(a[idx][m])
        row = {"curva": cp.curva, "sentido": "esquerda" if cp.direcao > 0 else "direita"}
        for n, v in vals.items():
            v = np.concatenate(v) if v else np.array([])
            row[n] = None if not v.size else {"mediana": round(float(np.median(v)), 4),
                                              "fracao_positiva": round(float((v > 0).mean()), 4), "pontos": int(v.size)}
        out.append(row)
    return out


def steer_per_curvature(laps: Sequence[Lap]) -> Dict[str, object]:
    """|volante| / (|r| / v_x) em baixa velocidade: perto de L / k_delta num carro sem deriva."""
    p = _pool([l for l in laps if l.a("yaw_rate") is not None], ("steer", "yaw_rate", "velocity_long", "lateral_g"))
    if not p["steer"].size:
        return {}
    out = {}
    for lo, hi in ((10, 20), (20, 30), (30, 45), (45, 90)):
        m = (p["velocity_long"] >= lo) & (p["velocity_long"] < hi) & (np.abs(p["yaw_rate"]) >= 0.1) & (np.abs(p["lateral_g"]) >= 0.3)
        if m.sum() < 50:
            continue
        ratio = np.abs(p["steer"][m]) / (np.abs(p["yaw_rate"][m]) / p["velocity_long"][m])
        out[f"{lo}-{hi} m/s"] = {"mediana_m": round(float(np.median(ratio)), 3), "pontos": int(m.sum())}
    return out


def slip_nature(laps: Sequence[Lap]) -> Dict[str, object]:
    """O escorregamento em tres situacoes: frenagem em reta, curva sem pedal e reta em pe embaixo."""
    p = _pool(laps, ("steer", "lateral_g", "brake", "throttle", "speed_kmh", "slip_front", "slip_rear"))
    if not p["steer"].size:
        return {}
    big = np.percentile(np.abs(p["steer"]), 99)
    cases = {
        "frenagem_em_reta": (p["brake"] >= 0.5) & (np.abs(p["lateral_g"]) < 0.1) & (np.abs(p["steer"]) < 0.05 * big),
        "curva_sem_pedal": (p["brake"] < 0.05) & (p["throttle"] < 0.05) & (np.abs(p["lateral_g"]) >= 1.0),
        "curva_com_aceleracao_parcial": (p["brake"] < 0.05) & (p["throttle"] > 0.2) & (p["throttle"] < 0.8) & (np.abs(p["lateral_g"]) >= 1.0),
        "reta_pe_embaixo": (p["throttle"] > 0.98) & (np.abs(p["lateral_g"]) < 0.1) & (p["speed_kmh"] > 150),
    }
    out = {}
    for name, m in cases.items():
        if m.sum() < 20:
            continue
        out[name] = {"pontos": int(m.sum()),
                     "dianteiro_mediana": round(float(np.nanmedian(p["slip_front"][m])), 4),
                     "dianteiro_p95": round(float(np.nanpercentile(p["slip_front"][m], 95)), 4),
                     "traseiro_mediana": round(float(np.nanmedian(p["slip_rear"][m])), 4),
                     "traseiro_p95": round(float(np.nanpercentile(p["slip_rear"][m], 95)), 4)}
    return out


def abs_setting(session: Session, every: int = 50) -> Dict[str, object]:
    """Os valores de `carState.abs` e `carState.tc` gravados (uma amostra a cada `every`)."""
    values, tcs = {}, {}
    with session.player_stream.open("r", encoding="utf-8", errors="replace") as handle:
        for i, line in enumerate(handle):
            if i % every:
                continue
            try:
                state = json.loads(line)["sample"]["carPhysics"]["carState"]
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            values[state.get("abs")] = values.get(state.get("abs"), 0) + 1
            tcs[state.get("tc")] = tcs.get(state.get("tc"), 0) + 1
    return {"gravacao": session.session_id, "abs": {str(k): v for k, v in values.items()},
            "tc": {str(k): v for k, v in tcs.items()}}


def abs_cycles(laps: Sequence[Lap]) -> Dict[str, object]:
    """Na frenagem forte em reta (freio >= 0,9 por 0,5 s ou mais): reversoes do escorregamento dianteiro por segundo."""
    from .detectores import count_reversals, runs
    rates, maxima = [], []
    for lap in laps:
        brake, sf, lat, el = lap.a("brake"), lap.a("slip_front"), lap.a("lateral_g"), lap.a("elapsed_s")
        if any(x is None for x in (brake, sf, lat, el)):
            continue
        for lo, hi in runs((brake >= 0.9) & (np.abs(lat) < 0.3)):
            dur = float(el[min(hi, el.size - 1)] - el[lo])
            if dur < 0.5:
                continue
            seg = sf[lo:hi]
            rates.append(count_reversals(seg, 0.02) / dur)
            maxima.append(float(np.nanmax(seg)))
    if not rates:
        return {}
    return {"trechos": len(rates), "reversoes_por_s_mediana": round(float(np.median(rates)), 2),
            "reversoes_por_s_p90": round(float(np.percentile(rates, 90)), 2),
            "escorregamento_max_mediana": round(float(np.median(maxima)), 4),
            "nota": "a grade de 2 m (cerca de 25 a 40 ms por ponto na frenagem) so resolve ciclos abaixo de ~12 Hz"}
