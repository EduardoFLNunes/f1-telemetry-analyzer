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


# ------------------------------- pedido 42: pastas, 144 voltas e margem ---

import json

from ml.modelo2 import dados as dados_mod
from ml.modelo2.perda import dentro_da_margem, loss_table


def test_as_144_voltas_da_rodada1_vem_da_lista_versionada():
    ids = dados_mod.voltas_da_rodada1()
    assert len(ids) == 144 and len(set(ids)) == 144
    voltas = json.loads(dados_mod.RODADA1_VOLTAS_FILE.read_text(encoding="utf-8"))["voltas"]
    assert sum(v["origem"] == "ia" for v in voltas) == 14
    assert sum(bool(v["fora_do_store"]) for v in voltas) == 10


def test_pasta_da_rodada_nunca_e_a_raiz_nem_um_arquivo_da_rodada1():
    assert dados_mod.pasta_da_rodada("rodada1_refeita") == dados_mod.raiz() / "rodada1_refeita"
    for bad in ("", ".", "..", "a/b", "a\\b", "C:x", "derivados.parquet", "rotulagem_gabarito.json", "rotulagem"):
        with pytest.raises(ValueError):
            dados_mod.pasta_da_rodada(bad)


def test_sessoes_com_margem_vem_do_meta():
    meta = {"sessoes_aceitas_com_margem": [{"sessao": "2026-11-01_19-47-03_vhe_interlagos", "efeito_ms": 1.8}],
            "margem_linha_do_jogo_ms": 2.0}
    sessions, margin = dados_mod.sessoes_com_margem(meta)
    assert set(sessions) == {"2026-11-01_19-47-03_vhe_interlagos"} and margin == pytest.approx(0.002)
    assert dados_mod._com_margem("2026-11-01_19-47-03_vhe_interlagos", sessions)
    assert not dados_mod._com_margem("2026-11-07_18-46-00_vhe_interlagos", sessions)
    assert dados_mod._com_margem("2026-11-01_19-47-03_vhe_interlagos", {"2026-11-01_19-47-03": {}})
    # sem a margem no meta, vale a decisao de 17/11 (2,0 ms); sem a lista, nenhuma sessao
    empty, margin = dados_mod.sessoes_com_margem({"sessoes_aceitas_com_margem": []})
    assert empty == {} and margin == pytest.approx(0.002)
    assert dados_mod.sessoes_com_margem({})[0] == {}


def test_margem_marca_a_perda_so_nas_sessoes_aceitas_com_margem(phases):
    ref = synthetic_lap("ref#0001", origem="ia")
    # cerca de 1 ms mais lenta na volta inteira: cada fase fica dentro da margem
    slow = lambda s: np.full_like(s, 150.0 * (1.0 - 1e-3 / ref.total))
    marked = synthetic_lap("m#0001", speed_kmh=slow)
    marked.volta.com_margem = True
    plain = synthetic_lap("p#0001", speed_kmh=slow)
    table = loss_table([marked, plain], ref, ref, TRACK, phases, margem_s=0.002)
    m = table[table["lap_id"] == "m#0001"]
    p = table[table["lap_id"] == "p#0001"]
    assert m["sessao_com_margem"].all() and m["dentro_da_margem"].all()
    assert not p["sessao_com_margem"].any() and not p["dentro_da_margem"].any()
    assert dentro_da_margem([0.0021, -0.002, 0.001], [True, True, False], 0.002).tolist() == [False, True, False]


def test_margem_tira_o_ganho_pequeno_do_falso_ganho(phases):
    # Frenagem com ganho de 1 ms (dentro da margem): sem a margem e falso ganho; com a margem, nao.
    loss = {"frenagem": -0.001, "entrada": 0.25, "meio": 0.05}
    laps, losses, passages, states, ai, cp = _ranking_inputs(
        phases, {f"r#{i:04d}": loss for i in range(1, 4)}, [30.0, 30.0, 30.0])
    plain = session_ranking("s", laps, losses, passages, states, phases, "r#0001", ai)
    assert [i["falso_ganho"] for i in plain["todos_os_itens"] if i["curva"] == cp.curva] == [True]
    flagged = losses.assign(sessao_com_margem=True)
    flagged["dentro_da_margem"] = dentro_da_margem(flagged["perda_s"], flagged["sessao_com_margem"], 0.002)
    flagged["dentro_da_margem_vs_melhor"] = flagged["dentro_da_margem"]
    out = session_ranking("s", laps, flagged, passages, states, phases, "r#0001", ai)
    items = [i for i in out["todos_os_itens"] if i["curva"] == cp.curva]
    assert out["sessao_com_margem"] is True
    assert not any(i["falso_ganho"] for i in items)
    assert sorted(i["fase_sintoma"] for i in items) == ["entrada", "meio"]


