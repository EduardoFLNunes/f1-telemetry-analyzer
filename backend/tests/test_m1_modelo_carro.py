"""M1, o modelo do carro para a frente (pedido 37; ADR 0022)."""

from __future__ import annotations

from collections import namedtuple

import numpy as np
import pandas as pd
import pytest

from ml.modelo_carro import convencoes as C
from ml.modelo_carro import dados as D

Curva = namedtuple("Curva", "start_s end_s direction label")


# ------------------------------------------------------------- dados ---

def test_descarta_amostra_com_cronometro_parado_ou_para_tras():
    frame = pd.DataFrame({"lap_time_s": [0.000, 0.015, 0.015, 0.030, 0.027, 0.045, np.nan, 0.060],
                          "v": range(8)})
    kept, dropped = D.descartar_repetidas(frame)
    assert kept["lap_time_s"].tolist() == [0.000, 0.015, 0.030, 0.045, 0.060]
    assert kept["v"].tolist() == [0, 1, 3, 5, 7]
    assert dropped == 3


def test_corta_trecho_em_buraco_de_50_ms_ou_mais():
    t = np.array([0.0, 0.015, 0.030, 0.080, 0.095, 0.1449, 0.20])
    # 0.030 -> 0.080 e 50 ms: corta; 0.095 -> 0.1449 e 49,9 ms: nao corta; 0.1449 -> 0.20: corta.
    assert D.cortar_trechos(t) == [(0, 3), (3, 6), (6, 7)]
    assert D.cortar_trechos(np.array([])) == []


def test_reamostra_linear_no_passo_e_desdobra_o_heading():
    frame = pd.DataFrame({"lap_time_s": [10.0, 10.03, 10.06, 10.12],
                          "speed_kmh": [100.0, 103.0, 106.0, 112.0],
                          "heading": [3.10, -3.12, -3.06, -2.94]})
    out = D.reamostrar(frame, columns=("speed_kmh", "heading"), dt=0.05)
    np.testing.assert_allclose(out["t"], [10.0, 10.05, 10.10])
    np.testing.assert_allclose(out["speed_kmh"], [100.0, 105.0, 110.0])
    # 3,10 -> -3,12 cruza o pi: desdobrado, o heading anda devagar e nao salta 6 rad.
    assert np.all(np.abs(np.diff(out["heading"])) < 0.2)
    assert out["k"].tolist() == [0, 1, 2]


def test_trecho_nao_atravessa_buraco_na_volta():
    t = np.concatenate([np.arange(0, 1.0, 0.015), np.arange(1.2, 2.0, 0.015)])
    frame = pd.DataFrame({"lap_time_s": t, "speed_kmh": 100.0 + t})
    pieces = D.cortar_trechos(t)
    assert len(pieces) == 2
    blocks = [D.reamostrar(frame.iloc[a:b], columns=("speed_kmh",)) for a, b in pieces]
    assert blocks[0]["t"].max() < 1.0 and blocks[1]["t"].min() >= 1.2


# -------------------------------------------------------- convencoes ---

def _curva_sintetica(direction: int, s0: float, n: int = 200, v: float = 30.0, radius: float = 60.0,
                     vy: float = -0.4, s_vy_gravado: int = 1) -> pd.DataFrame:
    """Um carro numa curva, na convencao achada no jogo: frente = (-sen h, cos h), esquerda = (cos h, sen h),
    o heading diminui girando para a esquerda, e a guinada gravada e positiva para a esquerda."""
    dt = 0.05
    t = np.arange(n) * dt
    v = v * (1.0 + 0.3 * np.sin(t))           # freia e acelera na curva: a velocidade varia
    r = direction * v / radius
    h = 0.3 - np.concatenate([[0.0], np.cumsum(0.5 * dt * (r[1:] + r[:-1]))])
    front = np.column_stack([-np.sin(h), np.cos(h)])
    left = np.column_stack([np.cos(h), np.sin(h)])
    lat = direction * vy
    world = v[:, None] * front + lat * left
    return pd.DataFrame({
        "trecho": f"t{direction}", "s": s0 + 30.0 * t, "heading": h, "yaw_rate": r,
        "velocity_long": v, "velocity_lat": np.full(n, s_vy_gravado * lat),
        "lateral_g": v * r / D.G, "steer_angle": -0.5 * r,
        "vel_wx": world[:, 0], "vel_wz": world[:, 1], "speed_kmh": 3.6 * np.hypot(v, lat),
        "throttle": 0.5, "brake": 0.0, "longitudinal_g": 0.0,
    })


def _pista():
    corners = [Curva(0.0, 6000.0, +1, "C01-esq"), Curva(10000.0, 16000.0, -1, "C02-dir")]
    frame = pd.concat([_curva_sintetica(+1, 0.0), _curva_sintetica(-1, 10000.0)], ignore_index=True)
    return frame, corners


def test_convencoes_numa_curva_a_esquerda_e_numa_a_direita():
    frame, corners = _pista()
    result, conv = C.conferir(frame, corners, 20000.0)
    assert result["todas_batem"]
    assert (conv.s_r, conv.s_psi, conv.s_vy) == (1, -1, 1)
    assert conv.forma_heading == "(-sen h, cos h)"
    model = C.no_modelo(frame, conv)
    esquerda, direita = model.iloc[50], model.iloc[250]
    assert esquerda["r"] > 0 and esquerda["a_y"] > 0 and -esquerda["steer"] > 0
    assert direita["r"] < 0 and direita["a_y"] < 0 and -direita["steer"] < 0


def test_sinal_da_velocidade_lateral_sai_da_velocidade_do_mundo():
    frame = pd.concat([_curva_sintetica(+1, 0.0, s_vy_gravado=-1), _curva_sintetica(-1, 10000.0, s_vy_gravado=-1)],
                      ignore_index=True)
    corners = [Curva(0.0, 6000.0, +1, "C01-esq"), Curva(10000.0, 16000.0, -1, "C02-dir")]
    result, conv = C.conferir(frame, corners, 20000.0)
    assert conv.s_vy == -1 and result["velocidade_lateral"]["bate"]
    model = C.no_modelo(frame, conv)
    # vy = -0,4 m/s na curva a esquerda (o carro aponta para dentro), +0,4 na direita.
    assert model["vy"].iloc[50] == pytest.approx(-0.4) and model["vy"].iloc[250] == pytest.approx(0.4)


def test_volante_com_sinal_trocado_nao_bate():
    frame, corners = _pista()
    frame["steer_angle"] = -frame["steer_angle"]
    result, _ = C.conferir(frame, corners, 20000.0)
    assert not result["volante"]["bate"] and not result["todas_batem"]
