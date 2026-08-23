"""Testes do subsistema de aprendizado de tracado (`backend/ml`).

Nenhum teste aqui depende das gravacoes nem do cache de geometria: os dois estao
fora do versionamento (`.gitignore`), e um teste que so passa na maquina de quem
tem 11 GB de telemetria nao e um teste. A pista usada e um circulo sintetico,
onde toda grandeza que o pipeline calcula tem valor fechado conhecido -- o
comprimento de uma trajetoria deslocada, a curvatura dela, o tempo de cada
microsetor -- e e contra esses valores que os modulos sao verificados.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.comparison.lap_vs_reference import compare_lap
from ml.data.recordings import _is_new_lap
from ml.data.samples import flatten
from ml.optimization.evolution import EvolutionConfig, evolve
from ml.optimization.fitness import FitnessEvaluator, FitnessWeights, ShapeReference
from ml.optimization.lap_time_model import simulate, simulate_batch
from ml.optimization.operators import crossover, mutate, tournament_selection
from ml.optimization.representation import build_encoding
from ml.optimization.vehicle_model import G, VehicleEnvelope
from ml.preprocessing.alignment import align_lap, unwrap_distance
from ml.preprocessing.cleaning import clean_lap, sample_gaps, sample_rate_hz
from ml.preprocessing.quality import evaluate_lap
from ml.preprocessing.resampling import lap_time_from_grid, resample_lap
from ml.preprocessing.splits import split_by_session
from ml.track.corners import Corner, detect_corners
from ml.track.geometry import TrackGeometry
from ml.track.microsectors import build_microsectors, split_times, theoretical_best
from ml.track.trajectory import (
    clip_to_corridor,
    corridor_violation,
    curvature,
    path_length,
    resample_control_points,
    world_path,
)

RADIUS = 200.0
WIDTH = 12.0
STEP = 2.0


def circular_track(radius: float = RADIUS, width: float = WIDTH, step: float = STEP):
    """Pista circular de raio conhecido, percorrida no sentido anti-horario.

    Num circulo tudo o que o pipeline calcula tem resposta fechada: a trajetoria
    deslocada de `L` tem comprimento `2*pi*(R + L)` e curvatura `-1/(R + L)`.
    """
    length = 2.0 * math.pi * radius
    count = int(round(length / step))
    used = length / count
    s = np.arange(count, dtype=float) * used
    theta = s / radius

    points = np.column_stack([radius * np.cos(theta), radius * np.sin(theta)])
    tangent = np.column_stack([-np.sin(theta), np.cos(theta)])
    normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
    return TrackGeometry(
        name="circulo",
        length=length,
        step=used,
        s=s,
        x=points[:, 0],
        z=points[:, 1],
        elevation=np.zeros(count),
        tangent=tangent,
        normal=normal,
        curvature=np.full(count, -1.0 / radius),
        width_left=np.full(count, width / 2.0),
        width_right=np.full(count, width / 2.0),
    )


def flat_envelope(lateral_g: float = 2.0, brake_g: float = 2.0, traction_g: float = 1.0):
    speeds = np.linspace(10.0, 90.0, 6)
    return VehicleEnvelope(
        speed_mps=speeds,
        lateral=np.full(speeds.size, lateral_g * G),
        braking=np.full(speeds.size, brake_g * G),
        traction=np.full(speeds.size, traction_g * G),
        top_speed_mps=90.0,
        samples=np.full(speeds.size, 1000.0),
    )


def synthetic_lap(track: TrackGeometry, speed_kmh: float = 108.0, hz: float = 50.0):
    """Amostras de uma volta a velocidade constante sobre a centerline."""
    speed = speed_kmh / 3.6
    duration = track.length / speed
    count = int(duration * hz)
    elapsed = np.arange(count) / hz
    distance = np.mod(elapsed * speed, track.length)
    index = track.index_of(distance)
    return pd.DataFrame(
        {
            "timestamp_s": 1_700_000_000.0 + elapsed,
            "lap_time_s": elapsed,
            "lap_number": np.full(count, 7.0),
            "x": track.x[index],
            "z": track.z[index],
            "speed_kmh": np.full(count, speed_kmh),
            "throttle": np.full(count, 0.8),
            "brake": np.zeros(count),
            "steering": np.zeros(count),
            "gear": np.full(count, 4.0),
            "rpm": np.full(count, 7000.0),
            "lateral_g": np.full(count, speed**2 / RADIUS / G),
            "longitudinal_g": np.zeros(count),
            "heading": np.zeros(count),
            "off_track": np.zeros(count, dtype=bool),
        }
    )


class TrackGeometryTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()

    def test_grid_is_arc_length(self):
        spacing = np.linalg.norm(
            np.diff(np.vstack([self.track.points, self.track.points[:1]]), axis=0), axis=1
        )
        # A corda de um passo e ligeiramente menor que o arco; num raio de 200 m
        # e num passo de 2 m a diferenca esta na quinta casa.
        self.assertAlmostEqual(float(spacing.mean()), self.track.step, places=3)

    def test_corridor_respects_car_width(self):
        low, high = self.track.corridor(car_half_width=1.0, kerb_allowance=0.0)
        self.assertAlmostEqual(float(high[0]), WIDTH / 2.0 - 1.0)
        self.assertAlmostEqual(float(low[0]), -(WIDTH / 2.0 - 1.0))

    def test_projection_recovers_position(self):
        expected_s = np.array([0.0, 100.0, 500.0, 900.0])
        expected_lateral = np.array([0.0, 2.5, -3.0, 4.0])
        world = self.track.to_world(expected_s, expected_lateral)
        recovered_s, recovered_lateral = self.track.project(world)
        np.testing.assert_allclose(recovered_s, expected_s, atol=0.5)
        np.testing.assert_allclose(recovered_lateral, expected_lateral, atol=0.05)

    def test_sequence_projection_is_monotonic(self):
        lateral = 3.0 * np.sin(self.track.s / 120.0)
        world = world_path(self.track, lateral)
        recovered_s, recovered_lateral = self.track.project_sequence(world)
        steps = np.mod(np.diff(recovered_s), self.track.length)
        self.assertTrue(np.all(steps < 10.0), "a projecao pulou de trecho")
        np.testing.assert_allclose(recovered_lateral, lateral, atol=0.05)


class TrajectoryTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()

    def test_offset_trajectory_length(self):
        for offset in (-4.0, 0.0, 4.0):
            lateral = np.full(self.track.size, offset)
            expected = 2.0 * math.pi * (RADIUS + offset)
            self.assertAlmostEqual(path_length(self.track, lateral), expected, delta=0.05)

    def test_offset_trajectory_curvature(self):
        lateral = np.full(self.track.size, 5.0)
        expected = -1.0 / (RADIUS + 5.0)
        values = curvature(self.track, lateral)
        np.testing.assert_allclose(values, expected, rtol=2e-3)

    def test_clip_keeps_trajectory_inside(self):
        lateral = np.full(self.track.size, 50.0)
        clipped = clip_to_corridor(self.track, lateral)
        self.assertTrue(np.all(corridor_violation(self.track, clipped) <= 1e-9))

    def test_control_points_interpolate_smoothly(self):
        control_s = np.linspace(0.0, self.track.length, 24, endpoint=False)
        control_lateral = 3.0 * np.sin(control_s / self.track.length * 2 * math.pi)
        lateral = resample_control_points(self.track, control_s, control_lateral)
        self.assertEqual(lateral.size, self.track.size)
        # A spline periodica fecha o laco: o fim encosta no comeco.
        self.assertLess(abs(lateral[0] - lateral[-1]), 0.2)


class MicrosectorTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.sectors = build_microsectors(self.track, count=12)

    def test_splits_sum_to_lap_time(self):
        total = 90.0
        elapsed = np.linspace(0.0, total, self.track.size, endpoint=False)
        splits = split_times(elapsed, self.sectors, self.track, total=total)
        self.assertAlmostEqual(float(splits.sum()), total, places=6)

    def test_theoretical_best_takes_the_minimum(self):
        first = np.array([1.0, 2.0, 3.0])
        second = np.array([2.0, 1.5, 2.5])
        np.testing.assert_allclose(theoretical_best([first, second]), [1.0, 1.5, 2.5])


class SampleFlatteningTest(unittest.TestCase):
    def test_reads_controls_from_car_physics(self):
        row = flatten(
            {
                "timestamp": 1_700_000_000_000.0,
                "sample": {
                    "lap": 3,
                    "lap_time": 12.5,
                    "world_x": 1.0,
                    "world_z": 2.0,
                    "speedKmh": 200.0,
                    "carPhysics": {
                        "controls": {"throttle": 1.0, "brake": 0.25, "steerAngle": -0.1, "gear": 5},
                        "motion": {"accG": {"lateral": 1.5, "longitudinal": -0.5}},
                        "environment": {"offTrack": False},
                    },
                },
            }
        )
        self.assertEqual(row["throttle"], 1.0)
        self.assertEqual(row["brake"], 0.25)
        self.assertEqual(row["gear"], 5.0)
        self.assertEqual(row["lateral_g"], 1.5)
        self.assertEqual(row["lap_number"], 3.0)
        # Timestamp em milissegundos vira segundos.
        self.assertAlmostEqual(row["timestamp_s"], 1_700_000_000.0)

    def test_missing_values_stay_none(self):
        row = flatten({"sample": {"lap": 1}})
        self.assertIsNone(row["throttle"])
        self.assertIsNone(row["speed_kmh"])


class LapSegmentationTest(unittest.TestCase):
    def test_timer_reset_opens_a_lap(self):
        previous = {"lap_number": 4.0, "lap_time_s": 85.2}
        current = {"lap_number": 4.0, "lap_time_s": 0.1}
        self.assertTrue(_is_new_lap(current, previous))

    def test_lagging_counter_does_not_open_a_lap(self):
        # O contador do jogo so alcanca alguns quadros depois do cronometro.
        previous = {"lap_number": 4.0, "lap_time_s": 0.3}
        current = {"lap_number": 5.0, "lap_time_s": 0.35}
        self.assertFalse(_is_new_lap(current, previous))

    def test_counter_change_without_timer_opens_a_lap(self):
        previous = {"lap_number": 4.0, "lap_time_s": None}
        current = {"lap_number": 5.0, "lap_time_s": None}
        self.assertTrue(_is_new_lap(current, previous))


class CleaningTest(unittest.TestCase):
    def test_percentage_channels_are_rescaled(self):
        frame = pd.DataFrame(
            {
                "timestamp_s": [0.0, 0.1, 0.2],
                "x": [0.0, 1.0, 2.0],
                "z": [0.0, 0.0, 0.0],
                "throttle": [0.0, 50.0, 100.0],
                "brake": [0.0, 0.0, 0.0],
            }
        )
        cleaned, report = clean_lap(frame)
        self.assertIn("throttle", report.rescaled)
        self.assertAlmostEqual(float(cleaned["throttle"].max()), 1.0)

    def test_out_of_range_values_are_clipped(self):
        frame = pd.DataFrame(
            {
                "timestamp_s": [0.0, 0.1],
                "x": [0.0, 1.0],
                "z": [0.0, 0.0],
                "speed_kmh": [100.0, 9_000.0],
            }
        )
        cleaned, report = clean_lap(frame)
        self.assertEqual(report.clipped.get("speed_kmh"), 1)
        self.assertLessEqual(float(cleaned["speed_kmh"].max()), 450.0)

    def test_sample_rate_and_gaps(self):
        frame = pd.DataFrame({"timestamp_s": [0.0, 0.02, 0.04, 1.04]})
        self.assertAlmostEqual(sample_rate_hz(frame), 3.0 / 1.04, places=6)
        largest, count = sample_gaps(frame, threshold=0.5)
        self.assertAlmostEqual(largest, 1.0)
        self.assertEqual(count, 1)


class AlignmentTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()

    def test_unwrap_removes_the_finish_line_jump(self):
        length = 100.0
        wrapped = np.array([90.0, 95.0, 99.0, 2.0, 6.0])
        unwrapped = unwrap_distance(wrapped, length)
        self.assertTrue(np.all(np.diff(unwrapped) > 0))
        self.assertAlmostEqual(float(unwrapped[-1] - unwrapped[0]), 16.0, places=6)

    def test_full_lap_reports_full_coverage(self):
        frame = synthetic_lap(self.track)
        cleaned, _ = clean_lap(frame)
        aligned, report = align_lap(cleaned, self.track)
        self.assertGreater(report.coverage, 0.98)
        self.assertEqual(report.backward_steps, 0)


class ResamplingTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()

    def test_grid_lap_has_one_row_per_grid_point(self):
        cleaned, _ = clean_lap(synthetic_lap(self.track))
        aligned, _ = align_lap(cleaned, self.track)
        grid = resample_lap(aligned, self.track)
        self.assertEqual(len(grid), self.track.size)
        self.assertFalse(grid["speed_kmh"].isna().any())

    def test_clock_starts_at_the_grid_origin_and_is_monotonic(self):
        cleaned, _ = clean_lap(synthetic_lap(self.track))
        aligned, _ = align_lap(cleaned, self.track)
        grid = resample_lap(aligned, self.track)
        elapsed = grid["elapsed_s"].to_numpy()
        self.assertAlmostEqual(float(elapsed[0]), 0.0, places=6)
        self.assertTrue(np.all(np.diff(elapsed) >= -1e-9))

    def test_lap_time_matches_constant_speed(self):
        speed_kmh = 108.0
        cleaned, _ = clean_lap(synthetic_lap(self.track, speed_kmh=speed_kmh))
        aligned, _ = align_lap(cleaned, self.track)
        grid = resample_lap(aligned, self.track)
        expected = self.track.length / (speed_kmh / 3.6)
        self.assertAlmostEqual(lap_time_from_grid(grid), expected, delta=0.15)


class QualityGateTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()

    def _aligned(self, frame):
        cleaned, _ = clean_lap(frame)
        return align_lap(cleaned, self.track)

    def test_clean_lap_passes(self):
        # A volta sintetica dura 41 s no circulo de 1257 m; o gate de duracao e
        # calibrado para Interlagos, entao aqui ele e afrouxado de proposito.
        from ml.config import LapQualityGates

        aligned, report = self._aligned(synthetic_lap(self.track))
        quality = evaluate_lap(
            aligned, self.track, report, LapQualityGates(min_lap_seconds=10.0)
        )
        self.assertTrue(quality.valid, quality.reasons)

    def test_stopped_car_is_rejected(self):
        from ml.config import LapQualityGates

        frame = synthetic_lap(self.track)
        frame.loc[: len(frame) // 3, "speed_kmh"] = 0.0
        aligned, report = self._aligned(frame)
        quality = evaluate_lap(
            aligned, self.track, report, LapQualityGates(min_lap_seconds=10.0)
        )
        self.assertFalse(quality.valid)
        self.assertTrue(any("parado" in reason for reason in quality.reasons))

    def test_lap_without_pedals_is_rejected(self):
        from ml.config import LapQualityGates

        # Posicao e velocidade perfeitas, `carPhysics` ausente -- exatamente o
        # que a sessao `2026-06-14_12-23-46` gravou em 12 voltas.
        frame = synthetic_lap(self.track)
        for channel in ("throttle", "brake", "steering", "lateral_g", "longitudinal_g"):
            frame[channel] = np.nan
        aligned, report = self._aligned(frame)
        quality = evaluate_lap(
            aligned, self.track, report, LapQualityGates(min_lap_seconds=10.0)
        )
        self.assertFalse(quality.valid)
        self.assertTrue(any("canais ausentes" in reason for reason in quality.reasons))

    def test_partial_lap_is_rejected(self):
        from ml.config import LapQualityGates

        frame = synthetic_lap(self.track).iloc[: int(0.6 * len(synthetic_lap(self.track)))]
        aligned, report = self._aligned(frame)
        quality = evaluate_lap(
            aligned, self.track, report, LapQualityGates(min_lap_seconds=10.0)
        )
        self.assertFalse(quality.valid)
        self.assertTrue(any("faltam" in reason for reason in quality.reasons))


class SplitTest(unittest.TestCase):
    def test_sessions_do_not_cross_parts(self):
        laps = pd.DataFrame(
            {
                "lap_id": [f"s{i // 10}#{i}" for i in range(60)],
                "session_id": [f"s{i // 10}" for i in range(60)],
                "lap_time_s": np.linspace(85.0, 95.0, 60),
            }
        )
        split = split_by_session(laps)
        self.assertEqual(len(split.train) + len(split.validation) + len(split.test), 60)
        for session, part in split.sessions.items():
            members = [lap for lap in getattr(split, part) if lap.startswith(f"{session}#")]
            self.assertEqual(len(members), 10)
        self.assertGreater(len(split.train), len(split.test))


class LapTimeModelTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.envelope = flat_envelope()

    def test_constant_radius_matches_closed_form(self):
        lateral = np.zeros(self.track.size)
        result = simulate(self.track, lateral, self.envelope)
        # Num circulo o limite de curva e constante e a volta e ele o tempo todo.
        expected_speed = math.sqrt(2.0 * G * RADIUS)
        self.assertAlmostEqual(float(result.speed_mps.mean()), expected_speed, delta=0.5)
        self.assertAlmostEqual(
            result.lap_time_s, self.track.length / expected_speed, delta=0.3
        )

    def test_more_grip_is_faster(self):
        lateral = np.zeros(self.track.size)
        slow = simulate(self.track, lateral, flat_envelope(lateral_g=1.5)).lap_time_s
        fast = simulate(self.track, lateral, flat_envelope(lateral_g=2.5)).lap_time_s
        self.assertLess(fast, slow)

    def test_weaving_is_slower_than_a_clean_line(self):
        clean = np.zeros(self.track.size)
        weaving = 4.0 * np.sin(self.track.s / 15.0)
        times, _, _ = simulate_batch(
            self.track, np.vstack([clean, weaving]), self.envelope
        )
        self.assertLess(times[0], times[1])

    def test_batch_matches_single(self):
        lateral = 2.0 * np.sin(self.track.s / 80.0)
        single = simulate(self.track, lateral, self.envelope).lap_time_s
        batch, _, _ = simulate_batch(self.track, lateral[None, :], self.envelope)
        self.assertAlmostEqual(single, float(batch[0]), places=6)


class EncodingTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.encoding = build_encoding(self.track, spacing_m=25.0)

    def test_decode_stays_inside_the_track(self):
        generator = np.random.default_rng(7)
        population = self.encoding.random(generator, 12)
        for genome in population:
            lateral = self.encoding.decode(genome)
            self.assertTrue(np.all(corridor_violation(self.track, lateral) <= 1e-9))

    def test_encode_decode_round_trip(self):
        lateral = 2.0 * np.sin(self.track.s / 100.0)
        genome = self.encoding.encode(lateral)
        recovered = self.encoding.decode(genome)
        self.assertLess(float(np.abs(recovered - lateral).max()), 0.6)


class OperatorTest(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.encoding = build_encoding(self.track, spacing_m=25.0)
        self.generator = np.random.default_rng(11)
        self.population = self.encoding.random(self.generator, 20)

    def test_tournament_prefers_lower_cost(self):
        cost = np.arange(20, dtype=float)
        chosen = tournament_selection(self.population, cost, 200, self.generator, pressure=4)
        # Com pressao 4 o custo medio dos escolhidos cai bem abaixo da media.
        indices = [np.argmin(np.abs(self.population - row).sum(axis=1)) for row in chosen]
        self.assertLess(float(np.mean(cost[indices])), 10.0)

    def test_crossover_keeps_genes_from_the_parents(self):
        children = crossover(
            self.population[:10], self.population[10:], self.generator, rate=1.0, segment_share=1.0
        )
        for child, first, second in zip(children, self.population[:10], self.population[10:]):
            from_either = np.isclose(child, first) | np.isclose(child, second)
            self.assertTrue(np.all(from_either))

    def test_mutation_stays_within_bounds(self):
        mutated = mutate(self.population, self.encoding, self.generator, rate=1.0, amplitude_m=5.0)
        self.assertTrue(np.all(mutated >= self.encoding.lower - 1e-9))
        self.assertTrue(np.all(mutated <= self.encoding.upper + 1e-9))


class EvolutionTest(unittest.TestCase):
    def test_search_improves_on_a_bad_start(self):
        track = circular_track()
        encoding = build_encoding(track, spacing_m=25.0)
        evaluator = FitnessEvaluator(
            track,
            encoding,
            flat_envelope(),
            ShapeReference(weaving=0.05, curvature_jerk=1e-3),
            FitnessWeights(surrogate_weight=0.0),
        )
        # Populacao inicial serpenteando: ha o que melhorar, e o alvo -- a linha
        # limpa -- e conhecido.
        generator = np.random.default_rng(3)
        seed = encoding.encode(4.0 * np.sin(track.s / 12.0))
        population = np.vstack([seed + generator.normal(0, 0.3, encoding.genes) for _ in range(24)])

        result = evolve(
            evaluator,
            encoding,
            population,
            EvolutionConfig(generations=25, population_size=24, seed=5),
        )
        self.assertLess(result.best_cost, result.initial_cost)
        self.assertTrue(np.all(corridor_violation(track, result.best_lateral) <= 1e-9))


class ComparisonTest(unittest.TestCase):
    def test_whole_circle_is_one_corner(self):
        track = circular_track()
        corners = detect_corners(track, threshold=1.0 / 500.0, min_length_m=50.0)
        self.assertEqual(len(corners), 1)
        self.assertAlmostEqual(corners[0].min_radius_m, RADIUS, delta=1.0)
        self.assertEqual(corners[0].direction, -1)

    def test_late_braking_is_reported(self):
        track = circular_track()
        sectors = build_microsectors(track, count=8)
        # Curva declarada a mao: num circulo a deteccao acha uma curva so, com
        # entrada e apice no mesmo ponto, e ai nao existe "antes da curva" onde
        # procurar o ponto de frenagem.
        corner = [
            Corner(
                index=0,
                start_s=float(track.s[260]),
                apex_s=float(track.s[300]),
                end_s=float(track.s[360]),
                direction=-1,
                min_radius_m=RADIUS,
                mean_radius_m=RADIUS,
                length_m=float(100 * track.step),
            )
        ]

        size = track.size
        base = pd.DataFrame(
            {
                "elapsed_s": np.linspace(0.0, 60.0, size, endpoint=False),
                "lateral": np.zeros(size),
                "speed_kmh": np.full(size, 120.0),
                "brake": np.zeros(size),
                "throttle": np.full(size, 0.9),
            }
        )
        reference = base.copy()
        # Ambas as frenagens caem dentro da janela de aproximacao da curva
        # declarada acima (indices 135..300).
        reference.loc[150:170, "brake"] = 0.8
        lap = base.copy()
        lap.loc[170:190, "brake"] = 0.8          # freou 20 pontos = 40 m depois
        lap["elapsed_s"] = np.linspace(0.0, 62.0, size, endpoint=False)

        comparison = compare_lap(
            "teste", lap, reference, track, sectors, corner, lap_total=62.0, reference_total=60.0
        )
        self.assertAlmostEqual(comparison.delta_s, 2.0, places=6)
        self.assertEqual(len(comparison.sectors), 8)
        deltas = [c.braking_delta_m for c in comparison.corners if c.braking_delta_m]
        self.assertTrue(any(delta > 30.0 for delta in deltas), deltas)


if __name__ == "__main__":
    unittest.main()
