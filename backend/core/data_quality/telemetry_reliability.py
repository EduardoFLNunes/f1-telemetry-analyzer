import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Deque, Dict, Optional

from ..telemetry.telemetry_models import TelemetrySample


logger = logging.getLogger(__name__)


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _valid_timestamp(value: Any) -> bool:
    if _finite(value):
        return float(value) >= 0.0
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _complete_wheel_values(values) -> bool:
    return isinstance(values, (list, tuple)) and len(values) >= 4 and all(
        value is not None and _finite(value) for value in values[:4]
    )


@dataclass(frozen=True)
class SampleValidationResult:
    status: str
    issues: tuple
    hasPhysics: bool
    hasTyres: bool
    hasFuel: bool
    hasSuspension: bool
    hasPosition: bool
    hasSpline: bool

    def to_api(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "issues": list(self.issues),
            "hasPhysics": self.hasPhysics,
            "hasTyres": self.hasTyres,
            "hasFuel": self.hasFuel,
            "hasSuspension": self.hasSuspension,
            "hasPosition": self.hasPosition,
            "hasSpline": self.hasSpline,
        }


def validate_telemetry_sample(sample: Optional[TelemetrySample]) -> SampleValidationResult:
    if sample is None:
        return SampleValidationResult(
            status="INVALID",
            issues=("sample is missing",),
            hasPhysics=False,
            hasTyres=False,
            hasFuel=False,
            hasSuspension=False,
            hasPosition=False,
            hasSpline=False,
        )

    invalid = []
    partial = []
    has_position = all(
        _finite(value)
        for value in (sample.worldPositionX, sample.worldPositionY, sample.worldPositionZ)
    )
    if not has_position:
        invalid.append("position contains a non-finite value")

    if not _valid_timestamp(sample.timestamp):
        invalid.append("timestamp is invalid")
    if not _finite(sample.speed) or float(sample.speed) < -1.0 or float(sample.speed) > 700.0:
        invalid.append("speed is outside the valid range")

    has_spline = _finite(sample.normalizedSplinePosition) and (
        0.0 <= float(sample.normalizedSplinePosition) <= 1.0
    )
    if not has_spline:
        invalid.append("splinePosition must be between 0 and 1")
    if not isinstance(sample.lap, int) or sample.lap < 0:
        invalid.append("lapNumber is invalid")
    if not _finite(sample.sessionTime) or float(sample.sessionTime) < 0.0:
        invalid.append("sessionTime is invalid")
    if sample.lapTime is None:
        partial.append("lapTime is unavailable")
    elif not _finite(sample.lapTime) or float(sample.lapTime) < 0.0:
        invalid.append("lapTime is invalid")

    velocity_present = any(
        value is not None and _finite(value)
        for value in (sample.velocityX, sample.velocityY, sample.velocityZ)
    )
    acceleration_present = any(
        _finite(value) and abs(float(value)) > 1e-6
        for value in (sample.accelX, sample.accelY, sample.accelZ)
    )
    has_physics = velocity_present or acceleration_present or int(sample.rpm or 0) > 0
    has_tyres = any(
        _complete_wheel_values(values)
        for values in (
            sample.tyreCoreTemperature,
            sample.tyrePressure,
            sample.tyreWear,
            sample.wheelLoad,
        )
    )
    has_fuel = sample.fuel is not None and _finite(sample.fuel)
    has_suspension = _complete_wheel_values(sample.suspensionTravel) or _complete_wheel_values(
        sample.rideHeight
    )

    for present, issue in (
        (has_physics, "physics channels are incomplete"),
        (has_tyres, "tyre channels are incomplete"),
        (has_fuel, "fuel channel is unavailable"),
        (has_suspension, "suspension channels are incomplete"),
    ):
        if not present:
            partial.append(issue)

    status = "INVALID" if invalid else "PARTIAL" if partial else "VALID"
    return SampleValidationResult(
        status=status,
        issues=tuple(invalid + partial),
        hasPhysics=has_physics,
        hasTyres=has_tyres,
        hasFuel=has_fuel,
        hasSuspension=has_suspension,
        hasPosition=has_position,
        hasSpline=has_spline,
    )