def _fake_world(tmp_path, monkeypatch, aprovado=True):
    """Um store, um cache da rodada 1 e gravacoes falsos, num data/ml temporario."""
    ml = tmp_path / "ml"
    root = ml / "modelo2"
    root.mkdir(parents=True)
    (ml / "laps_grid_v2.parquet").write_bytes(b"x")
    (ml / "laps_grid_v2_meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(dados_mod.config, "artifacts_root", lambda: ml)
    n = 5

    def derived_frame(lap_id):
        f = pd.DataFrame({"grid_index": np.arange(n)})
        for c in dados_mod.DERIVED:
            f[c] = 1.0
        return f.assign(lap_id=lap_id)

    def grid(lap_id):
        return pd.DataFrame({"lap_id": lap_id, "grid_index": np.arange(n), "speed_kmh": 100.0})

    store_ids = ["A_vhe#0001", "A_vhe#0002", "B_vhe#0001", "C_vhe#0001"]
    laps = pd.DataFrame({"lap_id": store_ids, "session_id": [i.split("#")[0] for i in store_ids],
                         "sequence": [1, 2, 1, 1], "raw_samples": [10, 10, 10, 10], "origem": "humano",
                         "lap_time_s": 90.0})
    frame = pd.concat([grid(i) for i in store_ids])
    pd.concat([derived_frame(i) for i in ("A_vhe#0001", "A_vhe#0002", "2026-10-22_09-46-01_vhe#0001")]).to_parquet(root / "derivados.parquet")
    grid("2026-10-22_09-46-01_vhe#0001").to_parquet(root / "fora_do_store.parquet")
    (root / "fora_do_store.json").write_text(json.dumps({
        "voltas": [{"lap_id": "2026-10-22_09-46-01_vhe#0001", "gravacao": "2026-10-22_09-46-01_vhe", "origem": "ia", "tempo_s": 85.0, "canais": []}],
        "relatorio": {}}), encoding="utf-8")
    periods = {g: {"inicio": f"2026-10-{d}T10:00:00", "duracao_s": 600}
               for g, d in (("A_vhe", "20"), ("B_vhe", "30"), ("C_vhe", "21"))}
    meta = {"aprovado": aprovado, "periodos_das_gravacoes": periods,
            "sessoes_aceitas_com_margem": [{"sessao": "B_vhe"}], "margem_linha_do_jogo_ms": 2.0}
    calls = []
    stream = tmp_path / "stream.jsonl"
    stream.write_text("x", encoding="utf-8")
    monkeypatch.setattr(dados_mod, "store_v2_meta", lambda: meta)
    monkeypatch.setattr(dados_mod, "load_store_v2", lambda track=None: SimpleNamespace(laps=laps, frame=frame))
    monkeypatch.setattr(dados_mod, "store_selection", lambda df: df)
    monkeypatch.setattr(dados_mod, "list_all_sessions", lambda: [
        SimpleNamespace(session_id=s, player_stream=stream) for s in ("A_vhe", "B_vhe", "C_vhe", "2026-10-22_09-46-01_vhe")])

    def fake_derived(session, sequences, track):
        calls.append((session.session_id, dict(sequences)))
        return {f"{session.session_id}#{q:04d}": derived_frame("x").drop(columns="lap_id") for q in sequences}

    monkeypatch.setattr(dados_mod, "derived_for_session", fake_derived)
    return root, calls


def _snapshot(root):
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns, p.read_bytes()) for p in root.iterdir() if p.is_file()}


