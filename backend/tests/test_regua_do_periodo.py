"""Pedido 34: a regua da checagem do periodo e a checagem da linha do jogo.

O periodo vai de s = 0 a s = 0 da geometria; o tempo do jogo, de linha do jogo a
linha do jogo, uns metros depois. A checagem leva o tempo do jogo ao s = 0 com a
travessia dessa distancia nas duas pontas. Tudo sintetico, numa pista circular,
com o caminho inteiro do store v2 (gravacao -> corte -> alinhamento -> grade).
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

from ml.data import store_checks  # noqa: E402
from ml.data.recordings import Session  # noqa: E402
from ml.data.store_v2 import build_store_v2, game_line_position, line_speeds  # noqa: E402
from test_lap_origin import circular_track  # noqa: E402

HZ = 60.0
LINE_M = 1.463          # a linha do jogo, depois do s = 0
SESSION = "2026-10-18_20-00-00_vhe_interlagos"


class Motion:
    """O carro numa velocidade, depois uma rampa de `ramp_s` segundos ate outra, a partir de `ramp_at_m`."""

    def __init__(self, start_m, v1, v2, ramp_at_m, ramp_s=4.0):
        self.start, self.v1, self.v2 = start_m, v1, v2
        self.t1 = (ramp_at_m - start_m) / v1
        self.ramp = ramp_s
        self.a = (v2 - v1) / ramp_s
        self.u1 = ramp_at_m
        self.u2 = ramp_at_m + v1 * ramp_s + 0.5 * self.a * ramp_s ** 2

    def position(self, t):
        if t <= self.t1:
            return self.start + self.v1 * t
        if t <= self.t1 + self.ramp:
            tau = t - self.t1
            return self.u1 + self.v1 * tau + 0.5 * self.a * tau ** 2
        return self.u2 + self.v2 * (t - self.t1 - self.ramp)

    def speed(self, t):
        if t <= self.t1:
            return self.v1
        if t <= self.t1 + self.ramp:
            return self.v1 + self.a * (t - self.t1)
        return self.v2

    def time_at(self, u):
        """O instante exato em que o carro passa por `u` (o movimento e monotono)."""
        low, high = 0.0, 1e5
        for _ in range(200):
            mid = 0.5 * (low + high)
            if self.position(mid) < u:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)


def write_session(directory: Path, track, motion: Motion, end_m: float, line_m: float = LINE_M,
                  phase_s: float = 0.0):
    """Amostras a 60 Hz; o cronometro do jogo zera e o contador sobe quando o carro passa pela linha do jogo."""
    L = track.length
    lines = []
    clock = 1_790_000_000.0
    t = phase_s
    while True:
        u = motion.position(t)
        if u >= end_m:
            break
        laps_done = int(np.floor((u - line_m) / L))          # linhas do jogo ja cruzadas
        # A primeira volta da gravacao comecou antes dela: o cronometro ja vinha contando.
        line_time = motion.time_at(laps_done * L + line_m) if laps_done >= 1 else -30.0
        theta = np.mod(u, L) / 200.0
        lines.append(json.dumps({"timestamp": (clock + t) * 1000.0, "track": "vhe_interlagos", "sample": {
            "lap": laps_done + 1, "lap_number": laps_done + 1, "lap_time": float(t - line_time),
            "world_x": 200.0 * np.cos(theta), "world_z": 200.0 * np.sin(theta),
            "speedKmh": motion.speed(t) * 3.6,
            "carPhysics": {"controls": {"throttle": 1.0, "brake": 0.0}},
        }}))
        t += 1.0 / HZ
    directory.mkdir(parents=True)
    (directory / "player.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(track, motion, end_m, *, phase_s=0.0, sequences=(0, 1)):
    root = Path(tempfile.mkdtemp())
    write_session(root / SESSION, track, motion, end_m, phase_s=phase_s)
    inventory = pd.DataFrame({
        "lap_id": [f"{SESSION}#{i:04d}" for i in sequences], "session_id": SESSION, "sequence": list(sequences),
        "valid": True, "duplicada_de": None, "geometry_id": track.geometry_id,
        "origem": "humano", "equipamento": "atual", "pasta": "repositorio",
        "relogio_verificado": True, "relogio_suspeito": False,
    })
    session = Session(session_id=SESSION, directory=root / SESSION, track="vhe_interlagos")
    store, _ = build_store_v2(inventory, track=track, sessions=[session])
    return store.laps.set_index("lap_id")


class SpeedAtTheLineTest(unittest.TestCase):
    """A diferenca da regua antiga e a travessia dos 1,463 m; a regua nova a tira."""

    def setUp(self):
        import dataclasses

        self.track = dataclasses.replace(circular_track(), geometry_id="circulo-34")
        self.L = self.track.length

    def check_lap(self, v_start, v_end):
        L = self.L
        start = LINE_M + 0.5
        # A volta 1 vai do s = 0 em L ao s = 0 em 2L: passa a v_start no comeco e a
        # v_end no fim; a rampa fica no meio dela, longe das duas linhas.
        motion = Motion(start, v_start, v_end, ramp_at_m=1.3 * L)
        laps = build(self.track, motion, end_m=2 * L + LINE_M + 80.0)
        lap = laps.loc[f"{SESSION}#0001"]
        true_period = motion.time_at(2 * L) - motion.time_at(L)
        true_game = motion.time_at(2 * L + LINE_M) - motion.time_at(L + LINE_M)

        self.assertAlmostEqual(lap["lap_time_s"], true_period, delta=0.001)
        self.assertAlmostEqual(lap["tempo_jogo_s"], true_game, delta=0.001)
        self.assertAlmostEqual(lap["linha_do_jogo_m"], LINE_M, delta=0.02)
        self.assertAlmostEqual(lap["v_linha_inicio_kmh"], v_start * 3.6, delta=0.5)
        self.assertAlmostEqual(lap["v_linha_fim_kmh"], v_end * 3.6, delta=0.5)

        # A regua antiga ve a travessia; a nova, nao.
        expected_ms = 1000.0 * LINE_M * (1.0 / v_start - 1.0 / v_end)
        raw = store_checks.raw_period_differences_ms(laps.reset_index())[f"{SESSION}#0001"]
        self.assertAlmostEqual(raw, expected_ms, delta=1.0)
        self.assertGreater(abs(raw), store_checks.PERIOD_LIMIT_MS)
        new = store_checks.period_differences_ms(laps.reset_index())[f"{SESSION}#0001"]
        self.assertLess(abs(new), 1.0)
        return raw, new

    def test_a_lap_that_starts_slow_and_ends_fast(self):
        raw, _ = self.check_lap(30.0, 75.0)            # 108 e 270 km/h: a regua antiga da +29 ms
        self.assertGreater(raw, 0)

    def test_a_lap_that_starts_fast_and_ends_slow(self):
        raw, _ = self.check_lap(75.0, 30.0)
        self.assertLess(raw, 0)

    def test_the_check_passes_with_the_new_ruler_and_failed_with_the_old(self):
        L = self.L
        motion = Motion(LINE_M + 0.5, 30.0, 75.0, ramp_at_m=1.3 * L)
        laps = build(self.track, motion, end_m=2 * L + LINE_M + 80.0).reset_index()
        laps = laps[laps["lap_id"] == f"{SESSION}#0001"]       # a primeira volta da gravacao nao fecha no jogo
        check = store_checks.check_period(laps)
        self.assertTrue(check["passou"])
        self.assertAlmostEqual(check["linha_do_jogo_m"], LINE_M, delta=0.02)
        self.assertEqual(check["regua_antiga (informativo)"]["acima_do_limite"], 1)
        self.assertEqual(check["acima_do_limite"], [])


class PassageBetweenSamplesTest(unittest.TestCase):
    """A passagem pela linha cai entre duas amostras: a medida e a regua continuam certas."""

    def setUp(self):
        import dataclasses

        self.track = dataclasses.replace(circular_track(), geometry_id="circulo-34")

    def test_the_line_and_the_period_with_the_passage_between_two_samples(self):
        L = self.track.length
        speed = 70.0                                    # 1,17 m entre amostras a 60 Hz
        for phase in (0.0, 0.004, 0.009, 0.013):        # a fase das amostras em relacao as linhas
            motion = Motion(LINE_M + 0.3, speed, speed, ramp_at_m=10 * L)
            laps = build(self.track, motion, end_m=2 * L + LINE_M + 60.0, phase_s=phase)
            lap = laps.loc[f"{SESSION}#0001"]
            self.assertAlmostEqual(lap["linha_do_jogo_m"], LINE_M, delta=0.02, msg=f"fase {phase}")
            self.assertAlmostEqual(lap["lap_time_s"], L / speed, delta=0.0005, msg=f"fase {phase}")
            self.assertAlmostEqual(lap["tempo_jogo_s"], L / speed, delta=0.0005, msg=f"fase {phase}")
            diff = store_checks.period_differences_ms(laps.reset_index())[f"{SESSION}#0001"]
            self.assertLess(abs(diff), 0.5, msg=f"fase {phase}")

    def test_the_line_measure_needs_the_first_samples_moving(self):
        L = self.track.length
        frame = pd.DataFrame({"s": [2.0, 3.0, 4.0], "speed_kmh": [50.0, 50.0, 50.0],
                              "lap_time_s": [0.04, 0.11, 0.18], "s_unwrapped": [2.0, 3.0, 4.0]})
        self.assertIsNone(game_line_position(frame, L))          # devagar demais para a conta
        moving = frame.assign(speed_kmh=250.0, lap_time_s=[0.0078, 0.0222, 0.0366])
        self.assertAlmostEqual(game_line_position(moving, L), 1.458, delta=0.01)
        start, end = line_speeds(moving, L)
        self.assertEqual((start, end), (250.0, None))            # o fim da volta nao esta no quadro


class GameLineCheckTest(unittest.TestCase):
    def laps(self, values):
        rows = []
        for session, measures in values.items():
            for i, value in enumerate(measures):
                rows.append({"lap_id": f"{session}#{i:04d}", "session_id": session, "linha_do_jogo_m": value})
        return pd.DataFrame(rows)

    def test_it_passes_near_the_registered_line(self):
        check = store_checks.check_game_line(self.laps({
            "s1": [1.44, 1.46, 1.47, 1.45], "s2": [1.50, 1.49, 1.52], "s3": [1.40, None]}))
        self.assertTrue(check["passou"], check["motivos"])
        self.assertEqual(check["sessoes_sem_veredito"], ["s3"])         # menos de 3 voltas medidas
        self.assertAlmostEqual(check["medida_m"], 1.46, delta=0.01)

    def test_it_fails_with_the_reason_when_the_line_moves(self):
        check = store_checks.check_game_line(self.laps({
            "s1": [1.44, 1.46, 1.47], "nova": [3.10, 3.12, 3.09, 3.11]}))
        self.assertFalse(check["passou"])
        self.assertTrue(check["motivos"][0].startswith("nova:"), check["motivos"])
        self.assertIn("geometria oficial ou a linha do jogo mudaram", check["motivos"][0])
        self.assertTrue(check["sessoes"]["s1"]["dentro"])
        self.assertFalse(check["sessoes"]["nova"]["dentro"])

    def test_it_fails_without_any_measure(self):
        check = store_checks.check_game_line(self.laps({"s1": [None, None, None]}))
        self.assertFalse(check["passou"])
        self.assertIn("nenhuma volta", check["motivos"][0])

    def test_the_period_check_needs_the_speeds_at_the_line(self):
        laps = pd.DataFrame({"lap_id": ["a", "b"], "lap_time_s": [85.0, 86.0], "tempo_jogo_s": [85.0, 86.0],
                             "linha_do_jogo_m": 1.463, "v_linha_inicio_kmh": [250.0, None],
                             "v_linha_fim_kmh": [250.0, 250.0]})
        check = store_checks.check_period(laps)
        self.assertEqual((check["voltas_medidas"], check["voltas_sem_velocidade_na_linha"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
