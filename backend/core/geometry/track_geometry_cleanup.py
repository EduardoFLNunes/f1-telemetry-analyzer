import math
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple


Point = List[float]


DEFAULT_CONFIG = {
    "targetSpacingMeters": 1.5,
    "nearZeroSegmentMeters": 0.05,
    "largeJumpMultiplier": 4.0,
    "largeJumpMinimumMeters": 6.0,
    "minPlausibleWidthMeters": 4.0,
    "maxPlausibleWidthMeters": 22.0,
    "smoothingWindow": 5,
}


def is_finite_point(point: Sequence[float]) -> bool:
    return len(point) >= 2 and math.isfinite(float(point[0])) and math.isfinite(float(point[1]))


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def round_point(point: Sequence[float], digits: int = 6) -> Point:
    return [round(float(point[0]), digits), round(float(point[1]), digits)]


def map_point_from_cache(point: Dict[str, Any]) -> Point:
    return [float(point["x"]), -float(point.get("z", point.get("y", 0.0)))]


def segment_lengths(points: Sequence[Sequence[float]], closed_loop: bool = True) -> List[Dict[str, Any]]:
    segments = []
    if len(points) < 2:
        return segments
    count = len(points)
    limit = count if closed_loop else count - 1
    for index in range(limit):
        start = points[index]
        end = points[(index + 1) % count]
        segments.append(
            {
                "index": index,
                "nextIndex": (index + 1) % count,
                "length": round(distance(start, end), 6),
                "from": round_point(start),
                "to": round_point(end),
            }
        )
    return segments


def stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return {"min": None, "avg": None, "max": None, "median": None}
    ordered = sorted(finite)
    return {
        "min": round(min(finite), 6),
        "avg": round(sum(finite) / len(finite), 6),
        "max": round(max(finite), 6),
        "median": round(median(ordered), 6),
    }


def remove_duplicate_points(
    centerline: Sequence[Point],
    left_edge: Sequence[Point],
    right_edge: Sequence[Point],
    widths: Sequence[float],
    *,
    epsilon: float = 1e-5,
) -> Tuple[List[Point], List[Point], List[Point], List[float], List[int]]:
    kept_center: List[Point] = []
    kept_left: List[Point] = []
    kept_right: List[Point] = []
    kept_widths: List[float] = []
    removed: List[int] = []
    for index, point in enumerate(centerline):
        if kept_center and distance(point, kept_center[-1]) <= epsilon:
            removed.append(index)
            continue
        kept_center.append(round_point(point))
        kept_left.append(round_point(left_edge[index]))
        kept_right.append(round_point(right_edge[index]))
        kept_widths.append(float(widths[index]))
    if len(kept_center) > 2 and distance(kept_center[0], kept_center[-1]) <= epsilon:
        kept_center.pop()
        kept_left.pop()
        kept_right.pop()
        kept_widths.pop()
        removed.append(len(centerline) - 1)
    return kept_center, kept_left, kept_right, kept_widths, removed


def remove_near_zero_segments(
    centerline: Sequence[Point],
    left_edge: Sequence[Point],
    right_edge: Sequence[Point],
    widths: Sequence[float],
    *,
    threshold: float = DEFAULT_CONFIG["nearZeroSegmentMeters"],
) -> Tuple[List[Point], List[Point], List[Point], List[float], List[int]]:
    if len(centerline) < 3:
        return list(centerline), list(left_edge), list(right_edge), list(widths), []
    keep = [True] * len(centerline)
    removed: List[int] = []
    for index in range(1, len(centerline)):
        if distance(centerline[index - 1], centerline[index]) < threshold:
            keep[index] = False
            removed.append(index)
    return (
        [round_point(point) for index, point in enumerate(centerline) if keep[index]],
        [round_point(point) for index, point in enumerate(left_edge) if keep[index]],
        [round_point(point) for index, point in enumerate(right_edge) if keep[index]],
        [float(width) for index, width in enumerate(widths) if keep[index]],
        removed,
    )


def detect_large_jumps(
    points: Sequence[Point],
    *,
    closed_loop: bool = True,
    multiplier: float = DEFAULT_CONFIG["largeJumpMultiplier"],
    minimum: float = DEFAULT_CONFIG["largeJumpMinimumMeters"],
) -> Tuple[List[Dict[str, Any]], float]:
    segments = segment_lengths(points, closed_loop=closed_loop)
    lengths = [segment["length"] for segment in segments]
    med = median(lengths) if lengths else 0.0
    threshold = max(float(minimum), float(med) * float(multiplier))
    jumps = [segment for segment in segments if segment["length"] > threshold]
    jumps.sort(key=lambda item: item["length"], reverse=True)
    return jumps, threshold