def test_carregar_le_os_caches_da_rodada1_e_grava_so_na_pasta_da_rodada(tmp_path, monkeypatch):
    root, calls = _fake_world(tmp_path, monkeypatch)
    before = _snapshot(root)
    out = root / "rodada2"
    data = dados_mod.carregar(None, saida=out, so_ids=["A_vhe#0001", "A_vhe#0002", "2026-10-22_09-46-01_vhe#0001"],
                              mais_ids=["B_vhe#0001"], progress=lambda *_: None)
    assert _snapshot(root) == before                       # nada da rodada 1 mudou
    assert set(data.voltas) == {"A_vhe#0001", "A_vhe#0002", "2026-10-22_09-46-01_vhe#0001", "B_vhe#0001"}
    assert calls == [("B_vhe", {1: 10})]                   # so a volta nova teve as taxas calculadas
    own = pd.read_parquet(out / "derivados.parquet")
    assert set(own["lap_id"]) == {"B_vhe#0001"}
    assert data.escritos == [str(out / "derivados.parquet")]
    assert data.voltas["B_vhe#0001"].com_margem and not data.voltas["A_vhe#0001"].com_margem
    assert data.voltas["2026-10-22_09-46-01_vhe#0001"].fora_do_store and data.margem_s == pytest.approx(0.002)
    # sem saida, nada e gravado
    again = dados_mod.carregar(None, so_ids=["A_vhe#0001"], progress=lambda *_: None)
    assert set(again.voltas) == {"A_vhe#0001"} and again.escritos == []
    assert _snapshot(root) == before


def test_carregar_para_sem_uma_volta_pedida_e_com_o_store_reprovado(tmp_path, monkeypatch):
    root, _ = _fake_world(tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match="nao foram encontradas"):
        dados_mod.carregar(None, so_ids=["A_vhe#0001", "Z_vhe#0009"], progress=lambda *_: None)
    with pytest.raises(ValueError):
        dados_mod.carregar(None, saida=root, so_ids=["A_vhe#0001"], progress=lambda *_: None)
    other = tmp_path / "b"
    other.mkdir()
    _fake_world(other, monkeypatch, aprovado=False)
    with pytest.raises(SystemExit, match="nao aprovado"):
        dados_mod.carregar(None, saida=other / "ml" / "modelo2" / "r", so_ids=["A_vhe#0001"])


# ------------------------------- pedido 42, Parte D.5: as emendas e a referencia ---

from ml.modelo2.detectores import pickup_index, turn_in_index
from ml.modelo2.perda import attribute_r2


def _longest_entry(phases):
    return max(phases, key=lambda cp: (cp.apice - cp.a) % TRACK.length)


def _longest_exit(phases):
    return max(phases, key=lambda cp: (cp.e - cp.apice) % TRACK.length)


def test_retomada_com_acelerador_parcial_na_entrada_fica_depois_da_minima(phases):
    cp = _longest_exit(phases)
    a, apex = cp.a, cp.apice
    speed = lambda s: 200.0 - 100.0 * np.exp(-((s - apex) / 40.0) ** 2)
    # a IA: acelerador parcial (0,3) desde antes da entrada, e a subida so depois da minima
    throttle = lambda s: np.where(s < a - 30.0, 1.0, np.where(s < apex + 5.0, 0.3,
                                                              np.clip(0.3 + (s - apex - 5.0) / 60.0, 0.3, 1.0)))
    lap = synthetic_lap("pu#0001", speed_kmh=speed, channels={"throttle": throttle,
                                                               "brake": bump(a - 60.0, 30.0, 0.8)})
    env = lambda v: np.full_like(np.asarray(v, dtype=float), 3.0)
    r1 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=1)
    r2 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=2)
    assert r1["retomada_s"] < -0.3                # rodada 1: o acelerador parcial ja conta como retomada
    assert 0.0 <= r2["retomada_s"] < 0.6          # rodada 2: o comeco da subida, depois da minima
    assert r2["s_pu_rel"] >= r2["s_vmin_rel"]
    assert r2["retomada_no_pleno"] is False


