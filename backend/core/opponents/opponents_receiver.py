import asyncio
import json
import logging
import socket
import threading
from typing import Any, Mapping, Optional

from .opponent_models import OpponentsUpdateResult, safe_float, safe_int, safe_str
from .opponents_buffer import OpponentsStateBuffer
from ..telemetry_events import OPPONENTS_FRAME, event_bus as default_event_bus


logger = logging.getLogger(__name__)


class OpponentsTelemetryReceiver:
    def __init__(
        self,
        buffer: OpponentsStateBuffer,
        host: str = "127.0.0.1",
        port: int = 8765,
        event_bus=default_event_bus,
    ):
        self.buffer = buffer
        self.host = host
        self.port = int(port)
        self.event_bus = event_bus
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None
        self._loop_ref: Optional[asyncio.AbstractEventLoop] = None

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

                logger.info(
                    "Opponents telemetry packet received from %s:%s (%s bytes)",
                    address[0],
                    address[1],
                    len(data),
                )
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
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Opponents telemetry JSON parse error: %s", exc)
            return None

        return self.handle_payload(payload)

    def handle_payload(self, payload: Any) -> Optional[OpponentsUpdateResult]:
        if not isinstance(payload, Mapping):
            logger.warning("Opponents telemetry payload ignored: expected JSON object")
            return None
        if payload.get("type") != "opponents_snapshot":
            logger.warning("Opponents telemetry payload ignored: unexpected type=%s", payload.get("type"))
            return None

        cars = payload.get("cars", [])
        if not isinstance(cars, list):
            logger.warning("Opponents telemetry payload ignored: cars must be a list")
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
        logger.info(
            "Opponents telemetry cars received=%s accepted=%s ignored_player=%s",
            result.received_count,
            result.accepted_count,
            result.ignored_player_count,
        )
        if result.reset_reason:
            logger.info("Opponents telemetry session reset applied: %s", result.reset_reason)
        self._emit(result)
        return result

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
