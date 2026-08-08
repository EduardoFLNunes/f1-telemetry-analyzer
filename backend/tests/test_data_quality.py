import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main
from core.data_quality import (
    TelemetryReliabilityMonitor,
    UdpReliabilityMonitor,
    validate_lap,
    validate_telemetry_sample,
    validate_track,
)
from core.geometry.paint_agreement import (
    evaluate_paint_agreement_cached,
    reset_paint_agreement_cache,
)
from core.opponents import OpponentsStateBuffer, OpponentsTelemetryReceiver
from core.telemetry.telemetry_models import TelemetrySample, TrackPoint


def complete_sample(**overrides):
    values = {
        "timestamp": 1_700_000_000_000,
        "worldPositionX": 10.0,
        "worldPositionY": 1.0,
        "worldPositionZ": 20.0,
        "speed": 180.0,
        "normalizedSplinePosition": 0.5,
        "lap": 2,
        "sessionTime": 90.0,
        "lapTime": 90.0,
        "rpm": 7000,
        "fuel": 30.0,
        "velocityX": 10.0,
        "velocityY": 0.0,
        "velocityZ": 20.0,
        "tyreCoreTemperature": [80.0, 81.0, 82.0, 83.0],
        "suspensionTravel": [0.05, 0.05, 0.05, 0.05],
    }
    values.update(overrides)
    return TelemetrySample(**values)


class PlayerReliabilityTests(unittest.TestCase):
    def test_player_without_samples_is_waiting(self):
        monitor = TelemetryReliabilityMonitor(time_provider=lambda: 10.0)
        payload = monitor.snapshot()
        self.assertEqual(payload["status"], "waiting")
        self.assertIsNone(payload["estimatedHz"])

    def test_player_receiving_at_60_hz_is_ok(self):
        now = [0.0]
        monitor = TelemetryReliabilityMonitor(time_provider=lambda: now[0])
        for index in range(300):
            now[0] = index / 60.0
            monitor.observe(complete_sample(timestamp=index))
        now[0] = 5.0
        payload = monitor.snapshot()
        self.assertEqual(payload["frequencyStatus"], "OK")
        self.assertGreaterEqual(payload["estimatedHz"], 59.0)
        self.assertLessEqual(payload["estimatedHz"], 61.0)

    def test_player_below_expected_frequency_is_error(self):
        now = [0.0]
        monitor = TelemetryReliabilityMonitor(time_provider=lambda: now[0])
        for index in range(100):
            now[0] = index / 20.0
            monitor.observe(complete_sample(timestamp=index))
        now[0] = 5.0
        payload = monitor.snapshot()
        self.assertEqual(payload["frequencyStatus"], "ERROR")
        self.assertLess(payload["estimatedHz"], 30.0)

    def test_partial_sample_keeps_session_usable(self):
        result = validate_telemetry_sample(
            TelemetrySample(
                timestamp=1.0,
                worldPositionX=1.0,
                worldPositionY=0.0,
                worldPositionZ=2.0,
                speed=100.0,
                normalizedSplinePosition=0.3,
                lap=1,
                sessionTime=10.0,
            )
        )
        self.assertEqual(result.status, "PARTIAL")
        self.assertTrue(result.hasPosition)
        self.assertFalse(result.hasTyres)

    def test_invalid_sample_is_identified(self):
        result = validate_telemetry_sample(
            complete_sample(speed=float("nan"), normalizedSplinePosition=1.5)
        )
        self.assertEqual(result.status, "INVALID")
        self.assertGreaterEqual(len(result.issues), 2)


