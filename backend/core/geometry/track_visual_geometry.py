import math
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple


Point = List[float]

VISUAL_GEOMETRY_VERSION = 5

DEFAULT_VISUAL_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "visualSurfaces": ["ROAD"],
    "useRoadOnly": False,
    "artifactFixEnabled": True,
    "widthMedianWindow": 9,
    "widthSmoothingWindow": 11,
    "artifactWidthMedianWindow": 31,
    "artifactWidthSmoothingWindow": 25,
    "maxWidthDeltaPerSample": 1.2,
    "minWidth": 6.0,
    "maxWidth": 22.0,
    "normalSmoothingWindow": 21,
    "edgeSmoothingWindow": 23,
    "centerlineSmoothingWindow": 25,
    "artifactRepairRadius": 8,
    "angleSpikeRadians": 0.55,
    "falseCurveAngleRadians": 0.24,
    "falseCurveCenterlineAngleRadians": 0.18,
    "falseCurveDeviationMeters": 0.85,
    "segmentSpikeMultiplier": 2.8,
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

    def _visual_centerline(self, centerline: Sequence[Sequence[float]], repair_indices: Sequence[int]) -> List[Point]:
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
        visual_left = _smooth_points(visual_left, int(self.config["edgeSmoothingWindow"]))
        visual_right = _smooth_points(visual_right, int(self.config["edgeSmoothingWindow"]))
        visual_centerline = [
            _point([(left[0] + right[0]) * 0.5, (left[1] + right[1]) * 0.5])
            for left, right in zip(visual_left, visual_right)
        ]
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
        initial_widths = self._visual_widths(raw_widths)
        initial_centerline = self._visual_centerline(centerline, [])
        preliminary_centerline, preliminary_left, preliminary_right, _ = self._build_edges(
            initial_centerline,
            left_edge,
            right_edge,
            initial_widths,
        )
        preliminary_widths = [_round(_distance(left, right)) for left, right in zip(preliminary_left, preliminary_right)]
        false_curve_report_before = audit_false_curve_artifacts(
            preliminary_centerline,
            preliminary_left,
            preliminary_right,
            preliminary_widths,
            p_values,
            config=self.config,
        )
        repair_indices = false_curve_report_before.get("artifactIndices", []) if self.config.get("artifactFixEnabled", True) else []
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

        base_centerline = self._visual_centerline(centerline, repair_indices)
        visual_centerline, visual_left, visual_right, normals = self._build_edges(
            base_centerline,
            left_edge,
            right_edge,
            visual_widths,
        )
        final_widths = [_round(_distance(left, right)) for left, right in zip(visual_left, visual_right)]
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
            "visualArtifactFixEnabled": bool(self.config.get("artifactFixEnabled", True)),
            "falseCurveArtifactsRemoved": false_curve_artifacts_removed,
            "medianWindow": int(self.config["widthMedianWindow"]),
            "smoothingWindow": int(self.config["widthSmoothingWindow"]),
            "minWidth": float(self.config["minWidth"]),
            "maxWidth": float(self.config["maxWidth"]),
            "maxWidthDeltaPerSample": float(self.config["maxWidthDeltaPerSample"]),
            "visualSurfaces": self.config.get("visualSurfaces", ["ROAD"]),
        }
        return {
            "version": VISUAL_GEOMETRY_VERSION,
            "enabled": True,
            "source": source,
            "visualSource": visual_source,
            "method": "centerline_width_smoothing",
            "visualOnly": True,
            "visualArtifactFixEnabled": bool(self.config.get("artifactFixEnabled", True)),
            "falseCurveArtifactsRemoved": false_curve_artifacts_removed,
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
            "artifactReport": artifact_report,
            "visualArtifactReport": visual_artifact_report,
            "falseCurveReport": false_curve_report_before,
            "falseCurveReportAfter": false_curve_report_after,
            "removedSpikeCount": len(artifacts_removed),
            "maxWidthDeltaBefore": _max_abs_delta(raw_widths),
            "maxWidthDeltaAfter": _max_abs_delta(final_widths),
            "widthProfile": width_profile,
            "artifactsRemoved": artifacts_removed,
        }
