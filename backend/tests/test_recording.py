import json
import tempfile
import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.recording.recording_models import RecordingConfig
from core.recording.session_recorder import SessionRecorder


class SessionRecorderTests(unittest.TestCase):
    def test_recorder_writes_metadata_player_and_opponents(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = SessionRecorder(
                RecordingConfig(
                    output_root=Path(tmp),
                    player_record_hz=1000.0,
                    opponents_record_hz=1000.0,
                    batch_size=1,
                    flush_interval_seconds=0.01,
                )
            )

            status = recorder.start(track="vhe_interlagos")
            recorder.enqueue_player(
                {
                    "timestamp": 1.0,
                    "sessionTime": None,
                    "speedKmh": 123.0,
                    "carPhysics": {
                        "tyres": {"tyreCoreTemperature": [81.0, 82.0, 83.0, 84.0]},
                        "carState": {"fuel": 31.5},
                    },
                },
                track="vhe_interlagos",
            )
            recorder.enqueue_opponents(
                {
                    "timestamp": 1.1,
                    "track": "vhe_interlagos",
                    "sessionTime": None,
                    "cars": [{"carId": 1, "driverName": "AI", "yaw": None}],
                }
            )
            final = recorder.stop()

            session_dir = Path(status.directory)
            self.assertTrue((session_dir / "metadata.json").exists())
            self.assertTrue((session_dir / "player.jsonl").exists())
            self.assertTrue((session_dir / "opponents.jsonl").exists())
            self.assertEqual(final.playerSamplesWritten, 1)
            self.assertEqual(final.opponentSnapshotsWritten, 1)

            metadata = json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))
            player = json.loads((session_dir / "player.jsonl").read_text(encoding="utf-8").strip())
            opponents = json.loads((session_dir / "opponents.jsonl").read_text(encoding="utf-8").strip())

            self.assertEqual(metadata["track"], "vhe_interlagos")
            self.assertEqual(metadata["schemaVersion"], 2)
            self.assertIsNotNone(metadata["endedAt"])
            self.assertEqual(metadata["playerSamplesWritten"], 1)
            self.assertEqual(player["type"], "player")
            self.assertIsNone(player["sessionTime"])
            self.assertEqual(player["sample"]["carPhysics"]["carState"]["fuel"], 31.5)
            self.assertEqual(
                player["sample"]["carPhysics"]["tyres"]["tyreCoreTemperature"],
                [81.0, 82.0, 83.0, 84.0],
            )
            self.assertEqual(opponents["type"], "opponents")
            self.assertEqual(opponents["count"], 1)
            self.assertIsNone(opponents["cars"][0]["yaw"])


if __name__ == "__main__":
    unittest.main()
