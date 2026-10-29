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


# ------------------------------------------------------------ fisica ---

from scipy.optimize import fsolve  # noqa: E402

from ml.modelo_carro import correcao as K  # noqa: E402
from ml.modelo_carro import fisica as F  # noqa: E402
from ml.modelo_carro import validacao as V  # noqa: E402


def _params(**extra) -> F.Parametros:
    values = dict(m=750.0, kappa_L=0.0, w_f=0.45, f_aero=0.45, h_L=0.1, b=1.53, L=3.4, k_delta=0.3,
                  brake_bias=0.55, env_speed=np.array([10.0, 90.0]), env_traction=np.array([10.0, 10.0]),
                  C_alpha=20.0, mu=100.0, k2=1.5, kappa_D=0.0, c0=0.0, s_T=1.0, beta_B=30.0, transferencia=False)
    values.update(extra)
    return F.Parametros(**values)


def test_curva_em_regime_permanente_da_o_que_a_conta_manda():
    # Uma rigidez so e w_f = b/L: o carro e neutro, entao r = vx*delta/L, e a deriva traseira
    # carrega a forca lateral do eixo: vy = b*r - vx*(vx*r)/(C_alpha*g).
    p = _params(w_f=1.53 / 3.4)
    vx, delta = 30.0, 0.01
    steer = -delta / p.k_delta                       # volante positivo a direita; delta positivo a esquerda

    def steady(z):
        state = np.array([[vx, z[0], z[1]]])
        return F.derivadas(state, np.array([[steer, 0.0, 0.0]]), p)[0, 1:]

    vy, r = fsolve(steady, [0.0, 0.05])
    assert r == pytest.approx(vx * delta / p.L, rel=0.01)
    assert vy == pytest.approx(p.b * r - vx * vx * r / (p.C_alpha * D.G), rel=0.02)
    assert r > 0                                      # volante a esquerda, giro a esquerda


def test_freada_em_linha_reta_da_o_que_a_conta_manda():
    state = np.array([[50.0, 0.0, 0.0]])
    brake = np.array([[0.0, 0.0, 1.0]])
    # Sem saturar: a desaceleracao e o pedido do freio mais o arrasto e o c0.
    p = _params(kappa_D=0.001, c0=0.5, beta_B=20.0, mu=2.0, kappa_L=0.003)
    d = F.derivadas(state, brake, p)[0]
    assert d[0] == pytest.approx(-(20.0 + 0.001 * 2500 + 0.5))
    assert d[1] == pytest.approx(0.0) and d[2] == pytest.approx(0.0)
    # Saturado: cada eixo no limite de atrito, 0,99*mu*carga.
    p = _params(beta_B=500.0, mu=1.5, kappa_L=0.003, f_aero=0.4)
    d = F.derivadas(state, brake, p)[0]
    assert d[0] == pytest.approx(-0.99 * 1.5 * (D.G + 0.003 * 2500))
    # Com a transferencia, a soma das cargas nao muda e o freio saturado da o mesmo total.
    d2 = F.derivadas(state, brake, replace_(p, transferencia=True))[0]
    assert d2[0] == pytest.approx(d[0], rel=1e-6)


def replace_(p, **kw):
    from dataclasses import replace
    return replace(p, **kw)


def test_persistencia_e_posicoes():
    states = np.tile(np.array([20.0, 0.0, 0.0]), (1, 11, 1))
    pos = F.posicoes(states)
    assert pos[0, -1, 0] == pytest.approx(20.0 * 0.5) and pos[0, -1, 1] == pytest.approx(0.0)
    turning = np.tile(np.array([20.0, 0.0, 0.4]), (1, 41, 1))
    # Em arco a esquerda, a posicao vai para y positivo.
    assert F.posicoes(turning)[0, -1, 1] > 0
    assert F.persistencia(np.array([[1.0, 2.0, 3.0]]), 4).shape == (1, 5, 3)


# --------------------------------------------------------- malha aberta ---

def _quadro(trechos=(("A", 25), ("B", 15))) -> pd.DataFrame:
    blocks = []
    for name, n in trechos:
        k = np.arange(n)
        blocks.append(pd.DataFrame({
            "session_id": "s", "lap_id": "s#0001", "trecho": name, "k": k, "t": k * D.DT,
            "x": 30.0 * k * D.DT, "z": 0.0, "heading": 0.0, "s": 30.0 * k * D.DT, "tyre_core_temp": 60.0,
            "vx": 30.0, "vy": 0.0, "r": 0.0, "steer": 0.0, "T": 1.0, "B": 0.0, "a_y": 0.0, "a_x": 0.0,
        }))
    return pd.concat(blocks, ignore_index=True)


def test_passo_e_caso_nao_atravessam_buraco():
    frame = _quadro()
    conv = C.Convencoes(s_r=1, s_psi=-1, s_vy=1, forma_heading="(-sen h, cos h)", s_esquerda=-1)
    assert len(V.passos(frame)) == (25 - 1) + (15 - 1)
    cs = V.casos(frame, conv)
    # O trecho B (15 passos) nao tem 1,0 s pela frente; no A, inicios em k = 0, 2 e 4.
    assert len(cs) == 3 and set(cs.trecho) == {"A"} and cs.k0.tolist() == [0, 2, 4]
    assert np.all(cs.k0 + V.H_MAX <= 24)


