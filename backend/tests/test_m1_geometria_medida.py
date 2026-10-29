"""A geometria do carro medida pela memoria do jogo (pedido 39; ADR 0024)."""

from __future__ import annotations

import ctypes
import json

import numpy as np
import pandas as pd
import pytest

from core.assetto_adapter import SPageFileGraphics, SPageFilePhysics, SPageFileStatic
from ml.modelo_carro import geometria_medida as GM
from ml.scripts import medir_geometria as MG


def _escrever_4x3(physics, field: str, values) -> None:
    """Escreve 12 numeros no campo, na ordem da memoria (roda por coordenada)."""
    offset = getattr(SPageFilePhysics, field).offset
    raw = (ctypes.c_float * 12)(*values)
    ctypes.memmove(ctypes.addressof(physics) + offset, raw, ctypes.sizeof(raw))


# ------------------------------------------------------- a ordem 4 x 3 ---

def test_campo_4x3_lido_na_ordem_da_memoria():
    physics = SPageFilePhysics()
    # Roda w, coordenada c -> 100*w + c: so a leitura achatada devolve isso no indice 3w + c.
    values = [100.0 * w + c for w in range(4) for c in range(3)]
    _escrever_4x3(physics, "tyreContactPoint", values)
    row = MG.amostra(physics, SPageFileGraphics(), 0.0)
    for w in range(4):
        for c in range(3):
            assert row[f"cp_{3 * w + c}"] == pytest.approx(100.0 * w + c)
    np.testing.assert_allclose(GM.achatar_4x3(physics.tyreContactPoint),
                               np.array(values).reshape(4, 3))
    # O vetor aninhado do ctypes tem 3 linhas de 4 -- e por isso nao pode ser lido como [roda][coord].
    assert len(physics.tyreContactPoint) == 3 and len(physics.tyreContactPoint[0]) == 4


# --------------------------------------------- o laco, o cronometro, o arquivo ---

class _Adapter:
    """Uma memoria simulada: o cronometro anda 16 ms por leitura, o packetId as vezes repete."""

    def __init__(self):
        self.physics, self.graphics, self.static = SPageFilePhysics(), SPageFileGraphics(), SPageFileStatic()
        self.static.carModel, self.static.track, self.static.acVersion = MG.CARRO_ESPERADO, MG.PISTA_ESPERADA, "1.16.4"
        self.n = 0

    def poll(self):
        self.n += 1
        self.physics.packetId = self.n // 2 * 2          # repete a cada duas leituras
        self.graphics.iCurrentTime = 1000 + 16 * self.n
        self.physics.steerAngle = 0.01 * self.n
        return {"type": "ac_frame"}


class _Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, dt):
        self.t += dt


def test_laco_grava_o_cronometro_sem_descartar_e_salva(tmp_path):
    clock = _Relogio()
    path = tmp_path / "geometria_teste.parquet"
    medidor = MG.Medidor(_Adapter(), path, hz=60.0, clock=clock, sleep=clock.sleep, log=lambda *_: None)
    out = medidor.rodar(max_amostras=12)
    frame = pd.read_parquet(out)
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(frame) == 12 and meta["amostras"] == 12
    assert frame["i_current_time_ms"].tolist() == [1000 + 16 * k for k in range(1, 13)]
    # Nada e descartado na gravacao: o packetId repetido continua la.
    assert frame["packet_id"].duplicated().sum() == 5
    np.testing.assert_allclose(np.diff(frame["t_wall"]), 1.0 / 60.0)
    assert {"cp_11", "ch_11", "lv_x", "lav_y", "cg_height", "car_z", "wheel_load_rr"} <= set(frame.columns)
    assert meta["carModel"] == MG.CARRO_ESPERADO and meta["track"] == MG.PISTA_ESPERADA


# ------------------------------------------------- as contas da geometria ---

