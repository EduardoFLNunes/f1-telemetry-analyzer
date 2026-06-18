from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SOURCE_FASTF1 = "FASTF1"
REFERENCE_TYPE_EXTERNAL_F1 = "EXTERNAL_F1"
CALIBRATION_UNCALIBRATED = "UNCALIBRATED"
CALIBRATION_CALIBRATED = "CALIBRATED"
COMPARABLE_LIMITED = "LIMITED"


class ExternalReferenceError(ValueError):
    pass


@dataclass
class ExternalReferenceSample:
    progress: float
    distance_m: float
    elapsed_s: float
    speed_kmh: Optional[float] = None
    throttle: Optional[float] = None
    brake: Optional[float] = None
    rpm: Optional[float] = None
    gear: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None

    def to_api(self) -> Dict[str, Any]:
        return {
            "progress": self.progress,
            "distanceM": self.distance_m,
            "elapsedS": self.elapsed_s,
            "speedKmh": self.speed_kmh,
            "throttle": self.throttle,
            "brake": self.brake,
            "rpm": self.rpm,
            "gear": self.gear,
            "x": self.x,
            "y": self.y,
        }

    @classmethod
    def from_api(cls, payload: Dict[str, Any]) -> "ExternalReferenceSample":
        return cls(
            progress=float(payload.get("progress") or 0.0),
            distance_m=float(payload.get("distanceM") or payload.get("distance_m") or 0.0),
            elapsed_s=float(payload.get("elapsedS") or payload.get("elapsed_s") or 0.0),
            speed_kmh=_optional_float(payload.get("speedKmh", payload.get("speed_kmh"))),
            throttle=_optional_float(payload.get("throttle")),
            brake=_optional_float(payload.get("brake")),
            rpm=_optional_float(payload.get("rpm")),
            gear=_optional_int(payload.get("gear")),
            x=_optional_float(payload.get("x")),
            y=_optional_float(payload.get("y")),
        )


@dataclass
class ExternalReferenceMetadata:
    reference_id: str
    source: str = SOURCE_FASTF1
    reference_type: str = REFERENCE_TYPE_EXTERNAL_F1
    calibration_status: str = CALIBRATION_UNCALIBRATED
    comparable_to_assetto: str = COMPARABLE_LIMITED
    year: Optional[int] = None
    event: Optional[str] = None
    session: Optional[str] = None
    driver: Optional[str] = None
    team: Optional[str] = None
    lap_number: Optional[int] = None
    lap_time: Optional[float] = None
    track: Optional[str] = None
    imported_at: Optional[str] = None
    sample_count: int = 0
    cache_path: Optional[str] = None
    provider_notes: List[str] = field(default_factory=list)

    def to_api(self) -> Dict[str, Any]:
        return {
            "referenceId": self.reference_id,
            "source": self.source,
            "referenceType": self.reference_type,
            "calibrationStatus": self.calibration_status,
            "comparableToAssetto": self.comparable_to_assetto,
            "year": self.year,
            "event": self.event,
            "session": self.session,
            "driver": self.driver,
            "team": self.team,
            "lapNumber": self.lap_number,
            "lapTime": self.lap_time,
            "track": self.track,
            "importedAt": self.imported_at,
            "sampleCount": self.sample_count,
            "cachePath": self.cache_path,
            "providerNotes": list(self.provider_notes),
        }

    @classmethod
    def from_api(cls, payload: Dict[str, Any]) -> "ExternalReferenceMetadata":
        return cls(
            reference_id=str(payload.get("referenceId") or payload.get("reference_id")),
            source=str(payload.get("source") or SOURCE_FASTF1),
            reference_type=str(payload.get("referenceType") or payload.get("reference_type") or REFERENCE_TYPE_EXTERNAL_F1),
            calibration_status=str(payload.get("calibrationStatus") or payload.get("calibration_status") or CALIBRATION_UNCALIBRATED),
            comparable_to_assetto=str(payload.get("comparableToAssetto") or payload.get("comparable_to_assetto") or COMPARABLE_LIMITED),
            year=_optional_int(payload.get("year")),
            event=_optional_str(payload.get("event")),
            session=_optional_str(payload.get("session")),
            driver=_optional_str(payload.get("driver")),
            team=_optional_str(payload.get("team")),
            lap_number=_optional_int(payload.get("lapNumber", payload.get("lap_number"))),
            lap_time=_optional_float(payload.get("lapTime", payload.get("lap_time"))),
            track=_optional_str(payload.get("track")),
            imported_at=_optional_str(payload.get("importedAt", payload.get("imported_at"))),
            sample_count=int(payload.get("sampleCount") or payload.get("sample_count") or 0),
            cache_path=_optional_str(payload.get("cachePath", payload.get("cache_path"))),
            provider_notes=list(payload.get("providerNotes") or payload.get("provider_notes") or []),
        )


@dataclass
class ExternalReferenceLap:
    metadata: ExternalReferenceMetadata
    samples: List[ExternalReferenceSample]

    def to_api(self, *, include_samples: bool = True) -> Dict[str, Any]:
        payload = {
            "metadata": self.metadata.to_api(),
            "sampleCount": len(self.samples),
        }
        if include_samples:
            payload["samples"] = [sample.to_api() for sample in self.samples]
        return payload

    @classmethod
    def from_api(cls, payload: Dict[str, Any]) -> "ExternalReferenceLap":
        metadata = ExternalReferenceMetadata.from_api(payload.get("metadata") or payload)
        samples = [
            ExternalReferenceSample.from_api(sample)
            for sample in payload.get("samples", [])
            if isinstance(sample, dict)
        ]
        metadata.sample_count = len(samples) or metadata.sample_count
        return cls(metadata=metadata, samples=samples)


def _optional_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
