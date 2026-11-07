"""A carga lateral da M1 v2, medida contra `wheel_load_*` (pedido 46, Parte B.1; ADR 0028, item 2).

    (carga_fr - carga_fl)/m = c_f*a_y + d_f      (carga_rr - carga_rl)/m = c_r*a_y + d_r

com |a_x| < 0,1 g e `vx` >= 10 m/s. Pela forma do ADR 0028, `c_f = 2*lam*h_y/t_f`
e `c_r = 2*(1 - lam)*h_y/t_r`, entao `lam = c_f*t_f/(c_f*t_f + c_r*t_r)` e
`h_y = (c_f*t_f + c_r*t_r)/2`. A incerteza sai de um bootstrap agrupado por
volta (200 reamostragens, semente 46).
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from . import fisica_v2 as F2
from .correcao import regimes
from .dados import G, WHEELS

BOOTSTRAP = 200
SEMENTE = 46


def _amostras(frame: pd.DataFrame, m: float):
    loads = frame[[f"wheel_load_{w}" for w in WHEELS]].to_numpy(dtype=float) / m
    a_x = frame["a_x"].to_numpy(dtype=float)
    a_y = frame["a_y"].to_numpy(dtype=float)
    vx = frame["vx"].to_numpy(dtype=float)
    sel = (np.isfinite(loads).all(1) & np.isfinite(a_x) & np.isfinite(a_y) & np.isfinite(vx)
           & (np.abs(a_x) < 0.1 * G) & (vx >= 10.0))
    return loads, a_x, a_y, vx, sel


def _coef(a_y, diff):
    X = np.column_stack([a_y, np.ones_like(a_y)])
    return np.linalg.lstsq(X, diff, rcond=None)[0]


def medir_lateral(frame: pd.DataFrame, m: float, t_f: float, t_r: float,
                  bootstrap: int = BOOTSTRAP, seed: int = SEMENTE) -> Dict[str, object]:
    """`lam` e `h_y` da rodada, com o intervalo de 95% e o que acontece com a faixa."""
    loads, _, a_y, _, sel = _amostras(frame, m)
    lap = frame["lap_id"].to_numpy()[sel]
    ay = a_y[sel]
    dfront = loads[sel, 1] - loads[sel, 0]
    drear = loads[sel, 3] - loads[sel, 2]

    def conta(idx):
        cf, df = _coef(ay[idx], dfront[idx])
        cr, dr = _coef(ay[idx], drear[idx])
        lam = cf * t_f / (cf * t_f + cr * t_r)
        h_y = 0.5 * (cf * t_f + cr * t_r)
        return {"c_f": float(cf), "d_f": float(df), "c_r": float(cr), "d_r": float(dr), "lam": float(lam), "h_y": float(h_y)}

    base = conta(np.arange(ay.size))
    laps = np.unique(lap)
    groups = {k: np.flatnonzero(lap == k) for k in laps}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(bootstrap):
        pick = rng.choice(laps, size=laps.size, replace=True)
        idx = np.concatenate([groups[k] for k in pick])
        draws.append(conta(idx))
    inc = {}
    for key in ("c_f", "c_r", "lam", "h_y"):
        vals = np.array([d[key] for d in draws])
        inc[key] = {"p2_5": float(np.percentile(vals, 2.5)), "p97_5": float(np.percentile(vals, 97.5)),
                    "desvio": float(np.std(vals))}
    lam_ok = F2.FAIXA_LAMBDA[0] <= base["lam"] <= F2.FAIXA_LAMBDA[1]
    h_ok = F2.FAIXA_H_Y[0] <= base["h_y"] <= F2.FAIXA_H_Y[1]
    ci_zero = any(inc[k]["p2_5"] <= 0.0 <= inc[k]["p97_5"] for k in ("c_f", "c_r"))
    usado = {"lam": float(np.clip(base["lam"], *F2.FAIXA_LAMBDA)), "h_y": float(np.clip(base["h_y"], *F2.FAIXA_H_Y))}
    return {**base, "incerteza_bootstrap": inc, "amostras": int(ay.size), "voltas": int(laps.size),
            "lam_na_faixa": lam_ok, "h_y_na_faixa": h_ok, "intervalo_passa_de_zero": bool(ci_zero),
            "usado": usado}


def erro_da_carga(frame: pd.DataFrame, p) -> Dict[str, object]:
    """A carga prevista (com `vx`, `a_x` e `a_y` gravados) contra a gravada, por roda e por regime, em N."""
    vx = frame["vx"].to_numpy(dtype=float)
    a_x = frame["a_x"].to_numpy(dtype=float)
    a_y = frame["a_y"].to_numpy(dtype=float)
    true = frame[[f"wheel_load_{w}" for w in WHEELS]].to_numpy(dtype=float)
    pred = F2.cargas(vx, a_x, a_y, p) * p.m
    good = np.isfinite(true).all(1) & np.isfinite(pred).all(1)
    reg = regimes(frame["B"].to_numpy(dtype=float), a_y, frame["T"].to_numpy(dtype=float), a_x)
    out = {}
    groups = [("todas", good)] + [(str(name), good & (reg == name)) for name in pd.unique(reg[good])]
    for name, sel in groups:
        err = pred[sel] - true[sel]
        out[name] = {"amostras": int(sel.sum())}
        for w, wheel in enumerate(WHEELS):
            mean_load = float(np.mean(true[sel, w]))
            rmse = float(np.sqrt(np.mean(err[:, w] ** 2)))
            out[name][wheel] = {"rmse_N": rmse, "vies_N": float(np.mean(err[:, w])), "carga_media_N": mean_load,
                                "rmse_pct": 100.0 * rmse / mean_load if mean_load else float("nan")}
    return out