# ------------------------------------------------------------ metricas ---

def test_skill_contra_referencia_conhecida():
    true = np.zeros((40, 11, 3))
    sigma = np.array([10.0, 1.0, 0.5])
    ref = true + np.array([2.0, 0.2, 0.1])
    model = true + np.array([1.0, 0.1, 0.05])        # metade do erro em toda grandeza
    e_m, e_r = V.erro_combinado(model, true, sigma, 10), V.erro_combinado(ref, true, sigma, 10)
    assert e_r == pytest.approx(0.2) and V.skill(e_m, e_r) == pytest.approx(0.5)
    laps = np.repeat(np.arange(8), 5)
    ci = V.bootstrap_skill(V.erro_quadrado(model, true, sigma, 10), V.erro_quadrado(ref, true, sigma, 10), laps, n=200)
    assert ci["p2_5"] == pytest.approx(0.5) and ci["p97_5"] == pytest.approx(0.5)
    assert V.por_grandeza(model, true, 10)["vx"] == {"rmse": pytest.approx(1.0), "vies": pytest.approx(1.0)}


def test_regimes():
    g = D.G
    reg = K.regimes(B=np.array([0.5, 0.5, 0.0, 0.0, 0.0]), a_y=np.array([0.6, 0.1, -0.7, 0.0, 0.0]) * g,
                    T=np.array([0.0, 0.0, 1.0, 1.0, 1.0]), a_x=np.array([-1.0, -2.0, 0.2, 0.5, 0.1]) * g)
    assert reg.tolist() == ["freio e volante juntos", "freada", "curva", "tracao", "reta"]


def test_ponto_fora_dos_dados_de_treino_e_marcado():
    rng = np.random.default_rng(0)
    n = 150
    state = np.column_stack([rng.uniform(20, 70, n), rng.normal(0, 1, n), rng.normal(0, 0.3, n)])
    u = np.column_stack([rng.normal(0, 0.2, n), rng.uniform(0, 1, n), rng.uniform(0, 0.3, n)])
    resid = np.column_stack([0.01 * state[:, 1], 0.02 * u[:, 0], 0.01 * state[:, 2]]) + rng.normal(0, 0.002, (n, 3))
    corr = K.Correcao().ajustar(np.column_stack([state, u]), resid)
    _, _, inside = corr.prever(state, u)
    cut = np.percentile(inside, 99)
    far_state, far_u = np.array([[150.0, 8.0, 3.0]]), np.array([[1.5, 1.0, 1.0]])
    mean, std, far = corr.prever(far_state, far_u)
    assert far[0] > cut and far[0] > 5 * np.max(inside)
    assert std.shape == (1, 3) and np.all(std > 0)


# ----------------------------------------------- experimento e figuras ---

from ml.modelo_carro import experimento as X  # noqa: E402
from ml.modelo_carro import figuras as FG  # noqa: E402


def test_inicio_da_figura_pela_regra_e_dentro_do_trecho():
    frame = _quadro(trechos=(("A", 60),))
    frame["B"] = np.where(frame["k"] >= 30, 1.0, 0.0)          # freio a partir de s = 45 m
    frame["vx"] = 30.0 + np.where(frame["k"] == 45, -5.0, 0.0)  # o minimo da curva em k = 45
    curva = type("Curva", (), {"start_s": 60.0, "apex_s": 70.0, "end_s": 80.0})()
    assert FG.achar_inicio(frame, curva, 5000.0, "freada") == 30 - FG.ANTES_DA_FREADA
    assert FG.achar_inicio(frame, curva, 5000.0, "curva") == 45 - FG.ANTES_DO_MINIMO
    # Sem 1,0 s pela frente dentro do trecho, o caso nao cabe.
    curto = _quadro(trechos=(("A", 40),))
    curto["B"] = np.where(curto["k"] >= 30, 1.0, 0.0)
    assert FG.achar_inicio(curto, curva, 5000.0, "freada") is None


def test_veredito_com_numeros_conhecidos():
    n, rng = 600, np.random.default_rng(1)
    h = V.H_PRINCIPAL
    cases = {"sessao": np.repeat(np.array([f"s{i}" for i in range(5)], dtype=object), n // 5),
             "volta": np.repeat(np.arange(30), n // 30), "nao_conclusivo": np.zeros(n, dtype=bool),
             "regime": np.full(n, "reta", dtype=object), "faixa": np.full(n, "x", dtype=object),
             "dentro_90": rng.random((n, 3)) < 0.9}
    for name, hh in V.HORIZONTES.items():
        for model, scale in (("M1", 0.25), ("R1", 0.5), ("R0", 1.0)):
            err = scale * np.ones((n, 3)) * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)[:, None]
            cases[f"err_{model}_{hh}"] = err
            cases[f"sq_{model}_{hh}"] = np.sum(err ** 2, axis=1)
    out = X.veredito(cases)
    by = {c["n"]: c for c in out["criterios"]}
    assert by[1]["valor"] == pytest.approx(0.75) and by[1]["passa"]
    assert by[2]["valor"] == pytest.approx(0.5) and by[2]["passa"]
    assert by[3]["passa"] and by[4]["valor"] == 5 and by[5]["passa"] and by[7]["valor"] == 5
    assert 0.8 <= by[6]["valor"] <= 0.97 and out["aprovada"]
