import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.reference_model import (  # noqa: E402
    DriverReferenceModel,
    build_reference_model,
    lap_is_usable,
    microsector_splits,
    model_path,
)


def synthetic_lap(seconds: float, *, hz: float = 57.0, speed: float = 200.0, slow_slice=None):
    """
    A lap driven at a constant rate, optionally losing time in one slice.

    `slow_slice` is `(index, extra_seconds)` out of 60 microsectors: the lap
    takes that much longer to cross that slice and makes it up nowhere.
    """
    count = int(seconds * hz)
    progress = np.linspace(0.0, 1.0, count)
    elapsed = progress * seconds
    if slow_slice is not None:
        index, extra = slow_slice
        start, end = index / 60.0, (index + 1) / 60.0
        inside = (progress >= start) & (progress < end)
        ramp = np.clip((progress - start) / max(end - start, 1e-9), 0.0, 1.0)
        elapsed = elapsed + np.where(progress >= end, extra, np.where(inside, ramp * extra, 0.0))
    return pd.DataFrame({
        "p": progress,
        "elapsed_s": elapsed,
        "speed_kmh": np.full(count, speed),
        "brake": np.zeros(count),
        "throttle": np.ones(count),
    })


class LapFilterTests(unittest.TestCase):
    def test_rejects_a_lap_whose_sampling_collapsed(self):
        # The one that was ranking as the driver's personal best: 937 samples
        # over 74 seconds is 13 Hz of a 57 Hz signal.
        usable, reason = lap_is_usable(73.653, 937)
        self.assertFalse(usable)
        self.assertEqual("sampling_too_sparse", reason)

    def test_accepts_a_normally_recorded_lap(self):
        usable, reason = lap_is_usable(85.059, 4845)
        self.assertTrue(usable, msg=reason)

    def test_rejects_laps_that_are_not_laps(self):
        self.assertFalse(lap_is_usable(None, 4000)[0])
        self.assertFalse(lap_is_usable(0.06, 2)[0])
        self.assertFalse(lap_is_usable(85.0, None)[0])
        self.assertFalse(lap_is_usable(float("nan"), 4000)[0])


class MicrosectorSplitTests(unittest.TestCase):
    def test_splits_add_up_to_the_lap(self):
        splits = microsector_splits(synthetic_lap(85.0))
        self.assertTrue(all(split is not None for split in splits))
        self.assertAlmostEqual(85.0, sum(splits), places=1)

    def test_interpolates_the_boundary_instead_of_rounding_to_a_sample(self):
        # At 57 Hz a sample is 17.5 ms; taking the first sample past the line
        # would show up as that much error on every slice.
        splits = microsector_splits(synthetic_lap(85.0, hz=20.0))
        for split in splits:
            self.assertAlmostEqual(85.0 / 60.0, split, places=3)

    def test_a_partial_lap_leaves_the_slices_it_never_reached_empty(self):
        lap = synthetic_lap(85.0)
        half = lap[lap["p"] <= 0.5]
        splits = microsector_splits(half)
        self.assertIsNotNone(splits[10])
        self.assertIsNone(splits[45])

    def test_says_nothing_about_a_lap_with_no_channels(self):
        self.assertEqual([None] * 60, microsector_splits(pd.DataFrame()))
        self.assertEqual([None] * 60, microsector_splits(pd.DataFrame({"p": [0.1, 0.2]})))


