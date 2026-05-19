import math
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple


Point = List[float]

VISUAL_GEOMETRY_VERSION = 7
TRACK_VISUAL_GEOMETRY_MODEL_VERSION = 2
TRACK_VISUAL_RIBBON_VERSION = "2-ribbon"

DEFAULT_VISUAL_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "visualSurfaces": ["ROAD"],
    "useRoadOnly": False,
    "visualRenderMode": "ribbon",
    "artifactFixEnabled": True,
    "widthMedianWindow": 9,
    "widthSmoothingWindow": 11,
    "artifactWidthMedianWindow": 31,
    "artifactWidthSmoothingWindow": 25,
    "maxWidthDeltaPerSample": 1.2,
    "minWidth": 6.0,
    "maxWidth": 22.0,
    "centerlineSmoothingEnabled": True,
    "centerlineSmoothingWindow": 15,
    "centerlineSmoothingStrength": 0.1,
    "centerlineArtifactSmoothingStrength": 0.32,
    "curvatureOutlierThreshold": "auto",
    "normalRecompute": True,
    "normalSmoothingWindow": 21,
    "edgeSmoothingWindow": 23,
    "artifactRepairRadius": 8,
    "angleSpikeRadians": 0.55,
    "falseCurveAngleRadians": 0.24,
    "falseCurveCenterlineAngleRadians": 0.18,
    "falseCurveDeviationMeters": 0.85,
    "segmentSpikeMultiplier": 2.8,
    "localRepairEnabled": False,
    "localRepairWindow": 9,
    "localRepairMaxDisplacement": 1.0,
    "localRepairCurvatureZScore": 3.0,
    "localRepairMinSegmentCount": 3,
    "localRepairMaxSegmentCount": 21,
    "ribbonCenterlineSmoothingWindow": 49,
    "ribbonCenterlineSmoothingStrength": 0.72,
    "ribbonCenterlineMaxDisplacement": 0.95,
    "ribbonMinWidth": 10.5,
    "ribbonMaxWidth": 13.5,
}


def _round(value: float) -> float:
    return round(float(value), 6)


def _point(point: Sequence[float]) -> Point:
    return [_round(point[0]), _round(point[1])]


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _window_size(value: int) -> int:
    size = max(1, int(value))
    return size if size % 2 == 1 else size + 1


def _circular_values(values: Sequence[float], index: int, window: int) -> List[float]:
    if not values:
        return []
    half = _window_size(window) // 2
    total = len(values)
    return [float(values[(index + offset) % total]) for offset in range(-half, half + 1)]


def _median_filter(values: Sequence[float], window: int) -> List[float]:
    if not values:
        return []
    window = _window_size(window)
    return [float(median(_circular_values(values, index, window))) for index in range(len(values))]


def _moving_average(values: Sequence[float], window: int) -> List[float]:
    if not values:
        return []
    window = _window_size(window)
    return [sum(_circular_values(values, index, window)) / window for index in range(len(values))]


def _smooth_points(points: Sequence[Sequence[float]], window: int) -> List[Point]:
    if not points:
        return []
    window = _window_size(window)
    half = window // 2
    smoothed: List[Point] = []
    for index in range(len(points)):
        sx = 0.0
        sy = 0.0
        for offset in range(-half, half + 1):
            point = points[(index + offset) % len(points)]
            sx += float(point[0])
            sy += float(point[1])
        smoothed.append(_point([sx / window, sy / window]))
    return smoothed


def _blend_points(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]], alpha: float) -> List[Point]:
    return [
        _point(
            [
                float(pa[0]) + (float(pb[0]) - float(pa[0])) * alpha,
                float(pa[1]) + (float(pb[1]) - float(pa[1])) * alpha,
            ]
        )
        for pa, pb in zip(a, b)
    ]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def _limit_delta(values: Sequence[float], max_delta: float) -> List[float]:
    if not values:
        return []
    limited = [float(values[0])]
    for value in values[1:]:
        previous = limited[-1]
        limited.append(previous + _clamp(float(value) - previous, -max_delta, max_delta))
    if len(limited) > 2:
        closing_delta = limited[0] - limited[-1]
        if abs(closing_delta) > max_delta:
            correction = (closing_delta - math.copysign(max_delta, closing_delta)) / len(limited)
            limited = [value + correction * index for index, value in enumerate(limited)]
    return limited


def _stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"min": None, "avg": None, "max": None}
    return {
        "min": _round(min(values)),
        "avg": _round(sum(values) / len(values)),
        "max": _round(max(values)),
    }