def interpolate_bad_samples(points: Sequence[Point], bad_indices: Sequence[int]) -> List[Point]:
    result = [round_point(point) for point in points]
    bad = set(int(index) for index in bad_indices)
    count = len(result)
    if count < 3:
        return result
    for index in sorted(bad):
        prev_index = (index - 1) % count
        next_index = (index + 1) % count
        result[index] = [
            (result[prev_index][0] + result[next_index][0]) * 0.5,
            (result[prev_index][1] + result[next_index][1]) * 0.5,
        ]
    return [round_point(point) for point in result]


def circular_smooth(points: Sequence[Point], window: int = DEFAULT_CONFIG["smoothingWindow"]) -> List[Point]:
    if len(points) < 3 or window <= 1:
        return [round_point(point) for point in points]
    if window % 2 == 0:
        window += 1
    radius = window // 2
    smoothed: List[Point] = []
    count = len(points)
    weights = [radius + 1 - abs(offset) for offset in range(-radius, radius + 1)]
    weight_sum = float(sum(weights))
    for index in range(count):
        x = 0.0
        y = 0.0
        for offset, weight in zip(range(-radius, radius + 1), weights):
            point = points[(index + offset) % count]
            x += float(point[0]) * weight
            y += float(point[1]) * weight
        smoothed.append(round_point([x / weight_sum, y / weight_sum]))
    return smoothed


def smooth_centerline(points: Sequence[Point], window: int = DEFAULT_CONFIG["smoothingWindow"]) -> List[Point]:
    return circular_smooth(points, window=window)


def smooth_edges(left_edge: Sequence[Point], right_edge: Sequence[Point], window: int = DEFAULT_CONFIG["smoothingWindow"]) -> Tuple[List[Point], List[Point]]:
    return circular_smooth(left_edge, window=window), circular_smooth(right_edge, window=window)


def tangent_at(points: Sequence[Point], index: int) -> Point:
    count = len(points)
    prev_point = points[(index - 1) % count]
    next_point = points[(index + 1) % count]
    dx = float(next_point[0]) - float(prev_point[0])
    dy = float(next_point[1]) - float(prev_point[1])
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return [1.0, 0.0]
    return [dx / length, dy / length]


def enforce_left_right_consistency(centerline: Sequence[Point], left_edge: Sequence[Point], right_edge: Sequence[Point]) -> Tuple[List[Point], List[Point], List[int]]:
    left = [round_point(point) for point in left_edge]
    right = [round_point(point) for point in right_edge]
    swapped: List[int] = []
    for index, center in enumerate(centerline):
        tangent = tangent_at(centerline, index)
        normal = [-tangent[1], tangent[0]]
        left_dot = (left[index][0] - center[0]) * normal[0] + (left[index][1] - center[1]) * normal[1]
        right_dot = (right[index][0] - center[0]) * normal[0] + (right[index][1] - center[1]) * normal[1]
        if left_dot < right_dot:
            left[index], right[index] = right[index], left[index]
            swapped.append(index)
    return left, right, swapped


def enforce_closed_loop_continuity(points: Sequence[Point]) -> Dict[str, Any]:
    if len(points) < 2:
        return {"closureDistance": None, "closed": False}
    closure = distance(points[-1], points[0])
    lengths = [segment["length"] for segment in segment_lengths(points, closed_loop=False)]
    med = median(lengths) if lengths else 0.0
    return {
        "closureDistance": round(closure, 6),
        "medianSegmentLength": round(med, 6),
        "closed": closure <= max(5.0, med * 4.0),
    }


def cumulative_distances(points: Sequence[Point], closed_loop: bool = True) -> Tuple[List[float], float]:
    if not points:
        return [], 0.0
    distances = [0.0]
    for index in range(1, len(points)):
        distances.append(distances[-1] + distance(points[index - 1], points[index]))
    total = distances[-1]
    if closed_loop and len(points) > 1:
        total += distance(points[-1], points[0])
    return distances, total


