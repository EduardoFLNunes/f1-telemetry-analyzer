from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .comparison_analysis import (
    AnalysisSample,
    build_microsectors,
    detect_acceleration_zone,
    detect_braking_zone,
    detect_speed_phase,
    estimate_segment_distance,
    estimate_segment_time_seconds,
    player_analysis_samples,
    samples_in_segment,
    select_current_and_reference_samples,
    speed_stats,
)
from .telemetry.telemetry_models import TelemetrySample


DEFAULT_TRAJECTORY_DEVIATION_METERS = 3.0
HIGH_TRAJECTORY_DEVIATION_METERS = 5.0
LOW_SPEED_DELTA_KMH = -4.0
LOW_EXIT_SPEED_DELTA_KMH = -8.0
MAX_VISUAL_REFERENCE_POINTS = 2400
_RACING_LINE_MODEL_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _track_length(track_data: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not track_data:
        return None
    return _safe_float(track_data.get("trackLength", track_data.get("track_length")))


def _track_name(track_name: Optional[str], track_data: Optional[Mapping[str, Any]]) -> str:
    if track_name:
        return track_name
    if track_data:
        name = track_data.get("name") or track_data.get("trackName") or track_data.get("geometryName")
        if name:
            return str(name)
    return "UNKNOWN"


def _valid_position(position: Optional[Tuple[float, float, float]]) -> Optional[Tuple[float, float, float]]:
    if position is None:
        return None
    if all(math.isfinite(value) for value in position):
        return position
    return None


def _point_distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _position_payload(position: Optional[Tuple[float, float, float]]) -> Dict[str, Optional[float]]:
    if position is None:
        return {"x": None, "y": None, "z": None}
    return {"x": _round_or_none(position[0], 4), "y": _round_or_none(position[1], 4), "z": _round_or_none(position[2], 4)}


def _average_position(samples: Sequence[AnalysisSample]) -> Tuple[Optional[Tuple[float, float, float]], int]:
    positions = [position for sample in samples if (position := _valid_position(sample.position)) is not None]
    if not positions:
        return None, 0
    count = len(positions)
    return (
        (
            sum(position[0] for position in positions) / count,
            sum(position[1] for position in positions) / count,
            sum(position[2] for position in positions) / count,
        ),
        count,
    )


def _visual_reference_line(reference_samples: Sequence[AnalysisSample]) -> Dict[str, Any]:
    visual_samples = [
        sample
        for sample in reference_samples
        if sample.progress is not None and _valid_position(sample.position) is not None
    ]
    visual_samples.sort(key=lambda sample: sample.progress or 0.0)

    stride = max(1, math.ceil(len(visual_samples) / MAX_VISUAL_REFERENCE_POINTS))
    display_samples = visual_samples[::stride]
    if visual_samples and display_samples and display_samples[-1] is not visual_samples[-1]:
        display_samples.append(visual_samples[-1])

    return {
        "source": "REFERENCE_LAP_SAMPLES",
        "sampleCount": len(visual_samples),
        "displayPointCount": len(display_samples),
        "downsampleStride": stride,
        "smoothingApplied": False,
        "points": [
            {
                "splinePosition": _round_or_none(sample.progress, 6),
                "position": _position_payload(_valid_position(sample.position)),
                "speedKmh": _round_or_none(sample.speed_kmh, 3),
                "brake": _round_or_none(sample.brake, 4),
                "throttle": _round_or_none(sample.throttle, 4),
                "timestamp": _round_or_none(sample.timestamp, 4),
            }
            for sample in display_samples
        ],
    }


def _estimated_curvature(samples: Sequence[AnalysisSample]) -> Optional[float]:
    points = [
        sample
        for sample in samples
        if sample.progress is not None and _valid_position(sample.position) is not None
    ]
    points.sort(key=lambda item: item.progress or 0.0)
    if len(points) < 3:
        return None

    first = _valid_position(points[0].position)
    middle = _valid_position(points[len(points) // 2].position)
    last = _valid_position(points[-1].position)
    if first is None or middle is None or last is None:
        return None

    a = _point_distance(first, middle)
    b = _point_distance(middle, last)
    c = _point_distance(first, last)
    denominator = a * b * c
    if denominator <= 1e-9:
        return None

    cross = abs(
        (middle[0] - first[0]) * (last[2] - first[2])
        - (middle[2] - first[2]) * (last[0] - first[0])
    )
    curvature = (2.0 * cross) / denominator
    return curvature if math.isfinite(curvature) else None


def detect_coasting_zone(samples: Sequence[AnalysisSample]) -> bool:
    phase = detect_speed_phase(samples)
    speed_delta = _safe_float(phase.get("speedDeltaKmh"))
    return phase.get("phase") == "NEUTRAL" and speed_delta is not None and abs(speed_delta) <= 3.0


def _confidence(sample_count: int, speed_count: int, position_count: int) -> str:
    if sample_count <= 0 or speed_count <= 0 or position_count <= 0:
        return "INSUFFICIENT_DATA"
    quality = min(speed_count, position_count) / max(1, sample_count)
    if sample_count >= 4 and quality >= 0.75:
        return "HIGH"
    if sample_count >= 2 and quality >= 0.5:
        return "MEDIUM"
    return "LOW"


def build_racing_line_model(
    *,
    reference_samples: Sequence[AnalysisSample],
    track: str,
    reference_lap_number: Optional[int],
    micro_sector_count: int = 50,
) -> Dict[str, Any]:
    microsectors = build_microsectors(micro_sector_count)
    count = len(microsectors)
    points: List[Dict[str, Any]] = []
    missing_position_samples = 0
    missing_speed_samples = 0
    valid_segments = 0
    rejected_segments = 0

    for segment in microsectors:
        index = int(segment["segmentIndex"])
        start = float(segment["splineStart"])
        end = float(segment["splineEnd"])
        segment_samples = samples_in_segment(reference_samples, start, end, index, count)
        stats = speed_stats(segment_samples)
        average_position, position_count = _average_position(segment_samples)
        speed_count = len([sample for sample in segment_samples if sample.speed_kmh is not None])
        confidence = _confidence(len(segment_samples), speed_count, position_count)
        braking = detect_braking_zone(segment_samples)
        acceleration = detect_acceleration_zone(segment_samples)
        coasting = detect_coasting_zone(segment_samples)

        missing_position_samples += max(0, len(segment_samples) - position_count)
        missing_speed_samples += max(0, len(segment_samples) - speed_count)
        if confidence == "INSUFFICIENT_DATA":
            rejected_segments += 1
        else:
            valid_segments += 1

        points.append(
            {
                **segment,
                "position": _position_payload(average_position),
                "avgSpeedKmh": _round_or_none(stats["avgSpeedKmh"], 3),
                "minSpeedKmh": _round_or_none(stats["minSpeedKmh"], 3),
                "maxSpeedKmh": _round_or_none(stats["maxSpeedKmh"], 3),
                "brakingZone": bool(braking.get("detected")),
                "accelerationZone": bool(acceleration.get("detected")),
                "coastingZone": coasting,
                "estimatedCurvature": _round_or_none(_estimated_curvature(segment_samples), 8),
                "confidence": confidence,
                "sampleCount": len(segment_samples),
            }
        )

    return {
        "track": track,
        "source": "REFERENCE_LAP",
        "referenceLapNumber": reference_lap_number,
        "microSectorCount": count,
        "generatedAt": _now_iso(),
        "points": points,
        "visualLine": _visual_reference_line(reference_samples),
        "debug": {
            "inputSamples": len(reference_samples),
            "validSegments": valid_segments,
            "rejectedSegments": rejected_segments,
            "missingPositionSamples": missing_position_samples,
            "missingSpeedSamples": missing_speed_samples,
            "smoothingApplied": False,
            "sourceLapWasPartial": False,
        },
    }


def _racing_line_position(point: Mapping[str, Any]) -> Optional[Tuple[float, float, float]]:
    position = point.get("position")
    if not isinstance(position, Mapping):
        return None
    x = _safe_float(position.get("x"))
    y = _safe_float(position.get("y"))
    z = _safe_float(position.get("z"))
    if x is None or y is None or z is None:
        return None
    return (x, y, z)


def _trajectory_deviation_to_point(
    player_segment: Sequence[AnalysisSample],
    racing_line_point: Mapping[str, Any],
) -> Optional[float]:
    reference_position = _racing_line_position(racing_line_point)
    if reference_position is None:
        return None
    distances = [
        _point_distance(position, reference_position)
        for sample in player_segment
        if (position := _valid_position(sample.position)) is not None
    ]
    if not distances:
        return None
    return sum(distances) / len(distances)


def _issue_message(issue: str) -> str:
    return {
        "TRAJECTORY": "Desvio relevante de trajetoria em relacao a linha de referencia.",
        "BRAKING_TOO_EARLY": "Voce parece estar freando antes da Racing Line.",
        "BRAKING_TOO_LATE": "Voce parece estar freando depois da Racing Line.",
        "ACCELERATING_TOO_LATE": "Voce esta acelerando depois da referencia.",
        "LOW_CORNER_SPEED": "Voce esta abaixo da velocidade de referencia neste trecho.",
        "LOW_EXIT_SPEED": "Voce esta saindo abaixo da velocidade de referencia.",
        "GOOD": "Trecho semelhante a Racing Line.",
        "UNKNOWN": "Dados inconclusivos para este microsetor.",
        "INSUFFICIENT_DATA": "Dados insuficientes para comparar este microsetor.",
    }.get(issue, "Dados inconclusivos para este microsetor.")


def _classify_issue(
    *,
    player_speed_kmh: Optional[float],
    racing_line_speed_kmh: Optional[float],
    trajectory_deviation_meters: Optional[float],
    player_braking: bool,
    racing_line_braking: bool,
    player_accelerating: bool,
    racing_line_accelerating: bool,
) -> str:
    if player_speed_kmh is None or racing_line_speed_kmh is None:
        return "INSUFFICIENT_DATA"

    speed_delta = player_speed_kmh - racing_line_speed_kmh
    if trajectory_deviation_meters is not None and trajectory_deviation_meters >= HIGH_TRAJECTORY_DEVIATION_METERS:
        return "TRAJECTORY"
    if player_braking and not racing_line_braking and speed_delta < -1.0:
        return "BRAKING_TOO_EARLY"
    if not player_braking and racing_line_braking and speed_delta > 3.0:
        return "BRAKING_TOO_LATE"
    if not player_accelerating and racing_line_accelerating and speed_delta < -2.0:
        return "ACCELERATING_TOO_LATE"
    if speed_delta <= LOW_EXIT_SPEED_DELTA_KMH and racing_line_accelerating:
        return "LOW_EXIT_SPEED"
    if speed_delta <= LOW_SPEED_DELTA_KMH:
        return "LOW_CORNER_SPEED"
    if trajectory_deviation_meters is not None and trajectory_deviation_meters >= DEFAULT_TRAJECTORY_DEVIATION_METERS:
        return "TRAJECTORY"
    if abs(speed_delta) <= 3.0 and (trajectory_deviation_meters is None or trajectory_deviation_meters < DEFAULT_TRAJECTORY_DEVIATION_METERS):
        return "GOOD"
    return "UNKNOWN"


def compare_player_to_racing_line(
    *,
    player_samples: Sequence[AnalysisSample],
    racing_line: Mapping[str, Any],
    track_data: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    points = list(racing_line.get("points") or [])
    count = len(points)
    track_length_meters = _track_length(track_data)
    segments: List[Dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()
    valid_comparison_segments = 0

    for point in points:
        index = int(point["segmentIndex"])
        start = float(point["splineStart"])
        end = float(point["splineEnd"])
        player_segment = samples_in_segment(player_samples, start, end, index, count)
        if not player_segment:
            rejection_reasons["missing_player_samples"] += 1

        player_stats = speed_stats(player_segment)
        player_speed = player_stats["avgSpeedKmh"]
        racing_line_speed = _safe_float(point.get("avgSpeedKmh"))
        speed_delta = player_speed - racing_line_speed if player_speed is not None and racing_line_speed is not None else None
        player_brake = detect_braking_zone(player_segment)
        player_accel = detect_acceleration_zone(player_segment)
        trajectory_deviation = _trajectory_deviation_to_point(player_segment, point)
        distance = estimate_segment_distance(
            [player_segment],
            track_length_meters,
            start,
            end,
        )
        player_time = estimate_segment_time_seconds(player_speed, distance)
        reference_time = estimate_segment_time_seconds(racing_line_speed, distance)
        estimated_delta = player_time - reference_time if player_time is not None and reference_time is not None else None
        player_braking = bool(player_brake.get("detected"))
        player_accelerating = bool(player_accel.get("detected"))
        racing_line_braking = bool(point.get("brakingZone"))
        racing_line_accelerating = bool(point.get("accelerationZone"))

        if player_speed is None:
            rejection_reasons["missing_player_speed"] += 1
        if racing_line_speed is None:
            rejection_reasons["missing_racing_line_speed"] += 1
        if trajectory_deviation is None:
            rejection_reasons["missing_position_samples"] += 1
        if player_speed is not None and racing_line_speed is not None:
            valid_comparison_segments += 1

        issue = _classify_issue(
            player_speed_kmh=player_speed,
            racing_line_speed_kmh=racing_line_speed,
            trajectory_deviation_meters=trajectory_deviation,
            player_braking=player_braking,
            racing_line_braking=racing_line_braking,
            player_accelerating=player_accelerating,
            racing_line_accelerating=racing_line_accelerating,
        )

        segments.append(
            {
                "segmentIndex": index,
                "splineStart": start,
                "splineEnd": end,
                "sector": int(point["sector"]),
                "playerSpeedKmh": _round_or_none(player_speed, 3),
                "racingLineSpeedKmh": _round_or_none(racing_line_speed, 3),
                "speedDeltaKmh": _round_or_none(speed_delta, 3),
                "trajectoryDeviationMeters": _round_or_none(trajectory_deviation, 3),
                "playerBraking": player_braking if player_segment else None,
                "racingLineBraking": racing_line_braking,
                "playerAccelerating": player_accelerating if player_segment else None,
                "racingLineAccelerating": racing_line_accelerating,
                "estimatedDeltaSeconds": _round_or_none(estimated_delta, 4),
                "mainIssue": issue,
                "message": _issue_message(issue),
            }
        )

    sector_summary = []
    for sector_id in (1, 2, 3):
        sector_segments = [segment for segment in segments if segment["sector"] == sector_id]
        deltas = [
            segment["estimatedDeltaSeconds"]
            for segment in sector_segments
            if segment["estimatedDeltaSeconds"] is not None
        ]
        issue_counts = Counter(
            segment["mainIssue"]
            for segment in sector_segments
            if segment["mainIssue"] not in {"GOOD", "UNKNOWN", "INSUFFICIENT_DATA"}
        )
        worst_segment = None
        loss_segments = [
            segment
            for segment in sector_segments
            if segment["estimatedDeltaSeconds"] is not None
        ]
        if loss_segments:
            worst_segment = max(loss_segments, key=lambda item: item["estimatedDeltaSeconds"])["segmentIndex"]

        sector_summary.append(
            {
                "sector": sector_id,
                "estimatedDeltaSeconds": _round_or_none(sum(deltas), 4) if deltas else None,
                "biggestIssue": issue_counts.most_common(1)[0][0] if issue_counts else None,
                "worstSegmentIndex": worst_segment,
            }
        )

    biggest_losses = [
        segment
        for segment in segments
        if segment["estimatedDeltaSeconds"] is not None and segment["estimatedDeltaSeconds"] > 0.03
    ]
    biggest_gains = [
        segment
        for segment in segments
        if segment["estimatedDeltaSeconds"] is not None and segment["estimatedDeltaSeconds"] < -0.03
    ]

    return {
        "track": str(racing_line.get("track") or "UNKNOWN"),
        "generatedAt": _now_iso(),
        "comparedAgainst": str(racing_line.get("source") or "REFERENCE_LAP"),
        "sectorSummary": sector_summary,
        "biggestLosses": sorted(biggest_losses, key=lambda item: item["estimatedDeltaSeconds"], reverse=True)[:5],
        "biggestGains": sorted(biggest_gains, key=lambda item: item["estimatedDeltaSeconds"])[:5],
        "segments": segments,
        "debug": {
            "playerSamples": len(player_samples),
            "racingLinePoints": len(points),
            "validComparisonSegments": valid_comparison_segments,
            "rejectedComparisonSegments": sum(rejection_reasons.values()),
            "reasonForRejectedSegments": sorted(rejection_reasons.keys()),
        },
    }


def build_live_racing_line_payload(
    *,
    telemetry_samples: Sequence[TelemetrySample],
    track_data: Optional[Mapping[str, Any]] = None,
    track_name: Optional[str] = None,
    micro_sector_count: int = 50,
    include_visual_line: bool = True,
    include_comparison: bool = True,
) -> Dict[str, Any]:
    current_samples, reference_samples, lap_debug = select_current_and_reference_samples(telemetry_samples)
    player_samples = player_analysis_samples(telemetry_samples)
    track = _track_name(track_name, track_data)
    base_debug = {
        "inputSamples": len(telemetry_samples),
        "playerSamples": len(player_samples),
        "currentLapSamples": len(current_samples),
        "referenceSamples": len(reference_samples),
        "microSectorCount": max(1, min(200, int(micro_sector_count or 50))),
        "includeVisualLine": bool(include_visual_line),
        "includeComparison": bool(include_comparison),
        "lapSelection": lap_debug,
    }

    if not reference_samples:
        return {
            "track": track,
            "status": "INSUFFICIENT_DATA",
            "racingLine": None,
            "comparison": None,
            "debug": {
                **base_debug,
                "reason": lap_debug.get("referenceRejected") or "no_valid_reference_lap",
            },
        }

    reference_key = (
        track,
        lap_debug.get("referenceLap"),
        max(1, min(200, int(micro_sector_count or 50))),
        len(reference_samples),
        _round_or_none(reference_samples[0].timestamp if reference_samples else None, 4),
        _round_or_none(reference_samples[-1].timestamp if reference_samples else None, 4),
        _round_or_none(reference_samples[0].progress if reference_samples else None, 6),
        _round_or_none(reference_samples[-1].progress if reference_samples else None, 6),
    )
    cached = _RACING_LINE_MODEL_CACHE.get(reference_key)
    cache_hit = cached is not None
    if cached is None:
        cached = build_racing_line_model(
            reference_samples=reference_samples,
            track=track,
            reference_lap_number=lap_debug.get("referenceLap"),
            micro_sector_count=micro_sector_count,
        )
        _RACING_LINE_MODEL_CACHE.clear()
        _RACING_LINE_MODEL_CACHE[reference_key] = cached
    racing_line = deepcopy(cached)
    if not include_visual_line:
        racing_line.pop("visualLine", None)
    if racing_line["debug"]["validSegments"] <= 0:
        return {
            "track": track,
            "status": "INSUFFICIENT_DATA",
            "racingLine": None,
            "comparison": None,
            "debug": {
                **base_debug,
                "reason": "reference_lap_has_no_valid_racing_line_segments",
                "racingLineDebug": racing_line["debug"],
                "racingLineCacheHit": cache_hit,
            },
        }

    comparison = None
    if include_comparison:
        comparison = compare_player_to_racing_line(
            player_samples=current_samples,
            racing_line=racing_line,
            track_data=track_data,
        )
    return {
        "track": track,
        "status": "READY",
        "racingLine": racing_line,
        "comparison": comparison,
        "debug": {
            **base_debug,
            "racingLineCacheHit": cache_hit,
            "racingLineCacheEntries": len(_RACING_LINE_MODEL_CACHE),
        },
    }
