import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from ..telemetry_events import COACHING_EVENT, LAP_FINALIZED, OPPONENTS_FRAME, PROCESSED_FRAME, SECTOR_SPLIT, event_bus
from .recording_models import RecordingConfig
from .session_recorder import SessionRecorder


logger = logging.getLogger(__name__)


class RecordingRuntime:
    def __init__(
        self,
        config: RecordingConfig,
        track_provider: Optional[Callable[[], Optional[str]]] = None,
        metadata_provider: Optional[Callable[[], Mapping[str, Any]]] = None,
        bus=event_bus,
    ):
        self.config = config
        self.track_provider = track_provider or (lambda: None)
        self.metadata_provider = metadata_provider or (lambda: {})
        self.event_bus = bus
        self.recorder = SessionRecorder(config)
        self._subscribed = False

    def start(self):
        if not self._subscribed:
            self.event_bus.subscribe(PROCESSED_FRAME, self.on_player_frame)
            self.event_bus.subscribe(OPPONENTS_FRAME, self.on_opponents_frame)
            self.event_bus.subscribe(SECTOR_SPLIT, self.on_event)
            self.event_bus.subscribe(LAP_FINALIZED, self.on_event)
            self.event_bus.subscribe(COACHING_EVENT, self.on_event)
            self._subscribed = True

        if self.config.auto_start:
            self.start_recording()

    def stop(self):
        if self._subscribed:
            self.event_bus.unsubscribe(PROCESSED_FRAME, self.on_player_frame)
            self.event_bus.unsubscribe(OPPONENTS_FRAME, self.on_opponents_frame)
            self.event_bus.unsubscribe(SECTOR_SPLIT, self.on_event)
            self.event_bus.unsubscribe(LAP_FINALIZED, self.on_event)
            self.event_bus.unsubscribe(COACHING_EVENT, self.on_event)
            self._subscribed = False
        self.recorder.stop()

    def start_recording(self):
        track = self._safe_track()
        metadata = self._safe_metadata()
        return self.recorder.start(track=track, metadata=metadata)

    def stop_recording(self):
        return self.recorder.stop()

    def status(self):
        return self.recorder.status()

    async def on_player_frame(self, frame: Mapping[str, Any]):
        try:
            self.recorder.enqueue_player(frame, track=self._safe_track())
        except Exception as exc:
            logger.warning("Recording player frame enqueue failed: %s", exc)

    async def on_opponents_frame(self, snapshot: Mapping[str, Any]):
        try:
            self.recorder.enqueue_opponents(snapshot, track=snapshot.get("track") or self._safe_track())
        except Exception as exc:
            logger.warning("Recording opponents frame enqueue failed: %s", exc)

    async def on_event(self, payload: Mapping[str, Any]):
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
        player_record_hz=env_float("TELEMETRY_RECORDING_PLAYER_HZ", 20.0),
        opponents_record_hz=env_float("TELEMETRY_RECORDING_OPPONENTS_HZ", 20.0),
        batch_size=env_int("TELEMETRY_RECORDING_BATCH_SIZE", 128),
        flush_interval_seconds=env_float("TELEMETRY_RECORDING_FLUSH_SECONDS", 1.0),
        max_queue_size=env_int("TELEMETRY_RECORDING_QUEUE_SIZE", 20000),
    )
