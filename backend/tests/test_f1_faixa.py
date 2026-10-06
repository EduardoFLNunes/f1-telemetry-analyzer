"""Testes do alinhamento das voltas secas, da incerteza e da faixa da F1 (pedido 23, Parte C).

Nada aqui usa a internet nem o cache: a pista e a curva sintetica do pedido 22
e as linhas e transformacoes sao conhecidas.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.external import f1_band  # noqa: E402
from ml.external.f1_line import (  # noqa: E402
    GridLine,
    Similarity,
    align_fixed_scale,
    refine_icp_session,
)
from ml.track.microsectors import build_microsectors  # noqa: E402
from tests.test_fastf1_alinhamento import irregular_s, synthetic_track, to_foreign  # noqa: E402


# ------------------------------------------------------- V1 e V2 ---

class VariantRecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.track = synthetic_track()

    def _line(self, amplitude, start, seed):
        s = irregular_s(self.track, start=start, seed=seed)
        lateral = amplitude * np.sin(2.0 * math.pi * 7.0 * s / self.track.length)
        return self.track.to_world(s, lateral)

    def _check(self, fitted, true, foreign, angle_deg=0.01, centroid_m=0.05):
        self.assertEqual(fitted.mirrored, true.mirrored)
        error = (fitted.rotation_deg - true.rotation_deg + 180.0) % 360.0 - 180.0
        self.assertLess(abs(error), angle_deg)
        centroid = foreign.mean(axis=0, keepdims=True)
        self.assertLess(float(np.linalg.norm(fitted.apply(centroid) - true.apply(centroid))), centroid_m)

    def test_v1_recovers_rotation_and_translation_with_the_fixed_scale(self):
        true = Similarity(0.1, math.radians(-63.0), np.array([900.0, -2400.0]), mirrored=True)
        foreign = to_foreign(self._line(0.0, 1234.0, 7), true)
        # Partida do metodo principal, um pouco errada em escala, angulo e posicao.
        start = Similarity(0.1004, math.radians(-62.0), true.translation + np.array([6.0, -4.0]), mirrored=True)
        fitted, info = align_fixed_scale(foreign, self.track, start, 0.1)
        self.assertTrue(info["convergiu"])
        self.assertEqual(fitted.scale, 0.1)
        self._check(fitted, true, foreign)

    def test_v2_recovers_one_transform_shared_by_several_laps(self):
        true = Similarity(0.0998, math.radians(141.0), np.array([-1500.0, 300.0]), mirrored=True)
        lines = [self._line(amplitude, start, seed)
                 for amplitude, start, seed in ((0.0, 100.0, 1), (0.0, 2100.0, 2), (0.0, 3300.0, 3))]
        foreign = [to_foreign(line, true) for line in lines]
        start = Similarity(0.1005, math.radians(139.5), true.translation + np.array([-8.0, 5.0]), mirrored=True)
        fitted, info = refine_icp_session(foreign, self.track, start)
        self.assertTrue(info["convergiu"])
        self.assertEqual(info["voltas"], 3)
        self.assertLess(abs(fitted.scale / true.scale - 1.0), 1e-4)
        self._check(fitted, true, np.vstack(foreign))

    def test_transform_spread_is_measured_at_the_centroid(self):
        base = Similarity(0.1, math.radians(30.0), np.array([100.0, 200.0]), mirrored=True)
        tilted = Similarity(0.1, math.radians(30.5), np.array([100.0, 200.0]), mirrored=True)
        centroid = np.array([0.0, 0.0])
        spread = f1_band.transform_spread([base, base, tilted], centroid)
        self.assertAlmostEqual(spread["rotacao_graus"]["amplitude"], 0.5, places=6)
        self.assertAlmostEqual(spread["centroide_m"]["distancia_max_a_mediana"], 0.0, places=6)
        self.assertEqual(spread["espelhadas"], 3)


# ------------------------------------------------------------ faixa ---

class BandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.track = synthetic_track()
        cls.sectors = build_microsectors(cls.track)

    def test_known_percentiles_with_equal_weight_per_lap(self):
        laterals = np.vstack([np.full(self.track.size, float(v)) for v in range(11)])
        faixa = f1_band.band(laterals)
        np.testing.assert_allclose(faixa["p10"], 1.0)
        np.testing.assert_allclose(faixa["p50"], 5.0)
        np.testing.assert_allclose(faixa["p90"], 9.0)
        self.assertTrue((faixa["n"] == 11).all())
        np.testing.assert_allclose(f1_band.sector_median(self.sectors, faixa["p50"]), 5.0)

    def test_inside_rule_per_microsector_and_the_side(self):
        p10 = np.full(self.track.size, -1.0)
        p90 = np.full(self.track.size, 1.0)
        line = np.zeros(self.track.size)
        first = np.flatnonzero(self.sectors.index == 0)
        second = np.flatnonzero(self.sectors.index == 1)
        third = np.flatnonzero(self.sectors.index == 2)
        line[first[int(0.6 * len(first)):]] = 3.0       # 60% dentro: conta como dentro
        line[second[int(0.4 * len(second)):]] = -4.0    # 40% dentro: fora, pela direita
        line[third] = 2.5                                # todo fora, pela esquerda
        result = f1_band.compare_to_band(self.sectors, line, p10, p90)
        rows = result["por_microsetor"]
        self.assertTrue(rows[0]["dentro"])
        self.assertFalse(rows[1]["dentro"])
        self.assertFalse(rows[2]["dentro"])
        self.assertEqual(result["microsetores_dentro"], self.sectors.count - 2)
        self.assertEqual(rows[1]["lado"], "direita")
        self.assertAlmostEqual(rows[1]["distancia_mediana_ate_a_borda_m"], -3.0)
        self.assertEqual(rows[2]["lado"], "esquerda")
        self.assertAlmostEqual(rows[2]["distancia_mediana_ate_a_borda_m"], 1.5)
        self.assertEqual([row["microsetor"] for row in result["mais_fora"][:2]], [1, 2])

    def test_minimum_to_form_the_band(self):
        self.assertTrue(f1_band.band_is_formed(20, 3))
        self.assertFalse(f1_band.band_is_formed(19, 5))
        self.assertFalse(f1_band.band_is_formed(40, 2))

    def test_session_spread_is_the_range_of_session_medians(self):
        laterals = np.vstack([np.full(self.track.size, v) for v in (0.0, 0.2, 1.0, 1.4, -0.5)])
        spread = f1_band.session_spread(self.sectors, laterals, ["a", "a", "b", "b", "c"])
        np.testing.assert_allclose(spread["amplitude"], 1.2 - (-0.5))
        self.assertEqual(spread["voltas_por_sessao"], {"a": 2, "b": 2, "c": 1})


# -------------------------------------------------------- criterio ---

class LapCriterionTest(unittest.TestCase):
    GOOD = {"fracao_fora": 0.05, "p95_m": 0.0, "max_m": 0.8}

    def test_each_condition_rejects_alone(self):
        self.assertTrue(f1_band.lap_verdict(0.995, 40.0, self.GOOD)["aceita"])
        self.assertFalse(f1_band.lap_verdict(0.985, 40.0, self.GOOD)["cobertura_ok"])
        self.assertFalse(f1_band.lap_verdict(0.995, 81.0, self.GOOD)["buraco_ok"])
        self.assertFalse(f1_band.lap_verdict(0.995, 40.0, {**self.GOOD, "fracao_fora": 0.11})["aceita"])
        self.assertFalse(f1_band.lap_verdict(0.995, 40.0, {**self.GOOD, "p95_m": 1.2})["aceita"])
        self.assertTrue(f1_band.lap_verdict(0.99, 80.0, {**self.GOOD, "fracao_fora": 0.10, "p95_m": 1.0})["aceita"])

    def test_largest_gap_counts_the_closing_gap(self):
        length = 4000.0
        s = np.array([10.0, 50.0, 140.0, 3900.0, 3970.0])
        line = GridLine(s=s, lateral=np.zeros(5), s_unwrapped=s, grid_lateral=np.zeros(10),
                        coverage=(s[-1] - s[0]) / length, backward_steps=0)
        self.assertAlmostEqual(f1_band.max_gap_m(line, length), 3760.0)
        # Amostras a cada 50 m de 100 a 3800 m: o maior buraco e o que fecha a volta, 300 m.
        s2 = np.arange(100.0, 3800.1, 50.0)
        line2 = GridLine(s=s2, lateral=np.zeros(s2.size), s_unwrapped=s2, grid_lateral=np.zeros(10),
                         coverage=(s2[-1] - s2[0]) / length, backward_steps=0)
        self.assertAlmostEqual(f1_band.max_gap_m(line2, length), 300.0)

    def test_fit_lap_rejects_a_lap_with_a_hole_and_accepts_the_clean_one(self):
        track = synthetic_track()
        true = Similarity(0.1, math.radians(12.0), np.array([300.0, -900.0]), mirrored=True)
        s = np.mod(500.0 + np.arange(0.0, track.length - 6.0, 6.0), track.length)
        clean = to_foreign(track.to_world(s, np.zeros_like(s)), true)
        fit = f1_band.fit_lap(track, clean)
        self.assertTrue(fit.verdict["aceita"], fit.verdict)
        holed = np.delete(clean, np.arange(200, 220), axis=0)   # 20 amostras de 6 m: buraco de 126 m
        fit = f1_band.fit_lap(track, holed)
        self.assertFalse(fit.verdict["buraco_ok"])
        self.assertGreater(fit.verdict["maior_buraco_m"], 80.0)
        self.assertFalse(fit.verdict["aceita"])


if __name__ == "__main__":
    unittest.main()
