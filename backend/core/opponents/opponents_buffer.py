import threading
import time
import logging
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from .opponent_models import OpponentCarState, OpponentsUpdateResult, safe_bool, safe_float, safe_int, safe_str


logger = logging.getLogger(__name__)


class OpponentsStateBuffer:
    def __init__(
        self,
        stale_after_seconds: float = 5.0,
        session_reset_threshold_seconds: float = 5.0,
        time_provider: Callable[[], float] = time.time,
    ):
        self.stale_after_seconds = float(stale_after_seconds)
        self.session_reset_threshold_seconds = float(session_reset_threshold_seconds)
        self._time = time_provider
        self._cars: Dict[int, OpponentCarState] = {}
        self._track: Optional[str] = None
        self._session_time: Optional[float] = None
        self._last_update_timestamp: Optional[float] = None
        self._lock = threading.Lock()

    def latest(self) -> Dict[int, OpponentCarState]:
        with self._lock:
            self._prune_stale_locked(self._time())
            return dict(self._cars)

    def metadata(self) -> Dict[str, Any]:
        with self._lock:
            self._prune_stale_locked(self._time())
            return {
                "count": len(self._cars),
                "track": self._track,
                "sessionTime": self._session_time,
                "lastUpdateTimestamp": self._last_update_timestamp,
                "staleAfterSeconds": self.stale_after_seconds,
            }

    def update_snapshot(
        self,
        cars: Iterable[Mapping[str, Any]],
        *,
        timestamp: Optional[float] = None,
        session_time: Optional[float] = None,
        player_car_id: Optional[int] = None,
        track: Optional[str] = None,
    ) -> OpponentsUpdateResult:
        parsed_timestamp = safe_float(timestamp)
        now = self._time()
        resolved_timestamp = parsed_timestamp if parsed_timestamp is not None else now
        resolved_session_time = safe_float(session_time)
        resolved_player_car_id = safe_int(player_car_id)
        resolved_track = safe_str(track)

        received_count = 0
        ignored_player_count = 0
        accepted = []
        reset_reason = None

        with self._lock:
            reset_reason = self._maybe_reset_session_locked(resolved_track, resolved_session_time)
            for car_payload in cars:
                received_count += 1
                if not isinstance(car_payload, Mapping):
                    continue

                car_id = safe_int(car_payload.get("carId", car_payload.get("car_id")))
                if car_id is None:
                    continue

                is_player = safe_bool(car_payload.get("isPlayer")) is True
                if is_player or (resolved_player_car_id is not None and car_id == resolved_player_car_id):
                    ignored_player_count += 1
                    continue

                existing = self._cars.get(car_id)
                state = OpponentCarState.from_payload(
                    car_payload,
                    timestamp=resolved_timestamp,
                    session_time=resolved_session_time,
                    existing=existing,
                    last_seen_timestamp=now,
                )
                if not state or state.isPlayer:
                    ignored_player_count += 1
                    continue

                self._cars[state.carId] = state
                accepted.append(state)

            if resolved_track is not None:
                self._track = resolved_track
            if resolved_session_time is not None:
                self._session_time = resolved_session_time
            self._last_update_timestamp = resolved_timestamp
            self._prune_stale_locked(now)

        return OpponentsUpdateResult(
            timestamp=resolved_timestamp,
            sessionTime=self._session_time,
            track=self._track,
            cars=accepted,
            received_count=received_count,
            accepted_count=len(accepted),
            ignored_player_count=ignored_player_count,
            reset_reason=reset_reason,
        )

    def clear(self):
        with self._lock:
            self._cars = {}
            self._track = None
            self._session_time = None
            self._last_update_timestamp = None

    def _maybe_reset_session_locked(self, track: Optional[str], session_time: Optional[float]) -> Optional[str]:
        if track and self._track and track != self._track:
            previous_track = self._track
            self._cars = {}
            self._session_time = None
            self._last_update_timestamp = None
            logger.info("Opponents telemetry buffer cleared: track changed from %s to %s", previous_track, track)
            return "track_changed"

        if (
            session_time is not None
            and self._session_time is not None
            and session_time + self.session_reset_threshold_seconds < self._session_time
        ):
            previous_session_time = self._session_time
            self._cars = {}
            self._last_update_timestamp = None
            logger.info(
                "Opponents telemetry buffer cleared: sessionTime reset from %.3f to %.3f",
                previous_session_time,
                session_time,
            )
            return "session_reset"

        return None

    def _prune_stale_locked(self, now: float):
        if self.stale_after_seconds <= 0:
            return
        stale_ids = [
            car_id
            for car_id, car in self._cars.items()
            if now - car.lastSeenTimestamp > self.stale_after_seconds
        ]
        for car_id in stale_ids:
            del self._cars[car_id]
        if stale_ids:
            logger.info("Opponents telemetry stale cars removed: %s", stale_ids)
