"""Coach na geometria oficial (ADR 0013), com pistas sinteticas.

* o projetor (o `MapMatchingEngine` existente, na grade exportada pelo `ml`)
  recupera `s` e `d` conhecidos e desempata por continuidade onde duas retas
  correm lado a lado;
* uma volta sem `p` (formato de 2026-08-09) entra no modelo;
* voltas com `p` de reguas diferentes entram no mesmo modelo, porque o `p`
  gravado e ignorado;
* geometria ausente ou com outro `geometry_id` deixa o coach em silencio.
"""

from __future__ import annotations

import dataclasses
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.official_geometry import OfficialGeometry, find_official_geometry, geometry_path  # noqa: E402
from core.assisted_analysis.reference_model import build_reference_model, microsector_splits  # noqa: E402
from core.live.driving_coach import LiveDrivingCoach, coach_recorded_lap  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402
from ml.export.geometry import official_geometry  # noqa: E402
from ml.track.geometry import TrackGeometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from tests.test_driving_coach import FakeBus  # noqa: E402
from tests.test_ml_pipeline import circular_track  # noqa: E402

HZ = 57.0


def exported(track: TrackGeometry, geometry_id: str = "geo-teste") -> OfficialGeometry:
    track = dataclasses.replace(track, geometry_id=geometry_id)
    return OfficialGeometry.from_dict(official_geometry(track, build_microsectors(track), "teste"))


def paperclip(straight: float = 400.0, gap: float = 10.0, step: float = 2.0) -> TrackGeometry:
    """Duas retas paralelas a `gap` metros, ligadas por semicirculos: a reta dos
    boxes ao lado do retorno, em miniatura."""
    radius = gap / 2.0
    length = 2 * straight + 2 * math.pi * radius
    count = int(round(length / step))
    used = length / count
    s = np.arange(count) * used
    x, z, tx, tz = (np.empty(count) for _ in range(4))
    arc = math.pi * radius
    for i, si in enumerate(s):
        if si < straight:                                   # reta de baixo, para +x
            x[i], z[i], tx[i], tz[i] = si, 0.0, 1.0, 0.0
        elif si < straight + arc:                           # curva da direita, sobe
            a = (si - straight) / radius - math.pi / 2
            x[i], z[i] = straight + radius * math.cos(a), radius + radius * math.sin(a)
            tx[i], tz[i] = -math.sin(a), math.cos(a)
        elif si < 2 * straight + arc:                       # reta de cima, para -x
            d = si - straight - arc
            x[i], z[i], tx[i], tz[i] = straight - d, gap, -1.0, 0.0
        else:                                               # curva da esquerda, desce
            a = (si - 2 * straight - arc) / radius + math.pi / 2
            x[i], z[i] = radius * math.cos(a), radius + radius * math.sin(a)
            tx[i], tz[i] = -math.sin(a), math.cos(a)
    tangent = np.column_stack([tx, tz])
    normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
    return TrackGeometry(
        name="clipe", length=length, step=used, s=s, x=x, z=z, elevation=np.zeros(count),
        tangent=tangent, normal=normal, curvature=np.zeros(count),
        width_left=np.full(count, 4.0), width_right=np.full(count, 4.0),
    )


def lap_on(track: TrackGeometry, seconds: float, *, lateral: float = 0.0, slow=None, p=None):
    """Volta sintetica com posicao no mundo. `p` = None, "zero" (formato 09/08)
    ou um deslocamento para simular a regua de outro cache."""
    count = int(seconds * HZ)
    s = np.linspace(0.0, track.length - 0.01, count)
    elapsed = s / track.length * seconds
    if slow is not None:
        index, extra = slow
        start, end = index / 60 * track.length, (index + 1) / 60 * track.length
        elapsed = elapsed + np.where(s >= end, extra, np.where(s >= start, extra * (s - start) / (end - start), 0.0))
    world = track.to_world(s, np.full(count, lateral))
    frame = pd.DataFrame({
        "x": world[:, 0], "z": world[:, 1], "elapsed_s": elapsed,
        "speed_kmh": 150.0, "brake": 0.0, "throttle": 1.0,
    })
    if p == "zero":
        frame["p"] = 0.0
    elif p is not None:
        frame["p"] = np.mod(s / track.length + float(p), 1.0)
    return frame


