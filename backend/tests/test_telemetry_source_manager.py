import unittest
from pathlib import Path
import sys
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.telemetry.telemetry_models import TelemetrySample
from core.telemetry.telemetry_reader_impl import TelemetrySourceConfig, TelemetrySourceManager


def sample():
    return TelemetrySample.from_dict(
        {
            "timestamp": 1.0,
            "x": 10.0,
            "y": 0.0,
            "z": 20.0,
            "speed": 120.0,
            "normalized_spline_pos": 0.2,
            "car_id": 0,
        }
    )


class FakeACReader:
    source_name = "assetto_corsa"
    active_reader_name = "ACSharedMemoryReader"

    def __init__(self, telemetry_sample=None, connected=True):
        self.telemetry_sample = telemetry_sample
        self.connected = connected
        self.stopped = False

    def read_sample(self):
        return self.telemetry_sample

    def stop(self):
        self.stopped = True


class TelemetrySourceManagerTests(unittest.TestCase):
    def test_auto_source_promotes_from_mock_when_assetto_auto_connect_is_enabled(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="auto", assetto_auto_connect=True))

        with patch(
            "core.telemetry.telemetry_reader_impl.ACSharedMemoryReader",
            side_effect=lambda: FakeACReader(sample(), connected=True),
        ):
            telemetry_sample = manager.read_sample()

        self.assertIsNotNone(telemetry_sample)
        self.assertEqual(manager.get_active_source_name(), "assetto_corsa")
        self.assertTrue(manager.ac_available)

    def test_default_auto_source_does_not_probe_assetto(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="auto"))

        with patch("core.telemetry.telemetry_reader_impl.ACSharedMemoryReader") as ac_reader:
            selected = manager.select_source()
            telemetry_sample = manager.read_sample()

        self.assertEqual(selected, "mock")
        self.assertIsNone(telemetry_sample)
        self.assertEqual(manager.get_active_source_name(), "mock")
        ac_reader.assert_not_called()

    def test_explicit_mock_source_does_not_auto_promote(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="mock"))
        manager.select_source("mock")

        with patch("core.telemetry.telemetry_reader_impl.ACSharedMemoryReader") as ac_reader:
            telemetry_sample = manager.read_sample()

        self.assertIsNone(telemetry_sample)
        self.assertEqual(manager.get_active_source_name(), "mock")
        ac_reader.assert_not_called()

    def test_explicit_assetto_source_requires_ready_sample(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="mock"))
        fake_reader = FakeACReader(None, connected=True)

        with patch(
            "core.telemetry.telemetry_reader_impl.ACSharedMemoryReader",
            return_value=fake_reader,
        ):
            with self.assertRaises(RuntimeError):
                manager.select_source("assetto_corsa")

        self.assertTrue(fake_reader.stopped)
        self.assertEqual(manager.get_active_source_name(), "mock")


if __name__ == "__main__":
    unittest.main()
