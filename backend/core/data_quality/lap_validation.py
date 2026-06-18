import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _sample_value(sample: Mapping[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _number(sample.get(key))
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class LapValidationResult:
    lapId: str
    lapNumber: Optional[int]
    status: str
    sampleCount: int
    durationSeconds: Optional[float]
    coveragePercent: Optional[float]
    issues: tuple

    def to_api(self) -> Dict[str, Any]:
        return {
            "lapId": self.lapId,
            "lapNumber": self.lapNumber,
            "status": self.status,
            "sampleCount": self.sampleCount,
            "durationSeconds": (
                round(self.durationSeconds, 3)
                if self.durationSeconds is not None
                else None
            ),
            "coveragePercent": (
                round(self.coveragePercent, 2)
                if self.coveragePercent is not None
                else None
            ),
            "issues": list(self.issues),
        }


def validate_lap(
    lap: Mapping[str, Any],
    *,
    min_samples: int = 40,
    min_duration_seconds: float = 10.0,
    max_duration_seconds: float = 1800.0,
    min_coverage_percent: float = 65.0,
    max_gap_seconds: float = 2.5,
) -> LapValidationResult:
    samples = lap.get("samples")
    sample_rows: Sequence[Mapping[str, Any]] = (
        [sample for sample in samples if isinstance(sample, Mapping)]
        if isinstance(samples, Sequence) and not isinstance(samples, (str, bytes))
        else []
    )
    sample_count = int(lap.get("sampleCount") or len(sample_rows))
    lap_number_value = _number(lap.get("lapNumber", lap.get("lap_number")))
    lap_number = int(lap_number_value) if lap_number_value is not None else None
    lap_id = str(
        lap.get("lapId")
        or f"{lap.get('sessionId') or 'live'}:{lap_number if lap_number is not None else 'unknown'}"
    )
    completed = bool(lap.get("completed", True))

    duration = _number(lap.get("durationSeconds", lap.get("duration")))
    progress_start = _number(lap.get("progressStart"))
    progress_end = _number(lap.get("progressEnd"))
    progress_min = _number(lap.get("progressMin"))
    progress_max = _number(lap.get("progressMax"))
    timestamp_inversions = int(lap.get("timestampInversions") or 0)
    largest_gap = _number(lap.get("maxGapSeconds"))

    if sample_rows:
        times = []
        progress = []
        for sample in sample_rows:
            timestamp = _sample_value(sample, "sessionTime", "session_time", "timestamp")
            if timestamp is not None:
                if timestamp > 100_000_000_000.0:
                    timestamp /= 1000.0
                times.append(timestamp)
            value = _sample_value(
                sample,
                "lapProgress",
                "p",
                "spline_t",
                "normalizedSplinePosition",
                "splinePosition",
            )
            if value is not None:
                progress.append(max(0.0, min(1.0, value)))
        if len(times) >= 2:
            deltas = [right - left for left, right in zip(times, times[1:])]
            timestamp_inversions = sum(1 for delta in deltas if delta < -1e-3)
            non_negative = [delta for delta in deltas if delta >= 0.0]
            largest_gap = max(non_negative, default=0.0)
            duration = max(times) - min(times)
        if progress:
            progress_start = progress[0]
            progress_end = progress[-1]
            progress_min = min(progress)
            progress_max = max(progress)

    coverage = _number(lap.get("coveragePercent"))
    if coverage is None and progress_min is not None and progress_max is not None:
        coverage = max(0.0, min(100.0, (progress_max - progress_min) * 100.0))
    wrapped_complete_lap = (
        completed
        and coverage is not None
        and coverage >= 98.0
        and progress_min is not None
        and progress_min <= 0.02
        and progress_max is not None
        and progress_max >= 0.98
        and progress_start is not None
        and progress_start <= 0.05
        and progress_end is not None
        and progress_end <= 0.05
    )

    invalid = []
    partial = []
    if lap_number is None or lap_number < 0:
        invalid.append("lap number is invalid")
    if timestamp_inversions > 0:
        invalid.append(f"{timestamp_inversions} timestamp inversion(s) detected")
    if largest_gap is not None and largest_gap > max_gap_seconds:
        invalid.append(f"sample gap too large: {largest_gap:.3f}s")
    if duration is None:
        partial.append("lap duration is unavailable")
    elif duration < min_duration_seconds or duration > max_duration_seconds:
        issue = f"lap duration is implausible: {duration:.3f}s"
        if completed:
            invalid.append(issue)
        else:
            partial.append(issue)
    if sample_count < min_samples:
        partial.append(f"not enough samples: {sample_count} < {min_samples}")
    if coverage is None:
        partial.append("spline coverage is unavailable")
    elif coverage < min_coverage_percent:
        partial.append(f"spline coverage is too low: {coverage:.1f}%")
    if progress_start is not None and progress_start > 0.25:
        partial.append(f"lap starts too late on spline: {progress_start:.3f}")
    if progress_end is not None and progress_end < 0.75 and not wrapped_complete_lap:
        partial.append(f"lap ends too early on spline: {progress_end:.3f}")
    if not completed:
        partial.append("lap is not completed")

    if invalid:
        status = "INVALID"
        issues = invalid + partial
    elif partial:
        status = "PARTIAL"
        issues = partial
    else:
        status = "VALID"
        issues = []

    return LapValidationResult(
        lapId=lap_id,
        lapNumber=lap_number,
        status=status,
        sampleCount=sample_count,
        durationSeconds=duration,
        coveragePercent=coverage,
        issues=tuple(issues),
    )
