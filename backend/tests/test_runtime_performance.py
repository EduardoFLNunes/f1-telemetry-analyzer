import asyncio
import sys
import unittest
from types import SimpleNamespace
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
        self.assertAlmostEqual(60.0, snapshot["windows"]["30s"]["rawReadHz"], delta=0.1)
        self.assertAlmostEqual(60.0, snapshot["windows"]["5s"]["acceptedSampleHz"], delta=0.1)
        self.assertEqual(1800, snapshot["counters"]["rawSamples"])
        self.assertIn("readLoopAvg", snapshot["durationsMs"])
        self.assertFalse(snapshot["bottleneckDetails"]["sourceLimited"])

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
        self.assertEqual("read_loop_interval_below_target", snapshot["bottleneck"])
        self.assertLess(snapshot["rawReadHz"], 30.0)

    def test_runtime_sampling_metrics_identify_source_limited_reader(self):
        metrics = PerformanceMetrics()
        base = 2500.0
        for index in range(300):
            now = base + index / 60.0
            metrics.mark_read_attempt(now=now)
            if index % 2 == 0:
                metrics.mark_raw_read(now=now)
                metrics.mark_sample_validation("VALID", now=now)

        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="assetto_corsa",
            player_source="shared_memory",
            player_status="receiving",
            now=base + 5.0,
        )

        self.assertEqual("SOURCE_LIMITED", snapshot["status"])
        self.assertEqual("assetto_shared_memory_source_limited", snapshot["bottleneckReason"])
        self.assertTrue(snapshot["sourceLimited"])
        self.assertAlmostEqual(60.0, snapshot["windows"]["5s"]["readAttemptHz"], delta=0.1)
        self.assertAlmostEqual(30.0, snapshot["windows"]["5s"]["rawReadHz"], delta=0.1)

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

    def test_persisted_sample_rate_is_reported_separately_from_collection(self):
        metrics = PerformanceMetrics()
        base = 3500.0
        for index in range(300):
            now = base + index / 60.0
            metrics.mark_read_attempt(now=now)
            metrics.mark_raw_read(now=now)
            metrics.mark_sample_validation("VALID", now=now)
        for index in range(100):
            now = base + index / 20.0
            metrics.mark_persisted_samples("player", now=now)

        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="assetto_corsa",
            player_source="shared_memory",
            player_status="receiving",
            now=base + 5.0,
        )

        self.assertAlmostEqual(60.0, snapshot["windows"]["5s"]["acceptedSampleHz"], delta=0.1)
        self.assertAlmostEqual(20.0, snapshot["windows"]["5s"]["persistedSampleHz"], delta=0.1)
        self.assertEqual(300, snapshot["counters"]["acceptedSamples"])
        self.assertEqual(100, snapshot["counters"]["persistedSamples"])

    def test_mock_source_reports_offline_mock_without_error(self):
        metrics = PerformanceMetrics()
        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="mock",
            player_source="mock",
            player_status="waiting",
            now=4000.0,
        )

        self.assertEqual("OFFLINE_MOCK", snapshot["status"])
        self.assertEqual("offline_or_mock_source", snapshot["bottleneckReason"])
        self.assertFalse(snapshot["sourceLimited"])

    def test_duplicate_samples_are_counted_separately(self):
        metrics = PerformanceMetrics()
        sample = SimpleNamespace(
            timestamp=10.0,
            sessionTime=20.0,
            lap=3,
            lapTime=11.5,
            normalizedSplinePosition=0.42,
            worldPositionX=1.0,
            worldPositionY=0.0,
            worldPositionZ=2.0,
        )
        metrics.mark_raw_read(sample, now=5000.0)
        metrics.mark_raw_read(sample, now=5000.1)

        snapshot = metrics.runtime_snapshot(
            target_hz=60.0,
            source="assetto_corsa",
            player_source="shared_memory",
            player_status="receiving",
            now=5001.0,
        )

        self.assertEqual(2, snapshot["counters"]["rawSamples"])
        self.assertEqual(1, snapshot["counters"]["duplicateSamples"])

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
        self.assertIn("adaptivePollMode", payload["sampling"])
        self.assertIn("adaptivePollHz", payload["sampling"])
        self.assertIn("windows", payload)
        self.assertIn("5s", payload["windows"])
        self.assertIn("30s", payload["windows"])
        self.assertIn("durationsMs", payload)
        self.assertIn("counters", payload)
        self.assertIn("bottleneck", payload)
        self.assertIn("reason", payload["bottleneck"])
        self.assertIn("recording", payload)
        self.assertIn("websocket", payload)


if __name__ == "__main__":
    unittest.main()
