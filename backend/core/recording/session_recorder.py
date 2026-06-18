import json
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..performance_metrics import performance_metrics
from .recording_models import RecordingConfig, RecordingStatus, build_session_id


logger = logging.getLogger(__name__)


class SessionRecorder:
    def __init__(self, config: RecordingConfig):
        self.config = config
        self.session_id: Optional[str] = None
        self.directory: Optional[Path] = None
        self.recording = False

        self._queue: queue.Queue = queue.Queue(maxsize=max(int(config.max_queue_size), 1))
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._files: Dict[str, Any] = {}

        self._player_samples_written = 0
        self._opponent_snapshots_written = 0
        self._events_written = 0
        self._dropped_frames = 0
        self._last_player_recorded_at = 0.0
        self._last_opponents_recorded_at = 0.0
        self._last_queue_warning_at = 0.0

    def start(self, track: Optional[str] = None, metadata: Optional[Mapping[str, Any]] = None) -> RecordingStatus:
        if not self.config.enabled:
            logger.info("Session recording is disabled")
            return self.status()

        with self._lock:
            if self.recording:
                return self.status()

            base_session_id = build_session_id(track)
            self.session_id = base_session_id
            self.directory = self.config.output_root / self.session_id
            suffix = 2
            while self.directory.exists():
                self.session_id = f"{base_session_id}_{suffix:02d}"
                self.directory = self.config.output_root / self.session_id
                suffix += 1
            self.directory.mkdir(parents=True, exist_ok=True)

            self._player_samples_written = 0
            self._opponent_snapshots_written = 0
            self._events_written = 0
            self._dropped_frames = 0
            self._last_player_recorded_at = 0.0
            self._last_opponents_recorded_at = 0.0
            self._last_queue_warning_at = 0.0
            self._drain_queue()

            self._write_metadata(track=track, metadata=metadata)
            self._stop_event.clear()
            self.recording = True
            self._thread = threading.Thread(target=self._writer_loop, name="session-recorder", daemon=True)
            self._thread.start()
            logger.info("Session recording started: %s", self.directory)
            return self.status()

    def stop(self) -> RecordingStatus:
        with self._lock:
            if not self.recording:
                return self.status()
            self.recording = False
            self._stop_event.set()
            thread = self._thread

        if thread:
            thread.join(timeout=5.0)

        with self._lock:
            self._thread = None
            self._close_files()
            self._finalize_metadata()
            logger.info("Session recording stopped: %s", self.directory)
            return self.status()

    def enqueue_player(self, frame: Mapping[str, Any], track: Optional[str] = None) -> bool:
        if not self._should_record("player"):
            return False

        payload = {
            "type": "player",
            "timestamp": self._timestamp_from(frame),
            "track": track or self._track_from(frame),
            "sessionTime": self._session_time_from(frame),
            "sample": dict(frame),
        }
        return self._enqueue("player", payload)

    def enqueue_opponents(self, snapshot: Mapping[str, Any], track: Optional[str] = None) -> bool:
        if not self._should_record("opponents"):
            return False

        cars = snapshot.get("cars")
        if cars is None:
            cars = snapshot.get("opponents", [])
        count = snapshot.get("count")
        if count is None and isinstance(cars, list):
            count = len(cars)

        payload = {
            "type": "opponents",
            "timestamp": self._timestamp_from(snapshot),
            "track": track or self._track_from(snapshot),
            "sessionTime": self._session_time_from(snapshot),
            "count": count,
            "cars": cars if isinstance(cars, list) else [],
        }
        return self._enqueue("opponents", payload)

    def enqueue_event(self, event: Mapping[str, Any], event_type: str = "event", track: Optional[str] = None) -> bool:
        if not self.recording:
            return False
        payload = {
            "type": event_type,
            "timestamp": self._timestamp_from(event),
            "track": track or self._track_from(event),
            "event": dict(event),
        }
        return self._enqueue("events", payload)

    def status(self) -> RecordingStatus:
        return RecordingStatus(
            enabled=self.config.enabled,
            recording=self.recording,
            sessionId=self.session_id,
            directory=str(self.directory) if self.directory else None,
            playerSamplesWritten=self._player_samples_written,
            opponentSnapshotsWritten=self._opponent_snapshots_written,
            eventsWritten=self._events_written,
            queueSize=self._queue.qsize(),
            droppedFrames=self._dropped_frames,
        )

    def _should_record(self, stream: str) -> bool:
        if not self.recording:
            return False

        now = time.monotonic()
        if stream == "player":
            hz = max(float(self.config.player_record_hz), 0.0)
            if hz <= 0:
                return False
            if now - self._last_player_recorded_at < 1.0 / hz:
                return False
            self._last_player_recorded_at = now
            return True

        if stream == "opponents":
            hz = max(float(self.config.opponents_record_hz), 0.0)
            if hz <= 0:
                return False
            if now - self._last_opponents_recorded_at < 1.0 / hz:
                return False
            self._last_opponents_recorded_at = now
            return True

        return True

    def _enqueue(self, stream: str, payload: Dict[str, Any]) -> bool:
        try:
            self._queue.put_nowait((stream, payload))
            self._warn_if_queue_is_high(stream)
            return True
        except queue.Full:
            self._dropped_frames += 1
            if stream == "player":
                performance_metrics.mark_dropped_samples()
            logger.warning("Session recorder queue full, dropped %s frame", stream)
            return False

    def _warn_if_queue_is_high(self, stream: str):
        max_size = max(int(self.config.max_queue_size), 1)
        queue_size = self._queue.qsize()
        if queue_size < max_size * 0.7:
            return

        now = time.monotonic()
        if now - self._last_queue_warning_at < 5.0:
            return

        self._last_queue_warning_at = now
        logger.warning(
            "Session recorder queue high: stream=%s queue=%s/%s dropped=%s",
            stream,
            queue_size,
            max_size,
            self._dropped_frames,
        )

    def _writer_loop(self):
        batch = []
        last_flush = time.monotonic()

        while not self._stop_event.is_set() or not self._queue.empty():
            timeout = max(0.05, self.config.flush_interval_seconds)
            try:
                item = self._queue.get(timeout=timeout)
                batch.append(item)
            except queue.Empty:
                pass

            now = time.monotonic()
            if batch and (len(batch) >= self.config.batch_size or now - last_flush >= self.config.flush_interval_seconds):
                self._write_batch(batch)
                batch.clear()
                last_flush = now

        if batch:
            self._write_batch(batch)
        self._flush_files()

    def _write_batch(self, batch):
        started = time.perf_counter()
        written_by_stream = {"player": 0, "opponents": 0, "events": 0}
        for stream, payload in batch:
            try:
                handle = self._file_for_stream(stream)
                handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=self._json_default) + "\n")
                if stream == "player":
                    self._player_samples_written += 1
                elif stream == "opponents":
                    self._opponent_snapshots_written += 1
                elif stream == "events":
                    self._events_written += 1
                written_by_stream[stream] = written_by_stream.get(stream, 0) + 1
            except Exception as exc:
                self._dropped_frames += 1
                if stream == "player":
                    performance_metrics.mark_dropped_samples()
                logger.warning("Session recorder write error for %s: %s", stream, exc)
        self._flush_files()
        performance_metrics.record_disk_write(time.perf_counter() - started)
        for stream, count in written_by_stream.items():
            performance_metrics.mark_persisted_samples(stream, count=count)

    def _file_for_stream(self, stream: str):
        if stream not in self._files:
            if not self.directory:
                raise RuntimeError("recording directory is not initialized")
            filename = {
                "player": "player.jsonl",
                "opponents": "opponents.jsonl",
                "events": "events.jsonl",
            }.get(stream, "events.jsonl")
            self._files[stream] = open(self.directory / filename, "a", encoding="utf-8")
        return self._files[stream]

    def _flush_files(self):
        for handle in self._files.values():
            try:
                handle.flush()
            except Exception:
                pass

    def _close_files(self):
        for handle in self._files.values():
            try:
                handle.flush()
                handle.close()
            except Exception:
                pass
        self._files = {}

    def _write_metadata(self, track: Optional[str], metadata: Optional[Mapping[str, Any]]):
        if not self.directory:
            return
        payload = {
            "schemaVersion": 2,
            "sessionId": self.session_id,
            "track": track,
            "startedAt": datetime.now().isoformat(),
            "playerRecordHz": self.config.player_record_hz,
            "opponentsRecordHz": self.config.opponents_record_hz,
            "metadata": dict(metadata or {}),
        }
        with open(self.directory / "metadata.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=self._json_default)

    def _finalize_metadata(self):
        if not self.directory:
            return
        path = self.directory / "metadata.json"
        try:
            metadata = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            metadata.update(
                {
                    "endedAt": datetime.now().isoformat(),
                    "playerSamplesWritten": self._player_samples_written,
                    "opponentSnapshotsWritten": self._opponent_snapshots_written,
                    "eventsWritten": self._events_written,
                    "droppedFrames": self._dropped_frames,
                }
            )
            path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2, default=self._json_default),
                encoding="utf-8",
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Session metadata finalization failed: %s", exc)

    def _drain_queue(self):
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            return

    @staticmethod
    def _timestamp_from(data: Mapping[str, Any]) -> Optional[float]:
        for key in ("timestamp", "timestamp_ms", "time"):
            value = data.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return time.time()

    @staticmethod
    def _session_time_from(data: Mapping[str, Any]) -> Optional[float]:
        for key in ("sessionTime", "session_time"):
            value = data.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @staticmethod
    def _track_from(data: Mapping[str, Any]) -> Optional[str]:
        for key in ("track", "trackName", "track_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _json_default(value: Any):
        item = getattr(value, "item", None)
        if callable(item):
            try:
                return item()
            except Exception:
                pass
        if isinstance(value, Path):
            return str(value)
        return str(value)
