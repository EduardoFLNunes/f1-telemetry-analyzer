import unittest
from pathlib import Path
import sys

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.classification import DrivingErrorClassifier
from core.assisted_analysis.comparison import ReferenceComparator
from core.assisted_analysis.driving_knowledge_base import DrivingKnowledgeBase
from core.assisted_analysis.metrics import CornerMetricsCalculator
from core.assisted_analysis.models import CornerComparison, CornerMetrics, CornerSegment, DrivingError, PhaseBounds
from core.assisted_analysis.utils import normalize_lap_dataframe
from core.assisted_analysis.vehicle_dynamics_analyzer import VehicleDynamicsAnalyzer


class AssistedAnalysisTests(unittest.TestCase):
    def test_normalize_lap_dataframe_converts_mps_speed(self):
        df = normalize_lap_dataframe(
            pd.DataFrame(
                {
                    "driver_id": ["player_1", "player_1"],
                    "lap_number": [3, 3],
                    "timestamp": [1000.0, 1001.0],
                    "s": [0.0, 10.0],
                    "speed": [10.0, 20.0],
                    "throttle": [50.0, 100.0],
                    "brake": [0.0, 25.0],
                }
            ),
            track_length=100.0,
        )

        self.assertAlmostEqual(df["speed_kmh"].iloc[0], 36.0)
        self.assertAlmostEqual(df["throttle"].iloc[0], 0.5)
        self.assertAlmostEqual(df["brake"].iloc[1], 0.25)
        self.assertIn("s_unwrapped", df.columns)

    def test_classifier_detects_late_throttle_and_extra_coasting(self):
        segment = CornerSegment(
            corner_id=1,
            start_s=100.0,
            end_s=170.0,
            apex_s=135.0,
            curvature_peak=0.01,
            phases={
                "entry": PhaseBounds(40.0, 80.0),
                "braking_zone": PhaseBounds(80.0, 120.0),
                "apex": PhaseBounds(120.0, 150.0),
                "exit": PhaseBounds(150.0, 210.0),
                "straight_after": PhaseBounds(210.0, 300.0),
            },
        )
        reference_df = pd.DataFrame(
            {
                "s": [40, 80, 100, 130, 160, 190, 230, 300],
                "s_unwrapped": [40, 80, 100, 130, 160, 190, 230, 300],
                "elapsed_s": [0.0, 1.0, 1.5, 2.0, 2.7, 3.2, 3.7, 4.5],
                "speed_kmh": [250, 230, 180, 120, 145, 180, 220, 250],
                "throttle": [0, 0, 0, 0, 0.35, 0.8, 1.0, 1.0],
                "brake": [0, 0.7, 0.9, 0.2, 0, 0, 0, 0],
                "L": [0.2, 0.3, 0.4, 0.2, 0.3, 0.2, 0.1, 0.1],
            }
        )
        player_df = reference_df.copy()
        player_df["elapsed_s"] = player_df["elapsed_s"] + [0, 0, 0, 0.05, 0.12, 0.18, 0.22, 0.25]
        player_df["throttle"] = [0, 0, 0, 0, 0, 0, 0.35, 1.0]
        player_df["brake"] = [0, 0.7, 0.9, 0.1, 0, 0, 0, 0]

        calculator = CornerMetricsCalculator()
        player = calculator.compute_one(player_df, segment, 500.0)
        reference = calculator.compute_one(reference_df, segment, 500.0)
        comparison = ReferenceComparator().compare({1: player}, {1: reference}, 500.0)[1]
        errors = DrivingErrorClassifier().classify(player, reference, comparison)
        codes = {error.code for error in errors}

        self.assertIn("LATE_THROTTLE", codes)
        self.assertIn("EXCESS_COASTING", codes)

    def test_vehicle_dynamics_derives_rates_and_friction_usage(self):
        segment = CornerSegment(
            corner_id=1,
            start_s=20.0,
            end_s=70.0,
            apex_s=45.0,
            curvature_peak=0.01,
            phases={
                "entry": PhaseBounds(0.0, 15.0),
                "braking_zone": PhaseBounds(15.0, 35.0),
                "apex": PhaseBounds(35.0, 55.0),
                "exit": PhaseBounds(55.0, 85.0),
                "straight_after": PhaseBounds(85.0, 110.0),
            },
        )
        df = pd.DataFrame(
            {
                "s": [0, 15, 30, 45, 60, 75, 90, 105],
                "s_unwrapped": [0, 15, 30, 45, 60, 75, 90, 105],
                "elapsed_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
                "speed_kmh": [220, 180, 130, 100, 120, 155, 190, 215],
                "speed_mps": [61.1, 50.0, 36.1, 27.8, 33.3, 43.1, 52.8, 59.7],
                "throttle": [0, 0, 0, 0.1, 0.4, 0.9, 1.0, 1.0],
                "brake": [0, 0.8, 0.7, 0.1, 0, 0, 0, 0],
                "steering": [0, 0.1, 0.3, 0.45, 0.3, 0.12, 0.02, 0],
                "yaw": [0.0, 0.05, 0.14, 0.25, 0.32, 0.35, 0.36, 0.36],
                "x": [0, 14, 27, 37, 46, 58, 74, 94],
                "z": [0, 2, 8, 17, 25, 29, 30, 30],
                "L": [0.0, 0.2, 0.4, 0.1, -0.1, -0.2, 0.0, 0.1],
            }
        )

        profile = VehicleDynamicsAnalyzer().analyze_corner(df, df, segment, 120.0)
        self.assertGreater(profile.phases["exit"].throttle_application_rate, 0.0)
        self.assertGreater(profile.phases["braking_zone"].brake_release_rate, 0.0)
        self.assertGreater(profile.summary["frictionUsagePeak"], 0.0)

    def test_knowledge_base_enriches_error(self):
        error = DrivingError(
            code="EXIT_OVERSTEER",
            label="Sobresterco na saida",
            phase="exit",
            severity=0.7,
            estimated_gain_s=0.1,
            description="Yaw alto na saida.",
            evidence={"maxYawRate": 1.4},
        )
        enriched = DrivingKnowledgeBase().enrich_error(error)

        self.assertIn("torque", enriched.concept.lower())
        self.assertIn("acelerador", enriched.technique.lower())
        self.assertTrue(enriched.expected_telemetry)

    def test_classifier_detects_poor_exit_from_exit_speed_loss(self):
        player = CornerMetrics(
            corner_id=1,
            segment_time=4.2,
            entry_speed_kmh=205.0,
            min_speed_kmh=112.0,
            exit_speed_kmh=154.0,
            apex_s=130.0,
            brake_start_s=90.0,
            brake_peak=0.9,
            brake_release_s=132.0,
            throttle_pickup_s=166.0,
            full_throttle_s=212.0,
            coasting_distance_m=22.0,
            mean_abs_lateral_offset_m=0.2,
            max_abs_lateral_offset_m=0.4,
            mean_line_deviation_m=0.2,
        )
        reference = CornerMetrics(
            corner_id=1,
            segment_time=3.95,
            entry_speed_kmh=204.0,
            min_speed_kmh=114.0,
            exit_speed_kmh=165.0,
            apex_s=130.0,
            brake_start_s=90.0,
            brake_peak=0.9,
            brake_release_s=130.0,
            throttle_pickup_s=150.0,
            full_throttle_s=190.0,
            coasting_distance_m=15.0,
            mean_abs_lateral_offset_m=0.2,
            max_abs_lateral_offset_m=0.4,
            mean_line_deviation_m=0.2,
        )
        comparison = CornerComparison(
            corner_id=1,
            segment_time_delta_s=0.25,
            entry_speed_delta_kmh=1.0,
            min_speed_delta_kmh=-2.0,
            exit_speed_delta_kmh=-11.0,
            brake_start_delta_m=0.0,
            brake_release_delta_m=2.0,
            apex_delta_m=0.0,
            throttle_pickup_delta_m=16.0,
            full_throttle_delta_m=22.0,
            coasting_delta_m=7.0,
            lateral_offset_delta_m=0.0,
            line_deviation_delta_m=0.0,
        )

        codes = {error.code for error in DrivingErrorClassifier().classify(player, reference, comparison)}

        self.assertIn("POOR_EXIT", codes)


if __name__ == "__main__":
    unittest.main()
