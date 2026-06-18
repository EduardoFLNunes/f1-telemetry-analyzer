import threading
import time
from collections import deque
from typing import Deque, Dict, Optional


class RateCounter:
    def __init__(self, window_seconds: float = 5.0, max_window_seconds: Optional[float] = None):
        self.window_seconds = max(float(window_seconds), 1.0)
        self.max_window_seconds = max(float(max_window_seconds or window_seconds), self.window_seconds)
        self._timestamps: Deque[float] = deque()
        self._total = 0
        self._lock = threading.Lock()

    def mark(self, count: int = 1, now: Optional[float] = None):
        timestamp = time.monotonic() if now is None else float(now)
        amount = max(int(count), 0)
        if amount <= 0:
            return
        with self._lock:
            for _ in range(amount):
                self._timestamps.append(timestamp)
            self._total += amount
            self._prune(timestamp, self.max_window_seconds)

    def rate(self, now: Optional[float] = None, window_seconds: Optional[float] = None) -> float:
        timestamp = time.monotonic() if now is None else float(now)
        window = max(float(window_seconds or self.window_seconds), 1.0)
        with self._lock:
            self._prune(timestamp, self.max_window_seconds)
            cutoff = timestamp - window
            return sum(1 for item in self._timestamps if item >= cutoff) / window

    def total(self) -> int:
        with self._lock:
            return self._total

    def snapshot(self, now: Optional[float] = None) -> Dict[str, float]:
        timestamp = time.monotonic() if now is None else float(now)
        return {
            "5s": round(self.rate(timestamp, 5.0), 2),
            "30s": round(self.rate(timestamp, 30.0), 2),
            "total": self.total(),
        }

    def _prune(self, now: float, window_seconds: float):
        cutoff = now - window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()


class RollingAverage:
    def __init__(self, max_samples: int = 240):
        self._values: Deque[float] = deque(maxlen=max(int(max_samples), 1))
        self._lock = threading.Lock()

    def add(self, value: float):
        if value < 0:
            return
        with self._lock:
            self._values.append(float(value))

    def average(self) -> float:
        with self._lock:
            if not self._values:
                return 0.0
            return sum(self._values) / len(self._values)

    def latest(self) -> float:
        with self._lock:
            return self._values[-1] if self._values else 0.0


