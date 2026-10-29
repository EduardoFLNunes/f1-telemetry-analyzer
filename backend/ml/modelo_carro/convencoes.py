"""As conferencias de convencao, antes de qualquer ajuste (pedido 37, Parte B.3).

A convencao do modelo: x para a frente, y para a esquerda, giro positivo para a
esquerda. A regra que decide cada sinal foi fixada antes de olhar os dados
(`docs/modelo_fisico_m1.md`, 1.3):

* **guinada (`s_r`):** o sinal que faz `a_y ~ vx * r` (centripeta) ter
  inclinacao positiva, com `a_y` positiva para a esquerda (M0, ADR 0003);
* **heading:** a derivada dele contra a guinada gravada da +1 ou -1;
* **velocidade lateral (`s_vy`):** a velocidade do mundo projetada no eixo do
  carro. O eixo vem do `heading` (a forma que alinha com a velocidade do mundo),
  e "esquerda" e o lado para onde o rumo gira nas curvas a esquerda da
  geometria (`Corner.direction = +1`). `s_vy` e o sinal da inclinacao de
  `localVelocity.x` contra essa projecao;
* **velocidade longitudinal:** `localVelocity.z` contra a projecao para a frente;
* **volante:** com |a_y| >= 0,5 g, o sinal de `-steer` e o de `r`.

Uma conferencia bate quando, em todas as amostras, a inclinacao fica entre 0,95 e
1,05 em modulo (0,90 a 1,10 para `vy`) e a correlacao e pelo menos 0,95 (0,90 para
`vy`), e quando o sinal e o mesmo nas curvas a esquerda e nas a direita; o volante,
em pelo menos 95% (no geral e em cada lado).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from .dados import DT, G

INCLINACAO = (0.95, 1.05)
INCLINACAO_VY = (0.90, 1.10)
CORRELACAO = 0.95
CORRELACAO_VY = 0.90
VOLANTE_MIN = 0.95
A_Y_VOLANTE_G = 0.5

# As 8 formas de tirar a direcao para a frente, no plano (x, z) do mundo, do heading.
FORMAS = {
    "(sen h, cos h)": lambda h: (np.sin(h), np.cos(h)),
    "(-sen h, cos h)": lambda h: (-np.sin(h), np.cos(h)),
    "(sen h, -cos h)": lambda h: (np.sin(h), -np.cos(h)),
    "(-sen h, -cos h)": lambda h: (-np.sin(h), -np.cos(h)),
    "(cos h, sen h)": lambda h: (np.cos(h), np.sin(h)),
    "(-cos h, sen h)": lambda h: (-np.cos(h), np.sin(h)),
    "(cos h, -sen h)": lambda h: (np.cos(h), -np.sin(h)),
    "(-cos h, -sen h)": lambda h: (-np.cos(h), -np.sin(h)),
}


def derivada(frame: pd.DataFrame, column: str, dt: float = DT) -> np.ndarray:
    """Derivada no tempo, dentro de cada trecho (diferenca central; nas pontas, de um lado)."""
    out = np.full(len(frame), np.nan)
    for _, index in frame.groupby("trecho", sort=False).indices.items():
        values = frame[column].to_numpy(dtype=float)[index]
        if values.size >= 2:
            out[index] = np.gradient(values, dt)
    return out


def inclinacao(x: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """`y = k*x` pela origem, e a correlacao de Pearson."""
    good = np.isfinite(x) & np.isfinite(y)
    x, y = x[good], y[good]
    if x.size < 10:
        return {"n": int(x.size), "inclinacao": float("nan"), "correlacao": float("nan")}
    slope = float(np.dot(x, y) / np.dot(x, x))
    corr = float(np.corrcoef(x, y)[0, 1])
    return {"n": int(x.size), "inclinacao": slope, "correlacao": corr}


def lado_da_curva(s: np.ndarray, corners, length: float) -> np.ndarray:
    """+1 dentro de uma curva a esquerda da geometria, -1 a direita, 0 fora."""
    side = np.zeros(len(s), dtype=int)
    s = np.asarray(s, dtype=float)
    for corner in corners:
        span = np.mod(corner.end_s - corner.start_s, length)
        inside = np.mod(s - corner.start_s, length) <= span
        side[inside] = int(corner.direction)
    return side


def curva_de(s: np.ndarray, corners, length: float) -> np.ndarray:
    """O rotulo da curva de cada ponto (`C01-esq`...), ou '' fora das curvas."""
    out = np.full(len(s), "", dtype=object)
    for corner in corners:
        span = np.mod(corner.end_s - corner.start_s, length)
        inside = np.mod(np.asarray(s, dtype=float) - corner.start_s, length) <= span
        out[inside] = corner.label
    return out


def _bate(result: Dict[str, float], faixa: Tuple[float, float], corr_min: float) -> bool:
    k, c = abs(result.get("inclinacao", np.nan)), result.get("correlacao", np.nan)
    return bool(np.isfinite(k) and faixa[0] <= k <= faixa[1] and np.isfinite(c) and abs(c) >= corr_min)


def _por_lado(x, y, side) -> Dict[str, Dict[str, float]]:
    return {"todas": inclinacao(x, y), "esquerda": inclinacao(x[side > 0], y[side > 0]),
            "direita": inclinacao(x[side < 0], y[side < 0])}


def _conferencia(nome: str, x, y, side, faixa, corr_min) -> Dict[str, object]:
    parts = _por_lado(x, y, side)
    # O texto registrado (1.3): a inclinacao e a correlacao em todas as amostras, e o
    # mesmo sinal nas curvas a esquerda e nas a direita. Dentro de um lado so, a faixa
    # dos valores e estreita e a correlacao cai sem o sinal estar em duvida; ela vai
    # no relatorio, mas nao decide.
    signs = {np.sign(parts[k]["inclinacao"]) for k in ("todas", "esquerda", "direita")}
    ok = _bate(parts["todas"], faixa, corr_min) and len(signs) == 1
    return {"nome": nome, **parts, "sinal": int(np.sign(parts["todas"]["inclinacao"])), "bate": bool(ok)}


@dataclass
class Convencoes:
    """O que as conferencias decidiram: multiplica o canal gravado para chegar na convencao do modelo."""

    s_r: int
    s_psi: int          # sinal de psi (rumo do modelo) em relacao ao heading gravado
    s_vy: int
    forma_heading: str  # como o heading da a direcao para a frente no mundo
    s_esquerda: int     # esquerda = s_esquerda * (-f_z, f_x)

    def to_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


def eixos(heading: np.ndarray, forma: str, s_esquerda: int) -> Tuple[np.ndarray, np.ndarray]:
    """(frente, esquerda) no plano (x, z) do mundo, cada um (n, 2)."""
    fx, fz = FORMAS[forma](np.asarray(heading, dtype=float))
    front = np.column_stack([fx, fz])
    left = s_esquerda * np.column_stack([-fz, fx])
    return front, left


def conferir(frame: pd.DataFrame, corners, length: float) -> Tuple[Dict[str, object], Convencoes]:
    """As 5 conferencias nos dados reamostrados (todas as sessoes juntas e por sessao)."""
    side = lado_da_curva(frame["s"].to_numpy(dtype=float), corners, length)
    yaw = frame["yaw_rate"].to_numpy(dtype=float)
    vx_local = frame["velocity_long"].to_numpy(dtype=float)
    vy_local = frame["velocity_lat"].to_numpy(dtype=float)
    a_y = frame["lateral_g"].to_numpy(dtype=float) * G
    steer = frame["steer_angle"].to_numpy(dtype=float)
    heading = frame["heading"].to_numpy(dtype=float)
    vw = frame[["vel_wx", "vel_wz"]].to_numpy(dtype=float)
    speed_w = np.hypot(vw[:, 0], vw[:, 1])

    out: Dict[str, object] = {}

    # 0. A aceleracao lateral positiva para a esquerda (M0), contra a geometria.
    strong = np.abs(a_y) >= 0.5 * G
    out["a_y_contra_geometria"] = {
        "esquerda_com_a_y_positiva": float(np.mean(a_y[strong & (side > 0)] > 0)),
        "direita_com_a_y_negativa": float(np.mean(a_y[strong & (side < 0)] < 0)),
    }

    # 1. Guinada: a_y ~ vx * yaw.
    moving = vx_local > 10.0
    check_r = _conferencia("a_y contra vx x guinada gravada", np.where(moving, vx_local * yaw, np.nan), a_y,
                           side, INCLINACAO, CORRELACAO)
    s_r = check_r["sinal"]
    out["guinada"] = check_r

    # 2. Heading: a derivada contra a guinada gravada.
    dh = derivada(frame, "heading")
    turning = np.abs(yaw) > 0.05
    check_h = _conferencia("derivada do heading contra a guinada gravada", np.where(turning, yaw, np.nan), dh,
                           side, INCLINACAO, CORRELACAO)
    s_psi = s_r * check_h["sinal"]     # psi do modelo gira como r: psi = s_psi * heading
    out["heading"] = check_h

    # 3. A forma do heading: a que alinha com a velocidade do mundo.
    fast = speed_w > 20.0
    unit = vw[fast] / speed_w[fast, None]
    scores = {}
    for name, fn in FORMAS.items():
        fx, fz = fn(heading[fast])
        scores[name] = float(np.median(fx * unit[:, 0] + fz * unit[:, 1]))
    forma = max(scores, key=scores.get)
    fx, fz = FORMAS[forma](heading)
    # Esquerda: o lado para onde a frente gira nas curvas a esquerda da geometria.
    dfx, dfz = derivada(frame.assign(_fx=fx), "_fx"), derivada(frame.assign(_fz=fz), "_fz")
    turn = dfx * (-fz) + dfz * fx
    s_esquerda = int(np.sign(np.nanmean(turn[(side > 0) & fast])))
    front, left = eixos(heading, forma, s_esquerda)
    vx_world = np.sum(vw * front, axis=1)
    vy_world = np.sum(vw * left, axis=1)
    out["forma_heading"] = {"escolhida": forma, "cosseno_mediano": scores,
                            "giro_na_esquerda": float(np.nanmean(turn[(side > 0) & fast])),
                            "giro_na_direita": float(np.nanmean(turn[(side < 0) & fast]))}

    moving_w = speed_w > 10.0
    check_vy = _conferencia("localVelocity.x contra a velocidade do mundo para a esquerda",
                            np.where(moving_w, vy_world, np.nan), vy_local, side, INCLINACAO_VY, CORRELACAO_VY)
    s_vy = check_vy["sinal"]
    out["velocidade_lateral"] = check_vy
    check_vx = _conferencia("localVelocity.z contra a velocidade do mundo para a frente",
                            np.where(moving_w, vx_world, np.nan), vx_local, side, INCLINACAO, CORRELACAO)
    out["velocidade_longitudinal"] = check_vx
    speed = frame["speed_kmh"].to_numpy(dtype=float) / 3.6
    out["velocidade_longitudinal_contra_speedKmh"] = inclinacao(np.where(moving_w, speed, np.nan), vx_local)

    # 4. Volante contra guinada.
    r = s_r * yaw
    sel = np.abs(a_y) >= A_Y_VOLANTE_G * G
    agree = np.sign(-steer) == np.sign(r)
    volante = {"todas": float(np.mean(agree[sel])), "esquerda": float(np.mean(agree[sel & (side > 0)])),
               "direita": float(np.mean(agree[sel & (side < 0)])), "n": int(sel.sum())}
    volante["bate"] = bool(min(volante["todas"], volante["esquerda"], volante["direita"]) >= VOLANTE_MIN)
    out["volante"] = volante

    out["todas_batem"] = bool(check_r["bate"] and check_h["bate"] and check_vy["bate"] and check_vx["bate"]
                              and volante["bate"])
    conv = Convencoes(s_r=int(s_r), s_psi=int(s_psi), s_vy=int(s_vy), forma_heading=forma, s_esquerda=s_esquerda)
    return out, conv


def sinais_por_curva(frame: pd.DataFrame, conv: Convencoes, corners, length: float) -> List[Dict[str, object]]:
    """Por curva: as medianas de vy, r, -steer e a_y na convencao do modelo, e a velocidade."""
    labels = curva_de(frame["s"].to_numpy(dtype=float), corners, length)
    vy = conv.s_vy * frame["velocity_lat"].to_numpy(dtype=float)
    r = conv.s_r * frame["yaw_rate"].to_numpy(dtype=float)
    steer = -frame["steer_angle"].to_numpy(dtype=float)
    a_y = frame["lateral_g"].to_numpy(dtype=float) * G
    vx = frame["velocity_long"].to_numpy(dtype=float)
    rows = []
    for corner in corners:
        sel = labels == corner.label
        if not sel.any():
            continue
        rows.append({"curva": corner.label, "n": int(sel.sum()), "vx_mediana_kmh": float(np.median(vx[sel]) * 3.6),
                     "vy_mediana": float(np.median(vy[sel])), "vy_positiva": float(np.mean(vy[sel] > 0)),
                     "r_mediana": float(np.median(r[sel])), "menos_steer_mediana": float(np.median(steer[sel])),
                     "a_y_mediana": float(np.median(a_y[sel]))})
    return rows


def no_modelo(frame: pd.DataFrame, conv: Convencoes) -> pd.DataFrame:
    """As colunas na convencao do modelo: vx, vy, r, psi, steer, T, B, a_y, a_x."""
    out = frame.copy()
    out["vx"] = frame["velocity_long"].to_numpy(dtype=float)
    out["vy"] = conv.s_vy * frame["velocity_lat"].to_numpy(dtype=float)
    out["r"] = conv.s_r * frame["yaw_rate"].to_numpy(dtype=float)
    out["psi"] = conv.s_psi * frame["heading"].to_numpy(dtype=float)
    out["steer"] = frame["steer_angle"].to_numpy(dtype=float)
    out["T"] = frame["throttle"].to_numpy(dtype=float)
    out["B"] = frame["brake"].to_numpy(dtype=float)
    out["a_y"] = frame["lateral_g"].to_numpy(dtype=float) * G
    out["a_x"] = frame["longitudinal_g"].to_numpy(dtype=float) * G
    return out
