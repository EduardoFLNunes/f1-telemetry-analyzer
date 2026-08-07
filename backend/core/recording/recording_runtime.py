import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from ..telemetry_events import COACHING_EVENT, LAP_FINALIZED, OPPONENTS_FRAME, PROCESSED_FRAME, SECTOR_SPLIT, event_bus
from .recording_models import RecordingConfig
from .session_recorder import SessionRecorder


logger = logging.getLogger(__name__)


class CaptureGateClosed(RuntimeError):
    """Raised when recording is requested while telemetry capture is not allowed."""

    def __init__(self, reason: Optional[str] = None):
        self.reason = reason or "capture_gate_closed"
        super().__init__(self.reason)


class RecordingRuntime:
    def __init__(
        self,
        config: RecordingConfig,
        track_provider: Optional[Callable[[], Optional[str]]] = None,
        metadata_provider: Optional[Callable[[], Mapping[str, Any]]] = None,
        bus=event_bus,
        capture_gate: Optional[Callable[[], Mapping[str, Any]]] = None,
    ):
        self.config = config
        self.track_provider = track_provider or (lambda: None)
        self.metadata_provider = metadata_provider or (lambda: {})
        self.event_bus = bus
        # Returns a mapping shaped like shared_memory_gate_status(): {"allowed": bool,
        # "reason": str|None}. Absent gate means "always allowed" so tests and any
        # non-Assetto embedding keep the previous behaviour.
        self.capture_gate = capture_gate
        self.recorder = SessionRecorder(config)
        self._subscribed = False
        self._auto_start_pending = False
        self._recording_track: Optional[str] = None
        self._last_lap: Optional[int] = None
        self._last_session_time: Optional[float] = None
        self._last_gate_reason: Optional[str] = None
        self._last_gate_log_reason: Optional[str] = None

    def capture_gate_status(self) -> Mapping[str, Any]:
        """Current capture-gate state, safe to call from request handlers."""
        if self.capture_gate is None:
            return {"allowed": True, "reason": None}
        try:
            status = dict(self.capture_gate())
        except Exception as exc:  # a broken gate must not take the backend down
            logger.warning("Capture gate check failed; treating as closed: %s", exc)
            return {"allowed": False, "reason": "capture_gate_error"}
        status.setdefault("allowed", False)
        status.setdefault("reason", None)
        return status

    def _capture_allowed(self) -> bool:
        status = self.capture_gate_status()
        allowed = bool(status.get("allowed"))
        reason = status.get("reason")
        self._last_gate_reason = None if allowed else (reason or "capture_gate_closed")
        if not allowed and reason != self._last_gate_log_reason:
            logger.info("Recording is waiting for telemetry capture gate: %s", reason)
            self._last_gate_log_reason = reason
        if allowed:
            self._last_gate_log_reason = None
        return allowed

    def start(self):
        if not self._subscribed:
            self.event_bus.subscribe(PROCESSED_FRAME, self.on_player_frame)
            self.event_bus.subscribe(OPPONENTS_FRAME, self.on_opponents_frame)
            self.event_bus.subscribe(SECTOR_SPLIT, self.on_event)
            self.event_bus.subscribe(LAP_FINALIZED, self.on_event)
            self.event_bus.subscribe(COACHING_EVENT, self.on_event)
            self._subscribed = True

        # Never open a session at boot: a session is only created once a real player
        # frame arrives with the capture gate open, so closing Assetto Corsa (or never
        # opening it) can no longer produce empty metadata-only recordings.
        if self.config.auto_start:
            self._auto_start_pending = True

    def stop(self):
        if self._subscribed:
            self.event_bus.unsubscribe(PROCESSED_FRAME, self.on_player_frame)
            self.event_bus.unsubscribe(OPPONENTS_FRAME, self.on_opponents_frame)
            self.event_bus.unsubscribe(SECTOR_SPLIT, self.on_event)
            self.event_bus.unsubscribe(LAP_FINALIZED, self.on_event)
            self.event_bus.unsubscribe(COACHING_EVENT, self.on_event)
            self._subscribed = False
        self.recorder.stop()

    def start_recording(self, track: Optional[str] = None, *, force: bool = False):
        if not force and not self._capture_allowed():
            raise CaptureGateClosed(self._last_gate_reason)
        track = track or self._safe_track()
        metadata = self._safe_metadata()
        status = self.recorder.start(track=track, metadata=metadata)
        self._recording_track = track
        self._auto_start_pending = False
        self._last_lap = None
        self._last_session_time = None
        return status

    def stop_recording(self):
        status = self.recorder.stop()
        self._recording_track = None
        self._last_lap = None
        self._last_session_time = None
        return status

    def status(self):
        return self.recorder.status()

    async def on_player_frame(self, frame: Mapping[str, Any]):
        try:
            if not self._capture_allowed():
                # Assetto Corsa closed (or shared memory not ready): finalize any open
                # session and re-arm auto-start so the next real session starts clean.
                if self.recorder.recording:
                    logger.info(
                        "Stopping recording because telemetry capture gate closed: %s",
                        self._last_gate_reason,
                    )
                    self.stop_recording()
                    self._auto_start_pending = bool(self.config.auto_start)
                return

            track = self._safe_track() or self._track_from_frame(frame)
            if self._auto_start_pending and not self.recorder.recording:
                self.start_recording(track=track)
            if self.recorder.recording and self._should_rotate(frame, track):
                self.recorder.stop()
                self.recorder.start(track=track, metadata=self._safe_metadata())
                self._recording_track = track
                self._last_lap = None
                self._last_session_time = None

            self.recorder.enqueue_player(frame, track=track)
            self._recording_track = self._recording_track or track
            self._last_lap = self._frame_int(frame, "lap_number", "lap")
            self._last_session_time = self._frame_float(frame, "sessionTime", "session_time")
        except Exception as exc:
            logger.warning("Recording player frame enqueue failed: %s", exc)

    async def on_opponents_frame(self, snapshot: Mapping[str, Any]):
        # Opponents arrive over UDP independently of the player shared memory, so they
        # must never open or feed a session on their own.
        if not self.recorder.recording:
            return
        try:
            self.recorder.enqueue_opponents(snapshot, track=snapshot.get("track") or self._safe_track())
        except Exception as exc:
            logger.warning("Recording opponents frame enqueue failed: %s", exc)

    async def on_event(self, payload: Mapping[str, Any]):
        if not self.recorder.recording:
            return
        try:
            event_type = payload.get("type", "event") if isinstance(payload, Mapping) else "event"
            self.recorder.enqueue_event(payload, event_type=event_type, track=self._safe_track())
        except Exception as exc:
            logger.warning("Recording event enqueue failed: %s", exc)

    def _safe_track(self) -> Optional[str]:
        try:
            return self.track_provider()
        except Exception:
            return None

    def _safe_metadata(self) -> Mapping[str, Any]:
        try:
            return dict(self.metadata_provider())
        except Exception:
            return {}

    def _should_rotate(self, frame: Mapping[str, Any], track: Optional[str]) -> bool:
        if track and self._recording_track and track != self._recording_track:
            return True

        lap = self._frame_int(frame, "lap_number", "lap")
        session_time = self._frame_float(frame, "sessionTime", "session_time")
        return bool(
            lap is not None
            and self._last_lap is not None
            and lap + 1 < self._last_lap
            and session_time is not None
            and self._last_session_time is not None
            and session_time + 5.0 < self._last_session_time
        )

    @staticmethod
    def _track_from_frame(frame: Mapping[str, Any]) -> Optional[str]:
        for key in ("trackName", "track", "track_name"):
            value = frame.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _frame_int(frame: Mapping[str, Any], *keys: str) -> Optional[int]:
        for key in keys:
            try:
                value = frame.get(key)
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _frame_float(frame: Mapping[str, Any], *keys: str) -> Optional[float]:
        for key in keys:
            try:
                value = frame.get(key)
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None


def config_from_env(repo_root: Path) -> RecordingConfig:
    import os

    def env_bool(name: str, default: bool) -> bool:
        value = os.environ.get(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def env_float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    def env_int(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    output_root = Path(os.environ.get("TELEMETRY_RECORDING_DIR", repo_root / "data" / "recordings"))
    return RecordingConfig(
        output_root=output_root,
        enabled=env_bool("TELEMETRY_RECORDING_ENABLED", True),
        auto_start=env_bool("TELEMETRY_RECORDING_AUTO_START", True),
        player_record_hz=env_float("TELEMETRY_RECORDING_PLAYER_HZ", 60.0),
        source_sample_hz=env_float("TELEMETRY_SOURCE_TARGET_HZ", 60.0),
        opponents_record_hz=env_float("TELEMETRY_RECORDING_OPPONENTS_HZ", 20.0),
        batch_size=env_int("TELEMETRY_RECORDING_BATCH_SIZE", 128),
        flush_interval_seconds=env_float("TELEMETRY_RECORDING_FLUSH_SECONDS", 1.0),
        max_queue_size=env_int("TELEMETRY_RECORDING_QUEUE_SIZE", 20000),
    )
