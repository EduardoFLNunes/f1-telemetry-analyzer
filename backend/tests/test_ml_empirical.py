"""Estimador empirico da Fase 2b (`ml.validation.empirical`), com dados sinteticos."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.track.corners import Corner
from ml.validation import empirical as em
from tests.test_ml_pipeline import circular_track


def corner(index, start, apex, end):
    return Corner(index, start, apex, end, 1, 30.0, 40.0, end - start)


def brake_trace(track, onsets, length_m=40.0):
    brake = np.zeros(track.size)
    for onset in onsets:
        span = (track.index_of(onset) + np.arange(int(length_m / track.step))) % track.size
        brake[span] = 0.8
    return brake


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()           # 1256,6 m
        self.corners = [corner(0, 60, 100, 140), corner(1, 310, 340, 380), corner(2, 720, 760, 800)]

    def test_onsets_ignore_short_taps(self):
        brake = brake_trace(self.track, [100.0])
        brake[self.track.index_of(500.0)] = 0.9    # toque de 2 m
        np.testing.assert_allclose(em.brake_onsets(brake, self.track), [100.0], atol=self.track.step)

    def test_windows_tile_the_lap_and_merge_close_taps(self):
        # Uma zona cruza a linha de chegada (~1255 m); outra em ~300 m com um
        # segundo toque 60 m depois, que nao abre janela; outra em ~700 m.
        rng = np.random.default_rng(0)
        brakes = [
            brake_trace(
                self.track,
                [np.mod(1255 + rng.normal(0, 3), self.track.length), 300 + rng.normal(0, 3), 360, 700],
            )
            for _ in range(10)
        ]
        windows = em.define_windows(brakes, self.track, self.corners)
        self.assertEqual(windows.count, 3)
        self.assertAlmostEqual(float(windows.lengths_m.sum()), self.track.length, places=6)
        self.assertEqual(np.bincount(windows.index, minlength=3).sum(), self.track.size)
        # Cada janela comeca antes da frenagem e usa a curva logo depois dela.
        self.assertTrue(np.all(np.mod(windows.zone_median_s - windows.start_s, self.track.length) < 30))
        labels = {round(s): c.index for s, c in zip(windows.start_s, windows.corner)}
        self.assertEqual(sorted(labels.values()), [0, 1, 2])

    def test_zones_braked_by_few_laps_do_not_open_a_window(self):
        brakes = [brake_trace(self.track, [300, 700]) for _ in range(9)]
        brakes.append(brake_trace(self.track, [300, 700, 1000]))
        self.assertEqual(em.define_windows(brakes, self.track, self.corners).count, 2)


class PairFeatureTest(unittest.TestCase):
    def test_differences_are_b_minus_a_across_the_line(self):
        track = circular_track()
        base = {
            "braking_point_s": track.length - 4.0, "throttle_point_s": 50.0,
            "lateral_entry_m": 1.0, "lateral_apex_m": -2.0, "lateral_exit_m": 0.5,
            "min_speed_kmh": 90.0, "exit_speed_kmh": 150.0,
        }
        later = dict(base, braking_point_s=6.0, lateral_apex_m=-1.5, min_speed_kmh=93.0)
        diff = em.pair_features(base, later, track)
        self.assertAlmostEqual(diff["braking_point_m"], 10.0)
        self.assertAlmostEqual(diff["lateral_apex_m"], 0.5)
        self.assertAlmostEqual(diff["min_speed_kmh"], 3.0)
        self.assertIsNone(em.pair_features(base, dict(base, throttle_point_s=None), track))

    def test_symmetrize_and_out_of_distribution(self):
        x, y = em.symmetrize(np.array([[1.0, 2.0]]), np.array([0.3]))
        np.testing.assert_allclose(x, [[1, 2], [-1, -2]])
        np.testing.assert_allclose(y, [0.3, -0.3])
        train = np.random.default_rng(1).normal(size=(500, 2))
        flags = em.ood_mask(train, np.array([[0.0, 0.0], [5.0, 0.0]]))
        self.assertEqual(flags.tolist(), [False, True])


class EstimatorTest(unittest.TestCase):
    """Uma relacao linear conhecida, por janela, com ruido e sessoes."""

    def setUp(self):
        rng = np.random.default_rng(7)
        n = 360
        self.windows = np.tile([0, 1], n // 2)
        self.sessions = np.repeat(["s1", "s2", "s3", "s4"], n // 4)
        self.x = rng.normal(size=(n, len(em.ACTIONABLE)))
        slope = np.where(self.windows == 0, 0.02, -0.01)
        self.y = slope * self.x[:, 0] + rng.normal(0, 0.005, n)
        self.test_x = rng.normal(size=(200, len(em.ACTIONABLE)))
        self.test_w = np.tile([0, 1], 100)
        self.test_y = np.where(self.test_w == 0, 0.02, -0.01) * self.test_x[:, 0] + rng.normal(0, 0.005, 200)

    def check(self, prediction, max_mae, min_cover=0.85):
        mae = np.mean(np.abs(prediction.point - self.test_y))
        zero = np.mean(np.abs(self.test_y))
        self.assertLess(mae, max_mae * zero)
        self.assertGreater(em.interval_coverage(prediction, self.test_y), min_cover)

    def test_ridge_recovers_a_per_window_effect(self):
        prediction, info = em.fit_ridge(self.x, self.y, self.windows, self.sessions, self.test_x, self.test_w, 2)
        self.check(prediction, 0.4)
        self.assertIn(info["alpha"], em.RIDGE_ALPHAS)

    def test_knn_and_gp_learn_the_relation(self):
        knn, info = em.fit_knn(self.x, self.y, self.windows, self.sessions, self.test_x, self.test_w, 2)
        self.check(knn, 0.9)
        self.assertIn(info["k"], em.KNN_KS)
        gp, _ = em.fit_gp(self.x, self.y, self.windows, self.test_x, self.test_w, 2)
        self.check(gp, 0.5)

    def test_answering_and_risk_coverage(self):
        prediction = em.Prediction(
            point=np.array([0.10, 0.01, -0.20, 0.0]),
            low=np.array([0.05, -0.02, -0.30, -0.1]),
            high=np.array([0.15, 0.04, -0.10, 0.1]),
        )
        self.assertEqual(em.answered(prediction).tolist(), [True, False, True, False])
        observed = np.array([0.10, 0.0, -0.20, 0.05])
        curve = em.risk_coverage(prediction, observed)
        self.assertEqual(curve[-1]["n"], 4)
        # Os mais confiantes primeiro: na metade de cobertura, so os dois certos.
        half = [c for c in curve if c["cobertura"] == 0.5][0]
        self.assertAlmostEqual(half["mae_s"], 0.0)
        self.assertAlmostEqual(em.interval_coverage(prediction, observed), 1.0)


if __name__ == "__main__":
    unittest.main()
