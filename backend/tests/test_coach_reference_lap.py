"""Coach contra a volta de referencia (ADR 0012).

O modo padrao mede cada microsetor contra uma volta real e completa do piloto
-- por padrao a melhor valida -- e diz a diferenca medida, nunca um ganho
prometido nem uma "volta ideal". O modo antigo continua disponivel quando ligado.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.reference_model import (  # noqa: E402
    MODE_BEST_PER_MICROSECTOR,
    MODE_REFERENCE_LAP,
    DriverReferenceModel,
    build_reference_model,
    microsector_splits,
)
from core.live.driving_coach import LiveDrivingCoach, coach_recorded_lap  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402
from tests.test_driving_coach import FakeBus, drive  # noqa: E402

HZ = 57.0
TRACK_M = 4300.0


def lap(seconds: float, *, slow=None, missing=None, brake_at=None, min_speed=None):
    """Volta sintetica com tempo, progresso, `s`, freio e velocidade.

    `slow=(indice, segundos)` atrasa um microsetor; `missing=(p0, p1)` apaga um
    trecho (volta incompleta); `brake_at=p` pisa no freio no microsetor de `p`.
    """
    count = int(seconds * HZ)
    progress = np.linspace(0.0, 1.0, count)
    elapsed = progress * seconds
    if slow is not None:
        index, extra = slow
        start, end = index / 60.0, (index + 1) / 60.0
        elapsed = elapsed + np.where(progress >= end, extra, np.where(progress >= start, extra * (progress - start) / (end - start), 0.0))
    speed = np.full(count, 180.0)
    brake = np.zeros(count)
    if brake_at is not None:
        zone = (progress >= brake_at) & (progress < brake_at + 0.005)
        brake[zone] = 0.9
        speed[zone] = min_speed or 95.0
    frame = pd.DataFrame(
        {"p": progress, "s": progress * TRACK_M, "elapsed_s": elapsed, "speed_kmh": speed, "brake": brake, "throttle": 1.0 - brake}
    )
    if missing is not None:
        frame = frame[(frame["p"] < missing[0]) | (frame["p"] > missing[1])].reset_index(drop=True)
    return frame


def entry(lap_id, seconds, frame, hz=HZ):
    total = float(frame["elapsed_s"].iloc[-1] - frame["elapsed_s"].iloc[0])
    return (lap_id, seconds, int(seconds * hz), frame)


class ReferenceSelectionTest(unittest.TestCase):
    def test_picks_the_best_valid_complete_lap(self):
        laps = [
            entry("lenta", 86.0, lap(86.0)),
            entry("referencia", 85.0, lap(85.0)),
            # Mais rapida, mas com um buraco de 6 microsetores: valida para o
            # modelo (cobertura >= 90 %), nao para referencia (incompleta).
            entry("incompleta", 84.5, lap(84.5, missing=(0.30, 0.40))),
            # Mais rapida ainda, mas gravada a 13 Hz: nem entra no modelo.
            ("rala", 84.0, int(84.0 * 13), lap(84.0)),
        ]
        model = build_reference_model(laps, track="t")
        self.assertEqual(model.mode, MODE_REFERENCE_LAP)
        self.assertEqual(model.reference_lap_id, "referencia")
        self.assertAlmostEqual(model.reference_lap_seconds, 85.0)
        self.assertTrue(model.has_reference)
        self.assertTrue(all(t.reference_seconds is not None for t in model.targets))
        # O melhor de todos por microsetor continua medido (o limiar usa ele).
        self.assertLess(min(t.best_seconds for t in model.targets[20:30]), model.targets[25].reference_seconds)

    def test_another_lap_can_be_chosen_by_lap_id(self):
        laps = [entry("a", 85.0, lap(85.0)), entry("b", 85.6, lap(85.6))]
        model = build_reference_model(laps, track="t", reference_lap_id="b")
        self.assertEqual(model.reference_lap_id, "b")
        with self.assertRaises(ValueError):
            build_reference_model(laps + [entry("c", 84.0, lap(84.0, missing=(0.3, 0.4)))], track="t", reference_lap_id="c")
        with self.assertRaises(ValueError):
            build_reference_model(laps, track="t", reference_lap_id="nao-existe")

    def test_the_reference_keeps_where_it_braked_and_how_slow_it_went(self):
        model = build_reference_model([entry("r", 85.0, lap(85.0, brake_at=0.4501, min_speed=92.0))], track="t")
        target = model.targets[27]                       # 0,45 a 0,4667
        self.assertAlmostEqual(target.reference_min_speed_kmh, 92.0)
        self.assertAlmostEqual(target.reference_brake_point_m, 0.4501 * TRACK_M, delta=5.0)
        self.assertIsNotNone(target.reference_brake_point_p)


class DifferenceAddsUpTest(unittest.TestCase):
    def test_microsector_differences_add_up_to_the_lap_difference(self):
        model = build_reference_model([entry("ref", 85.0, lap(85.0))], track="t")
        for observed in (lap(86.2), lap(85.0, slow=(22, 0.7)), lap(84.4)):
            splits = microsector_splits(observed, model.microsectors)
            differences = model.loss_against_reference(splits)
            lap_delta = float(observed["elapsed_s"].iloc[-1]) - 85.0
            self.assertTrue(all(d is not None for d in differences))
            # Tolerancia de interpolacao: as pontas da volta sao extrapoladas.
            self.assertAlmostEqual(sum(differences), lap_delta, delta=0.02)


class CoachWordsTest(unittest.TestCase):
    def setUp(self):
        # A segunda volta perde 0,2 s no microsetor 22: ele entra no foco (pedido 15).
        self.model = build_reference_model(
            [entry("ref", 85.0, lap(85.0, brake_at=0.3667, min_speed=110.0)), entry("x", 85.6, lap(85.4, slow=(22, 0.2)))],
            track="vhe_interlagos",
        )
        self.bus = FakeBus()
        self.coach = LiveDrivingCoach(self.bus, lambda _t: self.model, min_gap_seconds=0.0)

    def phrases(self):
        return [e for e in self.bus.of(COACHING_EVENT) if e.get("type") != "coaching_focus"]

    def said(self):
        return [e["event"] for e in self.bus.of(COACHING_EVENT)] + [m["message"] for m in self.bus.of(ENGINEER_SPEECH)]

    def test_new_phrases_state_a_measured_difference(self):
        drive(self.coach, seconds=85.0, lap=5, slow_slice=(22, 0.6))
        drive(self.coach, seconds=85.0, lap=6)
        said = self.said()
        self.assertTrue(said)
        for text in said:
            lowered = text.lower()
            self.assertNotIn("ganh", lowered)          # ganhar, ganho
            self.assertNotIn("ideal", lowered)
            self.assertNotIn("otimo", lowered)
        event = self.phrases()[0]
        self.assertIn("atras da sua volta de referencia neste trecho", event["event"])
        self.assertEqual(event["evidence"]["referenceLapId"], "ref")
        self.assertIn("referenceSeconds", event["evidence"])
        self.assertNotIn("bestSeconds", event["evidence"])
        # ADR 0016: o fim da volta lista os trechos de maior diferenca e nomeia a referencia.
        summary = self.bus.of(ENGINEER_SPEECH)[0]["message"]
        self.assertIn("Maiores diferencas para a sua volta de referencia: setor 22", summary)
        self.assertIn("Sua volta de referencia: 85.00s", summary)

    def test_the_reference_braking_is_said_relative_to_the_driver(self):
        """ADR 0016: a freada aparece em relacao a referencia, nao como posicao absoluta."""
        driven = lap(85.0, slow=(22, 0.6), brake_at=0.3640, min_speed=100.0)
        for number, frame in ((5, driven), (6, lap(85.0))):
            for row in frame.itertuples():
                self.coach.on_frame({"p": row.p, "s": row.s, "lap_time": row.elapsed_s, "lap_number": number,
                                     "speedKmh": row.speed_kmh, "brake": row.brake, "track": "vhe_interlagos"})
        event = self.phrases()[0]
        self.assertNotIn("freada em", event["event"])
        self.assertIn("A referencia freia", event["event"])
        self.assertIn("depois de voce", event["event"])
        self.assertIn("minima na referencia 110 km/h, a sua 100 km/h", event["event"])

    def test_threshold_is_unchanged(self):
        # Mesmo limiar nos dois modos: 2 x (mediana - melhor) do microsetor.
        legacy = build_reference_model(
            [entry("ref", 85.0, lap(85.0)), entry("x", 85.6, lap(85.4, slow=(22, 0.2)))], track="t",
            mode=MODE_BEST_PER_MICROSECTOR,
        )
        target_new, target_old = self.model.targets[22], legacy.targets[22]
        self.assertAlmostEqual(self.coach._threshold_for(target_new), self.coach._threshold_for(target_old))  # noqa: SLF001

    def test_an_old_model_file_loads_and_the_coach_stays_quiet(self):
        payload = self.model.to_dict()
        for key in ("mode", "reference_lap_id", "reference_lap_seconds"):
            payload.pop(key)
        for target in payload["targets"]:
            for key in [k for k in target if k.startswith("reference_")]:
                target.pop(key)
        path = Path(tempfile.mkdtemp()) / "antigo.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        old = DriverReferenceModel.load(path)
        self.assertIsNotNone(old)
        self.assertFalse(old.has_reference)
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: old, min_gap_seconds=0.0)
        drive(coach, seconds=85.0, lap=5, slow_slice=(22, 0.9))
        drive(coach, seconds=85.0, lap=6)
        self.assertEqual(bus.published, [])

    def test_a_newer_file_with_unknown_fields_still_loads(self):
        payload = self.model.to_dict()
        payload["targets"][0]["campo_do_futuro"] = 1
        path = Path(tempfile.mkdtemp()) / "novo.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(DriverReferenceModel.load(path).has_reference)


class LegacyModeTest(unittest.TestCase):
    def test_the_old_mode_still_works_when_switched_on(self):
        model = build_reference_model(
            [entry("ref", 85.0, lap(85.0)), entry("x", 85.4, lap(85.4))], track="t", mode=MODE_BEST_PER_MICROSECTOR
        )
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: model, min_gap_seconds=0.0)
        drive(coach, seconds=85.0, lap=5, slow_slice=(22, 0.6))
        drive(coach, seconds=85.0, lap=6)
        self.assertIn("atras do seu melhor", bus.of(COACHING_EVENT)[0]["event"])
        self.assertIn("ideal", bus.of(ENGINEER_SPEECH)[0]["message"].lower())

    def test_the_mode_survives_a_save_and_load(self):
        model = build_reference_model([entry("ref", 85.0, lap(85.0))], track="t", mode=MODE_BEST_PER_MICROSECTOR)
        path = Path(tempfile.mkdtemp()) / "m.json"
        model.save(path)
        self.assertEqual(DriverReferenceModel.load(path).mode, MODE_BEST_PER_MICROSECTOR)

    def test_recorded_lap_replay_uses_the_same_rules(self):
        model = build_reference_model([entry("ref", 85.0, lap(85.0)), entry("x", 85.2, lap(85.0, slow=(22, 0.2)))],
                                      track="t")
        frame = lap(85.0, slow=(22, 0.6))
        frame["speed_kmh"] = 180.0
        result = coach_recorded_lap(frame, model, lap_number=3, track="t")
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["events"])
        self.assertIn("volta de referencia", result["events"][0]["event"])


if __name__ == "__main__":
    unittest.main()