def interpolate_polyline(points: Sequence[Point], distances: Sequence[float], total_length: float, s: float) -> Point:
    if not points:
        return [0.0, 0.0]
    if len(points) == 1 or total_length <= 1e-9:
        return round_point(points[0])
    s = s % total_length
    for index in range(len(points)):
        start_s = distances[index]
        if index == len(points) - 1:
            end_s = total_length
            end_point = points[0]
        else:
            end_s = distances[index + 1]
            end_point = points[index + 1]
        if start_s <= s <= end_s:
            span = max(end_s - start_s, 1e-9)
            alpha = (s - start_s) / span
            start = points[index]
            return round_point([
                float(start[0]) + (float(end_point[0]) - float(start[0])) * alpha,
                float(start[1]) + (float(end_point[1]) - float(start[1])) * alpha,
            ])
    return round_point(points[-1])


def resample_evenly_by_distance(
    centerline: Sequence[Point],
    left_edge: Sequence[Point],
    right_edge: Sequence[Point],
    *,
    target_spacing: float = DEFAULT_CONFIG["targetSpacingMeters"],
) -> Tuple[List[Point], List[Point], List[Point], List[float]]:
    distances, total_length = cumulative_distances(centerline, closed_loop=True)
    if total_length <= 1e-9:
        return list(centerline), list(left_edge), list(right_edge), []
    count = max(8, int(round(total_length / target_spacing)))
    step = total_length / count
    resampled_center = []
    resampled_left = []
    resampled_right = []
    widths = []
    for index in range(count):
        s = index * step
        center = interpolate_polyline(centerline, distances, total_length, s)
        left = interpolate_polyline(left_edge, distances, total_length, s)
        right = interpolate_polyline(right_edge, distances, total_length, s)
        resampled_center.append(center)
        resampled_left.append(left)
        resampled_right.append(right)
        widths.append(distance(left, right))
    return resampled_center, resampled_left, resampled_right, widths


