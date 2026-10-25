"""A geometria do carro medida pela telemetria do jogo (pedido 39; ADR 0024; `docs/modelo_fisico_m1.md`, 1.9).

A pagina de fisica da memoria compartilhada tem o ponto de contato de cada pneu
(`tyreContactPoint`), a direcao de cada pneu (`tyreContactHeading`) e a altura do
centro de massa (`cgHeight`). Com eles a geometria sai sem regressao cinematica
e sem abrir arquivo do carro:

* **`L`:** o ponto medio dos contatos dianteiros menos o dos traseiros, projetado
  na frente do carro; a mediana em reta (em movimento, |a_y| < 0,2 g);
* **`h/L`:** a mediana de `cgHeight` em movimento, dividida por `L`;
* **`k_delta`:** o angulo da direcao media dos dianteiros menos o da media dos
  traseiros contra o `steerAngle`, por regressao linear em toda a sessao;
* **`x_v`:** onde, ao longo do carro, a `localVelocity` e medida: num corpo
  rigido, `vy_gravada = v_lat,traseiro + x_v * r`.

**A ordem 4 x 3.** No ctypes do adaptador, `c_float * 4 * 3` e um vetor de 3 por
4; na memoria do jogo o campo e de 4 rodas por 3 coordenadas. Lido achatado, na
ordem da memoria, a roda `w`, coordenada `c`, fica no indice `3*w + c`.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from . import dados as D
from .convencoes import eixos

FORMA = "(-sen h, cos h)"     # a convencao achada na Parte B do pedido 37 (secao 3)
S_ESQUERDA = -1
CARRO = "rss_formula_rss_3_v6_2026"
PISTA = "vhe_interlagos"
L_PUBLICADO = 2.943

# Portoes (1.9).
L_FAIXA = (2.8, 3.8)
L_LARGURA_MAX = 0.03
K_FAIXA = (0.05, 1.5)
K_R2_MIN = 0.95
XV_MEIA_LARGURA_MAX = 0.2

VX_MOVIMENTO = 10.0
A_Y_RETA_G = 0.2
R_MIN_XV = 0.05
DRDT_MAX = 0.1
BOOTSTRAP = 200
SEMENTE = 39

COLUNAS_CP = tuple(f"cp_{i}" for i in range(12))
COLUNAS_CH = tuple(f"ch_{i}" for i in range(12))


def achatar_4x3(values) -> np.ndarray:
    """Um campo 4 x 3 da memoria -> (4, 3): roda por coordenada.

    Aceita os 12 numeros na ordem da memoria ou o vetor aninhado do ctypes
    (3 linhas de 4), que, percorrido em ordem, e a mesma sequencia da memoria.
    """
    def items(row):
        # O vetor do ctypes tem `len` e indice, mas nao se declara iteravel.
        return [row[i] for i in range(len(row))] if hasattr(row, "__len__") and not isinstance(row, (str, bytes)) else [row]

    flat = np.asarray([float(v) for row in items(values) for v in items(row)])
    if flat.size != 12:
        raise ValueError(f"esperava 12 numeros, vieram {flat.size}")
    return flat.reshape(4, 3)


def campos_4x3(frame: pd.DataFrame, prefix: str) -> np.ndarray:
    """As colunas `<prefix>_0` a `_11` da gravacao -> (n, 4, 3)."""
    return frame[[f"{prefix}_{i}" for i in range(12)]].to_numpy(dtype=float).reshape(-1, 4, 3)


def _xz(v: np.ndarray) -> np.ndarray:
    return v[..., [0, 2]]


def instantaneas(contact: np.ndarray, dirs: np.ndarray, heading: np.ndarray,
                 car: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
    """As medidas de cada amostra. `contact` e `dirs` (n, 4, 3), `heading` (n,), `car` (n, 3).

    Devolve o entre-eixos, as bitolas, o sentido das direcoes dos pneus, o
    angulo das rodas (medio, esquerdo e direito, positivo para a esquerda) e, com
    `car`, onde o ponto do carro fica a partir do eixo traseiro.
    """
    contact, dirs = np.atleast_3d(contact), np.atleast_3d(dirs)
    heading = np.atleast_1d(np.asarray(heading, dtype=float))
    front, left = eixos(heading, FORMA, S_ESQUERDA)
    cp = _xz(contact)
    front_mid, rear_mid = cp[:, :2].mean(axis=1), cp[:, 2:].mean(axis=1)
    axis = front_mid - rear_mid
    out = {
        "L": np.sum(axis * front, axis=1),
        "bitola_dianteira": np.abs(np.sum((cp[:, 0] - cp[:, 1]) * left, axis=1)),
        "bitola_traseira": np.abs(np.sum((cp[:, 2] - cp[:, 3]) * left, axis=1)),
    }
    d = _xz(dirs)
    # O sentido: as direcoes dos pneus contra o vetor do eixo traseiro para o dianteiro.
    out["sentido"] = np.sign(np.sum(d.mean(axis=1) * axis, axis=1))
    out["_eixos"] = (front, left, front_mid, rear_mid)
    if car is not None:
        car = np.atleast_2d(np.asarray(car, dtype=float))
        rel = _xz(car) - rear_mid
        out["x_carro"] = np.sum(rel * front, axis=1)
        out["y_carro"] = np.sum(rel * left, axis=1)
        out["altura_carro"] = car[:, 1] - contact[:, :, 1].mean(axis=1)
    return out


def angulos_das_rodas(dirs: np.ndarray, heading: np.ndarray, sentido: float = 1.0) -> Dict[str, np.ndarray]:
    """O angulo das rodas, positivo para a esquerda: dianteiros (media, esquerdo, direito) menos a media dos traseiros."""
    dirs = np.atleast_3d(dirs) * float(sentido)
    front, left = eixos(np.atleast_1d(heading), FORMA, S_ESQUERDA)
    d = _xz(dirs)
    fx, fy = np.einsum("nwk,nk->nw", d, front), np.einsum("nwk,nk->nw", d, left)
    theta = np.arctan2(fy, fx)

    def mean_angle(cols):
        return np.arctan2(fy[:, cols].mean(axis=1), fx[:, cols].mean(axis=1))

    rear = mean_angle([2, 3])
    return {"media": mean_angle([0, 1]) - rear, "esquerda": theta[:, 0] - rear, "direita": theta[:, 1] - rear}


def regressao(x: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """`y = c + s*x`, com R2."""
    good = np.isfinite(x) & np.isfinite(y)
    x, y = x[good], y[good]
    s, c = np.polyfit(x, y, 1)
    resid = y - (c + s * x)
    r2 = 1.0 - np.sum(resid ** 2) / np.sum((y - y.mean()) ** 2)
    return {"inclinacao": float(s), "intercepto": float(c), "r2": float(r2), "n": int(x.size)}


# ------------------------------------------------------------ a sessao ---

def sem_relogio(raw: pd.DataFrame) -> pd.DataFrame:
    """As amostras com um `packetId` da fisica diferente do anterior (para `k_delta`)."""
    packet = raw["packet_id"].to_numpy()
    keep = np.concatenate([[True], packet[1:] != packet[:-1]])
    return raw.loc[keep].reset_index(drop=True)


COLUNAS_RELOGIO = ("heading", "steer", "speed_kmh", "lv_x", "lv_z", "lav_y", "acc_x", "cg_height",
                   *COLUNAS_CP)


def com_relogio(raw: pd.DataFrame, dt: float = D.DT, gap_s: float = D.GAP_S) -> pd.DataFrame:
    """O preparo da Parte B: cronometro do jogo, sem repetidas, trechos em buracos de 50 ms, grade de 50 ms.

    O cronometro zera a cada volta; cada volta (uma queda do cronometro) e
    tratada a parte, como no store.
    """
    t = raw["i_current_time_ms"].to_numpy(dtype=float) / 1000.0
    lap = np.concatenate([[0], np.cumsum(np.diff(t) < -1.0)])
    blocks = []
    for number in np.unique(lap):
        part = raw.loc[lap == number].copy()
        part["lap_time_s"] = part["i_current_time_ms"].to_numpy(dtype=float) / 1000.0
        kept, _ = D.descartar_repetidas(part)
        for j, (a, b) in enumerate(D.cortar_trechos(kept["lap_time_s"].to_numpy(dtype=float), gap_s)):
            block = D.reamostrar(kept.iloc[a:b], columns=COLUNAS_RELOGIO, dt=dt)
            if len(block) >= 3:
                block.insert(0, "trecho", f"{number:03d}/{j:04d}")
                blocks.append(block)
    if not blocks:
        raise ValueError("a sessao nao tem nenhum trecho com o cronometro andando")
    return pd.concat(blocks, ignore_index=True)


def _derivada(frame: pd.DataFrame, values: np.ndarray, dt: float = D.DT) -> np.ndarray:
    out = np.full(values.shape, np.nan)
    for _, index in frame.groupby("trecho", sort=False).indices.items():
        if index.size >= 2:
            out[index] = np.gradient(values[index], dt, axis=0)
    return out


def sinal_a_y(frame: pd.DataFrame) -> int:
    """O sinal que faz `accG[0]` ser positiva para a esquerda (contra `vx * r`, como na secao 3)."""
    vx, r, acc = (frame[c].to_numpy(dtype=float) for c in ("lv_z", "lav_y", "acc_x"))
    sel = np.isfinite(vx) & np.isfinite(r) & np.isfinite(acc) & (vx > VX_MOVIMENTO)
    return int(np.sign(np.dot(acc[sel], vx[sel] * r[sel]))) or 1


def medir_k_delta(raw: pd.DataFrame) -> Dict[str, object]:
    frame = sem_relogio(raw)
    contact, dirs = campos_4x3(frame, "cp"), campos_4x3(frame, "ch")
    heading = frame["heading"].to_numpy(dtype=float)
    inst = instantaneas(contact, dirs, heading)
    sentido = float(np.sign(np.nanmedian(inst["sentido"]))) or 1.0
    ang = angulos_das_rodas(dirs, heading, sentido)
    steer = frame["steer"].to_numpy(dtype=float)
    fits = {side: regressao(steer, ang[side]) for side in ("media", "esquerda", "direita")}
    out = {"sentido_invertido": bool(sentido < 0), "amostras": int(len(frame)),
           "steer_faixa": [float(np.nanmin(steer)), float(np.nanmax(steer))]}
    for side, fit in fits.items():
        out[side] = {**fit, "k_delta": -fit["inclinacao"], "convergencia_rad": fit["intercepto"]}
    # Linearidade: a razao angulo / volante por faixa de |steer|, sem o intercepto.
    edges = np.array([0.02, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5])
    rows = []
    centred = ang["media"] - fits["media"]["intercepto"]
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (np.abs(steer) >= lo) & (np.abs(steer) < hi)
        if sel.sum() >= 20:
            rows.append({"steer_de": float(lo), "steer_ate": float(hi), "n": int(sel.sum()),
                         "k_delta_local": float(-np.median(centred[sel] / steer[sel]))})
    out["linearidade"] = rows
    out["_angulos"] = ang
    out["_steer"] = steer
    return out


def medir_relogio(raw: pd.DataFrame, k_delta: Optional[float] = None) -> Dict[str, object]:
    """`L`, `cgHeight` e `x_v` na parte com relogio; e a regressao de reserva de `k_delta`."""
    from .dados import G
    frame = com_relogio(raw)
    contact = frame[list(COLUNAS_CP)].to_numpy(dtype=float).reshape(-1, 4, 3)
    heading = frame["heading"].to_numpy(dtype=float)
    vx = frame["lv_z"].to_numpy(dtype=float)
    r = frame["lav_y"].to_numpy(dtype=float)
    vy_g = frame["lv_x"].to_numpy(dtype=float)
    a_y = sinal_a_y(frame) * frame["acc_x"].to_numpy(dtype=float) * G
    moving = vx >= VX_MOVIMENTO
    straight = moving & (np.abs(a_y) < A_Y_RETA_G * G)

    # Aqui so os contatos importam; as direcoes dos pneus nao entram nesta parte.
    inst = instantaneas(contact, contact, heading)
    L_all = inst["L"]
    L_vals = L_all[straight & np.isfinite(L_all)]
    L = float(np.median(L_vals))
    p5, p95 = np.percentile(L_vals, [5, 95])
    cg = frame["cg_height"].to_numpy(dtype=float)[moving]

    front, left, front_mid, rear_mid = inst["_eixos"]
    v_rear = _derivada(frame, rear_mid)
    v_front = _derivada(frame, front_mid)
    lat_rear = np.sum(v_rear * left, axis=1)
    lat_front = np.sum(v_front * left, axis=1)
    sel = moving & (np.abs(r) >= R_MIN_XV) & np.isfinite(lat_rear) & np.isfinite(vy_g)

    def slope(idx, lat):
        y, x = vy_g[idx] - lat[idx], r[idx]
        return float(np.dot(x, y) / np.dot(x, x))

    idx_all = np.flatnonzero(sel)
    x_v = slope(idx_all, lat_rear)
    x_v_front = L + slope(idx_all, lat_front)
    trechos = frame["trecho"].to_numpy()
    groups = {t: idx_all[trechos[idx_all] == t] for t in np.unique(trechos[idx_all])}
    keys = np.array(list(groups))
    rng = np.random.default_rng(SEMENTE)
    draws = []
    for _ in range(BOOTSTRAP):
        pick = rng.choice(keys, size=keys.size, replace=True)
        draws.append(slope(np.concatenate([groups[k] for k in pick]), lat_rear))
    lo, hi = np.percentile(draws, [2.5, 97.5])

    out = {
        "L": L, "L_p5": float(p5), "L_p95": float(p95), "L_amostras": int(L_vals.size),
        "L_largura_relativa": float((p95 - p5) / L),
        "cg_height": float(np.median(cg)), "cg_height_p5_p95": [float(v) for v in np.percentile(cg, [5, 95])],
        "x_v": x_v, "x_v_ic95": [float(lo), float(hi)], "x_v_meia_largura": float((hi - lo) / 2),
        "x_v_pelo_eixo_dianteiro": float(x_v_front), "x_v_amostras": int(idx_all.size), "x_v_trechos": int(keys.size),
        "bitola_dianteira": float(np.median(inst["bitola_dianteira"][straight])),
        "bitola_traseira": float(np.median(inst["bitola_traseira"][straight])),
        "passos": int(len(frame)), "trechos": int(frame["trecho"].nunique()),
        "sinal_acc_x": sinal_a_y(frame),
    }
    # Reserva de k_delta (1.9): -steer = (L/k_delta)*kappa + K*a_y, em regime permanente.
    drdt = _derivada(frame, r)
    steady = moving & np.isfinite(drdt) & (np.abs(drdt) < DRDT_MAX)
    kappa = r / np.maximum(vx, 1e-6)
    X = np.column_stack([kappa[steady], a_y[steady]])
    coef, *_ = np.linalg.lstsq(X, -frame["steer"].to_numpy(dtype=float)[steady], rcond=None)
    out["reserva_k_delta"] = {"L_sobre_k": float(coef[0]), "K": float(coef[1]), "amostras": int(steady.sum()),
                              "k_delta": float(L / coef[0]) if coef[0] else float("nan")}
    return out


def portoes(L: Dict[str, object], K: Dict[str, object]) -> Dict[str, object]:
    """Os 3 portoes da 1.9 e o valor que o modelo usa em cada caso."""
    L_ok = bool(L_FAIXA[0] <= L["L"] <= L_FAIXA[1] and L["L_largura_relativa"] < L_LARGURA_MAX)
    L_used = L["L"] if L_ok else L_PUBLICADO
    k = K["media"]["k_delta"]
    k_ok = bool(K_FAIXA[0] <= k <= K_FAIXA[1] and K["media"]["r2"] >= K_R2_MIN)
    k_used = k if k_ok else L_used / L["reserva_k_delta"]["L_sobre_k"]
    xv_ok = bool(L["x_v_meia_largura"] < XV_MEIA_LARGURA_MAX)
    return {
        "L": {"valor": L["L"], "faixa": list(L_FAIXA), "largura_relativa": L["L_largura_relativa"],
              "passa": L_ok, "usado": float(L_used), "fonte": "medido" if L_ok else "publicado (2,943 m)"},
        "k_delta": {"valor": k, "faixa": list(K_FAIXA), "r2": K["media"]["r2"], "passa": k_ok, "usado": float(k_used),
                    "fonte": "medido" if k_ok else "regressao em regime permanente"},
        "x_v": {"valor": L["x_v"], "meia_largura": L["x_v_meia_largura"], "passa": xv_ok,
                "usado": float(L["x_v"]) if xv_ok else None,
                "fonte": "medido" if xv_ok else "velocidade suposta no centro de massa"},
        "h_L": {"valor": L["cg_height"] / L_used},
    }


def vy_no_centro(vy_gravada: np.ndarray, r: np.ndarray, b: float, x_v: Optional[float]) -> np.ndarray:
    """`vy_cm = vy_gravada + (b - x_v) * r`; sem `x_v` (portao falhou), a gravada ja e a do centro."""
    if x_v is None:
        return np.asarray(vy_gravada, dtype=float)
    return np.asarray(vy_gravada, dtype=float) + (b - x_v) * np.asarray(r, dtype=float)
