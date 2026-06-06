import asyncio
import math
from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.physics_lap_model import (
    _PHYSICS_TARGET_CACHE,
    aggregate_physics_profile_to_microsectors,
    apply_backward_braking_pass,
    apply_forward_acceleration_pass,
    build_physics_fast_lap_report,
    compute_cumulative_distance,
    compute_curvature_profile,
    estimate_corner_speed_limit,
    extract_visual_line_samples,
)


def line_point(progress, x, z, speed=180.0, brake=0.0, throttle=0.5):
    return {
        "splinePosition": progress,
        "position": {"x": x, "y": 0.0, "z": z},
        "speedKmh": speed,
        "brake": brake,
        "throttle": throttle,
        "timestamp": progress * 100.0,
    }


def straight_visual_points(count=60, speed=180.0):
    return [
        line_point(i / (count - 1), i * 10.0, 0.0, speed=speed)
        for i in range(count)
    ]


def curved_visual_points(count=80, radius=80.0):
    points = []
    for i in range(count):
        progress = i / (count - 1)
        angle = progress * math.pi
        points.append(
            line_point(
                progress,
                radius * math.cos(angle),
                radius * math.sin(angle),
                speed=165.0 + 12.0 * math.sin(angle),
            )
        )
    return points


def comparison_segments(count=50, player_speed=170.0, reference_speed=180.0):
    result = []
    for index in range(count):
        start = index / count
        end = (index + 1) / count
        sector = 1 if (start + end) / 2.0 < 1 / 3 else (2 if (start + end) / 2.0 < 2 / 3 else 3)
        result.append(
            {
                "segmentIndex": index,
                "splineStart": start,
                "splineEnd": end,
                "sector": sector,
                "playerSpeedKmh": player_speed,
                "racingLineSpeedKmh": reference_speed,
                "speedDeltaKmh": player_speed - reference_speed,
                "trajectoryDeviationMeters": 1.0,
                "playerBraking": False,
                "racingLineBraking": False,
                "playerAccelerating": False,
                "racingLineAccelerating": False,
                "estimatedDeltaSeconds": 0.02,
                "mainIssue": "LOW_CORNER_SPEED",
                "message": "test",
            }
        )
    return result


def ready_payload(points=None, micro_sectors=50):
    visual_points = points or curved_visual_points()
    return {
        "track": "test_track",
        "status": "READY",
        "racingLine": {
            "track": "test_track",
            "source": "BEST_LAP",
            "referenceLapNumber": 7,
            "microSectorCount": micro_sectors,
            "generatedAt": "2026-06-02T00:00:00Z",
            "points": [],
            "visualLine": {
                "source": "REFERENCE_LAP_SAMPLES",
                "sampleCount": len(visual_points),
                "displayPointCount": len(visual_points),
                "downsampleStride": 1,
                "smoothingApplied": False,
                "points": visual_points,
            },
            "debug": {
                "inputSamples": len(visual_points),
                "validSegments": micro_sectors,
                "rejectedSegments": 0,
            },
        },
        "comparison": {
            "segments": comparison_segments(micro_sectors),
            "debug": {"validComparisonSegments": micro_sectors},
        },
        "fastestLaps": [
            {
                "lapNumber": 7,
                "durationSeconds": 78.5,
                "valid": True,
                "usedForRacingLine": True,
            }
        ],
        "debug": {"lapSelection": {"referenceLap": 7, "currentLap": 8}},
    }


