import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.recording.session_repository import SessionRepository


class SessionRepositoryTests(unittest.TestCase):
    def test_indexes_completed_laps_and_returns_full_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "2026-06-14_10-00-00_ks_monza"
            session.mkdir()
            (session / "metadata.json").write_text(
                json.dumps(
                    {
                        "sessionId": session.name,
                        "track": "ks_monza",
                        "startedAt": "2026-06-14T10:00:00",
                        "playerRecordHz": 60.0,
                        "metadata": {"source": "assetto_corsa"},
                    }
                ),
                encoding="utf-8",
            )

            rows = []
            for index in range(45):
                rows.append(
                    {
                        "type": "player",
                        "track": "ks_monza",
                        "sample": {
                            "lap_number": 2,
                            "sessionTime": 100.0 + index,
                            "lapProgress": index / 44,
                            "speedKmh": 120 + index,
                            "timestamp": (1_700_000_000 + index) * 1000,
                            "carPhysics": {"carState": {"fuel": 30.0 - index * 0.1}},
                        },
                    }
                )
            for index in range(5):
                rows.append(
                    {
                        "type": "player",
                        "track": "ks_monza",
                        "sample": {
                            "lap_number": 3,
                            "sessionTime": 145.0 + index,
                            "lapProgress": index / 100,
                            "speedKmh": 90 + index,
                            "timestamp": (1_700_000_045 + index) * 1000,
                        },
                    }
                )
            (session / "player.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            repository = SessionRepository(root)
            summary = repository.session_summary(session.name)
            lap = repository.lap_detail(session.name, 2)

            self.assertTrue(summary["indexed"])
            self.assertEqual(summary["sampleCount"], 50)
            self.assertEqual(summary["completedLapCount"], 1)
            self.assertEqual(summary["validLapCount"], 1)
            self.assertEqual(summary["bestLapTime"], 44.0)
            self.assertEqual(summary["sampleRateHz"], 60.0)
            self.assertEqual(len(lap["samples"]), 45)
            self.assertFalse(lap["truncated"])
            self.assertEqual(lap["samples"][0]["carPhysics"]["carState"]["fuel"], 30.0)
            self.assertTrue((session / "session-index.json").exists())

            reduced_lap = repository.lap_detail(session.name, 2, max_samples=10)
            self.assertTrue(reduced_lap["truncated"])
            self.assertLessEqual(reduced_lap["returnedSampleCount"], 11)
            self.assertEqual(reduced_lap["totalSampleCount"], 45)

    def test_list_skips_large_unindexed_files_until_session_is_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "large_session"
            session.mkdir()
            (session / "metadata.json").write_text(
                json.dumps({"sessionId": session.name, "track": "spa"}),
                encoding="utf-8",
            )
            row = {
                "type": "player",
                "sample": {"lap_number": 1, "timestamp": 1.0, "speedKmh": 100.0},
            }
            (session / "player.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

            repository = SessionRepository(root)
            with patch("core.recording.session_repository.MAX_EAGER_INDEX_BYTES", 1):
                listed = repository.list_sessions()
                opened = repository.session_summary(session.name)

            self.assertFalse(listed[0]["indexed"])
            self.assertEqual(listed[0]["sampleCount"], 0)
            self.assertTrue(opened["indexed"])
            self.assertEqual(opened["sampleCount"], 1)

    def test_incrementally_indexes_appended_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "incremental_session"
            session.mkdir()
            player_path = session / "player.jsonl"

            def row(index):
                return json.dumps(
                    {
                        "type": "player",
                        "track": "ks_monza",
                        "sample": {
                            "lap_number": 1,
                            "sessionTime": index,
                            "lapProgress": index / 49,
                            "speedKmh": 100 + index,
                            "timestamp": index,
                        },
                    }
                )

            player_path.write_text("\n".join(row(index) for index in range(20)) + "\n", encoding="utf-8")
            repository = SessionRepository(root)
            first = repository.session_summary(session.name)

            with player_path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(row(index) for index in range(20, 50)) + "\n")
            second = repository.session_summary(session.name)

            self.assertEqual(first["sampleCount"], 20)
            self.assertEqual(second["sampleCount"], 50)
            self.assertEqual(second["laps"][0]["sampleCount"], 50)

    def test_ignores_assetto_lap_counter_lag_frame_at_finish_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "assetto_finish_line_lag"
            session.mkdir()
            rows = []
            for index in range(60):
                elapsed = index * (86.868 / 59)
                rows.append(
                    {
                        "type": "player",
                        "sample": {
                            "lap_number": 2,
                            "lap_time": elapsed,
                            "sessionTime": elapsed,
                            "p": index / 59,
                            "timestamp": 1_700_000_000_000 + index * 16,
                        },
                    }
                )
            rows.append(
                {
                    "type": "player",
                    "sample": {
                        "lap_number": 2,
                        "lap_time": 0.006,
                        "sessionTime": 0.006,
                        "p": 0.000448,
                        "timestamp": 1_700_000_000_960,
                    },
                }
            )
            rows.append(
                {
                    "type": "player",
                    "sample": {
                        "lap_number": 3,
                        "lap_time": 0.024,
                        "sessionTime": 0.024,
                        "p": 0.0008,
                        "timestamp": 1_700_000_000_976,
                    },
                }
            )
            (session / "player.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            repository = SessionRepository(root)
            summary = repository.session_summary(session.name)
            lap = repository.lap_detail(session.name, 2)

            completed = summary["laps"][0]
            self.assertEqual("VALID", completed["validationStatus"])
            self.assertEqual(60, completed["sampleCount"])
            self.assertEqual(0, completed["timestampInversions"])
            self.assertEqual(60, lap["totalSampleCount"])
            self.assertEqual(1.0, lap["samples"][-1]["p"])

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            repository = SessionRepository(Path(tmp))
            with self.assertRaises(ValueError):
                repository.session_summary("../outside")


if __name__ == "__main__":
    unittest.main()
