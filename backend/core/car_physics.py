from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .opponents.opponent_models import OpponentCarState
from .telemetry.telemetry_models import TelemetrySample


TelemetryDataSource = str
DataCompleteness = str
AccelerationState = str
GripLevel = str

ASSETTO_REAL: TelemetryDataSource = "ASSETTO_REAL"
INFERRED: TelemetryDataSource = "INFERRED"
UNAVAILABLE: TelemetryDataSource = "UNAVAILABLE"


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_bool(value: Any) -> Optional[bool]:
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


def _array4(values: Optional[Sequence[Any]]) -> List[Optional[float]]:
    normalized = [_safe_float(item) for item in list(values or [])[:4]]
    return normalized + [None] * (4 - len(normalized))


def _array5(values: Optional[Sequence[Any]]) -> List[Optional[float]]:
    normalized = [_safe_float(item) for item in list(values or [])[:5]]
    return normalized + [None] * (5 - len(normalized))


def _array2(values: Optional[Sequence[Any]]) -> List[Optional[float]]:
    normalized = [_safe_float(item) for item in list(values or [])[:2]]
    return normalized + [None] * (2 - len(normalized))


def _has_any_real(values: Sequence[Optional[float]]) -> bool:
    return any(value is not None for value in values)


def _smooth(values: Sequence[float], window: int = 3) -> List[float]:
    if len(values) < window:
        return list(values)
    radius = max(1, window // 2)
    result = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        chunk = values[start:end]
        result.append(sum(chunk) / len(chunk))
    return result


def _sample_speed_kmh(sample: Any) -> Optional[float]:
    if isinstance(sample, Mapping):
        speed = _safe_float(sample.get("speedKmh", sample.get("speed_kmh")))
        if speed is not None:
            return speed
        speed = _safe_float(sample.get("speed"))
        return speed * 3.6 if speed is not None and speed < 120 else speed
    if isinstance(sample, OpponentCarState):
        return _safe_float(sample.speedKmh)
    if isinstance(sample, TelemetrySample):
        return _safe_float(sample.speed)
    return _safe_float(getattr(sample, "speedKmh", getattr(sample, "speed", None)))


def _sample_progress(sample: Any) -> Optional[float]:
    if isinstance(sample, Mapping):
        progress = _safe_float(
            sample.get(
                "splinePosition",
                sample.get("normalizedSplinePosition", sample.get("lapProgress", sample.get("p"))),
            )
        )
    elif isinstance(sample, OpponentCarState):
        progress = _safe_float(sample.splinePosition)
    elif isinstance(sample, TelemetrySample):
        progress = _safe_float(sample.normalizedSplinePosition)
    else:
        progress = _safe_float(getattr(sample, "splinePosition", getattr(sample, "normalizedSplinePosition", None)))
    if progress is None or progress < 0.0 or progress > 1.0:
        return None
    return progress


def infer_acceleration_state(samples: Iterable[Any]) -> AccelerationState:
    points = [
        (_sample_progress(sample), _sample_speed_kmh(sample))
        for sample in samples
    ]
    valid = [(progress, speed) for progress, speed in points if progress is not None and speed is not None]
    valid.sort(key=lambda item: item[0])
    if len(valid) < 3:
        return "UNKNOWN"

    speeds = _smooth([speed for _, speed in valid])
    deltas = [current - previous for previous, current in zip(speeds, speeds[1:])]
    if not deltas:
        return "UNKNOWN"

    total_delta = speeds[-1] - speeds[0]
    drops = [delta for delta in deltas if delta <= -0.7]
    gains = [delta for delta in deltas if delta >= 0.7]
    stable = [delta for delta in deltas if abs(delta) <= 0.7]
    ratio_denominator = max(1, len(deltas))

    if total_delta <= -2.0 and len(drops) / ratio_denominator >= 0.45:
        return "BRAKING"
    if total_delta >= 2.0 and len(gains) / ratio_denominator >= 0.45:
        return "ACCELERATING"
    if abs(total_delta) <= 2.0 and len(stable) / ratio_denominator >= 0.6:
        return "COASTING"
    return "UNKNOWN"


def infer_grip_index(
    tyre_temp: Sequence[Optional[float]],
    tyre_wear: Sequence[Optional[float]],
    tyre_dirty_level: Sequence[Optional[float]],
    wheel_slip: Sequence[Optional[float]],
    wheel_load: Sequence[Optional[float]],
    surface_grip: Optional[float],
) -> Optional[float]:
    signals_available = any(
        _has_any_real(values)
        for values in (tyre_temp, tyre_wear, tyre_dirty_level, wheel_slip, wheel_load)
    ) or surface_grip is not None
    if not signals_available:
        return None

    index = 1.0
    surface = _safe_float(surface_grip)
    if surface is not None:
        index *= max(0.0, min(1.2, surface))

    slip_values = [abs(value) for value in wheel_slip if value is not None]
    if slip_values:
        index -= min(0.35, sum(slip_values) / len(slip_values) * 0.08)

    dirty_values = [value for value in tyre_dirty_level if value is not None]
    if dirty_values:
        index -= min(0.25, sum(dirty_values) / len(dirty_values) * 0.02)

    wear_values = [value for value in tyre_wear if value is not None]
    if wear_values:
        normalized_wear = [value / 100.0 if value > 1.0 else value for value in wear_values]
        index -= min(0.25, sum(normalized_wear) / len(normalized_wear) * 0.2)

    temp_values = [value for value in tyre_temp if value is not None]
    if temp_values:
        penalties = [max(0.0, abs(value - 85.0) - 20.0) / 100.0 for value in temp_values]
        index -= min(0.2, sum(penalties) / len(penalties))

    load_values = [value for value in wheel_load if value is not None and value > 0.0]
    if wheel_load and not load_values:
        index -= 0.1

    return max(0.0, min(1.0, index))


def infer_grip_level(grip_index: Optional[float]) -> GripLevel:
    if grip_index is None:
        return "UNKNOWN"
    if grip_index >= 0.78:
        return "HIGH"
    if grip_index >= 0.48:
        return "MEDIUM"
    return "LOW"


def infer_data_completeness(telemetry: Mapping[str, Any]) -> DataCompleteness:
    availability = telemetry.get("availability") if isinstance(telemetry, Mapping) else {}
    if not isinstance(availability, Mapping):
        return "MINIMAL"

    full_fields = [
        "hasRealThrottle",
        "hasRealBrake",
        "hasRealTyreData",
        "hasRealSuspensionData",
        "hasRealEnvironmentData",
    ]
    available_count = sum(1 for key in full_fields if availability.get(key) is True)
    if available_count >= 5:
        return "FULL"
    if available_count >= 2:
        return "PARTIAL"
    return "MINIMAL"


def _missing_fields(telemetry: Mapping[str, Any]) -> List[str]:
    missing = []

    def visit(prefix: str, value: Any):
        if value is None:
            missing.append(prefix)
            return
        if isinstance(value, list):
            if not value or all(item is None for item in value):
                missing.append(prefix)
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                visit(f"{prefix}.{key}" if prefix else str(key), child)

    visit("", telemetry)
    return [field for field in missing if field and not field.startswith("source.")]


def _base_unavailable_physics() -> Dict[str, Any]:
    return {
        "motion": {
            "speedKmh": None,
            "velocity": {"x": None, "y": None, "z": None},
            "accG": {"lateral": None, "longitudinal": None, "vertical": None},
        },
        "controls": {
            "throttle": None,
            "brake": None,
            "clutch": None,
            "steerAngle": None,
            "gear": None,
            "rpm": None,
        },
        "tyres": {
            "tyreCoreTemperature": [None, None, None, None],
            "tyrePressure": [None, None, None, None],
            "tyreWear": [None, None, None, None],
            "tyreDirtyLevel": [None, None, None, None],
            "wheelSlip": [None, None, None, None],
            "wheelLoad": [None, None, None, None],
            "estimatedGripIndex": [None, None, None, None],
        },
        "suspension": {
            "suspensionTravel": [None, None, None, None],
            "rideHeight": [None, None],
            "camberRad": [None, None, None, None],
        },
        "carState": {
            "fuel": None,
            "maxFuel": None,
            "ballast": None,
            "carDamage": [None, None, None, None, None],
            "abs": None,
            "tc": None,
            "drs": None,
            "turboBoost": None,
        },
        "environment": {
            "airTemp": None,
            "roadTemp": None,
            "surfaceGrip": None,
            "airDensity": None,
            "tyresOut": None,
            "offTrack": None,
            "penaltyTime": None,
        },
    }


def build_player_car_physics(
    sample: Optional[TelemetrySample],
    recent_samples: Optional[Sequence[TelemetrySample]] = None,
) -> Dict[str, Any]:
    base = _base_unavailable_physics()
    if sample is None:
        telemetry = {
            "source": {
                "playerPhysicsAvailable": False,
                "opponentPhysicsAvailable": False,
                "dataCompleteness": "MINIMAL",
            },
            **base,
            "inferred": {
                "estimatedAccelerationState": "UNKNOWN",
                "estimatedGripLevel": "UNKNOWN",
                "estimatedMassKg": None,
                "estimatedDragState": "UNKNOWN",
            },
            "availability": {
                "hasRealThrottle": False,
                "hasRealBrake": False,
                "hasRealTyreData": False,
                "hasRealSuspensionData": False,
                "hasRealEnvironmentData": False,
                "hasInferredGrip": False,
                "hasInferredAccelerationState": False,
            },
        }
        return telemetry

    tyre_temp = _array4(sample.tyreCoreTemperature)
    tyre_pressure = _array4(sample.tyrePressure)
    tyre_wear = _array4(sample.tyreWear)
    tyre_dirty = _array4(sample.tyreDirtyLevel)
    wheel_slip = _array4(sample.wheelSlip)
    wheel_load = _array4(sample.wheelLoad)
    suspension_travel = _array4(sample.suspensionTravel)
    ride_height = _array2(sample.rideHeight)
    camber = _array4(sample.camberRad)
    car_damage = _array5(sample.carDamage)
    surface_grip = _safe_float(sample.surfaceGrip)
    grip_index = infer_grip_index(tyre_temp, tyre_wear, tyre_dirty, wheel_slip, wheel_load, surface_grip)
    acceleration_state = infer_acceleration_state(recent_samples or [sample])

    telemetry = {
        "source": {
            "playerPhysicsAvailable": True,
            "opponentPhysicsAvailable": False,
            "dataCompleteness": "MINIMAL",
        },
        "motion": {
            "speedKmh": _safe_float(sample.speed),
            "velocity": {
                "x": _safe_float(sample.velocityX),
                "y": _safe_float(sample.velocityY),
                "z": _safe_float(sample.velocityZ),
            },
            "accG": {
                "lateral": _safe_float(sample.accelX),
                "longitudinal": _safe_float(sample.accelZ),
                "vertical": _safe_float(sample.accelY),
            },
        },
        "controls": {
            "throttle": _safe_float(sample.throttle),
            "brake": _safe_float(sample.brake),
            "clutch": _safe_float(sample.clutch),
            "steerAngle": _safe_float(sample.steering),
            "gear": _safe_float(sample.gear),
            "rpm": _safe_float(sample.rpm),
        },
        "tyres": {
            "tyreCoreTemperature": tyre_temp,
            "tyrePressure": tyre_pressure,
            "tyreWear": tyre_wear,
            "tyreDirtyLevel": tyre_dirty,
            "wheelSlip": wheel_slip,
            "wheelLoad": wheel_load,
            "estimatedGripIndex": [grip_index] * 4 if grip_index is not None else [None, None, None, None],
        },
        "suspension": {
            "suspensionTravel": suspension_travel,
            "rideHeight": ride_height,
            "camberRad": camber,
        },
        "carState": {
            "fuel": _safe_float(sample.fuel),
            "maxFuel": _safe_float(sample.maxFuel),
            "ballast": _safe_float(sample.ballast),
            "carDamage": car_damage,
            "abs": _safe_float(sample.abs),
            "tc": _safe_float(sample.tc),
            "drs": _safe_bool(sample.drs),
            "turboBoost": _safe_float(sample.turboBoost),
        },
        "environment": {
            "airTemp": _safe_float(sample.airTemp),
            "roadTemp": _safe_float(sample.roadTemp),
            "surfaceGrip": surface_grip,
            "airDensity": _safe_float(sample.airDensity),
            # The simulator's track-limits verdict, the ground truth the
            # reconstructed limit gets scored against.
            "tyresOut": sample.tyresOut,
            "offTrack": sample.offTrack,
            "penaltyTime": _safe_float(sample.penaltyTime),
        },
        "inferred": {
            "estimatedAccelerationState": acceleration_state,
            "estimatedGripLevel": infer_grip_level(grip_index),
            "estimatedMassKg": None,
            "estimatedDragState": "UNKNOWN",
        },
        "availability": {
            "hasRealThrottle": _safe_float(sample.throttle) is not None,
            "hasRealBrake": _safe_float(sample.brake) is not None,
            "hasRealTyreData": any(
                _has_any_real(values)
                for values in (tyre_temp, tyre_pressure, tyre_wear, tyre_dirty, wheel_slip, wheel_load)
            ),
            "hasRealSuspensionData": _has_any_real(suspension_travel) or _has_any_real(ride_height) or _has_any_real(camber),
            "hasRealEnvironmentData": any(
                value is not None
                for value in (sample.airTemp, sample.roadTemp, sample.surfaceGrip, sample.airDensity)
            ),
            "hasInferredGrip": grip_index is not None,
            "hasInferredAccelerationState": acceleration_state != "UNKNOWN",
        },
    }
    telemetry["source"]["dataCompleteness"] = infer_data_completeness(telemetry)
    return telemetry


def build_opponent_car_physics(
    opponent: OpponentCarState,
    recent_samples: Optional[Sequence[OpponentCarState]] = None,
) -> Dict[str, Any]:
    base = _base_unavailable_physics()
    speed = _safe_float(opponent.speedKmh)
    acceleration_state = infer_acceleration_state(recent_samples or [opponent])
    telemetry = {
        "source": {
            "playerPhysicsAvailable": False,
            "opponentPhysicsAvailable": True,
            "dataCompleteness": "MINIMAL",
        },
        **base,
        "motion": {
            **base["motion"],
            "speedKmh": speed,
        },
        "inferred": {
            "estimatedAccelerationState": acceleration_state,
            "estimatedGripLevel": "UNKNOWN",
            "estimatedMassKg": None,
            "estimatedDragState": "UNKNOWN",
        },
        "availability": {
            "hasRealThrottle": False,
            "hasRealBrake": False,
            "hasRealTyreData": False,
            "hasRealSuspensionData": False,
            "hasRealEnvironmentData": False,
            "hasInferredGrip": False,
            "hasInferredAccelerationState": acceleration_state != "UNKNOWN",
        },
    }
    return telemetry


@dataclass(frozen=True)
class CarPhysicsDebug:
    playerPhysicsSamples: int
    opponentPhysicsSamples: int
    playerDataCompleteness: DataCompleteness
    opponentDataCompleteness: DataCompleteness
    missingPlayerFields: List[str]
    missingOpponentFields: List[str]
    inferredFields: List[str]
    unavailableFields: List[str]

    def to_api(self) -> Dict[str, Any]:
        return {
            "playerPhysicsSamples": self.playerPhysicsSamples,
            "opponentPhysicsSamples": self.opponentPhysicsSamples,
            "playerDataCompleteness": self.playerDataCompleteness,
            "opponentDataCompleteness": self.opponentDataCompleteness,
            "missingPlayerFields": self.missingPlayerFields,
            "missingOpponentFields": self.missingOpponentFields,
            "inferredFields": self.inferredFields,
            "unavailableFields": self.unavailableFields,
        }


def build_car_physics_debug(
    player_physics: Mapping[str, Any],
    opponent_physics: Sequence[Mapping[str, Any]],
    *,
    player_sample_count: int,
    opponent_sample_count: int,
) -> Dict[str, Any]:
    opponent_completeness = "MINIMAL"
    if opponent_physics:
        levels = [item.get("source", {}).get("dataCompleteness", "MINIMAL") for item in opponent_physics]
        opponent_completeness = "FULL" if "FULL" in levels else ("PARTIAL" if "PARTIAL" in levels else "MINIMAL")

    inferred_fields = []
    unavailable_fields = []
    for prefix, physics in [("player", player_physics), *[(f"opponent.{index}", item) for index, item in enumerate(opponent_physics)]]:
        inferred = physics.get("inferred", {}) if isinstance(physics, Mapping) else {}
        if isinstance(inferred, Mapping):
            for key, value in inferred.items():
                if value not in (None, "UNKNOWN"):
                    inferred_fields.append(f"{prefix}.inferred.{key}")
        for field in _missing_fields(physics):
            unavailable_fields.append(f"{prefix}.{field}")

    debug = CarPhysicsDebug(
        playerPhysicsSamples=player_sample_count,
        opponentPhysicsSamples=opponent_sample_count,
        playerDataCompleteness=player_physics.get("source", {}).get("dataCompleteness", "MINIMAL"),
        opponentDataCompleteness=opponent_completeness,
        missingPlayerFields=_missing_fields(player_physics),
        missingOpponentFields=sorted(
            {
                field
                for physics in opponent_physics
                for field in _missing_fields(physics)
            }
        ),
        inferredFields=sorted(set(inferred_fields)),
        unavailableFields=sorted(set(unavailable_fields)),
    )
    return debug.to_api()
