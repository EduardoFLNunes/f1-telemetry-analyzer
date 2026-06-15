import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main
from core.recording.session_repository import SessionRepository
from core.session_audit import (
    LapStreamAggregator,
    SessionAuditExporter,
    SessionAuditService,
    analyze_sample_timestamps,
    audit_laps,
    calibration_for_track,
)


def write_session(
    root: Path,
    session_id: str,
    *,
    sample_count: int,
    hz: float,
    duration: float,
    track: str = "test_track",
    completed: bool = True,
):
    directory = root / session_id
    directory.mkdir()
    metadata = {
        "schemaVersion": 2,
        "sessionId": session_id,
        "track": track,
        "startedAt": "2026-06-14T10:00:00",
        "endedAt": "2026-06-14T10:01:00" if completed else None,
        "playerRecordHz": 60.0,
        "opponentsRecordHz": 20.0,
        "metadata": {
            "source": "assetto_corsa",
            "trackState": "TRACK_READY",
            "hasCenterline": True,
            "hasBounds": True,
            "hasSectors": False,
        },
    }
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    rows = []
    for index in range(sample_count):
        fraction = index / max(sample_count - 1, 1)
        rows.append(
            {
                "type": "player",
                "timestamp": (1_700_000_000.0 + index / hz) * 1000.0,
                "track": track,
                "sample": {
                    "lap_number": 1,
                    "sessionTime": duration * fraction,
                    "lap_time": duration * fraction,
                    "lapProgress": fraction,
                    "speedKmh": 150.0,
                    "timestamp": (1_700_000_000.0 + index / hz) * 1000.0,
                },
            }
        )
    (directory / "player.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    opponents = [
        {
            "type": "opponents",
            "timestamp": 1_700_000_000.0 + index / 20.0,
            "track": track,
            "count": 2,
            "cars": [{"carId": 1}, {"carId": 2}],
        }
        for index in range(20)
    ]
    (directory / "opponents.jsonl").write_text(
        "\n".join(json.dumps(row) for row in opponents) + "\n",
        encoding="utf-8",
    )
    return directory


class SampleLossReportTests(unittest.TestCase):
    def test_calculates_average_hz(self):
        report = analyze_sample_timestamps([index / 60.0 for index in range(301)])
        self.assertAlmostEqual(report["avgHz"], 60.0, places=1)
        self.assertEqual(report["qualityStatus"], "OK")

    def test_calculates_p95_and_p99(self):
        timestamps = [0.0]
        for gap_ms in [10.0] * 95 + [20.0] * 4 + [100.0]:
            timestamps.append(timestamps[-1] + gap_ms / 1000.0)
        report = analyze_sample_timestamps(timestamps)
        self.assertGreaterEqual(report["p95FrameGapMs"], 10.0)
        self.assertGreater(report["p99FrameGapMs"], report["p95FrameGapMs"])
        self.assertEqual(report["longestGapMs"], 100.0)

    def test_estimates_dropped_samples(self):
        report = analyze_sample_timestamps([0.0, 1 / 60.0, 3 / 60.0, 4 / 60.0])
        self.assertEqual(report["estimatedDroppedSamples"], 1)


class CalibrationAndLapAuditTests(unittest.TestCase):
    def test_default_calibration(self):
        profile = calibration_for_track("ks_monza")
        self.assertEqual(profile.profileId, "default")
        self.assertGreater(profile.maxValidLapSeconds, 1000.0)

    def test_interlagos_calibration(self):
        profile = calibration_for_track("vhe_interlagos_gp")
        self.assertEqual(profile.profileId, "interlagos")
        self.assertLess(profile.maxValidLapSeconds, 400.0)

    def test_valid_lap_can_be_reference(self):
        result = audit_laps(
            "session",
            [{
                "lapNumber": 2,
                "sampleCount": 3000,
                "durationSeconds": 60.0,
                "progressStart": 0.0,
                "progressEnd": 1.0,
                "coveragePercent": 100.0,
                "maxGapSeconds": 0.03,
                "timestampInversions": 0,
                "completed": True,
            }],
            calibration_for_track("interlagos"),
        )
        self.assertEqual(result["validLaps"], 1)
        self.assertTrue(result["items"][0]["canUseAsReference"])

    def test_partial_lap_cannot_be_reference(self):
        result = audit_laps(
            "session",
            [{
                "lapNumber": 3,
                "sampleCount": 20,
                "durationSeconds": 8.0,
                "coveragePercent": 20.0,
                "completed": False,
            }],
            calibration_for_track("default"),
        )
        self.assertEqual(result["partialLaps"], 1)
        self.assertFalse(result["items"][0]["canUseAsReference"])

    def test_invalid_lap_cannot_be_reference(self):
        result = audit_laps(
            "session",
            [{
                "lapNumber": 4,
                "sampleCount": 500,
                "durationSeconds": 60.0,
                "coveragePercent": 100.0,
                "timestampInversions": 1,
                "completed": True,
            }],
            calibration_for_track("default"),
        )
        self.assertEqual(result["invalidLaps"], 1)
        self.assertFalse(result["items"][0]["canUseAsReference"])

    def test_spline_wrap_does_not_create_single_sample_lap(self):
        aggregator = LapStreamAggregator("session")
        for index, progress in enumerate((0.95, 0.99, 0.0, 0.01)):
            aggregator.observe(
                {
                    "timestamp": 1_700_000_000_000 + index * 20,
                    "sample": {
                        "lap_number": 4,
                        "lap_time": 80.0 + index * 0.02,
                        "lapProgress": progress,
                    },
                }
            )
        aggregator.observe(
            {
                "timestamp": 1_700_000_000_100,
                "sample": {
                    "lap_number": 5,
                    "lap_time": 0.02,
                    "lapProgress": 0.01,
                },
            }
        )
        laps = aggregator.finish(recording_ended=False)
        self.assertEqual(len(laps), 2)
        self.assertEqual(laps[0]["sampleCount"], 4)
        self.assertEqual(laps[1]["sampleCount"], 1)


