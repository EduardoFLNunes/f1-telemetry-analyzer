from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class TrackCalibrationProfile:
    profileId: str
    trackName: str
    minValidLapSeconds: float
    maxValidLapSeconds: float
    minSamplesPerLap: int
    minSplineCoveragePercent: float
    maxAllowedGapMs: float
    notes: str

    def to_api(self) -> Dict[str, object]:
        return asdict(self)


DEFAULT_PROFILE = TrackCalibrationProfile(
    profileId="default",
    trackName="default",
    minValidLapSeconds=10.0,
    maxValidLapSeconds=1800.0,
    minSamplesPerLap=40,
    minSplineCoveragePercent=65.0,
    maxAllowedGapMs=2500.0,
    notes="Conservative fallback for tracks without a dedicated calibration.",
)

INTERLAGOS_PROFILE = TrackCalibrationProfile(
    profileId="interlagos",
    trackName="interlagos",
    minValidLapSeconds=45.0,
    maxValidLapSeconds=300.0,
    minSamplesPerLap=40,
    minSplineCoveragePercent=80.0,
    maxAllowedGapMs=1500.0,
    notes="Broad initial limits. TODO calibrate with additional real Interlagos sessions.",
)


def calibration_for_track(track_name: Optional[str]) -> TrackCalibrationProfile:
    normalized = (track_name or "").strip().lower()
    if "interlagos" in normalized:
        return INTERLAGOS_PROFILE
    return DEFAULT_PROFILE
