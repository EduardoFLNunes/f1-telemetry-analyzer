import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.comparison_analysis import AnalysisSample
from core.racing_line_analysis import (
    build_live_racing_line_payload,
    build_racing_line_model,
    compare_player_to_racing_line,
    detect_coasting_zone,
)
from core.telemetry.telemetry_models import TelemetrySample


def make_analysis_sample(progress, speed, x=None, z=0.0, brake=0.0, throttle=0.0, timestamp=0.0):
    return AnalysisSample(
        progress=progress,
        speed_kmh=speed,
        position=(progress * 1000.0 if x is None else x, 0.0, z),
        timestamp=timestamp,
        lap=1,
        throttle=throttle,
        brake=brake,
    )


def make_telemetry_sample(progress, speed, lap=1, timestamp_seconds=0.0, x=None, z=0.0):
    return TelemetrySample(
        timestamp=timestamp_seconds,
        worldPositionX=progress * 1000.0 if x is None else x,
        worldPositionY=0.0,
        worldPositionZ=z,
        speed=speed,
        normalizedSplinePosition=progress,
        carId=0,
        lap=lap,
        sessionTime=timestamp_seconds,
    )


def valid_reference_lap(lap=1, samples=60, speed_base=160.0):
    return [
        make_telemetry_sample(
            progress=i / (samples - 1),
            speed=speed_base + (i % 10),
            lap=lap,
            timestamp_seconds=float(i),
        )
        for i in range(samples)
    ]


