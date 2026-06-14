from dataclasses import dataclass, field
import math
import time
from typing import Any, Dict, List, Mapping, Optional


SOURCE_NAME = "udp"


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field(data: Mapping[str, Any], key: str, existing: Any = None) -> Any:
    return data[key] if key in data else existing


def _inferred_state(existing: Optional["OpponentCarState"], speed_kmh: Optional[float]) -> str:
    if existing is None or existing.speedKmh is None or speed_kmh is None:
        return "unknown"
    delta = speed_kmh - existing.speedKmh
    if delta > 0.35:
        return "accelerating"
    if delta < -0.35:
        return "braking"
    return "coasting"


def _data_completeness(values: List[Any]) -> float:
    if not values:
        return 0.0
    available = sum(value is not None for value in values)
    return round(available / len(values), 3)


@dataclass(frozen=True)
class OpponentCarState:
    carId: int
    source: str = SOURCE_NAME
    driverName: Optional[str] = None
    carModel: Optional[str] = None
    isPlayer: bool = False
    isAI: Optional[bool] = None
    isMultiplayer: Optional[bool] = None
    worldPositionX: Optional[float] = None
    worldPositionY: Optional[float] = None
    worldPositionZ: Optional[float] = None
    speedKmh: Optional[float] = None
    yaw: Optional[float] = None
    splinePosition: Optional[float] = None
    lap: Optional[int] = None
    lapTime: Optional[float] = None
    racePosition: Optional[int] = None
    status: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    sessionTime: Optional[float] = None
    lastSeenTimestamp: float = field(default_factory=time.time)
    inferredState: str = "unknown"
    dataCompleteness: float = 0.0

    @classmethod
    def from_payload(
        cls,
        data: Mapping[str, Any],
        *,
        timestamp: Optional[float] = None,
        session_time: Optional[float] = None,
        existing: Optional["OpponentCarState"] = None,
        last_seen_timestamp: Optional[float] = None,
    ) -> Optional["OpponentCarState"]:
        car_id = safe_int(data.get("carId", data.get("car_id")))
        if car_id is None:
            return None

        world = data.get("worldPosition") or data.get("world_position") or {}
        if not isinstance(world, Mapping):
            world = {}

        existing_timestamp = existing.timestamp if existing else time.time()
        resolved_timestamp = safe_float(data.get("timestamp"))
        if resolved_timestamp is None:
            resolved_timestamp = timestamp if timestamp is not None else existing_timestamp

        resolved_session_time = safe_float(data.get("sessionTime", data.get("session_time")))
        if resolved_session_time is None:
            resolved_session_time = session_time if session_time is not None else (existing.sessionTime if existing else None)

        status = _field(data, "status", existing.status if existing else "unknown")
        resolved_last_seen_timestamp = last_seen_timestamp
        if resolved_last_seen_timestamp is None:
            resolved_last_seen_timestamp = existing.lastSeenTimestamp if existing else time.time()
        driver_name = safe_str(_field(data, "driverName", existing.driverName if existing else None))
        car_model = safe_str(_field(data, "carModel", existing.carModel if existing else None))
        is_ai = safe_bool(_field(data, "isAI", existing.isAI if existing else None))
        is_multiplayer = safe_bool(
            _field(data, "isMultiplayer", existing.isMultiplayer if existing else None)
        )
        world_x = safe_float(_field(world, "x", existing.worldPositionX if existing else None))
        world_y = safe_float(_field(world, "y", existing.worldPositionY if existing else None))
        world_z = safe_float(_field(world, "z", existing.worldPositionZ if existing else None))
        speed_kmh = safe_float(_field(data, "speedKmh", existing.speedKmh if existing else None))
        yaw = safe_float(_field(data, "yaw", existing.yaw if existing else None))
        spline_position = safe_float(
            _field(data, "splinePosition", existing.splinePosition if existing else None)
        )
        lap = safe_int(_field(data, "lap", existing.lap if existing else None))
        lap_time = safe_float(_field(data, "lapTime", existing.lapTime if existing else None))
        race_position = safe_int(
            _field(data, "racePosition", existing.racePosition if existing else None)
        )
        resolved_status = safe_str(status) or "unknown"
        inferred_state = _inferred_state(existing, speed_kmh)
        completeness = _data_completeness(
            [
                driver_name,
                car_model,
                is_ai,
                is_multiplayer,
                world_x,
                world_y,
                world_z,
                speed_kmh,
                yaw,
                spline_position,
                lap,
                lap_time,
                race_position,
                None if resolved_status == "unknown" else resolved_status,
            ]
        )

        return cls(
            carId=car_id,
            source=SOURCE_NAME,
            driverName=driver_name,
            carModel=car_model,
            isPlayer=safe_bool(_field(data, "isPlayer", existing.isPlayer if existing else False)) or False,
            isAI=is_ai,
            isMultiplayer=is_multiplayer,
            worldPositionX=world_x,
            worldPositionY=world_y,
            worldPositionZ=world_z,
            speedKmh=speed_kmh,
            yaw=yaw,
            splinePosition=spline_position,
            lap=lap,
            lapTime=lap_time,
            racePosition=race_position,
            status=resolved_status,
            timestamp=float(resolved_timestamp),
            sessionTime=resolved_session_time,
            lastSeenTimestamp=float(resolved_last_seen_timestamp),
            inferredState=inferred_state,
            dataCompleteness=completeness,
        )

    def to_api(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "carId": self.carId,
            "driverName": self.driverName,
            "carModel": self.carModel,
            "isPlayer": self.isPlayer,
            "isAI": self.isAI,
            "isMultiplayer": self.isMultiplayer,
            "worldPosition": {
                "x": self.worldPositionX,
                "y": self.worldPositionY,
                "z": self.worldPositionZ,
            },
            "speedKmh": self.speedKmh,
            "yaw": self.yaw,
            "splinePosition": self.splinePosition,
            "lap": self.lap,
            "lapTime": self.lapTime,
            "racePosition": self.racePosition,
            "status": self.status,
            "timestamp": self.timestamp,
            "sessionTime": self.sessionTime,
            "lastSeenTimestamp": self.lastSeenTimestamp,
            "inferredState": self.inferredState,
            "dataCompleteness": self.dataCompleteness,
            "provenance": {
                "source": SOURCE_NAME,
                "inferredFields": ["inferredState"] if self.inferredState != "unknown" else [],
                "unavailablePhysics": [
                    "throttle",
                    "brake",
                    "tyreTemperature",
                    "suspension",
                    "fuel",
                    "setup",
                ],
            },
        }


@dataclass(frozen=True)
class OpponentsUpdateResult:
    timestamp: float
    sessionTime: Optional[float]
    track: Optional[str]
    cars: List[OpponentCarState]
    received_count: int
    accepted_count: int
    ignored_player_count: int
    reset_reason: Optional[str] = None
    ignored_out_of_order: bool = False

    def event_payload(self) -> Dict[str, Any]:
        return {
            "source": SOURCE_NAME,
            "timestamp": self.timestamp,
            "sessionTime": self.sessionTime,
            "track": self.track,
            "cars": [car.to_api() for car in self.cars],
        }
