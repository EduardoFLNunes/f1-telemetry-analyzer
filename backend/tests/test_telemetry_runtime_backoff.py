import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.live.telemetry_runtime import TelemetryRuntime  # noqa: E402


class TelemetryRuntimeBackoffTests(unittest.TestCase):
    def setUp(self):
        source = SimpleNamespace()
        self.runtime = TelemetryRuntime(
            source,
            poll_hz=60,
            idle_poll_hz=15,
            stale_poll_hz=5,
            error_poll_hz=2,
        )

    def test_waiting_runtime_uses_stale_poll_rate(self):
        self.runtime._set_adaptive_poll_interval(now=100.0)

        self.assertEqual("waiting", self.runtime._poll_mode)
        self.assertAlmostEqual(5.0, 1.0 / self.runtime._current_poll_interval)

    def test_runtime_steps_down_from_active_to_idle_and_stale(self):
        self.runtime._last_fresh_read_monotonic = 100.0

        self.runtime._set_adaptive_poll_interval(now=100.05)
        self.assertEqual("active", self.runtime._poll_mode)
        self.assertAlmostEqual(60.0, 1.0 / self.runtime._current_poll_interval)

        self.runtime._set_adaptive_poll_interval(now=101.0)
        self.assertEqual("idle", self.runtime._poll_mode)
        self.assertAlmostEqual(15.0, 1.0 / self.runtime._current_poll_interval)

        self.runtime._set_adaptive_poll_interval(now=106.0)
        self.assertEqual("stale", self.runtime._poll_mode)
        self.assertAlmostEqual(5.0, 1.0 / self.runtime._current_poll_interval)

    def test_new_valid_sample_reactivates_full_poll_rate(self):
        self.runtime._set_adaptive_poll_interval(now=100.0)
        self.assertEqual("waiting", self.runtime._poll_mode)

        self.runtime._activate_polling(now=101.0)

        self.assertEqual("active", self.runtime._poll_mode)
        self.assertAlmostEqual(60.0, 1.0 / self.runtime._current_poll_interval)
        self.assertEqual(101.0, self.runtime._last_fresh_read_monotonic)

    def test_error_uses_error_backoff_and_can_recover(self):
        self.runtime._activate_error_backoff()
        self.assertEqual("error", self.runtime._poll_mode)
        self.assertAlmostEqual(2.0, 1.0 / self.runtime._current_poll_interval)

        self.runtime._activate_polling(now=102.0)
        self.assertEqual("active", self.runtime._poll_mode)
        self.assertAlmostEqual(60.0, 1.0 / self.runtime._current_poll_interval)


if __name__ == "__main__":
    unittest.main()
