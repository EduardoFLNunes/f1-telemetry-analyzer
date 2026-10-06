"""Testes do alinhamento da linha da F1 a geometria oficial (pedido 22).

Nada aqui le a volta importada nem o cache de geometria: a pista e uma curva
fechada sintetica, com curvas para os dois lados, e a linha da F1 e uma linha
conhecida passada por uma transformacao conhecida.
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.external.f1_line import (  # noqa: E402
    Similarity,
    align,
    excess_on_grid,
    excess_summary,
    infer_unit,
    load_xy,
    mirror,
    project_to_grid,
    sector_median_difference,
    verdict,
    worst_sectors,
)
from ml.track.geometry import TrackGeometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402

HALF_WIDTH = 6.0
STEP = 2.0


def synthetic_track(centre=(2000.0, -1500.0)) -> TrackGeometry:
    """Curva fechada de ~4,1 km com trechos concavos (curvas para os dois lados).

    A normal segue `load_geometry`: `normal = (t_z, -t_x)`, o lado que o ML
    chama de esquerda (ADR 0003).
    """
    theta = np.linspace(0.0, 2.0 * math.pi, 40000, endpoint=False)
    radius = 600.0 * (1.0 + 0.15 * np.cos(3.0 * theta) + 0.08 * np.sin(5.0 * theta))
    dense = np.column_stack([radius * np.cos(theta), radius * np.sin(theta)]) + np.asarray(centre)
    closed = np.vstack([dense, dense[:1]])
    cumulative = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))])
    length = float(cumulative[-1])
    count = int(round(length / STEP))
    step = length / count
    s = np.arange(count) * step
    x = np.interp(s, cumulative, closed[:, 0])
    z = np.interp(s, cumulative, closed[:, 1])
    points = np.column_stack([x, z])
    derivative = (np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)) / (2.0 * step)
    tangent = derivative / np.linalg.norm(derivative, axis=1, keepdims=True)
    normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
    turn = (np.roll(tangent, -1, axis=0) - np.roll(tangent, 1, axis=0)) / (2.0 * step)
    return TrackGeometry(
        name="sintetica",
        length=length,
        step=step,
        s=s,
        x=x,
        z=z,
        elevation=np.zeros(count),
        tangent=tangent,
        normal=normal,
        curvature=np.sum(turn * normal, axis=1),
        width_left=np.full(count, HALF_WIDTH),
        width_right=np.full(count, HALF_WIDTH),
    )


def irregular_s(track: TrackGeometry, count: int = 640, start: float = 1234.0, seed: int = 7) -> np.ndarray:
    """`count` posicoes em `s`, espacadas de forma irregular, uma volta a partir de `start`."""
    rng = np.random.default_rng(seed)
    gaps = rng.uniform(0.3, 1.7, count)
    positions = np.concatenate([[0.0], np.cumsum(gaps[:-1])])
    positions *= (track.length - 3.0) / (positions[-1] + gaps[-1])
    return np.mod(start + positions, track.length)


def to_foreign(points: np.ndarray, true: Similarity) -> np.ndarray:
    """Inverso de `true`: leva pontos da pista para o sistema "de fora"."""
    rotated = (np.asarray(points) - true.translation) @ true.matrix / true.scale
    return mirror(rotated) if true.mirrored else rotated


class AlignmentRecoveryTest(unittest.TestCase):
    """Uma linha conhecida, uma transformacao conhecida: o alinhamento a recupera."""

    @classmethod
    def setUpClass(cls):
        cls.track = synthetic_track()

    def _recover(self, true: Similarity, lateral_amplitude: float, noise_m: float):
        s = irregular_s(self.track)
        lateral = lateral_amplitude * np.sin(2.0 * math.pi * 7.0 * s / self.track.length)
        line = self.track.to_world(s, lateral)
        if noise_m:
            line = line + np.random.default_rng(3).normal(0.0, noise_m, line.shape)
        foreign = to_foreign(line, true)
        fitted, info = align(foreign, self.track)
        self.assertTrue(info["icp"]["convergiu"])
        return fitted, foreign, line

    def _check(self, fitted: Similarity, true: Similarity, foreign, line,
               scale_rel: float, angle_deg: float, shift_m: float, line_m: float):
        self.assertEqual(fitted.mirrored, true.mirrored)
        self.assertLess(abs(fitted.scale / true.scale - 1.0), scale_rel)
        angle_error = (fitted.rotation_deg - true.rotation_deg + 180.0) % 360.0 - 180.0
        self.assertLess(abs(angle_error), angle_deg)
        # A translacao e medida no centroide da linha. O vetor `translation` e a
        # imagem da origem do sistema de fora, que fica a ~5 km da linha: ali
        # 0,02 grau de rotacao ja vira 1,6 m, sem a linha sair do lugar.
        centroid = foreign.mean(axis=0, keepdims=True)
        self.assertLess(float(np.linalg.norm(fitted.apply(centroid) - true.apply(centroid))), shift_m)
        moved = fitted.apply(foreign)
        self.assertLess(float(np.max(np.linalg.norm(moved - true.apply(foreign), axis=1))), line_m)

    def test_recovers_mirrored_transform_in_decimetres(self):
        true = Similarity(0.1, math.radians(37.0), np.array([-350.0, 820.0]), mirrored=True)
        fitted, foreign, line = self._recover(true, lateral_amplitude=0.0, noise_m=0.0)
        self._check(fitted, true, foreign, line, scale_rel=1e-4, angle_deg=0.01, shift_m=0.05, line_m=0.05)

    def test_recovers_proper_transform_with_a_racing_line(self):
        # Uma linha que nao e a central (1,5 m para os dois lados) e com ruido de
        # 0,2 m: o ICP contra a linha central continua recuperando a transformacao.
        true = Similarity(0.1, math.radians(-121.0), np.array([4100.0, -90.0]), mirrored=False)
        fitted, foreign, line = self._recover(true, lateral_amplitude=1.5, noise_m=0.2)
        self._check(fitted, true, foreign, line, scale_rel=1e-3, angle_deg=0.1, shift_m=0.5, line_m=0.5)

    def test_recovers_mirrored_transform_with_a_racing_line(self):
        true = Similarity(0.1, math.radians(200.0), np.array([-700.0, 2500.0]), mirrored=True)
        fitted, foreign, line = self._recover(true, lateral_amplitude=1.5, noise_m=0.2)
        self._check(fitted, true, foreign, line, scale_rel=1e-3, angle_deg=0.1, shift_m=0.5, line_m=0.5)


class LateralSignTest(unittest.TestCase):
    """Convencao do ADR 0003: lateral positivo a esquerda, a `+normal` da pista."""

    @classmethod
    def setUpClass(cls):
        cls.track = synthetic_track()

    def test_line_to_the_left_projects_positive_on_the_grid(self):
        s = irregular_s(self.track)
        for offset in (3.0, -2.0):
            grid = project_to_grid(self.track, self.track.to_world(s, np.full(s.size, offset)))
            self.assertEqual(grid.grid_lateral.size, self.track.size)
            np.testing.assert_allclose(grid.grid_lateral, offset, atol=0.05)
            self.assertGreater(grid.coverage, 0.99)
            self.assertEqual(grid.backward_steps, 0)

    def test_sign_survives_a_mirrored_source(self):
        # A linha alterna os lados (3 m a esquerda, depois a direita); o sistema
        # de fora e espelhado. Depois do alinhamento cada trecho continua do
        # mesmo lado: o espelho nao troca o sinal.
        #
        # Nao da para usar um deslocamento constante aqui: contra a linha
        # central, uma linha toda 3 m a esquerda se confunde com uma escala um
        # pouco diferente, e o ICP a traz para perto do centro. Pelo mesmo
        # motivo a onda de +-3 m sai com um vies de alguns decimetros; o teste
        # e do sinal, por isso a tolerancia do valor e de 1 m.
        s = irregular_s(self.track)
        lateral = 3.0 * np.sign(np.sin(2.0 * math.pi * 5.0 * s / self.track.length))
        line = self.track.to_world(s, lateral)
        true = Similarity(0.1, math.radians(75.0), np.array([300.0, 300.0]), mirrored=True)
        fitted, _ = align(to_foreign(line, true), self.track)
        grid = project_to_grid(self.track, fitted.apply(to_foreign(line, true)))
        self.assertTrue(fitted.mirrored)
        expected = 3.0 * np.sign(np.sin(2.0 * math.pi * 5.0 * self.track.s / self.track.length))
        steady = np.abs(np.sin(2.0 * math.pi * 5.0 * self.track.s / self.track.length)) > 0.1
        np.testing.assert_array_equal(np.sign(grid.grid_lateral[steady]), np.sign(expected[steady]))
        np.testing.assert_allclose(grid.grid_lateral[steady], expected[steady], atol=1.0)

    def test_left_side_is_plus_normal(self):
        # `to_world` com lateral positivo anda para `+normal`, e `project` devolve o mesmo sinal.
        s = np.array([100.0, 1500.0, 3000.0])
        left = self.track.to_world(s, np.full(3, 2.5))
        index = self.track.index_of(s)
        offset = np.sum((left - self.track.points[index]) * self.track.normal[index], axis=1)
        self.assertTrue(np.all(offset > 0))
        _, lateral = self.track.project(left)
        np.testing.assert_allclose(lateral, 2.5, atol=0.01)


class UnitTest(unittest.TestCase):
    def test_unit_comes_from_the_perimeter(self):
        track = synthetic_track()
        metres = track.to_world(irregular_s(track), np.zeros(640))
        self.assertEqual(infer_unit(metres, track.length)["unidade"], "m")
        self.assertEqual(infer_unit(metres * 10.0, track.length)["unidade"], "dm")
        self.assertEqual(infer_unit(metres * 100.0, track.length)["unidade"], "cm")


class ExcessAndVerdictTest(unittest.TestCase):
    def test_excess_is_zero_inside_and_the_overshoot_outside(self):
        track = synthetic_track()
        low, high = track.corridor()
        lateral = np.zeros(track.size)
        lateral[:10] = high[:10] + 0.7
        lateral[10:20] = low[10:20] - 0.3
        excess = excess_on_grid(track, lateral)
        np.testing.assert_allclose(excess[:10], 0.7)
        np.testing.assert_allclose(excess[10:20], 0.3)
        self.assertTrue(np.all(excess[20:] == 0.0))
        summary = excess_summary(excess)
        self.assertEqual(summary["pontos_fora"], 20)
        self.assertAlmostEqual(summary["max_m"], 0.7)
        worst = worst_sectors(build_microsectors(track), excess, top=5)
        self.assertEqual(worst[0]["microsetor"], 0)
        self.assertAlmostEqual(worst[0]["excesso_max_m"], 0.7)

    def test_verdict_uses_both_limits(self):
        self.assertTrue(verdict({"fracao_fora": 0.10, "p95_m": 1.0})["aceito"])
        self.assertFalse(verdict({"fracao_fora": 0.1001, "p95_m": 0.2})["aceito"])
        self.assertFalse(verdict({"fracao_fora": 0.02, "p95_m": 1.01})["aceito"])
        self.assertEqual(verdict({"fracao_fora": 0.5, "p95_m": 3.0})["veredito"], "não aceito")


class ReadingTest(unittest.TestCase):
    def test_reads_only_position(self):
        samples = [
            {"x": float(i), "y": float(-i), "speedKmh": 300.0, "throttle": 1.0, "brake": 0.0, "elapsedS": i * 0.1}
            for i in range(20)
        ]
        payload = {"metadata": {"referenceId": "teste", "lapTime": 83.4}, "samples": samples}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "volta.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            points, identity = load_xy(path)
        self.assertEqual(points.shape, (20, 2))
        np.testing.assert_allclose(points[:, 0], np.arange(20))
        np.testing.assert_allclose(points[:, 1], -np.arange(20))
        self.assertEqual(identity["referenceId"], "teste")
        self.assertNotIn("lapTime", identity)

    def test_missing_position_is_refused(self):
        samples = [{"x": float(i), "y": float(i)} for i in range(20)]
        del samples[5]["y"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "volta.json"
            path.write_text(json.dumps({"samples": samples}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_xy(path)


class ComparisonTest(unittest.TestCase):
    def test_difference_is_line_minus_median(self):
        track = synthetic_track()
        sectors = build_microsectors(track)
        laps = np.vstack([np.full(track.size, v) for v in (-1.0, 0.0, 0.5)])
        per_sector, median_line = sector_median_difference(sectors, np.full(track.size, 1.0), laps)
        np.testing.assert_allclose(median_line, 0.0)
        np.testing.assert_allclose(per_sector, 1.0)


if __name__ == "__main__":
    unittest.main()
