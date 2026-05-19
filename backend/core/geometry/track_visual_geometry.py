import math
from statistics import median
from typing import Any, Dict, List, Optional, Sequence


Point = List[float]

VISUAL_GEOMETRY_VERSION = 3

DEFAULT_VISUAL_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "widthMedianWindow": 9,
    "widthSmoothingWindow": 11,
    "maxWidthDeltaPerSample": 1.2,
    "minWidth": 6.0,
    "maxWidth": 22.0,
    "angleSpikeRadians": 0.55,
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
        averaged = _moving_average(medianed, int(self.config["widthSmoothingWindow"]))
        limited = _limit_delta(averaged, float(self.config["maxWidthDeltaPerSample"]))
        return [_clamp(width, self.config["minWidth"], self.config["maxWidth"]) for width in limited]

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
        visual_widths = self._visual_widths(raw_widths)
        normals = _visual_normals(
            centerline,
            left_edge,
            right_edge,
            int(self.config["widthSmoothingWindow"]),
        )
        visual_left: List[Point] = []
        visual_right: List[Point] = []
        for index, center in enumerate(centerline):
            width = visual_widths[index] if index < len(visual_widths) else raw_widths[index]
            normal = normals[index] if index < len(normals) else _fallback_normal(centerline, index)
            half_width = width * 0.5
            visual_left.append(_point([float(center[0]) + normal[0] * half_width, float(center[1]) + normal[1] * half_width]))
            visual_right.append(_point([float(center[0]) - normal[0] * half_width, float(center[1]) - normal[1] * half_width]))

        visual_centerline = [
            _point([(visual_left[index][0] + visual_right[index][0]) * 0.5, (visual_left[index][1] + visual_right[index][1]) * 0.5])
            for index in range(len(visual_left))
        ]
        final_widths = [_round(_distance(visual_left[index], visual_right[index])) for index in range(len(visual_left))]
        visual_artifact_report = audit_visual_edge_artifacts(
            visual_centerline,
            visual_left,
            visual_right,
            final_widths,
            p_values,
            config=self.config,
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
            }
            for index in range(len(final_widths))
        ]

        metadata = {
            "source": "track_physics_geometry",
            "visualOnly": True,
            "medianWindow": int(self.config["widthMedianWindow"]),
            "smoothingWindow": int(self.config["widthSmoothingWindow"]),
            "minWidth": float(self.config["minWidth"]),
            "maxWidth": float(self.config["maxWidth"]),
            "maxWidthDeltaPerSample": float(self.config["maxWidthDeltaPerSample"]),
        }
        return {
            "version": VISUAL_GEOMETRY_VERSION,
            "enabled": True,
            "source": "track_physics_geometry",
            "method": "centerline_width_smoothing",
            "visualOnly": True,
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
            "config": {
                "widthMedianWindow": int(self.config["widthMedianWindow"]),
                "widthSmoothingWindow": int(self.config["widthSmoothingWindow"]),
                "minWidth": float(self.config["minWidth"]),
                "maxWidth": float(self.config["maxWidth"]),
                "maxWidthDeltaPerSample": float(self.config["maxWidthDeltaPerSample"]),
            },
            "metadata": metadata,
            "normals": [{"x": _round(normal[0]), "y": _round(normal[1])} for normal in normals],
            "artifactReport": artifact_report,
            "visualArtifactReport": visual_artifact_report,
            "removedSpikeCount": len(artifacts_removed),
            "maxWidthDeltaBefore": _max_abs_delta(raw_widths),
            "maxWidthDeltaAfter": _max_abs_delta(final_widths),
            "widthProfile": width_profile,
            "artifactsRemoved": artifacts_removed,
        }
