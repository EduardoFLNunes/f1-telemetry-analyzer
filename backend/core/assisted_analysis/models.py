from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


PHASE_ENTRY = "entry"
PHASE_BRAKING = "braking_zone"
PHASE_APEX = "apex"
PHASE_EXIT = "exit"
PHASE_STRAIGHT_AFTER = "straight_after"


@dataclass
class LapDescriptor:
    lap_id: str
    source: str
    driver_id: str
    lap_number: int
    track: Optional[str] = None
    lap_time: Optional[float] = None
    sample_count: int = 0
    session_id: Optional[str] = None
    parquet_path: Optional[str] = None
    started_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_api(self) -> Dict[str, Any]:
        return {
            "lapId": self.lap_id,
            "source": self.source,
            "driverId": self.driver_id,
            "lapNumber": self.lap_number,
            "track": self.track,
            "lapTime": self.lap_time,
            "sampleCount": self.sample_count,
            "sessionId": self.session_id,
            "parquetPath": self.parquet_path,
            "startedAt": self.started_at,
            "metadata": self.metadata,
        }


@dataclass
class PhaseBounds:
    start_s: float
    end_s: float

    def to_api(self) -> Dict[str, float]:
        return {"startS": float(self.start_s), "endS": float(self.end_s)}


@dataclass
class CornerSegment:
    corner_id: int
    start_s: float
    end_s: float
    apex_s: float
    curvature_peak: float
    phases: Dict[str, PhaseBounds]
    name: Optional[str] = None

    def to_api(self) -> Dict[str, Any]:
        return {
            "cornerId": self.corner_id,
            "name": self.name or f"T{self.corner_id}",
            "startS": float(self.start_s),
            "endS": float(self.end_s),
            "apexS": float(self.apex_s),
            "curvaturePeak": float(self.curvature_peak),
            "phases": {key: value.to_api() for key, value in self.phases.items()},
        }


@dataclass
class CornerMetrics:
    corner_id: int
    segment_time: Optional[float]
    entry_speed_kmh: Optional[float]
    min_speed_kmh: Optional[float]
    exit_speed_kmh: Optional[float]
    apex_s: Optional[float]
    brake_start_s: Optional[float]
    brake_peak: Optional[float]
    brake_release_s: Optional[float]
    throttle_pickup_s: Optional[float]
    full_throttle_s: Optional[float]
    coasting_distance_m: float
    mean_abs_lateral_offset_m: Optional[float]
    max_abs_lateral_offset_m: Optional[float]
    mean_line_deviation_m: Optional[float]
    phase_line_deviation_m: Dict[str, Optional[float]] = field(default_factory=dict)
    optional_channels: Dict[str, bool] = field(default_factory=dict)

    def to_api(self) -> Dict[str, Any]:
        return {
            "cornerId": self.corner_id,
            "segmentTime": self.segment_time,
            "entrySpeedKmh": self.entry_speed_kmh,
            "minSpeedKmh": self.min_speed_kmh,
            "exitSpeedKmh": self.exit_speed_kmh,
            "apexS": self.apex_s,
            "brakeStartS": self.brake_start_s,
            "brakePeak": self.brake_peak,
            "brakeReleaseS": self.brake_release_s,
            "throttlePickupS": self.throttle_pickup_s,
            "fullThrottleS": self.full_throttle_s,
            "coastingDistanceM": self.coasting_distance_m,
            "meanAbsLateralOffsetM": self.mean_abs_lateral_offset_m,
            "maxAbsLateralOffsetM": self.max_abs_lateral_offset_m,
            "meanLineDeviationM": self.mean_line_deviation_m,
            "phaseLineDeviationM": self.phase_line_deviation_m,
            "optionalChannels": self.optional_channels,
        }


