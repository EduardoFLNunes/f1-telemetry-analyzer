"""Pedido 38: o Modelo 2 (fases, detectores, atribuicao do erro), com dados sinteticos."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from ml.modelo2 import detectores as det
from ml.modelo2.dados import Volta, raw_derived, to_grid
from ml.modelo2.detectores import APLICA, NAO_APLICA, NC, Lap, corner_refs, measure_passage, phase_time, state_of
from ml.modelo2.fases import build_phases, check_partition
from ml.modelo2.perda import session_ranking
from ml.track.corners import detect_corners

try:
    from ml.track.geometry import load_geometry
    TRACK = load_geometry()
except FileNotFoundError:  # pragma: no cover - maquina sem o cache da pista
    TRACK = None

pytestmark = pytest.mark.skipif(TRACK is None, reason="sem a geometria da pista")


@pytest.fixture(scope="module")
def corners():
    return detect_corners(TRACK)


@pytest.fixture(scope="module")
def phases(corners):
    onsets_ai = [[float(np.mod(c.start_s - 60.0, TRACK.length))] * 3 for c in corners]
    onsets_me = [[float(np.mod(c.start_s - 80.0, TRACK.length))] * 3 for c in corners]
    return build_phases(TRACK, corners, [100.0] * len(corners), onsets_ai, onsets_me)


def synthetic_lap(lap_id="s#0001", origem="humano", speed_kmh=None, channels=None, hz=60.0,
                  with_yaw=True, sessao="2026-10-30"):
    """Uma volta sintetica: canais como funcao de s, gravados a 60 Hz, levados a grade como no dados.py."""
    L = TRACK.length
    v = (lambda s: np.full_like(s, 150.0)) if speed_kmh is None else speed_kmh
    s_fine = np.linspace(0.0, L, 20000)
    t_fine = np.concatenate([[0.0], np.cumsum(np.diff(s_fine) / (v(s_fine[1:]) / 3.6))])
    total = float(t_fine[-1])
    t = np.arange(0.0, total, 1.0 / hz)
    s = np.interp(t, t_fine, s_fine)
    channels = dict(channels or {})
    raw = {"s_unwrapped": s, "lap_time_s": t, "speed_kmh": v(s)}
    for name in ("brake", "throttle", "steer_angle", "lateral_g", "longitudinal_g", "yaw_rate",
                 "velocity_long", "velocity_lat", "gear", "rpm", "lateral",
                 "wheel_slip_fl", "wheel_slip_fr", "wheel_slip_rl", "wheel_slip_rr",
                 "wheel_load_fl", "wheel_load_fr", "wheel_load_rl", "wheel_load_rr",
                 "tyre_core_temp_fl", "tyre_core_temp_fr", "tyre_core_temp_rl", "tyre_core_temp_rr"):
        default = {"throttle": 1.0, "gear": 4.0, "rpm": 7000.0, "velocity_long": None, "wheel_load_fl": 2000.0,
                   "wheel_load_fr": 2000.0, "wheel_load_rl": 3000.0, "wheel_load_rr": 3000.0}.get(name, 0.0)
        f = channels.get(name)
        if name == "velocity_long" and f is None:
            raw[name] = v(s) / 3.6
        elif f is not None:
            raw[name] = f(s)
        else:
            raw[name] = np.full(s.size, default)
        if not with_yaw and name in ("yaw_rate", "velocity_long", "velocity_lat"):
            raw[name] = np.full(s.size, np.nan)
    frame = pd.DataFrame(raw)
    derived = to_grid(raw_derived(frame), TRACK)
    grid = pd.DataFrame({"grid_index": np.arange(TRACK.size)})
    for name, values in raw.items():
        if name in ("s_unwrapped", "lap_time_s"):
            continue
        grid[name] = np.interp(TRACK.s, s, values) if np.isfinite(values).any() else np.nan
    grid["elapsed_s"] = np.interp(TRACK.s, s_fine, t_fine)
    grid = pd.concat([grid, derived.drop(columns="grid_index")], axis=1)
    volta = Volta(lap_id=lap_id, gravacao=lap_id.split("#")[0], origem=origem, tempo_s=total, grid=grid, sessao=sessao)
    return Lap.build(volta)


def corner_of(phases, label="C04"):
    return next(cp for cp in phases if cp.curva.startswith(label))


def bump(centre, half, value):
    return lambda s: np.where(np.abs(s - centre) <= half, value, 0.0)


# ---------------------------------------------------------------- fases ---

def test_fases_cobrem_a_volta_e_sao_as_mesmas_em_todas_as_voltas(phases):
    assert check_partition(TRACK, phases) == pytest.approx(TRACK.length, abs=1e-6)
    fast = synthetic_lap("a#0001")
    slow = synthetic_lap("b#0001", speed_kmh=lambda s: 120.0 + 60.0 * (np.sin(s / 200.0) > 0))
    for lap in (fast, slow):
        total = sum(phase_time(lap, TRACK, *bounds) for cp in phases for bounds in cp.bounds().values())
        assert total == pytest.approx(lap.total, abs=1e-9)
    again = build_phases(TRACK, detect_corners(TRACK), [100.0] * 14,
                         [[float(np.mod(c.start_s - 60.0, TRACK.length))] * 3 for c in detect_corners(TRACK)],
                         [[float(np.mod(c.start_s - 80.0, TRACK.length))] * 3 for c in detect_corners(TRACK)])
    assert [cp.bounds() for cp in again] == [cp.bounds() for cp in phases]
    for cp in phases:
        assert cp.b <= cp.a or cp.b > cp.e      # b_k vem antes do comeco da curva (ou da volta)


def test_curva_sem_frenagem_tem_a_fase_vazia(corners):
    none = [[None, None, None] for _ in corners]
    phases = build_phases(TRACK, corners, [200.0] * 14, none, none)
    assert all(cp.sem_frenagem and cp.b == cp.a for cp in phases)
    assert all(cp.tipo == "rapida" for cp in phases)


# -------------------------------------------------- medicao (sintetica) ---

def _measure(lap, phases, label="C04"):
    cp = corner_of(phases, label)
    env = lambda v: np.full_like(np.asarray(v, dtype=float), 3.0)
    return measure_passage(lap, TRACK, cp, phases[cp.k - 1], env), cp


def _braking_lap(phases, release, trail, label="C04", lap_id="x#0001", **kw):
    cp = corner_of(phases, label)
    a = cp.a
    steer_in = -cp.direcao * 0.3      # volante positivo a direita; para dentro da curva

    def brake(s):
        out = np.zeros_like(s)
        on = (s >= a - 120.0) & (s < a - 20.0)
        out[on] = 0.9
        tail = (s >= a - 20.0) & (s < a + 20.0)
        if release == "rampa":
            out[tail] = 0.9 * (1.0 - (s[tail] - (a - 20.0)) / 40.0)
        else:
            out[(s >= a - 20.0) & (s < a + 5.0)] = 0.9
        return out if trail else np.where(s >= a, 0.0, out)

    def steer(s):
        ramp = np.clip((s - (a - 5.0)) / 30.0, 0.0, 1.0)
        down = np.clip((cp.e - s) / 30.0, 0.0, 1.0)
        return steer_in * np.minimum(ramp, down)

    def throttle(s):
        return np.where((s >= a - 125.0) & (s < cp.apice + 10.0), 0.0, 1.0)

    channels = {"brake": brake, "steer_angle": steer, "throttle": throttle, **kw}
    return synthetic_lap(lap_id, channels=channels)


def test_soltura_em_rampa_e_em_degrau(phases):
    ramp, _ = _measure(_braking_lap(phases, "rampa", True), phases)
    step, _ = _measure(_braking_lap(phases, "degrau", True), phases)
    assert ramp["freia"] and step["freia"]
    assert ramp["taxa_soltura"] < 3.0 - 0.75
    assert step["taxa_soltura"] > 3.0 + 0.75
    ref = corner_refs([])
    assert state_of("F4", ramp, ref)[0] == APLICA
    assert state_of("F4", step, ref)[0] == NAO_APLICA


def test_trail_braking_com_e_sem(phases):
    yes, _ = _measure(_braking_lap(phases, "rampa", True), phases)
    no, _ = _measure(_braking_lap(phases, "rampa", False), phases)
    ref = corner_refs([])
    assert state_of("F5", yes, ref)[0] == APLICA
    assert state_of("F5", no, ref)[0] == NAO_APLICA


def test_sem_guinada_da_nao_conclusivo_nos_detectores_de_equilibrio(phases):
    lap = synthetic_lap("y#0001", with_yaw=False,
                        channels={"lateral_g": lambda s: np.full_like(s, 1.0),
                                  "steer_angle": lambda s: np.full_like(s, -0.2)})
    row, _ = _measure(lap, phases)
    ref = corner_refs([row])
    for d in ("E2", "E3", "E4"):
        assert state_of(d, row, ref)[0] == NC


def test_fase_sem_pedal_e_alivio(phases):
    cp = corner_of(phases)
    coast = synthetic_lap("c#0001", channels={"throttle": lambda s: np.where((s > cp.a) & (s < cp.a + 40.0), 0.0, 1.0)})
    row, _ = _measure(coast, phases)
    assert row["sem_pedal_s"] > 0.5
    assert state_of("M5", row, corner_refs([]))[0] == APLICA
    smooth = synthetic_lap("d#0001", channels={"throttle": lambda s: np.where(s < cp.apice, 0.0, 1.0),
                                                "brake": bump(cp.a - 40.0, 40.0, 0.8)})
    lift = synthetic_lap("e#0001", channels={
        # sobe a 0,6, cai a 0,3 e so depois vai ao pleno: "sobe, cai e sobe"
        "throttle": lambda s: np.where(s < cp.apice, 0.0, np.where(s < cp.apice + 20, 0.6,
                                                                   np.where(s < cp.apice + 30, 0.3, 1.0))),
        "brake": bump(cp.a - 40.0, 40.0, 0.8)})
    r_smooth, _ = _measure(smooth, phases)
    r_lift, _ = _measure(lift, phases)
    assert r_smooth["alivio"] == pytest.approx(0.0, abs=1e-6)
    assert state_of("M8", r_smooth, corner_refs([]))[0] == NAO_APLICA
    assert state_of("M8", r_lift, corner_refs([]))[0] == APLICA


def test_contraesterco(phases):
    cp = corner_of(phases)
    sign = cp.direcao
    counter = synthetic_lap("f#0001", channels={
        "yaw_rate": lambda s: np.full_like(s, 0.3 * sign),
        # volante "normal": -volante com o sinal da guinada; aqui ele tem o sinal oposto num trecho
        "steer_angle": lambda s: np.where((s > cp.apice + 5.0) & (s < cp.apice + 20.0), 0.1 * sign, -0.3 * sign),
        "lateral_g": lambda s: np.full_like(s, 1.0 * sign)})
    normal = synthetic_lap("g#0001", channels={
        "yaw_rate": lambda s: np.full_like(s, 0.3 * sign),
        "steer_angle": lambda s: np.full_like(s, -0.3 * sign),
        "lateral_g": lambda s: np.full_like(s, 1.0 * sign)})
    r_counter, _ = _measure(counter, phases)
    r_normal, _ = _measure(normal, phases)
    assert state_of("E4", r_counter, corner_refs([]))[0] == APLICA
    assert state_of("E4", r_normal, corner_refs([]))[0] == NAO_APLICA


def test_escorregamento_quebrado_sai_da_conta(phases):
    lap = synthetic_lap("h#0001", channels={"wheel_slip_rl": lambda s: np.full_like(s, 290.0),
                                            "wheel_slip_rr": lambda s: np.full_like(s, 290.0)})
    assert np.isnan(lap.a("slip_rear")).all()


# ----------------------------------------- estados de cada detector ---

AI_ROWS = [{"s_b_rel": -100.0 + d, "freia": True, "pico_freio": 1.0, "t_pico": 0.10, "pico_fracao": 0.2, "queda_meio": 0.2,
            "taxa_soltura": 1.5, "sobreposicao_s": 0.5, "retencao": 0.3, "escorr_dianteiro": 0.5, "pedais_juntos_s": 0.0,
            "escorr_reducao": 0.5, "s_ti_rel": 0.0 + d, "ua_graus": 1.0, "beta_p95": 2.0, "contra_s": 0.0,
            "reversoes": 2.0, "irregularidade": 0.02, "uso_aderencia": 0.95, "s_vmin_rel": 50.0 + d, "plato_s": 0.4,
            "afastamento_m": 5.0, "sem_pedal_s": 0.0, "retomada_s": 0.3, "volante_depois": 0.0, "alivio": 0.0,
            "escorr_traseiro": 0.5, "taxa_carga": 0.5, "retoma": True} for d in (-1.0, 0.0, 1.0)]
REF = corner_refs(AI_ROWS)
REF["_freia"] = det.Ref.of([1.0, 1.0, 1.0])

# detector -> (valores que aplicam, valores que nao aplicam, chave que some no "sem canal")
CASES = {
    "F1": ({"s_b_rel": -102.0}, {"s_b_rel": -140.0}, "s_b_rel"),
    "F2": ({"t_pico": 0.2, "pico_freio": 0.98}, {"t_pico": 1.2, "pico_freio": 0.98}, "t_pico"),
    "F3": ({"pico_fracao": 0.2, "queda_meio": 0.2}, {"pico_fracao": 0.7, "queda_meio": 0.2}, "pico_fracao"),
    "F4": ({"taxa_soltura": 1.0}, {"taxa_soltura": 6.0}, "taxa_soltura"),
    "F5": ({"sobreposicao_s": 0.5, "retencao": 0.3}, {"sobreposicao_s": 0.0, "retencao": 0.0}, "sobreposicao_s"),
    "F6": ({"escorr_dianteiro": 2.0}, {"escorr_dianteiro": 0.4}, "escorr_dianteiro"),
    "F7": ({"pedais_juntos_s": 0.5}, {"pedais_juntos_s": 0.0}, "pedais_juntos_s"),
    "F8": ({"escorr_reducao": 2.0}, {"escorr_reducao": 0.4}, "escorr_reducao"),
    "E1": ({"s_ti_rel": -40.0}, {"s_ti_rel": 0.0}, "s_ti_rel"),
    "E2": ({"ua_graus": 2.0}, {"ua_graus": 1.0}, "ua_graus"),
    "E3": ({"beta_p95": 4.0}, {"beta_p95": 2.0}, "beta_p95"),
    "E4": ({"contra_s": 0.3}, {"contra_s": 0.0}, "contra_s"),
    "E5": ({"reversoes": 6.0}, {"reversoes": 2.0}, "reversoes"),
    "E6": ({"irregularidade": 0.01}, {"irregularidade": 0.08}, "irregularidade"),
    "M1": ({"uso_aderencia": 0.97}, {"uso_aderencia": 0.6}, "uso_aderencia"),
    "M2": ({"s_vmin_rel": 20.0}, {"s_vmin_rel": 50.0}, "s_vmin_rel"),
    "M3": ({"plato_s": 0.9}, {"plato_s": 0.1}, "plato_s"),
    "M4": ({"afastamento_m": 5.0}, {"afastamento_m": 2.0}, "afastamento_m"),
    "M5": ({"sem_pedal_s": 0.6}, {"sem_pedal_s": 0.0}, "sem_pedal_s"),
    "M7": ({"volante_depois": 0.3}, {"volante_depois": 0.0}, "volante_depois"),
    "M8": ({"alivio": 0.4}, {"alivio": 0.0}, "alivio"),
    "M9": ({"escorr_traseiro": 2.0}, {"escorr_traseiro": 0.4}, "escorr_traseiro"),
    "V3": ({"taxa_carga": 2.0}, {"taxa_carga": 0.4}, "taxa_carga"),
}


def _row(values, freia=True):
    return {"freia": freia, "retoma": True, "_ausente": {}, **values}


@pytest.mark.parametrize("detector", sorted(CASES))
def test_cada_detector_aplica_nao_aplica_e_sem_canal(detector):
    yes, no, key = CASES[detector]
    assert state_of(detector, _row(yes), REF)[0] == APLICA
    assert state_of(detector, _row(no), REF)[0] == NAO_APLICA
    missing = _row({k: v for k, v in yes.items() if k != key})
    missing["_ausente"] = {detector: "sem o canal"}
    assert state_of(detector, missing, REF)[0] == NC


def test_m6_retomada():
    good = _row({"retomada_s": 0.3})
    early = _row({"retomada_s": -0.6})
    assert det.m6_state(good, REF, NAO_APLICA, NAO_APLICA, True)[0] == APLICA
    assert det.m6_state(early, REF, NAO_APLICA, NAO_APLICA, True)[0] == NAO_APLICA
    assert det.m6_state(good, REF, APLICA, NAO_APLICA, True)[0] == NAO_APLICA
    assert det.m6_state(_row({"retomada_s": 0.3}), {}, NAO_APLICA, NAO_APLICA, True)[0] == NC


def test_detectores_por_volta_e_consistencia():
    rows = [{"lap_id": f"ia#{i}", "origem": "ia", "sessao": "s", "decidido": 0.9, "rpm_troca": 8000.0, "pneu_c": 70.0}
            for i in range(3)]
    rows += [{"lap_id": "me#1", "origem": "humano", "sessao": "s", "decidido": 0.9, "rpm_troca": 8100.0, "pneu_c": 72.0},
             {"lap_id": "me#2", "origem": "humano", "sessao": "s", "decidido": 0.5, "rpm_troca": 7000.0, "pneu_c": 50.0},
             {"lap_id": "me#3", "origem": "humano", "sessao": "s", "decidido": None, "rpm_troca": None, "pneu_c": None}]
    st = det.lap_states(rows).set_index(["lap_id", "detector"])["estado"]
    assert (st["me#1", "V1"], st["me#1", "V2"], st["me#1", "V4"]) == (APLICA, APLICA, APLICA)
    assert (st["me#2", "V1"], st["me#2", "V2"], st["me#2", "V4"]) == (NAO_APLICA, NAO_APLICA, NAO_APLICA)
    assert (st["me#3", "V1"], st["me#3", "V2"], st["me#3", "V4"]) == (NC, NC, NC)
    seg = pd.DataFrame({"origem": "humano", "sessao": ["a"] * 5 + ["b"] * 5 + ["c"] * 2, "curva": "C01",
                        "lap_id": range(12), "tempo_trecho_s": [10.0, 10.01, 10.02, 10.0, 10.01,
                                                                  10.0, 10.5, 9.7, 10.3, 9.9, 10.0, 10.0]})
    v5 = det.consistency_states(seg).set_index("sessao")["estado"]
    assert (v5["a"], v5["b"], v5["c"]) == (APLICA, NAO_APLICA, NC)


# ------------------------------------------ atribuicao e ranking ---

def _ranking_inputs(phases, losses_by_lap, f1_values):
    cp = corner_of(phases)
    ids = [f"r#{i:04d}" for i in range(1, 4)]
    laps = [SimpleNamespace(volta=SimpleNamespace(gravacao="r", lap_id=i, sessao="s"), total=90.0) for i in ids]
    rows = []
    for lap_id in ids:
        for k, other in enumerate(phases):
            for ph in ("frenagem", "entrada", "meio", "saida", "reta"):
                loss = losses_by_lap[lap_id].get(ph, 0.0) if other.curva == cp.curva else 0.0
                rows.append({"lap_id": lap_id, "sessao": "s", "origem": "humano", "curva": other.curva, "k": k,
                             "fase": ph, "perda_s": loss, "perda_vs_melhor_s": loss})
    losses = pd.DataFrame(rows)
    passages = pd.DataFrame([{"lap_id": i, "curva": cp.curva, "s_b_rel": -80.0, "retomada_s": 0.2, "v_min": 100.0}
                             for i in ids])
    ai = pd.DataFrame([{"lap_id": f"ia#{i}", "curva": cp.curva, "s_b_rel": -110.0, "retomada_s": 0.2, "v_min": 100.0}
                       for i in range(3)])
    states = pd.DataFrame([{"lap_id": i, "curva": cp.curva, "detector": "F1", "estado": NAO_APLICA,
                            "valor_regra": v, "indicador": -80.0, "origem": "humano"} for i, v in zip(ids, f1_values)]
                          + [{"lap_id": f"ia#{i}", "curva": cp.curva, "detector": "F1", "estado": APLICA,
                              "valor_regra": 0.0, "indicador": -110.0, "origem": "ia"} for i in range(3)])
    return laps, losses, passages, states, ai, cp


def test_falso_ganho_da_frenagem_tardia(phases):
    loss = {"frenagem": -0.10, "entrada": 0.25, "meio": 0.05}
    laps, losses, passages, states, ai, cp = _ranking_inputs(
        phases, {f"r#{i:04d}": loss for i in range(1, 4)}, [30.0, 30.0, 30.0])
    out = session_ranking("s", laps, losses, passages, states, phases, "r#0001", ai)
    items = [i for i in out["todos_os_itens"] if i["curva"] == cp.curva]
    assert len(items) == 1
    assert items[0]["falso_ganho"] is True
    assert items[0]["perda_mediana_s"] == pytest.approx(0.20)
    assert all(i["fase_sintoma"] != "frenagem" for i in items)


def test_perda_numa_volta_so_nao_entra_no_ranking(phases):
    by_lap = {"r#0001": {"meio": 0.5}, "r#0002": {}, "r#0003": {}}
    laps, losses, passages, states, ai, cp = _ranking_inputs(phases, by_lap, [0.0, 0.0, 0.0])
    out = session_ranking("s", laps, losses, passages, states, phases, "r#0001", ai)
    assert not [i for i in out["todos_os_itens"] if i["curva"] == cp.curva]
    by_lap = {"r#0001": {"meio": 0.5}, "r#0002": {"meio": 0.3}, "r#0003": {}}
    laps, losses, passages, states, ai, cp = _ranking_inputs(phases, by_lap, [0.0, 0.0, 0.0])
    out = session_ranking("s", laps, losses, passages, states, phases, "r#0001", ai)
    assert [i["fase_sintoma"] for i in out["todos_os_itens"] if i["curva"] == cp.curva] == ["meio"]
