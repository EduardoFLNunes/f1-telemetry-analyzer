from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .comparison_analysis import build_microsectors


G = 9.81
DEFAULT_MAX_LATERAL_G = 1.55
DEFAULT_MAX_ACCELERATION_MS2 = 4.2
DEFAULT_MAX_BRAKING_MS2 = 10.0
STRAIGHT_SPEED_LIMIT_MS = 95.0
MIN_CORNER_CURVATURE = 1e-5
MAX_SAMPLE_JUMP_METERS = 120.0
MIN_SEGMENT_LENGTH_METERS = 0.5

_PHYSICS_TARGET_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


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


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _kmh_to_ms(value: Optional[float]) -> Optional[float]:
    return value / 3.6 if value is not None and value > 0.0 else None


def _ms_to_kmh(value: Optional[float]) -> Optional[float]:
    return value * 3.6 if value is not None and value >= 0.0 else None


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [value for value in values if value is not None and math.isfinite(value)]
    return sum(valid) / len(valid) if valid else None


def _mode(values: Iterable[Optional[str]]) -> Optional[str]:
    valid = [value for value in values if value]
    if not valid:
        return None
    return Counter(valid).most_common(1)[0][0]


def _progress(value: Any) -> Optional[float]:
    number = _safe_float(value)
    if number is None:
        return None
    return max(0.0, min(1.0, number))


def _point_position(point: Mapping[str, Any]) -> Optional[Tuple[float, float, float]]:
    position = point.get("position")
    if not isinstance(position, Mapping):
        return None
    x = _safe_float(position.get("x"))
    y = _safe_float(position.get("y"))
    z = _safe_float(position.get("z"))
    if x is None or y is None or z is None:
        return None
    return (x, y, z)


