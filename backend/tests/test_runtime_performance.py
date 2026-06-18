import asyncio
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main  # noqa: E402
from core.performance_metrics import PerformanceMetrics  # noqa: E402


class RuntimePerformanceMetricsTests(unittest.TestCase):
    def test_runtime_sampling_metrics_keep_5s_and_30s_windows(self):
        metrics = PerformanceMetrics()
        base = 1000.0
        for index in range(1800):
            now = base + index / 60.0
            metrics.mark_read_attempt(now=now)
            metrics.mark_raw_read(now=now)
            metrics.mark_sample_validation("VALID", now=now)
            metrics.mark_player_frame(now=now)

        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="assetto_corsa",
            player_status="receiving",
            now=base + 30.0,
        )

        self.assertEqual("OK", snapshot["status"])
        self.assertEqual("collection_on_target", snapshot["bottleneck"])
        self.assertAlmostEqual(60.0, snapshot["rawReadHz"], delta=0.1)
        self.assertAlmostEqual(60.0, snapshot["acceptedSampleHz"], delta=0.1)
        self.assertAlmostEqual(60.0, snapshot["windows"]["rawReads"]["30s"], delta=0.1)

    def test_runtime_sampling_metrics_identify_reader_bottleneck(self):
        metrics = PerformanceMetrics()
        base = 2000.0
        for index in range(125):
            now = base + index / 25.0
            metrics.mark_read_attempt(now=now)
            metrics.mark_raw_read(now=now)
            metrics.mark_sample_validation("VALID", now=now)

        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="assetto_corsa",
            player_status="receiving",
            now=base + 5.0,
        )

        self.assertEqual("ERROR", snapshot["status"])
        self.assertEqual("reader_or_source_limited", snapshot["bottleneck"])
        self.assertLess(snapshot["rawReadHz"], 30.0)

    def test_websocket_throttle_does_not_reclassify_collection_as_slow(self):
        metrics = PerformanceMetrics()
        base = 3000.0
        for index in range(300):
            now = base + index / 60.0
            metrics.mark_raw_read(now=now)
            metrics.mark_sample_validation("VALID", now=now)
        for index in range(75):
            now = base + index / 15.0
            metrics.mark_websocket_message(message_type="telemetry", now=now)

        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="assetto_corsa",
            player_status="receiving",
            now=base + 5.0,
        )

        self.assertEqual("OK", snapshot["status"])
        self.assertEqual("websocket_or_frontend_throttled_not_collection", snapshot["bottleneck"])
        self.assertAlmostEqual(60.0, snapshot["acceptedSampleHz"], delta=0.1)
        self.assertAlmostEqual(15.0, snapshot["websocketEmitHz"], delta=0.1)

    def test_runtime_performance_endpoint_returns_valid_structure(self):
        backend_main.performance_metrics.reset()
        payload = asyncio.run(backend_main.get_runtime_performance())

        self.assertEqual("success", payload["status"])
        self.assertIn("sampling", payload)
        self.assertIn("rawReadHz", payload["sampling"])
        self.assertIn("acceptedSampleHz", payload["sampling"])
        self.assertIn("persistedSampleHz", payload["sampling"])
        self.assertIn("websocketEmitHz", payload["sampling"])
        self.assertIn("bottleneck", payload["sampling"])
        self.assertIn("recording", payload)
        self.assertIn("websocket", payload)


if __name__ == "__main__":
    unittest.main()