def test_pickup_index_regras_fixas():
    t = np.arange(0.0, 3.0, 0.02)
    # sobe 0,10 e volta abaixo do comeco antes de 0,5 s: descartada; a subida seguinte vale
    thr = np.full(t.size, 0.2)
    thr[(t >= 0.4) & (t < 0.6)] = 0.35
    thr[(t >= 0.6) & (t < 1.0)] = 0.1
    thr[t >= 1.0] = np.clip(0.1 + (t[t >= 1.0] - 1.0), 0.1, 1.0)
    i, full = pickup_index(thr, t, 0, t.size - 1)
    assert not full and t[i] == pytest.approx(0.98, abs=0.03)
    # pleno na minima
    assert pickup_index(np.full(t.size, 0.95), t, 10, t.size - 1) == (10, True)
    # sem subida de 0,10
    assert pickup_index(np.full(t.size, 0.2) + 0.05 * (t > 1.0), t, 0, t.size - 1) == (None, False)


def test_turn_in_index_nao_corta_na_troca_de_sinal():
    into = np.concatenate([np.zeros(10), np.full(10, 0.5), np.full(5, -0.2), np.full(20, 1.0)])
    apex = 35
    assert turn_in_index(into, 1.0, apex, rodada=1) == 25      # rodada 1: corta no contraesterco
    assert turn_in_index(into, 1.0, apex, rodada=2) == 10      # rodada 2: une os dois trechos
    relaxed = np.concatenate([np.zeros(10), np.full(10, 0.5), np.full(5, 0.02), np.full(20, 1.0)])
    assert turn_in_index(relaxed, 1.0, apex, rodada=2) == 25   # sem troca de sinal, continua cortando


def test_contraesterco_antes_do_apice_e_visto_pelo_e4_da_rodada2(phases):
    cp = _longest_entry(phases)
    a, apex, sign = cp.a, cp.apice, cp.direcao
    c0, c1 = a + 0.35 * (apex - a), a + 0.35 * (apex - a) + 12.0
    assert c1 < apex - 5.0

    def steer(s):
        normal = -0.3 * sign * np.clip((s - (a - 20.0)) / 15.0, 0.0, 1.0) * np.clip((cp.e - s) / 20.0, 0.0, 1.0)
        return np.where((s >= c0) & (s < c1), 0.1 * sign, normal)

    lap = synthetic_lap("ce#0001", channels={"steer_angle": steer, "yaw_rate": lambda s: np.full_like(s, 0.3 * sign),
                                             "lateral_g": lambda s: np.full_like(s, 1.0 * sign),
                                             "brake": bump(a - 60.0, 30.0, 0.8)})
    env = lambda v: np.full_like(np.asarray(v, dtype=float), 3.0)
    r1 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=1)
    r2 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=2)
    assert r2["s_ti_rel"] < r1["s_ti_rel"]                    # a sequencia nao e cortada
    assert r1["contra_s"] < 0.03                               # rodada 1: fora da janela
    assert r2["contra_s"] >= 0.10 and r2["contra_antes_apice_s"] >= 0.10
    assert state_of("E4", r2, corner_refs([]))[0] == APLICA


def test_ranking_da_rodada2_e_sem_o_peso(phases):
    by_lap = {f"r#{i:04d}": {"meio": 0.30, "saida": 0.25} for i in range(1, 4)}
    laps, losses, passages, states, ai, cp = _ranking_inputs(phases, by_lap, [0.0, 0.0, 0.0])
    ref_points = pd.DataFrame([{"curva": c.curva, "s_b_rel": -110.0, "retomada_s": 0.2, "v_min": 100.0,
                                "s_vmin_rel": 50.0, "afastamento_m": 5.0} for c in phases]).set_index("curva")
    out = session_ranking("s", laps, losses, passages, states, phases, "r#0001", ai, rodada=2, ref_points=ref_points)
    items = [i for i in out["todos_os_itens"] if i["curva"] == cp.curva]
    assert {i["fase_sintoma"]: i["pontuacao"] for i in items} == {"meio": 0.30, "saida": 0.25}
    assert all(i["pontuacao_com_peso"] == pytest.approx(i["perda_mediana_s"] * cp.peso, abs=1e-4) for i in items)
    assert "itens_com_peso_informativo" in out and "itens_sem_peso_informativo" not in out
    r1 = session_ranking("s", laps, losses, passages, states, phases, "r#0001", ai)
    assert all(i["pontuacao"] == pytest.approx(i["perda_mediana_s"] * cp.peso, abs=1e-4)
               for i in r1["todos_os_itens"] if i["curva"] == cp.curva)


