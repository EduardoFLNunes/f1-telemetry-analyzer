import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.car_physics import (
    build_opponent_car_physics,
    build_player_car_physics,
    infer_acceleration_state,
    infer_data_completeness,
    infer_grip_index,
    infer_grip_level,
)
from core.opponents.opponent_models import OpponentCarState
from core.telemetry.telemetry_models import TelemetrySample


def player_sample(progress=0.1, speed=180.0, **overrides):
    data = {
        "timestamp": 1.0,
        "x": progress * 100.0,
        "y": 0.0,
        "z": 0.0,
        "speed": speed,
        "normalized_spline_pos": progress,
        "throttle": 0.75,
        "brake": 0.0,
        "steering": 0.1,
        "gear": 4,
        "rpm": 8200,
        "accel_x": 0.4,
        "accel_y": 0.0,
        "accel_z": 0.2,
        "velocity": {"x": 12.0, "y": 0.0, "z": 35.0},
        "clutch": 0.0,
        "fuel": 24.0,
        "max_fuel": 60.0,
        "ballast": 0.0,
        "abs": 1.0,
        "tc": 2.0,
        "drs": True,
        "turbo_boost": 0.5,
        "air_temp": 24.0,
        "road_temp": 32.0,
        "surface_grip": 0.96,
        "air_density": 1.18,
        "tyre_core_temperature": [82.0, 83.0, 84.0, 85.0],
        "wheels_pressure": [26.1, 26.0, 25.8, 25.9],
        "tyre_wear": [0.05, 0.05, 0.07, 0.07],
        "tyre_dirty_level": [0.1, 0.1, 0.2, 0.2],
        "wheel_slip": [0.02, 0.02, 0.04, 0.04],
        "wheel_load": [3200.0, 3180.0, 3300.0, 3310.0],
        "suspension_travel": [0.08, 0.08, 0.09, 0.09],
        "ride_height": [0.055, 0.062],
        "camber_rad": [-0.05, -0.05, -0.04, -0.04],
        "car_damage": [0.0, 0.0, 0.0, 0.0, 0.0],
    }
    data.update(overrides)
    return TelemetrySample.from_dict(data)


