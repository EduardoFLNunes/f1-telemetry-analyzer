from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .opponents.opponent_models import OpponentCarState
from .telemetry.telemetry_models import TelemetrySample


MIN_VALID_REFERENCE_SAMPLES = 40
MIN_VALID_REFERENCE_DURATION_SECONDS = 20.0
MAX_VALID_REFERENCE_DURATION_SECONDS = 900.0
VALID_REFERENCE_START_PROGRESS = 0.18
VALID_REFERENCE_END_PROGRESS = 0.82
MIN_TREND_SAMPLES = 3
SPEED_TREND_STEP_KMH = 0.8
SPEED_TREND_TOTAL_KMH = 2.0
EVENT_PROGRESS_EPSILON = 0.004


@dataclass(frozen=True)
class AnalysisSample:
    progress: Optional[float]
    speed_kmh: Optional[float]
    position: Optional[Tuple[float, float, float]]
    timestamp: Optional[float] = None
    lap: Optional[int] = None
    throttle: Optional[float] = None
    brake: Optional[float] = None


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


def _valid_progress(value: Any) -> Optional[float]:
    number = _safe_float(value)
    if number is None or number < 0.0 or number > 1.0:
        return None
    return max(0.0, min(1.0, number))


def _telemetry_timestamp_seconds(sample: TelemetrySample) -> Optional[float]:
    raw_timestamp = getattr(sample, "timestamp", None)
    if isinstance(raw_timestamp, (int, float)):
        timestamp = float(raw_timestamp)
        if not math.isfinite(timestamp):
            return None
        return timestamp / 1000.0 if timestamp > 100_000_000_000 else timestamp
    try:
        return datetime.fromisoformat(str(raw_timestamp)).timestamp()
    except (TypeError, ValueError):
        return None


def player_analysis_samples(samples: Iterable[TelemetrySample]) -> List[AnalysisSample]:
    """Convert only player telemetry samples into analysis samples.

    Opponent samples are deliberately ignored here so the player pipeline cannot
    be contaminated by side-channel opponent telemetry.
    """

    converted: List[AnalysisSample] = []
    for sample in samples:
        if int(getattr(sample, "carId", 0) or 0) != 0:
            continue
        converted.append(
            AnalysisSample(
                progress=_valid_progress(getattr(sample, "normalizedSplinePosition", None)),
                speed_kmh=_safe_float(getattr(sample, "speed", None)),
                position=(
                    float(sample.worldPositionX),
                    float(sample.worldPositionY),
                    float(sample.worldPositionZ),
                ),
                timestamp=_telemetry_timestamp_seconds(sample),
                lap=_safe_int(getattr(sample, "lap", None)),
                throttle=_safe_float(getattr(sample, "throttle", None)),
                brake=_safe_float(getattr(sample, "brake", None)),
            )
        )
    return converted


def opponent_analysis_samples(samples: Iterable[OpponentCarState]) -> List[AnalysisSample]:
    converted: List[AnalysisSample] = []
    for sample in samples:
        if sample.carId == 0 or sample.isPlayer:
            continue

        position = None
        if sample.worldPositionX is not None and sample.worldPositionZ is not None:
            position = (
                float(sample.worldPositionX),
                float(sample.worldPositionY or 0.0),
                float(sample.worldPositionZ),
            )

        converted.append(
            AnalysisSample(
                progress=_valid_progress(sample.splinePosition),
                speed_kmh=_safe_float(sample.speedKmh),
                position=position,
                timestamp=_safe_float(sample.timestamp),
                lap=_safe_int(sample.lap),
                throttle=None,
                brake=None,
            )
        )
    return converted


def build_microsectors(count: int) -> List[Dict[str, Any]]:
    safe_count = max(1, min(200, int(count or 50)))
    sectors = []
    for index in range(safe_count):
        start = index / safe_count
        end = (index + 1) / safe_count
        midpoint = (start + end) / 2.0
        sector = 1 if midpoint < (1.0 / 3.0) else (2 if midpoint < (2.0 / 3.0) else 3)
        sectors.append(
            {
                "segmentIndex": index,
                "splineStart": start,
                "splineEnd": end,
                "sector": sector,
            }
        )
    return sectors


