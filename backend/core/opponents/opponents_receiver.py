import asyncio
import json
import logging
import socket
import threading
import time
from typing import Any, Mapping, Optional

from .opponent_models import OpponentsUpdateResult, safe_float, safe_int, safe_str
from .opponents_buffer import OpponentsStateBuffer
from ..data_quality.udp_reliability import UdpReliabilityMonitor
from ..performance_metrics import performance_metrics
from ..telemetry_events import OPPONENTS_FRAME, event_bus as default_event_bus


logger = logging.getLogger(__name__)


class OpponentsTelemetryReceiver:
    def __init__(
        self,
        buffer: OpponentsStateBuffer,
        host: str = "127.0.0.1",
        port: int = 8765,
        event_bus=default_event_bus,
        reliability_monitor: Optional[UdpReliabilityMonitor] = None,
    ):
        self.buffer = buffer
        self.host = host
        self.port = int(port)
        self.event_bus = event_bus
        self.reliability_monitor = reliability_monitor or UdpReliabilityMonitor()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None
        self._loop_ref: Optional[asyncio.AbstractEventLoop] = None
        self._last_packet_log_at = 0.0
        self._packets_since_log = 0
        self._last_summary_log_at = 0.0
        self._received_since_summary = 0
        self._accepted_since_summary = 0
        self._ignored_since_summary = 0
        self._last_invalid_log_at = 0.0
        self._invalid_packet_count = 0
        self._out_of_order_count = 0
        self._accepted_snapshot_count = 0
        self._last_packet_received_at: Optional[float] = None
        self._last_valid_snapshot_at: Optional[float] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if self.running:
            return
        self._loop_ref = loop
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError as exc:
                logger.warning("Opponents telemetry receiver socket close error: %s", exc)
            self._socket = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket = sock
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(0.5)
            logger.info("Opponents telemetry receiver started on %s:%s", self.host, self.port)

            while self.running:
                try:
                    data, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if self.running:
                        logger.error("Opponents telemetry receiver socket error: %s", exc)
                    break

                self._log_packet_received(address, len(data))
                self.handle_packet(data)
        except OSError as exc:
            logger.error("Opponents telemetry receiver socket error: %s", exc)
        except Exception as exc:
            logger.exception("Opponents telemetry receiver error: %s", exc)
        finally:
            try:
                sock.close()
            except OSError:
                pass
            if self._socket is sock:
                self._socket = None
            self.running = False
            logger.info("Opponents telemetry receiver stopped")

    def handle_packet(self, data: bytes) -> Optional[OpponentsUpdateResult]:
        self._last_packet_received_at = time.time()
        self.reliability_monitor.packet_received(self._last_packet_received_at)
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._log_invalid("JSON parse error: %s" % exc)
            return None

        return self.handle_payload(payload)

    def handle_payload(self, payload: Any) -> Optional[OpponentsUpdateResult]:
        if not isinstance(payload, Mapping):
            self._log_invalid("expected JSON object")
            return None
        if payload.get("type") != "opponents_snapshot":
            self._log_invalid("unexpected type=%s" % payload.get("type"))
            return None

        cars = payload.get("cars", [])
        if not isinstance(cars, list):
            self._log_invalid("cars must be a list")
            return None

        timestamp = safe_float(payload.get("timestamp"))
        session_time = safe_float(payload.get("sessionTime"))
        player_car_id = safe_int(payload.get("playerCarId"))
        track = safe_str(payload.get("track"))

        result = self.buffer.update_snapshot(
            cars,
            timestamp=timestamp,
            session_time=session_time,
            player_car_id=player_car_id,
            track=track,
        )
        if result.ignored_out_of_order:
            self._out_of_order_count += 1
            self.reliability_monitor.out_of_order()
            logger.debug("Opponents telemetry out-of-order snapshot ignored: timestamp=%s", timestamp)
            return result

        self._accepted_snapshot_count += 1
        self._last_valid_snapshot_at = time.time()
        self.reliability_monitor.accepted(result.ignored_player_count)
        self._log_update_summary(result)
        if result.reset_reason:
            logger.info("Opponents telemetry session reset applied: %s", result.reset_reason)
        performance_metrics.mark_opponents_snapshot()
        self._emit(result)
        return result

    def status(self):
        reliability = self.reliability_monitor.snapshot(
            opponents_count=len(self.buffer.latest())
        )
        return {
            "source": "udp",
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "lastPacketReceivedAt": self._last_packet_received_at,
            "lastValidSnapshotAt": self._last_valid_snapshot_at,
            "acceptedSnapshots": self._accepted_snapshot_count,
            "invalidPackets": self._invalid_packet_count,
            "discardedOutOfOrder": self._out_of_order_count,
            **reliability,
        }

    def _log_update_summary(self, result: OpponentsUpdateResult):
        self._received_since_summary += result.received_count
        self._accepted_since_summary += result.accepted_count
        self._ignored_since_summary += result.ignored_player_count

        now = time.monotonic()
        if now - self._last_summary_log_at < 2.0:
            logger.debug(
                "Opponents telemetry cars received=%s accepted=%s ignored_player=%s",
                result.received_count,
                result.accepted_count,
                result.ignored_player_count,
            )
            return

        logger.info(
            "Opponents telemetry summary received=%s accepted=%s ignored_player=%s",
            self._received_since_summary,
            self._accepted_since_summary,
            self._ignored_since_summary,
        )
        self._received_since_summary = 0
        self._accepted_since_summary = 0
        self._ignored_since_summary = 0
        self._last_summary_log_at = now

    def _log_packet_received(self, address, byte_count: int):
        self._packets_since_log += 1
        now = time.monotonic()
        if now - self._last_packet_log_at < 2.0:
            logger.debug(
                "Opponents telemetry packet received from %s:%s (%s bytes)",
                address[0],
                address[1],
                byte_count,
            )
            return

        logger.info(
            "Opponents telemetry packets received=%s last_from=%s:%s last_bytes=%s",
            self._packets_since_log,
            address[0],
            address[1],
            byte_count,
        )
        self._packets_since_log = 0
        self._last_packet_log_at = now

    def _log_invalid(self, reason: str):
        self._invalid_packet_count += 1
        self.reliability_monitor.invalid()
        now = time.monotonic()
        if now - self._last_invalid_log_at >= 2.0:
            logger.warning(
                "Opponents telemetry invalid packets=%s last_error=%s",
                self._invalid_packet_count,
                reason,
            )
            self._last_invalid_log_at = now
        else:
            logger.debug("Opponents telemetry payload ignored: %s", reason)

    def _emit(self, result: OpponentsUpdateResult):
        if not self.event_bus or not self._loop_ref:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.emit(OPPONENTS_FRAME, result.event_payload()),
                self._loop_ref,
            )
        except Exception as exc:
            logger.warning("Opponents telemetry event emit error: %s", exc)