class RacingLineAnalysisTests(unittest.TestCase):
    def test_racing_line_model_splits_samples_by_microsector(self):
        reference = [
            make_analysis_sample(0.10, 100.0),
            make_analysis_sample(0.35, 120.0),
            make_analysis_sample(0.70, 140.0),
        ]

        model = build_racing_line_model(
            reference_samples=reference,
            track="test_track",
            reference_lap_number=3,
            micro_sector_count=3,
        )

        self.assertEqual(model["microSectorCount"], 3)
        self.assertEqual(model["points"][0]["sampleCount"], 1)
        self.assertEqual(model["points"][1]["sampleCount"], 1)
        self.assertEqual(model["points"][2]["sampleCount"], 1)

    def test_live_payload_rejects_missing_reference_lap(self):
        payload = build_live_racing_line_payload(
            telemetry_samples=valid_reference_lap(lap=1),
            track_name="test_track",
            micro_sector_count=5,
        )

        self.assertEqual(payload["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(payload["racingLine"])
        self.assertEqual(payload["debug"]["reason"], "no_previous_complete_lap")

    def test_live_payload_rejects_partial_reference_lap(self):
        partial = [
            make_telemetry_sample(
                progress=0.30 + (0.60 * i / 59),
                speed=170.0,
                lap=1,
                timestamp_seconds=float(i),
            )
            for i in range(60)
        ]
        current = [make_telemetry_sample(0.02 * i, 165.0, lap=2, timestamp_seconds=70.0 + i) for i in range(5)]

        payload = build_live_racing_line_payload(
            telemetry_samples=partial + current,
            track_name="test_track",
            micro_sector_count=5,
        )

        self.assertEqual(payload["status"], "INSUFFICIENT_DATA")
        self.assertEqual(payload["debug"]["reason"], "previous_lap_not_valid_reference")

    def test_live_payload_builds_model_from_valid_reference_lap(self):
        reference = valid_reference_lap(lap=1)
        current = [make_telemetry_sample(0.02 * i, 150.0, lap=2, timestamp_seconds=70.0 + i) for i in range(20)]

        payload = build_live_racing_line_payload(
            telemetry_samples=reference + current,
            track_name="test_track",
            track_data={"trackLength": 1000.0},
            micro_sector_count=10,
        )

        self.assertEqual(payload["status"], "READY")
        self.assertEqual(payload["racingLine"]["source"], "REFERENCE_LAP")
        self.assertEqual(payload["racingLine"]["referenceLapNumber"], 1)
        self.assertGreater(payload["racingLine"]["debug"]["validSegments"], 0)

    def test_live_payload_exposes_reference_samples_for_visual_line(self):
        reference = valid_reference_lap(lap=1, samples=120)
        current = [make_telemetry_sample(0.02 * i, 150.0, lap=2, timestamp_seconds=130.0 + i) for i in range(20)]

        payload = build_live_racing_line_payload(
            telemetry_samples=reference + current,
            track_name="test_track",
            track_data={"trackLength": 1000.0},
            micro_sector_count=10,
        )

        visual_line = payload["racingLine"]["visualLine"]
        self.assertEqual(visual_line["source"], "REFERENCE_LAP_SAMPLES")
        self.assertFalse(visual_line["smoothingApplied"])
        self.assertGreater(visual_line["sampleCount"], payload["racingLine"]["microSectorCount"])
        self.assertGreater(len(visual_line["points"]), payload["racingLine"]["microSectorCount"])
        self.assertIn("splinePosition", visual_line["points"][0])

    def test_racing_line_speed_statistics(self):
        model = build_racing_line_model(
            reference_samples=[
                make_analysis_sample(0.10, 100.0),
                make_analysis_sample(0.20, 120.0),
                make_analysis_sample(0.30, 80.0),
            ],
            track="test_track",
            reference_lap_number=1,
            micro_sector_count=1,
        )

        point = model["points"][0]
        self.assertEqual(point["avgSpeedKmh"], 100.0)
        self.assertEqual(point["minSpeedKmh"], 80.0)
        self.assertEqual(point["maxSpeedKmh"], 120.0)

    def test_racing_line_detects_braking_zone(self):
        model = build_racing_line_model(
            reference_samples=[
                make_analysis_sample(0.10, 220.0),
                make_analysis_sample(0.11, 214.0),
                make_analysis_sample(0.12, 205.0),
                make_analysis_sample(0.13, 190.0),
            ],
            track="test_track",
            reference_lap_number=1,
            micro_sector_count=1,
        )

        self.assertTrue(model["points"][0]["brakingZone"])

    def test_racing_line_detects_acceleration_zone(self):
        model = build_racing_line_model(
            reference_samples=[
                make_analysis_sample(0.40, 90.0),
                make_analysis_sample(0.41, 97.0),
                make_analysis_sample(0.42, 106.0),
                make_analysis_sample(0.43, 118.0),
            ],
            track="test_track",
            reference_lap_number=1,
            micro_sector_count=1,
        )

        self.assertTrue(model["points"][0]["accelerationZone"])

    def test_detects_coasting_zone(self):
        samples = [
            make_analysis_sample(0.50, 180.0),
            make_analysis_sample(0.51, 180.3),
            make_analysis_sample(0.52, 179.9),
            make_analysis_sample(0.53, 180.2),
        ]

        self.assertTrue(detect_coasting_zone(samples))

    def test_trajectory_deviation_to_racing_line_point(self):
        racing_line = {
            "track": "test_track",
            "source": "REFERENCE_LAP",
            "points": [
                {
                    "segmentIndex": 0,
                    "splineStart": 0.0,
                    "splineEnd": 1.0,
                    "sector": 1,
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "avgSpeedKmh": 100.0,
                    "brakingZone": False,
                    "accelerationZone": False,
                }
            ],
        }

        comparison = compare_player_to_racing_line(
            player_samples=[make_analysis_sample(0.50, 100.0, x=3.0, z=4.0)],
            racing_line=racing_line,
        )

        self.assertEqual(comparison["segments"][0]["trajectoryDeviationMeters"], 5.0)
        self.assertEqual(comparison["segments"][0]["mainIssue"], "TRAJECTORY")

    def test_comparison_uses_spline_position_instead_of_timestamp(self):
        reference = [
            make_analysis_sample(0.25, 100.0, x=250.0, timestamp=1000.0),
            make_analysis_sample(0.75, 160.0, x=750.0, timestamp=0.0),
        ]
        model = build_racing_line_model(
            reference_samples=reference,
            track="test_track",
            reference_lap_number=1,
            micro_sector_count=2,
        )
        player = [
            make_analysis_sample(0.25, 95.0, x=255.0, timestamp=0.0),
            make_analysis_sample(0.75, 140.0, x=755.0, timestamp=1000.0),
        ]

        comparison = compare_player_to_racing_line(player_samples=player, racing_line=model)

        self.assertEqual(comparison["segments"][1]["segmentIndex"], 1)
        self.assertEqual(comparison["segments"][1]["speedDeltaKmh"], -20.0)

    def test_comparison_returns_insufficient_data_when_speed_is_missing(self):
        racing_line = {
            "track": "test_track",
            "source": "REFERENCE_LAP",
            "points": [
                {
                    "segmentIndex": 0,
                    "splineStart": 0.0,
                    "splineEnd": 1.0,
                    "sector": 1,
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "avgSpeedKmh": None,
                    "brakingZone": False,
                    "accelerationZone": False,
                }
            ],
        }

        comparison = compare_player_to_racing_line(
            player_samples=[make_analysis_sample(0.5, None, x=0.0)],
            racing_line=racing_line,
        )

        self.assertEqual(comparison["segments"][0]["mainIssue"], "INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
