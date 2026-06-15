import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, Optional


logger = logging.getLogger(__name__)


class UdpReliabilityMonitor:
    def __init__(
        self,
        live_window_seconds: float = 5.0,
        stale_after_seconds: float = 5.0,
        time_provider: Callable[[], float] = time.time,
    ):
        self.live_window_seconds = float(live_window_seconds)
        self.stale_after_seconds = float(stale_after_seconds)
        self._time = time_provider
        self._packet_times: Deque[float] = deque()
        self._packets_received = 0
        self._packets_accepted = 0
        self._packets_invalid = 0
        self._packets_out_of_order = 0
        self._player_filtered_count = 0
        self._last_packet_at: Optional[float] = None
        self._last_stale_log_at = 0.0
        self._last_invalid_log_at = 0.0
        self._lock = threading.Lock()

    def packet_received(self, received_at: Optional[float] = None):
        now = float(self._time() if received_at is None else received_at)
        with self._lock:
            self._packets_received += 1
            self._last_packet_at = now
            self._packet_times.append(now)
            self._prune_locked(now)

    def accepted(self, player_filtered_count: int = 0):
        with self._lock:
            self._packets_accepted += 1
            self._player_filtered_count += max(0, int(player_filtered_count))

    def invalid(self):
        with self._lock:
            self._packets_invalid += 1

    def out_of_order(self):
        with self._lock:
            self._packets_out_of_order += 1

    def snapshot(self, opponents_count: int = 0, now: Optional[float] = None) -> Dict[str, object]:
        current = float(self._time() if now is None else now)
        with self._lock:
            self._prune_locked(current)
            age = None if self._last_packet_at is None else max(0.0, current - self._last_packet_at)
            if self._last_packet_at is None:
                status = "waiting"
            elif age is not None and age > self.stale_after_seconds:
                status = "stale"
            else:
                status = "receiving"
            estimated_hz = self._frequency_locked(current)
            dropped = self._packets_invalid + self._packets_out_of_order
            payload = {
                "source": "udp",
                "status": status,
                "targetHz": None,
                "estimatedHz": estimated_hz,
                "packetsReceived": self._packets_received,
                "packetsAccepted": self._packets_accepted,
                "packetsDropped": dropped,
                "packetsInvalid": self._packets_invalid,
                "packetsOutOfOrder": self._packets_out_of_order,
                "opponentsCount": max(0, int(opponents_count)),
                "lastPacketAtEpoch": self._last_packet_at,
                "lastPacketAt": (
                    datetime.fromtimestamp(self._last_packet_at, timezone.utc).isoformat()
                    if self._last_packet_at is not None
                    else None
                ),
                "secondsSinceLastPacket": round(age, 3) if age is not None else None,
                "playerFilteredCount": self._player_filtered_count,
            }
            self._maybe_log_locked(current, payload)
            return payload

    def _prune_locked(self, now: float):
        cutoff = now - self.live_window_seconds
        while self._packet_times and self._packet_times[0] < cutoff:
            self._packet_times.popleft()

    def _frequency_locked(self, now: float) -> Optional[float]:
        if len(self._packet_times) < 2:
            return None
        duration = min(
            self.live_window_seconds,
            max(now - self._packet_times[0], self._packet_times[-1] - self._packet_times[0]),
        )
        if duration < 0.5:
            return None
        return round(len(self._packet_times) / duration, 2)

    def _maybe_log_locked(self, now: float, payload: Dict[str, object]):
        if payload["status"] == "stale" and now - self._last_stale_log_at >= 30.0:
            self._last_stale_log_at = now
            logger.warning(
                "UDP opponents telemetry is stale: age=%ss",
                payload["secondsSinceLastPacket"],
            )
        received = int(payload["packetsReceived"])
        invalid = int(payload["packetsInvalid"])
        if received >= 10 and invalid / received >= 0.2 and now - self._last_invalid_log_at >= 30.0:
            self._last_invalid_log_at = now
            logger.warning(
                "UDP opponents invalid packet ratio is high: invalid=%s received=%s",
                invalid,
                received,
            )