def test_a_perda_e_contra_a_volta_do_modelo(phases):
    from ml.modelo2.perda import loss_table
    slow = synthetic_lap("me#0001", speed_kmh=lambda s: np.full_like(s, 140.0))
    model = synthetic_lap("vm#0001", origem="volta_do_modelo", speed_kmh=lambda s: np.full_like(s, 150.0))
    best = synthetic_lap("b#0001", speed_kmh=lambda s: np.full_like(s, 145.0))
    table = loss_table([slow], model, best, TRACK, phases)
    assert table["perda_s"].sum() == pytest.approx(slow.total - model.total, abs=1e-9)
    assert table["perda_vs_melhor_s"].sum() == pytest.approx(slow.total - best.total, abs=1e-9)


def test_a_forma_do_pedal_nunca_e_comparada_com_a_volta_do_modelo(phases):
    cp = corner_of(phases)
    last = ["me#0001", "me#0002", "me#0003"]
    rows = []
    for lap_id, origem, f4, x in [(i, "humano", NAO_APLICA, 6.0) for i in last] + [("best#0001", "humano", APLICA, 1.0)] \
            + [(f"ia#{i}", "ia", NAO_APLICA, 6.0) for i in range(3)]:
        rows.append({"lap_id": lap_id, "curva": cp.curva, "detector": "F4", "estado": f4, "indicador": x, "origem": origem})
    for lap_id in last + ["best#0001"]:
        rows.append({"lap_id": lap_id, "curva": cp.curva, "detector": "F1", "estado": APLICA, "indicador": -100.0,
                     "origem": "humano"})
    states = pd.DataFrame(rows)
    passages = pd.DataFrame([{"lap_id": i, "curva": cp.curva, "s_b_rel": -100.0} for i in last + ["best#0001"]])
    # A volta do modelo freia no mesmo ponto; o pedal dela (que a IA comandou) nao entra em nada.
    ref_points = pd.DataFrame([{"curva": cp.curva, "s_b_rel": -100.0}]).set_index("curva")
    out = attribute_r2(cp.curva, ["frenagem", "entrada"], last, "best#0001", states, passages, ref_points,
                       last + ["best#0001"])
    assert out["explica"]["detector"] == "F4"
    assert out["explica"]["comparado_com"] == "sua melhor volta"
    f1 = next(c for c in out["conferidos"] if c["detector"] == "F1")
    assert f1["tipo"] == "ponto" and f1["comparado_com"] == "volta de referencia"
    # a IA igual ao piloto nao muda nada: a forma e julgada contra a melhor volta
    assert out["explica"]["estado_ia"] == NAO_APLICA
    # sem a melhor volta diferente, nenhum detector de forma explica
    same = states.copy()
    same.loc[(same["lap_id"] == "best#0001") & (same["detector"] == "F4"), ["estado", "indicador"]] = [NAO_APLICA, 6.0]
    out2 = attribute_r2(cp.curva, ["frenagem", "entrada"], last, "best#0001", same, passages, ref_points,
                        last + ["best#0001"])
    assert out2["conclusao"] == "nao_conclusivo"


def test_kit2_esquematico_e_paginas_da_literatura():
    from ml.modelo2 import rotulagem
    for det in rotulagem.DETECTORS:
        page = rotulagem.literature_page(det)
        assert "aplica" in page and "não aplica" in page and "nao sei" in page and "Fonte" in page
        assert " IA" not in page.replace("IA do", "")


# ------------------------------- pedido 42, rodada 3: a emenda da entrada ---

