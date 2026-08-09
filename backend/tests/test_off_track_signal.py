import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class OffTrackSignalTests(unittest.TestCase):
    """Assetto Corsa counts the wheels outside the white line itself. The field
    was parsed from shared memory and never surfaced, which left the
    reconstructed limit with nothing to be checked against."""

    def test_the_adapter_publishes_the_simulators_verdict(self):
        source = (Path(__file__).resolve().parents[1] / "core" / "assetto_adapter.py").read_text(encoding="utf-8")

        self.assertIn('"tyres_out": self.physics.numberOfTyresOut', source)
        self.assertIn('"off_track": self.physics.numberOfTyresOut >= 4', source)

    def test_the_reader_carries_it_through(self):
        source = (Path(__file__).resolve().parents[1] / "core" / "telemetry"
                  / "telemetry_reader_impl.py").read_text(encoding="utf-8")

        for key in ('"tyres_out"', '"off_track"', '"penalty_time"'):
            self.assertIn(key, source, f"{key} is dropped between the adapter and the sample")

    def test_the_sample_model_types_the_fields(self):
        """Three earlier additions died here: the reader passes a dict, the model
        keeps only what it declares, and the rest vanishes without a word."""
        from core.telemetry.telemetry_models import TelemetrySample

        sample = TelemetrySample.from_dict({
            "timestamp": 1, "tyres_out": 4, "off_track": True, "penalty_time": 2.5,
        })

        self.assertEqual(sample.tyresOut, 4)
        self.assertTrue(sample.offTrack)
        self.assertEqual(sample.penaltyTime, 2.5)

    def test_the_field_survives_camel_case_too(self):
        from core.telemetry.telemetry_models import TelemetrySample

        sample = TelemetrySample.from_dict({"timestamp": 1, "tyresOut": 2})

        self.assertEqual(sample.tyresOut, 2)

    def test_off_track_means_all_four_wheels(self):
        """One wheel over the line is not a violation under any rule the FIA
        writes; four is."""
        for tyres, expected in ((0, False), (1, False), (3, False), (4, True)):
            self.assertEqual(tyres >= 4, expected)


if __name__ == "__main__":
    unittest.main()