@dataclass
class CornerComparison:
    corner_id: int
    segment_time_delta_s: Optional[float]
    entry_speed_delta_kmh: Optional[float]
    min_speed_delta_kmh: Optional[float]
    exit_speed_delta_kmh: Optional[float]
    brake_start_delta_m: Optional[float]
    brake_release_delta_m: Optional[float]
    apex_delta_m: Optional[float]
    throttle_pickup_delta_m: Optional[float]
    full_throttle_delta_m: Optional[float]
    coasting_delta_m: Optional[float]
    lateral_offset_delta_m: Optional[float]
    line_deviation_delta_m: Optional[float]
    phase_line_deviation_delta_m: Dict[str, Optional[float]] = field(default_factory=dict)

    def estimated_gain(self) -> float:
        if self.segment_time_delta_s is None:
            return 0.0
        return max(0.0, float(self.segment_time_delta_s))

    def to_api(self) -> Dict[str, Any]:
        return {
            "cornerId": self.corner_id,
            "segmentTimeDeltaS": self.segment_time_delta_s,
            "entrySpeedDeltaKmh": self.entry_speed_delta_kmh,
            "minSpeedDeltaKmh": self.min_speed_delta_kmh,
            "exitSpeedDeltaKmh": self.exit_speed_delta_kmh,
            "brakeStartDeltaM": self.brake_start_delta_m,
            "brakeReleaseDeltaM": self.brake_release_delta_m,
            "apexDeltaM": self.apex_delta_m,
            "throttlePickupDeltaM": self.throttle_pickup_delta_m,
            "fullThrottleDeltaM": self.full_throttle_delta_m,
            "coastingDeltaM": self.coasting_delta_m,
            "lateralOffsetDeltaM": self.lateral_offset_delta_m,
            "lineDeviationDeltaM": self.line_deviation_delta_m,
            "phaseLineDeviationDeltaM": self.phase_line_deviation_delta_m,
            "estimatedGainS": self.estimated_gain(),
        }


@dataclass
class DrivingError:
    code: str
    label: str
    phase: str
    severity: float
    estimated_gain_s: float
    description: str
    evidence: Dict[str, Any]
    concept: Optional[str] = None
    technique: Optional[str] = None
    physical_behavior: Optional[str] = None
    expected_telemetry: List[str] = field(default_factory=list)
    feedback: Optional[str] = None

    def to_api(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "phase": self.phase,
            "severity": float(max(0.0, min(1.0, self.severity))),
            "estimatedGainS": float(max(0.0, self.estimated_gain_s)),
            "description": self.description,
            "concept": self.concept,
            "technique": self.technique,
            "physicalBehavior": self.physical_behavior,
            "expectedTelemetry": self.expected_telemetry,
            "evidence": self.evidence,
            "feedback": self.feedback or self.description,
        }


@dataclass
class DrivingKnowledgeConcept:
    code: str
    label: str
    physical_concept: str
    driving_technique: str
    expected_telemetry: List[str]
    likely_error: str
    evidence_keys: List[str]
    feedback_hint: str

    def to_api(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "physicalConcept": self.physical_concept,
            "drivingTechnique": self.driving_technique,
            "expectedTelemetry": self.expected_telemetry,
            "likelyError": self.likely_error,
            "evidenceKeys": self.evidence_keys,
            "feedbackHint": self.feedback_hint,
        }


@dataclass
class PhaseDynamics:
    phase: str
    max_lateral_g: Optional[float] = None
    max_longitudinal_g: Optional[float] = None
    min_longitudinal_g: Optional[float] = None
    max_yaw_rate: Optional[float] = None
    mean_abs_yaw_rate: Optional[float] = None
    max_steering_rate: Optional[float] = None
    mean_abs_steering: Optional[float] = None
    brake_release_rate: Optional[float] = None
    throttle_application_rate: Optional[float] = None
    trajectory_curvature_peak: Optional[float] = None
    friction_usage_peak: Optional[float] = None
    reference_line_deviation_m: Optional[float] = None
    stability_score: Optional[float] = None

    def to_api(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "maxLateralG": self.max_lateral_g,
            "maxLongitudinalG": self.max_longitudinal_g,
            "minLongitudinalG": self.min_longitudinal_g,
            "maxYawRate": self.max_yaw_rate,
            "meanAbsYawRate": self.mean_abs_yaw_rate,
            "maxSteeringRate": self.max_steering_rate,
            "meanAbsSteering": self.mean_abs_steering,
            "brakeReleaseRate": self.brake_release_rate,
            "throttleApplicationRate": self.throttle_application_rate,
            "trajectoryCurvaturePeak": self.trajectory_curvature_peak,
            "frictionUsagePeak": self.friction_usage_peak,
            "referenceLineDeviationM": self.reference_line_deviation_m,
            "stabilityScore": self.stability_score,
        }


@dataclass
class VehicleDynamicsProfile:
    corner_id: int
    phases: Dict[str, PhaseDynamics]
    derived_channels: Dict[str, bool]
    summary: Dict[str, Optional[float]]

    def to_api(self) -> Dict[str, Any]:
        return {
            "cornerId": self.corner_id,
            "phases": {phase: dynamics.to_api() for phase, dynamics in self.phases.items()},
            "derivedChannels": self.derived_channels,
            "summary": self.summary,
        }


@dataclass
class TechniqueFinding:
    code: str
    phase: str
    severity: float
    evidence: Dict[str, Any]
    physical_behavior: str

    def to_api(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "phase": self.phase,
            "severity": self.severity,
            "evidence": self.evidence,
            "physicalBehavior": self.physical_behavior,
        }