def speed_stats(samples: Sequence[AnalysisSample]) -> Dict[str, Optional[float]]:
    speeds = [sample.speed_kmh for sample in samples if sample.speed_kmh is not None]
    if not speeds:
        return {"avgSpeedKmh": None, "minSpeedKmh": None, "maxSpeedKmh": None}
    return {
        "avgSpeedKmh": sum(speeds) / len(speeds),
        "minSpeedKmh": min(speeds),
        "maxSpeedKmh": max(speeds),
    }


def _is_in_segment(progress: Optional[float], start: float, end: float, index: int, count: int) -> bool:
    if progress is None:
        return False
    if index == count - 1:
        return start <= progress <= end
    return start <= progress < end


def samples_in_segment(
    samples: Sequence[AnalysisSample],
    start: float,
    end: float,
    index: int,
    count: int,
) -> List[AnalysisSample]:
    return [sample for sample in samples if _is_in_segment(sample.progress, start, end, index, count)]


def _point_distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _path_distance(samples: Sequence[AnalysisSample]) -> Optional[float]:
    points = [sample for sample in samples if sample.position is not None and sample.progress is not None]
    points.sort(key=lambda item: item.progress or 0.0)
    if len(points) < 2:
        return None
    distance = 0.0
    for previous, current in zip(points, points[1:]):
        distance += _point_distance(previous.position, current.position)  # type: ignore[arg-type]
    return distance if distance > 0.0 else None


def estimate_segment_distance(
    sample_groups: Sequence[Sequence[AnalysisSample]],
    track_length_meters: Optional[float],
    spline_start: float,
    spline_end: float,
) -> Optional[float]:
    for samples in sample_groups:
        distance = _path_distance(samples)
        if distance is not None and distance >= 1.0:
            return distance
    if track_length_meters is not None and track_length_meters > 0.0:
        return track_length_meters * max(0.0, spline_end - spline_start)
    return None


def estimate_segment_time_seconds(avg_speed_kmh: Optional[float], distance_meters: Optional[float]) -> Optional[float]:
    if avg_speed_kmh is None or avg_speed_kmh <= 1.0:
        return None
    if distance_meters is None or distance_meters <= 0.0:
        return None
    return distance_meters / (avg_speed_kmh / 3.6)