class ReferenceModelTests(unittest.TestCase):
    def test_keeps_the_quickest_the_driver_has_been_in_each_slice(self):
        laps = [
            ("lap_a", 85.0, 4845, synthetic_lap(85.0, slow_slice=(10, 0.5))),
            ("lap_b", 85.0, 4845, synthetic_lap(85.0, slow_slice=(30, 0.5))),
        ]
        model = build_reference_model(laps, track="vhe_interlagos")
        self.assertEqual(2, model.lap_count)
        # Each lap is the best in the slice the other one lost time in.
        self.assertEqual("lap_b", model.target_at(10.5 / 60).best_lap_id)
        self.assertEqual("lap_a", model.target_at(30.5 / 60).best_lap_id)

    def test_the_ideal_lap_is_quicker_than_any_lap_actually_driven(self):
        # This is the number the driver never sees on the timing screen: the sum
        # of his own bests, which he has never strung together.
        # Each lap is a clean 85.5 plus half a second dropped in one slice, so
        # both cross the line at 86.0 and the ideal is the clean 85.5.
        laps = [
            ("lap_a", 86.0, 4845, synthetic_lap(85.5, slow_slice=(10, 0.5))),
            ("lap_b", 86.0, 4845, synthetic_lap(85.5, slow_slice=(30, 0.5))),
        ]
        model = build_reference_model(laps)
        self.assertLess(model.ideal_lap_seconds, model.best_lap_seconds)
        self.assertAlmostEqual(0.5, model.gap_best_to_ideal, places=1)

    def test_a_corrupt_lap_cannot_set_the_record(self):
        laps = [
            ("bom", 85.059, 4845, synthetic_lap(85.059)),
            ("corrompido", 73.653, 937, synthetic_lap(73.653, hz=12.7)),
        ]
        model = build_reference_model(laps)
        self.assertEqual(1, model.lap_count)
        self.assertEqual("bom", model.best_lap_id)
        self.assertEqual(85.059, model.best_lap_seconds)
        self.assertEqual({"sampling_too_sparse": 1}, model.rejected_reasons)

    def test_reports_where_a_lap_gave_time_away(self):
        model = build_reference_model([("ref", 85.0, 4845, synthetic_lap(85.0))])
        splits = microsector_splits(synthetic_lap(85.6, slow_slice=(20, 0.6)))
        losses = model.loss_against_ideal(splits)
        self.assertGreater(losses[20], 0.4)
        for index in (5, 40, 55):
            self.assertLess(abs(losses[index]), 0.05)

    def test_remembers_how_the_best_slice_was_driven(self):
        lap = synthetic_lap(85.0)
        lap["brake"] = np.where((lap["p"] > 0.17) & (lap["p"] < 0.19), 0.9, 0.0)
        model = build_reference_model([("ref", 85.0, 4845, lap)])
        target = model.target_at(0.175)
        self.assertIsNotNone(target.brake_point_p)
        self.assertAlmostEqual(0.17, target.brake_point_p, places=1)
        self.assertIsNotNone(target.min_speed_kmh)

    def test_has_nothing_to_say_without_usable_laps(self):
        model = build_reference_model([("ruim", 73.6, 937, synthetic_lap(73.6, hz=12.7))])
        self.assertEqual(0, model.lap_count)
        self.assertIsNone(model.ideal_lap_seconds)
        self.assertIsNone(model.target_at(0.5))
        self.assertEqual([None, None], model.loss_against_ideal([1.0, 2.0]))

    def test_survives_a_round_trip_through_disk(self):
        import tempfile

        model = build_reference_model([("ref", 85.0, 4845, synthetic_lap(85.0))], track="vhe_interlagos")
        with tempfile.TemporaryDirectory() as tmp:
            path = model_path(Path(tmp), "vhe_interlagos")
            model.save(path)
            loaded = DriverReferenceModel.load(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(model.ideal_lap_seconds, loaded.ideal_lap_seconds)
        self.assertEqual(len(model.targets), len(loaded.targets))
        self.assertEqual(model.target_at(0.5).best_seconds, loaded.target_at(0.5).best_seconds)

    def test_a_broken_model_file_does_not_take_the_app_down(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quebrado.json"
            path.write_text("{ isto nao e json", encoding="utf-8")
            self.assertIsNone(DriverReferenceModel.load(path))
            self.assertIsNone(DriverReferenceModel.load(Path(tmp) / "nao_existe.json"))


if __name__ == "__main__":
    unittest.main()
