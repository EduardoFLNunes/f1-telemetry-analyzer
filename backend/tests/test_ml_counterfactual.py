"""Avaliacao contrafactual (`ml.validation.counterfactual`), sobre a pista circular."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.track.microsectors import build_microsectors
from ml.validation import counterfactual as cf
from tests.test_ml_pipeline import circular_track, flat_envelope


def profile(track, sectors, lap_id, session, lateral, efficiency, envelope, fuel=20.0):
    """Volta sintetica que percorre `lateral` a `efficiency` x a velocidade simulada."""
    lap = cf.LapProfile(
        lap_id=lap_id,
        session_id=session,
        lap_time_s=0.0,
        lateral=np.full(track.size, float(lateral)) if np.isscalar(lateral) else lateral,
        observed_step_s=np.ones(track.size),
        speed_kmh=np.full(track.size, 100.0),
        brake=np.zeros(track.size),
        throttle=np.ones(track.size),
        fuel=fuel,
        tyre_wear=100.0,
        off_track=0.0,
        sector_time_s=np.zeros(sectors.count),
    )
    cf.simulate_profiles(track, envelope, [lap])
    eta = np.full(track.size, float(efficiency)) if np.isscalar(efficiency) else efficiency
    lap.observed_step_s = lap.step_length_m / (eta * lap.sim_speed_mps)
    lap.sector_time_s = np.bincount(sectors.index, weights=lap.observed_step_s, minlength=sectors.count)
    lap.lap_time_s = float(lap.observed_step_s.sum())
    return lap


class CounterfactualTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.sectors = build_microsectors(self.track, count=12)
        self.envelope = flat_envelope()

    def make(self, lap_id, lateral, efficiency, session="s1", fuel=20.0):
        return profile(self.track, self.sectors, lap_id, session, lateral, efficiency, self.envelope, fuel)

    def test_own_line_with_own_efficiency_reproduces_the_clock(self):
        lap = self.make("a", 1.0, np.linspace(0.8, 0.95, self.track.size))
        np.testing.assert_allclose(
            cf.modelled_sector_time(lap, lap, 0, self.sectors), lap.sector_time_s, rtol=1e-9
        )

    def test_same_execution_means_no_execution_effect_and_no_interaction(self):
        # Mesma eficiencia, linhas diferentes: o efeito e todo de linha.
        profiles = {"a": self.make("a", 0.0, 0.9), "b": self.make("b", -2.0, 0.9)}
        pairs = cf.build_pairs(profiles, self.sectors)
        parts = cf.decompose(pairs, profiles, self.sectors)
        np.testing.assert_allclose(parts["execution"], 0.0, atol=1e-9)
        np.testing.assert_allclose(parts["interaction"], 0.0, atol=1e-9)
        np.testing.assert_allclose(parts["total"], pairs.observed, atol=1e-9)
        # Linha por dentro (L < 0 aqui e o lado do centro do circulo) e mais curta.
        self.assertTrue(np.all(parts["line"] < 0))

    def test_efficiency_estimator_is_exact_when_only_the_line_changes(self):
        profiles = {"a": self.make("a", 0.0, 0.9), "b": self.make("b", -2.0, 0.9)}
        pairs = cf.build_pairs(profiles, self.sectors)
        predicted = cf.predict(pairs, profiles, self.sectors, window=0, slope=1.0)
        np.testing.assert_allclose(predicted["efficiency"], pairs.observed, atol=1e-9)
        # A fisica crua supoe o piloto no limite: a 90 % dele, preve ~0,9 x o real.
        ratio = predicted["physics"].sum() / pairs.observed.sum()
        self.assertAlmostEqual(ratio, 0.9, delta=0.01)

    def test_pairs_put_the_slower_lap_first_and_flag_incompatible_fuel(self):
        profiles = {
            "fast": self.make("fast", 0.0, 0.95),
            "slow": self.make("slow", 0.0, 0.85, fuel=40.0),
            "other": self.make("other", 0.0, 0.9, session="s2"),
        }
        pairs = cf.build_pairs(profiles, self.sectors)
        self.assertEqual(len(pairs), 1)                 # sessoes diferentes nao formam par
        self.assertEqual(pairs.slow, ["slow"])
        self.assertEqual(pairs.fast, ["fast"])
        self.assertIn("combustivel", pairs.lap_reason[0])
        self.assertTrue(np.all(pairs.sector_reason[0] == pairs.lap_reason[0]))

    def test_incidents_are_flagged_per_sector(self):
        eta = np.full(self.track.size, 0.9)
        eta[self.sectors.index == 3] = 0.3
        profiles = {"a": self.make("a", 0.0, eta), "b": self.make("b", 0.0, 0.92)}
        pairs = cf.build_pairs(profiles, self.sectors)
        self.assertIn("incidente", pairs.sector_reason[0, 3])
        self.assertEqual(pairs.sector_reason[0, 4], "")

    def test_metrics_against_the_zero_baseline(self):
        observed = np.array([0.1, -0.2, 0.3, -0.1])
        zero = cf.error_metrics(np.zeros(4), observed)
        perfect = cf.error_metrics(observed.copy(), observed)
        self.assertAlmostEqual(zero["skill"], 0.0)
        self.assertAlmostEqual(perfect["skill"], 1.0)
        self.assertAlmostEqual(perfect["sign_agreement"], 1.0)
        self.assertAlmostEqual(cf.fit_slope(2.0 * observed, observed), 0.5)

    def test_criteria_need_every_check(self):
        criteria = cf.AcceptanceCriteria()
        good = {"skill": 0.5, "bias_s": 0.0, "mae_zero_s": 0.1, "spearman": 0.8, "sign_agreement": 0.9}
        sessions = {f"s{i}": {"n": 10, "skill": 0.4} for i in range(6)}
        self.assertTrue(criteria.evaluate(good, 0.2, sessions)["aprovado"])
        self.assertFalse(criteria.evaluate(good, -0.1, sessions)["aprovado"])
        self.assertFalse(criteria.evaluate(good, 0.2, dict(list(sessions.items())[:3]))["aprovado"])


if __name__ == "__main__":
    unittest.main()