class UdpReliabilityTests(unittest.TestCase):
    def test_udp_without_packets_is_waiting(self):
        monitor = UdpReliabilityMonitor(time_provider=lambda: 1.0)
        self.assertEqual(monitor.snapshot()["status"], "waiting")

    def test_udp_receives_valid_packets_and_filters_player(self):
        now = [1.0]
        monitor = UdpReliabilityMonitor(time_provider=lambda: now[0])
        buffer = OpponentsStateBuffer(time_provider=lambda: now[0])
        receiver = OpponentsTelemetryReceiver(
            buffer,
            event_bus=None,
            reliability_monitor=monitor,
        )
        payload = {
            "type": "opponents_snapshot",
            "timestamp": 10.0,
            "playerCarId": 0,
            "cars": [
                {"carId": 0, "isPlayer": True},
                {"carId": 2, "driverName": "AI"},
            ],
        }
        receiver.handle_packet(json.dumps(payload).encode("utf-8"))
        stats = monitor.snapshot(opponents_count=len(buffer.latest()))
        self.assertEqual(stats["packetsReceived"], 1)
        self.assertEqual(stats["packetsAccepted"], 1)
        self.assertEqual(stats["playerFilteredCount"], 1)
        self.assertEqual(stats["opponentsCount"], 1)
        self.assertNotIn(0, buffer.latest())

    def test_udp_invalid_packet_is_counted(self):
        monitor = UdpReliabilityMonitor(time_provider=lambda: 1.0)
        receiver = OpponentsTelemetryReceiver(
            OpponentsStateBuffer(),
            event_bus=None,
            reliability_monitor=monitor,
        )
        receiver.handle_packet(b"{invalid")
        stats = monitor.snapshot()
        self.assertEqual(stats["packetsReceived"], 1)
        self.assertEqual(stats["packetsInvalid"], 1)
        self.assertEqual(stats["packetsDropped"], 1)

    def test_udp_out_of_order_packet_is_counted(self):
        now = [1.0]
        monitor = UdpReliabilityMonitor(time_provider=lambda: now[0])
        receiver = OpponentsTelemetryReceiver(
            OpponentsStateBuffer(time_provider=lambda: now[0]),
            event_bus=None,
            reliability_monitor=monitor,
        )
        for timestamp in (20.0, 19.0):
            receiver.handle_packet(
                json.dumps(
                    {
                        "type": "opponents_snapshot",
                        "timestamp": timestamp,
                        "cars": [{"carId": 3}],
                    }
                ).encode("utf-8")
            )
            now[0] += 0.1
        stats = monitor.snapshot()
        self.assertEqual(stats["packetsReceived"], 2)
        self.assertEqual(stats["packetsOutOfOrder"], 1)
        self.assertEqual(stats["packetsDropped"], 1)


