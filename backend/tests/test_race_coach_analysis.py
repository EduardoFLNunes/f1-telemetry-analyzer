import unittest
from pathlib import Path
import sys
import asyncio

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.race_coach_analysis import build_coaching_report


def segment(index, issue="UNKNOWN", **overrides):
    data = {
        "segmentIndex": index,
        "splineStart": index / 50,
        "splineEnd": (index + 1) / 50,
        "sector": 1 if index < 17 else (2 if index < 34 else 3),
        "playerSpeedKmh": 150.0,
        "racingLineSpeedKmh": 158.0,
        "speedDeltaKmh": -8.0,
        "trajectoryDeviationMeters": 1.5,
        "playerBraking": False,
        "racingLineBraking": False,
        "playerAccelerating": False,
        "racingLineAccelerating": False,
        "estimatedDeltaSeconds": 0.10,
        "mainIssue": issue,
        "message": "test",
    }
    data.update(overrides)
    return data


def ready_payload(segments):
    return {
        "track": "test_track",
        "status": "READY",
        "racingLine": {
            "track": "test_track",
            "source": "BEST_LAP",
            "referenceLapNumber": 41,
            "microSectorCount": 50,
            "points": [],
            "debug": {},
        },
        "comparison": {
            "track": "test_track",
            "generatedAt": "2026-06-02T00:00:00Z",
            "comparedAgainst": "BEST_LAP",
            "sectorSummary": [],
            "biggestLosses": [],
            "biggestGains": [],
            "segments": segments,
            "debug": {
                "playerSamples": 100,
                "racingLinePoints": 50,
                "validComparisonSegments": len(segments),
                "rejectedComparisonSegments": 0,
                "reasonForRejectedSegments": [],
            },
        },
        "debug": {
            "lapSelection": {
                "currentLap": 42,
                "referenceLap": 41,
                "selectionMode": "FASTEST_VALID_LAP",
            }
        },
    }


class RaceCoachAnalysisTests(unittest.TestCase):
    def test_insufficient_data_when_racing_line_not_ready(self):
        report = build_coaching_report(
            {
                "track": "test_track",
                "status": "INSUFFICIENT_DATA",
                "racingLine": None,
                "comparison": None,
                "debug": {"reason": "no_valid_reference_lap"},
            }
        )

        self.assertEqual(report["status"], "INSUFFICIENT_DATA")
        self.assertEqual(report["topInsights"], [])
        self.assertEqual(report["debug"]["racingLineStatus"], "INSUFFICIENT_DATA")

    def test_generates_low_corner_speed_insight(self):
        report = build_coaching_report(ready_payload([segment(20, "LOW_CORNER_SPEED")]))

        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["topInsights"][0]["type"], "LOW_CORNER_SPEED")
        self.assertIn("Velocidade", report["topInsights"][0]["evidence"][0])

    def test_generates_braking_too_early_insight(self):
        report = build_coaching_report(
            ready_payload([
                segment(10, "BRAKING_TOO_EARLY", playerBraking=True, racingLineBraking=False)
            ])
        )

        self.assertEqual(report["topInsights"][0]["type"], "BRAKING_TOO_EARLY")

    def test_generates_accelerating_too_late_insight(self):
        report = build_coaching_report(
            ready_payload([
                segment(35, "ACCELERATING_TOO_LATE", playerAccelerating=False, racingLineAccelerating=True)
            ])
        )

        self.assertEqual(report["topInsights"][0]["type"], "ACCELERATING_TOO_LATE")

    def test_generates_trajectory_deviation_insight(self):
        report = build_coaching_report(
            ready_payload([
                segment(22, "TRAJECTORY", trajectoryDeviationMeters=6.2, estimatedDeltaSeconds=0.12)
            ])
        )

        self.assertEqual(report["topInsights"][0]["type"], "TRAJECTORY_DEVIATION")

    def test_does_not_invent_cause_when_confidence_is_insufficient(self):
        report = build_coaching_report(
            ready_payload([
                segment(
                    5,
                    "INSUFFICIENT_DATA",
                    playerSpeedKmh=None,
                    racingLineSpeedKmh=None,
                    speedDeltaKmh=None,
                    estimatedDeltaSeconds=None,
                    trajectoryDeviationMeters=None,
                )
            ])
        )

        self.assertEqual(report["topInsights"][0]["type"], "INSUFFICIENT_DATA")
        self.assertEqual(report["topInsights"][0]["confidence"], "INSUFFICIENT_DATA")

    def test_groups_consecutive_microsectors_with_same_problem(self):
        report = build_coaching_report(
            ready_payload([
                segment(21, "LOW_CORNER_SPEED", estimatedDeltaSeconds=0.05),
                segment(22, "LOW_CORNER_SPEED", estimatedDeltaSeconds=0.06),
                segment(23, "LOW_CORNER_SPEED", estimatedDeltaSeconds=0.07),
            ])
        )

        low_corner = [item for item in report["topInsights"] if item["type"] == "LOW_CORNER_SPEED"]
        self.assertEqual(len(low_corner), 1)
        self.assertEqual(low_corner[0]["estimatedDeltaSeconds"], 0.18)
        self.assertIn("21-23", low_corner[0]["evidence"][0])

    def test_limits_top_insights(self):
        issues = [
            "LOW_CORNER_SPEED",
            "BRAKING_TOO_EARLY",
            "ACCELERATING_TOO_LATE",
            "TRAJECTORY",
            "LOW_EXIT_SPEED",
            "BRAKING_TOO_LATE",
        ]
        segments = [
            segment(index, issues[index % len(issues)], estimatedDeltaSeconds=0.05 + index * 0.01)
            for index in range(12)
        ]

        report = build_coaching_report(ready_payload(segments))

        self.assertLessEqual(len(report["topInsights"]), 6)

    def test_generates_sector_insights(self):
        report = build_coaching_report(
            ready_payload([
                segment(5, "BRAKING_TOO_EARLY", estimatedDeltaSeconds=0.04),
                segment(20, "LOW_CORNER_SPEED", estimatedDeltaSeconds=0.12),
                segment(40, "ACCELERATING_TOO_LATE", estimatedDeltaSeconds=0.08),
            ])
        )

        self.assertEqual(len(report["sectorInsights"]), 3)
        self.assertEqual(report["summary"]["worstSector"], 2)

    def test_does_not_depend_on_visual_line(self):
        payload = ready_payload([segment(20, "LOW_CORNER_SPEED")])
        self.assertNotIn("visualLine", payload["racingLine"])

        report = build_coaching_report(payload)

        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["referenceLapNumber"], 41)

    def test_null_fields_do_not_break_report(self):
        report = build_coaching_report(
            ready_payload([
                segment(
                    7,
                    "UNKNOWN",
                    playerSpeedKmh=None,
                    racingLineSpeedKmh=None,
                    speedDeltaKmh=None,
                    trajectoryDeviationMeters=None,
                    estimatedDeltaSeconds=None,
                    playerBraking=None,
                    racingLineBraking=None,
                    playerAccelerating=None,
                    racingLineAccelerating=None,
                )
            ])
        )

        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["topInsights"], [])

    def test_live_coach_endpoint_returns_payload_without_lifespan(self):
        import main

        route_paths = {route.path for route in main.app.routes}
        response = asyncio.run(main.get_live_coach(microSectors=50))

        self.assertIn("/api/live/coach", route_paths)
        self.assertIn(response["status"], {"READY", "INSUFFICIENT_DATA"})


if __name__ == "__main__":
    unittest.main()