def _smooth(values: Sequence[float], window: int = 3) -> List[float]:
    if len(values) < window:
        return list(values)
    radius = max(1, window // 2)
    smoothed = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        chunk = values[start:end]
        smoothed.append(sum(chunk) / len(chunk))
    return smoothed


def _speed_trend(samples: Sequence[AnalysisSample]) -> Dict[str, Any]:
    points = [
        sample
        for sample in samples
        if sample.progress is not None and sample.speed_kmh is not None
    ]
    points.sort(key=lambda item: item.progress or 0.0)
    if len(points) < MIN_TREND_SAMPLES:
        return {"phase": "UNKNOWN", "startSpline": None, "source": "speed_inference", "speedDeltaKmh": None}

    speeds = _smooth([sample.speed_kmh or 0.0 for sample in points])
    deltas = [current - previous for previous, current in zip(speeds, speeds[1:])]
    total_delta = speeds[-1] - speeds[0]
    drops = [index for index, delta in enumerate(deltas) if delta <= -SPEED_TREND_STEP_KMH]
    gains = [index for index, delta in enumerate(deltas) if delta >= SPEED_TREND_STEP_KMH]
    denominator = max(1, len(deltas))

    if total_delta <= -SPEED_TREND_TOTAL_KMH and len(drops) / denominator >= 0.45:
        return {
            "phase": "BRAKING",
            "startSpline": points[drops[0]].progress if drops else points[0].progress,
            "source": "speed_inference",
            "speedDeltaKmh": total_delta,
        }
    if total_delta >= SPEED_TREND_TOTAL_KMH and len(gains) / denominator >= 0.45:
        return {
            "phase": "ACCELERATION",
            "startSpline": points[gains[0]].progress if gains else points[0].progress,
            "source": "speed_inference",
            "speedDeltaKmh": total_delta,
        }
    return {
        "phase": "NEUTRAL",
        "startSpline": points[0].progress,
        "source": "speed_inference",
        "speedDeltaKmh": total_delta,
    }


def detect_braking_zone(samples: Sequence[AnalysisSample]) -> Dict[str, Any]:
    direct_brake = [
        sample
        for sample in samples
        if sample.progress is not None and sample.brake is not None and sample.brake > 0.05
    ]
    if len(direct_brake) >= 2:
        direct_brake.sort(key=lambda item: item.progress or 0.0)
        return {"detected": True, "startSpline": direct_brake[0].progress, "source": "brake"}

    trend = _speed_trend(samples)
    return {
        "detected": trend["phase"] == "BRAKING",
        "startSpline": trend["startSpline"] if trend["phase"] == "BRAKING" else None,
        "source": trend["source"],
    }


def detect_acceleration_zone(samples: Sequence[AnalysisSample]) -> Dict[str, Any]:
    trend = _speed_trend(samples)
    if trend["phase"] == "ACCELERATION":
        return {"detected": True, "startSpline": trend["startSpline"], "source": trend["source"]}

    direct_throttle = [
        sample
        for sample in samples
        if sample.progress is not None and sample.throttle is not None and sample.throttle > 0.35
    ]
    if len(direct_throttle) >= 2:
        direct_throttle.sort(key=lambda item: item.progress or 0.0)
        return {"detected": True, "startSpline": direct_throttle[0].progress, "source": "throttle"}

    return {"detected": False, "startSpline": None, "source": trend["source"]}


def detect_speed_phase(samples: Sequence[AnalysisSample]) -> Dict[str, Any]:
    return _speed_trend(samples)


def trajectory_deviation(
    samples: Sequence[AnalysisSample],
    reference_samples: Sequence[AnalysisSample],
) -> Dict[str, Optional[float]]:
    points = [sample for sample in samples if sample.progress is not None and sample.position is not None]
    reference = [sample for sample in reference_samples if sample.progress is not None and sample.position is not None]
    if not points or not reference:
        return {"avgMeters": None, "maxMeters": None, "maxAtSpline": None}

    distances: List[Tuple[float, float]] = []
    for sample in points:
        nearest = min(reference, key=lambda ref: abs((ref.progress or 0.0) - (sample.progress or 0.0)))
        distance = _point_distance(sample.position, nearest.position)  # type: ignore[arg-type]
        distances.append((distance, sample.progress or 0.0))

    max_distance, max_progress = max(distances, key=lambda item: item[0])
    return {
        "avgMeters": sum(distance for distance, _ in distances) / len(distances),
        "maxMeters": max_distance,
        "maxAtSpline": max_progress,
    }


def classify_trajectory(avg_deviation_meters: Optional[float]) -> str:
    if avg_deviation_meters is None:
        return "INSUFFICIENT_DATA"
    if avg_deviation_meters <= 1.0:
        return "SIMILAR"
    if avg_deviation_meters >= 5.0:
        return "TRAJECTORY_DEVIATION"
    return "DIFFERENT"


def classify_player_vs_reference(
    delta_seconds: Optional[float],
    speed_delta_kmh: Optional[float],
    trajectory_delta_meters: Optional[float],
    player_brake: Mapping[str, Any],
    reference_brake: Mapping[str, Any],
    player_accel: Mapping[str, Any],
    reference_accel: Mapping[str, Any],
) -> Optional[str]:
    if delta_seconds is None:
        return None
    if delta_seconds <= 0.03:
        return "UNKNOWN"

    player_brake_start = _safe_float(player_brake.get("startSpline"))
    reference_brake_start = _safe_float(reference_brake.get("startSpline"))
    if (
        player_brake_start is not None
        and reference_brake_start is not None
        and player_brake_start + EVENT_PROGRESS_EPSILON < reference_brake_start
    ):
        return "BRAKING"

    player_accel_start = _safe_float(player_accel.get("startSpline"))
    reference_accel_start = _safe_float(reference_accel.get("startSpline"))
    if (
        player_accel_start is not None
        and reference_accel_start is not None
        and player_accel_start > reference_accel_start + EVENT_PROGRESS_EPSILON
    ):
        return "ACCELERATION"

    if speed_delta_kmh is not None and speed_delta_kmh < -3.0:
        return "SPEED"
    if trajectory_delta_meters is not None and trajectory_delta_meters >= 5.0:
        return "TRAJECTORY"
    return "UNKNOWN"


def classify_opponent(
    delta_to_player_seconds: Optional[float],
    speed_delta_to_player_kmh: Optional[float],
    trajectory_delta_meters: Optional[float],
    opponent_brake: Mapping[str, Any],
    player_brake: Mapping[str, Any],
    opponent_accel: Mapping[str, Any],
    player_accel: Mapping[str, Any],
) -> str:
    if delta_to_player_seconds is None and speed_delta_to_player_kmh is None:
        return "INSUFFICIENT_DATA"

    opponent_brake_start = _safe_float(opponent_brake.get("startSpline"))
    player_brake_start = _safe_float(player_brake.get("startSpline"))
    if (
        opponent_brake_start is not None
        and player_brake_start is not None
        and opponent_brake_start > player_brake_start + EVENT_PROGRESS_EPSILON
    ):
        return "OPPONENT_BRAKES_LATER"

    opponent_accel_start = _safe_float(opponent_accel.get("startSpline"))
    player_accel_start = _safe_float(player_accel.get("startSpline"))
    if (
        opponent_accel_start is not None
        and player_accel_start is not None
        and opponent_accel_start + EVENT_PROGRESS_EPSILON < player_accel_start
    ):
        return "OPPONENT_ACCELERATES_EARLIER"

    if delta_to_player_seconds is not None:
        if delta_to_player_seconds < -0.04:
            return "OPPONENT_FASTER"
        if delta_to_player_seconds > 0.04:
            return "PLAYER_FASTER"
    if speed_delta_to_player_kmh is not None:
        if speed_delta_to_player_kmh > 3.0:
            return "OPPONENT_HIGHER_SPEED"
        if speed_delta_to_player_kmh < -3.0:
            return "PLAYER_HIGHER_SPEED"
    if trajectory_delta_meters is not None and trajectory_delta_meters >= 5.0:
        return "TRAJECTORY_DEVIATION"
    return "SIMILAR"


def _lap_duration(samples: Sequence[AnalysisSample]) -> Optional[float]:
    session_times = [sample.timestamp for sample in samples if sample.timestamp is not None]
    if len(session_times) >= 2:
        duration = max(session_times) - min(session_times)
        return duration if duration >= 0.0 else None
    return None


def _is_valid_reference_lap(samples: Sequence[AnalysisSample]) -> bool:
    if len(samples) < MIN_VALID_REFERENCE_SAMPLES:
        return False
    progress_values = [sample.progress for sample in samples if sample.progress is not None]
    if not progress_values:
        return False
    if min(progress_values) > VALID_REFERENCE_START_PROGRESS or max(progress_values) < VALID_REFERENCE_END_PROGRESS:
        return False
    duration = _lap_duration(samples)
    if duration is not None and (
        duration < MIN_VALID_REFERENCE_DURATION_SECONDS or duration > MAX_VALID_REFERENCE_DURATION_SECONDS
    ):
        return False
    return True


def select_current_and_reference_samples(
    samples: Iterable[TelemetrySample],
) -> Tuple[List[AnalysisSample], List[AnalysisSample], Dict[str, Any]]:
    player_samples = player_analysis_samples(samples)
    if not player_samples:
        return [], [], {"currentLap": None, "referenceLap": None, "referenceRejected": "missing_player_samples"}

    latest_lap = player_samples[-1].lap
    if latest_lap is None:
        return player_samples[-1200:], [], {
            "currentLap": None,
            "referenceLap": None,
            "referenceRejected": "missing_lap_number",
        }

    laps: Dict[int, List[AnalysisSample]] = defaultdict(list)
    for sample in player_samples:
        if sample.lap is not None:
            laps[sample.lap].append(sample)

    current = laps.get(latest_lap, [])
    reference: List[AnalysisSample] = []
    reference_lap_number: Optional[int] = None
    rejected_reason = "no_previous_complete_lap"
    for lap_number in sorted((lap for lap in laps if lap < latest_lap), reverse=True):
        candidate = laps[lap_number]
        if _is_valid_reference_lap(candidate):
            reference = candidate
            reference_lap_number = lap_number
            rejected_reason = None
            break
        rejected_reason = "previous_lap_not_valid_reference"

    return current, reference, {
        "currentLap": latest_lap,
        "referenceLap": reference_lap_number,
        "referenceRejected": rejected_reason,
    }


def _track_length(track_data: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not track_data:
        return None
    return _safe_float(track_data.get("trackLength", track_data.get("track_length")))


def _track_name(track_name: Optional[str], track_data: Optional[Mapping[str, Any]]) -> Optional[str]:
    if track_name:
        return track_name
    if not track_data:
        return None
    name = track_data.get("name") or track_data.get("trackName") or track_data.get("geometryName")
    return str(name) if name else None


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _reason_message(reason: Optional[str]) -> str:
    return {
        "BRAKING": "frear antes",
        "ACCELERATION": "acelerar depois",
        "SPEED": "menor velocidade minima/media",
        "TRAJECTORY": "trajetoria diferente",
        "UNKNOWN": "dados inconclusivos",
    }.get(reason or "UNKNOWN", "dados inconclusivos")


def build_comparison_analysis(
    *,
    player_samples: Sequence[AnalysisSample],
    reference_samples: Sequence[AnalysisSample],
    opponents_by_car_id: Mapping[int, Sequence[AnalysisSample]],
    track_data: Optional[Mapping[str, Any]] = None,
    track_name: Optional[str] = None,
    micro_sector_count: int = 50,
) -> Dict[str, Any]:
    microsectors = build_microsectors(micro_sector_count)
    count = len(microsectors)
    track_length_meters = _track_length(track_data)
    rejection_reasons: Counter[str] = Counter()
    valid_microsector_count = 0
    segments: List[Dict[str, Any]] = []
    opponent_delta_totals: Dict[int, float] = defaultdict(float)
    opponent_valid_counts: Dict[int, int] = defaultdict(int)

    filtered_opponents = {
        int(car_id): list(samples)
        for car_id, samples in opponents_by_car_id.items()
        if int(car_id) != 0
    }

    for segment in microsectors:
        index = int(segment["segmentIndex"])
        start = float(segment["splineStart"])
        end = float(segment["splineEnd"])
        player_segment = samples_in_segment(player_samples, start, end, index, count)
        reference_segment = samples_in_segment(reference_samples, start, end, index, count)
        opponent_segments = {
            car_id: samples_in_segment(samples, start, end, index, count)
            for car_id, samples in filtered_opponents.items()
        }

        if not player_segment:
            rejection_reasons["missing_player_samples"] += 1
        if not reference_segment:
            rejection_reasons["missing_reference_samples"] += 1
        if filtered_opponents and not any(opponent_segments.values()):
            rejection_reasons["missing_opponent_samples"] += 1

        player_stats = speed_stats(player_segment)
        reference_stats = speed_stats(reference_segment)
        segment_distance = estimate_segment_distance(
            [player_segment, reference_segment, *opponent_segments.values()],
            track_length_meters,
            start,
            end,
        )
        player_time = estimate_segment_time_seconds(player_stats["avgSpeedKmh"], segment_distance)
        reference_time = estimate_segment_time_seconds(reference_stats["avgSpeedKmh"], segment_distance)
        player_brake = detect_braking_zone(player_segment)
        reference_brake = detect_braking_zone(reference_segment)
        player_accel = detect_acceleration_zone(player_segment)
        reference_accel = detect_acceleration_zone(reference_segment)
        player_vs_reference_trajectory = trajectory_deviation(player_segment, reference_segment)
        speed_delta = _delta(player_stats["avgSpeedKmh"], reference_stats["avgSpeedKmh"])
        player_reference_delta = _delta(player_time, reference_time)
        main_loss_reason = classify_player_vs_reference(
            player_reference_delta,
            speed_delta,
            player_vs_reference_trajectory["avgMeters"],
            player_brake,
            reference_brake,
            player_accel,
            reference_accel,
        )

        opponent_payloads = []
        for car_id in sorted(opponent_segments):
            opponent_segment = opponent_segments[car_id]
            opponent_stats = speed_stats(opponent_segment)
            opponent_time = estimate_segment_time_seconds(opponent_stats["avgSpeedKmh"], segment_distance)
            delta_to_player = _delta(opponent_time, player_time)
            delta_to_reference = _delta(opponent_time, reference_time)
            if delta_to_player is not None:
                opponent_delta_totals[car_id] += delta_to_player
                opponent_valid_counts[car_id] += 1

            opponent_brake = detect_braking_zone(opponent_segment)
            opponent_accel = detect_acceleration_zone(opponent_segment)
            opponent_trajectory = trajectory_deviation(opponent_segment, player_segment)
            opponent_speed_delta = _delta(opponent_stats["avgSpeedKmh"], player_stats["avgSpeedKmh"])
            opponent_brake_start = _safe_float(opponent_brake.get("startSpline"))
            player_brake_start = _safe_float(player_brake.get("startSpline"))
            opponent_accel_start = _safe_float(opponent_accel.get("startSpline"))
            player_accel_start = _safe_float(player_accel.get("startSpline"))

            braking_earlier = None
            if opponent_brake_start is not None and player_brake_start is not None:
                braking_earlier = opponent_brake_start + EVENT_PROGRESS_EPSILON < player_brake_start

            accelerating_earlier = None
            if opponent_accel_start is not None and player_accel_start is not None:
                accelerating_earlier = opponent_accel_start + EVENT_PROGRESS_EPSILON < player_accel_start

            opponent_payloads.append(
                {
                    "carId": car_id,
                    "avgSpeedKmh": _round_or_none(opponent_stats["avgSpeedKmh"], 3),
                    "minSpeedKmh": _round_or_none(opponent_stats["minSpeedKmh"], 3),
                    "maxSpeedKmh": _round_or_none(opponent_stats["maxSpeedKmh"], 3),
                    "deltaToPlayerSeconds": _round_or_none(delta_to_player, 4),
                    "deltaToReferenceSeconds": _round_or_none(delta_to_reference, 4),
                    "trajectoryDeviationMeters": _round_or_none(opponent_trajectory["avgMeters"], 3),
                    "brakingEarlierThanPlayer": braking_earlier,
                    "acceleratingEarlierThanPlayer": accelerating_earlier,
                    "classification": classify_opponent(
                        delta_to_player,
                        opponent_speed_delta,
                        opponent_trajectory["avgMeters"],
                        opponent_brake,
                        player_brake,
                        opponent_accel,
                        player_accel,
                    ),
                    "braking": opponent_brake,
                    "acceleration": opponent_accel,
                    "trajectoryClassification": classify_trajectory(opponent_trajectory["avgMeters"]),
                }
            )

        has_valid_comparison = (
            player_stats["avgSpeedKmh"] is not None
            and (reference_stats["avgSpeedKmh"] is not None or any(item["avgSpeedKmh"] is not None for item in opponent_payloads))
        )
        if has_valid_comparison:
            valid_microsector_count += 1

        segments.append(
            {
                **segment,
                "player": {key: _round_or_none(value, 3) for key, value in player_stats.items()},
                "reference": {key: _round_or_none(value, 3) for key, value in reference_stats.items()},
                "opponents": opponent_payloads,
                "playerVsReference": {
                    "deltaSeconds": _round_or_none(player_reference_delta, 4),
                    "speedDeltaKmh": _round_or_none(speed_delta, 3),
                    "trajectoryDeviationMeters": _round_or_none(player_vs_reference_trajectory["avgMeters"], 3),
                    "mainLossReason": main_loss_reason,
                    "braking": player_brake,
                    "referenceBraking": reference_brake,
                    "acceleration": player_accel,
                    "referenceAcceleration": reference_accel,
                    "trajectoryClassification": classify_trajectory(player_vs_reference_trajectory["avgMeters"]),
                },
            }
        )

    sector_payloads = []
    for sector_id in (1, 2, 3):
        sector_segments = [segment for segment in segments if segment["sector"] == sector_id]
        deltas = [
            segment["playerVsReference"]["deltaSeconds"]
            for segment in sector_segments
            if segment["playerVsReference"]["deltaSeconds"] is not None
        ]
        sector_delta = sum(deltas) if deltas else None
        loss_reasons = [
            segment["playerVsReference"]["mainLossReason"]
            for segment in sector_segments
            if segment["playerVsReference"]["deltaSeconds"] is not None
            and segment["playerVsReference"]["deltaSeconds"] > 0.03
            and segment["playerVsReference"]["mainLossReason"]
        ]
        worst_segment = None
        losses = [
            segment
            for segment in sector_segments
            if segment["playerVsReference"]["deltaSeconds"] is not None
        ]
        if losses:
            worst_segment = max(losses, key=lambda item: item["playerVsReference"]["deltaSeconds"])["segmentIndex"]

        opponent_sector_totals: Dict[int, float] = defaultdict(float)
        opponent_sector_counts: Dict[int, int] = defaultdict(int)
        for segment in sector_segments:
            for opponent in segment["opponents"]:
                delta = opponent["deltaToPlayerSeconds"]
                if delta is None:
                    continue
                opponent_sector_totals[opponent["carId"]] += delta
                opponent_sector_counts[opponent["carId"]] += 1
        best_opponent = None
        if opponent_sector_totals:
            best_opponent = min(opponent_sector_totals, key=lambda car_id: opponent_sector_totals[car_id])

        sector_payloads.append(
            {
                "sector": sector_id,
                "playerVsReferenceDeltaSeconds": _round_or_none(sector_delta, 4),
                "mainLossReason": Counter(loss_reasons).most_common(1)[0][0] if loss_reasons else None,
                "bestOpponentCarId": best_opponent,
                "worstSegmentIndex": worst_segment,
            }
        )

    losses = [
        segment
        for segment in segments
        if segment["playerVsReference"]["deltaSeconds"] is not None
        and segment["playerVsReference"]["deltaSeconds"] > 0.03
    ]
    gains = [
        segment
        for segment in segments
        if segment["playerVsReference"]["deltaSeconds"] is not None
        and segment["playerVsReference"]["deltaSeconds"] < -0.03
    ]

    biggest_losses = []
    for segment in sorted(losses, key=lambda item: item["playerVsReference"]["deltaSeconds"], reverse=True)[:5]:
        delta = segment["playerVsReference"]["deltaSeconds"]
        reason = segment["playerVsReference"]["mainLossReason"]
        biggest_losses.append(
            {
                "segmentIndex": segment["segmentIndex"],
                "sector": segment["sector"],
                "splineStart": segment["splineStart"],
                "splineEnd": segment["splineEnd"],
                "deltaSeconds": delta,
                "reason": reason,
                "message": (
                    f"Voce perde aproximadamente {abs(delta):.2f}s no setor {segment['sector']} por {_reason_message(reason)}."
                    if delta is not None
                    else "Dados insuficientes para classificar este trecho."
                ),
            }
        )

    biggest_gains = []
    for segment in sorted(gains, key=lambda item: item["playerVsReference"]["deltaSeconds"])[:5]:
        delta = segment["playerVsReference"]["deltaSeconds"]
        biggest_gains.append(
            {
                "segmentIndex": segment["segmentIndex"],
                "sector": segment["sector"],
                "splineStart": segment["splineStart"],
                "splineEnd": segment["splineEnd"],
                "deltaSeconds": delta,
                "reason": segment["playerVsReference"]["mainLossReason"],
                "message": (
                    f"Voce ganha aproximadamente {abs(delta):.2f}s no setor {segment['sector']}."
                    if delta is not None
                    else "Dados insuficientes para classificar este trecho."
                ),
            }
        )

    opponent_ranking = [
        {
            "carId": car_id,
            "estimatedAdvantageSeconds": _round_or_none(delta_total, 4),
            "validSegments": opponent_valid_counts[car_id],
        }
        for car_id, delta_total in sorted(opponent_delta_totals.items(), key=lambda item: item[1])
    ]

    return {
        "track": _track_name(track_name, track_data),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "microSectorCount": count,
        "sectors": sector_payloads,
        "biggestLosses": biggest_losses,
        "biggestGains": biggest_gains,
        "opponentRanking": opponent_ranking,
        "segments": segments,
        "debug": {
            "playerSamples": len(player_samples),
            "referenceSamples": len(reference_samples),
            "opponentsAnalyzed": len(filtered_opponents),
            "validMicroSectors": valid_microsector_count,
            "rejectedSegments": sum(rejection_reasons.values()),
            "rejectionReasons": dict(rejection_reasons),
            "notes": [
                "Opponent braking/acceleration uses speed trend inference when throttle/brake channels are unavailable.",
                "Opponent yaw, racePosition and sessionTime are never required for comparison.",
            ],
        },
    }


def build_live_comparison_payload(
    *,
    telemetry_samples: Sequence[TelemetrySample],
    opponent_history: Mapping[int, Sequence[OpponentCarState]],
    track_data: Optional[Mapping[str, Any]] = None,
    track_name: Optional[str] = None,
    micro_sector_count: int = 50,
) -> Dict[str, Any]:
    current_samples, reference_samples, lap_debug = select_current_and_reference_samples(telemetry_samples)
    opponents_by_car_id = {
        car_id: opponent_analysis_samples(samples)
        for car_id, samples in opponent_history.items()
        if int(car_id) != 0
    }
    payload = build_comparison_analysis(
        player_samples=current_samples,
        reference_samples=reference_samples,
        opponents_by_car_id=opponents_by_car_id,
        track_data=track_data,
        track_name=track_name,
        micro_sector_count=micro_sector_count,
    )
    payload["debug"]["lapSelection"] = lap_debug
    return payload
