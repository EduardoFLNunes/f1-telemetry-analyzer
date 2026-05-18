from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from ..telemetry.telemetry_models import TelemetrySample


class TrackBuildState(str, Enum):
    NO_TRACK = "NO_TRACK"
    COLLECTING_LAP = "COLLECTING_LAP"
    TRACK_READY = "TRACK_READY"
    TRACK_INVALID = "TRACK_INVALID"


@dataclass
class LapValidationResult:
    valid: bool
    reason: str = ""
    distance: float = 0.0
    bounds: Optional[Tuple[float, float, float, float]] = None


@dataclass
class LapCollector:
    min_samples: int = 300
    min_distance: float = 1000.0
    wrap_high: float = 0.95
    wrap_low: float = 0.10
    max_live_trajectory: int = 2400
    candidate_lap_samples: List[TelemetrySample] = field(default_factory=list)
    live_trajectory: List[TelemetrySample] = field(default_factory=list)
    completed_lap_samples: List[TelemetrySample] = field(default_factory=list)
    lap_complete: bool = False
    last_normalized_spline_position: Optional[float] = None
    invalid_reason: str = ""

    def reset(self):
        self.candidate_lap_samples = []
        self.live_trajectory = []
        self.completed_lap_samples = []
        self.lap_complete = False
        self.last_normalized_spline_position = None
        self.invalid_reason = ""

    def add_sample(self, sample: TelemetrySample) -> bool:
        self.live_trajectory.append(sample)
        if len(self.live_trajectory) > self.max_live_trajectory:
            self.live_trajectory = self.live_trajectory[-self.max_live_trajectory:]

        current = self._normalized_position(sample)
        previous = self.last_normalized_spline_position
        self.last_normalized_spline_position = current

        if previous is None:
            self.candidate_lap_samples = [sample]
            return False

        wrapped = previous >= self.wrap_high and current <= self.wrap_low
        if wrapped and len(self.candidate_lap_samples) >= self.min_samples:
            self.completed_lap_samples = list(self.candidate_lap_samples)
            self.candidate_lap_samples = [sample]
            self.lap_complete = True
            return True

        if wrapped:
            self.candidate_lap_samples = [sample]
            return False

        self.candidate_lap_samples.append(sample)
        return False

    def validate_completed_lap(self, expected_length: Optional[float] = None) -> LapValidationResult:
        samples = self.completed_lap_samples
        if len(samples) < self.min_samples:
            return LapValidationResult(False, f"not enough samples: {len(samples)}")

        points = np.array([[s.worldPositionX, s.worldPositionZ] for s in samples], dtype=float)
        if not np.isfinite(points).all():
            return LapValidationResult(False, "non-finite coordinates")

        diffs = np.diff(points, axis=0)
        distance = float(np.linalg.norm(diffs, axis=1).sum())
        min_x, min_z = points.min(axis=0)
        max_x, max_z = points.max(axis=0)
        bounds = (float(min_x), float(min_z), float(max_x), float(max_z))

        min_distance = self.min_distance
        if expected_length and expected_length > 1000.0:
            min_distance = max(min_distance, expected_length * 0.70)
            max_distance = expected_length * 1.35
            if distance > max_distance:
                return LapValidationResult(False, f"lap distance too long: {distance:.1f}m", distance, bounds)

        if distance < min_distance:
            return LapValidationResult(False, f"lap distance too short: {distance:.1f}m", distance, bounds)

        if max_x - min_x < 100.0 or max_z - min_z < 100.0:
            return LapValidationResult(False, "lap bounds too small", distance, bounds)

        return LapValidationResult(True, "", distance, bounds)

    def live_trajectory_api(self, stride: int = 3) -> List[dict]:
        samples = self.live_trajectory[::max(1, stride)]
        return [
            {
                "x": float(sample.worldPositionX),
                "y": float(-sample.worldPositionZ),
                "worldPosition": sample.worldPosition,
                "spline_t": float(sample.normalizedSplinePosition),
                "timestamp": sample.timestamp,
            }
            for sample in samples
        ]

    @staticmethod
    def _normalized_position(sample: TelemetrySample) -> float:
        value = float(sample.normalizedSplinePosition or 0.0)
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return value % 1.0
        return value