class LapAndTrackValidationTests(unittest.TestCase):
    def test_valid_lap(self):
        result = validate_lap(
            {
                "sessionId": "session",
                "lapNumber": 2,
                "sampleCount": 5400,
                "durationSeconds": 90.0,
                "progressStart": 0.0,
                "progressEnd": 0.99,
                "progressMin": 0.0,
                "progressMax": 0.99,
                "maxGapSeconds": 0.05,
                "completed": True,
            }
        )
        self.assertEqual(result.status, "VALID")
        self.assertGreater(result.coveragePercent, 98.0)

    def test_valid_lap_with_progress_wrap_after_finish_line(self):
        result = validate_lap(
            {
                "sessionId": "real_interlagos",
                "lapNumber": 72,
                "sampleCount": 2200,
                "durationSeconds": 89.5,
                "progressStart": 0.001,
                "progressEnd": 0.0005,
                "progressMin": 0.0005,
                "progressMax": 0.9998,
                "maxGapSeconds": 0.2,
                "completed": True,
            }
        )
        self.assertEqual(result.status, "VALID")
        self.assertGreater(result.coveragePercent, 99.0)

    def test_partial_lap(self):
        result = validate_lap(
            {
                "lapNumber": 3,
                "sampleCount": 20,
                "durationSeconds": 5.0,
                "progressMin": 0.2,
                "progressMax": 0.35,
                "completed": False,
            }
        )
        self.assertIn(result.status, {"PARTIAL", "INVALID"})
        self.assertTrue(result.issues)

    def test_invalid_lap_with_timestamp_inversion(self):
        result = validate_lap(
            {
                "lapNumber": 4,
                "sampleCount": 4000,
                "durationSeconds": 80.0,
                "progressMin": 0.0,
                "progressMax": 1.0,
                "timestampInversions": 1,
                "completed": True,
            }
        )
        self.assertEqual(result.status, "INVALID")

    def test_track_ready(self):
        result = validate_track(
            "TRACK_READY",
            {
                "centerline": [{"x": 0}, {"x": 1}],
                "boundsLeft": [{"x": 0}, {"x": 1}],
                "boundsRight": [{"x": 0}, {"x": 1}],
                "sectors": [{"index": 1}],
            },
            "interlagos",
        )
        self.assertEqual(result["status"], "TRACK_READY")
        self.assertTrue(result["hasCenterline"])
        self.assertTrue(result["hasBounds"])

    def test_track_missing(self):
        result = validate_track("NO_TRACK", None)
        self.assertEqual(result["status"], "TRACK_MISSING")
        self.assertTrue(result["issues"])

    def test_track_without_paint_still_reports_ready(self):
        reset_paint_agreement_cache()
        result = validate_track(
            "TRACK_READY",
            {
                "centerline": [{"x": 0}, {"x": 1}],
                "boundsLeft": [{"x": 0}, {"x": 1}],
                "boundsRight": [{"x": 0}, {"x": 1}],
                "sectors": [{"index": 1}],
            },
            "no_paint",
        )
        self.assertEqual(result["status"], "TRACK_READY")
        self.assertEqual(result["paintAgreement"]["status"], "UNAVAILABLE")

    def test_edges_that_disagree_with_the_paint_are_reported(self):
        reset_paint_agreement_cache()
        centerline = [
            TrackPoint(x=float(i), y=0.0, z=0.0, distance=float(i), spline_t=i / 200,
                       tangent=(1.0, 0.0), normal=(0.0, 1.0))
            for i in range(200)
        ]
        paint = {"rings": [[[float(i), 6.0] for i in range(200)]]}
        result = validate_track(
            "TRACK_READY",
            {
                "trackName": "paint_mismatch",
                "centerline": centerline,
                "localWidth": [9.0] * 200,  # paint says 12 m
                "boundsLeft": [{"x": 0}, {"x": 1}],
                "boundsRight": [{"x": 0}, {"x": 1}],
                "sectors": [{"index": 1}],
                "markingGeometry": {"polygons": [paint]},
            },
            "paint_mismatch",
        )
        self.assertEqual(result["paintAgreement"]["status"], "DIVERGENT")
        self.assertTrue(any(issue.startswith("paint check:") for issue in result["issues"]))
        self.assertEqual(result["status"], "TRACK_READY", "paint is a warning, not a structural failure")

    def test_paint_check_is_computed_once_per_track(self):
        reset_paint_agreement_cache()
        track = {
            "trackName": "cached",
            "generatedAt": "2026-01-01T00:00:00",
            "centerline": [{"x": 0}, {"x": 1}],
            "boundsLeft": [{"x": 0}, {"x": 1}],
            "boundsRight": [{"x": 0}, {"x": 1}],
            "sectors": [{"index": 1}],
        }
        with patch(
            "core.data_quality.track_validation.evaluate_paint_agreement_cached",
            wraps=evaluate_paint_agreement_cached,
        ) as spy:
            validate_track("TRACK_READY", track, "cached")
            validate_track("TRACK_READY", track, "cached")
        self.assertEqual(spy.call_count, 2, "the payload asks every time")
        self.assertIs(
            evaluate_paint_agreement_cached(track),
            evaluate_paint_agreement_cached(track),
            "but the answer is reused -- the evaluation blocks the event loop for ~0.2s",
        )


class DataQualityEndpointTests(unittest.TestCase):
    def test_data_quality_endpoint_contract(self):
        backend_main.player_reliability.reset()
        with patch.object(backend_main.session_repository, "list_sessions", return_value=[]):
            payload = asyncio.run(backend_main.data_quality_payload(force_sessions=True))
        self.assertIn(payload["status"], {"OK", "WARNING", "ERROR", "UNKNOWN"})
        self.assertEqual(payload["player"]["source"], "shared_memory")
        self.assertEqual(payload["opponents"]["source"], "udp")
        self.assertIn("laps", payload)
        self.assertIn("track", payload)
        self.assertIn("comparison", payload)
        route_paths = {route.path for route in backend_main.app.routes}
        self.assertIn("/api/validation/data-quality", route_paths)


if __name__ == "__main__":
    unittest.main()