class SessionAuditServiceTests(unittest.TestCase):
    def test_audit_without_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = SessionAuditService(
                SessionRepository(root / "recordings"),
                root / "reports",
            )
            self.assertIsNone(service.audit_latest())

    def test_audit_short_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_session(root, "short", sample_count=10, hz=20.0, duration=0.45)
            service = SessionAuditService(SessionRepository(root), root / "reports")
            report = service.audit_session("short")
            self.assertIn(report["overallStatus"], {"WARNING", "ERROR"})
            self.assertEqual(report["laps"]["partialLaps"], 0)
            self.assertEqual(report["laps"]["invalidLaps"], 1)

    def test_audit_valid_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_session(root, "valid", sample_count=601, hz=50.0, duration=12.0)
            service = SessionAuditService(SessionRepository(root), root / "reports")
            report = service.audit_session("valid")
            self.assertEqual(report["playerCapture"]["qualityStatus"], "OK")
            self.assertEqual(report["laps"]["validLaps"], 1)
            self.assertEqual(report["udpOpponents"]["opponentsSeen"], 2)
            self.assertEqual(report["track"]["status"], "TRACK_READY")

    def test_export_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_session(root, "exportable", sample_count=601, hz=50.0, duration=12.0)
            service = SessionAuditService(SessionRepository(root), root / "reports")
            result = service.export_latest()
            self.assertTrue(Path(result["jsonPath"]).exists())
            self.assertTrue(Path(result["markdownPath"]).exists())
            markdown = Path(result["markdownPath"]).read_text(encoding="utf-8")
            self.assertIn("# Session Telemetry Audit", markdown)
            self.assertIn("## Player Capture", markdown)

    def test_exporter_latest_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporter = SessionAuditExporter(Path(tmp) / "reports")
            self.assertIsNone(exporter.latest())


class SessionAuditEndpointTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "sessionId": "fixture",
            "overallStatus": "OK",
            "laps": {"items": [], "validLaps": 0},
        }

    def test_endpoint_latest(self):
        with patch.object(
            backend_main.session_audit_service,
            "audit_latest",
            return_value=self.report,
        ):
            payload = asyncio.run(backend_main.get_latest_session_audit(False))
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["audit"]["sessionId"], "fixture")

    def test_endpoint_laps(self):
        with patch.object(
            backend_main.session_audit_service,
            "audit_latest",
            return_value=self.report,
        ):
            payload = asyncio.run(backend_main.get_audited_laps(None))
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["sessionId"], "fixture")

    def test_endpoint_export(self):
        export = {"status": "success", "sessionId": "fixture"}
        with patch.object(
            backend_main.session_audit_service,
            "export_latest",
            return_value=export,
        ):
            payload = asyncio.run(backend_main.export_latest_session_audit())
        self.assertEqual(payload["status"], "success")

    def test_routes_are_registered(self):
        paths = {route.path for route in backend_main.app.routes}
        self.assertIn("/api/audit/session/latest", paths)
        self.assertIn("/api/audit/session/{session_id}", paths)
        self.assertIn("/api/audit/laps", paths)
        self.assertIn("/api/audit/export/latest", paths)


if __name__ == "__main__":
    unittest.main()
