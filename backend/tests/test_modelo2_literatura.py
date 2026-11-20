"""Pedido 42, 20/11: os rotulos pelos criterios da literatura, com tracos sinteticos (secao 7)."""

from __future__ import annotations

import sys

import numpy as np

from ml.modelo2 import rotulos_literatura as RL

N = 400                      # pontos da janela (2 m cada)
T = np.arange(N) * 0.05      # 0,05 s por ponto (144 km/h)
MARCOS = {"a": 150, "apice": 200, "m1": 180, "m2": 220, "e": 260, "e60": 290}


def janela(**canais):
    base = {n: None for n in ("brake", "throttle", "steer", "yaw_rate", "velocity_long", "velocity_lat", "lateral_g", "speed_kmh")}
    base.update(canais)
    return RL.Janela(canais=base, t=T.copy(), marcos=dict(MARCOS), direcao=1)


def freio_com_descida(descida):
    b = np.zeros(N)
    b[60:120] = 0.9
    b[120:120 + descida.size] = descida
    return b


def test_o_modulo_nao_importa_os_detectores():
    import ast
    for mod in (RL,):
        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        names += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any("detectores" in x or "calibra" in x or "rotulagem" in x for x in names), names
    from ml.modelo2 import literatura_execucao as X
    tree = ast.parse(open(X.__file__, encoding="utf-8").read())
    names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any("detectores" in x for x in names), names


def test_f4_rampa_degrau_penhasco_e_gagueira():
    x = np.linspace(0, 1, 40)
    rampa = RL.rotulo_f4(janela(brake=freio_com_descida(0.9 * (1 - x) ** 2)))
    assert rampa["rotulo"] == RL.APLICA
    degrau = RL.rotulo_f4(janela(brake=freio_com_descida(np.where(x < 0.8, 0.9, 0.0))))
    assert degrau["rotulo"] == RL.NAO_APLICA
    penhasco = RL.rotulo_f4(janela(brake=freio_com_descida(np.array([0.5, 0.1, 0.0]))))
    assert penhasco["rotulo"] == RL.NAO_APLICA and "penhasco" in penhasco["criterio"]
    gag = 0.9 * (1 - x)
    gag[20:24] += 0.1
    assert "gagueira" in RL.rotulo_f4(janela(brake=freio_com_descida(gag)))["criterio"]
    assert RL.rotulo_f4(janela(brake=np.full(N, 0.05)))["rotulo"] == RL.NAO_SEI


def test_f5_com_e_sem_trail_braking():
    steer = -np.clip((np.arange(N) - 140) / 40.0, 0, 1) * 0.3          # para dentro de uma curva a esquerda
    trail = np.zeros(N)
    trail[60:140] = 0.9
    trail[140:200] = np.linspace(0.6, 0.0, 60)
    assert RL.rotulo_f5(janela(brake=trail, steer=steer))["rotulo"] == RL.APLICA
    seco = np.zeros(N)
    seco[60:140] = 0.9
    assert RL.rotulo_f5(janela(brake=seco, steer=steer))["rotulo"] == RL.NAO_APLICA


def test_m6_retomada_continua_e_alivio():
    speed = 200 - 100 * np.exp(-((np.arange(N) - 200) / 30.0) ** 2)
    steer = -0.3 * np.ones(N)
    suave = np.where(np.arange(N) < 205, 0.0, np.clip((np.arange(N) - 205) / 40.0, 0, 1))
    assert RL.rotulo_m6(janela(throttle=suave, speed_kmh=speed, steer=steer))["rotulo"] == RL.APLICA
    alivio = suave.copy()
    alivio[220:230] = 0.1
    assert RL.rotulo_m6(janela(throttle=alivio, speed_kmh=speed, steer=steer))["rotulo"] == RL.NAO_APLICA


def test_e2_e_e3_com_a_referencia_do_carro():
    L, k = 2.96, 0.30
    ref = RL.ReferenciaDoCarro(L=L, k_delta=k, k_us=0.0, intercepto=0.0, mu=2.0)
    v = np.full(N, 100.0)
    ay = np.full(N, 1.0)
    neutro = -(L * ay * RL.G / (v / 3.6) ** 2) / k                         # o volante que a curva pede
    yaw = (v / 3.6) * (-k * neutro) / L
    base = dict(speed_kmh=v, lateral_g=ay, yaw_rate=yaw, velocity_long=v / 3.6, velocity_lat=np.zeros(N))
    assert RL.rotulo_e2(janela(steer=neutro, **base), ref)["rotulo"] == RL.NAO_APLICA
    mais = neutro - np.radians(2.0) / k                                     # 2 graus a mais de roda
    assert RL.rotulo_e2(janela(steer=mais, **base), ref)["rotulo"] == RL.APLICA
    assert RL.rotulo_e3(janela(steer=neutro, **base), ref)["rotulo"] == RL.NAO_APLICA
    deriva = dict(base, velocity_lat=np.where((np.arange(N) > 200) & (np.arange(N) < 230), 6.0, 0.0))
    r = RL.rotulo_e3(janela(steer=neutro, **deriva), ref)
    assert r["rotulo"] == RL.APLICA and "deriva" in r["criterio"]
    sem_guinada = dict(base, yaw_rate=None, velocity_long=None, velocity_lat=None)
    assert RL.rotulo_e2(janela(steer=neutro, **sem_guinada), ref)["rotulo"] == RL.NAO_SEI


def test_referencia_do_carro_acha_o_gradiente():
    L, k = 2.96, 0.30
    ay = np.linspace(-0.5, 0.5, 400)
    v = np.full(ay.size, 120.0)
    k_us = np.radians(0.8)                                                   # 0,8 grau por g
    delta = L * ay * RL.G / (v / 3.6) ** 2 + k_us * ay
    ref = RL.referencia_do_carro([{"steer": -delta / k, "lateral_g": ay, "speed_kmh": v}], L, k)
    assert abs(ref.k_us - k_us) < 1e-6 and abs(ref.intercepto) < 1e-6
