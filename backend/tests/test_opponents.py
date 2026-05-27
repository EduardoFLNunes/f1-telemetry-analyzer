import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.opponents import OpponentsStateBuffer, OpponentsTelemetryReceiver


class OpponentsTelemetryTests(unittest.TestCase):
    def test_valid_payload_with_two_opponents(self):
        buffer = OpponentsStateBuffer()
        receiver = OpponentsTelemetryReceiver(buffer, event_bus=None)
        result = receiver.handle_payload(
            {
                "type": "opponents_snapshot",
                "timestamp": 123456.789,
                "sessionTime": 348.22,
                "playerCarId": 0,
                "cars": [
                    {"carId": 1, "driverName": "AI 1", "isPlayer": False, "speedKmh": 173.2},
                    {"carId": 2, "driverName": "AI 2", "isPlayer": False, "speedKmh": 160.0},
                ],
            }
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.accepted_count, 2)
        self.assertEqual(set(buffer.latest().keys()), {1, 2})

    def test_payload_containing_player_ignores_player(self):
        buffer = OpponentsStateBuffer()
        result = buffer.update_snapshot(
            [
                {"carId": 0, "driverName": "Player", "isPlayer": True},
                {"carId": 1, "driverName": "AI 1", "isPlayer": False},
            ],
            timestamp=123456.789,
            session_time=348.22,
            player_car_id=0,
        )

        latest = buffer.latest()
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.ignored_player_count, 1)
        self.assertNotIn(0, latest)
        self.assertIn(1, latest)

    def test_payload_with_missing_fields_does_not_break(self):
        buffer = OpponentsStateBuffer()
        result = buffer.update_snapshot(
            [{"carId": 7}],
            timestamp=123456.789,
            session_time=None,
            player_car_id=0,
        )

        car = buffer.latest()[7]
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(car.status, "unknown")
        self.assertIsNone(car.speedKmh)
        self.assertIsNone(car.worldPositionX)

    def test_latest_returns_cars_by_car_id(self):
        buffer = OpponentsStateBuffer()
        buffer.update_snapshot([{"carId": 3}, {"carId": 4}], timestamp=1.0)

        latest = buffer.latest()
        self.assertEqual(set(latest.keys()), {3, 4})

    def test_update_same_car_id_replaces_previous_values(self):
        buffer = OpponentsStateBuffer()
        buffer.update_snapshot(
            [
                {
                    "carId": 5,
                    "driverName": "AI Driver",
                    "worldPosition": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "speedKmh": 100.0,
                }
            ],
            timestamp=1.0,
        )
        buffer.update_snapshot(
            [{"carId": 5, "speedKmh": 150.0, "worldPosition": {"x": 9.0}}],
            timestamp=2.0,
        )

        car = buffer.latest()[5]
        self.assertEqual(car.speedKmh, 150.0)
        self.assertEqual(car.timestamp, 2.0)
        self.assertEqual(car.driverName, "AI Driver")
        self.assertEqual(car.worldPositionX, 9.0)
        self.assertEqual(car.worldPositionY, 2.0)

    def test_stale_car_is_hidden_from_latest(self):
        now = [100.0]
        buffer = OpponentsStateBuffer(stale_after_seconds=1.0, time_provider=lambda: now[0])
        buffer.update_snapshot([{"carId": 1, "driverName": "AI 1"}], timestamp=10.0)

        self.assertIn(1, buffer.latest())
        now[0] = 102.0
        self.assertNotIn(1, buffer.latest())

    def test_track_change_resets_previous_opponents(self):
        buffer = OpponentsStateBuffer()
        buffer.update_snapshot(
            [{"carId": 1, "driverName": "Interlagos AI"}],
            timestamp=1.0,
            track="ks_interlagos",
        )
        result = buffer.update_snapshot(
            [{"carId": 2, "driverName": "Monza AI"}],
            timestamp=2.0,
            track="monza",
        )

        latest = buffer.latest()
        self.assertEqual(result.reset_reason, "track_changed")
        self.assertNotIn(1, latest)
        self.assertIn(2, latest)

    def test_session_time_rollback_resets_previous_opponents(self):
        buffer = OpponentsStateBuffer(session_reset_threshold_seconds=5.0)
        buffer.update_snapshot(
            [{"carId": 1, "driverName": "Old Session AI"}],
            timestamp=1.0,
            session_time=300.0,
        )
        result = buffer.update_snapshot(
            [{"carId": 2, "driverName": "New Session AI"}],
            timestamp=2.0,
            session_time=10.0,
        )

        latest = buffer.latest()
        self.assertEqual(result.reset_reason, "session_reset")
        self.assertNotIn(1, latest)
        self.assertIn(2, latest)


if __name__ == "__main__":
    unittest.main()
