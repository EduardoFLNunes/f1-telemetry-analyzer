from dataclasses import dataclass, field
from datetime import datetime
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
    lapTime: Optional[float] = None
    lap: int = 0
    throttle: float = 0.0
    brake: float = 0.0
    steering: float = 0.0
    gear: int = 0
    rpm: int = 0
    accelX: float = 0.0
    accelY: float = 0.0
    accelZ: float = 0.0
    velocityX: Optional[float] = None
    velocityY: Optional[float] = None
    velocityZ: Optional[float] = None
    clutch: Optional[float] = None
    fuel: Optional[float] = None
    maxFuel: Optional[float] = None
    ballast: Optional[float] = None
    abs: Optional[float] = None
    tc: Optional[float] = None
    drs: Optional[bool] = None
    turboBoost: Optional[float] = None
    airTemp: Optional[float] = None
    roadTemp: Optional[float] = None
    surfaceGrip: Optional[float] = None
    airDensity: Optional[float] = None
    tyreCoreTemperature: List[Optional[float]] = field(default_factory=list)
    tyrePressure: List[Optional[float]] = field(default_factory=list)
    tyreWear: List[Optional[float]] = field(default_factory=list)
    tyreDirtyLevel: List[Optional[float]] = field(default_factory=list)
    wheelSlip: List[Optional[float]] = field(default_factory=list)
    wheelLoad: List[Optional[float]] = field(default_factory=list)
    suspensionTravel: List[Optional[float]] = field(default_factory=list)
    rideHeight: List[Optional[float]] = field(default_factory=list)
    camberRad: List[Optional[float]] = field(default_factory=list)
    carDamage: List[Optional[float]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetrySample":
        world = data.get("worldPosition") or data.get("world_position")

        def nullable_float(value: Any) -> Optional[float]:
            if value is None:
                return None
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            return number if number == number and number not in (float("inf"), float("-inf")) else None

        def nullable_bool(value: Any) -> Optional[bool]:
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

        def nullable_float_list(value: Any) -> List[Optional[float]]:
            if value is None:
                return []
            if not isinstance(value, (list, tuple)):
                return []
            return [nullable_float(item) for item in value]

        velocity = data.get("velocity") or {}
        if not isinstance(velocity, dict):
            velocity = {}

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
            lapTime=nullable_float(
                data.get("lapTime", data.get("lap_time", data.get("currentLapTime")))
            ),
            lap=int(data.get("lap", data.get("lap_number", 0))),
            throttle=float(data.get("throttle", 0.0)),
            brake=float(data.get("brake", 0.0)),
            steering=float(data.get("steering", 0.0)),
            gear=int(data.get("gear", 0)),
            rpm=int(data.get("rpm", data.get("rpms", 0))),
            accelX=float(data.get("accelX", data.get("accel_x", 0.0))),
            accelY=float(data.get("accelY", data.get("accel_y", 0.0))),
            accelZ=float(data.get("accelZ", data.get("accel_z", 0.0))),
            velocityX=nullable_float(data.get("velocityX", data.get("velocity_x", velocity.get("x")))),
            velocityY=nullable_float(data.get("velocityY", data.get("velocity_y", velocity.get("y")))),
            velocityZ=nullable_float(data.get("velocityZ", data.get("velocity_z", velocity.get("z")))),
            clutch=nullable_float(data.get("clutch")),
            fuel=nullable_float(data.get("fuel")),
            maxFuel=nullable_float(data.get("maxFuel", data.get("max_fuel"))),
            ballast=nullable_float(data.get("ballast")),
            abs=nullable_float(data.get("abs")),
            tc=nullable_float(data.get("tc")),
            drs=nullable_bool(data.get("drs")),
            turboBoost=nullable_float(data.get("turboBoost", data.get("turbo_boost"))),
            airTemp=nullable_float(data.get("airTemp", data.get("air_temp"))),
            roadTemp=nullable_float(data.get("roadTemp", data.get("road_temp"))),
            surfaceGrip=nullable_float(data.get("surfaceGrip", data.get("surface_grip"))),
            airDensity=nullable_float(data.get("airDensity", data.get("air_density"))),
            tyreCoreTemperature=nullable_float_list(data.get("tyreCoreTemperature", data.get("tyre_core_temperature"))),
            tyrePressure=nullable_float_list(data.get("tyrePressure", data.get("wheelsPressure", data.get("wheels_pressure")))),
            tyreWear=nullable_float_list(data.get("tyreWear", data.get("tyre_wear"))),
            tyreDirtyLevel=nullable_float_list(data.get("tyreDirtyLevel", data.get("tyre_dirty_level"))),
            wheelSlip=nullable_float_list(data.get("wheelSlip", data.get("wheel_slip"))),
            wheelLoad=nullable_float_list(data.get("wheelLoad", data.get("wheel_load"))),
            suspensionTravel=nullable_float_list(data.get("suspensionTravel", data.get("suspension_travel"))),
            rideHeight=nullable_float_list(data.get("rideHeight", data.get("ride_height"))),
            camberRad=nullable_float_list(data.get("camberRad", data.get("camberRAD", data.get("camber_rad")))),
            carDamage=nullable_float_list(data.get("carDamage", data.get("car_damage"))),
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
            return datetime.fromisoformat(str(self.timestamp)).timestamp() * 1000.0
        except ValueError:
            return datetime.utcnow().timestamp() * 1000.0


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
