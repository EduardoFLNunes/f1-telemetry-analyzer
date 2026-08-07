import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.recording.recording_models import RecordingConfig  # noqa: E402
from core.recording.recording_runtime import CaptureGateClosed, RecordingRuntime  # noqa: E402
from core.telemetry_events import TelemetryEventBus  # noqa: E402


def player_frame(lap: int = 1, session_time: float = 10.0):
    return {
        "lap_number": lap,
        "sessionTime": session_time,
        "trackName": "vhe_interlagos",
        "speed": 55.0,
        "throttle": 1.0,
        "brake": 0.0,
        "worldPositionX": 1.0,
        "worldPositionY": 0.0,
        "worldPositionZ": 2.0,
        "timestamp": session_time,
    }


class RecordingCaptureGateTests(unittest.TestCase):
    """The recorder must only ever create a session while Assetto Corsa is capturable."""

    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.output_root = Path(self._tempdir.name)
        self.gate = {"allowed": False, "reason": "waiting_for_assetto_corsa_process"}

    def build_runtime(self, auto_start: bool = True) -> RecordingRuntime:
        config = RecordingConfig(
            output_root=self.output_root,
            enabled=True,
            auto_start=auto_start,
            player_record_hz=60.0,
            source_sample_hz=60.0,
        )
        runtime = RecordingRuntime(
            config=config,
            track_provider=lambda: "vhe_interlagos",
            metadata_provider=lambda: {"source": "assetto_corsa"},
            bus=TelemetryEventBus(),
            capture_gate=lambda: self.gate,
        )
        self.addCleanup(runtime.stop)
        return runtime

    def session_dirs(self):
        return sorted(path.name for path in self.output_root.iterdir() if path.is_dir())

    def test_start_does_not_open_a_session_while_assetto_is_closed(self):
        runtime = self.build_runtime()
        runtime.start()

        self.assertFalse(runtime.recorder.recording)
        self.assertEqual(self.session_dirs(), [], "no recording directory may be created at boot")

    def test_player_frames_are_ignored_while_gate_is_closed(self):
        runtime = self.build_runtime()
        runtime.start()

        asyncio.run(runtime.on_player_frame(player_frame()))

        self.assertFalse(runtime.recorder.recording)
        self.assertEqual(self.session_dirs(), [])

    def test_session_starts_on_first_frame_once_gate_opens(self):
        runtime = self.build_runtime()
        runtime.start()

        asyncio.run(runtime.on_player_frame(player_frame()))
        self.assertEqual(self.session_dirs(), [])

        self.gate = {"allowed": True, "reason": None}
        asyncio.run(runtime.on_player_frame(player_frame(lap=1, session_time=11.0)))

        self.assertTrue(runtime.recorder.recording)
        self.assertEqual(len(self.session_dirs()), 1)

    def test_session_stops_and_rearms_when_assetto_closes(self):
        runtime = self.build_runtime()
        runtime.start()
        self.gate = {"allowed": True, "reason": None}
        asyncio.run(runtime.on_player_frame(player_frame()))
        self.assertTrue(runtime.recorder.recording)
        first_session = self.session_dirs()

        # Assetto Corsa closed mid-session.
        self.gate = {"allowed": False, "reason": "waiting_for_assetto_corsa_process"}
        asyncio.run(runtime.on_player_frame(player_frame(lap=2, session_time=20.0)))
        self.assertFalse(runtime.recorder.recording)

        # Reopening the game starts a fresh session rather than resuming the stale one.
        self.gate = {"allowed": True, "reason": None}
        asyncio.run(runtime.on_player_frame(player_frame(lap=1, session_time=30.0)))
        self.assertTrue(runtime.recorder.recording)
        self.assertEqual(len(self.session_dirs()), len(first_session) + 1)

    def test_manual_start_is_refused_while_gate_is_closed(self):
        runtime = self.build_runtime(auto_start=False)
        runtime.start()

        with self.assertRaises(CaptureGateClosed) as ctx:
            runtime.start_recording()

        self.assertEqual(ctx.exception.reason, "waiting_for_assetto_corsa_process")
        self.assertFalse(runtime.recorder.recording)
        self.assertEqual(self.session_dirs(), [])

    def test_opponent_frames_alone_never_open_a_session(self):
        runtime = self.build_runtime()
        runtime.start()
        self.gate = {"allowed": True, "reason": None}

        asyncio.run(runtime.on_opponents_frame({"track": "vhe_interlagos", "opponents": []}))

        self.assertFalse(runtime.recorder.recording)
        self.assertEqual(self.session_dirs(), [])

    def test_gate_failure_is_treated_as_closed(self):
        runtime = self.build_runtime()

        def broken_gate():
            raise RuntimeError("gate probe exploded")

        runtime.capture_gate = broken_gate
        runtime.start()
        asyncio.run(runtime.on_player_frame(player_frame()))

        self.assertFalse(runtime.recorder.recording)
        self.assertEqual(runtime.capture_gate_status()["reason"], "capture_gate_error")

    def test_absent_gate_keeps_legacy_always_allowed_behaviour(self):
        config = RecordingConfig(output_root=self.output_root, enabled=True, auto_start=True)
        runtime = RecordingRuntime(
            config=config,
            track_provider=lambda: "vhe_interlagos",
            bus=TelemetryEventBus(),
        )
        self.addCleanup(runtime.stop)
        runtime.start()
        asyncio.run(runtime.on_player_frame(player_frame()))

        self.assertTrue(runtime.recorder.recording)


if __name__ == "__main__":
    unittest.main()