def _distance_2d(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[float]:
    ax = _safe_float(a.get("x"))
    az = _safe_float(a.get("z"))
    bx = _safe_float(b.get("x"))
    bz = _safe_float(b.get("z"))
    if ax is None or az is None or bx is None or bz is None:
        return None
    return math.hypot(bx - ax, bz - az)


def _sector(value: Any) -> Optional[int]:
    number = _safe_int(value)
    return number if number in (1, 2, 3) else None


def physics_default_parameters() -> Dict[str, Any]:
    return {
        "massKg": {"value": None, "source": "UNAVAILABLE"},
        "maxLateralG": {"value": DEFAULT_MAX_LATERAL_G, "source": "CONFIG_DEFAULT"},
        "maxAccelerationMs2": {"value": DEFAULT_MAX_ACCELERATION_MS2, "source": "CONFIG_DEFAULT"},
        "maxBrakingMs2": {"value": DEFAULT_MAX_BRAKING_MS2, "source": "CONFIG_DEFAULT"},
        "surfaceGrip": {"value": None, "source": "UNAVAILABLE"},
        "airTemp": {"value": None, "source": "UNAVAILABLE"},
        "roadTemp": {"value": None, "source": "UNAVAILABLE"},
    }


def extract_visual_line_samples(racing_line_payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    racing_line = racing_line_payload.get("racingLine")
    if not isinstance(racing_line, Mapping):
        return []

    visual_line = racing_line.get("visualLine")
    points = visual_line.get("points") if isinstance(visual_line, Mapping) else None
    source = "VISUAL_LINE"
    if not points:
        points = racing_line.get("points")
        source = "RACING_LINE_POINTS"
    if not isinstance(points, Sequence):
        return []

    samples: List[Dict[str, Any]] = []
    for raw in points:
        if not isinstance(raw, Mapping):
            continue
        position = _point_position(raw)
        progress = _progress(raw.get("splinePosition", raw.get("splineStart")))
        if position is None or progress is None:
            continue
        samples.append(
            {
                "source": source,
                "splinePosition": progress,
                "x": position[0],
                "y": position[1],
                "z": position[2],
                "speedKmh": _safe_float(raw.get("speedKmh", raw.get("avgSpeedKmh"))),
                "brake": _safe_float(raw.get("brake")),
                "throttle": _safe_float(raw.get("throttle")),
            }
        )

    samples.sort(key=lambda sample: sample["splinePosition"])
    return samples


def compute_cumulative_distance(samples: Sequence[Mapping[str, Any]]) -> List[Optional[float]]:
    if not samples:
        return []

    distances: List[Optional[float]] = [0.0]
    cumulative = 0.0
    previous = samples[0]
    for current in samples[1:]:
        step = _distance_2d(previous, current)
        if step is None or step <= 0.0 or step > MAX_SAMPLE_JUMP_METERS:
            distances.append(None)
        else:
            cumulative += step
            distances.append(cumulative)
            previous = current
    return distances


def _triangle_curvature(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    c: Mapping[str, Any],
) -> Optional[float]:
    ax = _safe_float(a.get("x"))
    az = _safe_float(a.get("z"))
    bx = _safe_float(b.get("x"))
    bz = _safe_float(b.get("z"))
    cx = _safe_float(c.get("x"))
    cz = _safe_float(c.get("z"))
    if ax is None or az is None or bx is None or bz is None or cx is None or cz is None:
        return None

    ab = math.hypot(bx - ax, bz - az)
    bc = math.hypot(cx - bx, cz - bz)
    ac = math.hypot(cx - ax, cz - az)
    denominator = ab * bc * ac
    if denominator <= 1e-9:
        return None

    area2 = abs((bx - ax) * (cz - az) - (bz - az) * (cx - ax))
    curvature = 2.0 * area2 / denominator
    return curvature if math.isfinite(curvature) else None


def _smooth_nullable(values: Sequence[Optional[float]], window: int = 5) -> List[Optional[float]]:
    radius = max(1, window // 2)
    result: List[Optional[float]] = []
    for index in range(len(values)):
        local = [
            value
            for value in values[max(0, index - radius): min(len(values), index + radius + 1)]
            if value is not None
        ]
        result.append(sum(local) / len(local) if local else None)
    return result


def compute_curvature_profile(samples: Sequence[Mapping[str, Any]]) -> List[Optional[float]]:
    if not samples:
        return []
    if len(samples) < 3:
        return [None for _ in samples]

    raw: List[Optional[float]] = [None]
    for index in range(1, len(samples) - 1):
        raw.append(_triangle_curvature(samples[index - 1], samples[index], samples[index + 1]))
    raw.append(None)
    return _smooth_nullable(raw, window=5)


def estimate_corner_speed_limit(
    curvature: Optional[float],
    max_lateral_g: float,
    surface_grip: Optional[float] = None,
) -> Optional[float]:
    if curvature is None:
        return None
    if curvature <= MIN_CORNER_CURVATURE:
        return STRAIGHT_SPEED_LIMIT_MS

    grip_factor = surface_grip if surface_grip is not None and surface_grip > 0.0 else 1.0
    lateral_limit = max(0.1, max_lateral_g * grip_factor) * G
    speed = math.sqrt(lateral_limit / curvature)
    return max(3.0, min(STRAIGHT_SPEED_LIMIT_MS, speed)) if math.isfinite(speed) else None


def apply_forward_acceleration_pass(
    speed_limits: Sequence[Optional[float]],
    distances: Sequence[Optional[float]],
    max_acceleration_ms2: float,
) -> List[Optional[float]]:
    profile: List[Optional[float]] = []
    for index, limit in enumerate(speed_limits):
        safe_limit = limit if limit is not None else STRAIGHT_SPEED_LIMIT_MS
        if index == 0 or not profile or profile[-1] is None:
            profile.append(safe_limit)
            continue

        previous_distance = distances[index - 1] if index - 1 < len(distances) else None
        current_distance = distances[index] if index < len(distances) else None
        if previous_distance is None or current_distance is None or current_distance <= previous_distance:
            profile.append(safe_limit)
            continue

        previous_speed = profile[-1]
        reachable = math.sqrt(max(0.0, previous_speed * previous_speed + 2.0 * max_acceleration_ms2 * (current_distance - previous_distance)))
        profile.append(min(safe_limit, reachable))
    return profile


def apply_backward_braking_pass(
    speed_profile: Sequence[Optional[float]],
    distances: Sequence[Optional[float]],
    max_braking_ms2: float,
) -> List[Optional[float]]:
    profile = list(speed_profile)
    for index in range(len(profile) - 2, -1, -1):
        current_speed = profile[index]
        next_speed = profile[index + 1] if index + 1 < len(profile) else None
        current_distance = distances[index] if index < len(distances) else None
        next_distance = distances[index + 1] if index + 1 < len(distances) else None
        if current_speed is None or next_speed is None or current_distance is None or next_distance is None:
            continue
        if next_distance <= current_distance:
            continue

        reachable = math.sqrt(max(0.0, next_speed * next_speed + 2.0 * max_braking_ms2 * (next_distance - current_distance)))
        if current_speed > reachable:
            profile[index] = reachable
    return profile


def _segment_time_from_entries(entries: Sequence[Mapping[str, Any]], speed_key: str) -> Optional[float]:
    total = 0.0
    valid = 0
    for previous, current in zip(entries, entries[1:]):
        prev_distance = _safe_float(previous.get("distanceMeters"))
        cur_distance = _safe_float(current.get("distanceMeters"))
        prev_speed = _kmh_to_ms(_safe_float(previous.get(speed_key))) if speed_key.endswith("Kmh") else _safe_float(previous.get(speed_key))
        cur_speed = _kmh_to_ms(_safe_float(current.get(speed_key))) if speed_key.endswith("Kmh") else _safe_float(current.get(speed_key))
        if prev_distance is None or cur_distance is None or cur_distance <= prev_distance:
            continue
        if prev_speed is None or cur_speed is None or prev_speed <= 0.5 or cur_speed <= 0.5:
            continue
        avg_speed = (prev_speed + cur_speed) / 2.0
        total += (cur_distance - prev_distance) / avg_speed
        valid += 1
    return total if valid else None


def _segment_confidence(sample_count: int, length: Optional[float], curvature_count: int, target_time: Optional[float]) -> str:
    if sample_count < 2 or length is None or length <= 0.0 or target_time is None:
        return "INSUFFICIENT_DATA"
    if sample_count >= 5 and curvature_count >= 2:
        return "HIGH"
    if sample_count >= 3:
        return "MEDIUM"
    return "LOW"


def _limiting_factor(entry: Mapping[str, Any]) -> str:
    value = entry.get("limitingFactor")
    return str(value) if value else "UNKNOWN"


def aggregate_physics_profile_to_microsectors(
    profile: Sequence[Mapping[str, Any]],
    micro_sectors: int = 50,
) -> List[Dict[str, Any]]:
    sectors = build_microsectors(micro_sectors)
    count = len(sectors)
    segments: List[Dict[str, Any]] = []

    for sector in sectors:
        index = int(sector["segmentIndex"])
        start = float(sector["splineStart"])
        end = float(sector["splineEnd"])
        entries = [
            entry
            for entry in profile
            if (progress := _safe_float(entry.get("splinePosition"))) is not None
            and (start <= progress <= end if index == count - 1 else start <= progress < end)
        ]
        distances = [_safe_float(entry.get("distanceMeters")) for entry in entries]
        valid_distances = [distance for distance in distances if distance is not None]
        distance_start = min(valid_distances) if valid_distances else None
        distance_end = max(valid_distances) if valid_distances else None
        segment_length = (
            distance_end - distance_start
            if distance_start is not None and distance_end is not None and distance_end > distance_start
            else None
        )

        physics_time = _segment_time_from_entries(entries, "physicsTargetSpeedMs")
        reference_time = _segment_time_from_entries(entries, "referenceSpeedKmh")
        physics_speed = _mean([_ms_to_kmh(_safe_float(entry.get("physicsTargetSpeedMs"))) for entry in entries])
        reference_speed = _mean([_safe_float(entry.get("referenceSpeedKmh")) for entry in entries])
        curvature = _mean([_safe_float(entry.get("curvature")) for entry in entries])
        radius = 1.0 / curvature if curvature is not None and curvature > MIN_CORNER_CURVATURE else None
        limiting = _mode(_limiting_factor(entry) for entry in entries) or "DATA_LIMITED"
        curvature_count = len([entry for entry in entries if _safe_float(entry.get("curvature")) is not None])
        confidence = _segment_confidence(len(entries), segment_length, curvature_count, physics_time)
        if confidence == "INSUFFICIENT_DATA":
            limiting = "DATA_LIMITED"

        segments.append(
            {
                **sector,
                "distanceStartMeters": _round_or_none(distance_start, 3),
                "distanceEndMeters": _round_or_none(distance_end, 3),
                "segmentLengthMeters": _round_or_none(segment_length, 3),
                "curvature": _round_or_none(curvature, 8),
                "radiusMeters": _round_or_none(radius, 3),
                "playerAvgSpeedKmh": None,
                "referenceAvgSpeedKmh": _round_or_none(reference_speed, 3),
                "physicsTargetSpeedKmh": _round_or_none(physics_speed, 3),
                "playerEstimatedTimeSeconds": None,
                "referenceEstimatedTimeSeconds": _round_or_none(reference_time, 4),
                "physicsTargetTimeSeconds": _round_or_none(physics_time, 4),
                "playerVsPhysicsDeltaSeconds": None,
                "referenceVsPhysicsDeltaSeconds": (
                    _round_or_none(reference_time - physics_time, 4)
                    if reference_time is not None and physics_time is not None
                    else None
                ),
                "limitingFactor": limiting,
                "confidence": confidence,
            }
        )
    return segments


def _estimated_time_from_speed(speed_kmh: Optional[float], distance_meters: Optional[float]) -> Optional[float]:
    speed_ms = _kmh_to_ms(speed_kmh)
    if speed_ms is None or speed_ms <= 0.5 or distance_meters is None or distance_meters <= 0.0:
        return None
    return distance_meters / speed_ms


def compare_player_to_physics_target(
    player_segments: Sequence[Mapping[str, Any]],
    physics_segments: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    by_index = {
        _safe_int(segment.get("segmentIndex")): segment
        for segment in player_segments
        if isinstance(segment, Mapping) and _safe_int(segment.get("segmentIndex")) is not None
    }
    compared: List[Dict[str, Any]] = []
    for segment in physics_segments:
        index = _safe_int(segment.get("segmentIndex"))
        player = by_index.get(index)
        player_speed = _safe_float(player.get("playerSpeedKmh")) if isinstance(player, Mapping) else None
        reference_speed = _safe_float(player.get("racingLineSpeedKmh")) if isinstance(player, Mapping) else _safe_float(segment.get("referenceAvgSpeedKmh"))
        distance = _safe_float(segment.get("segmentLengthMeters"))
        player_time = _estimated_time_from_speed(player_speed, distance)
        reference_time = _estimated_time_from_speed(reference_speed, distance)
        physics_time = _safe_float(segment.get("physicsTargetTimeSeconds"))

        enriched = dict(segment)
        enriched["playerAvgSpeedKmh"] = _round_or_none(player_speed, 3)
        enriched["referenceAvgSpeedKmh"] = _round_or_none(reference_speed, 3)
        enriched["playerEstimatedTimeSeconds"] = _round_or_none(player_time, 4)
        enriched["referenceEstimatedTimeSeconds"] = _round_or_none(reference_time, 4)
        enriched["playerVsPhysicsDeltaSeconds"] = (
            _round_or_none(player_time - physics_time, 4)
            if player_time is not None and physics_time is not None
            else None
        )
        enriched["referenceVsPhysicsDeltaSeconds"] = (
            _round_or_none(reference_time - physics_time, 4)
            if reference_time is not None and physics_time is not None
            else segment.get("referenceVsPhysicsDeltaSeconds")
        )
        if player_speed is None and reference_speed is None:
            enriched["confidence"] = "INSUFFICIENT_DATA"
            enriched["limitingFactor"] = "DATA_LIMITED"
        compared.append(enriched)
    return compared


def _build_profile(samples: Sequence[Mapping[str, Any]], parameters: Mapping[str, Any]) -> Dict[str, Any]:
    distances = compute_cumulative_distance(samples)
    curvature = compute_curvature_profile(samples)
    max_lateral_g = float(parameters["maxLateralG"]["value"])
    max_accel = float(parameters["maxAccelerationMs2"]["value"])
    max_brake = float(parameters["maxBrakingMs2"]["value"])
    surface_grip = _safe_float(parameters["surfaceGrip"]["value"])
    limits = [estimate_corner_speed_limit(value, max_lateral_g, surface_grip) for value in curvature]
    forward = apply_forward_acceleration_pass(limits, distances, max_accel)
    target = apply_backward_braking_pass(forward, distances, max_brake)

    entries: List[Dict[str, Any]] = []
    for index, sample in enumerate(samples):
        limit = limits[index] if index < len(limits) else None
        forward_speed = forward[index] if index < len(forward) else None
        target_speed = target[index] if index < len(target) else None
        factor = "UNKNOWN"
        if distances[index] is None:
            factor = "DATA_LIMITED"
        elif target_speed is None:
            factor = "DATA_LIMITED"
        elif limit is not None and limit < STRAIGHT_SPEED_LIMIT_MS * 0.96 and abs(target_speed - limit) < 0.6:
            factor = "CURVATURE"
        elif forward_speed is not None and target_speed < forward_speed - 0.6:
            factor = "BRAKING"
        elif limit is not None and forward_speed is not None and forward_speed < limit - 0.6:
            factor = "ACCELERATION"
        else:
            factor = "STRAIGHT_SPEED"

        entries.append(
            {
                "splinePosition": sample.get("splinePosition"),
                "distanceMeters": distances[index] if index < len(distances) else None,
                "curvature": curvature[index] if index < len(curvature) else None,
                "speedLimitMs": limit,
                "forwardSpeedMs": forward_speed,
                "physicsTargetSpeedMs": target_speed,
                "referenceSpeedKmh": sample.get("speedKmh"),
                "limitingFactor": factor,
            }
        )
    return {
        "profile": entries,
        "distances": distances,
        "curvature": curvature,
        "speedLimits": limits,
        "forward": forward,
        "target": target,
    }


def _target_cache_key(
    racing_line_payload: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    micro_sector_count: int,
    parameters: Mapping[str, Any],
) -> Tuple[Any, ...]:
    racing_line = racing_line_payload.get("racingLine") if isinstance(racing_line_payload.get("racingLine"), Mapping) else {}
    first = samples[0] if samples else {}
    last = samples[-1] if samples else {}
    return (
        racing_line_payload.get("track"),
        racing_line.get("referenceLapNumber") if isinstance(racing_line, Mapping) else None,
        len(samples),
        _round_or_none(_safe_float(first.get("splinePosition")), 6),
        _round_or_none(_safe_float(last.get("splinePosition")), 6),
        _round_or_none(_safe_float(first.get("x")), 3),
        _round_or_none(_safe_float(last.get("x")), 3),
        micro_sector_count,
        parameters["maxLateralG"]["value"],
        parameters["maxAccelerationMs2"]["value"],
        parameters["maxBrakingMs2"]["value"],
    )


def _reference_lap_time(racing_line_payload: Mapping[str, Any]) -> Optional[float]:
    laps = racing_line_payload.get("fastestLaps")
    if isinstance(laps, Sequence):
        for lap in laps:
            if isinstance(lap, Mapping) and lap.get("usedForRacingLine"):
                return _safe_float(lap.get("durationSeconds"))
        for lap in laps:
            if isinstance(lap, Mapping):
                return _safe_float(lap.get("durationSeconds"))
    return None


def _insufficient_report(racing_line_payload: Mapping[str, Any], micro_sector_count: int, reason: str) -> Dict[str, Any]:
    parameters = physics_default_parameters()
    return {
        "status": "INSUFFICIENT_DATA",
        "track": racing_line_payload.get("track"),
        "generatedAt": _now_iso(),
        "source": "UNKNOWN",
        "referenceLapNumber": None,
        "microSectorCount": micro_sector_count,
        "parameters": parameters,
        "summary": {
            "estimatedPhysicsLapTimeSeconds": None,
            "referenceLapTimeSeconds": None,
            "playerCurrentEstimatedLapTimeSeconds": None,
            "playerLossToPhysicsSeconds": None,
            "referenceLossToPhysicsSeconds": None,
            "biggestLossSector": None,
            "biggestLimitingFactor": None,
        },
        "sectors": [
            {
                "sector": sector,
                "physicsTargetTimeSeconds": None,
                "playerEstimatedTimeSeconds": None,
                "deltaSeconds": None,
                "mainLimitingFactor": "DATA_LIMITED",
            }
            for sector in (1, 2, 3)
        ],
        "segments": [],
        "debug": {
            "visualLineSamples": 0,
            "validDistanceSamples": 0,
            "validCurvatureSegments": 0,
            "rejectedSegments": micro_sector_count,
            "usedEstimatedParameters": [],
            "unavailableParameters": ["massKg", "surfaceGrip", "airTemp", "roadTemp"],
            "warnings": [reason],
            "physicsTargetCacheHit": False,
        },
    }


def _sum_field(segments: Sequence[Mapping[str, Any]], field: str) -> Optional[float]:
    values = [_safe_float(segment.get(field)) for segment in segments]
    valid = [value for value in values if value is not None]
    return sum(valid) if valid else None


def _sector_summary(segments: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for sector in (1, 2, 3):
        sector_segments = [segment for segment in segments if _sector(segment.get("sector")) == sector]
        physics_time = _sum_field(sector_segments, "physicsTargetTimeSeconds")
        player_time = _sum_field(sector_segments, "playerEstimatedTimeSeconds")
        delta = player_time - physics_time if player_time is not None and physics_time is not None else None
        result.append(
            {
                "sector": sector,
                "physicsTargetTimeSeconds": _round_or_none(physics_time, 4),
                "playerEstimatedTimeSeconds": _round_or_none(player_time, 4),
                "deltaSeconds": _round_or_none(delta, 4),
                "mainLimitingFactor": _mode(segment.get("limitingFactor") for segment in sector_segments),
            }
        )
    return result


def build_physics_fast_lap_report(
    racing_line_payload: Mapping[str, Any],
    telemetry_payload: Optional[Mapping[str, Any]] = None,
    micro_sectors: int = 50,
) -> Dict[str, Any]:
    del telemetry_payload
    micro_sector_count = max(1, min(200, int(micro_sectors or 50)))
    racing_line = racing_line_payload.get("racingLine")
    if racing_line_payload.get("status") != "READY" or not isinstance(racing_line, Mapping):
        return _insufficient_report(racing_line_payload, micro_sector_count, "racing_line_not_ready")

    samples = extract_visual_line_samples(racing_line_payload)
    if len(samples) < 6:
        return _insufficient_report(racing_line_payload, micro_sector_count, "visual_line_has_too_few_samples")

    parameters = physics_default_parameters()
    cache_key = _target_cache_key(racing_line_payload, samples, micro_sector_count, parameters)
    cached_target = _PHYSICS_TARGET_CACHE.get(cache_key)
    cache_hit = cached_target is not None
    if cached_target is None:
        target = _build_profile(samples, parameters)
        physics_segments = aggregate_physics_profile_to_microsectors(target["profile"], micro_sector_count)
        cached_target = {
            "target": target,
            "physicsSegments": physics_segments,
        }
        _PHYSICS_TARGET_CACHE.clear()
        _PHYSICS_TARGET_CACHE[cache_key] = cached_target

    target = cached_target["target"]
    comparison = racing_line_payload.get("comparison")
    player_segments = comparison.get("segments") if isinstance(comparison, Mapping) else []
    segments = compare_player_to_physics_target(
        player_segments if isinstance(player_segments, Sequence) else [],
        deepcopy(cached_target["physicsSegments"]),
    )

    physics_lap_time = _sum_field(segments, "physicsTargetTimeSeconds")
    player_lap_time = _sum_field(segments, "playerEstimatedTimeSeconds")
    reference_sum_time = _sum_field(segments, "referenceEstimatedTimeSeconds")
    reference_lap_time = _reference_lap_time(racing_line_payload) or reference_sum_time
    player_loss = player_lap_time - physics_lap_time if player_lap_time is not None and physics_lap_time is not None else None
    reference_loss = reference_lap_time - physics_lap_time if reference_lap_time is not None and physics_lap_time is not None else None
    sectors = _sector_summary(segments)
    positive_sector_losses = [
        sector
        for sector in sectors
        if (delta := _safe_float(sector.get("deltaSeconds"))) is not None and delta > 0.0
    ]
    biggest_loss_sector = (
        max(positive_sector_losses, key=lambda sector: _safe_float(sector.get("deltaSeconds")) or 0.0).get("sector")
        if positive_sector_losses
        else None
    )
    loss_segments = [
        segment
        for segment in segments
        if (_safe_float(segment.get("playerVsPhysicsDeltaSeconds")) or 0.0) > 0.0
    ]
    biggest_factor = _mode(segment.get("limitingFactor") for segment in loss_segments) or _mode(segment.get("limitingFactor") for segment in segments)

    valid_distances = len([value for value in target["distances"] if value is not None])
    valid_curvatures = len([value for value in target["curvature"] if value is not None])
    rejected_segments = sum(1 for segment in segments if segment.get("confidence") == "INSUFFICIENT_DATA")
    warnings = [
        "physics_model_v1_simplified",
        "uses_existing_reference_racing_line",
        "not_a_full_assetto_corsa_physics_simulation",
    ]

    return {
        "status": "READY",
        "track": racing_line_payload.get("track") or racing_line.get("track"),
        "generatedAt": _now_iso(),
        "source": "REFERENCE_RACING_LINE",
        "referenceLapNumber": racing_line.get("referenceLapNumber"),
        "microSectorCount": int(racing_line.get("microSectorCount") or micro_sector_count),
        "parameters": parameters,
        "summary": {
            "estimatedPhysicsLapTimeSeconds": _round_or_none(physics_lap_time, 4),
            "referenceLapTimeSeconds": _round_or_none(reference_lap_time, 4),
            "playerCurrentEstimatedLapTimeSeconds": _round_or_none(player_lap_time, 4),
            "playerLossToPhysicsSeconds": _round_or_none(player_loss, 4),
            "referenceLossToPhysicsSeconds": _round_or_none(reference_loss, 4),
            "biggestLossSector": biggest_loss_sector,
            "biggestLimitingFactor": biggest_factor,
        },
        "sectors": sectors,
        "segments": segments,
        "debug": {
            "visualLineSamples": len(samples),
            "validDistanceSamples": valid_distances,
            "validCurvatureSegments": valid_curvatures,
            "rejectedSegments": rejected_segments,
            "usedEstimatedParameters": [],
            "unavailableParameters": ["massKg", "surfaceGrip", "airTemp", "roadTemp"],
            "warnings": warnings,
            "physicsTargetCacheHit": cache_hit,
            "physicsTargetCacheEntries": len(_PHYSICS_TARGET_CACHE),
        },
    }