def _sessao_sintetica(L=3.0, tf=1.58, tr=1.52, x_v=0.4, k=0.27, toe=0.004, v=30.0, invertido=True):
    """Um carro rigido com geometria conhecida, na convencao do jogo (frente (-sen h, cos h), h = -psi)."""
    hz = 60.0
    n_box, n_run = 1200, 3600
    rows = []
    pos = np.zeros(2)
    psi = 0.3
    for i in range(n_box + n_run):
        moving = i >= n_box
        t = (i - n_box) / hz if moving else 0.0
        steer = 0.9 * np.sin(2 * np.pi * i / 600.0) if not moving else 0.05 * np.sin(0.5 * t)
        r = 0.3 * np.sin(0.5 * t) if moving else 0.0
        h = -psi
        fwd = np.array([-np.sin(h), np.cos(h)])
        left = np.array([np.cos(h), np.sin(h)])
        rear_l, rear_r = pos + 0.5 * tr * left, pos - 0.5 * tr * left
        front = pos + L * fwd
        front_l, front_r = front + 0.5 * tf * left, front - 0.5 * tf * left

        def turned(theta):
            d = np.cos(theta) * fwd + np.sin(theta) * left
            return -d if invertido else d

        delta = -k * steer
        dirs = [turned(delta + toe), turned(delta - toe), turned(toe / 2), turned(-toe / 2)]
        row = {"packet_id": i, "i_current_time_ms": int(round(1000 * (t if moving else i / hz))),
               "steer": steer, "heading": h, "lv_x": x_v * r, "lv_z": v if moving else 0.0, "lav_y": r,
               "acc_x": (v * r if moving else 0.0) / 9.80665, "cg_height": 0.26, "speed_kmh": 3.6 * v if moving else 0.0}
        for w, p in enumerate([front_l, front_r, rear_l, rear_r]):
            row[f"cp_{3 * w}"], row[f"cp_{3 * w + 1}"], row[f"cp_{3 * w + 2}"] = p[0], 0.0, p[1]
        for w, d in enumerate(dirs):
            row[f"ch_{3 * w}"], row[f"ch_{3 * w + 1}"], row[f"ch_{3 * w + 2}"] = d[0], 0.0, d[1]
        rows.append(row)
        if moving:
            # O eixo traseiro anda na direcao do carro (no meio do passo, para nao atrasar meio passo).
            h_mid = -(psi + 0.5 * r / hz)
            pos = pos + v * np.array([-np.sin(h_mid), np.cos(h_mid)]) / hz
            psi = psi + r / hz
    return pd.DataFrame(rows)


def test_entre_eixos_bitolas_e_ponto_do_carro():
    raw = _sessao_sintetica().iloc[[4000]]
    contact, dirs = GM.campos_4x3(raw, "cp"), GM.campos_4x3(raw, "ch")
    car = np.column_stack([raw["cp_6"] + 0.0, [0.3], raw["cp_8"]])   # o ponto do carro no contato traseiro esquerdo
    inst = GM.instantaneas(contact, dirs, raw["heading"].to_numpy(), car)
    assert inst["L"][0] == pytest.approx(3.0)
    assert inst["bitola_dianteira"][0] == pytest.approx(1.58) and inst["bitola_traseira"][0] == pytest.approx(1.52)
    assert inst["sentido"][0] == -1                       # as direcoes apontam para tras, como no retrato
    assert inst["x_carro"][0] == pytest.approx(0.0, abs=1e-9) and inst["y_carro"][0] == pytest.approx(0.76)


def test_k_delta_e_convergencia_pelo_angulo_das_rodas():
    K = GM.medir_k_delta(_sessao_sintetica())
    assert K["sentido_invertido"]
    assert K["media"]["k_delta"] == pytest.approx(0.27, rel=1e-3) and K["media"]["r2"] > 0.999
    # Cada lado tem a mesma inclinacao; a convergencia (toe) aparece no intercepto, com sinais opostos.
    assert K["esquerda"]["k_delta"] == pytest.approx(0.27, rel=1e-3)
    assert K["esquerda"]["convergencia_rad"] == pytest.approx(0.004, abs=1e-4)
    assert K["direita"]["convergencia_rad"] == pytest.approx(-0.004, abs=1e-4)
    assert all(row["k_delta_local"] == pytest.approx(0.27, rel=0.01) for row in K["linearidade"])


def test_entre_eixos_e_ponto_da_velocidade_na_parte_com_relogio():
    raw = _sessao_sintetica(x_v=0.4)
    out = GM.medir_relogio(raw)
    assert out["L"] == pytest.approx(3.0, abs=1e-6) and out["L_largura_relativa"] < 1e-6
    assert out["cg_height"] == pytest.approx(0.26)
    assert out["x_v"] == pytest.approx(0.4, abs=0.05)
    assert out["x_v_pelo_eixo_dianteiro"] == pytest.approx(0.4, abs=0.05)
    assert out["sinal_acc_x"] == 1
    gates = GM.portoes(out, GM.medir_k_delta(raw))
    assert gates["L"]["passa"] and gates["k_delta"]["passa"] and gates["x_v"]["passa"]
    assert gates["h_L"]["valor"] == pytest.approx(0.26 / 3.0)


def test_portao_que_falha_usa_o_caminho_registrado():
    L = {"L": 1.0, "L_largura_relativa": 0.01, "x_v": 0.5, "x_v_meia_largura": 0.5, "cg_height": 0.26,
         "reserva_k_delta": {"L_sobre_k": 11.0}}
    K = {"media": {"k_delta": 0.27, "r2": 0.5}}
    gates = GM.portoes(L, K)
    assert not gates["L"]["passa"] and gates["L"]["usado"] == pytest.approx(2.943)
    assert not gates["k_delta"]["passa"] and gates["k_delta"]["usado"] == pytest.approx(2.943 / 11.0)
    assert not gates["x_v"]["passa"] and gates["x_v"]["usado"] is None
    np.testing.assert_allclose(GM.vy_no_centro(np.array([1.0]), np.array([0.5]), 1.3, None), [1.0])
    np.testing.assert_allclose(GM.vy_no_centro(np.array([1.0]), np.array([0.5]), 1.3, 0.3), [1.5])
