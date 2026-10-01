"""Identidade da geometria, associacao com o replay e conferencia da projecao.

Tudo sintetico: nenhum teste depende das gravacoes nem do cache de geometria.
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data import lap_identity
from ml.data.lap_store import GeometryMismatchError, StoredLaps, load_store, save_store
from ml.preprocessing.alignment import align_lap, recorded_agreement
from ml.track.geometry import load_geometry

RADIUS = 300.0
VERTICES = 900


def circle_cache(radius=RADIUS, vertices=VERTICES, nudge=0.0, generated_at="2026-01-01"):
    """Um cache no formato de `data/cache/tracks/*.json`, para um circulo."""
    length = 2.0 * math.pi * radius
    theta = np.arange(vertices) * 2.0 * math.pi / vertices
    centre = np.column_stack([radius * np.cos(theta), radius * np.sin(theta)])
    centre[10, 0] += nudge
    outward = np.column_stack([np.cos(theta), np.sin(theta)])
    distance = theta * radius
    return {
        "trackName": "circulo",
        "trackLength": length,
        "generatedAt": generated_at,
        "sourceHash": "abc123",
        "centerline": [
            {"x": float(x), "z": float(z), "worldY": 0.0, "distance": float(d)}
            for (x, z), d in zip(centre, distance)
        ],
        "normals": [{"x": float(x), "z": float(z)} for x, z in outward],
        "boundsLeft": [{"x": float(x), "z": float(z)} for x, z in centre + 6.0 * outward],
        "boundsRight": [{"x": float(x), "z": float(z)} for x, z in centre - 6.0 * outward],
    }


def write(directory: Path, name: str, payload: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class GeometryFingerprintTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())

    def test_rewriting_the_same_geometry_keeps_the_id(self):
        first = load_geometry(write(self.directory, "a.json", circle_cache(generated_at="x")))
        second = load_geometry(write(self.directory, "b.json", circle_cache(generated_at="y")))
        self.assertTrue(first.geometry_id)
        self.assertEqual(first.geometry_id, second.geometry_id)
        self.assertEqual(first.source_hash, "abc123")

    def test_moving_one_vertex_by_centimetres_changes_the_id(self):
        base = load_geometry(write(self.directory, "a.json", circle_cache()))
        moved = load_geometry(write(self.directory, "b.json", circle_cache(nudge=0.05)))
        self.assertNotEqual(base.geometry_id, moved.geometry_id)

    def test_processing_parameters_are_part_of_the_id(self):
        path = write(self.directory, "a.json", circle_cache())
        self.assertNotEqual(
            load_geometry(path).geometry_id,
            load_geometry(path, centerline_smoothing_m=30.0).geometry_id,
        )


class StoreGeometryCheckTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.track = load_geometry(write(self.directory, "a.json", circle_cache()))
        other = load_geometry(write(self.directory, "b.json", circle_cache(nudge=0.05)))
        self.other = other
        frame = pd.DataFrame({"lap_id": ["s#0000"] * 3, "grid_index": [0, 1, 2], "lateral": 0.0})
        laps = pd.DataFrame([{"lap_id": "s#0000", "lap_time_s": 90.0}])
        self.store = StoredLaps(
            frame=frame, laps=laps, grid_size=3, track_length=self.track.length,
            geometry_id=self.track.geometry_id, source_hash=self.track.source_hash,
        )

    def test_store_round_trips_with_its_geometry(self):
        save_store(self.store, self.directory)
        loaded = load_store(self.directory, track=self.track)
        self.assertEqual(loaded.geometry_id, self.track.geometry_id)

    def test_store_refuses_another_geometry(self):
        save_store(self.store, self.directory)
        with self.assertRaises(GeometryMismatchError):
            load_store(self.directory, track=self.other)

    def test_store_without_geometry_record_is_refused(self):
        save_store(self.store, self.directory)
        meta_path = self.directory / "laps_grid_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.pop("geometry_id")
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(GeometryMismatchError):
            load_store(self.directory, track=self.track)
        # Sem `track`, o comportamento antigo continua: so le.
        self.assertEqual(load_store(self.directory).geometry_id, "")


class LapIdentityTest(unittest.TestCase):
    SESSION = "2026-08-16_03-30-14_vhe_interlagos"

    def test_clean_laps_with_counter_lag_are_exact(self):
        counts = {
            ("S#0000", 0): {1: 5000},
            # Tres quadros com o numero da volta anterior, o atraso do contador.
            ("S#0001", 1): {1: 3, 2: 5100},
            ("S#0002", 2): {2: 2, 3: 4900},
        }
        out = lap_identity.classify(self.SESSION, counts)
        self.assertEqual(out["S#0001"].match, lap_identity.EXACT)
        self.assertEqual(out["S#0001"].replay_lap_id, f"rec__{self.SESSION}__2")
        self.assertEqual(out["S#0002"].game_lap_number, 3)

    def test_a_frozen_counter_is_not_taken_as_one_lap(self):
        # O caso real: quatro trechos gravados como volta 6, tres deles no box.
        counts = {
            ("S#0010", 10): {6: 5200},
            ("S#0011", 11): {6: 900},
            ("S#0012", 12): {6: 1500},
            ("S#0013", 13): {6: 700},
        }
        out = lap_identity.classify(self.SESSION, counts)
        for lap_id in ("S#0010", "S#0011", "S#0012", "S#0013"):
            self.assertEqual(out[lap_id].match, lap_identity.REPLAY_HAS_MORE, lap_id)
            self.assertEqual(out[lap_id].replay_lap_id, f"rec__{self.SESSION}__6")
        self.assertAlmostEqual(out["S#0010"].share_of_replay, 5200 / 8300)

    def test_a_lap_that_spans_two_counters_is_flagged(self):
        out = lap_identity.classify(self.SESSION, {("S#0000", 0): {4: 3000, 5: 2000}})
        self.assertEqual(out["S#0000"].match, lap_identity.SPANS_COUNTERS)

    def test_counts_come_from_the_raw_frame(self):
        frame = pd.DataFrame({"lap_number": [1.0, 2.0, 2.0, np.nan]})
        self.assertEqual(lap_identity.counter_counts(frame), {1: 1, 2: 2})


class RecordedAgreementTest(unittest.TestCase):
    def test_a_flipped_recorded_offset_shows_up_as_negative_correlation(self):
        lateral = np.sin(np.linspace(0, 20, 400)) * 4.0
        s_values = np.linspace(0, 1000, 400)
        right = pd.DataFrame({"lateral_recorded": lateral + 0.05, "s_recorded": s_values + 0.1})
        wrong = pd.DataFrame({"lateral_recorded": -lateral})
        good = recorded_agreement(right, s_values, lateral, 2000.0)
        bad = recorded_agreement(wrong, s_values, lateral, 2000.0)
        self.assertGreater(good["recorded_lateral_correlation"], 0.99)
        self.assertLess(good["recorded_lateral_p95_m"], 0.06)
        self.assertLess(good["recorded_s_p95_m"], 0.11)
        self.assertLess(bad["recorded_lateral_correlation"], -0.99)

    def test_finish_line_wrap_is_not_a_disagreement(self):
        s_values = np.full(100, 1999.5)
        frame = pd.DataFrame({"s_recorded": np.full(100, 0.3)})
        agreement = recorded_agreement(frame, s_values, np.zeros(100), 2000.0)
        self.assertAlmostEqual(agreement["recorded_s_p95_m"], 0.8, places=6)

    def test_alignment_reports_agreement(self):
        track = load_geometry(write(Path(tempfile.mkdtemp()), "a.json", circle_cache()))
        s = np.linspace(10.0, 600.0, 200)
        lateral = np.full(200, 1.5)
        world = track.to_world(s, lateral)
        frame = pd.DataFrame(
            {
                "x": world[:, 0],
                "z": world[:, 1],
                "timestamp_s": np.arange(200) * 0.02,
                "s_recorded": s,
                "lateral_recorded": lateral,
            }
        )
        _, report = align_lap(frame, track)
        self.assertLess(report.recorded_s_p95_m, 0.5)
        self.assertLess(report.recorded_lateral_p95_m, 0.1)


if __name__ == "__main__":
    unittest.main()
