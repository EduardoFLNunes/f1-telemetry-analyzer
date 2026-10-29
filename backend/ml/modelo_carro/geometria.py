"""Massa, cargas, entre-eixos e a unidade do volante, medidos por conta direta (pedido 37, Parte C.3 e C.4).

O `data.acd` do carro e criptografado e nao e aberto (ADR 0017): tudo sai da
telemetria das sessoes de treino da rodada. As regras foram registradas antes de
construir (`docs/modelo_fisico_m1.md`, 1.4):

* **massa, carga aerodinamica e distribuicao:** a soma das 4 cargas e
  `m*g + m*kL*v^2`, e a da frente `m*g*w_f + m*kL*f_aero*v^2`, com |a_x| e
  |a_y| < 0,1 g;
* **h/L:** o que sobra da carga da frente contra `a_x`, com |a_y| < 0,1 g
  (`-m*(h/L)*a_x`);
* **b:** o eixo traseiro anda na direcao da roda, menos a deriva:
  `vy = b*r + c_r*vx*a_y + d`, com |a_y| <= 0,5 g, `vx` >= 10 m/s e freio < 0,05;
* **L = b / w_f** (o peso parado se divide na razao das distancias), `a = L - b`;
* **k_delta:** o eixo dianteiro anda na direcao da roda, menos a deriva:
  `(vy + a*r)/vx = k_delta*(-steer) + c_f*a_y + d`, nas mesmas amostras.

A incerteza de `b`, `L` e `k_delta` sai de um bootstrap agrupado por volta.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .dados import G, WHEELS

BOOTSTRAP = 200
SEMENTE = 37


def _amostras(frame: pd.DataFrame) -> Dict[str, np.ndarray]:
    loads = frame[[f"wheel_load_{w}" for w in WHEELS]].to_numpy(dtype=float)
    return {
        "lap": frame["lap_id"].to_numpy(), "vx": frame["vx"].to_numpy(dtype=float),
        "vy": frame["vy"].to_numpy(dtype=float), "r": frame["r"].to_numpy(dtype=float),
        "steer": frame["steer"].to_numpy(dtype=float), "B": frame["B"].to_numpy(dtype=float),
        "a_x": frame["a_x"].to_numpy(dtype=float), "a_y": frame["a_y"].to_numpy(dtype=float),
        "total": loads.sum(axis=1), "front": loads[:, 0] + loads[:, 1],
    }


def _por_volta(lap: np.ndarray, X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, Dict[str, Tuple[np.ndarray, np.ndarray]]]:
    """X'X e X'Y de cada volta, para o bootstrap somar sem refazer as contas."""
    keys = np.unique(lap)
    stats = {}
    for key in keys:
        sel = lap == key
        stats[key] = (X[sel].T @ X[sel], X[sel].T @ Y[sel])
    return keys, stats


def _resolver(stats, keys) -> np.ndarray:
    xtx = sum(stats[k][0] for k in keys)
    xty = sum(stats[k][1] for k in keys)
    return np.linalg.solve(xtx, xty)


def medir(frame: pd.DataFrame, bootstrap: int = BOOTSTRAP, seed: int = SEMENTE) -> Dict[str, object]:
    """Os parametros medidos, com a incerteza. `frame` ja na convencao do modelo (`convencoes.no_modelo`)."""
    s = _amostras(frame)
    finite_loads = np.isfinite(s["total"]) & np.isfinite(s["front"]) & (s["total"] > 0)
    calm = finite_loads & (np.abs(s["a_x"]) < 0.1 * G) & (np.abs(s["a_y"]) < 0.1 * G)

    # Cargas: [1, v^2] -> (total, frente).
    X_load = np.column_stack([np.ones(calm.sum()), s["vx"][calm] ** 2])
    Y_load = np.column_stack([s["total"][calm], s["front"][calm]])
    keys_l, stats_l = _por_volta(s["lap"][calm], X_load, Y_load)

    def cargas(keys):
        coef = _resolver(stats_l, keys)       # (2, 2): linhas [1, v^2], colunas [total, frente]
        mg, mkl = coef[0, 0], coef[1, 0]
        m = mg / G
        return {"m": m, "kappa_L": mkl / m, "w_f": coef[0, 1] / mg, "f_aero": coef[1, 1] / mkl,
                "_coef": coef}

    base = cargas(keys_l)

    # h/L: o resto da carga da frente contra a_x.
    lateral_calm = finite_loads & (np.abs(s["a_y"]) < 0.1 * G)
    coef = base["_coef"]
    rest = s["front"][lateral_calm] - (coef[0, 1] + coef[1, 1] * s["vx"][lateral_calm] ** 2)
    ax = s["a_x"][lateral_calm]
    h_L = float(-(np.dot(ax, rest) / np.dot(ax, ax)) / base["m"])

    # b e k_delta.
    sel = ((np.abs(s["a_y"]) <= 0.5 * G) & (s["vx"] >= 10.0) & (s["B"] < 0.05)
           & np.isfinite(s["vy"]) & np.isfinite(s["r"]) & np.isfinite(s["steer"]))
    vx, vy, r, a_y, steer = s["vx"][sel], s["vy"][sel], s["r"][sel], s["a_y"][sel], s["steer"][sel]
    X_b = np.column_stack([r, vx * a_y, np.ones(sel.sum())])
    keys_b, stats_b = _por_volta(s["lap"][sel], X_b, vy[:, None])
    X_k = np.column_stack([-steer, a_y, np.ones(sel.sum())])
    Y_k = np.column_stack([vy / vx, r / vx])
    keys_k, stats_k = _por_volta(s["lap"][sel], X_k, Y_k)

    def cinematica(keys, w_f):
        cb = _resolver(stats_b, keys)[:, 0]
        b = float(cb[0])
        L = b / w_f
        a = L - b
        ck = _resolver(stats_k, keys)            # (3, 2): colunas vy/vx e r/vx
        coef_k = ck[:, 0] + a * ck[:, 1]
        return {"b": b, "c_r": float(cb[1]), "d_r": float(cb[2]), "L": L, "a": a,
                "k_delta": float(coef_k[0]), "c_f": float(coef_k[1]), "d_f": float(coef_k[2])}

    kin = cinematica(keys_b, base["w_f"])

    rng = np.random.default_rng(seed)
    laps = np.array(sorted(set(keys_l) & set(keys_b)))
    draws = []
    for _ in range(bootstrap):
        pick = rng.choice(laps, size=laps.size, replace=True)
        loads = cargas(pick)
        k = cinematica(pick, loads["w_f"])
        draws.append([loads["m"], loads["w_f"], k["b"], k["L"], k["k_delta"]])
    draws = np.asarray(draws)
    names = ["m", "w_f", "b", "L", "k_delta"]
    incerteza = {name: {"p2_5": float(np.percentile(draws[:, i], 2.5)), "p97_5": float(np.percentile(draws[:, i], 97.5)),
                        "desvio": float(np.std(draws[:, i]))} for i, name in enumerate(names)}

    # A fracao do freio na frente: a media do brakeBias gravado.
    brake_bias = float(np.nanmean(frame["brake_bias"].to_numpy(dtype=float)))
    return {
        "m": float(base["m"]), "kappa_L": float(base["kappa_L"]), "w_f": float(base["w_f"]),
        "f_aero": float(base["f_aero"]), "h_L": h_L, "b": kin["b"], "L": kin["L"], "a": kin["a"],
        "k_delta": kin["k_delta"], "brake_bias": brake_bias,
        "termos": {k: kin[k] for k in ("c_r", "d_r", "c_f", "d_f")},
        "amostras": {"cargas": int(calm.sum()), "h_L": int(lateral_calm.sum()), "cinematica": int(sel.sum()),
                     "voltas": int(laps.size)},
        "incerteza_bootstrap": incerteza,
        "k_delta_em_graus": float(np.degrees(kin["k_delta"])),
    }
