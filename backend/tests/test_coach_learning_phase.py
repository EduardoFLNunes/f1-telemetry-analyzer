"""Coach na fase de aprendizado (pedido 14): continuidade rigida, linha de chegada.

Tudo sintetico.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.reference_model import build_reference_model, microsector_splits  # noqa: E402
from core.live.driving_coach import LiveDrivingCoach  # noqa: E402
from core.spatial_engine import CanonicalTrackSpace, MapMatchingEngine  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402
from tests.test_coach_official_geometry import HZ, exported, lap_on, paperclip  # noqa: E402
from tests.test_driving_coach import FakeBus  # noqa: E402
from tests.test_ml_pipeline import circular_track  # noqa: E402

SPEED_MPS = 150.0 / 3.6


def phrases_of(bus):
    """As frases de trecho, sem as linhas de foco (pedido 15)."""
    return [e for e in bus.of(COACHING_EVENT) if e.get("type") != "coaching_focus"]


class HardContinuityTest(unittest.TestCase):
    def test_the_map_engine_keeps_its_default(self):
        """Mapa e painel: a continuidade continua sendo so uma penalidade."""
        track = circular_track()
        engine = MapMatchingEngine(CanonicalTrackSpace(track.x, track.z))
        self.assertIsNone(engine.max_advance_factor)

    def test_the_coach_turns_it_on(self):
        projector = exported(circular_track()).projector()
        self.assertIsNotNone(projector.engine.max_advance_factor)

    def test_one_sample_on_the_other_straight_does_not_jump(self):
        """Uma amostra isolada em cima da outra reta: o mapa salta, o coach nao."""
        track = paperclip(gap=10.0)
        geometry = exported(track)
        s_true = np.arange(100.0, 300.0, SPEED_MPS / HZ)
        world = track.to_world(s_true, np.zeros(s_true.size))
        outlier = len(s_true) // 2
        straight, arc = 400.0, math.pi * 5.0
        other = track.to_world(np.array([2 * straight + arc - s_true[outlier]]), np.zeros(1))[0]
        world[outlier] = other                              # mesmo x, na reta de cima

        coach = geometry.projector()
        plain = MapMatchingEngine(CanonicalTrackSpace(geometry.x, geometry.z))
        coach_s, plain_s = [], []
        for x, z in world:
            coach_s.append(coach.project(x, z, speed_mps=SPEED_MPS, dt_s=1.0 / HZ)[0])
            plain_s.append(plain.project(float(x), float(z), velocity=1e6)["s"] * coach.scale)
        self.assertGreater(abs(plain_s[outlier] - s_true[outlier]), 100.0)
        self.assertLess(abs(coach_s[outlier] - s_true[outlier]), 7.0)
        np.testing.assert_allclose(np.delete(coach_s, outlier), np.delete(s_true, outlier), atol=0.2)

    def test_a_recording_gap_does_not_leave_the_projection_behind(self):
        """Medido em 04/10: 357 ms sem amostras a 248 km/h, 24 m de uma vez. O limite deixa
        passar, e dentro dele vale o trecho mais perto, sem a penalidade antiga."""
        track = circular_track()
        projector = exported(track).projector()
        speed = 248.0 / 3.6
        for s in np.arange(100.0, 140.0, speed / HZ):
            x, z = track.to_world(np.array([s]), np.zeros(1))[0]
            projector.project(x, z, speed_mps=speed, dt_s=1.0 / HZ)
        target = s + speed * 0.357
        x, z = track.to_world(np.array([target]), np.zeros(1))[0]
        got, _ = projector.project(x, z, speed_mps=speed, dt_s=0.357)
        self.assertAlmostEqual(got, target, delta=0.1)

    def test_a_real_move_is_followed(self):
        """Voltar ao box pelo menu leva o carro para longe: a projecao acompanha."""
        track = circular_track()
        projector = exported(track).projector()
        for s in (100.0, 101.0, 102.0):
            x, z = track.to_world(np.array([s]), np.zeros(1))[0]
            projector.project(x, z, speed_mps=SPEED_MPS, dt_s=1.0 / HZ)
        x, z = track.to_world(np.array([600.0]), np.zeros(1))[0]
        s, _ = projector.project(x, z, speed_mps=0.0, dt_s=1.0 / HZ)
        self.assertAlmostEqual(s, 600.0, delta=0.5)


class FinishLineSplitsTest(unittest.TestCase):
    def test_the_lap_is_timed_from_s0_to_s0(self):
        """A volta gravada comeca 3 m depois da linha e termina 2,5 m depois dela."""
        track = circular_track()
        s_total = np.arange(3.0, track.length + 2.5, SPEED_MPS / HZ)
        elapsed = (s_total - s_total[0]) / SPEED_MPS
        frame = pd.DataFrame({"p": np.mod(s_total, track.length) / track.length, "elapsed_s": elapsed})
        splits = microsector_splits(frame, 60)
        self.assertNotIn(None, splits)
        expected = track.length / 60 / SPEED_MPS
        np.testing.assert_allclose(splits, expected, atol=2e-3)
        # A soma e o periodo: o tempo entre duas passagens pelo mesmo ponto.
        self.assertAlmostEqual(sum(splits), track.length / SPEED_MPS, delta=5e-3)

    def test_a_lap_that_starts_too_late_has_no_first_slice(self):
        track = circular_track()
        s_total = np.arange(100.0, track.length + 2.5, SPEED_MPS / HZ)
        frame = pd.DataFrame({"p": np.mod(s_total, track.length) / track.length,
                              "elapsed_s": (s_total - s_total[0]) / SPEED_MPS})
        splits = microsector_splits(frame, 60)
        self.assertIsNone(splits[0])
        self.assertIsNotNone(splits[5])


def drive_across_laps(track, laps, *, speed=SPEED_MPS, line_m=3.0, slow=None, jump_at=None):
    """Frames de varias voltas seguidas, com `timestamp` continuo.

    O cronometro do jogo zera `line_m` metros depois de `s = 0`, e o contador de
    voltas sobe junto: como no Assetto Corsa, onde a linha do jogo fica alguns
    metros depois do `s = 0` da geometria oficial.
    """
    step = speed / HZ
    s_total = np.arange(line_m, laps * track.length + line_m, step)
    t = (s_total - s_total[0]) / speed
    if slow is not None:
        lap, index, extra = slow
        start = lap * track.length + index / 60 * track.length
        end = start + track.length / 60
        t = t + np.where(s_total >= end, extra, np.where(s_total >= start, extra * (s_total - start) / (end - start), 0.0))
    lap_number = 1 + np.floor((s_total - line_m) / track.length).astype(int)
    line_times = {n: t[lap_number == n][0] for n in np.unique(lap_number)}
    s = np.mod(s_total, track.length)
    if jump_at is not None:
        s = np.where(s_total >= jump_at, np.mod(s + 400.0, track.length), s)
    world = track.to_world(s, np.zeros(s.size))
    frames = []
    for i in range(s.size):
        frames.append({
            "world_x": world[i, 0], "world_z": world[i, 1], "speedKmh": speed * 3.6,
            "lap_time": t[i] - line_times[lap_number[i]], "lap_number": int(lap_number[i]),
            "timestamp": 1.7e12 + t[i] * 1000.0, "track": "t",
        })
    return frames


class LiveFinishLineTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.geometry = exported(self.track, "geo-1")
        # Voltas de 60 s, como nos testes do pedido 11 (o modelo recusa voltas curtas).
        seconds = 60.0
        self.speed = self.track.length / seconds
        # A segunda volta perde 0,3 s nos microsetores 0 e 30: eles entram no foco (pedido 15).
        self.model = build_reference_model(
            [("ref", seconds, int(seconds * HZ), lap_on(self.track, seconds)),
             ("x", seconds + 0.6, int((seconds + 0.6) * HZ),
              synthetic_lap(self.track, seconds, slow=[(0, 0.3), (30, 0.3)]))],
            track="t", geometry=self.geometry,
        )

    def run_coach(self, frames):
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: self.model, geometry_provider=lambda _t: self.geometry,
                                 min_gap_seconds=0.0)
        for frame in frames:
            coach.on_frame(frame)
        return bus

    def test_the_first_slice_is_measured_from_s0(self):
        """O microsetor 0 da volta 2 conta a partir de s = 0, antes de o jogo zerar o cronometro."""
        bus = self.run_coach(drive_across_laps(self.track, 3, speed=self.speed, slow=(1, 0, 0.5)))
        events = [e for e in phrases_of(bus) if e["evidence"]["microsector"] == 0]
        self.assertEqual(len(events), 1)
        reference = self.model.targets[0].reference_seconds
        self.assertAlmostEqual(events[0]["evidence"]["yourSeconds"] - reference, 0.5, delta=0.02)

    def test_the_lap_summary_comes_at_the_line(self):
        bus = self.run_coach(drive_across_laps(self.track, 3, speed=self.speed, slow=(1, 30, 0.8)))
        self.assertTrue(bus.of(ENGINEER_SPEECH))

    def test_a_car_moved_mid_lap_starts_counting_again(self):
        """400 m de salto no meio da volta: nem frase de trecho, nem resumo no salto."""
        frames = drive_across_laps(self.track, 1, speed=self.speed, jump_at=0.3 * self.track.length)
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: self.model, geometry_provider=lambda _t: self.geometry,
                                 min_gap_seconds=0.0)
        jumped = False
        for frame in frames:
            coach.on_frame(frame)
            if not jumped and coach._lap_loss == 0.0 and coach._sector_index not in (None, 0)                     and coach._sector_index > int(0.3 * 60) + 3:
                jumped = True
                self.assertEqual(bus.of(ENGINEER_SPEECH), [])
        self.assertTrue(jumped)
        self.assertEqual(phrases_of(bus), [])



class WallClockStutterTest(LiveFinishLineTest):
    def test_a_stutter_in_the_recorder_clock_changes_nothing(self):
        """Medido em 04/10: o `timestamp` do gravador andou 357 ms numa amostra e 2 ms na
        seguinte, com o cronometro do jogo certo. O coach usa o cronometro."""
        frames = drive_across_laps(self.track, 3, speed=self.speed, slow=(1, 30, 0.8))
        clean = self.run_coach([dict(f) for f in frames])
        for i in range(200, len(frames), 400):
            frames[i]["timestamp"] += 357.0
            frames[i + 1]["timestamp"] += 2.0 - (frames[i + 1]["timestamp"] - frames[i]["timestamp"])
        stuttered = self.run_coach(frames)
        self.assertEqual(
            [e["evidence"]["yourSeconds"] for e in phrases_of(clean)],
            [e["evidence"]["yourSeconds"] for e in phrases_of(stuttered)],
        )
        self.assertTrue(phrases_of(clean))


# ── Parte C: as duas referencias (ADR 0016) ─────────────────────────────────

from core.assisted_analysis.reference_model import (  # noqa: E402
    REFERENCE_AI,
    REFERENCE_OWN_BEST,
    configured_reference_kind,
    reference_from_laps,
)
from ml.data.coach_references import ai_laps, driver_laps  # noqa: E402

FORBIDDEN = ("ganh", "ideal", "otimo")


def inventory_row(lap_id, origem, equipamento, **extra):
    session = lap_id.split("#")[0]
    row = {"lap_id": lap_id, "session_id": session, "origem": origem, "equipamento": equipamento,
           "valid": True, "relogio_verificado": True, "relogio_suspeito": False, "duplicada_de": None}
    row.update(extra)
    return row


class ReferenceSelectionTest(unittest.TestCase):
    def setUp(self):
        self.inventory = pd.DataFrame([
            inventory_row("2026-10-04_03-42-10_x#0013", "ia", "atual"),          # IA nova
            inventory_row("2026-08-09_19-20-59_x#0001", "ia", "anterior"),       # IA antiga
            inventory_row("2026-10-04_02-24-04_x#0018", "humano", "atual"),      # piloto de hoje
            inventory_row("2026-08-16_03-30-14_x#0004", "humano", "anterior"),   # piloto com o controle antigo
            inventory_row("2026-10-04_02-24-04_x#0007", "misturada", "atual"),
            inventory_row("2026-10-04_03-42-10_x#0014", "ia", "atual", relogio_suspeito=True),  # box
            inventory_row("2026-10-04_03-42-10_x#0015", "ia", "atual", valid=False),
        ])
        self.cars = {lap.split("#")[0]: "rss_formula_rss_3_v6_2026" for lap in self.inventory["lap_id"]}

    def test_volta_ia_uses_only_ai_laps_from_new_sessions(self):
        chosen = ai_laps(self.inventory, cars=self.cars, car="rss_formula_rss_3_v6_2026")["lap_id"].tolist()
        self.assertEqual(chosen, ["2026-10-04_03-42-10_x#0013"])

    def test_minha_melhor_uses_only_human_laps_with_the_current_equipment(self):
        chosen = driver_laps(self.inventory, cars=self.cars, car="rss_formula_rss_3_v6_2026")["lap_id"].tolist()
        self.assertEqual(chosen, ["2026-10-04_02-24-04_x#0018"])

    def test_pit_laps_and_other_cars_stay_out(self):
        self.assertTrue(ai_laps(self.inventory, ["2026-10-04_03-42-10_x#0013"]).empty)
        self.cars["2026-10-04_03-42-10_x"] = "outro_carro"
        self.assertTrue(ai_laps(self.inventory, cars=self.cars, car="rss_formula_rss_3_v6_2026").empty)


def synthetic_lap(track, seconds, *, slow=(), brake_at=None):
    """Volta sintetica a velocidade constante; `slow` = microsetores com tempo a mais."""
    count = int(seconds * HZ)
    s = np.linspace(0.0, track.length - 0.01, count)
    elapsed = s / track.length * seconds
    for index, extra in slow:
        start, end = index / 60 * track.length, (index + 1) / 60 * track.length
        elapsed = elapsed + np.where(s >= end, extra, np.where(s >= start, extra * (s - start) / (end - start), 0.0))
    world = track.to_world(s, np.zeros(count))
    brake = np.zeros(count)
    if brake_at is not None:
        brake[(s >= brake_at) & (s < brake_at + 40.0)] = 1.0
    return pd.DataFrame({"x": world[:, 0], "z": world[:, 1], "elapsed_s": elapsed, "s": s,
                         "speed_kmh": track.length / seconds * 3.6, "brake": brake, "throttle": 1.0})


FOCUS_OF_MODEL = (5, 14, 40)


class TwoReferencesTest(unittest.TestCase):
    """A IA freia em 300 m; o piloto freia em outro ponto."""

    def setUp(self):
        self.track = circular_track()
        self.geometry = exported(self.track, "geo-1")
        seconds = 60.0
        # As voltas do piloto freiam em 296 m, dentro do mesmo microsetor da IA (293-314 m).
        # Pedido 15: as voltas do piloto perdem 0,1, 0,2 e 0,3 s nos microsetores 5, 14 e 40,
        # que viram o foco do modelo nos dois modos.
        mine = [(f"h{i}", seconds + 0.5 + 0.3 * (i + 1), int((seconds + 0.5 + 0.3 * (i + 1)) * HZ),
                 synthetic_lap(self.track, seconds + 0.5, slow=[(k, 0.1 * (i + 1)) for k in FOCUS_OF_MODEL],
                               brake_at=296.0)) for i in range(3)]
        ai = [("ia", seconds, int(seconds * HZ), synthetic_lap(self.track, seconds, brake_at=300.0))]
        self.model = build_reference_model(mine, track="t", geometry=self.geometry)
        for kind, laps in ((REFERENCE_OWN_BEST, mine), (REFERENCE_AI, ai)):
            reference, _ = reference_from_laps(laps, geometry=self.geometry, kind=kind)
            self.model.references[kind] = reference
        self.model.use_reference(REFERENCE_AI)
        self.sector = int(300.0 / self.track.length * 60)

    def drive(self, lap):
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: self.model, geometry_provider=lambda _t: self.geometry,
                                 min_gap_seconds=0.0)
        for number, frame in ((1, lap), (2, synthetic_lap(self.track, 60.5, brake_at=290.0))):
            for row in frame.itertuples():
                coach.on_frame({"world_x": row.x, "world_z": row.z, "lap_time": row.elapsed_s, "lap_number": number,
                                "speedKmh": row.speed_kmh, "brake": row.brake, "track": "t"})
        return bus

    def test_at_most_three_phrases_a_lap_and_only_in_the_focus(self):
        slow = [(i, 0.5) for i in (5, 10, 14, 20, 40, 50)]
        bus = self.drive(synthetic_lap(self.track, 62.0, slow=slow, brake_at=290.0))
        lap_one = [e for e in phrases_of(bus) if e["lap_number"] == 1]
        self.assertEqual([e["evidence"]["microsector"] for e in lap_one], [5, 14, 40])

    def test_the_lap_summary_lists_the_three_largest(self):
        slow = [(5, 0.2), (10, 0.5), (20, 0.4), (30, 0.3), (40, 0.25)]
        bus = self.drive(synthetic_lap(self.track, 62.0, slow=slow, brake_at=290.0))
        summary = bus.of(ENGINEER_SPEECH)[0]["message"]
        self.assertIn("Maiores diferencas para a volta da IA", summary)
        self.assertLess(summary.index("setor 10"), summary.index("setor 20"))
        self.assertLess(summary.index("setor 20"), summary.index("setor 30"))
        self.assertNotIn("setor 40", summary)

    def test_braking_is_said_relative_to_the_reference(self):
        for driver_at, word in ((288.0, "depois"), (312.0, "antes")):
            bus = self.drive(synthetic_lap(self.track, 60.5, slow=[(self.sector, 0.4)], brake_at=driver_at))
            event = [e for e in phrases_of(bus) if e["evidence"]["microsector"] == self.sector][0]
            self.assertIn(f"A IA freia 12 m {word} de voce", event["event"])
            self.assertAlmostEqual(event["evidence"]["brakeDeltaM"], 300.0 - driver_at, delta=1.5)

    def test_phrases_name_the_reference_and_never_promise(self):
        texts = []
        for kind in (REFERENCE_AI, REFERENCE_OWN_BEST):
            self.model.use_reference(kind)
            bus = self.drive(synthetic_lap(self.track, 62.0, slow=[(self.sector, 0.6), (40, 0.5)], brake_at=288.0))
            events = phrases_of(bus)
            self.assertTrue(events)
            name = "volta da IA" if kind == REFERENCE_AI else "sua melhor volta"
            for event in events:
                self.assertIn(f"atras da {name} neste trecho", event["event"])
                self.assertEqual(event["evidence"]["referenceKind"], kind)
            texts += [e["event"] for e in events] + [m["message"] for m in bus.of(ENGINEER_SPEECH)]
        for text in texts:
            for word in FORBIDDEN:
                self.assertNotIn(word, text.lower())
        self.assertTrue(any("na sua melhor volta voce freou" in t.lower() for t in texts))

    def test_the_reference_comes_from_configuration(self):
        import os
        previous = os.environ.get("AT_COACH_REFERENCE")
        try:
            os.environ["AT_COACH_REFERENCE"] = "minha_melhor"
            self.assertEqual(configured_reference_kind(), REFERENCE_OWN_BEST)
            os.environ["AT_COACH_REFERENCE"] = "qualquer"
            self.assertEqual(configured_reference_kind(), REFERENCE_AI)
        finally:
            if previous is None:
                os.environ.pop("AT_COACH_REFERENCE", None)
            else:
                os.environ["AT_COACH_REFERENCE"] = previous

    def test_a_model_without_the_reference_stays_silent(self):
        del self.model.references[REFERENCE_OWN_BEST]
        self.assertFalse(self.model.use_reference(REFERENCE_OWN_BEST))
        self.assertFalse(self.model.has_reference)


class NotComparableSlicesTest(TwoReferencesTest):
    def test_a_slice_where_the_car_stopped_is_not_compared(self):
        """Medido em 04/10: saindo do box, "52.84s atras ... a sua 0 km/h"."""
        lap = synthetic_lap(self.track, 60.5, slow=[(14, 1.0)], brake_at=288.0)
        stop = int(len(lap) * 14.5 / 60)
        parked = pd.concat([lap.iloc[[stop]]] * int(20 * HZ), ignore_index=True)
        parked["speed_kmh"] = 0.0
        lap = pd.concat([lap.iloc[:stop], parked, lap.iloc[stop:]], ignore_index=True)
        lap.loc[stop:, "elapsed_s"] = lap.loc[stop:, "elapsed_s"].to_numpy() + np.r_[
            np.arange(len(parked)) / HZ, np.full(len(lap) - stop - len(parked), len(parked) / HZ)]
        bus = self.drive(lap)
        sector = 14
        self.assertFalse([e for e in phrases_of(bus) if e["evidence"]["microsector"] == sector])

    def test_the_slice_the_count_starts_in_is_not_compared(self):
        lap = synthetic_lap(self.track, 60.5, slow=[(5, 2.0)], brake_at=288.0)
        start = int(len(lap) * 5.5 / 60)                    # comeca no meio do microsetor 5
        bus = self.drive(lap.iloc[start:].reset_index(drop=True))
        self.assertFalse([e for e in phrases_of(bus) if e["evidence"]["microsector"] == 5 and e["lap_number"] == 1])


class SummaryRoundingTest(TwoReferencesTest):
    def test_no_summary_when_the_lap_matches_the_reference(self):
        """Medido: a melhor volta contra ela mesma listava "setor 0 (0.00s)"."""
        self.model.use_reference(REFERENCE_OWN_BEST)
        best = synthetic_lap(self.track, 60.5, slow=[(k, 0.1) for k in FOCUS_OF_MODEL], brake_at=296.0)
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: self.model, geometry_provider=lambda _t: self.geometry,
                                 min_gap_seconds=0.0)
        for number, frame in ((1, best), (2, best), (3, best)):
            for row in frame.itertuples():
                coach.on_frame({"world_x": row.x, "world_z": row.z, "lap_time": row.elapsed_s, "lap_number": number,
                                "speedKmh": row.speed_kmh, "brake": row.brake, "track": "t"})
        # A volta 2, inteira e igual a referencia, fecha sem resumo.
        self.assertEqual(len(bus.of(ENGINEER_SPEECH)), 0)


class FocusTest(unittest.TestCase):
    """Pedido 15: o coach so fala nos 3 trechos de foco."""

    setUp = TwoReferencesTest.setUp

    def drive_laps(self, laps, *, ai_laps=()):
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: self.model, geometry_provider=lambda _t: self.geometry,
                                 min_gap_seconds=0.0)
        for number, frame in enumerate(list(laps) + [synthetic_lap(self.track, 60.5, brake_at=296.0)], start=1):
            ai = number in ai_laps
            for row in frame.itertuples():
                coach.on_frame({"world_x": row.x, "world_z": row.z, "lap_time": row.elapsed_s, "lap_number": number,
                                "speedKmh": row.speed_kmh, "brake": row.brake, "track": "t",
                                "carPhysics": {"controls": {"isAIControlled": ai}}})
        return bus, coach

    def focus_lines(self, bus):
        return [e for e in bus.of(COACHING_EVENT) if e.get("type") == "coaching_focus"]

    def session_lap(self):
        return synthetic_lap(self.track, 60.5, slow=[(20, 0.6), (30, 0.5), (50, 0.4)], brake_at=296.0)

    def test_before_five_laps_the_focus_comes_from_the_model(self):
        bus, coach = self.drive_laps([self.session_lap()])
        self.assertEqual(coach.focus_sectors(self.model), (FOCUS_OF_MODEL, "modelo"))
        first = self.focus_lines(bus)[0]
        self.assertEqual(first["event"], "Foco nas proximas voltas: setores 5, 14 e 40")
        self.assertEqual(first["focusSource"], "modelo")

    def test_the_focus_is_the_three_largest_medians_of_the_last_five_valid_laps(self):
        laps = [self.session_lap() for _ in range(7)]
        # Uma volta so com um erro grande no microsetor 10: a mediana nao muda.
        laps[2] = synthetic_lap(self.track, 60.5, slow=[(10, 3.0), (20, 0.6), (30, 0.5), (50, 0.4)], brake_at=296.0)
        bus, coach = self.drive_laps(laps)
        # A volta 1 comeca a contar no meio dela mesma e nao vale; as voltas 2 a 6 sao as 5 validas.
        self.assertEqual(coach.focus_sectors(self.model), ((20, 30, 50), "sessao"))
        last = self.focus_lines(bus)[-1]
        self.assertEqual(last["event"], "Foco nas proximas voltas: setores 20, 30 e 50")
        self.assertIn("ultimas 5 voltas validas", last["evidence"])
        # Na volta 7, ja com o foco novo, as frases caem nos microsetores 20, 30 e 50.
        seventh = [e["evidence"]["microsector"] for e in phrases_of(bus) if e["lap_number"] == 7]
        self.assertEqual(seventh, [20, 30, 50])

    def test_outside_the_focus_the_coach_says_nothing(self):
        bus, _ = self.drive_laps([synthetic_lap(self.track, 60.5, slow=[(25, 2.0)], brake_at=296.0)])
        self.assertFalse([e for e in phrases_of(bus) if e["evidence"]["microsector"] == 25])

    def test_never_more_than_three_phrases_a_lap(self):
        slow = [(k, 0.8) for k in range(0, 60, 3)] + [(k, 0.8) for k in FOCUS_OF_MODEL]
        bus, _ = self.drive_laps([synthetic_lap(self.track, 70.0, slow=slow, brake_at=296.0) for _ in range(3)])
        per_lap = {}
        for event in phrases_of(bus):
            per_lap[event["lap_number"]] = per_lap.get(event["lap_number"], 0) + 1
        self.assertTrue(per_lap)
        self.assertLessEqual(max(per_lap.values()), 3)

    def test_laps_with_the_ai_at_the_wheel_do_not_count(self):
        laps = [self.session_lap() for _ in range(6)]
        _, coach = self.drive_laps(laps, ai_laps={3, 4})
        self.assertEqual(coach.focus_sectors(self.model)[1], "modelo")


if __name__ == "__main__":
    unittest.main()
