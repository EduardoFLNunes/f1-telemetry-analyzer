import asyncio
import tempfile
import unittest
from pathlib import Path
import sys

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
from core.telemetry.telemetry_buffer import TelemetryBuffer  # noqa: E402


def _make_service(repo_root: Path) -> AssistedAnalysisService:
    return AssistedAnalysisService(
        repo_root,
        TelemetryBuffer(max_size=5000),
        RuntimeState(),
        TrackCache(str(repo_root / "data" / "cache" / "tracks")),
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


if __name__ == "__main__":
    unittest.main()
