"""Detector de volta da IA (pedido 13): linha por trechos, frenagem, tempo e box. Tudo sintetico."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from ml.data import ai_detector as det  # noqa: E402
from ml.track.geometry import TrackGeometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402

BRAKE_AT = (300.0, 900.0)
LIMITS = det.DetectorLimits(
    lateral_ai_m=0.10, lateral_human_m=0.30, ai_run=3, human_run=2,
    braking_ai_m=3.0, braking_human_m=8.0,
    informative_microsectors=tuple(range(20)), braking_zones_m=BRAKE_AT,
)


def circular_track(radius: float = 200.0, step: float = 2.0) -> TrackGeometry:
    length = 2.0 * math.pi * radius
    count = int(round(length / step))
    used = length / count
    s = np.arange(count, dtype=float) * used
    theta = s / radius
    tangent = np.column_stack([-np.sin(theta), np.cos(theta)])
    return TrackGeometry(
        name="circulo", length=length, step=used, s=s,
        x=radius * np.cos(theta), z=radius * np.sin(theta), elevation=np.zeros(count),
        tangent=tangent, normal=np.column_stack([tangent[:, 1], -tangent[:, 0]]),
        curvature=np.full(count, -1.0 / radius),
        width_left=np.full(count, 6.0), width_right=np.full(count, 6.0),
    )


TRACK = circular_track()
SECTORS = build_microsectors(TRACK, 20)
AI_LINE = 2.0 * np.sin(TRACK.s / TRACK.length * 2 * math.pi * 3)


def lap(offset=0.0, noise=0.0, brake_shift=0.0, seed=0, speed=200.0):
    rng = np.random.default_rng(seed)
    brake = np.zeros(TRACK.size)
    for start in BRAKE_AT:
        on = (TRACK.s >= start + brake_shift) & (TRACK.s < start + brake_shift + 60)
        brake[on] = 1.0
    return pd.DataFrame({
        "lateral": AI_LINE + offset + rng.normal(0.0, noise, TRACK.size),
        "brake": brake,
        "speed_kmh": np.full(TRACK.size, speed),
    })


REFERENCE = det.build_reference({f"ia#{i}": lap(noise=0.01, seed=i) for i in range(5)}, TRACK)


def verdict(grid, lap_time):
    return det.classify_lap(grid, lap_time, REFERENCE, TRACK, SECTORS, LIMITS)


class ReferenceTests(unittest.TestCase):
    def test_the_reference_is_the_median_line_and_the_common_braking_points(self):
        self.assertLess(np.max(np.abs(REFERENCE.lateral - AI_LINE)), 0.03)
        self.assertEqual(len(REFERENCE.braking_s), 2)
        for found, expected in zip(REFERENCE.braking_s, BRAKE_AT):
            self.assertLess(abs(found - expected), 2.5)

    def test_a_missing_braking_counts_as_far(self):
        grid = lap(noise=0.01, seed=5)
        grid["brake"] = 0.0
        self.assertEqual(det.zone_distances(grid, BRAKE_AT, TRACK).tolist(), [det.BRAKE_MATCH_WINDOW_M] * 2)


class CalibrationTests(unittest.TestCase):
    def test_only_microsectors_where_the_ai_repeats_itself_are_used(self):
        steady = np.full(5, 0.05)
        loose = np.array([0.05, 0.05, 0.9, 0.05, 0.05])
        self.assertEqual(det.informative_microsectors([steady, loose], 0.25), (0, 1, 3, 4))

    def test_only_braking_zones_the_ai_repeats_are_used(self):
        distances = np.array([[0.0, 2.0], [1.0, 60.0], [2.0, 60.0]])
        self.assertEqual(det.reliable_zones(distances, (100.0, 500.0), 4.0), (100.0,))


class LineTests(unittest.TestCase):
    def test_an_ai_lap(self):
        result = verdict(lap(noise=0.01, seed=9), 85.0)
        self.assertEqual((result["linha"], result["origem_detector"]), ("ia", "ia"))

    def test_a_human_lap(self):
        result = verdict(lap(offset=0.8, noise=0.2, brake_shift=-12, seed=3), 94.0)
        self.assertEqual((result["linha"], result["origem_detector"]), ("humano", "humano"))

    def test_a_lap_handed_over_halfway_is_mixed(self):
        grid = lap(noise=0.01, seed=4)
        grid.loc[TRACK.s > TRACK.length / 2, "lateral"] += 1.0
        self.assertEqual(verdict(grid, 89.0)["origem_detector"], "misturada")

    def test_isolated_near_misses_do_not_make_a_human_lap_mixed(self):
        """Medido: as voltas do piloto passam perto da IA em ate 2 microsetores seguidos."""
        states = ["humano"] * 8 + ["ia", "ia"] + ["humano"] * 8 + ["ia"] + ["humano"]
        self.assertEqual(det.line_label(states, LIMITS), "humano")

    def test_a_long_ai_stretch_and_a_human_stretch_are_mixed(self):
        states = ["ia"] * 15 + ["humano"] * 4 + ["fora"]
        self.assertEqual(det.line_label(states, LIMITS), "misturada")

    def test_unclear_laps_stay_unknown(self):
        self.assertEqual(det.line_label(["ia"] * 18 + ["indefinido", "indefinido"], LIMITS), "desconhecida")
        self.assertEqual(det.line_label(["indefinido"] * 20, LIMITS), "desconhecida")
        self.assertEqual(det.line_label(["fora"] * 20, LIMITS), "desconhecida")

    def test_states_use_only_informative_microsectors(self):
        limits = det.DetectorLimits(0.10, 0.30, 3, 2, 3.0, 8.0, informative_microsectors=(0, 2))
        self.assertEqual(det.microsector_states([0.05, 0.05, 0.5, 0.2], limits), ["ia", "fora", "humano", "fora"])


class AgreementTests(unittest.TestCase):
    def test_braking_must_confirm_the_line(self):
        grid = lap(noise=0.01, seed=6, brake_shift=-20)   # linha da IA, freia 20 m antes
        result = verdict(grid, 85.0)
        self.assertEqual(result["linha"], "ia")
        self.assertEqual(result["origem_detector"], "desconhecida")
        self.assertIn("frenagem", result["motivo"])

    def test_time_votes(self):
        self.assertEqual(det.time_votes(85.0, LIMITS), ("ia", "misturada"))
        self.assertEqual(det.time_votes(94.0, LIMITS), ("humano", "misturada"))
        self.assertEqual(det.time_votes(90.0, LIMITS), ("ia", "humano", "misturada"))

    def test_line_and_time_must_agree(self):
        self.assertEqual(verdict(lap(noise=0.01, seed=9), 94.0)["origem_detector"], "desconhecida")
        self.assertEqual(verdict(lap(offset=0.8, noise=0.2, brake_shift=-12, seed=3), 85.0)["origem_detector"], "desconhecida")

    def test_between_88_and_92_the_line_decides(self):
        self.assertEqual(verdict(lap(offset=0.8, noise=0.2, brake_shift=-12, seed=3), 91.7)["origem_detector"], "humano")


class PitTests(unittest.TestCase):
    def test_a_lap_through_the_pit_lane_is_left_out(self):
        grid = lap()
        near = np.isin(SECTORS.index, [0, 1])
        grid.loc[near, "lateral"] = 15.0
        grid.loc[near, "speed_kmh"] = 80.0
        self.assertTrue(det.pit_lap(grid, SECTORS))
        self.assertEqual(verdict(grid, 101.7)["motivo"], "box")

    def test_a_normal_lap_is_not_a_pit_lap(self):
        self.assertFalse(det.pit_lap(lap(), SECTORS))


class RegisteredLimitsTests(unittest.TestCase):
    def test_the_registered_limits_are_the_ones_in_the_stage_document(self):
        limits = det.LIMITS
        self.assertIsNotNone(limits)
        self.assertEqual((limits.lateral_ai_m, limits.lateral_human_m, limits.ai_run, limits.human_run),
                         (0.25, 0.30, 3, 2))
        self.assertEqual((limits.braking_ai_m, limits.braking_human_m), (4.0, 8.0))
        self.assertEqual((limits.time_ai_max_s, limits.time_human_min_s), (88.0, 92.0))
        self.assertEqual(len(limits.informative_microsectors), 40)
        self.assertEqual(len(limits.braking_zones_m), 8)


if __name__ == "__main__":
    unittest.main()
