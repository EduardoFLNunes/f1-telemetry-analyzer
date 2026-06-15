import math
from typing import Any, Dict, Iterable, Optional


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def timestamp_seconds(value: Any) -> Optional[float]:
    number = _number(value)
    if number is None:
        return None
    if number > 100_000_000_000.0:
        return number / 1000.0
    return number


def _percentile(values, percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def analyze_sample_timestamps(
    timestamps: Iterable[Any],
    *,
    target_hz: float = 60.0,
    stale_threshold_ms: float = 1000.0,
) -> Dict[str, Any]:
    expected_interval_ms = 1000.0 / max(float(target_hz), 1.0)
    previous = None
    valid_count = 0
    gaps_ms = []
    timestamp_inversions = 0

    for raw_value in timestamps:
        current = timestamp_seconds(raw_value)
        if current is None:
            continue
        valid_count += 1
        if previous is not None:
            gap_ms = (current - previous) * 1000.0
            if gap_ms < -0.1:
                timestamp_inversions += 1
            elif gap_ms > 0.0:
                gaps_ms.append(gap_ms)
        previous = current

    if not gaps_ms:
        return {
            "targetHz": float(target_hz),
            "avgHz": None,
            "minHz": None,
            "maxHz": None,
            "p95FrameGapMs": None,
            "p99FrameGapMs": None,
            "totalSamples": valid_count,
            "estimatedDroppedSamples": None,
            "longestGapMs": None,
            "stalePeriods": 0,
            "timestampInversions": timestamp_inversions,
            "qualityStatus": "UNKNOWN",
        }

    total_duration_ms = sum(gaps_ms)
    avg_hz = len(gaps_ms) * 1000.0 / total_duration_ms if total_duration_ms > 0.0 else None
    instantaneous_hz = [1000.0 / gap for gap in gaps_ms if gap > 0.0]
    p95 = _percentile(gaps_ms, 0.95)
    p99 = _percentile(gaps_ms, 0.99)
    longest = max(gaps_ms)
    dropped = sum(
        max(0, int(round(gap / expected_interval_ms)) - 1)
        for gap in gaps_ms
    )
    stale_periods = sum(1 for gap in gaps_ms if gap >= stale_threshold_ms)

    if avg_hz is None:
        quality = "UNKNOWN"
    elif avg_hz < 30.0 or (p95 is not None and p95 > 250.0) or longest > 5000.0:
        quality = "ERROR"
    elif avg_hz < 50.0 or (p95 is not None and p95 > 40.0) or longest > 1000.0:
        quality = "WARNING"
    else:
        quality = "OK"

    def rounded(value: Optional[float]) -> Optional[float]:
        return round(value, 3) if value is not None else None

    return {
        "targetHz": float(target_hz),
        "avgHz": rounded(avg_hz),
        "minHz": rounded(min(instantaneous_hz)) if instantaneous_hz else None,
        "maxHz": rounded(max(instantaneous_hz)) if instantaneous_hz else None,
        "p95FrameGapMs": rounded(p95),
        "p99FrameGapMs": rounded(p99),
        "totalSamples": valid_count,
        "estimatedDroppedSamples": dropped,
        "longestGapMs": rounded(longest),
        "stalePeriods": stale_periods,
        "timestampInversions": timestamp_inversions,
        "qualityStatus": quality,
    }
