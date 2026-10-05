"""Pedido 16: store v2 (periodo, box, duplicatas) e relatorio de evolucao.

Tudo sintetico, numa pista circular: nenhum teste depende das gravacoes.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))

from ml.comparison import evolution as ev  # noqa: E402
from ml.data import store_checks  # noqa: E402
from ml.data.ai_detector import pit_lap  # noqa: E402
from ml.data.lap_store import StoredLaps  # noqa: E402
from ml.data.recordings import RawLap, Session  # noqa: E402
from ml.data.store_v2 import build_store_v2, game_lap_time, select_v2  # noqa: E402
from ml.preprocessing.resampling import resample_lap  # noqa: E402
from ml.track.corners import Corner  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from test_lap_origin import circular_track  # noqa: E402

SPEED = 40.0          # m/s
HZ = 60.0


def aligned_lap(track, *, start_m=1.3, end_gap_m=0.7, speed=SPEED, stale_last=False):
    """Uma volta alinhada a velocidade constante, do inicio (logo depois da linha) a pouco antes dela."""
    step = speed / HZ
    u = np.arange(start_m, track.length - end_gap_m, step)
    t = (u - 0.0) / speed
    if stale_last:
        t[-1] = t[-2]                       # o cronometro do jogo repetiu o valor
    return pd.DataFrame({
        "s": np.mod(u, track.length), "s_unwrapped": u, "lateral": np.zeros(u.size),
        "elapsed_s": t - t.min(), "speed_kmh": np.full(u.size, speed * 3.6),
        "brake": np.zeros(u.size), "throttle": np.ones(u.size),
    })


def raw_lap(track, sequence, *, start_m, end_m, timer_zero_m=0.0, speed=SPEED, t0=1000.0, lap_number=1):
    """Volta crua: posicao no circulo, cronometro do jogo zerado na linha, relogio de parede."""
    step = speed / HZ
    u = np.arange(start_m, end_m, step)
    theta = np.mod(u, track.length) / 200.0
    timer = np.mod(u - timer_zero_m, track.length) / speed
    return RawLap(
        session_id="2026-10-05_20-00-00_vhe_interlagos", lap_number=lap_number, track="vhe_interlagos",
        sequence=sequence,
        frame=pd.DataFrame({"x": 200.0 * np.cos(theta), "z": 200.0 * np.sin(theta), "lap_time_s": timer,
                            "speed_kmh": np.full(u.size, speed * 3.6), "timestamp_s": t0 + u / speed}),
    )


class PeriodTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.period = self.track.length / SPEED

    def test_the_line_clock_gives_the_true_period(self):
        grid = resample_lap(aligned_lap(self.track), self.track, line_clock=True)
        self.assertAlmostEqual(grid["lap_time_s"].iloc[0], self.period, places=6)
        self.assertEqual(grid["elapsed_s"].iloc[0], 0.0)
        self.assertTrue(np.all(np.diff(grid["elapsed_s"]) >= 0))

    def test_the_old_clock_is_one_grid_step_short(self):
        """O erro que o store v2 corrige: o store antigo perde o tempo de um passo da grade."""
        old = resample_lap(aligned_lap(self.track), self.track)["lap_time_s"].iloc[0]
        self.assertAlmostEqual(self.period - old, self.track.step / SPEED, delta=0.2 * self.track.step / SPEED)

    def test_a_repeated_game_timer_does_not_move_the_period(self):
        grid = resample_lap(aligned_lap(self.track, stale_last=True), self.track, line_clock=True)
        self.assertLess(abs(grid["lap_time_s"].iloc[0] - self.period), 0.001)

    def test_the_game_time_is_stitched_at_the_reset(self):
        lap = raw_lap(self.track, 3, start_m=0.4, end_m=self.track.length - 0.3)
        following = raw_lap(self.track, 4, start_m=self.track.length + 0.4, end_m=self.track.length + 60.0,
                            t0=1000.0, lap_number=2)
        self.assertAlmostEqual(game_lap_time(lap, following, self.track), self.period, places=4)

    def test_no_game_time_without_the_following_lap_right_after(self):
        lap = raw_lap(self.track, 3, start_m=0.4, end_m=self.track.length - 0.3)
        far = raw_lap(self.track, 4, start_m=self.track.length + 120.0, end_m=self.track.length + 200.0)
        later = raw_lap(self.track, 6, start_m=self.track.length + 0.4, end_m=self.track.length + 60.0)
        self.assertIsNone(game_lap_time(lap, far, self.track))
        self.assertIsNone(game_lap_time(lap, later, self.track))

    def test_the_main_check(self):
        laps = pd.DataFrame({"lap_id": ["a", "b", "c", "d"], "lap_time_s": [85.001, 86.0, 84.9985, 90.0],
                             "tempo_jogo_s": [85.0, 86.002, 85.0, None]})
        ok = store_checks.check_period(laps)
        self.assertTrue(ok["passou"])
        self.assertEqual((ok["voltas_medidas"], ok["voltas_sem_fechamento_medido"]), (3, 1))
        short = laps.assign(lap_time_s=laps["lap_time_s"] - 0.026)
        self.assertFalse(store_checks.check_period(short)["passou"])
        self.assertFalse(store_checks.check_period(laps.assign(tempo_jogo_s=None))["passou"])


def grid_frame(track, *, pit=False):
    sectors = build_microsectors(track)
    lateral = np.zeros(track.size)
    speed = np.full(track.size, 200.0)
    if pit:
        near = np.isin(sectors.index, [58, 59])
        lateral[near], speed[near] = 25.0, 60.0
    return pd.DataFrame({"lateral": lateral, "speed_kmh": speed, "elapsed_s": track.s / SPEED,
                         "brake": np.zeros(track.size)})


class BoxAndDuplicatesTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.sectors = build_microsectors(self.track)

    def test_the_box_gate(self):
        self.assertFalse(pit_lap(grid_frame(self.track), self.sectors))
        self.assertTrue(pit_lap(grid_frame(self.track, pit=True), self.sectors))
        frames = []
        for lap_id, pit in (("a#0000", False), ("a#0001", True)):
            frame = grid_frame(self.track, pit=pit)
            frame.insert(0, "grid_index", np.arange(self.track.size))
            frame.insert(0, "lap_id", lap_id)
            frames.append(frame)
        store = StoredLaps(frame=pd.concat(frames, ignore_index=True),
                           laps=pd.DataFrame({"lap_id": ["a#0000", "a#0001"]}),
                           grid_size=self.track.size, track_length=self.track.length)
        check = store_checks.check_no_box(store, self.sectors)
        self.assertEqual((check["passou"], check["voltas_com_box"]), (False, ["a#0001"]))

    def test_duplicates_are_left_out(self):
        inventory = pd.DataFrame({"lap_id": ["a#0", "a#1", "b#0", "c#0"], "valid": [True, True, True, False],
                                  "duplicada_de": [None, None, "a#0", None]})
        wanted, counts = select_v2(inventory)
        self.assertEqual(wanted["lap_id"].tolist(), ["a#0", "a#1"])
        self.assertEqual((counts["validas"], counts["duplicadas_tiradas"]), (3, 1))

    def test_the_duplicate_check(self):
        laps = pd.DataFrame({
            "lap_id": ["s1#0", "s2#0", "s3#0"], "session_id": ["s1", "s2", "s3"],
            "pasta": ["repositorio", "app_instalado", "repositorio"], "duplicada_de": [None, None, None],
            "inicio_epoch_s": [0.0, 1.0, 200.0], "fim_epoch_s": [85.0, 86.0, 285.0],
        })
        check = store_checks.check_no_duplicates(laps)
        self.assertFalse(check["passou"])
        self.assertEqual(len(check["pares_de_pastas_diferentes_sobrepostos"]), 1)
        self.assertTrue(store_checks.check_no_duplicates(laps.drop(index=1))["passou"])


def write_session(directory: Path, track, laps):
    """Grava um player.jsonl com as voltas dadas: (numero, s_inicio, s_fim, pit_no_fim)."""
    lines = []
    clock = 1_790_000_000.0
    for number, start, end, pit in laps:
        u = np.arange(start, end, SPEED / HZ)
        for value in u:
            lateral = 25.0 if pit and np.mod(value, track.length) > track.length - 120.0 else 0.0
            speed = 60.0 / 3.6 if lateral else SPEED
            radius = 200.0 - lateral          # pista anti-horaria, normal para fora: lateral positivo e para dentro
            theta = np.mod(value, track.length) / 200.0
            clock += (SPEED / HZ) / SPEED
            lines.append(json.dumps({"timestamp": clock * 1000.0, "track": "vhe_interlagos", "sample": {
                "lap": number, "lap_number": number, "lap_time": float(np.mod(value, track.length) / SPEED),
                "world_x": radius * np.cos(theta), "world_z": radius * np.sin(theta), "speedKmh": speed * 3.6,
                "carPhysics": {"controls": {"throttle": 1.0, "brake": 0.0}},
            }}))
    directory.mkdir(parents=True)
    (directory / "player.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class BuildTest(unittest.TestCase):
    def test_box_laps_and_duplicates_stay_out_and_the_game_time_is_measured(self):
        import dataclasses

        track = dataclasses.replace(circular_track(), geometry_id="circulo-1")
        root = Path(tempfile.mkdtemp())
        session_id = "2026-10-05_20-00-00_vhe_interlagos"
        L = track.length
        write_session(root / session_id, track, [
            (1, 0.4, L - 0.3, False),
            (2, L + 0.4, 2 * L - 0.3, True),          # entra no box no fim
            (3, 2 * L + 0.4, 3 * L - 0.3, False),
            (4, 3 * L + 0.4, 3 * L + 50.0, False),
        ])
        inventory = pd.DataFrame({
            "lap_id": [f"{session_id}#{i:04d}" for i in range(3)], "session_id": session_id, "sequence": [0, 1, 2],
            "valid": True, "duplicada_de": [None, None, "outra#0000"], "geometry_id": track.geometry_id,
            "origem": "humano", "equipamento": "atual", "pasta": "repositorio",
            "relogio_verificado": True, "relogio_suspeito": False,
        })
        session = Session(session_id=session_id, directory=root / session_id, track="vhe_interlagos")
        store, details = build_store_v2(inventory, track=track, sessions=[session])
        self.assertEqual(store.lap_ids, [f"{session_id}#0000"])
        self.assertEqual(details.box_removed, [f"{session_id}#0001"])
        self.assertEqual(details.selection["duplicadas_tiradas"], 1)
        lap = store.laps.iloc[0]
        self.assertAlmostEqual(lap["lap_time_s"], L / SPEED, delta=0.002)
        self.assertAlmostEqual(lap["tempo_jogo_s"], L / SPEED, delta=0.002)
        self.assertEqual(lap["origem"], "humano")
        self.assertTrue(store_checks.check_period(store.laps)["passou"])


class EvolutionRulesTest(unittest.TestCase):
    def test_consistent_difference_needs_an_interval_without_zero(self):
        losing = ev.consistency([0.30, 0.32, 0.29, 0.35, 0.31, 0.33])
        self.assertEqual((losing["situacao"], losing["lado"]), ("diferenca_consistente", "perde"))
        self.assertGreater(losing["intervalo_90_s"][0], 0.0)
        gaining = ev.consistency([-0.2, -0.25, -0.22, -0.18, -0.21])
        self.assertEqual((gaining["situacao"], gaining["lado"]), ("diferenca_consistente", "ganha"))
        mixed = ev.consistency([0.4, -0.3, 0.1, -0.2, 0.05, -0.1])
        self.assertEqual(mixed["situacao"], "sem_diferenca_consistente")
        low, high = mixed["intervalo_90_s"]
        self.assertLessEqual(low, 0.0)
        self.assertGreaterEqual(high, 0.0)

    def test_fewer_than_five_laps_is_few_data(self):
        few = ev.consistency([0.5, 0.6, 0.55, 0.52])
        self.assertEqual((few["situacao"], few["intervalo_90_s"]), ("poucos_dados", None))
        self.assertEqual(ev.consistency([0.5, 0.6, 0.55, 0.52, 0.51])["situacao"], "diferenca_consistente")

    def test_the_bootstrap_is_reproducible(self):
        values = [0.1, 0.4, 0.2, 0.3, 0.25, 0.15]
        self.assertEqual(ev.bootstrap_median_interval(values), ev.bootstrap_median_interval(values))

    def test_only_human_laps_with_the_current_equipment_and_a_checked_clock(self):
        laps = pd.DataFrame({
            "lap_id": list("abcdef"),
            "origem": ["humano", "ia", "humano", "humano", "humano", "misturada"],
            "equipamento": ["atual", "atual", "anterior", "atual", "atual", "atual"],
            "relogio_verificado": [True, True, True, False, True, True],
            "relogio_suspeito": [False, False, False, False, True, False],
        })
        self.assertEqual(ev.driver_laps(laps)["lap_id"].tolist(), ["a"])

    def test_sessions_are_split_by_a_pause_and_dated_by_their_end(self):
        """Emenda de 05/10: a madrugada de 04/10 e a noite de 04/10 a 05/10 sao sessoes diferentes."""
        periods = {
            "2026-10-04_02-24-04_vhe_interlagos": {"inicio": "2026-10-04T02:24:04", "duracao_s": 3400.0},
            "2026-10-04_03-21-52_vhe_interlagos": {"inicio": "2026-10-04T03:21:52", "duracao_s": 840.0},
            "2026-10-04_03-42-10_vhe_interlagos": {"inicio": "2026-10-04T03:42:10", "duracao_s": 2400.0},
            "2026-10-04_23-51-42_vhe_interlagos": {"inicio": "2026-10-04T23:51:42", "duracao_s": 2440.0},
        }
        sessions = ev.group_sessions(periods)
        self.assertEqual(sessions["2026-10-04_02-24-04_vhe_interlagos"], "2026-10-04")
        self.assertEqual(sessions["2026-10-04_03-42-10_vhe_interlagos"], "2026-10-04")
        self.assertEqual(sessions["2026-10-04_23-51-42_vhe_interlagos"], "2026-10-05")
        # Pausa de ate 3 h nao separa; duas sessoes no mesmo dia nao se juntam.
        close = {"a": {"inicio": "2026-10-06T10:00:00", "duracao_s": 3600.0},
                 "b": {"inicio": "2026-10-06T13:30:00", "duracao_s": 600.0},
                 "c": {"inicio": "2026-10-06T20:00:00", "duracao_s": 600.0}}
        self.assertEqual(ev.group_sessions(close), {"a": "2026-10-06", "b": "2026-10-06", "c": "2026-10-06-2"})

    def test_the_corner_segments_cover_the_lap_and_add_up(self):
        track = circular_track()
        corners = [Corner(i, a, (a + b) / 2, b, 1, 50.0, 50.0, b - a)
                   for i, (a, b) in enumerate([(100.0, 200.0), (500.0, 600.0), (1000.0, 1100.0)])]
        segments = ev.corner_segments(track, corners)
        lengths = [np.mod(s.end_s - s.start_s, track.length) for s in segments]
        self.assertAlmostEqual(sum(lengths), track.length, places=6)
        self.assertAlmostEqual(segments[1].start_s, 350.0)
        # Uma volta 1 s mais lenta, toda no trecho da segunda curva: a perda aparece ali e soma 1 s.
        ref = pd.DataFrame({"elapsed_s": track.s / SPEED, "speed_kmh": np.full(track.size, 144.0),
                            "lateral": np.zeros(track.size), "brake": np.zeros(track.size)})
        lap = ref.copy()
        inside = (track.s >= 450.0) & (track.s < 600.0)
        lap["elapsed_s"] = ref["elapsed_s"] + np.where(track.s >= 600.0, 1.0, np.where(inside, (track.s - 450.0) / 150.0, 0.0))
        total = track.length / SPEED
        features = ev.lap_corner_features(lap, total + 1.0, ref, total, track, segments)
        losses = [f["perda_s"] for f in features]
        self.assertAlmostEqual(sum(losses), 1.0, places=6)
        self.assertAlmostEqual(losses[1], 1.0, places=3)

    def test_braking_point_is_a_rising_edge(self):
        track = circular_track()
        brake = np.zeros(track.size)
        brake[(track.s >= 300.0) & (track.s < 340.0)] = 0.8
        self.assertAlmostEqual(ev.braking_point(brake, track, 250.0, 400.0), 300.0, delta=track.step)
        # Freio ja apertado no comeco do trecho (vindo da curva anterior): sem ponto de frenagem.
        self.assertIsNone(ev.braking_point(brake, track, 310.0, 400.0))
        # Freada que comeca exatamente no primeiro ponto da janela conta.
        start = float(track.s[np.flatnonzero(track.s >= 300.0)[0]])      # o primeiro ponto com o freio apertado
        self.assertAlmostEqual(ev.braking_point(brake, track, start, 400.0), start)

    def test_stability_of_adr_0015(self):
        self.assertIsNone(ev.stability([93.0, 92.5])["estabilizou"])
        self.assertTrue(ev.stability([95.0, 92.1, 92.3, 92.4])["estabilizou"])
        self.assertFalse(ev.stability([93.0, 92.4, 91.9])["estabilizou"])

    def test_braking_is_searched_from_the_previous_apex(self):
        """Emenda de 04/10 (pedido 17): a freada que comeca antes do trecho, depois do apice anterior, conta."""
        track = circular_track()
        corners = [Corner(i, a, (a + b) / 2, b, 1, 50.0, 50.0, b - a)
                   for i, (a, b) in enumerate([(100.0, 200.0), (500.0, 600.0), (1000.0, 1100.0)])]
        segments = ev.corner_segments(track, corners)
        self.assertAlmostEqual(segments[1].start_s, 350.0)           # o trecho da curva 2 comeca em 350 m

        def lap_braking_at(start):
            brake = np.zeros(track.size)
            brake[(track.s >= start) & (track.s < 520.0)] = 0.9
            return pd.DataFrame({"elapsed_s": track.s / SPEED, "speed_kmh": np.full(track.size, 144.0),
                                 "lateral": np.zeros(track.size), "brake": brake})

        total = track.length / SPEED
        ref, lap = lap_braking_at(320.0), lap_braking_at(300.0)      # as duas antes do trecho, depois do apice 150
        features = ev.lap_corner_features(lap, total, ref, total, track, segments)
        self.assertTrue(features[1]["ia_freia"])
        self.assertAlmostEqual(features[1]["frenagem_vs_ia_m"], -20.0, delta=track.step)


def load_report_tool():
    import importlib.util

    spec = importlib.util.spec_from_file_location("relatorio_evolucao", BACKEND / "tools" / "relatorio_evolucao.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PanelTest(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace

        self.tool = load_report_tool()
        theta = np.linspace(0.0, 2 * np.pi, 100, endpoint=False)
        self.geometry = SimpleNamespace(x=200.0 * np.cos(theta), z=200.0 * np.sin(theta), length=1256.6)
        self.session = {"formato": "evolucao-sessao/1", "sessao": "2026-10-04", "regras": "texto com </script> dentro",
                        "resumo": {"voltas": 11}, "curvas": [], "voltas": []}
        self.summary = {"formato": "evolucao-resumo/1", "sessoes": [{"sessao": "2026-10-04"}]}

    def panel(self):
        data = self.tool.panel_data(self.summary, [self.session], self.geometry, ["rss_formula_rss_3_v6_2026", None])
        html = self.tool.render_panel(self.tool.PANEL_TEMPLATE.read_text(encoding="utf-8"), data)
        start = html.index('<script type="application/json" id="dados">') + len('<script type="application/json" id="dados">')
        return html, html[start:html.index("</script>", start)]

    def test_the_marker_is_replaced_by_valid_json_with_the_keys(self):
        html, payload = self.panel()
        self.assertNotIn("/*DADOS*/", html)
        data = json.loads(payload)
        self.assertEqual(set(data), {"resumo", "sessoes", "pista", "carro", "pista_nome"})
        self.assertEqual(data["resumo"]["formato"], "evolucao-resumo/1")
        self.assertEqual(list(data["sessoes"]), ["2026-10-04"])
        self.assertEqual(data["sessoes"]["2026-10-04"]["resumo"]["voltas"], 11)
        self.assertEqual(set(data["pista"]), {"x", "z", "ds", "L"})
        self.assertEqual(len(data["pista"]["x"]), 100)
        self.assertAlmostEqual(data["pista"]["ds"], 12.566)
        self.assertEqual(data["carro"], "rss_formula_rss_3_v6_2026")
        self.assertEqual(data["pista_nome"], "Interlagos")

    def test_text_in_the_data_cannot_close_the_script(self):
        html, payload = self.panel()
        self.assertEqual(json.loads(payload)["sessoes"]["2026-10-04"]["regras"], "texto com </script> dentro")
        self.assertEqual(html.count("</script>"), 2)                  # os dois do proprio modelo

    def test_a_template_without_the_marker_stops(self):
        with self.assertRaises(SystemExit):
            self.tool.render_panel("<html></html>", {})


class SessionAnnotationsTest(unittest.TestCase):
    def notes(self, rows):
        return pd.DataFrame(rows, columns=["sessao", "origem", "carModel", "anotado_em", "observacao"])

    def inventory(self):
        return pd.DataFrame({
            "lap_id": ["noite#0000", "noite#0001", "outra#0000"], "session_id": ["noite", "noite", "outra"],
            "origem": ["desconhecida"] * 3, "origem_indicador": ["desconhecida"] * 3, "origem_fonte": [None] * 3,
        })

    def test_every_lap_of_an_annotated_recording_gets_the_annotated_origin(self):
        from ml.data.session_annotations import apply_session_annotations

        inventory = self.inventory()
        inventory.loc[1, "origem_indicador"] = "humano"        # mesmo concordando, a fonte e a anotacao
        notes = self.notes([["noite", "humano", "rss_formula_rss_3_v6_2026", "2026-10-05", ""]])
        out = apply_session_annotations(inventory, notes)
        self.assertEqual(out["origem"].tolist(), ["humano", "humano", "desconhecida"])
        self.assertEqual(out["origem_fonte"].tolist(), ["anotacao_sessao", "anotacao_sessao", None])

    def test_it_stops_when_the_annotation_does_not_match(self):
        from ml.data.session_annotations import check_session_annotations

        notes = self.notes([["sumiu", "humano", "", "2026-10-05", ""], ["noite", "humano", "", "2026-10-05", ""]])
        problems = check_session_annotations(self.inventory(), notes, lap_labelled={"noite"})
        self.assertEqual(len(problems), 2)

    def test_the_annotated_car_fills_the_missing_one_and_never_overrides(self):
        from ml.data.session_annotations import cars_with_annotations

        notes = self.notes([["noite", "humano", "rss_formula_rss_3_v6_2026", "2026-10-05", ""]])
        cars = cars_with_annotations({"noite": None, "tarde": "rss_formula_rss_3_v6_2026"}, notes)
        self.assertEqual(cars, {"noite": "rss_formula_rss_3_v6_2026", "tarde": "rss_formula_rss_3_v6_2026"})
        with self.assertRaises(SystemExit):
            cars_with_annotations({"noite": "outro_carro"}, notes)

    def test_the_versioned_file_names_the_evening_session(self):
        from ml.data.session_annotations import session_annotations

        notes = session_annotations()
        row = notes.set_index("sessao").loc["2026-10-04_23-51-42_vhe_interlagos"]
        self.assertEqual((row["origem"], row["carModel"]), ("humano", "rss_formula_rss_3_v6_2026"))


if __name__ == "__main__":
    unittest.main()