class ProjectorTest(unittest.TestCase):
    def test_known_points_come_back_on_the_circle(self):
        track = circular_track()
        geometry = exported(track)
        projector = geometry.projector()
        s_true = np.linspace(5.0, track.length - 5.0, 300)
        lateral = 1.5 * np.sin(s_true / 40.0)
        world = track.to_world(s_true, lateral)
        out = np.array([projector.project(x, z) for x, z in world])
        np.testing.assert_allclose(out[:, 0], s_true, atol=0.1)
        # `d` na convencao do ml: positivo do lado da normal exportada (esquerda).
        np.testing.assert_allclose(out[:, 1], lateral, atol=0.05)

    def test_crossing_the_finish_line_wraps(self):
        track = circular_track()
        projector = exported(track).projector()
        s_true = np.mod(np.linspace(track.length - 20.0, track.length + 20.0, 41), track.length)
        world = track.to_world(s_true, np.zeros(s_true.size))
        out = np.array([projector.project(x, z)[0] for x, z in world])
        diff = np.mod(out - s_true + track.length / 2, track.length) - track.length / 2
        self.assertLess(np.max(np.abs(diff)), 0.1)
        self.assertTrue(np.all((out >= 0) & (out < track.length)))

    def test_continuity_keeps_the_car_on_its_own_straight(self):
        track = paperclip(gap=10.0)
        projector = exported(track).projector()
        # A volta pela reta de baixo, deslocada 4,5 m em direcao a de cima: a
        # 5,5 m da reta de cima, so 1 m mais longe. Sem continuidade, qualquer
        # ruido trocaria de reta.
        s_true = np.linspace(20.0, 380.0, 200)
        world = track.to_world(s_true, np.full(s_true.size, 4.5))
        out = np.array([projector.project(x, z)[0] for x, z in world])
        np.testing.assert_allclose(out, s_true, atol=0.2)


class GeometryFileTest(unittest.TestCase):
    def test_export_round_trip_and_lookup(self):
        track = dataclasses.replace(circular_track(), geometry_id="abc123")
        payload = official_geometry(track, build_microsectors(track), "pista")
        root = Path(tempfile.mkdtemp())
        path = geometry_path(root, "pista")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = find_official_geometry([None, root], "pista")
        self.assertEqual(loaded.geometry_id, "abc123")
        self.assertEqual(loaded.microsectors, 60)
        np.testing.assert_allclose(loaded.x, np.round(track.x, 4))

    def test_broken_or_unequal_edges_are_refused(self):
        track = dataclasses.replace(circular_track(), geometry_id="abc")
        payload = official_geometry(track, build_microsectors(track), "pista")
        payload["microsector_edges"][10] += 5.0
        with self.assertRaises(ValueError):
            OfficialGeometry.from_dict(payload)
        payload = official_geometry(track, build_microsectors(track), "pista")
        payload["geometry_id"] = ""
        with self.assertRaises(ValueError):
            OfficialGeometry.from_dict(payload)


class ModelOnOfficialGeometryTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.geometry = exported(self.track, "geo-1")

    def entry(self, lap_id, seconds, frame):
        return (lap_id, seconds, int(seconds * HZ), frame)

    def test_a_lap_without_p_enters_the_model(self):
        model = build_reference_model([self.entry("agosto", 60.0, lap_on(self.track, 60.0, p="zero"))],
                                      track="t", geometry=self.geometry)
        self.assertEqual(model.lap_count, 1)
        self.assertEqual(model.reference_lap_id, "agosto")
        self.assertEqual(model.geometry_id, "geo-1")
        self.assertAlmostEqual(sum(t.reference_seconds for t in model.targets), 60.0, delta=0.05)
        # Sem a geometria, a mesma volta (p constante) nao serve.
        legacy = build_reference_model([self.entry("agosto", 60.0, lap_on(self.track, 60.0, p="zero"))], track="t")
        self.assertEqual(legacy.lap_count, 0)

    def test_laps_from_different_rulers_enter_the_same_model(self):
        laps = [
            self.entry("cache_atual", 60.4, lap_on(self.track, 60.4, p=0.0)),
            self.entry("merge_fix", 60.0, lap_on(self.track, 60.0, p=0.013)),   # regua deslocada ~16 m
            self.entry("sem_cache", 60.7, lap_on(self.track, 60.7)),
        ]
        model = build_reference_model(laps, track="t", geometry=self.geometry)
        self.assertEqual(model.lap_count, 3)
        self.assertEqual(model.reference_lap_id, "merge_fix")
        # O p gravado foi ignorado: os microsetores do modelo sao os de mesma
        # distancia, e o tempo de cada um e o da volta na regua oficial.
        self.assertAlmostEqual(model.targets[0].reference_seconds, 1.0, delta=0.02)
        reasons = {c["lap_id"]: c["motivo"] for c in model.reference_candidates}
        self.assertTrue(reasons["merge_fix"].startswith("escolhida"))
        self.assertIn("mais lenta", reasons["cache_atual"])

    def test_a_lap_whose_projection_jumps_is_left_out(self):
        # O carro "aparece" 150 m adiante por meio segundo (saida de pista longe,
        # projecao no trecho errado): os microsetores dali nao tem tempo real.
        bad = lap_on(self.track, 58.0)
        world = self.track.to_world(np.full(30, 650.0), np.zeros(30))
        bad.loc[1500:1529, ["x", "z"]] = world
        laps = [self.entry("salto", 58.0, bad), self.entry("boa", 60.0, lap_on(self.track, 60.0))]
        model = build_reference_model(laps, track="t", geometry=self.geometry)
        self.assertEqual(model.lap_count, 1)
        self.assertEqual(model.rejected_reasons, {"projection_jump": 1})
        self.assertEqual(model.reference_lap_id, "boa")
        self.assertGreater(min(t.best_seconds for t in model.targets), 0.5)

    def test_reference_reasons_explain_an_incomplete_lap(self):
        hole = lap_on(self.track, 59.0)
        hole = hole[(hole.index < 1200) | (hole.index > 1500)].reset_index(drop=True)
        laps = [self.entry("buraco", 59.0, hole), self.entry("boa", 60.0, lap_on(self.track, 60.0))]
        model = build_reference_model(laps, track="t", geometry=self.geometry)
        self.assertEqual(model.reference_lap_id, "boa")
        reasons = {c["lap_id"]: c["motivo"] for c in model.reference_candidates}
        self.assertIn("buraco", reasons["buraco"])


class CoachOnOfficialGeometryTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.geometry = exported(self.track, "geo-1")
        self.model = build_reference_model(
            [("ref", 60.0, int(60 * HZ), lap_on(self.track, 60.0)), ("x", 60.5, int(60.5 * HZ), lap_on(self.track, 60.5))],
            track="t", geometry=self.geometry,
        )

    def drive(self, geometry, seconds=60.0, lap=5, slow=None):
        bus = FakeBus()
        coach = LiveDrivingCoach(bus, lambda _t: self.model, geometry_provider=lambda _t: geometry, min_gap_seconds=0.0)
        for current in (lap, lap + 1):
            frame = lap_on(self.track, seconds, slow=slow if current == lap else None)
            for row in frame.itertuples():
                # So posicao no mundo: nenhum `p` no frame.
                coach.on_frame({"world_x": row.x, "world_z": row.z, "lap_time": row.elapsed_s,
                                "lap_number": current, "track": "t", "speedKmh": 150.0})
        return bus

    def test_the_coach_speaks_from_world_position(self):
        bus = self.drive(self.geometry, slow=(22, 0.6))
        events = bus.of(COACHING_EVENT)
        self.assertTrue(events)
        self.assertEqual(events[0]["evidence"]["microsector"], 22)
        self.assertIn("volta de referencia", events[0]["event"])

    def test_missing_geometry_keeps_the_coach_silent(self):
        with self.assertLogs("core.live.driving_coach", level="WARNING") as logs:
            bus = self.drive(None, slow=(22, 0.9))
        self.assertEqual(bus.published, [])
        self.assertTrue(any("missing" in line for line in logs.output))

    def test_another_geometry_keeps_the_coach_silent(self):
        other = exported(self.track, "outra-geometria")
        with self.assertLogs("core.live.driving_coach", level="WARNING") as logs:
            bus = self.drive(other, slow=(22, 0.9))
        self.assertEqual(bus.published, [])
        self.assertEqual(sum("outra-geometria" in line for line in logs.output), 1)   # avisa uma vez

    def test_the_replay_coach_uses_the_same_projection(self):
        frame = lap_on(self.track, 60.0, slow=(22, 0.6), p="zero")
        result = coach_recorded_lap(frame, self.model, lap_number=3, track="t", geometry=self.geometry)
        self.assertTrue(result["events"])
        self.assertEqual(result["events"][0]["evidence"]["microsector"], 22)


if __name__ == "__main__":
    unittest.main()
