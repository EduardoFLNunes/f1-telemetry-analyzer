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

    def test_source_rate_recording_keeps_bursty_accepted_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = SessionRecorder(
                RecordingConfig(
                    output_root=Path(tmp),
                    player_record_hz=60.0,
                    source_sample_hz=60.0,
                    batch_size=128,
                    flush_interval_seconds=0.01,
                )
            )
            recorder.start(track="test")
            base_timestamp = 1_781_000_000_000.0
            for index in range(60):
                self.assertTrue(
                    recorder.enqueue_player(
                        {
                            "timestamp": base_timestamp + index * (1000.0 / 60.0),
                            "lap_number": 2,
                            "lap_time": index / 60.0,
                        }
                    )
                )
            recorder.enqueue_player(
                {
                    "timestamp": base_timestamp + 1000.0,
                    "lap_number": 3,
                    "lap_time": 0.0,
                }
            )
            status = recorder.stop()

            self.assertEqual(61, status.playerSamplesReceived)
            self.assertEqual(61, status.playerSamplesEnqueued)
            self.assertEqual(0, status.playerSamplesDownsampled)
            self.assertEqual(0, status.playerSamplesDropped)
            self.assertFalse(status.playerDownsamplingEnabled)
            self.assertEqual(1.0, status.recorderDownsampleRatio)
            self.assertEqual(60, status.lastPersistedLapSampleCount)
            self.assertAlmostEqual(59.0 / 60.0, status.lastPersistedLapDurationSeconds, places=3)

    def test_explicit_downsampling_uses_source_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = SessionRecorder(
                RecordingConfig(
                    output_root=Path(tmp),
                    player_record_hz=20.0,
                    source_sample_hz=60.0,
                    batch_size=128,
                    flush_interval_seconds=0.01,
                )
            )
            recorder.start(track="test")
            base_timestamp = 1_781_000_000_000.0
            for index in range(60):
                recorder.enqueue_player(
                    {
                        "timestamp": base_timestamp + index * (1000.0 / 60.0),
                        "lap_number": 1,
                        "lap_time": index / 60.0,
                    }
                )
            status = recorder.stop()

            self.assertTrue(status.playerDownsamplingEnabled)
            self.assertEqual(60, status.playerSamplesReceived)
            self.assertGreaterEqual(status.playerSamplesEnqueued, 19)
            self.assertLessEqual(status.playerSamplesEnqueued, 21)
            self.assertEqual(
                status.playerSamplesReceived - status.playerSamplesEnqueued,
                status.playerSamplesDownsampled,
            )


if __name__ == "__main__":
    unittest.main()
