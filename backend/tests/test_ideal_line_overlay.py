import math
import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.ideal_line_overlay import build_racing_line_response
from core.telemetry.telemetry_models import TelemetrySample


def sample(x, z, speed, lap=41, spline=0.0):
    return TelemetrySample(
        timestamp=1.0,
        worldPositionX=x,
        worldPositionY=0.0,
        worldPositionZ=z,
        speed=speed,
        normalizedSplinePosition=spline,
        lap=lap,
        sessionTime=12.5,
    )


class IdealLineOverlayTests(unittest.TestCase):
    def test_visual_line_preserves_available_speed(self):
        response = build_racing_line_response(
            [
                sample(0.0, 0.0, 118.0, spline=0.1),
                sample(10.0, 2.0, 242.0, spline=0.2),
            ],
            source="REFERENCE_LAP",
        )

        visual = response["visualLine"]
        self.assertEqual(visual["source"], "REFERENCE_LAP_SAMPLES")
        self.assertEqual(visual["referenceLapNumber"], 41)
        self.assertEqual(visual["points"][0]["speedKmh"], 118.0)
        self.assertEqual(visual["points"][1]["splinePosition"], 0.2)

    def test_min_and_max_speed_ignore_unknown_values(self):
        response = build_racing_line_response(
            [
                sample(0.0, 0.0, 0.0),
                sample(1.0, 0.0, 90.0),
                sample(2.0, 0.0, 210.0),
            ],
            source="REFERENCE_LAP",
        )

        ideal = response["idealLineOverlay"]
        self.assertIsNone(ideal["points"][0]["speedKmh"])
        self.assertEqual(ideal["minSpeedKmh"], 90.0)
        self.assertEqual(ideal["maxSpeedKmh"], 210.0)

    def test_invalid_coordinates_are_returned_as_null_fields(self):
        response = build_racing_line_response(
            [sample(math.nan, 5.0, 120.0)],
            source="REFERENCE_LAP",
        )

        point = response["idealLineOverlay"]["points"][0]
        self.assertIsNone(point["x"])
        self.assertEqual(point["z"], 5.0)
        self.assertEqual(response["debug"]["pointCount"], 1)

    def test_empty_candidate_reports_unknown_sources(self):
        response = build_racing_line_response([], source="UNKNOWN")

        self.assertEqual(response["idealLineOverlay"]["source"], "UNKNOWN")
        self.assertEqual(response["visualLine"]["source"], "UNKNOWN")
        self.assertEqual(response["idealLineOverlay"]["points"], [])


if __name__ == "__main__":
    unittest.main()
