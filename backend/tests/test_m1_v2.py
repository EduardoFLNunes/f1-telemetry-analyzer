"""M1 v2 e o medidor do Modelo 1 (pedido 46, Parte E; ADR 0028), com dados sinteticos."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from ml.modelo_carro import cargas_v2 as CG
from ml.modelo_carro import correcao as K
from ml.modelo_carro import correcao_v2 as K2
from ml.modelo_carro import fisica as F
from ml.modelo_carro import fisica_v2 as F2
from ml.modelo_carro.dados import G

ENV_V = np.array([10.0, 90.0])
ENV_A = np.array([10.0, 6.0])


def _v2(**extra) -> F2.ParametrosV2:
    values = dict(m=650.0, kappa_L=0.0033, w_f=0.43, f_aero=0.44, h_L=0.0915, b=0.43 * 2.964, L=2.964,
                  k_delta=0.304, brake_bias=0.55, lam=0.5, h_y=0.27, t_f=1.588, t_r=1.509,
                  env_speed=ENV_V, env_traction=ENV_A, C_alpha=20.0, mu_ref=1.8, q=0.8,
                  alpha_pico=np.radians(7.0), f=0.8, k2=1.5, kappa_D=0.001, c0=0.5, s_T=1.0, beta_B=30.0)
    values.update(extra)
    return F2.ParametrosV2(**values)


def _v1_igual(p2: F2.ParametrosV2) -> F.Parametros:
    return F.Parametros(m=p2.m, kappa_L=p2.kappa_L, w_f=p2.w_f, f_aero=p2.f_aero, h_L=p2.h_L, b=p2.b, L=p2.L,
                        k_delta=p2.k_delta, brake_bias=p2.brake_bias, env_speed=p2.env_speed,
                        env_traction=p2.env_traction, C_alpha=p2.C_alpha, mu=p2.mu_ref, k2=p2.k2,
                        kappa_D=p2.kappa_D, c0=p2.c0, s_T=p2.s_T, beta_B=p2.beta_B, transferencia=True)


# -------------------------------------------------------------- cargas ---

def test_transferencia_lateral_vai_para_as_rodas_de_fora():
    p = _v2()
    vx = np.array([40.0, 40.0])
    a_y = np.array([2.0 * G, -2.0 * G])          # curva a esquerda e curva a direita
    n = F2.cargas(vx, np.zeros(2), a_y, p)
    fl, fr, rl, rr = n.T
    # Curva a esquerda (a_y > 0): as rodas da direita estao por fora e ganham carga.
    assert fr[0] > fl[0] and rr[0] > rl[0]
    # Curva a direita: o contrario, na mesma quantidade.
    assert fl[1] > fr[1] and rl[1] > rr[1]
    assert fr[0] - fl[0] == pytest.approx(fl[1] - fr[1])
    assert fr[0] - fl[0] == pytest.approx(2 * p.lam * p.h_y * 2.0 * G / p.t_f)
    assert rr[0] - rl[0] == pytest.approx(2 * (1 - p.lam) * p.h_y * 2.0 * G / p.t_r)


def test_soma_das_quatro_cargas_e_o_peso_mais_o_downforce():
    p = _v2()
    rng = np.random.default_rng(1)
    vx = rng.uniform(10, 80, 50)
    a_x = rng.uniform(-4 * G, 1.5 * G, 50)
    a_y = rng.uniform(-3 * G, 3 * G, 50)
    n = F2.cargas(vx, a_x, a_y, p)
    np.testing.assert_allclose(n.sum(axis=1), G + p.kappa_L * vx ** 2)


def test_sem_bitola_nao_ha_transferencia_lateral():
    p = _v2(t_f=0.0, t_r=0.0)
    n = F2.cargas(np.array([50.0]), np.zeros(1), np.array([3.0 * G]), p)[0]
    assert n[0] == pytest.approx(n[1]) and n[2] == pytest.approx(n[3])


def test_mede_lam_e_h_y_das_cargas_gravadas():
    rng = np.random.default_rng(7)
    p = _v2(lam=0.42, h_y=0.31)
    n = 4000
    vx = rng.uniform(15, 75, n)
    a_y = rng.uniform(-3 * G, 3 * G, n)
    a_x = rng.uniform(-0.09 * G, 0.09 * G, n)
    loads = F2.cargas(vx, a_x, a_y, p) * p.m + rng.normal(0, 20.0, (n, 4))
    frame = pd.DataFrame({"vx": vx, "a_x": a_x, "a_y": a_y, "lap_id": np.repeat(np.arange(20), n // 20),
                          **{f"wheel_load_{w}": loads[:, i] for i, w in enumerate(("fl", "fr", "rl", "rr"))}})
    out = CG.medir_lateral(frame, p.m, p.t_f, p.t_r, bootstrap=20)
    assert out["lam"] == pytest.approx(0.42, abs=0.01)
    assert out["h_y"] == pytest.approx(0.31, abs=0.01)
    assert out["lam_na_faixa"] and out["h_y_na_faixa"] and not out["intervalo_passa_de_zero"]


# ---------------------------------------------------------------- pneu ---

def _curva(p, n, alpha):
    D = F2.mu_de(np.full_like(alpha, n), p) * n
    return F2.forca_lateral(alpha, np.full_like(alpha, n), D, p)


def test_pneu_tem_o_pico_no_alpha_pico_e_cai_ate_f():
    p = _v2(alpha_pico=np.radians(8.0), f=0.8, q=1.0)
    n = 5.0
    alpha = np.radians(np.linspace(0.01, 60.0, 60000))
    fy = _curva(p, n, alpha)
    D = p.mu_ref * n
    assert alpha[np.argmax(fy)] == pytest.approx(np.radians(8.0), abs=np.radians(0.05))
    assert fy.max() == pytest.approx(D, rel=1e-4)
    # Depois do pico ela cai e tende a f*D.
    big = F2.forca_lateral(np.array([50.0]), np.array([n]), np.array([D]), p)[0]
    assert big == pytest.approx(0.8 * D, rel=0.01)
    assert fy[-1] < fy.max()
    # A rigidez na origem e a da v1: C_alpha*n.
    small = np.radians(0.001)
    assert _curva(p, n, np.array([small]))[0] / small == pytest.approx(p.C_alpha * n, rel=1e-3)
    # E impar.
    assert _curva(p, n, np.array([-0.05]))[0] == pytest.approx(-_curva(p, n, np.array([0.05]))[0])


def test_forca_maxima_cresce_menos_que_a_carga_com_q_menor_que_1():
    p = _v2(q=0.75)
    n1, n2 = 3.0, 6.0
    alpha = np.radians(np.linspace(0.01, 30.0, 20000))
    f1, f2 = _curva(p, n1, alpha).max(), _curva(p, n2, alpha).max()
    assert f2 / f1 == pytest.approx(2.0 ** 0.75, rel=1e-3)
    assert f2 / f1 < 2.0
    # Com q = 1 e proporcional a carga.
    p1 = _v2(q=1.0)
    assert _curva(p1, n2, alpha).max() / _curva(p1, n1, alpha).max() == pytest.approx(2.0, rel=1e-3)
    # Na carga de referencia o atrito e mu_ref.
    assert F2.mu_de(np.array([F2.N_REF]), p)[0] == pytest.approx(p.mu_ref)


# --------------------------------------------------- quatro rodas e v1 ---

def test_quatro_rodas_sem_bitola_e_com_o_pneu_da_v1_e_a_bicicleta_da_v1():
    p2 = _v2(t_f=0.0, t_r=0.0, pneu="v1", q=1.0)
    p1 = _v1_igual(p2)
    rng = np.random.default_rng(3)
    n = 300
    state = np.column_stack([rng.uniform(8, 80, n), rng.uniform(-3, 3, n), rng.uniform(-1, 1, n)])
    u = np.column_stack([rng.uniform(-0.9, 0.9, n), rng.uniform(0, 1, n), rng.uniform(0, 1, n) * (rng.random(n) < 0.4)])
    np.testing.assert_allclose(F2.derivadas(state, u, p2), F.derivadas(state, u, p1), rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(F2.passo(state, u, p2), F.passo(state, u, p1), rtol=1e-9, atol=1e-9)


def test_momento_de_guinada_inclui_os_lados():
    # Freio so numa roda nao existe no modelo, mas a tracao com transferencia lateral sim:
    # com a bitola, o carro em curva gira diferente de sem a bitola.
    state = np.array([[40.0, 0.0, 0.5]])
    u = np.array([[-0.3, 1.0, 0.0]])
    com = F2.derivadas(state, u, _v2())[0, 2]
    sem = F2.derivadas(state, u, _v2(t_f=0.0, t_r=0.0))[0, 2]
    assert com != pytest.approx(sem, rel=1e-3)


def test_curva_a_esquerda_gira_a_esquerda_e_simetrica():
    p = _v2()
    state = np.array([[40.0, 0.0, 0.0], [40.0, 0.0, 0.0]])
    u = np.array([[-0.2, 0.3, 0.0], [0.2, 0.3, 0.0]])      # volante positivo a direita
    d = F2.derivadas(state, u, p)
    assert d[0, 2] > 0 and d[1, 2] < 0
    assert d[0, 2] == pytest.approx(-d[1, 2]) and d[0, 1] == pytest.approx(-d[1, 1])


# ------------------------------------------------------------ correcao ---

def test_amostra_da_correcao_segue_a_proporcao_dos_regimes():
    regime = np.array(["curva"] * 6500 + ["reta"] * 2000 + ["freada"] * 900 + ["tracao"] * 400
                      + ["freio e volante juntos"] * 200, dtype=object)
    idx, quota = K2.subconjunto(regime, 1000)
    assert idx.size == 1000 and np.unique(idx).size == 1000
    assert quota == {"freio e volante juntos": 20, "freada": 90, "curva": 650, "tracao": 40, "reta": 200}
    picked = pd.Series(regime[idx]).value_counts().to_dict()
    assert picked == {k: v for k, v in quota.items() if v}
    # Mesma semente, mesma amostra.
    idx2, _ = K2.subconjunto(regime, 1000)
    np.testing.assert_array_equal(idx, idx2)


def test_cotas_somam_o_total_pelos_maiores_restos():
    regime = np.array(["curva"] * 1 + ["reta"] * 1 + ["freada"] * 1, dtype=object)
    q = K2.cotas(regime, 2)
    assert sum(q.values()) == 2


def test_nao_conclusivo_pela_vizinhanca():
    rng = np.random.default_rng(5)
    X = rng.normal(size=(3000, 6))
    laps = np.repeat(np.arange(30), 100)
    viz = K2.Vizinhanca(X, laps)
    near = viz.indice(rng.normal(size=(50, 6)) * 0.5)
    far = viz.indice(rng.normal(size=(50, 6)) * 0.5 + 8.0)
    assert far.min() > near.max()
    # Sem a propria volta, o indice de um ponto de treino nao e zero.
    own = viz.indice_sem_a_volta(X[:100], laps[:100])
    assert own.min() > 0.0
    assert np.all(viz.indice(X[:100]) <= own + 1e-12)


# --------------------------------------------------- envelope (D.1) ---

def test_envelope_da_m1_v2_cresce_com_o_downforce_e_respeita_a_aderencia():
    p = _v2()
    speeds = np.linspace(15.0, 85.0, 12)
    env = F2.envelope(p, speeds, top_speed_mps=85.0)
    assert np.all(np.diff(env.lateral) > 0)          # o downforce domina
    assert np.all(np.diff(env.braking) > 0)
    for v, a_lat in zip(speeds, env.lateral):
        n = F2.cargas(np.array([v]), np.zeros(1), np.array([a_lat]), p)[0]
        grip = (F2.mu_de(n, p) * n).sum()
        assert a_lat <= grip * (1 + 1e-9)            # nunca mais que a aderencia somada das 4 rodas
    # A elipse do simulador: com o lateral todo usado, nao sobra longitudinal.
    assert env.longitudinal_available(np.array([50.0]), env.lateral_limit(50.0), braking=True)[0] == pytest.approx(0.0, abs=1e-9)
    half = env.longitudinal_available(np.array([50.0]), 0.5 * env.lateral_limit(50.0), braking=True)[0]
    assert half == pytest.approx(env.braking_limit(50.0)[0] * np.sqrt(0.75))


# ------------------------------------------------------------ medidor ---

def test_medidor_da_o_mesmo_tempo_para_a_mesma_linha_nas_duas_chamadas():
    from tests.test_ml_pipeline import circular_track, flat_envelope
    from ml.optimization.lap_time_model import simulate

    track = circular_track()
    lateral = 0.5 * np.sin(np.linspace(0, 6 * np.pi, track.s.size, endpoint=False))
    env = flat_envelope()
    first = simulate(track, lateral, env)
    second = simulate(track, lateral.copy(), env)
    assert first.lap_time_s == second.lap_time_s
    np.testing.assert_array_equal(first.step_time_s, second.step_time_s)


def test_envelope_da_m1_v2_no_simulador_e_repetivel():
    from tests.test_ml_pipeline import circular_track
    from ml.optimization.lap_time_model import simulate

    track = circular_track()
    env = F2.envelope(_v2(), np.linspace(15.0, 85.0, 12), top_speed_mps=85.0)
    lateral = np.zeros(track.s.size)
    assert simulate(track, lateral, env).lap_time_s == simulate(track, lateral, env).lap_time_s