class CarPhysicsTelemetryTests(unittest.TestCase):
    def test_player_physics_with_complete_assetto_data(self):
        samples = [
            player_sample(progress=0.10, speed=160.0),
            player_sample(progress=0.11, speed=166.0),
            player_sample(progress=0.12, speed=174.0),
            player_sample(progress=0.13, speed=182.0),
        ]

        telemetry = build_player_car_physics(samples[-1], samples)

        self.assertEqual(telemetry["source"]["dataCompleteness"], "FULL")
        self.assertEqual(telemetry["source"]["playerPhysicsAvailable"], True)
        self.assertEqual(telemetry["motion"]["speedKmh"], 182.0)
        self.assertEqual(telemetry["controls"]["throttle"], 0.75)
        self.assertEqual(telemetry["controls"]["gear"], 4.0)
        self.assertEqual(telemetry["tyres"]["tyreCoreTemperature"], [82.0, 83.0, 84.0, 85.0])
        self.assertEqual(telemetry["environment"]["surfaceGrip"], 0.96)
        self.assertEqual(telemetry["inferred"]["estimatedAccelerationState"], "ACCELERATING")
        self.assertTrue(telemetry["availability"]["hasRealTyreData"])

    def test_player_physics_with_partial_null_data(self):
        sample = player_sample(
            tyre_core_temperature=None,
            wheels_pressure=None,
            tyre_wear=None,
            tyre_dirty_level=None,
            wheel_slip=None,
            wheel_load=None,
            suspension_travel=None,
            ride_height=None,
            camber_rad=None,
            air_temp=None,
            road_temp=None,
            surface_grip=None,
            air_density=None,
        )

        telemetry = build_player_car_physics(sample, [sample])

        self.assertEqual(telemetry["source"]["dataCompleteness"], "PARTIAL")
        self.assertEqual(telemetry["tyres"]["wheelSlip"], [None, None, None, None])
        self.assertFalse(telemetry["availability"]["hasRealTyreData"])
        self.assertFalse(telemetry["availability"]["hasRealEnvironmentData"])
        self.assertEqual(telemetry["inferred"]["estimatedGripLevel"], "UNKNOWN")

    def test_opponent_physics_uses_minimal_real_data_only(self):
        opponent = OpponentCarState(
            carId=7,
            speedKmh=190.0,
            splinePosition=0.42,
            worldPositionX=1.0,
            worldPositionY=0.0,
            worldPositionZ=2.0,
        )
        history = [
            OpponentCarState(carId=7, speedKmh=180.0, splinePosition=0.40),
            OpponentCarState(carId=7, speedKmh=185.0, splinePosition=0.41),
            opponent,
        ]

        telemetry = build_opponent_car_physics(opponent, history)

        self.assertEqual(telemetry["source"]["dataCompleteness"], "MINIMAL")
        self.assertEqual(telemetry["motion"]["speedKmh"], 190.0)
        self.assertIsNone(telemetry["controls"]["throttle"])
        self.assertIsNone(telemetry["controls"]["brake"])
        self.assertEqual(telemetry["tyres"]["tyrePressure"], [None, None, None, None])
        self.assertFalse(telemetry["availability"]["hasRealThrottle"])
        self.assertFalse(telemetry["availability"]["hasRealTyreData"])
        self.assertEqual(telemetry["inferred"]["estimatedAccelerationState"], "ACCELERATING")

    def test_infer_braking_accelerating_coasting_and_unknown(self):
        braking = [
            {"splinePosition": 0.10, "speedKmh": 220.0},
            {"splinePosition": 0.11, "speedKmh": 214.0},
            {"splinePosition": 0.12, "speedKmh": 205.0},
            {"splinePosition": 0.13, "speedKmh": 190.0},
        ]
        accelerating = [
            {"splinePosition": 0.20, "speedKmh": 100.0},
            {"splinePosition": 0.21, "speedKmh": 106.0},
            {"splinePosition": 0.22, "speedKmh": 114.0},
            {"splinePosition": 0.23, "speedKmh": 124.0},
        ]
        coasting = [
            {"splinePosition": 0.30, "speedKmh": 180.0},
            {"splinePosition": 0.31, "speedKmh": 180.4},
            {"splinePosition": 0.32, "speedKmh": 179.8},
            {"splinePosition": 0.33, "speedKmh": 180.2},
        ]

        self.assertEqual(infer_acceleration_state(braking), "BRAKING")
        self.assertEqual(infer_acceleration_state(accelerating), "ACCELERATING")
        self.assertEqual(infer_acceleration_state(coasting), "COASTING")
        self.assertEqual(infer_acceleration_state(coasting[:2]), "UNKNOWN")

    def test_grip_and_completeness_helpers(self):
        grip_index = infer_grip_index(
            [82.0, 84.0, 85.0, 86.0],
            [0.05, 0.05, 0.05, 0.05],
            [0.0, 0.0, 0.0, 0.0],
            [0.01, 0.01, 0.02, 0.02],
            [3000.0, 3100.0, 3200.0, 3300.0],
            0.98,
        )

        self.assertIsNotNone(grip_index)
        self.assertEqual(infer_grip_level(grip_index), "HIGH")
        self.assertEqual(infer_data_completeness({"availability": {}}), "MINIMAL")
        self.assertEqual(
            infer_data_completeness(
                {
                    "availability": {
                        "hasRealThrottle": True,
                        "hasRealBrake": True,
                    }
                }
            ),
            "PARTIAL",
        )
        self.assertEqual(
            infer_data_completeness(
                {
                    "availability": {
                        "hasRealThrottle": True,
                        "hasRealBrake": True,
                        "hasRealTyreData": True,
                        "hasRealSuspensionData": True,
                        "hasRealEnvironmentData": True,
                    }
                }
            ),
            "FULL",
        )


if __name__ == "__main__":
    unittest.main()