def audit_geometry(
    centerline: Sequence[Point],
    left_edge: Sequence[Point],
    right_edge: Sequence[Point],
    widths: Sequence[float],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    center_segments = segment_lengths(centerline)
    left_segments = segment_lengths(left_edge)
    right_segments = segment_lengths(right_edge)
    center_jumps, center_threshold = detect_large_jumps(centerline, minimum=cfg["largeJumpMinimumMeters"], multiplier=cfg["largeJumpMultiplier"])
    left_jumps, left_threshold = detect_large_jumps(left_edge, minimum=cfg["largeJumpMinimumMeters"], multiplier=cfg["largeJumpMultiplier"])
    right_jumps, right_threshold = detect_large_jumps(right_edge, minimum=cfg["largeJumpMinimumMeters"], multiplier=cfg["largeJumpMultiplier"])

    invalid_points = []
    for name, series in (("centerline", centerline), ("leftEdge", left_edge), ("rightEdge", right_edge)):
        invalid_points.extend({"series": name, "index": index, "point": point} for index, point in enumerate(series) if not is_finite_point(point))

    near_zero = {
        "centerline": [segment for segment in center_segments if segment["length"] < cfg["nearZeroSegmentMeters"]],
        "leftEdge": [segment for segment in left_segments if segment["length"] < cfg["nearZeroSegmentMeters"]],
        "rightEdge": [segment for segment in right_segments if segment["length"] < cfg["nearZeroSegmentMeters"]],
    }
    low_width = [
        {"index": index, "localWidth": round(float(width), 6), "centerline": round_point(centerline[index])}
        for index, width in enumerate(widths)
        if math.isfinite(float(width)) and float(width) < cfg["minPlausibleWidthMeters"]
    ]
    high_width = [
        {"index": index, "localWidth": round(float(width), 6), "centerline": round_point(centerline[index])}
        for index, width in enumerate(widths)
        if math.isfinite(float(width)) and float(width) > cfg["maxPlausibleWidthMeters"]
    ]

    left_right_inversions = []
    for index, center in enumerate(centerline):
        tangent = tangent_at(centerline, index)
        normal = [-tangent[1], tangent[0]]
        left_dot = (left_edge[index][0] - center[0]) * normal[0] + (left_edge[index][1] - center[1]) * normal[1]
        right_dot = (right_edge[index][0] - center[0]) * normal[0] + (right_edge[index][1] - center[1]) * normal[1]
        if left_dot < right_dot:
            left_right_inversions.append({"index": index, "leftDot": round(left_dot, 6), "rightDot": round(right_dot, 6)})

    closure = enforce_closed_loop_continuity(centerline)
    suspicious_count = (
        len(center_jumps)
        + len(left_jumps)
        + len(right_jumps)
        + len(near_zero["centerline"])
        + len(near_zero["leftEdge"])
        + len(near_zero["rightEdge"])
        + len(low_width)
        + len(high_width)
        + len(left_right_inversions)
        + len(invalid_points)
    )
    recommendations = []
    if center_jumps or left_jumps or right_jumps:
        recommendations.append("Resample by accumulated centerline distance and apply a small circular smoothing window.")
    if near_zero["centerline"] or near_zero["leftEdge"] or near_zero["rightEdge"]:
        recommendations.append("Remove duplicate/near-zero samples before generating render paths.")
    if low_width:
        recommendations.append("Inspect narrow intervals; keep interval containment test and mark low-width debug samples.")
    if high_width:
        recommendations.append("Clamp or reject implausibly wide interval candidates before runtime promotion.")
    if left_right_inversions:
        recommendations.append("Run left/right consistency enforcement after smoothing and resampling.")
    if not recommendations:
        recommendations.append("Geometry is usable; apply cleanup primarily for visual continuity and render performance.")

    return {
        "config": cfg,
        "totalPoints": len(centerline),
        "suspiciousSegmentCount": suspicious_count,
        "segmentLengthStats": {
            "centerline": stats([segment["length"] for segment in center_segments]),
            "leftEdge": stats([segment["length"] for segment in left_segments]),
            "rightEdge": stats([segment["length"] for segment in right_segments]),
        },
        "localWidthStats": stats(widths),
        "largeJumpThresholds": {
            "centerline": round(center_threshold, 6),
            "leftEdge": round(left_threshold, 6),
            "rightEdge": round(right_threshold, 6),
        },
        "top50LargestCenterlineJumps": center_jumps[:50],
        "top50LargestLeftEdgeJumps": left_jumps[:50],
        "top50LargestRightEdgeJumps": right_jumps[:50],
        "nearZeroSegments": {key: value[:50] for key, value in near_zero.items()},
        "nearZeroSegmentCounts": {key: len(value) for key, value in near_zero.items()},
        "invalidPointCount": len(invalid_points),
        "invalidPoints": invalid_points[:50],
        "leftRightInversionCount": len(left_right_inversions),
        "leftRightInversions": left_right_inversions[:50],
        "samplesBelowWidthLimit": low_width[:100],
        "samplesBelowWidthLimitCount": len(low_width),
        "samplesAboveWidthLimit": high_width[:100],
        "samplesAboveWidthLimitCount": len(high_width),
        "loopClosure": closure,
        "recommendations": recommendations,
    }


def cleanup_geometry(
    centerline: Sequence[Point],
    left_edge: Sequence[Point],
    right_edge: Sequence[Point],
    widths: Sequence[float],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    c1, l1, r1, w1, duplicates = remove_duplicate_points(centerline, left_edge, right_edge, widths)
    c2, l2, r2, w2, near_zero = remove_near_zero_segments(c1, l1, r1, w1, threshold=cfg["nearZeroSegmentMeters"])
    c3, l3, r3, w3 = resample_evenly_by_distance(c2, l2, r2, target_spacing=cfg["targetSpacingMeters"])
    c4 = smooth_centerline(c3, window=cfg["smoothingWindow"])
    l4, r4 = smooth_edges(l3, r3, window=cfg["smoothingWindow"])
    l5, r5, swapped = enforce_left_right_consistency(c4, l4, r4)
    widths_clean = [distance(left, right) for left, right in zip(l5, r5)]
    return {
        "centerline": c4,
        "leftEdge": l5,
        "rightEdge": r5,
        "localWidth": [round(width, 6) for width in widths_clean],
        "metadata": {
            "removedDuplicateIndices": duplicates,
            "removedNearZeroIndices": near_zero,
            "leftRightSwappedIndices": swapped,
            "targetSpacingMeters": cfg["targetSpacingMeters"],
            "smoothingWindow": cfg["smoothingWindow"],
            "rawPointCount": len(centerline),
            "cleanedPointCount": len(c4),
            "loopClosure": enforce_closed_loop_continuity(c4),
            "localWidthStats": stats(widths_clean),
        },
    }
