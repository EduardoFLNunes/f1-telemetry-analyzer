from datetime import datetime, timezone
from math import isfinite
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .telemetry.telemetry_models import TelemetrySample


IDEAL_LINE_REFERENCE_SOURCE = "REFERENCE_LAP"
VISUAL_LINE_SOURCE = "REFERENCE_LAP_SAMPLES"


def _finite_float_or_none(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _speed_kmh_or_none(sample: TelemetrySample) -> Optional[float]:
    speed = _finite_float_or_none(getattr(sample, "speedKmh", None))
    if speed is None or speed <= 0.0:
        return None
    return speed


def _lap_number(samples: Sequence[TelemetrySample]) -> Optional[int]:
    lap_values = {
        int(sample.lap)
        for sample in samples
        if isinstance(getattr(sample, "lap", None), int) and sample.lap >= 0
    }
    return lap_values.pop() if len(lap_values) == 1 else None


def _visual_point(sample: TelemetrySample) -> Dict[str, Any]:
    x = _finite_float_or_none(sample.worldPositionX)
    y = _finite_float_or_none(sample.worldPositionY)
    z = _finite_float_or_none(sample.worldPositionZ)
    return {
        "x": x,
        "y": y,
        "z": z,
        "splinePosition": _finite_float_or_none(sample.normalizedSplinePosition),
        "speedKmh": _speed_kmh_or_none(sample),
        "lapTime": _finite_float_or_none(sample.sessionTime),
        "position": {
            "x": x,
            "y": y,
            "z": z,
        },
    }


def build_ideal_line_overlay(
    samples: Iterable[TelemetrySample],
    *,
    source: str = IDEAL_LINE_REFERENCE_SOURCE,
    reference_lap_number: Optional[int] = None,
) -> Dict[str, Any]:
    point_samples = list(samples)
    points: List[Dict[str, Any]] = [_visual_point(sample) for sample in point_samples]
    speeds = [
        point["speedKmh"]
        for point in points
        if isinstance(point.get("speedKmh"), (int, float)) and isfinite(float(point["speedKmh"]))
    ]

    resolved_lap = reference_lap_number
    if resolved_lap is None:
        resolved_lap = _lap_number(point_samples)

    return {
        "source": source if source else "UNKNOWN",
        "referenceLapNumber": resolved_lap,
        "points": points,
        "minSpeedKmh": min(speeds) if speeds else None,
        "maxSpeedKmh": max(speeds) if speeds else None,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def build_racing_line_response(
    samples: Iterable[TelemetrySample],
    *,
    source: str = IDEAL_LINE_REFERENCE_SOURCE,
    reference_lap_number: Optional[int] = None,
) -> Dict[str, Any]:
    ideal_line = build_ideal_line_overlay(
        samples,
        source=source,
        reference_lap_number=reference_lap_number,
    )
    visual_source = VISUAL_LINE_SOURCE if ideal_line["points"] and ideal_line["source"] != "UNKNOWN" else "UNKNOWN"
    visual_line = {
        "source": visual_source,
        "referenceLapNumber": ideal_line["referenceLapNumber"],
        "points": ideal_line["points"],
        "minSpeedKmh": ideal_line["minSpeedKmh"],
        "maxSpeedKmh": ideal_line["maxSpeedKmh"],
        "generatedAt": ideal_line["generatedAt"],
    }
    return {
        "status": "success",
        "idealLineOverlay": ideal_line,
        "visualLine": visual_line,
        "debug": {
            "idealLineSource": ideal_line["source"],
            "visualLineSource": visual_line["source"],
            "pointCount": len(ideal_line["points"]),
            "referenceLapNumber": ideal_line["referenceLapNumber"],
        },
    }
