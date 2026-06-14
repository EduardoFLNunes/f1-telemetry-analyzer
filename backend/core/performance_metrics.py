import threading
import time
from collections import deque
from typing import Deque, Dict, Optional


class RateCounter:
    def __init__(self, window_seconds: float = 5.0):
        self.window_seconds = max(float(window_seconds), 1.0)
        self._timestamps: Deque[float] = deque()
        self._lock = threading.Lock()

    def mark(self, count: int = 1, now: Optional[float] = None):
        timestamp = time.monotonic() if now is None else float(now)
        amount = max(int(count), 0)
        if amount <= 0:
            return
        with self._lock:
            for _ in range(amount):
                self._timestamps.append(timestamp)
            self._prune(timestamp)

    def rate(self, now: Optional[float] = None) -> float:
        timestamp = time.monotonic() if now is None else float(now)
        with self._lock:
            self._prune(timestamp)
            return len(self._timestamps) / self.window_seconds

    def _prune(self, now: float):
        cutoff = now - self.window_seconds
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


class PerformanceMetrics:
    def __init__(self):
        self._player_samples = RateCounter()
        self._opponent_snapshots = RateCounter()
        self._websocket_messages = RateCounter()
        self._websocket_frames_coalesced = RateCounter()
        self._frame_processing_seconds = RollingAverage()
        self._disk_write_seconds = RollingAverage()

    def mark_player_frame(self, processing_seconds: Optional[float] = None):
        self._player_samples.mark()
        if processing_seconds is not None:
            self._frame_processing_seconds.add(processing_seconds)

    def mark_opponents_snapshot(self):
        self._opponent_snapshots.mark()

    def mark_websocket_message(self, count: int = 1):
        self._websocket_messages.mark(count=count)

    def mark_websocket_frame_coalesced(self):
        self._websocket_frames_coalesced.mark()

    def record_disk_write(self, seconds: float):
        self._disk_write_seconds.add(seconds)

    def snapshot(self) -> Dict[str, float]:
        return {
            "playerSamplesPerSecond": round(self._player_samples.rate(), 2),
            "opponentSnapshotsPerSecond": round(self._opponent_snapshots.rate(), 2),
            "websocketMessagesPerSecond": round(self._websocket_messages.rate(), 2),
            "websocketFramesCoalescedPerSecond": round(self._websocket_frames_coalesced.rate(), 2),
            "averageFrameProcessingMs": round(self._frame_processing_seconds.average() * 1000.0, 3),
            "averageDiskWriteMs": round(self._disk_write_seconds.average() * 1000.0, 3),
        }


performance_metrics = PerformanceMetrics()
