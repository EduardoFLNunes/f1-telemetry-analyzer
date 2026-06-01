import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.comparison_analysis import (
    AnalysisSample,
    build_comparison_analysis,
    build_live_comparison_payload,
    build_microsectors,
    detect_acceleration_zone,
    detect_braking_zone,
    estimate_segment_time_seconds,
    speed_stats,
)
from core.opponents.opponent_models import OpponentCarState
from core.telemetry.telemetry_models import TelemetrySample


def make_player_sample(progress, speed, lap=1, timestamp_seconds=0.0, car_id=0):
    return TelemetrySample(
        timestamp=timestamp_seconds * 1000.0,
        worldPositionX=progress * 1000.0,
        worldPositionY=0.0,
        worldPositionZ=0.0,
        speed=speed,
        normalizedSplinePosition=progress,
        carId=car_id,
        lap=lap,
        sessionTime=timestamp_seconds,
    )


class ComparisonAnalysisTests(unittest.TestCase):
    def test_microsector_split_and_sector_assignment(self):
        sectors = build_microsectors(6)

        self.assertEqual(len(sectors), 6)
        self.assertEqual(sectors[0]["splineStart"], 0.0)
        self.assertEqual(sectors[-1]["splineEnd"], 1.0)
        self.assertEqual([segment["sector"] for segment in sectors], [1, 1, 2, 2, 3, 3])

    def test_speed_stats(self):
        stats = speed_stats(
            [
                AnalysisSample(progress=0.1, speed_kmh=100.0, position=None),
                AnalysisSample(progress=0.2, speed_kmh=120.0, position=None),
                AnalysisSample(progress=0.3, speed_kmh=80.0, position=None),
            ]
        )

        self.assertEqual(stats["avgSpeedKmh"], 100.0)
        self.assertEqual(stats["minSpeedKmh"], 80.0)
        self.assertEqual(stats["maxSpeedKmh"], 120.0)

    def test_detect_braking_from_speed_drop(self):
        samples = [
            AnalysisSample(progress=0.10, speed_kmh=220.0, position=None),
            AnalysisSample(progress=0.11, speed_kmh=215.0, position=None),
            AnalysisSample(progress=0.12, speed_kmh=205.0, position=None),
            AnalysisSample(progress=0.13, speed_kmh=190.0, position=None),
            AnalysisSample(progress=0.14, speed_kmh=178.0, position=None),
        ]

        result = detect_braking_zone(samples)

        self.assertTrue(result["detected"])
        self.assertEqual(result["source"], "speed_inference")

    def test_detect_acceleration_from_speed_gain(self):
        samples = [
            AnalysisSample(progress=0.40, speed_kmh=90.0, position=None),
            AnalysisSample(progress=0.41, speed_kmh=96.0, position=None),
            AnalysisSample(progress=0.42, speed_kmh=104.0, position=None),
            AnalysisSample(progress=0.43, speed_kmh=115.0, position=None),
            AnalysisSample(progress=0.44, speed_kmh=128.0, position=None),
        ]

        result = detect_acceleration_zone(samples)

        self.assertTrue(result["detected"])
        self.assertEqual(result["source"], "speed_inference")

    def test_estimated_delta_time_uses_average_speed_and_distance(self):
        slow = estimate_segment_time_seconds(100.0, 100.0)
        fast = estimate_segment_time_seconds(200.0, 100.0)

        self.assertAlmostEqual(slow, 3.6)
        self.assertAlmostEqual(fast, 1.8)
        self.assertAlmostEqual(slow - fast, 1.8)

    def test_missing_data_returns_null_metrics(self):
        payload = build_comparison_analysis(
            player_samples=[AnalysisSample(progress=0.1, speed_kmh=None, position=None)],
            reference_samples=[],
            opponents_by_car_id={},
            track_data={"trackLength": 1000.0},
            micro_sector_count=1,
        )

        segment = payload["segments"][0]
        self.assertIsNone(segment["player"]["avgSpeedKmh"])
        self.assertIsNone(segment["playerVsReference"]["deltaSeconds"])
        self.assertIsNone(segment["playerVsReference"]["mainLossReason"])

    def test_live_payload_filters_car_id_zero_from_opponents(self):
        telemetry = [
            make_player_sample(i / 50.0, 180.0, lap=1, timestamp_seconds=float(i))
            for i in range(50)
        ] + [
            make_player_sample(0.02 * i, 170.0, lap=2, timestamp_seconds=60.0 + i)
            for i in range(10)
        ]
        opponent_history = {
            0: [
                OpponentCarState(
                    carId=0,
                    isPlayer=True,
                    speedKmh=250.0,
                    splinePosition=0.1,
                    worldPositionX=0.0,
                    worldPositionY=0.0,
                    worldPositionZ=0.0,
                )
            ],
            3: [
                OpponentCarState(
                    carId=3,
                    speedKmh=190.0,
                    splinePosition=0.1,
                    worldPositionX=10.0,
                    worldPositionY=0.0,
                    worldPositionZ=0.0,
                )
            ],
        }

        payload = build_live_comparison_payload(
            telemetry_samples=telemetry,
            opponent_history=opponent_history,
            track_data={"trackLength": 1000.0},
            micro_sector_count=1,
        )

        opponent_ids = [opponent["carId"] for opponent in payload["segments"][0]["opponents"]]
        self.assertEqual(opponent_ids, [3])
        self.assertEqual(payload["debug"]["opponentsAnalyzed"], 1)


if __name__ == "__main__":
    unittest.main()
