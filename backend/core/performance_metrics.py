import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple


WINDOW_5S = "5s"
WINDOW_30S = "30s"


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


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
            WINDOW_5S: round(self.rate(timestamp, 5.0), 2),
            WINDOW_30S: round(self.rate(timestamp, 30.0), 2),
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
        self._duplicate_samples = RateCounter(max_window_seconds=30.0)
        self._dropped_samples = RateCounter(max_window_seconds=30.0)
        self._player_samples = RateCounter(max_window_seconds=30.0)
        self._opponent_snapshots = RateCounter(max_window_seconds=30.0)
        self._persisted_player_samples = RateCounter(max_window_seconds=30.0)
        self._websocket_messages = RateCounter(max_window_seconds=30.0)
        self._websocket_telemetry_messages = RateCounter(max_window_seconds=30.0)
        self._websocket_send_failures = RateCounter(max_window_seconds=30.0)
        self._websocket_frames_coalesced = RateCounter(max_window_seconds=30.0)
        self._frame_processing_seconds = RollingAverage()
        self._read_loop_interval_seconds = RollingAverage()
        self._read_seconds = RollingAverage()
        self._validation_seconds = RollingAverage()
        self._disk_write_seconds = RollingAverage()
        self._websocket_send_seconds = RollingAverage()
        self._last_loop_started_at: Optional[float] = None
        self._last_sample_identity: Optional[Tuple[Any, ...]] = None
        self._identity_lock = threading.Lock()

    def reset(self):
        self.__init__()

    def mark_read_loop_start(self, now: Optional[float] = None):
        timestamp = time.perf_counter() if now is None else float(now)
        if self._last_loop_started_at is not None:
            self._read_loop_interval_seconds.add(timestamp - self._last_loop_started_at)
        self._last_loop_started_at = timestamp

    def mark_read_attempt(self, read_seconds: Optional[float] = None, now: Optional[float] = None):
        self._read_attempts.mark(now=now)
        if read_seconds is not None:
            self._read_seconds.add(read_seconds)

    def mark_raw_read(self, sample: Optional[Any] = None, now: Optional[float] = None):
        self._raw_reads.mark(now=now)
        if sample is None:
            return

        identity = self._sample_identity(sample)
        if identity is None:
            return

        with self._identity_lock:
            if identity == self._last_sample_identity:
                self._duplicate_samples.mark(now=now)
            self._last_sample_identity = identity

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

    def mark_stale_sample(self, count: int = 1, now: Optional[float] = None):
        self._stale_samples.mark(count=count, now=now)

    def mark_dropped_samples(self, count: int = 1, now: Optional[float] = None):
        self._dropped_samples.mark(count=count, now=now)

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

    def mark_websocket_send_failure(self, count: int = 1, now: Optional[float] = None):
        self._websocket_send_failures.mark(count=count, now=now)

    def mark_websocket_frame_coalesced(self, now: Optional[float] = None):
        self._websocket_frames_coalesced.mark(now=now)

    def record_disk_write(self, seconds: float):
        self._disk_write_seconds.add(seconds)

    def record_websocket_send(self, seconds: float):
        self._websocket_send_seconds.add(seconds)

    def snapshot(self) -> Dict[str, object]:
        runtime_sampling = self.runtime_snapshot()
        return {
            "playerSamplesPerSecond": round(self._player_samples.rate(), 2),
            "opponentSnapshotsPerSecond": round(self._opponent_snapshots.rate(), 2),
            "websocketMessagesPerSecond": round(self._websocket_messages.rate(), 2),
            "websocketFramesCoalescedPerSecond": round(self._websocket_frames_coalesced.rate(), 2),
            "averageFrameProcessingMs": round(self._frame_processing_seconds.average() * 1000.0, 3),
            "averageDiskWriteMs": round(self._disk_write_seconds.average() * 1000.0, 3),
            "runtimeSampling": runtime_sampling,
        }

    def runtime_snapshot(
        self,
        *,
        target_hz: float = 60.0,
        source: Optional[str] = None,
        player_source: Optional[str] = None,
        player_status: Optional[str] = None,
        last_sample_age_ms: Optional[float] = None,
        recording_queue_depth: Optional[int] = None,
        recording_dropped_frames: Optional[int] = None,
        websocket_queue_depth: Optional[int] = None,
        now: Optional[float] = None,
    ) -> Dict[str, object]:
        timestamp = time.monotonic() if now is None else float(now)
        counter_windows = {
            "readAttempts": self._read_attempts.snapshot(timestamp),
            "rawReads": self._raw_reads.snapshot(timestamp),
            "acceptedSamples": self._accepted_samples.snapshot(timestamp),
            "invalidSamples": self._invalid_samples.snapshot(timestamp),
            "staleSamples": self._stale_samples.snapshot(timestamp),
            "duplicateSamples": self._duplicate_samples.snapshot(timestamp),
            "droppedSamples": self._dropped_samples.snapshot(timestamp),
            "persistedSamples": self._persisted_player_samples.snapshot(timestamp),
            "websocketTelemetry": self._websocket_telemetry_messages.snapshot(timestamp),
            "websocketMessages": self._websocket_messages.snapshot(timestamp),
            "websocketSendFailures": self._websocket_send_failures.snapshot(timestamp),
            "websocketCoalesced": self._websocket_frames_coalesced.snapshot(timestamp),
        }
        windows = self._sampling_windows(counter_windows)
        five = windows[WINDOW_5S]
        thirty = windows[WINDOW_30S]
        counters = self._counters(counter_windows, recording_dropped_frames)
        durations = {
            "readLoopAvg": round(self._frame_processing_seconds.average() * 1000.0, 3),
            "readLoopIntervalAvg": round(self._read_loop_interval_seconds.average() * 1000.0, 3),
            "readAvg": round(self._read_seconds.average() * 1000.0, 3),
            "validationAvg": round(self._validation_seconds.average() * 1000.0, 3),
            "persistenceAvg": round(self._disk_write_seconds.average() * 1000.0, 3),
            "websocketEmitAvg": round(self._websocket_send_seconds.average() * 1000.0, 3),
        }
        read_attempt_hz = float(five["readAttemptHz"] or 0.0)
        raw_hz = float(five["rawReadHz"] or 0.0)
        accepted_hz = float(five["acceptedSampleHz"] or 0.0)
        persisted_hz = float(five["persistedSampleHz"] or 0.0)
        websocket_hz = float(five["websocketEmitHz"] or 0.0)
        backpressure_detected = bool(
            (recording_queue_depth or 0) > 1000
            or (websocket_queue_depth or 0) > 2
            or counters["websocketSendFailures"] > 0
        )
        status, reason, source_limited = self._diagnose(
            target_hz=float(target_hz),
            source=source,
            player_source=player_source,
            player_status=player_status,
            read_attempt_hz=read_attempt_hz,
            raw_hz=raw_hz,
            accepted_hz=accepted_hz,
            persisted_hz=persisted_hz,
            websocket_hz=websocket_hz,
            last_sample_age_ms=last_sample_age_ms,
            backpressure_detected=backpressure_detected,
            recording_queue_depth=recording_queue_depth,
        )
        bottleneck = {
            "reason": reason,
            "sourceLimited": source_limited,
            "backpressureDetected": backpressure_detected,
        }
        dropped_estimate = self._dropped_estimate(float(target_hz), accepted_hz)
        counters["droppedSamples"] = max(int(counters["droppedSamples"]), int(dropped_estimate))

        return {
            "targetHz": float(target_hz),
            "source": source,
            "playerSource": player_source,
            "playerStatus": player_status,
            "status": status,
            "bottleneck": reason,
            "bottleneckReason": reason,
            "sourceLimited": source_limited,
            "backpressureDetected": backpressure_detected,
            "rawReadHz": five["rawReadHz"],
            "readAttemptHz": five["readAttemptHz"],
            "acceptedSampleHz": five["acceptedSampleHz"],
            "persistedSampleHz": five["persistedSampleHz"],
            "websocketEmitHz": five["websocketEmitHz"],
            "frontendReceiveHz": None,
            "droppedSamples": counters["droppedSamples"],
            "staleSamples": counters["staleSamples"],
            "duplicateSamples": counters["duplicateSamples"],
            "invalidSamples": counters["invalidSamples"],
            "readLoopIntervalMs": durations["readLoopIntervalAvg"],
            "readLoopDurationMs": durations["readLoopAvg"],
            "readDurationMs": durations["readAvg"],
            "validationDurationMs": durations["validationAvg"],
            "persistenceDurationMs": durations["persistenceAvg"],
            "websocketDurationMs": durations["websocketEmitAvg"],
            "websocketQueueDepth": websocket_queue_depth,
            "recordingQueueDepth": recording_queue_depth,
            "lastSampleAgeMs": last_sample_age_ms,
            "windows": windows,
            "counterWindows": counter_windows,
            "durationsMs": durations,
            "counters": counters,
            "queues": {
                "recordingQueueDepth": recording_queue_depth or 0,
                "websocketQueueDepth": websocket_queue_depth or 0,
            },
            "bottleneckDetails": bottleneck,
            "30s": thirty,
        }

    @staticmethod
    def _sampling_windows(counter_windows: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        def build(window: str) -> Dict[str, float]:
            return {
                "readAttemptHz": counter_windows["readAttempts"][window],
                "rawReadHz": counter_windows["rawReads"][window],
                "acceptedSampleHz": counter_windows["acceptedSamples"][window],
                "persistedSampleHz": counter_windows["persistedSamples"][window],
                "websocketEmitHz": counter_windows["websocketTelemetry"][window],
                "duplicateSampleHz": counter_windows["duplicateSamples"][window],
                "invalidSampleHz": counter_windows["invalidSamples"][window],
                "staleSampleHz": counter_windows["staleSamples"][window],
            }

        return {
            WINDOW_5S: build(WINDOW_5S),
            WINDOW_30S: build(WINDOW_30S),
        }

    @staticmethod
    def _counters(
        counter_windows: Dict[str, Dict[str, float]],
        recording_dropped_frames: Optional[int],
    ) -> Dict[str, int]:
        dropped = int(counter_windows["droppedSamples"]["total"])
        if recording_dropped_frames is not None:
            dropped += max(int(recording_dropped_frames), 0)
        return {
            "rawSamples": int(counter_windows["rawReads"]["total"]),
            "acceptedSamples": int(counter_windows["acceptedSamples"]["total"]),
            "persistedSamples": int(counter_windows["persistedSamples"]["total"]),
            "invalidSamples": int(counter_windows["invalidSamples"]["total"]),
            "staleSamples": int(counter_windows["staleSamples"]["total"]),
            "duplicateSamples": int(counter_windows["duplicateSamples"]["total"]),
            "droppedSamples": dropped,
            "websocketMessagesSent": int(counter_windows["websocketTelemetry"]["total"]),
            "websocketAllMessagesSent": int(counter_windows["websocketMessages"]["total"]),
            "websocketMessagesCoalesced": int(counter_windows["websocketCoalesced"]["total"]),
            "websocketSendFailures": int(counter_windows["websocketSendFailures"]["total"]),
        }

    @staticmethod
    def _sample_identity(sample: Any) -> Optional[Tuple[Any, ...]]:
        keys = (
            "timestamp",
            "sessionTime",
            "session_time",
            "lap",
            "lapTime",
            "lap_time",
            "normalizedSplinePosition",
            "splinePosition",
            "worldPositionX",
            "worldPositionY",
            "worldPositionZ",
        )
        values = []
        for key in keys:
            value = getattr(sample, key, None)
            if value is None and isinstance(sample, dict):
                value = sample.get(key)
            if isinstance(value, float):
                value = round(value, 5)
            values.append(value)
        if all(value is None for value in values):
            return None
        return tuple(values)

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
        player_source: Optional[str],
        player_status: Optional[str],
        read_attempt_hz: float,
        raw_hz: float,
        accepted_hz: float,
        persisted_hz: float,
        websocket_hz: float,
        last_sample_age_ms: Optional[float],
        backpressure_detected: bool,
        recording_queue_depth: Optional[int],
    ) -> tuple[str, str, bool]:
        normalized_source = (source or "").lower()
        normalized_player_source = (player_source or "").lower()
        normalized_status = (player_status or "").lower()
        offline_or_mock = normalized_source == "mock" or normalized_player_source == "mock"

        if offline_or_mock:
            return "OFFLINE_MOCK", "offline_or_mock_source", False
        if normalized_status in {"waiting", ""} and raw_hz <= 0:
            return "WAITING", "source_waiting", False
        if normalized_status == "stale" or (last_sample_age_ms is not None and last_sample_age_ms > 5000):
            return "ERROR", "last_sample_stale", False
        if backpressure_detected:
            if recording_queue_depth and recording_queue_depth > 1000:
                return "WARNING", "persistence_queue_backpressure", False
            return "WARNING", "websocket_backpressure", False
        if read_attempt_hz > 0 and read_attempt_hz < target_hz * 0.5:
            return "ERROR", "read_loop_interval_below_target", False
        if read_attempt_hz > 0 and read_attempt_hz < target_hz * 0.83:
            return "WARNING", "read_loop_interval_below_target", False
        if raw_hz > 0 and raw_hz < target_hz * 0.83:
            source_limited = read_attempt_hz >= target_hz * 0.83 and accepted_hz >= raw_hz * 0.8
            if source_limited:
                return "SOURCE_LIMITED", "assetto_shared_memory_source_limited", True
            if raw_hz < target_hz * 0.5:
                return "ERROR", "reader_or_source_limited", False
            return "WARNING", "reader_loop_below_target", False
        if accepted_hz > 0 and raw_hz > 0 and accepted_hz < raw_hz * 0.8:
            return "WARNING", "validation_filtering_samples", False
        if persisted_hz > 0 and accepted_hz > 0 and persisted_hz < accepted_hz * 0.7:
            return "WARNING", "persistence_below_collection_rate", False
        if websocket_hz > 0 and accepted_hz > 0 and websocket_hz < accepted_hz * 0.5:
            return "OK", "websocket_or_frontend_throttled_not_collection", False
        if accepted_hz >= target_hz * 0.83:
            return "OK", "collection_on_target", False
        return "WARNING", "sampling_below_target", False


performance_metrics = PerformanceMetrics()