class PhysicsLapModelTests(unittest.TestCase):
    def setUp(self):
        _PHYSICS_TARGET_CACHE.clear()

    def test_insufficient_data_without_racing_line(self):
        report = build_physics_fast_lap_report({"track": "test", "status": "INSUFFICIENT_DATA", "racingLine": None})

        self.assertEqual(report["status"], "INSUFFICIENT_DATA")
        self.assertEqual(report["segments"], [])

    def test_extracts_visual_line_samples(self):
        samples = extract_visual_line_samples(ready_payload(straight_visual_points(8)))

        self.assertEqual(len(samples), 8)
        self.assertEqual(samples[0]["source"], "VISUAL_LINE")
        self.assertEqual(samples[-1]["splinePosition"], 1.0)

    def test_calculates_cumulative_distance(self):
        samples = [
            {"x": 0.0, "z": 0.0},
            {"x": 3.0, "z": 4.0},
            {"x": 6.0, "z": 8.0},
        ]

        self.assertEqual(compute_cumulative_distance(samples), [0.0, 5.0, 10.0])

    def test_calculates_curvature_for_simple_curve(self):
        samples = [
            {"x": 10.0, "z": 0.0},
            {"x": 7.071, "z": 7.071},
            {"x": 0.0, "z": 10.0},
        ]

        curvature = compute_curvature_profile(samples)

        self.assertIsNotNone(curvature[1])
        self.assertAlmostEqual(curvature[1], 0.1, delta=0.01)

    def test_returns_low_curvature_on_straight(self):
        samples = [{"x": float(i), "z": 0.0} for i in range(5)]

        curvature = compute_curvature_profile(samples)

        self.assertTrue(all(value is None or value <= 1e-6 for value in curvature))

    def test_speed_limit_is_lower_for_tighter_curve(self):
        open_curve = estimate_corner_speed_limit(0.01, 1.5)
        tight_curve = estimate_corner_speed_limit(0.12, 1.5)

        self.assertIsNotNone(open_curve)
        self.assertIsNotNone(tight_curve)
        self.assertLess(tight_curve, open_curve)

    def test_forward_acceleration_pass_respects_limit(self):
        profile = apply_forward_acceleration_pass([10.0, 100.0], [0.0, 10.0], 2.0)

        self.assertAlmostEqual(profile[1], math.sqrt(10.0**2 + 2 * 2.0 * 10.0), places=4)

    def test_backward_braking_pass_respects_limit(self):
        profile = apply_backward_braking_pass([100.0, 10.0], [0.0, 10.0], 2.0)

        self.assertAlmostEqual(profile[0], math.sqrt(10.0**2 + 2 * 2.0 * 10.0), places=4)

    def test_aggregates_profile_to_microsectors(self):
        profile = [
            {
                "splinePosition": i / 9,
                "distanceMeters": i * 10.0,
                "curvature": 0.01,
                "physicsTargetSpeedMs": 40.0,
                "referenceSpeedKmh": 150.0,
                "limitingFactor": "CURVATURE",
            }
            for i in range(10)
        ]

        segments = aggregate_physics_profile_to_microsectors(profile, 2)

        self.assertEqual(len(segments), 2)
        self.assertIsNotNone(segments[0]["physicsTargetTimeSeconds"])
        self.assertEqual(segments[0]["limitingFactor"], "CURVATURE")

    def test_report_groups_microsectors(self):
        report = build_physics_fast_lap_report(ready_payload(curved_visual_points(), micro_sectors=10), micro_sectors=10)

        self.assertEqual(report["status"], "READY")
        self.assertEqual(len(report["segments"]), 10)
        self.assertIsNotNone(report["summary"]["estimatedPhysicsLapTimeSeconds"])

    def test_report_compares_player_to_physics_target(self):
        report = build_physics_fast_lap_report(ready_payload(curved_visual_points(), micro_sectors=10), micro_sectors=10)

        valid = [segment for segment in report["segments"] if segment["playerVsPhysicsDeltaSeconds"] is not None]
        self.assertTrue(valid)
        self.assertIsNotNone(report["summary"]["playerLossToPhysicsSeconds"])

    def test_invalid_segment_returns_nulls_without_breaking(self):
        points = [
            line_point(0.0, 0.0, 0.0),
            line_point(0.5, 400.0, 0.0),
            line_point(1.0, 800.0, 0.0),
        ]
        report = build_physics_fast_lap_report(ready_payload(points, micro_sectors=5), micro_sectors=5)

        self.assertEqual(report["status"], "INSUFFICIENT_DATA")
        self.assertEqual(report["summary"]["estimatedPhysicsLapTimeSeconds"], None)

    def test_cache_does_not_change_segments(self):
        payload = ready_payload(curved_visual_points(), micro_sectors=10)

        first = build_physics_fast_lap_report(payload, micro_sectors=10)
        second = build_physics_fast_lap_report(payload, micro_sectors=10)

        self.assertFalse(first["debug"]["physicsTargetCacheHit"])
        self.assertTrue(second["debug"]["physicsTargetCacheHit"])
        self.assertEqual(first["segments"], second["segments"])

    def test_default_parameters_are_marked(self):
        report = build_physics_fast_lap_report(ready_payload(curved_visual_points(), micro_sectors=10), micro_sectors=10)

        self.assertEqual(report["parameters"]["maxLateralG"]["source"], "CONFIG_DEFAULT")
        self.assertIn("massKg", report["debug"]["unavailableParameters"])

    def test_null_fields_do_not_break_model(self):
        points = straight_visual_points(12)
        points[4]["speedKmh"] = None
        points[5]["position"]["x"] = None
        report = build_physics_fast_lap_report(ready_payload(points, micro_sectors=4), micro_sectors=4)

        self.assertIn(report["status"], {"READY", "INSUFFICIENT_DATA"})

    def test_endpoint_returns_payload_without_lifespan(self):
        import main

        route_paths = {route.path for route in main.app.routes}
        response = asyncio.run(main.get_analysis_physics_fast_lap(microSectors=50))

        self.assertIn("/api/analysis/physics-fast-lap", route_paths)
        self.assertIn(response["status"], {"READY", "INSUFFICIENT_DATA"})


if __name__ == "__main__":
    unittest.main()
