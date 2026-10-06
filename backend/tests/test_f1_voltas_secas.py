"""Testes da coleta das voltas secas da F1 (pedido 23, Parte B).

Nada aqui usa a internet nem o cache: o FastF1 e um modulo falso, com uma
tabela de voltas montada a mao e dados de posicao que anotam o que foi lido.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.external import f1_dry_laps  # noqa: E402

T = pd.Timedelta


# ------------------------------------------------------------ fakes ---

class RecordingPosition:
    """Dados de posicao falsos que anotam quais colunas foram pedidas."""

    def __init__(self, frame: pd.DataFrame):
        self.frame = frame
        self.requested = []

    def __getitem__(self, key):
        self.requested.append(key)
        return self.frame[key]


POSITIONS = {}


class FakeLap(pd.Series):
    @property
    def _constructor(self):
        return FakeLap

    def get_pos_data(self, **_kwargs):
        return POSITIONS[(self["Driver"], int(self["LapNumber"]))]

    def get_telemetry(self, **_kwargs):
        raise AssertionError("get_telemetry nao pode ser usado")

    def get_car_data(self, **_kwargs):
        raise AssertionError("get_car_data nao pode ser usado")


class FakeLaps(pd.DataFrame):
    @property
    def _constructor(self):
        return FakeLaps

    @property
    def _constructor_sliced(self):
        return FakeLap


def lap_row(driver, number, seconds, start_s, compound="SOFT", accurate=True, deleted=False,
            status="1", pit_in=None, pit_out=None):
    return {
        "Driver": driver,
        "LapNumber": number,
        "LapTime": T(seconds=seconds),
        "Compound": compound,
        "IsAccurate": accurate,
        "Deleted": deleted,
        "TrackStatus": status,
        "PitInTime": pd.NaT if pit_in is None else T(seconds=pit_in),
        "PitOutTime": pd.NaT if pit_out is None else T(seconds=pit_out),
        "LapStartTime": T(seconds=start_s),
        "Time": T(seconds=start_s + seconds),
    }


def weather_frame(rain_between=None):
    """Um registro por minuto, de 0 a 30 min; chuva so dentro de `rain_between` (s)."""
    times = np.arange(0, 1800, 60)
    rain = np.zeros(len(times), dtype=bool)
    if rain_between is not None:
        rain = (times >= rain_between[0]) & (times <= rain_between[1])
    return pd.DataFrame({"Time": pd.to_timedelta(times, unit="s"), "Rainfall": rain})


def case_laps():
    """Uma volta de cada caso do funil, mais a volta limpa."""
    rows = [
        lap_row("INT", 1, 80.0, 100.0, compound="INTERMEDIATE"),
        lap_row("IMP", 1, 80.0, 100.0, accurate=False),
        lap_row("DEL", 1, 80.0, 100.0, deleted=True),
        lap_row("YEL", 1, 80.0, 100.0, status="12"),
        lap_row("BOX", 1, 80.0, 100.0, pit_out=95.0),
        lap_row("RAI", 1, 80.0, 1000.0),
        lap_row("OK", 1, 80.0, 100.0),
    ]
    return pd.DataFrame(rows)


class FakeSession:
    def __init__(self, laps, weather):
        self._laps = laps
        self.weather_data = weather
        self.pos_data = {"ok": True}
        self.race_control_messages = pd.DataFrame({"Message": ["GREEN LIGHT - PIT EXIT OPEN"]})
        self.date = pd.Timestamp("2023-11-03 18:00")
        self.api_path = "/static/fake/"
        self.loaded_with = None

    def load(self, **kwargs):
        self.loaded_with = kwargs

    @property
    def laps(self):
        return self._laps


class FakeEvent(dict):
    def __init__(self, sessions, session_obj=None):
        super().__init__({"EventName": "Fake Grand Prix"})
        for i, (name, date) in enumerate(sessions, start=1):
            self[f"Session{i}"] = name
            self[f"Session{i}Date"] = pd.Timestamp(date)
        self.session_obj = session_obj

    def get_session(self, _name):
        return self.session_obj


class FakeFastF1:
    def __init__(self, event):
        self.event = event

    def get_event(self, _year, _gp):
        return self.event


# ------------------------------------------------------------ filtros ---

class FunnelTest(unittest.TestCase):
    def test_only_the_clean_lap_survives_each_case_falls_in_its_stage(self):
        laps = case_laps()
        stages = f1_dry_laps.funnel(laps, weather_frame(rain_between=(1020, 1080)))
        by_driver = dict(zip(laps["Driver"], stages["etapa"]))
        self.assertEqual(by_driver, {
            "INT": "composto", "IMP": "imprecisa", "DEL": "apagada", "YEL": "bandeira",
            "BOX": "box", "RAI": "chuva", "OK": "passou",
        })
        counts = f1_dry_laps.funnel_counts(stages["etapa"].tolist(), len(laps))
        self.assertEqual(counts["restam_depois_chuva"], 1)
        self.assertEqual(counts["caem_composto"], 1)

    def test_the_first_failing_stage_wins(self):
        # Intermediario e apagado: cai no composto, que vem antes.
        laps = pd.DataFrame([lap_row("X", 1, 80.0, 100.0, compound="WET", deleted=True)])
        self.assertEqual(f1_dry_laps.funnel(laps, weather_frame())["etapa"].iloc[0], "composto")

    def test_lap_without_interval_cannot_be_checked_for_rain(self):
        laps = pd.DataFrame([lap_row("X", 1, 80.0, 100.0)])
        laps["LapStartTime"] = pd.Series([pd.NaT], dtype="timedelta64[ns]")
        stages = f1_dry_laps.funnel(laps, weather_frame())
        self.assertEqual(stages["etapa"].iloc[0], "chuva")
        self.assertEqual(stages["registros_de_tempo"].iloc[0], -1)

    def test_best_lap_per_driver_and_top_ten(self):
        rows = []
        for d in range(12):
            for n, extra in enumerate((0.5, 0.0, 0.9), start=1):
                rows.append(lap_row(f"D{d:02d}", n, 80.0 + d * 0.1 + extra, 100.0 * n))
        passed = pd.DataFrame(rows)
        chosen, not_best, beyond = f1_dry_laps.pick_laps(passed)
        picked = passed.loc[chosen]
        self.assertEqual(len(chosen), 10)
        self.assertEqual(list(picked["Driver"]), [f"D{d:02d}" for d in range(10)])
        self.assertTrue((picked["LapNumber"] == 2).all())
        self.assertEqual(sorted(passed.loc[beyond, "Driver"]), ["D10", "D11"])
        self.assertEqual(len(not_best), 24)

    def test_session_without_deleted_information_is_left_out(self):
        laps = case_laps().drop(columns=["Deleted"])
        self.assertFalse(f1_dry_laps.has_deleted_info(laps))
        incomplete = case_laps().astype({"Deleted": object})
        incomplete.loc[0, "Deleted"] = None
        self.assertFalse(f1_dry_laps.has_deleted_info(incomplete))
        self.assertTrue(f1_dry_laps.has_deleted_info(case_laps()))

        session = FakeSession(FakeLaps(laps), weather_frame())
        event = FakeEvent([("Qualifying", "2023-11-03 15:00")], session)
        data = f1_dry_laps.collect_session(FakeFastF1(event), 2023, "Qualifying", "Q")
        self.assertTrue(data.info["carregou"])
        self.assertIn("Deleted", data.info["fora"])
        self.assertEqual(data.laps, [])
        self.assertEqual(data.xy, {})


class SessionChoiceTest(unittest.TestCase):
    def test_sprint_qualifying_must_come_before_the_sprint_race(self):
        y2021 = FakeEvent([("Practice 1", "2021-11-12 12:30"), ("Qualifying", "2021-11-12 16:00"),
                           ("Practice 2", "2021-11-13 12:00"), ("Sprint Qualifying", "2021-11-13 16:30"),
                           ("Race", "2021-11-14 14:00")])
        chosen, skipped = f1_dry_laps.choose_sessions(y2021)
        self.assertEqual([row["nome"] for row in chosen], ["Qualifying"])
        self.assertEqual([row["nome"] for row in skipped], ["Sprint Qualifying"])

        y2023 = FakeEvent([("Practice 1", "2023-11-03 11:30"), ("Qualifying", "2023-11-03 15:00"),
                           ("Sprint Shootout", "2023-11-04 11:00"), ("Sprint", "2023-11-04 15:30"),
                           ("Race", "2023-11-05 14:00")])
        chosen, skipped = f1_dry_laps.choose_sessions(y2023)
        self.assertEqual([(row["nome"], row["tipo"]) for row in chosen],
                         [("Qualifying", "Q"), ("Sprint Shootout", "SQ")])
        self.assertEqual([row["nome"] for row in skipped], ["Sprint"])


# ------------------------------------------------------------ leitura ---

class ReadingTest(unittest.TestCase):
    def setUp(self):
        POSITIONS.clear()

    def _position(self, n=40):
        frame = pd.DataFrame({
            "X": np.arange(n, dtype=float), "Y": np.arange(n, dtype=float) * 2.0,
            "Z": np.ones(n), "Status": ["OnTrack"] * n, "Speed": np.full(n, 300.0),
            "Throttle": np.full(n, 100.0), "Distance": np.arange(n) * 10.0,
        })
        return RecordingPosition(frame)

    def test_reads_only_x_and_y_of_the_position_data(self):
        position = self._position()
        POSITIONS[("OK", 1)] = position
        lap = FakeLap(lap_row("OK", 1, 80.0, 100.0))
        xy, dropped = f1_dry_laps.read_xy(lap)
        self.assertEqual(position.requested, [["X", "Y"]])
        self.assertEqual(xy.shape, (40, 2))
        np.testing.assert_allclose(xy[:, 1], 2.0 * xy[:, 0])
        self.assertEqual(dropped, 0)

    def test_session_reads_xy_only_of_the_chosen_laps(self):
        for driver in ("INT", "IMP", "DEL", "YEL", "BOX", "RAI", "OK"):
            POSITIONS[(driver, 1)] = self._position()
        session = FakeSession(FakeLaps(case_laps()), weather_frame(rain_between=(1020, 1080)))
        event = FakeEvent([("Qualifying", "2023-11-03 15:00")], session)
        data = f1_dry_laps.collect_session(FakeFastF1(event), 2023, "Qualifying", "Q",
                                           extra_laps=[("INT", 1)])
        self.assertEqual(session.loaded_with, f1_dry_laps.LOAD_KWARGS)
        self.assertEqual(sorted(data.xy), ["2023_Q_INT_1", "2023_Q_OK_1"])
        for driver in ("IMP", "DEL", "YEL", "BOX", "RAI"):
            self.assertEqual(POSITIONS[(driver, 1)].requested, [])
        stages = {row["piloto"]: row["etapa"] for row in data.laps}
        self.assertEqual(stages["OK"], "escolhida")
        self.assertEqual(stages["INT"], "composto")
        extra = next(row for row in data.laps if row["piloto"] == "INT")
        self.assertIn("chuva", extra["a_parte"])
        self.assertEqual(data.info["funil"]["escolhidas"], 1)

    def test_session_that_does_not_load_records_the_error(self):
        class Broken(FakeSession):
            def load(self, **_kwargs):
                raise RuntimeError("sem rede")

        event = FakeEvent([("Qualifying", "2023-11-03 15:00")], Broken(FakeLaps(case_laps()), weather_frame()))
        data = f1_dry_laps.collect_session(FakeFastF1(event), 2023, "Qualifying", "Q")
        self.assertFalse(data.info["carregou"])
        self.assertIn("sem rede", data.info["erro"])



if __name__ == "__main__":
    unittest.main()
