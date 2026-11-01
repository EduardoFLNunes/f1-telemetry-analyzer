"""Os detectores de tecnica e de erro (secoes 1.4 e 1.5).

Em duas etapas:

1. `measure_passage` mede os eventos e os indicadores de uma passagem (uma
   volta numa curva), sem estado nenhum;
2. `assign_states` calibra nas passagens da IA da mesma curva e da a cada
   passagem "aplica", "nao aplica" ou "nao conclusivo".

Tipo P (regra fisica): o limiar e fixo e a referencia so alarga a faixa de
duvida (metade do intervalo entre os dois limiares, ou 0,5 x o desvio robusto
da IA, o que for maior). Tipo C (comparacao): o limiar e relativo as passagens
da IA, com um minimo fixo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .dados import HOLE_S, Volta
from .fases import CornerPhases, ahead, window
from ..track.geometry import TrackGeometry

APLICA, NAO_APLICA, NC = "aplica", "nao_aplica", "nao_conclusivo"
STATES = (APLICA, NAO_APLICA, NC)

PEDAL_EPS = 0.05
BRAKE_MIN_PEAK = 0.15
MERGE_M = 10.0
TURN_IN_SHARE = 0.15
PICKUP = 0.10
FULL = 0.95

# Medida substituta do subesterco (1.2): o retrato da memoria do jogo, pedido 39, Parte B.
WHEELBASE_SUBSTITUTE_M = 2.955
STEER_GAIN_SUBSTITUTE_RAD = 0.267
G = 9.80665
SLIP_RELIABLE_MAX = 10.0

# Detector -> (familia, tecnica ou erro, tipo, nome, fases para a atribuicao).
CATALOG = {
    "F1": ("frenagem", "tecnica", "C", "referencia de frenagem"),
    "F2": ("frenagem", "tecnica", "C", "frenagem no limiar"),
    "F3": ("frenagem", "tecnica", "P", "perfil com carga aerodinamica"),
    "F4": ("frenagem", "tecnica", "P", "soltura progressiva"),
    "F5": ("frenagem", "tecnica", "P", "trail braking"),
    "F6": ("frenagem", "erro", "C", "travamento de roda"),
    "F7": ("frenagem", "tecnica", "P", "sobreposicao de pedais"),
    "F8": ("frenagem", "erro", "C", "reducao de marcha brusca"),
    "E1": ("entrada", "erro", "C", "entrada antecipada"),
    "E2": ("entrada", "erro", "C", "subesterco (substituta)"),
    "E3": ("entrada", "erro", "C", "sobresterco"),
    "E4": ("entrada", "erro", "P", "contraesterco"),
    "E5": ("entrada", "erro", "C", "reversoes do volante"),
    "E6": ("entrada", "tecnica", "C", "suavidade do volante"),
    "M1": ("meio_saida", "tecnica", "P", "uso do circulo de atrito"),
    "M2": ("meio_saida", "erro", "C", "apice antecipado"),
    "M3": ("meio_saida", "tecnica", "P", "forma em U"),
    "M4": ("meio_saida", "tecnica", "C", "uso da largura na saida"),
    "M5": ("meio_saida", "erro", "P", "fase sem pedal"),
    "M6": ("meio_saida", "tecnica", "C", "retomada do acelerador"),
    "M7": ("meio_saida", "erro", "P", "acelerador cedo"),
    "M8": ("meio_saida", "erro", "P", "alivio depois da retomada"),
    "M9": ("meio_saida", "erro", "C", "patinacao"),
    "V1": ("volta", "tecnica", "P", "uso decidido do acelerador"),
    "V2": ("volta", "tecnica", "C", "rotacao de troca"),
    "V3": ("volta", "erro", "C", "transferencia de carga brusca"),
    "V4": ("volta", "tecnica", "C", "pneus na faixa da IA"),
    "V5": ("volta", "tecnica", "P", "consistencia"),
}
PER_CORNER = [d for d in CATALOG if d not in ("V1", "V2", "V4", "V5")]
PHASE_DETECTORS = {
    "frenagem": ("F1", "F2", "F3", "F6", "F7", "F8", "V3"),
    "entrada": ("F4", "F5", "E1", "E5", "E6", "M5"),
    "meio": ("E2", "E3", "E4", "M1", "M2", "M3", "M5"),
    "saida": ("M6", "M7", "M8", "M9", "M4", "E3"),
    "reta": ("M4", "M6", "M8"),
}
# O indicador principal de cada detector (atribuicao, estilo e modelo leve).
PRIMARY = {"F1": "s_b_rel", "F2": "t_pico", "F3": "pico_fracao", "F4": "taxa_soltura", "F5": "sobreposicao_s",
           "F6": "escorr_dianteiro", "F7": "pedais_juntos_s", "F8": "escorr_reducao", "E1": "s_ti_rel",
           "E2": "ua_graus", "E3": "beta_p95", "E4": "contra_s", "E5": "reversoes", "E6": "irregularidade",
           "M1": "uso_aderencia", "M2": "s_vmin_rel", "M3": "plato_s", "M4": "afastamento_m", "M5": "sem_pedal_s",
           "M6": "retomada_s", "M7": "volante_depois", "M8": "alivio", "M9": "escorr_traseiro",
           "V3": "taxa_carga"}


def _f(frame: pd.DataFrame, name: str) -> Optional[np.ndarray]:
    if name not in frame.columns:
        return None
    values = frame[name].to_numpy(dtype=float)
    return values if np.isfinite(values).any() else None


def robust_sd(values: Sequence[float]) -> float:
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if v.size < 2:
        return float("nan")
    q75, q25 = np.percentile(v, [75, 25])
    return float((q75 - q25) / 1.349)


def runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    """Sequencias de True como (inicio, fim exclusivo)."""
    if mask.size == 0 or not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(int)
    edges = np.diff(padded)
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def merged_runs(mask: np.ndarray, gap_points: int) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for a, b in runs(mask):
        if out and a - out[-1][1] < gap_points:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def count_reversals(signal: np.ndarray, gap: float) -> int:
    """Mudancas de sentido com excursao >= `gap` (contagem com histerese)."""
    x = signal[np.isfinite(signal)]
    if x.size < 3 or not np.isfinite(gap) or gap <= 0:
        return 0
    direction, extreme, count = 0, x[0], 0
    for v in x[1:]:
        if direction >= 0 and v > extreme:
            extreme = v
            if direction == 0 and v - x[0] >= gap:
                direction = 1
        elif direction <= 0 and v < extreme:
            extreme = v
            if direction == 0 and x[0] - v >= gap:
                direction = -1
        if direction == 1 and extreme - v >= gap:
            count += 1
            direction, extreme = -1, v
        elif direction == -1 and v - extreme >= gap:
            count += 1
            direction, extreme = 1, v
    return count


# ------------------------------------------------------- passagem ---

@dataclass
class Lap:
    """Os canais de uma volta prontos para as contas."""

    volta: Volta
    total: float
    arrays: Dict[str, Optional[np.ndarray]]
    dt: np.ndarray                # tempo de cada ponto ao seguinte (o ultimo fecha a volta)

    @classmethod
    def build(cls, volta: Volta) -> "Lap":
        g = volta.grid
        names = ("brake", "throttle", "speed_kmh", "lateral_g", "longitudinal_g", "lateral", "gear", "rpm",
                 "yaw_rate", "velocity_long", "velocity_lat", "brake_rate", "throttle_rate", "steer_rate",
                 "steer_ma01", "steer_ma02", "steer_dev05", "front_share", "front_share_rate", "raw_dt",
                 "elapsed_s", "wheel_slip_fl", "wheel_slip_fr", "wheel_slip_rl", "wheel_slip_rr",
                 "tyre_core_temp_fl", "tyre_core_temp_fr", "tyre_core_temp_rl", "tyre_core_temp_rr")
        arrays = {n: _f(g, n) for n in names}
        steer = _f(g, "steer_angle")
        arrays["steer"] = steer if steer is not None else _f(g, "steering")
        # Secao 2 (emenda de 25/10): escorregamento acima de 10 e leitura quebrada ou
        # roda no ar; o ponto sai da conta ("canal nao confiavel no trecho").
        for w in ("fl", "fr", "rl", "rr"):
            slip = arrays[f"wheel_slip_{w}"]
            if slip is not None:
                arrays[f"wheel_slip_{w}"] = np.where(slip > SLIP_RELIABLE_MAX, np.nan, slip)
        fl, fr, rl, rr = (arrays[f"wheel_slip_{w}"] for w in ("fl", "fr", "rl", "rr"))
        arrays["slip_front"] = None if fl is None or fr is None else np.fmax(fl, fr)
        arrays["slip_rear"] = None if rl is None or rr is None else np.fmax(rl, rr)
        elapsed = arrays["elapsed_s"]
        total = float(volta.tempo_s)
        dt = np.append(np.diff(elapsed), total - elapsed[-1] + elapsed[0])
        dt = np.where(np.isfinite(dt) & (dt >= 0), dt, 0.0)
        return cls(volta=volta, total=total, arrays=arrays, dt=dt)

    def a(self, name: str) -> Optional[np.ndarray]:
        return self.arrays.get(name)


def phase_time(lap: Lap, track: TrackGeometry, start: float, end: float) -> float:
    idx = window(track, start, end)
    return float(lap.dt[idx].sum()) if idx.size else 0.0


@dataclass
class Window:
    idx: np.ndarray
    t: np.ndarray                 # tempo desde o inicio da janela, s
    offsets: Dict[str, int]       # marcos da curva como indice dentro da janela


def corner_window(lap: Lap, track: TrackGeometry, cp: CornerPhases, previous: CornerPhases) -> Window:
    """Do apice anterior ate e_k + 100 m, com os marcos da curva."""
    start = previous.apice
    end = float(np.mod(cp.e + 100.0, track.length))
    idx = window(track, start, end)
    t = np.concatenate([[0.0], np.cumsum(lap.dt[idx[:-1]])])
    step = track.step

    def off(s):
        return int(min(round(ahead(track, start, s) / step), idx.size - 1))

    offsets = {"p_prev": 0, "b": off(cp.b), "a": off(cp.a), "m1": off(cp.m1), "apice": off(cp.apice),
               "m2": off(cp.m2), "e": off(cp.e), "e50": off(np.mod(cp.e + 50.0, track.length)),
               "e60": off(np.mod(cp.e + 60.0, track.length)), "fim": idx.size - 1}
    return Window(idx=idx, t=t, offsets=offsets)


def _seg(values: Optional[np.ndarray], w: Window) -> Optional[np.ndarray]:
    return None if values is None else values[w.idx]


def _sum_dt(mask: np.ndarray, t: np.ndarray) -> float:
    if mask.size < 2:
        return 0.0
    dt = np.diff(t)
    return float(dt[mask[:-1]].sum())


def _holes(lap: Lap, w: Window, lo: int, hi: int) -> bool:
    raw_dt = _seg(lap.a("raw_dt"), w)
    if raw_dt is None:
        return True
    part = raw_dt[lo:max(hi, lo + 1)]
    return bool(np.nanmax(part) >= HOLE_S) if part.size and np.isfinite(part).any() else True


def measure_passage(lap: Lap, track: TrackGeometry, cp: CornerPhases, previous: CornerPhases,
                    envelope: Callable[[np.ndarray], np.ndarray]) -> Dict[str, object]:
    """Eventos e indicadores de uma passagem (1.4 e 1.5), sem estado."""
    w = corner_window(lap, track, cp, previous)
    o, t, step = w.offsets, w.t, track.step
    brake = np.nan_to_num(_seg(lap.a("brake"), w))
    throttle = np.nan_to_num(_seg(lap.a("throttle"), w))
    speed = _seg(lap.a("speed_kmh"), w)
    steer = _seg(lap.a("steer"), w)
    out: Dict[str, object] = {"lap_id": lap.volta.lap_id, "curva": cp.curva, "k": cp.k, "origem": lap.volta.origem,
                              "sessao": lap.volta.sessao, "gravacao": lap.volta.gravacao,
                              "fora_do_store": lap.volta.fora_do_store}
    missing: Dict[str, str] = {}

    # ---- eventos
    a, e, apex = o["a"], o["e"], o["apice"]
    into = None if steer is None else -steer * cp.direcao        # positivo virando para dentro da curva
    d_pk = float(np.nanmax(np.abs(steer[a:e + 1]))) if steer is not None else float("nan")
    out["delta_pk"] = d_pk
    braking_zone = brake[:apex + 1]
    ib = ie = itpk = None
    b_pk = float(braking_zone.max()) if braking_zone.size else 0.0
    if b_pk >= BRAKE_MIN_PEAK:
        segs = merged_runs(braking_zone >= PEDAL_EPS, int(round(MERGE_M / step)))
        peak = int(np.argmax(braking_zone))
        for lo, hi in segs:
            if lo <= peak < hi:
                ib, ie = lo, hi
        if ib is not None:
            b_pk = float(brake[ib:ie].max())
            itpk = ib + int(np.flatnonzero(brake[ib:ie] >= 0.9 * b_pk)[0])
    out["freia"] = ib is not None
    out["s_b_rel"] = None if ib is None else (ib - a) * step
    out["pico_freio"] = b_pk if ib is not None else None
    iti = None
    if into is not None and np.isfinite(d_pk) and d_pk > 0:
        mask = into >= TURN_IN_SHARE * d_pk
        for lo, hi in runs(mask):
            if lo <= apex < hi:
                iti = lo
    out["s_ti_rel"] = None if iti is None else (iti - a) * step
    ivmin = a + int(np.nanargmin(speed[a:e + 1])) if speed is not None else None
    out["s_vmin_rel"] = None if ivmin is None else (ivmin - a) * step
    out["v_min"] = None if ivmin is None else float(speed[ivmin])
    after = max([x for x in (ie, iti) if x is not None] or [a])
    ipu = ifull = None
    cand = np.flatnonzero(throttle[after:o["e50"] + 1] >= PICKUP)
    if cand.size:
        ipu = after + int(cand[0])
        full = np.flatnonzero(throttle[ipu:] >= FULL)
        ifull = ipu + int(full[0]) if full.size else None
    out["retoma"] = ipu is not None

    # ---- frenagem
    if ib is not None:
        out["t_pico"] = float(t[itpk] - t[ib])
        end_t = t[min(ie, t.size - 1)]
        dur = float(end_t - t[ib])
        out["duracao_freio"] = dur
        if dur >= 0.6:
            out["pico_fracao"] = (t[itpk] - t[ib]) / dur
            mid = (t >= t[ib] + dur / 3.0) & (t <= t[ib] + 2.0 * dur / 3.0)
            out["queda_meio"] = float((b_pk - np.median(brake[mid])) / b_pk) if mid.any() else None
        else:
            missing["F3"] = "frenagem com menos de 0,6 s"
        rel = ib + int(np.flatnonzero(brake[ib:ie] >= 0.5 * b_pk)[-1])
        rate = _seg(lap.a("brake_rate"), w)
        if rate is None or _holes(lap, w, ib, ie):
            missing["F4"] = "buraco no cronometro ou sem taxa"
        else:
            t0, t1 = t[rel], end_t
            last = (t >= t0 + 2.0 * (t1 - t0) / 3.0) & (t <= t1)
            last[min(ie, t.size - 1)] = True
            out["taxa_soltura"] = float(-np.nanmin(rate[last]))
            fsr = _seg(lap.a("front_share_rate"), w)
            out["queda_carga_dianteira"] = None if fsr is None else float(-np.nanmin(fsr[rel:min(ie, t.size - 1) + 1]))
        sf = _seg(lap.a("slip_front"), w)
        if sf is None or steer is None:
            missing["F6"] = "sem escorregamento"
        else:
            straight = (brake[ib:ie] >= 0.3) & (np.abs(steer[ib:ie]) <= 0.1 * d_pk)
            if straight.any():
                out["escorr_dianteiro"] = float(np.nanmax(sf[ib:ie][straight]))
            else:
                missing["F6"] = "sem frenagem em linha reta"
    # trail braking
    if iti is not None and into is not None:
        x1 = float(brake[iti] / b_pk) if ib is not None and b_pk > 0 else 0.0
        both = (brake >= PEDAL_EPS) & (into >= TURN_IN_SHARE * d_pk)
        both[:iti] = False
        both[e + 1:] = False
        out["retencao"] = x1
        out["sobreposicao_s"] = _sum_dt(both, t)
        if both.sum() >= 5:
            from scipy.stats import spearmanr
            rho = spearmanr(brake[both], np.abs(steer[both])).correlation
            out["coordenacao"] = None if not np.isfinite(rho) else float(rho)
    # pedais juntos e reducoes
    gear = _seg(lap.a("gear"), w)
    fb, fm1 = o["b"], o["m1"]
    downs = []
    if gear is not None:
        g = np.nan_to_num(gear)
        downs = [i for i in range(max(fb, 1), fm1) if g[i] < g[i - 1]]
    both = (brake >= PEDAL_EPS) & (throttle >= PEDAL_EPS)
    keep = np.zeros_like(both)
    keep[fb:fm1] = True
    for i in downs:
        keep &= ~(np.abs(t - t[i]) <= 0.15)
    out["pedais_juntos_s"] = _sum_dt(both & keep, t)
    out["reducoes"] = len(downs) if gear is not None else None
    sr = _seg(lap.a("slip_rear"), w)
    if gear is None or sr is None:
        missing["F8"] = "sem marcha ou escorregamento"
    elif not downs:
        missing["F8"] = "sem reducao"
    else:
        out["escorr_reducao"] = float(max(np.nanmax(sr[(t >= t[i]) & (t <= t[i] + 0.3)]) for i in downs))

    # ---- entrada e equilibrio
    srate = _seg(lap.a("steer_rate"), w)
    if iti is not None and srate is not None and np.isfinite(d_pk) and d_pk > 0:
        span = (t >= t[iti]) & (t <= t[iti] + 0.5)
        out["taxa_entrada"] = float(np.nanmax(np.abs(srate[span])) / d_pk)
    yaw, vx, vy = _seg(lap.a("yaw_rate"), w), _seg(lap.a("velocity_long"), w), _seg(lap.a("velocity_lat"), w)
    lat = _seg(lap.a("lateral_g"), w)
    if yaw is None or vx is None or steer is None or lat is None:
        missing["E2"] = "sem guinada ou velocidade no referencial do carro"
    else:
        sl = slice(o["m1"], o["m2"])
        m = (np.abs(lat[sl]) >= 0.4) & (np.abs(yaw[sl]) >= 0.05) & (vx[sl] > 5.0)
        if m.any():
            wheel = -STEER_GAIN_SUBSTITUTE_RAD * steer[sl][m]
            ua = np.sign(yaw[sl][m]) * (wheel - WHEELBASE_SUBSTITUTE_M * yaw[sl][m] / vx[sl][m])
            out["ua_graus"] = float(np.degrees(np.median(ua)))
        else:
            missing["E2"] = "sem pontos com |a_y| >= 0,4 g no meio"
    if vx is None or vy is None:
        missing["E3"] = "sem velocidades no referencial do carro"
    else:
        beta = np.degrees(np.arctan2(vy[a:e + 1], np.where(vx[a:e + 1] > 1.0, vx[a:e + 1], np.nan)))
        out["beta_p95"] = float(np.nanpercentile(np.abs(beta), 95)) if np.isfinite(beta).any() else None
        # resposta na entrada (estilo): guinada / angulo de roda nos 0,5 s depois de s_ti
        if iti is not None and yaw is not None and steer is not None:
            span = (t >= t[iti]) & (t <= t[iti] + 0.5)
            wheel = np.abs(STEER_GAIN_SUBSTITUTE_RAD * steer[span])
            ok = wheel > 0.005
            out["guinada_por_roda"] = float(np.median(np.abs(yaw[span][ok]) / wheel[ok])) if ok.any() else None
            out["beta_entrada"] = float(np.nanmax(np.abs(beta[max(iti - a, 0):max(apex - a, 1)]))) if apex > iti else None
    if yaw is None or steer is None or iti is None:
        missing["E4"] = "sem guinada ou sem entrada"
    else:
        counter = (steer * yaw > 0) & (np.abs(steer) >= 0.05 * d_pk) & (np.abs(yaw) >= 0.05)
        counter[:iti] = False
        counter[e + 1:] = False
        longest = 0.0
        for lo, hi in runs(counter):
            longest = max(longest, float(t[min(hi, t.size - 1)] - t[lo]))
        out["contra_s"] = longest
    ma01 = _seg(lap.a("steer_ma01"), w)
    dev = _seg(lap.a("steer_dev05"), w)
    if iti is None or ma01 is None or _holes(lap, w, iti, e):
        missing["E5"] = missing["E6"] = "sem entrada ou buraco no cronometro"
    else:
        out["reversoes"] = count_reversals(ma01[iti:e + 1], 0.05 * d_pk)
        out["irregularidade"] = float(np.nanmean(dev[iti:e + 1]) / d_pk) if dev is not None else None

    # ---- meio e saida
    lon = _seg(lap.a("longitudinal_g"), w)
    if lat is not None and lon is not None and speed is not None:
        comb = np.hypot(lat, lon)
        env = envelope(speed)
        use = comb[fb:e + 1] / env[fb:e + 1]
        out["uso_aderencia"] = float(np.nanpercentile(use, 95)) if np.isfinite(use).any() else None
        if ib is not None:
            seg = slice(ib, apex + 1)
            diag = (np.abs(lon[seg]) >= 0.3 * env[seg]) & (np.abs(lat[seg]) >= 0.3 * env[seg])
            out["fracao_diagonal"] = float(diag.mean())
    lateral = _seg(lap.a("lateral"), w)
    if lateral is not None:
        out["lateral_apice"] = float(lateral[apex])
        out["afastamento_m"] = float(np.nanmax(-cp.direcao * lateral[o["m2"]:o["e60"] + 1]))
    if speed is not None and ivmin is not None:
        vmin = speed[ivmin]
        out["plato_s"] = _sum_dt(speed[fb:e + 1] <= 1.03 * vmin, t[fb:e + 1])
        v_ref = speed[ib] if ib is not None else speed[fb]
        out["vmin_sobre_ventrada"] = float(vmin / v_ref) if v_ref > 0 else None
        out["vmin_posicao"] = float((ivmin - a) / max(e - a, 1))
        coast = (throttle < PEDAL_EPS) & (brake < PEDAL_EPS) & (speed > 18.0)
        part = np.zeros_like(coast)
        part[fb:e + 1] = True
        total = 0.0
        for lo, hi in runs(coast & part):
            d = float(t[min(hi, t.size - 1)] - t[lo])
            total += d if d >= 0.1 else 0.0
        out["sem_pedal_s"] = total
        # o menor acelerador entre o alivio e s_b (estilo: uso dos pedais)
        if ib is not None:
            lifted = np.flatnonzero(throttle[:ib] < 0.95)
            out["acelerador_min_antes"] = float(throttle[lifted[0]:ib + 1].min()) if lifted.size else None
    if ipu is not None and ivmin is not None:
        out["retomada_s"] = float(t[ipu] - t[ivmin])
        if ifull is not None:
            out["apice_ao_pleno_s"] = float(t[ifull] - t[ivmin])
        stop = ifull if ifull is not None else o["fim"]
        seg_thr = throttle[ipu:stop + 1]
        out["alivio"] = float(np.max(np.maximum.accumulate(seg_thr) - seg_thr)) if seg_thr.size else 0.0
        ma02 = _seg(lap.a("steer_ma02"), w)
        if ma02 is not None and ipu < e and np.isfinite(d_pk) and d_pk > 0:
            out["volante_depois"] = float((np.nanmax(ma02[ipu:e + 1]) - ma02[ipu]) / d_pk)
        else:
            missing["M7"] = "retomada depois do fim da curva"
        saida = slice(o["m2"], e + 1)
        out["f20_60_saida"] = float(((throttle[saida] >= 0.2) & (throttle[saida] <= 0.6)).mean())
    if sr is None:
        missing["M9"] = "sem escorregamento"
    else:
        zone = np.zeros(t.size, dtype=bool)
        zone[o["m2"]:] = True
        zone &= throttle >= 0.3
        out["escorr_traseiro"] = float(np.nanmax(sr[zone])) if zone.any() else None
    fsr = _seg(lap.a("front_share_rate"), w)
    lo_v3 = ib if ib is not None else fb
    if fsr is None or _holes(lap, w, lo_v3, e):
        missing["V3"] = "sem cargas ou buraco no cronometro"
    else:
        out["taxa_carga"] = float(np.nanmax(np.abs(fsr[lo_v3:e + 1])))
    out["_ausente"] = missing
    return out


def lap_measures(lap: Lap) -> Dict[str, object]:
    """V1, V2 e V4: por volta."""
    thr = lap.a("throttle")
    out: Dict[str, object] = {"lap_id": lap.volta.lap_id, "origem": lap.volta.origem, "sessao": lap.volta.sessao,
                              "gravacao": lap.volta.gravacao, "fora_do_store": lap.volta.fora_do_store,
                              "tempo_s": lap.total}
    if thr is not None:
        w = lap.dt / lap.dt.sum()
        out["f0"] = float(w[thr < 0.02].sum())
        out["f100"] = float(w[thr > 0.98].sum())
        out["f20_60"] = float(w[(thr >= 0.2) & (thr <= 0.6)].sum())
        out["decidido"] = out["f0"] + out["f100"]
    gear, rpm = lap.a("gear"), lap.a("rpm")
    if gear is not None and rpm is not None:
        g = np.nan_to_num(gear)
        ups = [i - 1 for i in range(1, g.size) if g[i] > g[i - 1] and g[i - 1] >= 1]
        out["rpm_troca"] = float(np.median(rpm[ups])) if ups else None
        out["_rpm"] = rpm
    temps = [lap.a(f"tyre_core_temp_{w}") for w in ("fl", "fr", "rl", "rr")]
    if all(x is not None for x in temps):
        out["pneu_c"] = float(np.nanmean(np.vstack(temps)))
    return out


def envelope_from(laps: Sequence[Lap], bin_kmh: float = 20.0):
    """E(v): o percentil 98 da aceleracao combinada por faixa de 20 km/h, em todas as voltas rotuladas."""
    speeds, combs = [], []
    for lap in laps:
        lat, lon, v = lap.a("lateral_g"), lap.a("longitudinal_g"), lap.a("speed_kmh")
        if lat is None or lon is None or v is None:
            continue
        speeds.append(v)
        combs.append(np.hypot(lat, lon))
    v = np.concatenate(speeds)
    c = np.concatenate(combs)
    edges = np.arange(0.0, 320.0, bin_kmh)
    centres, values = [], []
    for lo in edges:
        m = (v >= lo) & (v < lo + bin_kmh) & np.isfinite(c)
        if m.sum() >= 50:
            centres.append(lo + bin_kmh / 2.0)
            values.append(float(np.percentile(c[m], 98)))
    centres, values = np.asarray(centres), np.asarray(values)

    def env(speed: np.ndarray) -> np.ndarray:
        return np.interp(np.nan_to_num(speed), centres, values)

    env.table = {"faixa_kmh": centres.tolist(), "p98_g": values.tolist()}
    return env


# ------------------------------------------------------- estados ---

def _two(x, aplica_le: bool, t_aplica: float, t_nao: float, sdr: float = float("nan"), widen: bool = False) -> str:
    """Estado de uma condicao com dois limiares. `widen`: tipo P, a faixa e max(meio intervalo, 0,5 x sdr)."""
    if x is None or not np.isfinite(x):
        return NC
    if widen and np.isfinite(sdr):
        centre = (t_aplica + t_nao) / 2.0
        half = max(abs(t_nao - t_aplica) / 2.0, 0.5 * sdr)
        t_aplica = centre - half if aplica_le else centre + half
        t_nao = centre + half if aplica_le else centre - half
    if aplica_le:
        return APLICA if x <= t_aplica else (NAO_APLICA if x >= t_nao else NC)
    return APLICA if x >= t_aplica else (NAO_APLICA if x <= t_nao else NC)


def _combine(states: Sequence[str]) -> str:
    """Aplica se todas aplicam; nao aplica se alguma nao aplica; senao, nao conclusivo."""
    if any(s == NAO_APLICA for s in states):
        return NAO_APLICA
    if states and all(s == APLICA for s in states):
        return APLICA
    return NC


@dataclass
class Ref:
    n: int
    med: float
    q90: float
    q95: float
    sdr: float

    @classmethod
    def of(cls, values: Sequence[Optional[float]]) -> "Ref":
        v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
        if v.size == 0:
            return cls(0, float("nan"), float("nan"), float("nan"), float("nan"))
        return cls(int(v.size), float(np.median(v)), float(np.percentile(v, 90)), float(np.percentile(v, 95)),
                   robust_sd(v) if v.size >= 2 else float("nan"))


def _num(row: Dict[str, object], key: str) -> Optional[float]:
    v = row.get(key)
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else float(v)


def corner_refs(ai_rows: Sequence[Dict[str, object]]) -> Dict[str, Ref]:
    keys = set()
    for r in ai_rows:
        keys |= {k for k, v in r.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {k: Ref.of([_num(r, k) for r in ai_rows]) for k in keys}


def state_of(det: str, row: Dict[str, object], ref: Dict[str, Ref]) -> Tuple[str, Optional[str], Optional[float]]:
    """(estado, motivo do nao conclusivo, valor usado na regra) de um detector por curva."""
    missing = row.get("_ausente", {})
    if det in missing:
        return NC, missing[det], None
    R = lambda k: ref.get(k, Ref(0, float("nan"), float("nan"), float("nan"), float("nan")))
    x = lambda k: _num(row, k)

    def need_ref(k):
        return R(k).n >= 1

    if det == "F1":
        ai_brake_share = R("_freia").med if "_freia" in ref else float("nan")
        if np.isfinite(ai_brake_share) and ai_brake_share < 0.5:
            return NC, "a referencia nao freia", None
        if not row.get("freia"):
            return NAO_APLICA, "sem frenagem com a IA freando", None
        if not need_ref("s_b_rel"):
            return NC, "sem referencia", None
        d = x("s_b_rel") - R("s_b_rel").med
        T = max(10.0, 2.0 * R("s_b_rel").sdr) if np.isfinite(R("s_b_rel").sdr) else 10.0
        return _two(abs(d), True, T, T + 5.0), None, d
    if det in ("F2", "F3", "F4", "F5", "F6") and not row.get("freia"):
        return NC, "sem frenagem", None
    if det == "F2":
        if not need_ref("t_pico"):
            return NC, "sem referencia", None
        T1 = max(0.38, R("t_pico").q90)
        rel = x("pico_freio") / R("pico_freio").med if R("pico_freio").med > 0 else None
        return _combine([_two(x("t_pico"), True, T1, T1 + 0.20), _two(rel, False, 0.90, 0.80)]), None, x("t_pico")
    if det == "F3":
        return _combine([_two(x("pico_fracao"), True, 0.35, 0.50, R("pico_fracao").sdr, True),
                         _two(x("queda_meio"), False, 0.10, 0.03, R("queda_meio").sdr, True)]), None, x("pico_fracao")
    if det == "F4":
        return _two(x("taxa_soltura"), True, 3.0 - 0.75, 3.0 + 0.75, R("taxa_soltura").sdr, True), None, x("taxa_soltura")
    if det == "F5":
        if x("sobreposicao_s") is None:
            return NC, "sem entrada", None
        return _combine([_two(x("sobreposicao_s"), False, 0.20, 0.05, R("sobreposicao_s").sdr, True),
                         _two(x("retencao"), False, 0.10, 0.03, R("retencao").sdr, True)]), None, x("sobreposicao_s")
    if det in ("F6", "F8", "M9", "V3"):
        key, q = {"F6": ("escorr_dianteiro", "q95"), "F8": ("escorr_reducao", "q95"),
                  "M9": ("escorr_traseiro", "q95"), "V3": ("taxa_carga", "q90")}[det]
        if x(key) is None:
            return NC, "sem o evento", None
        base = getattr(R(key), q)
        if not need_ref(key) or not base > 0:
            return NC, "sem referencia", None
        ratio = x(key) / base
        return _two(ratio, False, 1.5, 1.1), None, ratio
    if det == "F7":
        return _two(x("pedais_juntos_s"), False, 0.20, 0.05, R("pedais_juntos_s").sdr, True), None, x("pedais_juntos_s")
    if det in ("E1", "M2"):
        key = "s_ti_rel" if det == "E1" else "s_vmin_rel"
        if x(key) is None:
            return NC, "sem o evento", None
        if not need_ref(key):
            return NC, "sem referencia", None
        d = x(key) - R(key).med
        T = max(10.0, 2.0 * R(key).sdr) if np.isfinite(R(key).sdr) else 10.0
        return _two(d, True, -(T + 5.0), -T), None, d
    if det == "E2":
        if x("ua_graus") is None:
            return NC, "sem o evento", None
        if not need_ref("ua_graus"):
            return NC, "sem referencia com guinada", None
        d = x("ua_graus") - R("ua_graus").med
        return _two(d, False, 0.5, 0.2), None, d
    if det == "E3":
        if x("beta_p95") is None:
            return NC, "sem o evento", None
        if not need_ref("beta_p95"):
            return NC, "sem referencia com velocidades no referencial do carro", None
        d = x("beta_p95") - R("beta_p95").med
        return _two(d, False, 1.0, 0.3), None, d
    if det == "E4":
        return _two(x("contra_s"), False, 0.10, 0.03, R("contra_s").sdr, True), None, x("contra_s")
    if det == "E5":
        if not need_ref("reversoes"):
            return NC, "sem referencia", None
        d = x("reversoes") - R("reversoes").med
        return _two(d, False, 2.0, 0.0), None, d
    if det == "E6":
        if not need_ref("irregularidade") or not R("irregularidade").q90 > 0:
            return NC, "sem referencia", None
        q = R("irregularidade").q90
        return _two(x("irregularidade"), True, 1.2 * q, 1.6 * q), None, x("irregularidade")
    if det == "M1":
        return _two(x("uso_aderencia"), False, 0.90, 0.80, R("uso_aderencia").sdr, True), None, x("uso_aderencia")
    if det == "M3":
        return _two(x("plato_s"), False, 0.60, 0.30, R("plato_s").sdr, True), None, x("plato_s")
    if det == "M4":
        if x("afastamento_m") is None or not need_ref("afastamento_m"):
            return NC, "sem referencia", None
        d = x("afastamento_m") - R("afastamento_m").med
        return _two(d, False, -0.5, -1.5), None, d
    if det == "M5":
        return _two(x("sem_pedal_s"), False, 0.25 + 0.05, 0.25 - 0.05, R("sem_pedal_s").sdr, True), None, x("sem_pedal_s")
    if det == "M7":
        if not row.get("retoma"):
            return NC, "sem retomada", None
        return _two(x("volante_depois"), False, 0.10, 0.03, R("volante_depois").sdr, True), None, x("volante_depois")
    if det == "M8":
        if not row.get("retoma"):
            return NC, "sem retomada", None
        return _two(x("alivio"), False, 0.15, 0.05, R("alivio").sdr, True), None, x("alivio")
    raise KeyError(det)


def m6_state(row: Dict[str, object], ref: Dict[str, Ref], m7: str, m8: str, ai_picks_up: bool) -> Tuple[str, Optional[str], Optional[float]]:
    """M6 depende de M7 e M8 (1.5)."""
    if not row.get("retoma"):
        return (NAO_APLICA, "sem retomada com a IA retomando", None) if ai_picks_up else (NC, "sem retomada", None)
    x1 = _num(row, "retomada_s")
    r = ref.get("retomada_s")
    if r is None or r.n == 0 or x1 is None:
        return NC, "sem referencia", None
    x2 = x1 - r.med
    aplica = x1 >= -0.10 and x2 <= 0.20 and m7 == NAO_APLICA and m8 == NAO_APLICA
    nao = x1 <= -0.30 or x2 >= 0.50 or m7 == APLICA or m8 == APLICA
    return (APLICA if aplica else NAO_APLICA if nao else NC), None, x2


def assign_states(rows: Sequence[Dict[str, object]]) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Ref]]]:
    """Os estados de todos os detectores por curva, calibrados na IA de cada curva."""
    by_corner: Dict[str, List[Dict[str, object]]] = {}
    for r in rows:
        by_corner.setdefault(r["curva"], []).append(r)
    out = []
    refs_out: Dict[str, Dict[str, Ref]] = {}
    for curva, items in by_corner.items():
        ai = [r for r in items if r["origem"] == "ia"]
        ref = corner_refs(ai)
        ref["_freia"] = Ref.of([1.0 if r.get("freia") else 0.0 for r in ai]) if ai else Ref.of([])
        refs_out[curva] = ref
        ai_picks = bool(ai) and np.mean([bool(r.get("retoma")) for r in ai]) >= 0.5
        for r in items:
            states = {}
            for det in PER_CORNER:
                if det == "M6":
                    continue
                states[det] = state_of(det, r, ref)
            states["M6"] = m6_state(r, ref, states["M7"][0], states["M8"][0], ai_picks)
            for det, (state, why, value) in states.items():
                out.append({"lap_id": r["lap_id"], "curva": curva, "k": r["k"], "origem": r["origem"],
                            "sessao": r["sessao"], "gravacao": r["gravacao"], "fora_do_store": r["fora_do_store"],
                            "detector": det, "estado": state, "motivo": why,
                            "valor_regra": value, "indicador": _num(r, PRIMARY[det])})
    return pd.DataFrame(out), refs_out


def lap_states(rows: Sequence[Dict[str, object]]) -> pd.DataFrame:
    """V1, V2 e V4, calibrados nas voltas da IA."""
    ai = [r for r in rows if r["origem"] == "ia"]
    rpm_ref = Ref.of([r.get("rpm_troca") for r in ai])
    tyre_ref = Ref.of([r.get("pneu_c") for r in ai])
    dec_ref = Ref.of([r.get("decidido") for r in ai])
    out = []
    for r in rows:
        v1 = _two(r.get("decidido"), False, 0.85, 0.75, dec_ref.sdr, True)
        v2 = NC if r.get("rpm_troca") is None or rpm_ref.n == 0 else _two(abs(r["rpm_troca"] - rpm_ref.med), True, 300, 600)
        v4 = NC if r.get("pneu_c") is None or tyre_ref.n == 0 else _two(abs(r["pneu_c"] - tyre_ref.med), True, 5, 10)
        for det, st, val in (("V1", v1, r.get("decidido")),
                             ("V2", v2, None if r.get("rpm_troca") is None or rpm_ref.n == 0 else r["rpm_troca"] - rpm_ref.med),
                             ("V4", v4, None if r.get("pneu_c") is None or tyre_ref.n == 0 else r["pneu_c"] - tyre_ref.med)):
            out.append({"lap_id": r["lap_id"], "origem": r["origem"], "sessao": r["sessao"], "detector": det,
                        "estado": st, "valor_regra": val})
    return pd.DataFrame(out)


def consistency_states(segment_times: pd.DataFrame) -> pd.DataFrame:
    """V5 por (origem, sessao, curva), com 5 voltas ou mais: o desvio do tempo do trecho."""
    out = []
    for (origem, sessao, curva), g in segment_times.groupby(["origem", "sessao", "curva"]):
        values = g["tempo_trecho_s"].to_numpy(dtype=float)
        if values.size < 5:
            state, sd = NC, None
        else:
            sd = float(np.std(values, ddof=1))
            state = _two(sd, True, 0.08, 0.15)
        out.append({"origem": origem, "sessao": sessao, "curva": curva, "detector": "V5", "estado": state,
                    "valor_regra": sd, "voltas": int(values.size)})
    return pd.DataFrame(out)