def _same_side_pair(phases):
    """Uma curva que vem depois de outra para o mesmo lado, com reta de 100 m ou mais entre elas."""
    from ml.modelo2.fases import ahead
    for cp in phases:
        prev = phases[cp.k - 1]
        if (prev.direcao == cp.direcao and ahead(TRACK, prev.e, cp.a) > 100.0 and prev.a < prev.e < cp.a < cp.e):
            return prev, cp
    raise AssertionError("sem par de curvas para o mesmo lado")


def test_rodada3_a_entrada_nao_recua_ate_a_curva_anterior(phases):
    prev, cp = _same_side_pair(phases)
    sign = cp.direcao
    mid = prev.e + 0.5 * (cp.a - prev.e)       # o meio da reta entre as duas curvas

    def steer(s):
        first = np.where((s >= prev.a - 10.0) & (s < prev.e + 10.0), -0.3 * sign, 0.0)
        second = -0.3 * sign * np.clip((s - (cp.a - 5.0)) / 15.0, 0.0, 1.0) * np.clip((cp.e + 20.0 - s) / 20.0, 0.0, 1.0)
        straight = np.where((s >= mid - 5.0) & (s < mid + 5.0), 0.05 * sign, 0.0)   # levemente para o outro lado
        return first + second + straight

    lap = synthetic_lap("r3#0001", channels={"steer_angle": steer, "yaw_rate": lambda s: np.full_like(s, 0.3 * sign),
                                             "lateral_g": lambda s: np.full_like(s, 1.0 * sign)})
    env = lambda v: np.full_like(np.asarray(v, dtype=float), 3.0)
    r2 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=2)
    r3 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=3)
    gap = (cp.a - prev.e) % TRACK.length
    assert r2["s_ti_rel"] < -gap                   # rodada 2: recua ate a curva anterior (o defeito)
    assert -10.0 <= r3["s_ti_rel"] <= 5.0          # rodada 3: a entrada desta curva


def test_rodada3_o_contraesterco_antes_do_apice_continua_visto(phases):
    cp = _longest_entry(phases)
    a, apex, sign = cp.a, cp.apice, cp.direcao
    c0, c1 = a + 0.35 * (apex - a), a + 0.35 * (apex - a) + 12.0

    def steer(s):
        normal = -0.3 * sign * np.clip((s - (a - 20.0)) / 15.0, 0.0, 1.0) * np.clip((cp.e - s) / 20.0, 0.0, 1.0)
        return np.where((s >= c0) & (s < c1), 0.1 * sign, normal)

    lap = synthetic_lap("r3#0002", channels={"steer_angle": steer, "yaw_rate": lambda s: np.full_like(s, 0.3 * sign),
                                             "lateral_g": lambda s: np.full_like(s, 1.0 * sign),
                                             "brake": bump(a - 60.0, 30.0, 0.8)})
    env = lambda v: np.full_like(np.asarray(v, dtype=float), 3.0)
    r2 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=2)
    r3 = measure_passage(lap, TRACK, cp, phases[cp.k - 1], env, rodada=3)
    assert r3["s_ti_rel"] == r2["s_ti_rel"]        # dentro da curva, a uniao vale como na rodada 2
    assert r3["contra_s"] >= 0.10 and r3["contra_antes_apice_s"] >= 0.10
    assert state_of("E4", r3, corner_refs([]))[0] == APLICA


def test_turn_in_index_rodada3_so_une_depois_do_fim_da_curva_anterior():
    into = np.concatenate([np.full(10, 0.5), np.full(5, -0.2), np.full(10, 0.0), np.full(5, 0.5), np.full(4, -0.2),
                           np.full(16, 1.0)])
    apex = 40
    assert turn_in_index(into, 1.0, apex, rodada=2) == 0            # rodada 2: une tudo, desde a curva anterior
    assert turn_in_index(into, 1.0, apex, rodada=3, previous_end=12) == 25   # o primeiro buraco comeca antes de e_(k-1)
    # um trecho que comeca antes de e_(k-1) nunca e unido, mesmo que acabe depois dele
    assert turn_in_index(into, 1.0, apex, rodada=3, previous_end=5) == 25
    assert turn_in_index(into, 1.0, apex, rodada=3, previous_end=0) == 0
