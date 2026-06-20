import sys
import unittest
from collections import deque
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.telemetry.telemetry_buffer import TelemetryBuffer  # noqa: E402


class TelemetryBufferTests(unittest.TestCase):
    def test_uses_bounded_deque_and_keeps_latest_samples(self):
        buffer = TelemetryBuffer(max_size=3)

        buffer.add_samples([1, 2, 3])
        buffer.add_sample(4)

        self.assertIsInstance(buffer.samples, deque)
        self.assertEqual(3, buffer.samples.maxlen)
        self.assertEqual([2, 3, 4], buffer.get_samples())
        self.assertEqual(4, buffer.get_latest_sample())

    def test_clear_preserves_bounded_storage(self):
        buffer = TelemetryBuffer(max_size=2)
        storage = buffer.samples
        buffer.add_samples([1, 2, 3])

        buffer.clear()

        self.assertIs(storage, buffer.samples)
        self.assertEqual([], buffer.get_samples())
        self.assertEqual(2, buffer.samples.maxlen)

    def test_get_lap_samples_preserves_public_filtering_api(self):
        class Sample:
            def __init__(self, lap):
                self.lap = lap

        buffer = TelemetryBuffer(max_size=4)
        buffer.add_samples([Sample(1), Sample(2), Sample(2)])

        self.assertEqual(2, len(buffer.get_lap_samples(2)))
        self.assertEqual(3, len(buffer.get_lap_samples()))


if __name__ == "__main__":
    unittest.main()
