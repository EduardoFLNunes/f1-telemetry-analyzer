from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


Number = Union[int, float]


@dataclass
class TelemetrySample:
    """Canonical telemetry sample in simulator/world coordinates.

    The reconstruction and projection pipeline uses Assetto Corsa style world
    X/Z as its spatial plane. No frontend-specific map transform is stored here.
    """

    timestamp: Union[str, Number]
    worldPositionX: float
    worldPositionY: float
    worldPositionZ: float
    speed: float = 0.0
    yaw: float = 0.0
    normalizedSplinePosition: float = 0.0
    carId: int = 0
    sector: int = 0
    sessionTime: float = 0.0
    lap: int = 0
    throttle: float = 0.0
    brake: float = 0.0
    steering: float = 0.0
    gear: int = 0
    rpm: int = 0
    accelX: float = 0.0
    accelY: float = 0.0
    accelZ: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetrySample":
        world = data.get("worldPosition") or data.get("world_position")
        return cls(
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            worldPositionX=float(data.get("worldPositionX", data.get("x", world[0] if world else 0.0))),
            worldPositionY=float(data.get("worldPositionY", data.get("y", world[1] if world else 0.0))),
            worldPositionZ=float(data.get("worldPositionZ", data.get("z", world[2] if world else 0.0))),
            speed=float(data.get("speed", data.get("speedKmh", data.get("speed_kmh", 0.0)))),
            yaw=float(data.get("yaw", data.get("heading", 0.0))),
            normalizedSplinePosition=float(data.get("normalizedSplinePosition", data.get("splinePosition", data.get("normalized_spline_pos", 0.0)))),
            carId=int(data.get("carId", data.get("car_id", 0))),
            sector=int(data.get("sector", 0)),
            sessionTime=float(data.get("sessionTime", data.get("session_time", 0.0))),
            lap=int(data.get("lap", data.get("lap_number", 0))),
            throttle=float(data.get("throttle", 0.0)),
            brake=float(data.get("brake", 0.0)),
            steering=float(data.get("steering", 0.0)),
            gear=int(data.get("gear", 0)),
            rpm=int(data.get("rpm", data.get("rpms", 0))),
            accelX=float(data.get("accelX", data.get("accel_x", 0.0))),
            accelY=float(data.get("accelY", data.get("accel_y", 0.0))),
            accelZ=float(data.get("accelZ", data.get("accel_z", 0.0))),
        )

    @property
    def worldPosition(self) -> List[float]:
        return [self.worldPositionX, self.worldPositionY, self.worldPositionZ]

    @property
    def splinePosition(self) -> float:
        return self.normalizedSplinePosition

    @property
    def speedKmh(self) -> float:
        return self.speed

    @property
    def timestamp_ms(self) -> float:
        if isinstance(self.timestamp, (int, float)):
            return float(self.timestamp)
        try:
            parsed = datetime.fromisoformat(str(self.timestamp))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp() * 1000.0
        except ValueError:
            return datetime.now(timezone.utc).timestamp() * 1000.0


@dataclass
class TrackPoint:
    """A reconstructed centerline point in the same world X/Z coordinate space."""

    x: float
    y: float
    z: float
    distance: float
    spline_t: float
    curvature: float = 0.0
    tangent: Tuple[float, float] = (1.0, 0.0)
    normal: Tuple[float, float] = (0.0, 1.0)

    @property
    def p(self) -> float:
        return self.spline_t

    @property
    def mapX(self) -> float:
        return self.x

    @property
    def mapY(self) -> float:
        return self.z

    @property
    def tangentX(self) -> float:
        return self.tangent[0]

    @property
    def tangentY(self) -> float:
        return self.tangent[1]

    @property
    def normalX(self) -> float:
        return self.normal[0]

    @property
    def normalY(self) -> float:
        return self.normal[1]

    @property
    def normal_x(self) -> float:
        return self.normal[0]

    @property
    def normal_z(self) -> float:
        return self.normal[1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": float(self.x),
            "y": float(self.z),
            "z": float(self.z),
            "worldY": float(self.y),
            "distance": float(self.distance),
            "spline_t": float(self.spline_t),
            "curvature": float(self.curvature),
            "tangent": {"x": float(self.tangent[0]), "z": float(self.tangent[1])},
            "normal": {"x": float(self.normal[0]), "z": float(self.normal[1])},
        }