class TelemetryReliabilityMonitor:
    def __init__(
        self,
        target_hz: float = 60.0,
        live_window_seconds: float = 5.0,
        stability_window_seconds: float = 30.0,
        stale_after_seconds: float = 5.0,
        time_provider: Callable[[], float] = time.time,
    ):
        self.target_hz = float(target_hz)
        self.live_window_seconds = float(live_window_seconds)
        self.stability_window_seconds = float(stability_window_seconds)
        self.stale_after_seconds = float(stale_after_seconds)
        self._time = time_provider
        self._arrivals: Deque[float] = deque()
        self._sample_count = 0
        self._valid_count = 0
        self._partial_count = 0
        self._invalid_count = 0
        self._last_sample_at: Optional[float] = None
        self._last_validation: Optional[SampleValidationResult] = None
        self._last_frequency_warning_at = 0.0
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self._arrivals.clear()
            self._sample_count = 0
            self._valid_count = 0
            self._partial_count = 0
            self._invalid_count = 0
            self._last_sample_at = None
            self._last_validation = None
            self._last_frequency_warning_at = 0.0

    def observe(
        self,
        sample: TelemetrySample,
        received_at: Optional[float] = None,
    ) -> SampleValidationResult:
        now = float(self._time() if received_at is None else received_at)
        validation = validate_telemetry_sample(sample)
        with self._lock:
            self._sample_count += 1
            self._arrivals.append(now)
            self._last_sample_at = now
            self._last_validation = validation
            if validation.status == "VALID":
                self._valid_count += 1
            elif validation.status == "PARTIAL":
                self._partial_count += 1
            else:
                self._invalid_count += 1
            self._prune_locked(now)
        return validation

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        current = float(self._time() if now is None else now)
        with self._lock:
            self._prune_locked(current)
            last_sample_at = self._last_sample_at
            age = None if last_sample_at is None else max(0.0, current - last_sample_at)
            if last_sample_at is None:
                stream_status = "waiting"
            elif age is not None and age > self.stale_after_seconds:
                stream_status = "stale"
            else:
                stream_status = "receiving"

            estimated_hz = self._frequency_locked(current, self.live_window_seconds)
            stable_hz = self._frequency_locked(current, self.stability_window_seconds)
            frequency_status = self._frequency_status(stream_status, estimated_hz)
            dropped = self._dropped_estimate_locked(current)
            validation = self._last_validation
            result = {
                "source": "shared_memory",
                "status": stream_status,
                "frequencyStatus": frequency_status,
                "targetHz": self.target_hz,
                "estimatedHz": estimated_hz,
                "stableHz": stable_hz,
                "sampleCount": self._sample_count,
                "droppedSamplesEstimate": dropped,
                "lastSampleAtEpoch": last_sample_at,
                "secondsSinceLastSample": round(age, 3) if age is not None else None,
                "validSampleCount": self._valid_count,
                "partialSampleCount": self._partial_count,
                "invalidSampleCount": self._invalid_count,
                "hasPhysics": bool(validation and validation.hasPhysics),
                "hasTyres": bool(validation and validation.hasTyres),
                "hasFuel": bool(validation and validation.hasFuel),
                "hasSuspension": bool(validation and validation.hasSuspension),
                "hasPosition": bool(validation and validation.hasPosition),
                "hasSpline": bool(validation and validation.hasSpline),
                "latestSampleValidation": validation.to_api() if validation else None,
            }
            self._maybe_log_frequency_locked(current, result)
            return result

    def _prune_locked(self, now: float):
        cutoff = now - self.stability_window_seconds
        while self._arrivals and self._arrivals[0] < cutoff:
            self._arrivals.popleft()

    def _frequency_locked(self, now: float, window_seconds: float) -> Optional[float]:
        cutoff = now - window_seconds
        timestamps = [timestamp for timestamp in self._arrivals if timestamp >= cutoff]
        if len(timestamps) < 2:
            return None
        duration = min(window_seconds, max(now - timestamps[0], timestamps[-1] - timestamps[0]))
        if duration < 1.0:
            return None
        return round(len(timestamps) / duration, 2)

    def _dropped_estimate_locked(self, now: float) -> Optional[int]:
        cutoff = now - self.live_window_seconds
        timestamps = [timestamp for timestamp in self._arrivals if timestamp >= cutoff]
        if len(timestamps) < 2:
            return None
        duration = min(self.live_window_seconds, max(now - timestamps[0], 0.0))
        if duration < 1.0:
            return None
        expected = self.target_hz * duration
        return max(0, int(round(expected - len(timestamps))))

    @staticmethod
    def _frequency_status(stream_status: str, estimated_hz: Optional[float]) -> str:
        if stream_status != "receiving" or estimated_hz is None:
            return "UNKNOWN"
        if estimated_hz >= 50.0:
            return "OK"
        if estimated_hz >= 30.0:
            return "WARNING"
        return "ERROR"

    def _maybe_log_frequency_locked(self, now: float, snapshot: Dict[str, Any]):
        if snapshot["frequencyStatus"] != "ERROR":
            return
        if now - self._last_frequency_warning_at < 30.0:
            return
        self._last_frequency_warning_at = now
        logger.warning(
            "Player telemetry frequency severely low: estimatedHz=%s targetHz=%s",
            snapshot["estimatedHz"],
            self.target_hz,
        )
