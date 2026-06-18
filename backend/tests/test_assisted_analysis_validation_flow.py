import asyncio
import tempfile
import unittest
from pathlib import Path
import sys
from typing import Optional

from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main  # noqa: E402
from core.assisted_analysis.service import AssistedAnalysisService  # noqa: E402
from core.assisted_analysis.validation_fixture_factory import (  # noqa: E402
    write_phase14_1_validation_recording,
)
from core.cache.track_cache import TrackCache  # noqa: E402
from core.live.runtime_state import RuntimeState  # noqa: E402
from core.recording.session_repository import SessionRepository  # noqa: E402
from core.telemetry.telemetry_buffer import TelemetryBuffer  # noqa: E402


def _make_service(repo_root: Path, runtime_root: Optional[Path] = None) -> AssistedAnalysisService:
    return AssistedAnalysisService(
        repo_root,
        TelemetryBuffer(max_size=5000),
        RuntimeState(),
        TrackCache(str(repo_root / "data" / "cache" / "tracks")),
        runtime_root=runtime_root,
    )


class AssistedAnalysisValidationFlowTests(unittest.TestCase):
    def test_fixture_laps_are_accepted_and_invalid_lap_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = write_phase14_1_validation_recording(root)
            service = _make_service(root)

            self.assertEqual("VALID", fixture.validations[1]["status"])
            self.assertEqual("VALID", fixture.validations[2]["status"])
            self.assertNotEqual("VALID", fixture.validations[3]["status"])

            lap_ids = {lap["lapId"] for lap in service.list_laps()["laps"]}
            self.assertIn(fixture.reference_lap_id, lap_ids)
            self.assertIn(fixture.target_lap_id, lap_ids)
            self.assertNotIn(fixture.invalid_lap_id, lap_ids)

            with self.assertRaises(ValueError):
                service.analyze_lap(
                    fixture.invalid_lap_id,
                    reference_lap_id=fixture.reference_lap_id,
                    force=True,
                )

    def test_assisted_analysis_produces_complete_phase14_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = write_phase14_1_validation_recording(root)
            service = _make_service(root)

            payload = service.analyze_lap(fixture.target_lap_id, force=True)
            analysis = payload["analysis"]
            summary = analysis["summary"]
            corners = analysis["corners"]
            top_losses = analysis["topLosses"]
            error_codes = {
                error["code"]
                for corner in corners
                for error in corner.get("errors", [])
            }

            self.assertEqual("success", payload["status"])
            self.assertEqual("ANALYZED", analysis["status"])
            self.assertEqual("post_lap_only", analysis["pipeline"])
            self.assertEqual(fixture.target_lap_id, analysis["lapId"])
            self.assertEqual(fixture.reference_lap_id, analysis["reference"]["lapId"])
            self.assertEqual("previous_lap", analysis["reference"]["mode"])
            self.assertGreater(summary["totalEstimatedGainS"], 0.0)
            self.assertGreaterEqual(summary["cornerCount"], 3)
            self.assertGreaterEqual(len(top_losses), 3)
            self.assertGreaterEqual(len(error_codes), 6)
            self.assertIn("EARLY_BRAKING", error_codes)
            self.assertIn("LATE_THROTTLE", error_codes)
            self.assertIn("TRAJECTORY_DEVIATION", error_codes)

            for corner in corners[:3]:
                self.assertTrue(corner["primaryError"])
                self.assertTrue(corner["primaryPhase"])
                self.assertTrue(corner["technicalConcept"])
                self.assertTrue(corner["physicalBehavior"])
                self.assertTrue(corner["evidenceTelemetry"])
                self.assertTrue(corner["feedback"])
                self.assertIn("metrics", corner)
                self.assertIn("referenceMetrics", corner)

            cached = service.get_cached_analysis(fixture.target_lap_id)
            self.assertIsNotNone(cached)
            self.assertEqual("ANALYZED", cached["analysis"]["status"])

    def test_desktop_runtime_recordings_are_listed_from_runtime_root(self):
        with tempfile.TemporaryDirectory() as resource_tmp, tempfile.TemporaryDirectory() as runtime_tmp:
            resource_root = Path(resource_tmp)
            runtime_root = Path(runtime_tmp)
            fixture = write_phase14_1_validation_recording(runtime_root)
            service = _make_service(resource_root, runtime_root)

            lap_ids = {lap["lapId"] for lap in service.list_laps()["laps"]}

            self.assertIn(fixture.reference_lap_id, lap_ids)
            self.assertIn(fixture.target_lap_id, lap_ids)

            payload = service.analyze_lap(fixture.target_lap_id, force=True)
            self.assertEqual("ANALYZED", payload["analysis"]["status"])
            self.assertTrue((runtime_root / "data" / "assisted_analysis").exists())

    def test_phase14_endpoints_keep_validity_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = write_phase14_1_validation_recording(root)
            service = _make_service(root)
            previous_service = backend_main.assisted_analysis_service
            backend_main.assisted_analysis_service = service
            try:
                payload = asyncio.run(
                    backend_main.request_phase14_assisted_analysis(
                        fixture.target_lap_id,
                        payload={"force": True},
                    )
                )
                self.assertEqual("ANALYZED", payload["analysis"]["status"])

                cached = asyncio.run(
                    backend_main.get_phase14_assisted_analysis(fixture.target_lap_id)
                )
                self.assertEqual("ANALYZED", cached["analysis"]["status"])

                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(
                        backend_main.request_phase14_assisted_analysis(
                            fixture.invalid_lap_id,
                            payload={
                                "referenceLapId": fixture.reference_lap_id,
                                "force": True,
                            },
                        )
                    )
                self.assertEqual(400, ctx.exception.status_code)
                self.assertIn("not valid", str(ctx.exception.detail))
            finally:
                backend_main.assisted_analysis_service = previous_service

    def test_phase14_lap_telemetry_endpoint_returns_driver_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = write_phase14_1_validation_recording(root)
            service = _make_service(root)
            previous_service = backend_main.assisted_analysis_service
            backend_main.assisted_analysis_service = service
            try:
                payload = asyncio.run(
                    backend_main.get_phase14_assisted_lap_telemetry(
                        fixture.target_lap_id,
                        max_samples=500,
                    )
                )

                self.assertEqual("success", payload["status"])
                self.assertEqual(fixture.target_lap_id, payload["lap"]["lapId"])
                self.assertEqual("VALID", payload["validation"]["status"])
                self.assertGreater(payload["sampleCount"], 40)
                self.assertGreater(len(payload["samples"]), 40)
                sample = payload["samples"][0]
                self.assertIn("speedKmh", sample)
                self.assertIn("throttle", sample)
                self.assertIn("brake", sample)
                self.assertIn("progress", sample)
            finally:
                backend_main.assisted_analysis_service = previous_service

    def test_offline_persisted_lap_viewer_endpoints_do_not_require_live_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = write_phase14_1_validation_recording(root)
            service = _make_service(root)
            repository = SessionRepository(root / "data" / "recordings")
            previous_service = backend_main.assisted_analysis_service
            previous_repository = backend_main.session_repository
            previous_recording_runtime = backend_main.recording_runtime
            backend_main.assisted_analysis_service = service
            backend_main.session_repository = repository
            backend_main.recording_runtime = None
            try:
                sessions = asyncio.run(backend_main.list_recorded_sessions(limit=10))
                self.assertEqual("success", sessions["status"])
                self.assertTrue(sessions["offlineAvailable"])
                self.assertFalse(sessions["liveDependency"])
                self.assertEqual(str(repository.root), sessions["recordingRoot"])
                self.assertIn(fixture.session_id, {session["sessionId"] for session in sessions["sessions"]})

                laps_payload = asyncio.run(backend_main.get_recorded_session_laps(fixture.session_id))
                laps = laps_payload["laps"]
                lap_ids = {lap["lapId"] for lap in laps}
                self.assertIn(fixture.target_lap_id, lap_ids)
                self.assertIn(fixture.invalid_lap_id, lap_ids)

                target = next(lap for lap in laps if lap["lapId"] == fixture.target_lap_id)
                invalid = next(lap for lap in laps if lap["lapId"] == fixture.invalid_lap_id)
                self.assertTrue(target["acceptedByPhase13"])
                self.assertTrue(target["canAnalyze"])
                self.assertFalse(invalid["acceptedByPhase13"])
                self.assertEqual("NOT_ELIGIBLE", invalid["analysisStatus"])

                summary = asyncio.run(backend_main.get_offline_recorded_lap_summary(fixture.target_lap_id))
                self.assertEqual(fixture.target_lap_id, summary["lap"]["lapId"])
                self.assertTrue(summary["offlineAvailable"])
                self.assertFalse(summary["liveDependency"])

                samples = asyncio.run(
                    backend_main.get_offline_recorded_lap_samples(
                        fixture.target_lap_id,
                        limit=120,
                    )
                )
                self.assertEqual(fixture.target_lap_id, samples["lapId"])
                self.assertGreater(samples["totalSampleCount"], 120)
                self.assertLessEqual(samples["returnedSampleCount"], 121)
                self.assertIn("speedKmh", samples["samples"][0])
                self.assertIn("throttle", samples["samples"][0])
                self.assertIn("brake", samples["samples"][0])

                analysis = asyncio.run(
                    backend_main.request_phase14_assisted_analysis(
                        fixture.target_lap_id,
                        payload={"force": True},
                    )
                )
                self.assertEqual("ANALYZED", analysis["analysis"]["status"])

                refreshed = asyncio.run(backend_main.get_offline_recorded_lap_summary(fixture.target_lap_id))
                self.assertTrue(refreshed["lap"]["hasAssistedAnalysis"])
            finally:
                backend_main.assisted_analysis_service = previous_service
                backend_main.session_repository = previous_repository
                backend_main.recording_runtime = previous_recording_runtime


if __name__ == "__main__":
    unittest.main()
