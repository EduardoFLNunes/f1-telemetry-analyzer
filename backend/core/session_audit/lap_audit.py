import math
from typing import Any, Dict, Mapping, Optional, Sequence

from ..data_quality.lap_validation import validate_lap
from .sample_loss_report import timestamp_seconds
from .track_calibration import TrackCalibrationProfile


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _lap_number(sample: Mapping[str, Any]) -> Optional[int]:
    value = _number(sample.get("lap_number", sample.get("lap")))
    return int(value) if value is not None else None


def _progress(sample: Mapping[str, Any]) -> Optional[float]:
    for key in ("lapProgress", "p", "spline_t", "normalizedSplinePosition", "splinePosition"):
        value = _number(sample.get(key))
        if value is not None:
            return max(0.0, min(1.0, value))
    return None


def _lap_time(sample: Mapping[str, Any]) -> Optional[float]:
    for key in ("lap_time", "lapTime", "currentLapTime"):
        value = _number(sample.get(key))
        if value is not None and value >= 0.0:
            return value / 1000.0 if value > 10_000.0 else value
    return None


class LapStreamAggregator:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._current: Optional[Dict[str, Any]] = None
        self._items = []
        self._occurrences: Dict[int, int] = {}

    def observe(self, row: Mapping[str, Any]):
        sample = row.get("sample") if isinstance(row.get("sample"), Mapping) else {}
        lap_number = _lap_number(sample)
        if lap_number is None:
            return
        progress = _progress(sample)
        timestamp = timestamp_seconds(row.get("timestamp", sample.get("timestamp")))
        # Persisted Assetto sessions may reset spline one sample before the lap
        # counter changes. The lap number is the stable boundary for audit.
        transition = bool(
            self._current
            and lap_number != self._current["lapNumber"]
        )
        if transition:
            self._finalize_current(completed=True)
        if self._current is None:
            occurrence = self._occurrences.get(lap_number, 0) + 1
            self._occurrences[lap_number] = occurrence
            self._current = {
                "lapId": f"{self.session_id}:{lap_number}:{occurrence}",
                "lapNumber": lap_number,
                "sampleCount": 0,
                "durationSeconds": None,
                "progressStart": progress,
                "progressEnd": progress,
                "progressMin": progress,
                "progressMax": progress,
                "maxGapSeconds": None,
                "timestampInversions": 0,
                "previousTimestamp": None,
                "timestampMin": timestamp,
                "timestampMax": timestamp,
            }

        current = self._current
        current["sampleCount"] += 1
        if progress is not None:
            current["progressEnd"] = progress
            current["progressMin"] = min(
                current["progressMin"] if current["progressMin"] is not None else progress,
                progress,
            )
            current["progressMax"] = max(
                current["progressMax"] if current["progressMax"] is not None else progress,
                progress,
            )
        lap_time = _lap_time(sample)
        if lap_time is not None:
            current["durationSeconds"] = max(current["durationSeconds"] or lap_time, lap_time)
        previous_timestamp = current["previousTimestamp"]
        if timestamp is not None and previous_timestamp is not None:
            gap = timestamp - previous_timestamp
            if gap < -1e-6:
                current["timestampInversions"] += 1
            elif gap >= 0.0:
                current["maxGapSeconds"] = max(current["maxGapSeconds"] or 0.0, gap)
        if timestamp is not None:
            current["previousTimestamp"] = timestamp
            current["timestampMin"] = min(
                current["timestampMin"] if current["timestampMin"] is not None else timestamp,
                timestamp,
            )
            current["timestampMax"] = max(
                current["timestampMax"] if current["timestampMax"] is not None else timestamp,
                timestamp,
            )

    def finish(self, recording_ended: bool) -> Sequence[Mapping[str, Any]]:
        if self._current is not None:
            completed = bool(
                recording_ended
                and self._current.get("progressEnd") is not None
                and self._current["progressEnd"] >= 0.98
            )
            self._finalize_current(completed=completed)
        return list(self._items)

    def _finalize_current(self, completed: bool):
        if self._current is None:
            return
        current = dict(self._current)
        if current["durationSeconds"] is None:
            start = current.get("timestampMin")
            end = current.get("timestampMax")
            if start is not None and end is not None:
                current["durationSeconds"] = max(0.0, end - start)
        progress_min = current.get("progressMin")
        progress_max = current.get("progressMax")
        current["coveragePercent"] = (
            max(0.0, min(100.0, (progress_max - progress_min) * 100.0))
            if progress_min is not None and progress_max is not None
            else None
        )
        current["completed"] = completed
        current.pop("previousTimestamp", None)
        current.pop("timestampMin", None)
        current.pop("timestampMax", None)
        self._items.append(current)
        self._current = None


def audit_laps(
    session_id: str,
    laps: Sequence[Mapping[str, Any]],
    profile: TrackCalibrationProfile,
) -> Dict[str, Any]:
    items = []
    for lap in laps:
        result = validate_lap(
            {
                **dict(lap),
                "lapId": lap.get("lapId") or f"{session_id}:{lap.get('lapNumber', 'unknown')}",
                "durationSeconds": lap.get("durationSeconds", lap.get("duration")),
                "maxGapSeconds": (
                    float(lap["maxGapSeconds"])
                    if lap.get("maxGapSeconds") is not None
                    else None
                ),
            },
            min_samples=profile.minSamplesPerLap,
            min_duration_seconds=profile.minValidLapSeconds,
            max_duration_seconds=profile.maxValidLapSeconds,
            min_coverage_percent=profile.minSplineCoveragePercent,
            max_gap_seconds=profile.maxAllowedGapMs / 1000.0,
        )
        duration = result.durationSeconds
        avg_hz = (
            round(result.sampleCount / duration, 3)
            if duration is not None and duration > 0.0
            else None
        )
        max_gap_seconds = lap.get("maxGapSeconds")
        max_gap_ms = (
            round(float(max_gap_seconds) * 1000.0, 3)
            if max_gap_seconds is not None
            else None
        )
        items.append(
            {
                "lapId": result.lapId,
                "lapNumber": result.lapNumber,
                "status": result.status,
                "lapTimeSeconds": (
                    round(duration, 3) if duration is not None else None
                ),
                "sampleCount": result.sampleCount,
                "avgHz": avg_hz,
                "coveragePercent": result.coveragePercent,
                "maxGapMs": max_gap_ms,
                "timestampInversions": int(lap.get("timestampInversions") or 0),
                "issues": list(result.issues),
                "canUseAsReference": result.status == "VALID",
            }
        )

    valid = [item for item in items if item["status"] == "VALID"]
    partial = [item for item in items if item["status"] == "PARTIAL"]
    invalid = [item for item in items if item["status"] == "INVALID"]
    timed_valid = [item for item in valid if item["lapTimeSeconds"] is not None]
    best = min(timed_valid, key=lambda item: item["lapTimeSeconds"], default=None)
    issues = [
        f"{item['lapId']}: {issue}"
        for item in invalid + partial
        for issue in item["issues"]
    ][:20]
    return {
        "totalLaps": len(items),
        "validLaps": len(valid),
        "partialLaps": len(partial),
        "invalidLaps": len(invalid),
        "bestValidLapId": best["lapId"] if best else None,
        "bestValidLapTime": best["lapTimeSeconds"] if best else None,
        "issues": issues,
        "items": items,
    }
