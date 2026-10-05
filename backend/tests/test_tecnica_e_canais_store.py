"""Pedido 18, Partes C e D: canais fisicos no store v2 e tecnica de pilotagem.

Tudo sintetico, numa pista circular.
"""

from __future__ import annotations

import dataclasses
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
from ml.data.lap_store import StoredLaps  # noqa: E402
from ml.data.recordings import Session  # noqa: E402
from ml.data.store_v2 import PHYSICAL_COLUMNS, build_store_v2  # noqa: E402
from ml.scripts.checar_canais_fisicos import unchanged  # noqa: E402
from ml.track.corners import Corner  # noqa: E402
from test_lap_origin import circular_track  # noqa: E402

SPEED = 40.0
HZ = 60.0


def write_session(directory: Path, track, laps):
    """player.jsonl com voltas (numero, s_inicio, s_fim, com_pneus)."""
    lines = []
    clock = 1_790_000_000.0
    for number, start, end, tyres in laps:
        for value in np.arange(start, end, SPEED / HZ):
            theta = np.mod(value, track.length) / 200.0
            clock += 1.0 / HZ
            physics = {"controls": {"throttle": 1.0, "brake": 0.0, "steerAngle": 0.12}}
            if tyres:
                physics["tyres"] = {"tyreCoreTemperature": [80.0, 81.0, 90.0, 91.0], "wheelLoad": [2000.0] * 4,
                                    "wheelSlip": [0.1] * 4, "tyrePressure": [20.0] * 4}
            lines.append(json.dumps({"timestamp": clock * 1000.0, "track": "vhe_interlagos", "sample": {
                "lap": number, "lap_number": number, "lap_time": float(np.mod(value, track.length) / SPEED),
                "world_x": 200.0 * np.cos(theta), "world_z": 200.0 * np.sin(theta), "speedKmh": SPEED * 3.6,
                "carPhysics": physics,
            }}))
    directory.mkdir(parents=True)
    (directory / "player.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class StoreChannelsTest(unittest.TestCase):
    def build(self):
        track = dataclasses.replace(circular_track(), geometry_id="circulo-1")
        root = Path(tempfile.mkdtemp())
        sid = "2026-10-05_20-00-00_vhe_interlagos"
        L = track.length
        write_session(root / sid, track, [(1, 0.4, L - 0.3, True), (2, L + 0.4, 2 * L - 0.3, False),
                                          (3, 2 * L + 0.4, 2 * L + 50.0, False)])
        inventory = pd.DataFrame({
            "lap_id": [f"{sid}#0000", f"{sid}#0001"], "session_id": sid, "sequence": [0, 1], "valid": True,
            "duplicada_de": [None, None], "geometry_id": track.geometry_id, "origem": "humano",
            "equipamento": "atual", "pasta": "repositorio", "relogio_verificado": True, "relogio_suspeito": False,
        })
        session = Session(session_id=sid, directory=root / sid, track="vhe_interlagos")
        return sid, build_store_v2(inventory, track=track, sessions=[session])

    def test_the_new_columns_exist_and_a_lap_without_the_field_stays_empty(self):
        sid, (store, details) = self.build()
        for column in PHYSICAL_COLUMNS:
            self.assertIn(column, store.frame.columns)
        with_tyres, without = store.lap(f"{sid}#0000"), store.lap(f"{sid}#0001")
        self.assertTrue(np.allclose(with_tyres["tyre_core_temp_rl"], 90.0))
        self.assertTrue(np.isnan(without["tyre_core_temp_rl"]).all())
        self.assertTrue(np.isnan(with_tyres["brake_temp_fl"]).all())        # campo que a gravacao nao tem
        self.assertIn("tyre_core_temp_fl", details.channels_by_lap[f"{sid}#0000"])
        self.assertNotIn("tyre_core_temp_fl", details.channels_by_lap[f"{sid}#0001"])
        self.assertIn("steer_angle", details.channels_by_lap[f"{sid}#0001"])
        self.assertNotIn("yaw_rate", details.channels_by_lap[f"{sid}#0000"])

    def test_the_old_columns_do_not_change(self):
        _, (store, _) = self.build()
        old_columns = [c for c in store.frame.columns if c not in PHYSICAL_COLUMNS]
        base = StoredLaps(frame=store.frame[old_columns].copy(), laps=store.laps.copy(),
                          grid_size=store.grid_size, track_length=store.track_length)
        self.assertTrue(unchanged(store, base)["passou"])
        tampered = store.frame.copy()
        tampered.loc[tampered.index[5], "speed_kmh"] += 0.001
        moved = StoredLaps(frame=tampered, laps=store.laps.copy(), grid_size=store.grid_size,
                           track_length=store.track_length)
        result = unchanged(moved, base)
        self.assertFalse(result["passou"])
        self.assertEqual(result["colunas_mudadas"], ["speed_kmh"])
        fewer = StoredLaps(frame=store.frame[store.frame["lap_id"] != store.lap_ids[0]], laps=store.laps.iloc[1:],
                           grid_size=store.grid_size, track_length=store.track_length)
        self.assertFalse(unchanged(fewer, base)["passou"])


def corners_and_segments(track):
    corners = [Corner(i, a, (a + b) / 2, b, 1, 50.0, 50.0, b - a)
               for i, (a, b) in enumerate([(100.0, 200.0), (500.0, 600.0), (1000.0, 1100.0)])]
    return corners, ev.corner_segments(track, corners)


def lap_frame(track, *, brake_from=None, brake_to=None, steer=None, lat=0.0, lon=0.0):
    brake = np.zeros(track.size)
    if brake_from is not None:
        brake[(track.s >= brake_from) & (track.s < brake_to)] = 0.8
    return pd.DataFrame({
        "brake": brake, "steer_angle": steer if steer is not None else np.zeros(track.size),
        "lateral_g": np.full(track.size, lat), "longitudinal_g": np.full(track.size, lon),
    })


class TechniqueTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.corners, self.segments = corners_and_segments(self.track)

    def test_combined_acceleration(self):
        frame = lap_frame(self.track, lat=1.2, lon=-0.9)
        self.assertAlmostEqual(ev.grip_usage(frame, self.track, self.segments[1]), 1.5, places=6)
        self.assertIsNone(ev.grip_usage(frame.drop(columns=["lateral_g"]), self.track, self.segments[1]))

    def test_brake_and_steer_together(self):
        # Curva 2: apice anterior 150 m, apice 550 m, curva de 500 a 600 m.
        steer = np.zeros(self.track.size)
        steer[(self.track.s >= 480.0) & (self.track.s < 600.0)] = 0.4      # maior volante na curva: 0,4
        steer[(self.track.s >= 470.0) & (self.track.s < 480.0)] = 0.05     # abaixo de 25% de 0,4
        frame = lap_frame(self.track, brake_from=460.0, brake_to=520.0, steer=steer)
        meters = ev.brake_and_steer_m(frame, self.track, self.corners[0].apex_s, self.corners[1])
        self.assertAlmostEqual(meters, 40.0, delta=2 * self.track.step)   # de 480 a 520 m
        self.assertIsNone(ev.brake_and_steer_m(frame.drop(columns=["steer_angle"]), self.track,
                                               self.corners[0].apex_s, self.corners[1]))

    def test_chained_braking_starts_before_or_after_the_previous_apex(self):
        previous_apex, apex = self.corners[0].apex_s, self.corners[1].apex_s     # 150 e 550 m
        chained = lap_frame(self.track, brake_from=120.0, brake_to=520.0)["brake"].to_numpy()
        separate = lap_frame(self.track, brake_from=300.0, brake_to=520.0)["brake"].to_numpy()
        self.assertTrue(ev.chained_braking(chained, self.track, previous_apex, apex))
        self.assertFalse(ev.chained_braking(separate, self.track, previous_apex, apex))
        self.assertIsNone(ev.chained_braking(np.zeros(self.track.size), self.track, previous_apex, apex))

    def test_tyre_temperature_means(self):
        frame = pd.DataFrame({c: np.full(self.track.size, v) for c, v in
                              zip(ev.TYRE_COLUMNS, (80.0, 82.0, 90.0, 92.0))})
        frame.loc[0, "tyre_core_temp_fl"] = 60.0
        temps = ev.tyre_temperatures(frame)
        self.assertEqual(temps["media_s0_c"], 81.0)
        self.assertAlmostEqual(temps["dianteira_c"], 81.0, delta=0.05)     # o ponto em s = 0 pesa pouco
        self.assertEqual(temps["traseira_c"], 91.0)
        self.assertIsNone(ev.tyre_temperatures(frame.drop(columns=["tyre_core_temp_rr"])))

    def test_the_technique_block_does_not_change_the_rest_of_the_report(self):
        from ml.track.microsectors import build_microsectors

        track = self.track
        sectors = build_microsectors(track)
        ref = pd.DataFrame({"elapsed_s": track.s / SPEED, "speed_kmh": np.full(track.size, 144.0),
                            "lateral": np.zeros(track.size), "brake": np.zeros(track.size),
                            "lateral_g": np.ones(track.size), "longitudinal_g": np.zeros(track.size)})
        grids, rows = {}, []
        for i in range(6):
            lap = ref.copy()
            lap["elapsed_s"] = ref["elapsed_s"] * (1.0 + 0.01 * (i + 1))
            lap_id = f"s#{i:04d}"
            grids[lap_id] = lap
            rows.append({"lap_id": lap_id, "session_id": "s", "sequence": i,
                         "lap_time_s": track.length / SPEED * (1.0 + 0.01 * (i + 1))})
        laps = pd.DataFrame(rows)
        total = track.length / SPEED
        before = ev.session_report("2026-10-05", laps, grids, ref, total, track, self.segments, sectors)
        snapshot = json.dumps(before, sort_keys=True)
        block = ev.technique_report(laps, grids, ref, track, self.segments)
        after = ev.session_report("2026-10-05", laps, grids, ref, total, track, self.segments, sectors)
        self.assertEqual(json.dumps(after, sort_keys=True), snapshot)
        self.assertEqual(json.dumps(before, sort_keys=True), snapshot)
        self.assertEqual([c["curva"] for c in block["curvas"]], [c["curva"] for c in after["curvas"]])
        self.assertEqual(block["pneus"]["sem_canal"], 6)                  # sem as colunas de pneu
        self.assertFalse(block["freios"]["canal"])


if __name__ == "__main__":
    unittest.main()