def _max_abs_delta(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    deltas = [abs(float(values[(index + 1) % len(values)]) - float(values[index])) for index in range(len(values))]
    return _round(max(deltas)) if deltas else None


def _median_abs_deviation(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    med = float(median(values))
    return float(median([abs(float(value) - med) for value in values]))


def _closed_distances(points: Sequence[Sequence[float]]) -> Tuple[List[float], float, float]:
    if not points:
        return [], 0.0, 0.0
    distances = [0.0]
    for index in range(1, len(points)):
        distances.append(distances[-1] + _distance(points[index - 1], points[index]))
    if len(points) > 1:
        total_length = distances[-1] + _distance(points[-1], points[0])
    else:
        total_length = 0.0
    avg_spacing = total_length / len(points) if points else 0.0
    return distances, total_length, avg_spacing


def _circular_distance(distances: Sequence[float], total_length: float, a_index: int, b_index: int) -> float:
    if not distances or total_length <= 1e-9:
        return 0.0
    direct = abs(float(distances[b_index]) - float(distances[a_index]))
    return min(direct, max(0.0, total_length - direct))


def _distance_weighted_smooth_points(points: Sequence[Sequence[float]], window: int) -> List[Point]:
    if not points:
        return []
    window = _window_size(window)
    distances, total_length, avg_spacing = _closed_distances(points)
    if total_length <= 1e-9 or avg_spacing <= 1e-9:
        return [_point(point) for point in points]

    radius = max(avg_spacing, avg_spacing * window * 0.5)
    max_steps = min(len(points) // 2, max(window * 3, 1))
    smoothed: List[Point] = []
    for index, point in enumerate(points):
        sx = 0.0
        sy = 0.0
        sw = 0.0
        for offset in range(-max_steps, max_steps + 1):
            candidate_index = (index + offset) % len(points)
            distance = _circular_distance(distances, total_length, index, candidate_index)
            if distance > radius:
                continue
            normalized = distance / radius if radius > 1e-9 else 0.0
            weight = (1.0 - normalized * normalized) ** 2
            candidate = points[candidate_index]
            sx += float(candidate[0]) * weight
            sy += float(candidate[1]) * weight
            sw += weight
        if sw <= 1e-9:
            smoothed.append(_point(point))
        else:
            smoothed.append(_point([sx / sw, sy / sw]))
    return smoothed


def _bounds(*series: Sequence[Sequence[float]]) -> Dict[str, float]:
    points = [point for points in series for point in points]
    if not points:
        return {}
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {
        "minX": _round(min(xs)),
        "maxX": _round(max(xs)),
        "minY": _round(min(ys)),
        "maxY": _round(max(ys)),
        "width": _round(max(xs) - min(xs)),
        "height": _round(max(ys) - min(ys)),
    }


def _angle_delta(a: Sequence[float], b: Sequence[float]) -> float:
    al = math.hypot(float(a[0]), float(a[1]))
    bl = math.hypot(float(b[0]), float(b[1]))
    if al <= 1e-9 or bl <= 1e-9:
        return 0.0
    dot = max(-1.0, min(1.0, (float(a[0]) * float(b[0]) + float(a[1]) * float(b[1])) / (al * bl)))
    return abs(math.acos(dot))


def _point_angle_delta(points: Sequence[Sequence[float]], index: int) -> float:
    if len(points) < 3:
        return 0.0
    prev_point = points[(index - 1) % len(points)]
    point = points[index]
    next_point = points[(index + 1) % len(points)]
    prev_vector = [float(point[0]) - float(prev_point[0]), float(point[1]) - float(prev_point[1])]
    next_vector = [float(next_point[0]) - float(point[0]), float(next_point[1]) - float(point[1])]
    return _angle_delta(prev_vector, next_vector)


def _signed_curvature(points: Sequence[Sequence[float]], index: int) -> float:
    if len(points) < 3:
        return 0.0
    prev_point = points[(index - 1) % len(points)]
    point = points[index]
    next_point = points[(index + 1) % len(points)]
    ax, ay = float(point[0]) - float(prev_point[0]), float(point[1]) - float(prev_point[1])
    bx, by = float(next_point[0]) - float(point[0]), float(next_point[1]) - float(point[1])
    len_a = math.hypot(ax, ay)
    len_b = math.hypot(bx, by)
    if len_a <= 1e-9 or len_b <= 1e-9:
        return 0.0
    cross = ax * by - ay * bx
    dot = ax * bx + ay * by
    signed_angle = math.atan2(cross, dot)
    return signed_angle / max((len_a + len_b) * 0.5, 1e-9)


def _local_trend_deviation(points: Sequence[Sequence[float]], index: int, span: int = 6) -> float:
    count = len(points)
    if count < span * 2 + 1:
        return 0.0
    start = points[(index - span) % count]
    point = points[index]
    end = points[(index + span) % count]
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    px, py = float(point[0]), float(point[1])
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return _distance(point, start)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx, cy = ax + dx * t, ay + dy * t
    return math.hypot(px - cx, py - cy)


def _tangent(points: Sequence[Sequence[float]], index: int) -> Point:
    if len(points) < 2:
        return [1.0, 0.0]
    prev_point = points[(index - 1) % len(points)]
    next_point = points[(index + 1) % len(points)]
    tx = float(next_point[0]) - float(prev_point[0])
    ty = float(next_point[1]) - float(prev_point[1])
    length = math.hypot(tx, ty)
    if length <= 1e-9:
        return [1.0, 0.0]
    return [tx / length, ty / length]


def _fallback_normal(points: Sequence[Sequence[float]], index: int) -> Point:
    tangent = _tangent(points, index)
    return [-tangent[1], tangent[0]]


def _normalize_vector(vector: Sequence[float], fallback: Sequence[float]) -> Point:
    length = math.hypot(float(vector[0]), float(vector[1]))
    if length <= 1e-9:
        return [float(fallback[0]), float(fallback[1])]
    return [float(vector[0]) / length, float(vector[1]) / length]


def _visual_normals(
    centerline: Sequence[Sequence[float]],
    left_edge: Sequence[Sequence[float]],
    right_edge: Sequence[Sequence[float]],
    smoothing_window: int,
) -> List[Point]:
    raw: List[Point] = []
    for index, center in enumerate(centerline):
        fallback = _fallback_normal(centerline, index)
        if index < len(left_edge) and index < len(right_edge):
            vector = [
                float(left_edge[index][0]) - float(right_edge[index][0]),
                float(left_edge[index][1]) - float(right_edge[index][1]),
            ]
            normal = _normalize_vector(vector, fallback)
            if normal[0] * fallback[0] + normal[1] * fallback[1] < 0:
                normal = [-normal[0], -normal[1]]
            raw.append(normal)
        else:
            raw.append(fallback)

    if not raw:
        return []

    window = _window_size(smoothing_window)
    smoothed: List[Point] = []
    for index, normal in enumerate(raw):
        half = window // 2
        sx = 0.0
        sy = 0.0
        for offset in range(-half, half + 1):
            candidate = raw[(index + offset) % len(raw)]
            if candidate[0] * normal[0] + candidate[1] * normal[1] < 0:
                candidate = [-candidate[0], -candidate[1]]
            sx += candidate[0]
            sy += candidate[1]
        smoothed.append(_normalize_vector([sx, sy], normal))
    return smoothed


def _recomputed_normals_from_centerline(
    centerline: Sequence[Sequence[float]],
    reference_left: Sequence[Sequence[float]],
    reference_right: Sequence[Sequence[float]],
    smoothing_window: int,
) -> List[Point]:
    raw: List[Point] = []
    for index, _center in enumerate(centerline):
        normal = _fallback_normal(centerline, index)
        if index < len(reference_left) and index < len(reference_right):
            reference = [
                float(reference_left[index][0]) - float(reference_right[index][0]),
                float(reference_left[index][1]) - float(reference_right[index][1]),
            ]
            if normal[0] * reference[0] + normal[1] * reference[1] < 0:
                normal = [-normal[0], -normal[1]]
        raw.append(normal)

    if not raw:
        return []

    window = _window_size(smoothing_window)
    smoothed: List[Point] = []
    for index, normal in enumerate(raw):
        half = window // 2
        sx = 0.0
        sy = 0.0
        for offset in range(-half, half + 1):
            candidate = raw[(index + offset) % len(raw)]
            if candidate[0] * normal[0] + candidate[1] * normal[1] < 0:
                candidate = [-candidate[0], -candidate[1]]
            sx += candidate[0]
            sy += candidate[1]
        smoothed.append(_normalize_vector([sx, sy], normal))
    return smoothed


def _expand_indices(indices: Sequence[int], count: int, radius: int) -> List[int]:
    if count <= 0:
        return []
    expanded = set()
    for index in indices:
        for offset in range(-radius, radius + 1):
            expanded.add((int(index) + offset) % count)
    return sorted(expanded)


def _replace_width_indices(
    widths: Sequence[float],
    indices: Sequence[int],
    median_window: int,
    smoothing_window: int,
) -> List[float]:
    if not widths:
        return []
    broad = _moving_average(_median_filter(widths, median_window), smoothing_window)
    result = [float(width) for width in widths]
    for index in indices:
        result[int(index) % len(result)] = float(broad[int(index) % len(broad)])
    return [_round(width) for width in result]


def _artifact_record(
    *,
    index: int,
    p_values: Sequence[float],
    edge: str,
    widths: Sequence[float],
    segment_length: float,
    angle_delta: float,
    reason: str,
) -> Dict[str, Any]:
    previous_width = widths[(index - 1) % len(widths)] if widths else None
    next_width = widths[(index + 1) % len(widths)] if widths else None
    return {
        "index": index,
        "p": _round(p_values[index]) if index < len(p_values) else None,
        "edge": edge,
        "localWidth": _round(widths[index]) if index < len(widths) else None,
        "previousWidth": _round(previous_width) if previous_width is not None else None,
        "nextWidth": _round(next_width) if next_width is not None else None,
        "angleDelta": _round(angle_delta),
        "segmentLength": _round(segment_length),
        "reason": reason,
    }


def audit_visual_edge_artifacts(
    centerline: Sequence[Sequence[float]],
    left_edge: Sequence[Sequence[float]],
    right_edge: Sequence[Sequence[float]],
    widths: Sequence[float],
    p_values: Sequence[float],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_VISUAL_CONFIG, **(config or {})}
    artifacts: List[Dict[str, Any]] = []
    width_deltas = [
        abs(float(widths[(index + 1) % len(widths)]) - float(widths[index]))
        for index in range(len(widths))
    ] if widths else []
    segment_lengths = {
        "left": [_distance(left_edge[index], left_edge[(index + 1) % len(left_edge)]) for index in range(len(left_edge))] if left_edge else [],
        "right": [_distance(right_edge[index], right_edge[(index + 1) % len(right_edge)]) for index in range(len(right_edge))] if right_edge else [],
    }
    average_segment = {
        key: (sum(values) / len(values) if values else 0.0)
        for key, values in segment_lengths.items()
    }

    for edge_name, points in (("left", left_edge), ("right", right_edge)):
        if len(points) < 3:
            continue
        for index in range(len(points)):
            prev_vector = [
                float(points[index][0]) - float(points[(index - 1) % len(points)][0]),
                float(points[index][1]) - float(points[(index - 1) % len(points)][1]),
            ]
            next_vector = [
                float(points[(index + 1) % len(points)][0]) - float(points[index][0]),
                float(points[(index + 1) % len(points)][1]) - float(points[index][1]),
            ]
            angle = _angle_delta(prev_vector, next_vector)
            segment_length = segment_lengths[edge_name][index]
            reasons = []
            if angle > float(cfg["angleSpikeRadians"]):
                reasons.append("angle_spike")
            if average_segment[edge_name] and segment_length > average_segment[edge_name] * float(cfg["segmentSpikeMultiplier"]):
                reasons.append("edge_segment_spike")
            if index < len(width_deltas) and width_deltas[index] > float(cfg["maxWidthDeltaPerSample"]):
                reasons.append("width_delta_spike")
            if reasons:
                artifacts.append(
                    _artifact_record(
                        index=index,
                        p_values=p_values,
                        edge=edge_name,
                        widths=widths,
                        segment_length=segment_length,
                        angle_delta=angle,
                        reason=",".join(reasons),
                    )
                )

    artifacts.sort(key=lambda item: (item["index"], item["edge"]))
    return {
        "artifactCount": len(artifacts),
        "artifacts": artifacts[:500],
        "summary": {
            "maxWidthDelta": _round(max(width_deltas)) if width_deltas else None,
            "leftMaxSegmentLength": _round(max(segment_lengths["left"])) if segment_lengths["left"] else None,
            "rightMaxSegmentLength": _round(max(segment_lengths["right"])) if segment_lengths["right"] else None,
            "centerlinePointCount": len(centerline),
            "leftEdgePointCount": len(left_edge),
            "rightEdgePointCount": len(right_edge),
        },
    }


def audit_false_curve_artifacts(
    centerline: Sequence[Sequence[float]],
    left_edge: Sequence[Sequence[float]],
    right_edge: Sequence[Sequence[float]],
    widths: Sequence[float],
    p_values: Sequence[float],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_VISUAL_CONFIG, **(config or {})}
    artifacts: List[Dict[str, Any]] = []
    if len(centerline) < 5:
        return {"config": cfg, "pointCount": len(centerline), "artifactCount": 0, "artifacts": []}

    count = len(centerline)
    center_angles = [_point_angle_delta(centerline, index) for index in range(count)]
    center_deviation = [_local_trend_deviation(centerline, index, span=8) for index in range(count)]
    for edge_name, points in (("left", left_edge), ("right", right_edge)):
        if len(points) != count:
            continue
        for index in range(count):
            edge_angle = _point_angle_delta(points, index)
            edge_deviation = _local_trend_deviation(points, index, span=8)
            width_delta_prev = abs(float(widths[index]) - float(widths[(index - 1) % count])) if widths else 0.0
            width_delta_next = abs(float(widths[(index + 1) % count]) - float(widths[index])) if widths else 0.0
            reasons = []
            if edge_angle > float(cfg["falseCurveAngleRadians"]) and center_angles[index] < float(cfg["falseCurveCenterlineAngleRadians"]):
                reasons.append("edge_turn_not_supported_by_centerline")
            if edge_deviation > float(cfg["falseCurveDeviationMeters"]) and center_deviation[index] < float(cfg["falseCurveDeviationMeters"]) * 0.7:
                reasons.append("edge_deviates_from_neighbor_trend")
            if max(width_delta_prev, width_delta_next) > float(cfg["maxWidthDeltaPerSample"]):
                reasons.append("abrupt_visual_width_delta")
            if center_angles[index] > float(cfg["falseCurveCenterlineAngleRadians"]) * 1.6:
                reasons.append("visual_centerline_angle_spike")
            for reason in reasons:
                artifacts.append(
                    {
                        **_artifact_record(
                            index=index,
                            p_values=p_values,
                            edge=edge_name,
                            widths=widths,
                            segment_length=_distance(points[index], points[(index + 1) % count]),
                            angle_delta=edge_angle,
                            reason=reason,
                        ),
                        "centerlineAngleDelta": _round(center_angles[index]),
                        "edgeTrendDeviation": _round(edge_deviation),
                        "centerlineTrendDeviation": _round(center_deviation[index]),
                    }
                )

    artifacts.sort(key=lambda item: (-max(abs(float(item["angleDelta"])), float(item["edgeTrendDeviation"])), item["index"]))
    unique_indices = sorted({int(item["index"]) for item in artifacts})
    return {
        "config": cfg,
        "pointCount": count,
        "artifactCount": len(artifacts),
        "uniqueArtifactIndexCount": len(unique_indices),
        "artifactIndices": unique_indices,
        "artifacts": artifacts[:800],
        "summary": {
            "leftArtifacts": sum(1 for item in artifacts if item["edge"] == "left"),
            "rightArtifacts": sum(1 for item in artifacts if item["edge"] == "right"),
            "widthStats": _stats(widths),
            "maxCenterlineAngleDelta": _round(max(center_angles) if center_angles else 0.0),
            "maxCenterlineTrendDeviation": _round(max(center_deviation) if center_deviation else 0.0),
        },
    }


def audit_centerline_artifacts(
    centerline: Sequence[Sequence[float]],
    p_values: Sequence[float],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_VISUAL_CONFIG, **(config or {})}
    count = len(centerline)
    if count < 5:
        return {
            "config": cfg,
            "pointCount": count,
            "artifactCount": 0,
            "artifactIndices": [],
            "artifacts": [],
            "topCurvatureOutliers": [],
            "topAngleOutliers": [],
            "summary": {},
        }

    angles = [_point_angle_delta(centerline, index) for index in range(count)]
    signed_curvatures = [_signed_curvature(centerline, index) for index in range(count)]
    abs_curvatures = [abs(value) for value in signed_curvatures]
    trend_deviations = [_local_trend_deviation(centerline, index, span=8) for index in range(count)]
    angle_median = float(median(angles))
    angle_mad = _median_abs_deviation(angles)
    curvature_median = float(median(abs_curvatures))
    curvature_mad = _median_abs_deviation(abs_curvatures)
    trend_median = float(median(trend_deviations))
    trend_mad = _median_abs_deviation(trend_deviations)

    raw_threshold = str(cfg.get("curvatureOutlierThreshold", "auto")).strip().lower()
    if raw_threshold == "auto":
        curvature_threshold = max(curvature_median + curvature_mad * 4.5, curvature_median + 0.012)
    else:
        try:
            curvature_threshold = float(raw_threshold)
        except ValueError:
            curvature_threshold = max(curvature_median + curvature_mad * 4.5, curvature_median + 0.012)
    angle_threshold = max(angle_median + angle_mad * 4.0, float(cfg["falseCurveCenterlineAngleRadians"]))
    trend_threshold = max(trend_median + trend_mad * 4.0, float(cfg["falseCurveDeviationMeters"]) * 0.45)

    artifacts: List[Dict[str, Any]] = []
    for index in range(count):
        reasons = []
        curvature = signed_curvatures[index]
        abs_curvature = abs_curvatures[index]
        angle = angles[index]
        trend = trend_deviations[index]
        prev_curvature = signed_curvatures[(index - 1) % count]
        next_curvature = signed_curvatures[(index + 1) % count]
        sign_flip = (curvature * prev_curvature < 0.0) or (curvature * next_curvature < 0.0)
        if abs_curvature > curvature_threshold:
            reasons.append("curvature_outlier")
        if angle > angle_threshold:
            reasons.append("angle_outlier")
        if sign_flip and abs_curvature > max(curvature_threshold * 0.55, curvature_median + curvature_mad * 2.5):
            reasons.append("short_s_curve_oscillation")
        if trend > trend_threshold and angle > angle_median + angle_mad * 2.0:
            reasons.append("deviates_from_centerline_trend")
        if not reasons:
            continue
        score = abs_curvature / max(curvature_threshold, 1e-9) + angle / max(angle_threshold, 1e-9) + trend / max(trend_threshold, 1e-9)
        artifacts.append(
            {
                "index": index,
                "p": _round(p_values[index]) if index < len(p_values) else None,
                "point": _point(centerline[index]),
                "curvature": _round(curvature),
                "absCurvature": _round(abs_curvature),
                "angleDelta": _round(angle),
                "trendDeviation": _round(trend),
                "score": _round(score),
                "reason": ",".join(reasons),
            }
        )

    artifacts.sort(key=lambda item: (-float(item["score"]), item["index"]))
    top_curvature = sorted(
        [
            {
                "index": index,
                "p": _round(p_values[index]) if index < len(p_values) else None,
                "point": _point(centerline[index]),
                "curvature": _round(signed_curvatures[index]),
                "absCurvature": _round(abs_curvatures[index]),
                "angleDelta": _round(angles[index]),
                "trendDeviation": _round(trend_deviations[index]),
            }
            for index in range(count)
        ],
        key=lambda item: (-float(item["absCurvature"]), item["index"]),
    )[:50]
    top_angle = sorted(
        [
            {
                "index": index,
                "p": _round(p_values[index]) if index < len(p_values) else None,
                "point": _point(centerline[index]),
                "curvature": _round(signed_curvatures[index]),
                "absCurvature": _round(abs_curvatures[index]),
                "angleDelta": _round(angles[index]),
                "trendDeviation": _round(trend_deviations[index]),
            }
            for index in range(count)
        ],
        key=lambda item: (-float(item["angleDelta"]), item["index"]),
    )[:50]
    return {
        "config": cfg,
        "pointCount": count,
        "artifactCount": len(artifacts),
        "artifactIndices": sorted({int(item["index"]) for item in artifacts}),
        "artifacts": artifacts[:500],
        "topCurvatureOutliers": top_curvature,
        "topAngleOutliers": top_angle,
        "summary": {
            "curvatureMedian": _round(curvature_median),
            "curvatureMad": _round(curvature_mad),
            "curvatureThreshold": _round(curvature_threshold),
            "angleMedian": _round(angle_median),
            "angleMad": _round(angle_mad),
            "angleThreshold": _round(angle_threshold),
            "trendMedian": _round(trend_median),
            "trendMad": _round(trend_mad),
            "trendThreshold": _round(trend_threshold),
            "maxAbsCurvature": _round(max(abs_curvatures) if abs_curvatures else 0.0),
            "maxAngleDelta": _round(max(angles) if angles else 0.0),
            "maxTrendDeviation": _round(max(trend_deviations) if trend_deviations else 0.0),
        },
    }


def _points_from_series_payload(series: Dict[str, Any]) -> List[Point]:
    if not series:
        return []
    return [
        _point([x, y])
        for x, y in zip(series.get("x", []), series.get("y", []))
    ]


def _window_angle_delta(points: Sequence[Sequence[float]], index: int, span: int) -> float:
    count = len(points)
    if count < 3:
        return 0.0
    span = max(1, min(int(span), count // 2))
    start = points[(index - span) % count]
    point = points[index]
    end = points[(index + span) % count]
    prev_vector = [float(point[0]) - float(start[0]), float(point[1]) - float(start[1])]
    next_vector = [float(end[0]) - float(point[0]), float(end[1]) - float(point[1])]
    return _angle_delta(prev_vector, next_vector)


def _normal_delta(normals: Sequence[Sequence[float]], index: int, span: int = 1) -> float:
    if len(normals) < 3:
        return 0.0
    span = max(1, int(span))
    return _angle_delta(normals[(index - span) % len(normals)], normals[(index + span) % len(normals)])


def _local_deformation_record(
    *,
    index: int,
    p_values: Sequence[float],
    centerline: Sequence[Sequence[float]],
    widths: Sequence[float],
    reason: str,
    score: float,
    angle_local: float,
    angle_window: float,
    curvature_local: float,
    curvature_median: float,
    curvature_zscore: float,
    edge_deviation: float,
    width_delta: float,
    normal_delta: float,
    window_start: int,
    window_end: int,
) -> Dict[str, Any]:
    return {
        "index": index,
        "p": _round(p_values[index]) if index < len(p_values) else None,
        "reason": reason,
        "score": _round(score),
        "curvatureLocal": _round(curvature_local),
        "curvatureMedian": _round(curvature_median),
        "curvatureZScore": _round(curvature_zscore),
        "angleDelta": _round(angle_local),
        "angleDeltaLocal": _round(angle_local),
        "angleDeltaWindow": _round(angle_window),
        "edgeDeviationFromWindowTrend": _round(edge_deviation),
        "widthDelta": _round(width_delta),
        "normalDelta": _round(normal_delta),
        "width": _round(widths[index]) if index < len(widths) else None,
        "position": _point(centerline[index]),
        "windowStart": window_start,
        "windowEnd": window_end,
    }


def audit_local_visual_deformations(
    centerline: Sequence[Sequence[float]],
    left_edge: Sequence[Sequence[float]],
    right_edge: Sequence[Sequence[float]],
    widths: Sequence[float],
    p_values: Sequence[float],
    *,
    normals: Optional[Sequence[Sequence[float]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_VISUAL_CONFIG, **(config or {})}
    count = len(centerline)
    if count < 7:
        return {
            "config": cfg,
            "pointCount": count,
            "artifactCount": 0,
            "artifactIndices": [],
            "topSuspects": [],
            "summary": {},
        }

    local_window = _window_size(int(cfg["localRepairWindow"]))
    half = local_window // 2
    threshold = float(cfg["localRepairCurvatureZScore"])
    abs_curvatures = [abs(_signed_curvature(centerline, index)) for index in range(count)]
    signed_curvatures = [_signed_curvature(centerline, index) for index in range(count)]
    angles_local = [_point_angle_delta(centerline, index) for index in range(count)]
    angles_window = [_window_angle_delta(centerline, index, half) for index in range(count)]
    visual_normals = list(normals or [])
    if len(visual_normals) != count:
        visual_normals = _recomputed_normals_from_centerline(
            centerline,
            left_edge,
            right_edge,
            int(cfg["normalSmoothingWindow"]),
        )
    edge_deviations = [
        max(
            _local_trend_deviation(left_edge, index, span=half),
            _local_trend_deviation(right_edge, index, span=half),
        )
        for index in range(count)
    ]
    width_deltas = [
        max(
            abs(float(widths[index]) - float(widths[(index - 1) % count])),
            abs(float(widths[(index + 1) % count]) - float(widths[index])),
        )
        for index in range(count)
    ] if widths else [0.0 for _ in range(count)]
    normal_deltas = [_normal_delta(visual_normals, index, span=2) for index in range(count)]

    global_curvature_median = float(median(abs_curvatures))
    global_curvature_mad = max(_median_abs_deviation(abs_curvatures), 1e-6)
    global_angle_median = float(median(angles_local))
    global_angle_mad = max(_median_abs_deviation(angles_local), 1e-6)
    global_edge_median = float(median(edge_deviations))
    global_edge_mad = max(_median_abs_deviation(edge_deviations), 1e-6)
    global_normal_median = float(median(normal_deltas))
    global_normal_mad = max(_median_abs_deviation(normal_deltas), 1e-6)

    suspects: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = []
    for index in range(count):
        local_curvature_values = _circular_values(abs_curvatures, index, local_window)
        local_curvature_median = float(median(local_curvature_values)) if local_curvature_values else 0.0
        local_curvature_mad = max(_median_abs_deviation(local_curvature_values), global_curvature_mad * 0.4, 1e-6)
        curvature_zscore = (abs_curvatures[index] - local_curvature_median) / local_curvature_mad
        angle_zscore = (angles_local[index] - global_angle_median) / global_angle_mad
        edge_zscore = (edge_deviations[index] - global_edge_median) / global_edge_mad
        normal_zscore = (normal_deltas[index] - global_normal_median) / global_normal_mad
        signs = [
            1 if signed_curvatures[(index + offset) % count] > 0 else -1 if signed_curvatures[(index + offset) % count] < 0 else 0
            for offset in range(-half, half + 1)
        ]
        sign_flips = sum(1 for a, b in zip(signs, signs[1:]) if a and b and a != b)
        sustained_ratio = max(signs.count(1), signs.count(-1)) / max(1, len([sign for sign in signs if sign]))
        sustained_real_curve = sustained_ratio > 0.82 and local_curvature_median > global_curvature_median + global_curvature_mad

        reasons: List[str] = []
        if curvature_zscore >= threshold and abs_curvatures[index] > global_curvature_median + global_curvature_mad * 1.3:
            reasons.append("curvature_local_spike")
        if sign_flips >= 2 and curvature_zscore >= threshold * 0.72:
            reasons.append("short_s_curve_oscillation")
        if edge_zscore >= 2.6 and angles_window[index] < max(0.18, global_angle_median + global_angle_mad * 2.0):
            reasons.append("edge_deviates_from_window_trend")
        if normal_zscore >= 2.8 and angles_local[index] > global_angle_median + global_angle_mad * 2.0:
            reasons.append("normal_delta_spike")
        if width_deltas[index] > float(cfg["maxWidthDeltaPerSample"]) * 0.85 and edge_zscore >= 1.6:
            reasons.append("notch_width_edge_delta")
        if sustained_real_curve and "short_s_curve_oscillation" not in reasons and "edge_deviates_from_window_trend" not in reasons:
            reasons = []

        score = (
            max(0.0, curvature_zscore) * 1.45
            + max(0.0, edge_zscore) * 1.05
            + max(0.0, normal_zscore) * 0.75
            + max(0.0, angle_zscore) * 0.35
            + sign_flips * 0.45
        )
        record = _local_deformation_record(
            index=index,
            p_values=p_values,
            centerline=centerline,
            widths=widths,
            reason=",".join(reasons) if reasons else "ranked_suspect",
            score=score,
            angle_local=angles_local[index],
            angle_window=angles_window[index],
            curvature_local=signed_curvatures[index],
            curvature_median=local_curvature_median,
            curvature_zscore=curvature_zscore,
            edge_deviation=edge_deviations[index],
            width_delta=width_deltas[index],
            normal_delta=normal_deltas[index],
            window_start=(index - half) % count,
            window_end=(index + half) % count,
        )
        suspects.append(record)
        if reasons:
            artifacts.append(record)

    suspects.sort(key=lambda item: (-float(item["score"]), item["index"]))
    artifacts.sort(key=lambda item: (-float(item["score"]), item["index"]))
    return {
        "config": cfg,
        "pointCount": count,
        "artifactCount": len(artifacts),
        "artifactIndices": sorted({int(item["index"]) for item in artifacts}),
        "artifacts": artifacts[:300],
        "topSuspects": suspects[:100],
        "summary": {
            "curvatureMedian": _round(global_curvature_median),
            "curvatureMad": _round(global_curvature_mad),
            "angleMedian": _round(global_angle_median),
            "angleMad": _round(global_angle_mad),
            "edgeDeviationMedian": _round(global_edge_median),
            "edgeDeviationMad": _round(global_edge_mad),
            "normalDeltaMedian": _round(global_normal_median),
            "normalDeltaMad": _round(global_normal_mad),
            "maxCurvatureZScore": _round(max((float(item["curvatureZScore"]) for item in suspects), default=0.0)),
            "maxEdgeDeviation": _round(max(edge_deviations) if edge_deviations else 0.0),
            "maxNormalDelta": _round(max(normal_deltas) if normal_deltas else 0.0),
            "threshold": _round(threshold),
        },
    }


def _blend_point_toward_target(point: Sequence[float], target: Sequence[float], alpha: float, max_displacement: float) -> Point:
    dx = float(target[0]) - float(point[0])
    dy = float(target[1]) - float(point[1])
    distance = math.hypot(dx, dy)
    if distance <= 1e-9:
        return _point(point)
    move = min(distance * alpha, max_displacement)
    scale = move / distance
    return _point([float(point[0]) + dx * scale, float(point[1]) + dy * scale])


def _local_curvature_metric(points: Sequence[Sequence[float]], indices: Sequence[int]) -> float:
    if not points or not indices:
        return 0.0
    return sum(abs(_signed_curvature(points, index % len(points))) for index in indices)


def _repair_local_centerline(
    centerline: Sequence[Sequence[float]],
    deformation_report: Dict[str, Any],
    *,
    config: Dict[str, Any],
) -> Tuple[List[Point], Dict[str, Any]]:
    count = len(centerline)
    repaired = [_point(point) for point in centerline]
    if count < 7 or not config.get("localRepairEnabled", False):
        return repaired, {
            "enabled": bool(config.get("localRepairEnabled", False)),
            "repairedSegmentCount": 0,
            "repairedPointCount": 0,
            "maxRepairDisplacement": 0.0,
            "avgRepairDisplacement": 0.0,
            "segments": [],
            "points": [],
        }

    window = _window_size(int(config["localRepairWindow"]))
    min_count = max(3, int(config["localRepairMinSegmentCount"]))
    max_count = max(min_count, int(config["localRepairMaxSegmentCount"]))
    segment_count = max(min_count, min(max_count, window))
    if segment_count % 2 == 0:
        segment_count += 1
    half = segment_count // 2
    max_displacement = float(config["localRepairMaxDisplacement"])
    candidates = [
        item
        for item in deformation_report.get("artifacts", [])
        if float(item.get("curvatureZScore", 0.0)) >= float(config["localRepairCurvatureZScore"]) * 0.72
        or "edge_deviates_from_window_trend" in str(item.get("reason", ""))
        or "short_s_curve_oscillation" in str(item.get("reason", ""))
    ]
    candidates.sort(key=lambda item: (-float(item.get("score", 0.0)), int(item.get("index", 0))))

    used: set[int] = set()
    segments: List[Dict[str, Any]] = []
    repaired_points: List[Dict[str, Any]] = []
    smooth_reference = _distance_weighted_smooth_points(centerline, max(window * 3, 15))
    for candidate in candidates[:48]:
        center_index = int(candidate["index"]) % count
        indices = [(center_index - half + offset) % count for offset in range(segment_count)]
        if any(index in used for index in indices):
            continue
        before_metric = _local_curvature_metric(repaired, indices)
        proposed_points: List[Tuple[int, Point, float]] = []
        for index in indices:
            target = smooth_reference[index] if index < len(smooth_reference) else repaired[index]
            proposed = _blend_point_toward_target(repaired[index], target, 0.55, max_displacement)
            proposed_points.append((index, proposed, _distance(repaired[index], proposed)))

        test_centerline = list(repaired)
        for index, proposed, _distance_value in proposed_points:
            test_centerline[index] = proposed
        after_metric = _local_curvature_metric(test_centerline, indices)
        if after_metric > before_metric * 0.94:
            continue
        max_segment_displacement = max((distance_value for _index, _point_value, distance_value in proposed_points), default=0.0)
        if max_segment_displacement > max_displacement + 1e-9:
            continue
        for index, proposed, distance_value in proposed_points:
            old = repaired[index]
            repaired[index] = proposed
            used.add(index)
            repaired_points.append(
                {
                    "index": index,
                    "oldPosition": _point(old),
                    "newPosition": _point(proposed),
                    "displacement": _round(distance_value),
                    "sourceIndex": center_index,
                    "reason": candidate.get("reason"),
                }
            )
        segments.append(
            {
                "centerIndex": center_index,
                "indices": indices,
                "reason": candidate.get("reason"),
                "score": candidate.get("score"),
                "curvatureMetricBefore": _round(before_metric),
                "curvatureMetricAfter": _round(after_metric),
                "maxDisplacement": _round(max_segment_displacement),
            }
        )

    displacements = [float(item["displacement"]) for item in repaired_points]
    return repaired, {
        "enabled": True,
        "repairedSegmentCount": len(segments),
        "repairedPointCount": len(repaired_points),
        "maxRepairDisplacement": _round(max(displacements) if displacements else 0.0),
        "avgRepairDisplacement": _round(sum(displacements) / len(displacements) if displacements else 0.0),
        "segments": segments,
        "points": repaired_points,
    }


def build_visual_geometry_v3_candidate(
    visual_geometry: Dict[str, Any],
    p_values: Sequence[float],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_VISUAL_CONFIG, **(visual_geometry.get("config") or {}), **(config or {})}
    cfg["localRepairEnabled"] = bool(cfg.get("localRepairEnabled", True))
    centerline = _points_from_series_payload(visual_geometry.get("centerline") or {})
    left_edge = _points_from_series_payload(visual_geometry.get("leftEdge") or visual_geometry.get("left_edge") or {})
    right_edge = _points_from_series_payload(visual_geometry.get("rightEdge") or visual_geometry.get("right_edge") or {})
    widths = [float(width) for width in visual_geometry.get("width") or visual_geometry.get("localWidth") or []]
    normals = [
        [float(normal.get("x", 0.0)), float(normal.get("y", 0.0))]
        for normal in visual_geometry.get("normals", [])
        if isinstance(normal, dict)
    ]
    if not centerline or len(centerline) != len(left_edge) or len(centerline) != len(right_edge) or len(centerline) != len(widths):
        result = dict(visual_geometry)
        result["visualVersion"] = 3
        result["localRepairEnabled"] = bool(cfg.get("localRepairEnabled", True))
        result["localRepairError"] = "inconsistent_point_counts"
        return result

    before_report = audit_local_visual_deformations(
        centerline,
        left_edge,
        right_edge,
        widths,
        p_values,
        normals=normals,
        config=cfg,
    )
    repaired_centerline, repair_report = _repair_local_centerline(
        centerline,
        before_report,
        config=cfg,
    )
    repaired_normals = _recomputed_normals_from_centerline(
        repaired_centerline,
        left_edge,
        right_edge,
        int(cfg["normalSmoothingWindow"]),
    )
    repaired_left: List[Point] = []
    repaired_right: List[Point] = []
    for index, center in enumerate(repaired_centerline):
        normal = repaired_normals[index] if index < len(repaired_normals) else _fallback_normal(repaired_centerline, index)
        half_width = float(widths[index]) * 0.5
        repaired_left.append(_point([float(center[0]) + normal[0] * half_width, float(center[1]) + normal[1] * half_width]))
        repaired_right.append(_point([float(center[0]) - normal[0] * half_width, float(center[1]) - normal[1] * half_width]))
    repaired_widths = [_round(_distance(left, right)) for left, right in zip(repaired_left, repaired_right)]
    after_report = audit_local_visual_deformations(
        repaired_centerline,
        repaired_left,
        repaired_right,
        repaired_widths,
        p_values,
        normals=repaired_normals,
        config=cfg,
    )
    local_detected = int(before_report.get("artifactCount", 0))
    local_after = int(after_report.get("artifactCount", 0))
    local_repaired = int(repair_report.get("repairedPointCount", 0))
    stats = _stats(repaired_widths)
    metadata = {
        **(visual_geometry.get("metadata") or {}),
        "visualVersion": 3,
        "localRepairEnabled": bool(cfg.get("localRepairEnabled", True)),
        "localDeformationsDetected": local_detected,
        "localDeformationsRepaired": local_repaired,
        "maxRepairDisplacement": repair_report.get("maxRepairDisplacement"),
        "avgRepairDisplacement": repair_report.get("avgRepairDisplacement"),
    }
    result = {
        **visual_geometry,
        "visualVersion": 3,
        "localRepairEnabled": bool(cfg.get("localRepairEnabled", True)),
        "localDeformationsDetected": local_detected,
        "localDeformationsRepaired": local_repaired,
        "localDeformationsRemaining": local_after,
        "maxRepairDisplacement": repair_report.get("maxRepairDisplacement"),
        "avgRepairDisplacement": repair_report.get("avgRepairDisplacement"),
        "centerline": _series_payload(repaired_centerline),
        "leftEdge": _series_payload(repaired_left),
        "rightEdge": _series_payload(repaired_right),
        "left_edge": _series_payload(repaired_left),
        "right_edge": _series_payload(repaired_right),
        "width": repaired_widths,
        "localWidth": repaired_widths,
        "widthMin": stats["min"],
        "widthAvg": stats["avg"],
        "widthMax": stats["max"],
        "bounds": _bounds(repaired_left, repaired_right, repaired_centerline),
        "config": cfg,
        "metadata": metadata,
        "normals": [{"x": _round(normal[0]), "y": _round(normal[1])} for normal in repaired_normals],
        "localDeformationReport": before_report,
        "localDeformationReportAfter": after_report,
        "localRepairReport": repair_report,
        "debugGeometry": {
            **(visual_geometry.get("debugGeometry") or {}),
            "v2Centerline": visual_geometry.get("centerline"),
        },
    }
    return result


def _ribbon_width(widths: Sequence[float], cfg: Dict[str, Any]) -> float:
    if not widths:
        return _round(float(cfg["ribbonMinWidth"]))
    avg_width = sum(float(width) for width in widths) / len(widths)
    return _round(_clamp(avg_width, float(cfg["ribbonMinWidth"]), float(cfg["ribbonMaxWidth"])))


def _build_ribbon_geometry(
    centerline: Sequence[Sequence[float]],
    widths: Sequence[float],
    orientation_left: Sequence[Sequence[float]],
    orientation_right: Sequence[Sequence[float]],
    *,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    if not centerline:
        return {}
    smooth_reference = _distance_weighted_smooth_points(
        centerline,
        int(config["ribbonCenterlineSmoothingWindow"]),
    )
    strength = float(config["ribbonCenterlineSmoothingStrength"])
    max_displacement = float(config["ribbonCenterlineMaxDisplacement"])
    ribbon_centerline = [
        _blend_point_toward_target(point, smooth_reference[index], strength, max_displacement)
        for index, point in enumerate(centerline)
    ]
    displacements = [_distance(point, ribbon_centerline[index]) for index, point in enumerate(centerline)]
    ribbon_width = _ribbon_width(widths, config)
    normals = _recomputed_normals_from_centerline(
        ribbon_centerline,
        orientation_left,
        orientation_right,
        int(config["normalSmoothingWindow"]),
    )
    tangents = [_tangent(ribbon_centerline, index) for index in range(len(ribbon_centerline))]
    half_width = ribbon_width * 0.5
    left = [
        _point([float(center[0]) + normals[index][0] * half_width, float(center[1]) + normals[index][1] * half_width])
        for index, center in enumerate(ribbon_centerline)
    ]
    right = [
        _point([float(center[0]) - normals[index][0] * half_width, float(center[1]) - normals[index][1] * half_width])
        for index, center in enumerate(ribbon_centerline)
    ]
    return {
        "renderMode": "stroke_ribbon",
        "visualOnly": True,
        "source": "smoothed_centerline_ribbon",
        "physicsUnaffected": True,
        "centerline": _series_payload(ribbon_centerline),
        "width": ribbon_width,
        "widthProfile": [ribbon_width for _ in ribbon_centerline],
        "ribbonWidthMeters": ribbon_width,
        "closedLoop": True,
        "bounds": _bounds(left, right, ribbon_centerline),
        "leftEdgePreview": _series_payload(left),
        "rightEdgePreview": _series_payload(right),
        "normals": [{"x": _round(normal[0]), "y": _round(normal[1])} for normal in normals],
        "tangents": [{"x": _round(tangent[0]), "y": _round(tangent[1])} for tangent in tangents],
        "metadata": {
            "visualOnly": True,
            "source": "smoothed_centerline_ribbon",
            "physicsUnaffected": True,
            "centerlineSmoothingWindow": int(config["ribbonCenterlineSmoothingWindow"]),
            "centerlineSmoothingStrength": float(config["ribbonCenterlineSmoothingStrength"]),
            "centerlineMaxDisplacement": _round(max(displacements) if displacements else 0.0),
            "centerlineAvgDisplacement": _round(sum(displacements) / len(displacements) if displacements else 0.0),
            "ribbonWidthMeters": ribbon_width,
            "ribbonMinWidth": float(config["ribbonMinWidth"]),
            "ribbonMaxWidth": float(config["ribbonMaxWidth"]),
        },
    }


def _series_payload(points: Sequence[Sequence[float]]) -> Dict[str, List[float]]:
    return {
        "x": [_round(point[0]) for point in points],
        "y": [_round(point[1]) for point in points],
    }


class TrackVisualGeometryBuilder:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_VISUAL_CONFIG, **(config or {})}

    def _visual_widths(self, widths: Sequence[float]) -> List[float]:
        if not widths:
            return []
        clamped = [_clamp(width, self.config["minWidth"], self.config["maxWidth"]) for width in widths]
        medianed = _median_filter(clamped, int(self.config["widthMedianWindow"]))
        limited = _limit_delta(medianed, float(self.config["maxWidthDeltaPerSample"]))
        averaged = _moving_average(limited, int(self.config["widthSmoothingWindow"]))
        return [_round(_clamp(width, self.config["minWidth"], self.config["maxWidth"])) for width in averaged]

    def _legacy_visual_centerline(self, centerline: Sequence[Sequence[float]], repair_indices: Sequence[int]) -> List[Point]:
        if not centerline:
            return []
        broad = _smooth_points(centerline, int(self.config["centerlineSmoothingWindow"]))
        base = _blend_points(centerline, broad, 0.32)
        if self.config.get("artifactFixEnabled", True) and repair_indices:
            expanded = _expand_indices(repair_indices, len(centerline), int(self.config["artifactRepairRadius"]))
            smooth = _smooth_points(base, int(self.config["centerlineSmoothingWindow"]))
            for index in expanded:
                base[index] = smooth[index]
        return base

    def _visual_centerline_v2(self, centerline: Sequence[Sequence[float]], repair_indices: Sequence[int]) -> List[Point]:
        if not centerline:
            return []
        if not self.config.get("centerlineSmoothingEnabled", True):
            return [_point(point) for point in centerline]

        smooth = _distance_weighted_smooth_points(centerline, int(self.config["centerlineSmoothingWindow"]))
        base = _blend_points(centerline, smooth, float(self.config["centerlineSmoothingStrength"]))
        if self.config.get("artifactFixEnabled", True) and repair_indices:
            expanded = _expand_indices(repair_indices, len(centerline), int(self.config["artifactRepairRadius"]))
            stronger = _blend_points(centerline, smooth, float(self.config["centerlineArtifactSmoothingStrength"]))
            for index in expanded:
                base[index] = stronger[index]
        return base

    def _build_edges(
        self,
        centerline: Sequence[Sequence[float]],
        orientation_left: Sequence[Sequence[float]],
        orientation_right: Sequence[Sequence[float]],
        widths: Sequence[float],
    ) -> Tuple[List[Point], List[Point], List[Point], List[Point]]:
        visual_left: List[Point] = []
        visual_right: List[Point] = []
        normals: List[Point] = []
        if self.config.get("normalRecompute", True):
            visual_normals = _recomputed_normals_from_centerline(
                centerline,
                orientation_left,
                orientation_right,
                int(self.config["normalSmoothingWindow"]),
            )
        else:
            visual_normals = _visual_normals(
                centerline,
                orientation_left,
                orientation_right,
                int(self.config["normalSmoothingWindow"]),
            )
        for index, center in enumerate(centerline):
            normal = visual_normals[index] if index < len(visual_normals) else _fallback_normal(centerline, index)
            width = float(widths[index]) if index < len(widths) else float(self.config["minWidth"])
            half_width = width * 0.5
            normals.append(_point(normal))
            visual_left.append(_point([float(center[0]) + normal[0] * half_width, float(center[1]) + normal[1] * half_width]))
            visual_right.append(_point([float(center[0]) - normal[0] * half_width, float(center[1]) - normal[1] * half_width]))
        if not self.config.get("normalRecompute", True):
            visual_left = _smooth_points(visual_left, int(self.config["edgeSmoothingWindow"]))
            visual_right = _smooth_points(visual_right, int(self.config["edgeSmoothingWindow"]))
            visual_centerline = [
                _point([(left[0] + right[0]) * 0.5, (left[1] + right[1]) * 0.5])
                for left, right in zip(visual_left, visual_right)
            ]
        else:
            visual_centerline = [_point(point) for point in centerline]
        return visual_centerline, visual_left, visual_right, normals

    def build(
        self,
        centerline: Sequence[Sequence[float]],
        left_edge: Sequence[Sequence[float]],
        right_edge: Sequence[Sequence[float]],
        widths: Sequence[float],
        p_values: Sequence[float],
    ) -> Dict[str, Any]:
        raw_widths = [float(width) for width in widths]
        artifact_report = audit_visual_edge_artifacts(
            centerline,
            left_edge,
            right_edge,
            raw_widths,
            p_values,
            config=self.config,
        )
        centerline_artifact_report_before = audit_centerline_artifacts(
            centerline,
            p_values,
            config=self.config,
        )
        initial_widths = self._visual_widths(raw_widths)
        initial_centerline = self._legacy_visual_centerline(centerline, [])
        original_normal_recompute = self.config.get("normalRecompute", True)
        self.config["normalRecompute"] = False
        preliminary_centerline, preliminary_left, preliminary_right, _ = self._build_edges(
            initial_centerline,
            left_edge,
            right_edge,
            initial_widths,
        )
        self.config["normalRecompute"] = original_normal_recompute
        preliminary_widths = [_round(_distance(left, right)) for left, right in zip(preliminary_left, preliminary_right)]
        false_curve_report_before = audit_false_curve_artifacts(
            preliminary_centerline,
            preliminary_left,
            preliminary_right,
            preliminary_widths,
            p_values,
            config=self.config,
        )
        repair_indices = []
        if self.config.get("artifactFixEnabled", True):
            repair_indices = list(false_curve_report_before.get("artifactIndices", []))
            repair_indices.extend(centerline_artifact_report_before.get("artifactIndices", []))
        repair_indices = _expand_indices(repair_indices, len(centerline), int(self.config["artifactRepairRadius"])) if repair_indices else []
        visual_widths = initial_widths
        if repair_indices:
            visual_widths = _replace_width_indices(
                visual_widths,
                repair_indices,
                int(self.config["artifactWidthMedianWindow"]),
                int(self.config["artifactWidthSmoothingWindow"]),
            )
            visual_widths = _limit_delta(visual_widths, float(self.config["maxWidthDeltaPerSample"]))
            visual_widths = [_round(_clamp(width, self.config["minWidth"], self.config["maxWidth"])) for width in visual_widths]

        base_centerline = self._visual_centerline_v2(centerline, repair_indices)
        visual_centerline, visual_left, visual_right, normals = self._build_edges(
            base_centerline,
            left_edge,
            right_edge,
            visual_widths,
        )
        final_widths = [_round(_distance(left, right)) for left, right in zip(visual_left, visual_right)]
        centerline_artifact_report_after = audit_centerline_artifacts(
            visual_centerline,
            p_values,
            config=self.config,
        )
        visual_artifact_report = audit_visual_edge_artifacts(
            visual_centerline,
            visual_left,
            visual_right,
            final_widths,
            p_values,
            config=self.config,
        )
        false_curve_report_after = audit_false_curve_artifacts(
            visual_centerline,
            visual_left,
            visual_right,
            final_widths,
            p_values,
            config=self.config,
        )
        false_curve_artifacts_removed = max(
            0,
            int(false_curve_report_before.get("artifactCount", 0)) - int(false_curve_report_after.get("artifactCount", 0)),
        )
        centerline_artifacts_detected = int(centerline_artifact_report_before.get("artifactCount", 0))
        centerline_artifacts_reduced = max(
            0,
            centerline_artifacts_detected - int(centerline_artifact_report_after.get("artifactCount", 0)),
        )

        changed_indices = [
            index
            for index, width in enumerate(raw_widths)
            if index < len(final_widths) and abs(float(width) - float(final_widths[index])) > 0.05
        ]
        artifacts_removed = [
            artifact
            for artifact in artifact_report.get("artifacts", [])
            if int(artifact.get("index", -1)) in set(changed_indices)
        ][:500]
        stats = _stats(final_widths)
        render_mode = str(self.config.get("visualRenderMode", "ribbon")).strip().lower()
        if render_mode not in {"polygon", "ribbon"}:
            render_mode = "ribbon"
        ribbon_geometry = _build_ribbon_geometry(
            visual_centerline,
            final_widths,
            visual_left,
            visual_right,
            config=self.config,
        )
        visual_version: Any = TRACK_VISUAL_RIBBON_VERSION if render_mode == "ribbon" else TRACK_VISUAL_GEOMETRY_MODEL_VERSION
        width_profile = [
            {
                "index": index,
                "p": _round(p_values[index]) if index < len(p_values) else None,
                "physicalWidth": _round(raw_widths[index]) if index < len(raw_widths) else None,
                "visualWidth": _round(final_widths[index]) if index < len(final_widths) else None,
                "delta": _round(final_widths[index] - raw_widths[index]) if index < len(raw_widths) else None,
            }
            for index in range(len(final_widths))
        ]
        visual_source = "road_only" if self.config.get("visualSource") == "road_only" else "centerline_width_smoothing"
        source = "road_only" if visual_source == "road_only" else "track_physics_geometry"

        metadata = {
            "source": source,
            "visualSource": visual_source,
            "method": "centerline_width_smoothing",
            "visualOnly": True,
            "visualVersion": visual_version,
            "visualRenderMode": render_mode,
            "visualArtifactFixEnabled": bool(self.config.get("artifactFixEnabled", True)),
            "falseCurveArtifactsRemoved": false_curve_artifacts_removed,
            "centerlineSmoothingEnabled": bool(self.config.get("centerlineSmoothingEnabled", True)),
            "centerlineSmoothingWindow": int(self.config["centerlineSmoothingWindow"]),
            "normalRecomputed": bool(self.config.get("normalRecompute", True)),
            "centerlineArtifactsDetected": centerline_artifacts_detected,
            "centerlineArtifactsReduced": centerline_artifacts_reduced,
            "curvatureOutlierThreshold": self.config.get("curvatureOutlierThreshold", "auto"),
            "medianWindow": int(self.config["widthMedianWindow"]),
            "smoothingWindow": int(self.config["widthSmoothingWindow"]),
            "minWidth": float(self.config["minWidth"]),
            "maxWidth": float(self.config["maxWidth"]),
            "maxWidthDeltaPerSample": float(self.config["maxWidthDeltaPerSample"]),
            "visualSurfaces": self.config.get("visualSurfaces", ["ROAD"]),
            "ribbonWidthMeters": ribbon_geometry.get("ribbonWidthMeters"),
            "centerlineMaxDisplacement": (ribbon_geometry.get("metadata") or {}).get("centerlineMaxDisplacement"),
            "physicsUnaffected": True,
        }
        return {
            "version": VISUAL_GEOMETRY_VERSION,
            "visualVersion": visual_version,
            "enabled": True,
            "source": source,
            "visualSource": visual_source,
            "visualRenderMode": render_mode,
            "method": "centerline_width_smoothing",
            "visualOnly": True,
            "physicsUnaffected": True,
            "visualArtifactFixEnabled": bool(self.config.get("artifactFixEnabled", True)),
            "falseCurveArtifactsRemoved": false_curve_artifacts_removed,
            "centerlineSmoothingEnabled": bool(self.config.get("centerlineSmoothingEnabled", True)),
            "normalRecomputed": bool(self.config.get("normalRecompute", True)),
            "centerlineArtifactsDetected": centerline_artifacts_detected,
            "centerlineArtifactsReduced": centerline_artifacts_reduced,
            "ribbonWidthMeters": ribbon_geometry.get("ribbonWidthMeters"),
            "centerlineMaxDisplacement": (ribbon_geometry.get("metadata") or {}).get("centerlineMaxDisplacement"),
            "coordinateSystem": "map_x_world_x_y_negative_world_z",
            "centerline": _series_payload(visual_centerline),
            "leftEdge": _series_payload(visual_left),
            "rightEdge": _series_payload(visual_right),
            "left_edge": _series_payload(visual_left),
            "right_edge": _series_payload(visual_right),
            "width": final_widths,
            "localWidth": final_widths,
            "widthMin": stats["min"],
            "widthAvg": stats["avg"],
            "widthMax": stats["max"],
            "bounds": _bounds(visual_left, visual_right, visual_centerline),
            "config": self.config,
            "metadata": metadata,
            "normals": [{"x": _round(normal[0]), "y": _round(normal[1])} for normal in normals],
            "visualRibbonGeometry": ribbon_geometry,
            "artifactReport": artifact_report,
            "visualArtifactReport": visual_artifact_report,
            "falseCurveReport": false_curve_report_before,
            "falseCurveReportAfter": false_curve_report_after,
            "centerlineArtifactReport": centerline_artifact_report_before,
            "centerlineArtifactReportAfter": centerline_artifact_report_after,
            "removedSpikeCount": len(artifacts_removed),
            "maxWidthDeltaBefore": _max_abs_delta(raw_widths),
            "maxWidthDeltaAfter": _max_abs_delta(final_widths),
            "widthProfile": width_profile,
            "artifactsRemoved": artifacts_removed,
            "debugGeometry": {
                "preSmoothingCenterline": _series_payload(preliminary_centerline),
            },
        }