class PerformanceMetrics:
    def __init__(self):
        self._read_attempts = RateCounter(max_window_seconds=30.0)
        self._raw_reads = RateCounter(max_window_seconds=30.0)
        self._accepted_samples = RateCounter(max_window_seconds=30.0)
        self._invalid_samples = RateCounter(max_window_seconds=30.0)
        self._stale_samples = RateCounter(max_window_seconds=30.0)
        self._player_samples = RateCounter(max_window_seconds=30.0)
        self._opponent_snapshots = RateCounter(max_window_seconds=30.0)
        self._persisted_player_samples = RateCounter(max_window_seconds=30.0)
        self._websocket_messages = RateCounter(max_window_seconds=30.0)
        self._websocket_telemetry_messages = RateCounter(max_window_seconds=30.0)
        self._websocket_frames_coalesced = RateCounter(max_window_seconds=30.0)
        self._frame_processing_seconds = RollingAverage()
        self._read_seconds = RollingAverage()
        self._validation_seconds = RollingAverage()
        self._disk_write_seconds = RollingAverage()
        self._websocket_send_seconds = RollingAverage()

    def reset(self):
        self.__init__()

    def mark_read_attempt(self, read_seconds: Optional[float] = None, now: Optional[float] = None):
        self._read_attempts.mark(now=now)
        if read_seconds is not None:
            self._read_seconds.add(read_seconds)

    def mark_raw_read(self, now: Optional[float] = None):
        self._raw_reads.mark(now=now)

    def mark_sample_validation(
        self,
        status: Optional[str],
        validation_seconds: Optional[float] = None,
        now: Optional[float] = None,
    ):
        normalized = (status or "").upper()
        if normalized == "INVALID":
            self._invalid_samples.mark(now=now)
        else:
            self._accepted_samples.mark(now=now)
        if validation_seconds is not None:
            self._validation_seconds.add(validation_seconds)

    def mark_stale_sample(self, now: Optional[float] = None):
        self._stale_samples.mark(now=now)

    def mark_player_frame(self, processing_seconds: Optional[float] = None, now: Optional[float] = None):
        self._player_samples.mark(now=now)
        if processing_seconds is not None:
            self._frame_processing_seconds.add(processing_seconds)

    def mark_opponents_snapshot(self):
        self._opponent_snapshots.mark()

    def mark_persisted_samples(self, stream: str, count: int = 1, now: Optional[float] = None):
        if stream == "player":
            self._persisted_player_samples.mark(count=count, now=now)

    def mark_websocket_message(self, count: int = 1, message_type: Optional[str] = None, now: Optional[float] = None):
        self._websocket_messages.mark(count=count, now=now)
        if message_type == "telemetry":
            self._websocket_telemetry_messages.mark(count=count, now=now)

    def mark_websocket_frame_coalesced(self, now: Optional[float] = None):
        self._websocket_frames_coalesced.mark(now=now)

    def record_disk_write(self, seconds: float):
        self._disk_write_seconds.add(seconds)

    def record_websocket_send(self, seconds: float):
        self._websocket_send_seconds.add(seconds)

    def snapshot(self) -> Dict[str, float]:
        return {
            "playerSamplesPerSecond": round(self._player_samples.rate(), 2),
            "opponentSnapshotsPerSecond": round(self._opponent_snapshots.rate(), 2),
            "websocketMessagesPerSecond": round(self._websocket_messages.rate(), 2),
            "websocketFramesCoalescedPerSecond": round(self._websocket_frames_coalesced.rate(), 2),
            "averageFrameProcessingMs": round(self._frame_processing_seconds.average() * 1000.0, 3),
            "averageDiskWriteMs": round(self._disk_write_seconds.average() * 1000.0, 3),
            "runtimeSampling": self.runtime_snapshot(),
        }

    def runtime_snapshot(
        self,
        *,
        target_hz: float = 60.0,
        source: Optional[str] = None,
        player_status: Optional[str] = None,
        last_sample_age_ms: Optional[float] = None,
        recording_queue_depth: Optional[int] = None,
        websocket_queue_depth: Optional[int] = None,
        now: Optional[float] = None,
    ) -> Dict[str, object]:
        timestamp = time.monotonic() if now is None else float(now)
        windows = {
            "readAttempts": self._read_attempts.snapshot(timestamp),
            "rawReads": self._raw_reads.snapshot(timestamp),
            "acceptedSamples": self._accepted_samples.snapshot(timestamp),
            "invalidSamples": self._invalid_samples.snapshot(timestamp),
            "staleSamples": self._stale_samples.snapshot(timestamp),
            "persistedSamples": self._persisted_player_samples.snapshot(timestamp),
            "websocketTelemetry": self._websocket_telemetry_messages.snapshot(timestamp),
            "websocketMessages": self._websocket_messages.snapshot(timestamp),
            "websocketCoalesced": self._websocket_frames_coalesced.snapshot(timestamp),
        }
        raw_hz = windows["rawReads"]["5s"]
        accepted_hz = windows["acceptedSamples"]["5s"]
        persisted_hz = windows["persistedSamples"]["5s"]
        websocket_hz = windows["websocketTelemetry"]["5s"]
        status, bottleneck = self._diagnose(
            target_hz=float(target_hz),
            source=source,
            player_status=player_status,
            raw_hz=float(raw_hz),
            accepted_hz=float(accepted_hz),
            persisted_hz=float(persisted_hz),
            websocket_hz=float(websocket_hz),
            recording_queue_depth=recording_queue_depth,
        )
        return {
            "targetHz": float(target_hz),
            "source": source,
            "playerStatus": player_status,
            "status": status,
            "bottleneck": bottleneck,
            "rawReadHz": raw_hz,
            "readAttemptHz": windows["readAttempts"]["5s"],
            "acceptedSampleHz": accepted_hz,
            "persistedSampleHz": persisted_hz,
            "websocketEmitHz": websocket_hz,
            "frontendReceiveHz": None,
            "droppedSamples": self._dropped_estimate(float(target_hz), float(accepted_hz)),
            "staleSamples": windows["staleSamples"]["total"],
            "invalidSamples": windows["invalidSamples"]["total"],
            "readLoopDurationMs": round(self._frame_processing_seconds.average() * 1000.0, 3),
            "readDurationMs": round(self._read_seconds.average() * 1000.0, 3),
            "validationDurationMs": round(self._validation_seconds.average() * 1000.0, 3),
            "persistenceDurationMs": round(self._disk_write_seconds.average() * 1000.0, 3),
            "websocketDurationMs": round(self._websocket_send_seconds.average() * 1000.0, 3),
            "websocketQueueDepth": websocket_queue_depth,
            "recordingQueueDepth": recording_queue_depth,
            "lastSampleAgeMs": last_sample_age_ms,
            "windows": windows,
        }

    @staticmethod
    def _dropped_estimate(target_hz: float, accepted_hz: float) -> int:
        if accepted_hz <= 0 or target_hz <= 0:
            return 0
        return max(0, int(round((target_hz - accepted_hz) * 5.0)))

    @staticmethod
    def _diagnose(
        *,
        target_hz: float,
        source: Optional[str],
        player_status: Optional[str],
        raw_hz: float,
        accepted_hz: float,
        persisted_hz: float,
        websocket_hz: float,
        recording_queue_depth: Optional[int],
    ) -> tuple[str, str]:
        if player_status in {"waiting", "stale"}:
            return "WAITING", "source_waiting"
        if source == "mock" and raw_hz <= 0:
            return "WAITING", "mock_source_no_live_samples"
        if raw_hz < target_hz * 0.5:
            return "ERROR", "reader_or_source_limited"
        if raw_hz < target_hz * 0.83:
            return "WARNING", "reader_loop_below_target"
        if accepted_hz < raw_hz * 0.8:
            return "WARNING", "validation_filtering_samples"
        if recording_queue_depth and recording_queue_depth > 1000:
            return "WARNING", "persistence_queue_backpressure"
        if persisted_hz > 0 and persisted_hz < accepted_hz * 0.7:
            return "WARNING", "persistence_below_collection_rate"
        if websocket_hz > 0 and websocket_hz < accepted_hz * 0.5:
            return "OK", "websocket_or_frontend_throttled_not_collection"
        if accepted_hz >= target_hz * 0.83:
            return "OK", "collection_on_target"
        return "WARNING", "sampling_below_target"


performance_metrics = PerformanceMetrics()
