"""Origem das voltas (ADR 0014): quem pilotou, relogio plausivel, duplicatas.

Tudo sintetico: nenhum teste depende das gravacoes.
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

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.telemetry.channels import ai_controlled  # noqa: E402
from ml.data import origin  # noqa: E402
from ml.data.origin_signals import lap_signals, steering_reversals  # noqa: E402
from ml.data.samples import flatten  # noqa: E402
from ml.track.geometry import TrackGeometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402


def circular_track(radius: float = 200.0, step: float = 2.0) -> TrackGeometry:
    length = 2.0 * math.pi * radius
    count = int(round(length / step))
    used = length / count
    s = np.arange(count, dtype=float) * used
    theta = s / radius
    tangent = np.column_stack([-np.sin(theta), np.cos(theta)])
    return TrackGeometry(
        name="circulo",
        length=length,
        step=used,
        s=s,
        x=radius * np.cos(theta),
        z=radius * np.sin(theta),
        elevation=np.zeros(count),
        tangent=tangent,
        normal=np.column_stack([tangent[:, 1], -tangent[:, 0]]),
        curvature=np.full(count, -1.0 / radius),
        width_left=np.full(count, 6.0),
        width_right=np.full(count, 6.0),
    )


class RecorderTests(unittest.TestCase):
    """O gravador registra quem pilota em toda amostra e o carro nos metadados."""

    def source(self, *parts):
        return BACKEND.joinpath(*parts).read_text(encoding="utf-8")

    def test_the_adapter_reads_the_physics_page_field(self):
        self.assertIn('("isAIControlled", c_int)', self.source("core", "assetto_adapter.py"))
        self.assertIn('"is_ai_controlled": bool(self.physics.isAIControlled)', self.source("core", "assetto_adapter.py"))

    def test_the_reader_carries_it_through(self):
        self.assertIn('"is_ai_controlled"', self.source("core", "telemetry", "telemetry_reader_impl.py"))

    def test_the_sample_model_types_it(self):
        from core.telemetry.telemetry_models import TelemetrySample

        self.assertIs(TelemetrySample.from_dict({"timestamp": 1, "is_ai_controlled": True}).isAIControlled, True)
        self.assertIs(TelemetrySample.from_dict({"timestamp": 1, "isAIControlled": 0}).isAIControlled, False)
        self.assertIsNone(TelemetrySample.from_dict({"timestamp": 1}).isAIControlled)

    def test_every_recorded_sample_carries_it(self):
        from core.car_physics import build_player_car_physics
        from core.telemetry.telemetry_models import TelemetrySample

        sample = TelemetrySample.from_dict({"timestamp": 1, "speed": 30.0, "is_ai_controlled": True})
        self.assertIs(build_player_car_physics(sample)["controls"]["isAIControlled"], True)
        self.assertIn("isAIControlled", build_player_car_physics(None)["controls"])

    def test_the_session_metadata_names_the_car(self):
        self.assertIn('"carModel": source_manager.current_car_model()', self.source("main.py"))


class ChannelTests(unittest.TestCase):
    def test_nested_top_level_and_absent(self):
        self.assertIs(ai_controlled({"carPhysics": {"controls": {"isAIControlled": True}}}), True)
        self.assertIs(ai_controlled({"sample": {"isAIControlled": False}}), False)
        self.assertIs(ai_controlled({"is_ai_controlled": 1}), True)
        self.assertIsNone(ai_controlled({"throttle": 1.0, "carPhysics": {"controls": {"gear": 3}}}))

    def test_flatten_keeps_the_difference_between_absent_and_false(self):
        self.assertIsNone(flatten({"sample": {"lap": 1}})["ai_controlled"])
        recorded = flatten({"sample": {"lap": 1, "carPhysics": {"controls": {"isAIControlled": False}}}})
        self.assertIs(recorded["ai_controlled"], False)


class LapOriginTests(unittest.TestCase):
    def test_constant_flag(self):
        self.assertEqual(origin.lap_origin([False] * 5), origin.HUMAN)
        self.assertEqual(origin.lap_origin([True] * 5), origin.AI)

    def test_flag_changes_within_the_lap(self):
        self.assertEqual(origin.lap_origin([False, False, True, False]), origin.MIXED)

    def test_no_field(self):
        self.assertEqual(origin.lap_origin([None, None]), origin.UNKNOWN)
        self.assertEqual(origin.lap_origin([float("nan")] * 3), origin.UNKNOWN)

    def test_field_missing_in_part_of_the_lap_is_not_human(self):
        self.assertEqual(origin.lap_origin([False, None, False]), origin.UNKNOWN)

    def test_ai_share(self):
        self.assertAlmostEqual(origin.ai_share([True, False, False, None]), 1 / 3)
        self.assertTrue(math.isnan(origin.ai_share([None])))


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.track = circular_track()
        self.sectors = build_microsectors(self.track, 60)
        speed = 30.0
        self.grid = pd.DataFrame(
            {
                "elapsed_s": self.track.s / speed,
                "lap_time_s": np.full(self.track.size, self.track.length / speed),
                "speed_kmh": np.full(self.track.size, speed * 3.6),
                "lateral": np.zeros(self.track.size),
            }
        )

    def test_a_consistent_lap_agrees(self):
        check = origin.clock_check(self.grid, self.track, self.sectors)
        self.assertEqual(len(check), 60)
        self.assertLess(check["diferenca_s"].abs().max(), 1e-6)
        self.assertTrue(origin.clock_summary(check)["relogio_verificado"])

    def test_a_clock_jump_shows_in_its_microsector(self):
        grid = self.grid.copy()
        inside = int(np.argmax(self.sectors.index == 10)) + 3
        grid.loc[inside:, "elapsed_s"] -= 0.5
        grid["lap_time_s"] -= 0.5
        summary = origin.clock_summary(origin.clock_check(grid, self.track, self.sectors))
        self.assertEqual(summary["relogio_pior_microsetor"], 10)
        self.assertAlmostEqual(summary["relogio_pior_s"], -0.5, places=6)

    def test_the_trajectory_length_is_used_not_the_centerline(self):
        """A linha por fora de um circulo e mais longa: com o relogio dela, nada a acusar."""
        grid = self.grid.copy()
        # Neste circulo a trajetoria deslocada de L mede 2*pi*(R + L): L = +3 e por fora.
        lateral = 3.0
        radius = 200.0
        grid["lateral"] = lateral
        factor = (radius + lateral) / radius
        grid["elapsed_s"] *= factor
        grid["lap_time_s"] *= factor
        check = origin.clock_check(grid, self.track, self.sectors)
        self.assertLess(check["diferenca_s"].abs().max(), 1e-3)

    def test_missing_speed_is_not_verified(self):
        grid = self.grid.copy()
        grid.loc[100, "speed_kmh"] = np.nan
        self.assertFalse(origin.clock_summary(origin.clock_check(grid, self.track, self.sectors))["relogio_verificado"])

    def test_marking_uses_the_absolute_worst_microsector(self):
        inventory = pd.DataFrame(
            {"relogio_verificado": [True, True, False], "relogio_pior_s": [0.02, -0.4, np.nan]}
        )
        marked = origin.mark_clock(inventory, limit=0.1)
        self.assertEqual(marked["relogio_suspeito"].tolist(), [False, True, False])

    def test_no_limit_marks_nothing(self):
        inventory = pd.DataFrame({"relogio_verificado": [True], "relogio_pior_s": [5.0]})
        if origin.CLOCK_LIMIT_S is None:
            self.assertNotIn("relogio_suspeito", origin.mark_clock(inventory).columns)
        else:
            self.assertTrue(origin.mark_clock(inventory)["relogio_suspeito"].iloc[0])


class DuplicateTests(unittest.TestCase):
    def test_the_same_moment_recorded_twice(self):
        inventory = pd.DataFrame(
            {
                "lap_id": ["a#0001", "b#0000", "a#0002"],
                "session_id": ["a", "b", "a"],
                "lap_number": [56, 56, 57],
                "raw_samples": [5000, 1500, 5000],
                "inicio_epoch_s": [100.0, 101.0, 186.0],
                "fim_epoch_s": [186.0, 185.0, 272.0],
            }
        )
        marked = origin.mark_duplicates(inventory)
        self.assertEqual(marked["duplicada_de"].tolist(), [None, "a#0001", None])

    def test_consecutive_laps_of_one_session_are_not_duplicates(self):
        inventory = pd.DataFrame(
            {
                "lap_id": ["a#0001", "a#0002"],
                "session_id": ["a", "a"],
                "lap_number": [1, 2],
                "raw_samples": [10, 10],
                "inicio_epoch_s": [0.0, 85.0],
                "fim_epoch_s": [86.0, 170.0],
            }
        )
        self.assertTrue(origin.mark_duplicates(inventory)["duplicada_de"].isna().all())


class SelectionTests(unittest.TestCase):
    def inventory(self):
        return pd.DataFrame(
            {
                "lap_id": ["s#1", "s#2", "s#3", "s#4", "s#5", "s#6"],
                "replay_lap_id": ["rec__s__1", "rec__s__2", "rec__s__3", "rec__s__4", "rec__s__5", "rec__s__5"],
                "origem": ["humano", "ia", "humano", "humano", "humano", "misturada"],
                "relogio_verificado": [True, True, True, False, True, True],
                "relogio_suspeito": [False, False, True, False, False, False],
                "duplicada_de": [None, None, None, None, None, None],
            }
        )

    def test_the_default_is_the_driver_with_a_checked_clock(self):
        self.assertEqual(origin.select_laps(self.inventory())["lap_id"].tolist(), ["s#1", "s#5"])

    def test_filters_can_be_opened(self):
        everything = origin.select_laps(self.inventory(), origins=None, include_clock_suspect=True)
        self.assertEqual(len(everything), 6)
        ai = origin.select_laps(self.inventory(), origins=["ia"])
        self.assertEqual(ai["lap_id"].tolist(), ["s#2"])

    def test_duplicates_never_pass(self):
        inventory = self.inventory()
        inventory.loc[0, "duplicada_de"] = "x#9"
        self.assertNotIn("s#1", origin.select_laps(inventory, origins=None, include_clock_suspect=True)["lap_id"].tolist())

    def test_an_old_inventory_gives_nothing_by_default(self):
        old = pd.DataFrame({"lap_id": ["s#1"], "valid": [True]})
        self.assertTrue(origin.select_laps(old).empty)

    def test_a_replay_lap_passes_only_if_every_part_does(self):
        self.assertEqual(origin.replay_selection(self.inventory()), {"rec__s__1"})

    def test_command_line_origins(self):
        self.assertEqual(origin.parse_origins(None), ["humano"])
        self.assertIsNone(origin.parse_origins(["todas"]))
        with self.assertRaises(ValueError):
            origin.parse_origins(["piloto"])

    def test_the_store_refuses_an_inventory_without_origin(self):
        from ml.data.lap_store import build_store

        old = pd.DataFrame({"lap_id": ["s#1"], "valid": [True], "geometry_id": ["g"], "session_id": ["s"], "sequence": [1]})
        with self.assertRaisesRegex(ValueError, "ADR 0014"):
            build_store(inventory=old, track=circular_track(), sessions=[])


class CoachTrainingFilterTests(unittest.TestCase):
    def test_the_trainer_filters_by_origin_before_loading_anything(self):
        source = (BACKEND / "tools" / "train_reference_model.py").read_text(encoding="utf-8")
        self.assertIn("replay_selection(inventory, origins, args.incluir_relogio_suspeito)", source)
        self.assertIn('"origem" not in inventory.columns', source)
        self.assertLess(source.index("replay_selection(inventory"), source.index("loader.load_lap("))


class FolderTests(unittest.TestCase):
    def test_a_session_id_in_both_folders_stops_the_listing(self):
        from ml.data.recordings import list_all_sessions

        roots = [Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())]
        for root in roots:
            session = root / "2026-10-03_10-00-00_vhe_interlagos"
            session.mkdir()
            line = {"type": "player", "track": "vhe_interlagos", "sample": {"lap": 1}}
            (session / "player.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "existe em"):
            list_all_sessions(roots)

    def test_folder_label(self):
        from ml import config

        repo = config.recordings_root() / "2026-05-26_19-06-59_vhe_interlagos"
        self.assertEqual(origin.recording_folder(repo), "repositorio" if config.recordings_root().exists() else str(repo.parent))


class SignalTests(unittest.TestCase):
    def test_steering_reversals_ignore_small_noise(self):
        zigzag = np.tile([0.0, 0.2, 0.0, -0.2], 5)
        self.assertEqual(steering_reversals(zigzag), 2 * 5 - 1)
        self.assertEqual(steering_reversals(zigzag * 0.01), 0)

    def test_lap_signals(self):
        time_s = np.arange(0.0, 10.0, 0.05)
        aligned = pd.DataFrame(
            {
                "elapsed_s": time_s,
                "steering": np.sin(time_s),
                "throttle": np.where(time_s < 5, 1.0, 0.5),
                "brake": np.where((time_s > 6) & (time_s < 7), 1.0, 0.0),
                "gear": np.where(time_s < 3, 3, np.where(time_s < 8, 4, 5)).astype(float),
                "rpm": 6000.0 + 500.0 * np.mod(time_s, 3.0),
            }
        )
        signals = lap_signals(aligned, track_length=1000.0)
        self.assertAlmostEqual(signals["acelerador_parcial"], 0.5, delta=0.02)
        self.assertEqual(signals["freio_eventos"], 1.0)
        self.assertEqual(signals["freio_pico_mediano"], 1.0)
        self.assertGreater(signals["volante_taxa_p95"], 0.9)


if __name__ == "__main__":
    unittest.main()
