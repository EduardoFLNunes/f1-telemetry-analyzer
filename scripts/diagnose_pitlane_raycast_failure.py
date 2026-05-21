from __future__ import annotations

import json
import math
import statistics
import struct
import sys
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402


Point = Tuple[float, float]
Triangle = Dict[str, Any]

PROJECTIONS = {
    "A": {"label": "mapX = x, mapY = -z", "color": "#22c55e"},
    "B": {"label": "mapX = x, mapY = z", "color": "#38bdf8"},
    "C": {"label": "mapX = z, mapY = -x", "color": "#f97316"},
    "D": {"label": "mapX = -x, mapY = -z", "color": "#e879f9"},
}


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _round_point(point: Sequence[float], digits: int = 6) -> List[float]:
    return [_round(point[0], digits), _round(point[1], digits)]


def _distance_stats(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "avg": 0.0, "p95": 0.0, "max": 0.0}
    sorted_values = sorted(float(value) for value in values)
    p95_index = min(len(sorted_values) - 1, max(0, int(math.ceil(len(sorted_values) * 0.95)) - 1))
    return {
        "min": _round(sorted_values[0]),
        "avg": _round(sum(sorted_values) / len(sorted_values)),
        "p95": _round(sorted_values[p95_index]),
        "max": _round(sorted_values[-1]),
    }


def parse_ai_line(path: str) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    diagnostics: List[Dict[str, Any]] = []
    if len(data) < 16:
        return {
            "path": str(ai_path),
            "version": None,
            "declaredPointCount": 0,
            "pointCount": 0,
            "points": [],
            "diagnostics": [{"code": "invalid_ai_file", "message": "AI line file is smaller than the AC header"}],
        }

    version, point_count = struct.unpack_from("<II", data, 0)
    offset = 16
    stride = 20
    expected = offset + point_count * stride
    if expected > len(data):
        diagnostics.append(
            {
                "code": "ai_file_truncated",
                "message": "AI line ended before the declared point count",
                "declaredPointCount": int(point_count),
                "availablePointCount": max(0, (len(data) - offset) // stride),
            }
        )
        point_count = max(0, (len(data) - offset) // stride)

    points = []
    for index in range(point_count):
        point_offset = offset + index * stride
        world_x, world_y, world_z = struct.unpack_from("<3f", data, point_offset)
        distance = struct.unpack_from("<f", data, point_offset + 12)[0]
        raw_index = struct.unpack_from("<I", data, point_offset + 16)[0]
        points.append(
            {
                "index": index,
                "worldPosition": [_round(world_x), _round(world_y), _round(world_z)],
                "distance": _round(distance),
                "rawIndex": int(raw_index),
            }
        )

    return {
        "path": str(ai_path),
        "version": int(version),
        "declaredPointCount": int(struct.unpack_from("<II", data, 0)[1]),
        "pointCount": len(points),
        "points": points,
        "diagnostics": diagnostics,
    }


def project_point(world_position: Sequence[float], projection_key: str) -> Point:
    x, _y, z = [float(value) for value in world_position[:3]]
    if projection_key == "A":
        return x, -z
    if projection_key == "B":
        return x, z
    if projection_key == "C":
        return z, -x
    if projection_key == "D":
        return -x, -z
    raise ValueError(f"Unknown projection key {projection_key}")


def _point_in_triangle(point: Point, triangle: Sequence[Sequence[float]], epsilon: float = 1e-7) -> bool:
    px, py = point
    ax, ay = float(triangle[0][0]), float(triangle[0][1])
    bx, by = float(triangle[1][0]), float(triangle[1][1])
    cx, cy = float(triangle[2][0]), float(triangle[2][1])
    denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denom) <= 1e-12:
        return False
    w1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denom
    w2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denom
    w3 = 1.0 - w1 - w2
    return w1 >= -epsilon and w2 >= -epsilon and w3 >= -epsilon


def _point_to_segment_distance(point: Point, a: Sequence[float], b: Sequence[float]) -> float:
    px, py = point
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def _point_to_triangle_distance(point: Point, triangle: Sequence[Sequence[float]]) -> Tuple[bool, float]:
    if _point_in_triangle(point, triangle):
        return True, 0.0
    distances = (
        _point_to_segment_distance(point, triangle[0], triangle[1]),
        _point_to_segment_distance(point, triangle[1], triangle[2]),
        _point_to_segment_distance(point, triangle[2], triangle[0]),
    )
    return False, min(distances)


def _bounds(points: Iterable[Sequence[float]]) -> Optional[Dict[str, float]]:
    values = [(float(point[0]), float(point[1])) for point in points]
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": _round(min(xs)),
        "maxX": _round(max(xs)),
        "minY": _round(min(ys)),
        "maxY": _round(max(ys)),
        "width": _round(max(xs) - min(xs)),
        "height": _round(max(ys) - min(ys)),
    }


def _bbox_overlap(a: Optional[Dict[str, float]], b: Optional[Dict[str, float]]) -> Dict[str, float]:
    if not a or not b:
        return {"area": 0.0, "ratioAi": 0.0, "ratioSurface": 0.0}
    overlap_w = max(0.0, min(a["maxX"], b["maxX"]) - max(a["minX"], b["minX"]))
    overlap_h = max(0.0, min(a["maxY"], b["maxY"]) - max(a["minY"], b["minY"]))
    area = overlap_w * overlap_h
    ai_area = max(1e-9, float(a["width"]) * float(a["height"]))
    surface_area = max(1e-9, float(b["width"]) * float(b["height"]))
    return {
        "area": _round(area),
        "ratioAi": _round(area / ai_area),
        "ratioSurface": _round(area / surface_area),
    }


def _surface_bounds(surface: Dict[str, Any]) -> Optional[Dict[str, float]]:
    vertices: List[Sequence[float]] = []
    for triangle in surface.get("triangles", []):
        vertices.extend(triangle.get("vertices", []))
    return _bounds(vertices)


def analyze_projection(
    ai_points: Sequence[Dict[str, Any]],
    triangles: Sequence[Triangle],
    projection_key: str,
    surface_bounds: Optional[Dict[str, float]],
    *,
    include_points: bool,
) -> Dict[str, Any]:
    projected = [project_point(point["worldPosition"], projection_key) for point in ai_points]
    point_bounds = _bounds(projected)
    rows: List[Dict[str, Any]] = []
    distances: List[float] = []
    inside_count = 0

    triangle_vertices = [triangle["vertices"] for triangle in triangles]
    for index, point in enumerate(projected):
        nearest_distance = float("inf")
        nearest_triangle_id: Optional[int] = None
        nearest_mesh_name: Optional[str] = None
        nearest_surface: Optional[str] = None
        inside = False
        for triangle_id, vertices in enumerate(triangle_vertices):
            point_inside, distance = _point_to_triangle_distance(point, vertices)
            if point_inside:
                inside = True
                nearest_distance = 0.0
                nearest_triangle_id = triangle_id
                nearest_mesh_name = triangles[triangle_id].get("mesh")
                nearest_surface = triangles[triangle_id].get("surface")
                break
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_triangle_id = triangle_id
                nearest_mesh_name = triangles[triangle_id].get("mesh")
                nearest_surface = triangles[triangle_id].get("surface")

        if inside:
            inside_count += 1
        distances.append(float(nearest_distance))
        if include_points:
            rows.append(
                {
                    "index": index,
                    "mapPosition": _round_point(point),
                    "insideSurface": inside,
                    "nearestTriangleId": nearest_triangle_id,
                    "nearestMeshName": nearest_mesh_name,
                    "nearestSurface": nearest_surface,
                    "nearestDistance": _round(nearest_distance),
                }
            )

    stats = _distance_stats(distances)
    return {
        "projection": projection_key,
        "label": PROJECTIONS[projection_key]["label"],
        "pointCount": len(projected),
        "pointsInsideSurfaceCount": inside_count,
        "pointsOutsideSurfaceCount": len(projected) - inside_count,
        "nearestDistanceMin": stats["min"],
        "nearestDistanceAvg": stats["avg"],
        "nearestDistanceP95": stats["p95"],
        "nearestDistanceMax": stats["max"],
        "pointsWithin1mCount": sum(1 for distance in distances if distance <= 1.0),
        "pointsOutsideOver1mCount": sum(1 for distance in distances if distance > 1.0),
        "bbox": point_bounds,
        "bboxOverlapWithPitLaneSurface": _bbox_overlap(point_bounds, surface_bounds),
        "points": rows,
    }


def _surface_contains(point: Point, triangle_vertices: Sequence[Sequence[Sequence[float]]]) -> bool:
    return any(_point_in_triangle(point, triangle) for triangle in triangle_vertices)


def _line_segment_intersection_t(point: Point, normal: Point, a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    px, py = point
    rx, ry = normal
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    sx = bx - ax
    sy = by - ay
    rxs = rx * sy - ry * sx
    if abs(rxs) <= 1e-9:
        return None
    qpx = ax - px
    qpy = ay - py
    t = (qpx * sy - qpy * sx) / rxs
    u = (qpx * ry - qpy * rx) / rxs
    if -1e-7 <= u <= 1.0000001:
        return float(t)
    return None


def _open_line_tangent(points: Sequence[Point], index: int) -> Point:
    count = len(points)
    prev_index = max(0, index - 1)
    next_index = min(count - 1, index + 1)
    dx = points[next_index][0] - points[prev_index][0]
    dy = points[next_index][1] - points[prev_index][1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return 1.0, 0.0
    return dx / length, dy / length


def diagnose_raycast(
    projected_points: Sequence[Point],
    surface: Dict[str, Any],
    *,
    max_side_distance: float = 80.0,
) -> Dict[str, Any]:
    boundary_segments = [
        (segment["from"], segment["to"])
        for segment in (surface.get("outline") or {}).get("segments", [])
    ]
    triangle_vertices = [triangle["vertices"] for triangle in surface.get("triangles", [])]
    simple_valid = 0
    simple_valid_inverted = 0
    interval_valid = 0
    interval_contains_point = 0
    interval_nearest_correction = 0
    simple_widths: List[float] = []
    interval_widths: List[float] = []
    samples: List[Dict[str, Any]] = []

    for index, point in enumerate(projected_points):
        tx, ty = _open_line_tangent(projected_points, index)
        normal = (-ty, tx)
        point_inside = _surface_contains(point, triangle_vertices)

        hits = []
        for segment_index, (start, end) in enumerate(boundary_segments):
            t = _line_segment_intersection_t(point, normal, start, end)
            if t is None or abs(t) <= 0.05 or abs(t) > max_side_distance:
                continue
            hits.append({"t": t, "segmentIndex": segment_index})
        hits.sort(key=lambda hit: hit["t"])

        positive = [hit["t"] for hit in hits if hit["t"] > 0.0]
        negative = [hit["t"] for hit in hits if hit["t"] < 0.0]
        simple_width: Optional[float] = None
        if positive and negative:
            simple_width = min(positive) - max(negative)
            if 1.0 <= simple_width <= 40.0:
                simple_valid += 1
                simple_valid_inverted += 1
                simple_widths.append(simple_width)

        selected_interval: Optional[Dict[str, Any]] = None
        inside_intervals: List[Dict[str, Any]] = []
        for pair_index in range(len(hits) - 1):
            left_t = hits[pair_index]["t"]
            right_t = hits[pair_index + 1]["t"]
            width = right_t - left_t
            if width <= 0.05 or width > 40.0:
                continue
            midpoint_t = (left_t + right_t) * 0.5
            midpoint = (point[0] + normal[0] * midpoint_t, point[1] + normal[1] * midpoint_t)
            midpoint_inside = _surface_contains(midpoint, triangle_vertices)
            if not midpoint_inside:
                continue
            interval = {
                "index": pair_index,
                "leftT": left_t,
                "rightT": right_t,
                "width": width,
                "containsPoint": left_t <= 0.0 <= right_t,
                "midpointInsideSurface": midpoint_inside,
            }
            inside_intervals.append(interval)
            if interval["containsPoint"] and selected_interval is None:
                selected_interval = interval

        if selected_interval is None and inside_intervals:
            selected_interval = min(
                inside_intervals,
                key=lambda interval: min(abs(interval["leftT"]), abs(interval["rightT"]), abs((interval["leftT"] + interval["rightT"]) * 0.5)),
            )
            interval_nearest_correction += 1

        if selected_interval:
            interval_valid += 1
            interval_widths.append(float(selected_interval["width"]))
            if selected_interval["containsPoint"]:
                interval_contains_point += 1

        if len(samples) < 80 or not selected_interval or simple_width is None:
            samples.append(
                {
                    "index": index,
                    "point": _round_point(point),
                    "pointInsideSurface": point_inside,
                    "allIntersectionCount": len(hits),
                    "simpleRaycastValid": simple_width is not None and 1.0 <= simple_width <= 40.0,
                    "simpleWidth": _round(simple_width) if simple_width is not None else None,
                    "intervalRaycastValid": selected_interval is not None,
                    "intervalWidth": _round(selected_interval["width"]) if selected_interval else None,
                    "intervalContainsPoint": bool(selected_interval and selected_interval["containsPoint"]),
                    "usedNearestIntervalCorrection": bool(selected_interval and not selected_interval["containsPoint"]),
                }
            )

    return {
        "boundarySegmentCount": len(boundary_segments),
        "maxSideDistance": max_side_distance,
        "simpleRaycastValidCount": simple_valid,
        "simpleRaycastFailedCount": len(projected_points) - simple_valid,
        "simpleRaycastInvertedNormalValidCount": simple_valid_inverted,
        "simpleWidthStats": _distance_stats(simple_widths),
        "intervalRaycastValidCount": interval_valid,
        "intervalRaycastFailedCount": len(projected_points) - interval_valid,
        "intervalContainsPointCount": interval_contains_point,
        "intervalNearestCorrectionCount": interval_nearest_correction,
        "intervalWidthStats": _distance_stats(interval_widths),
        "samples": samples,
    }


def choose_best_projection(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    def score(candidate: Dict[str, Any]) -> Tuple[float, float, float, float]:
        overlap = candidate.get("bboxOverlapWithPitLaneSurface") or {}
        return (
            float(candidate.get("pointsInsideSurfaceCount") or 0),
            float(candidate.get("pointsWithin1mCount") or 0),
            float(overlap.get("ratioAi") or 0.0),
            -float(candidate.get("nearestDistanceP95") or 0.0),
        )

    return max(candidates, key=score)


def infer_failure_cause(best: Dict[str, Any], canonical: Dict[str, Any], raycast: Dict[str, Any]) -> Tuple[str, str]:
    point_count = max(1, int(canonical.get("pointCount") or 0))
    canonical_inside_ratio = float(canonical.get("pointsInsideSurfaceCount") or 0) / point_count
    canonical_near_ratio = float(canonical.get("pointsWithin1mCount") or 0) / point_count
    best_projection = best.get("projection")
    best_p95 = float(best.get("nearestDistanceP95") or 0.0)

    if best_projection != "A" and float(best.get("pointsInsideSurfaceCount") or 0) > float(canonical.get("pointsInsideSurfaceCount") or 0) * 1.5:
        return (
            "projection_mismatch",
            "Another projection has materially better surface containment than canonical A. Do not change runtime mapping yet; inspect the candidate SVG first.",
        )

    if canonical_near_ratio < 0.35 and best_p95 > 2.0:
        return (
            "centerline_outside_surface",
            "pit_lane.ai is not mostly inside or within 1m of the extracted PITLANE surface. Keep pit_lane.ai as a logical centerline or broaden/verify the pit surface mesh set before raycasting.",
        )

    simple_failed = int(raycast.get("simpleRaycastFailedCount") or 0)
    interval_failed = int(raycast.get("intervalRaycastFailedCount") or 0)
    if canonical_inside_ratio >= 0.5 and interval_failed < simple_failed:
        return (
            "normal_algorithm_failure",
            "The canonical points are on/near the surface, but simple nearest-hit raycasting fails more often than interval containment. Use boundary interval selection instead of arbitrary nearest hits.",
        )

    if canonical_inside_ratio >= 0.5 and interval_failed > point_count * 0.25:
        return (
            "surface_fragmented",
            "Many canonical points are on the surface, but interval raycast still misses. The PITLANE mesh is likely fragmented or has local boundary gaps.",
        )

    return ("unknown", "The metrics do not isolate one cause. Inspect distance and candidate SVGs before changing runtime geometry.")


def _svg_projection() -> str:
    return "map-space debug only; runtime mapping is not changed"


def _xml_text(value: Any) -> str:
    return escape(str(value), quote=False)


def build_distance_svg(surface: Dict[str, Any], analysis: Dict[str, Any], output_path: Path) -> None:
    bounds = surface.get("bounds") or {"minX": -500.0, "maxX": 500.0, "minY": -500.0, "maxY": 500.0}
    points = analysis.get("points") or []
    for row in points:
        x, y = row["mapPosition"]
        bounds["minX"] = min(bounds["minX"], x)
        bounds["maxX"] = max(bounds["maxX"], x)
        bounds["minY"] = min(bounds["minY"], y)
        bounds["maxY"] = max(bounds["maxY"], y)
    svg = _build_svg_canvas(bounds, width=1400, height=1000)
    parts = svg["parts"]
    sx = svg["sx"]

    parts.append('<text x="18" y="28" fill="#e2e8f0" font-size="16" font-family="monospace">PitLaneSurface vs pit_lane.ai distance - canonical A (x,-z)</text>')
    stats_text = (
        f"inside={analysis['pointsInsideSurfaceCount']} "
        f"outside={analysis['pointsOutsideSurfaceCount']} "
        f"avg={analysis['nearestDistanceAvg']}m "
        f"p95={analysis['nearestDistanceP95']}m "
        f"max={analysis['nearestDistanceMax']}m"
    )
    parts.append(
        f'<text x="18" y="50" fill="#94a3b8" font-size="12" font-family="monospace">{_xml_text(stats_text)}</text>'
    )
    _draw_surface(parts, sx, surface, fill="#eab308", opacity=0.24)
    _draw_centerline(parts, sx, [row["mapPosition"] for row in points], stroke="#fef08a", dash="7,5", width=1.5)
    for row in points:
        x, y = sx(row["mapPosition"])
        distance = float(row["nearestDistance"])
        color = "#22c55e" if row["insideSurface"] else ("#facc15" if distance <= 1.0 else "#ef4444")
        radius = 2.5 if distance <= 1.0 else 3.5
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{color}" fill-opacity="0.92"/>')
    _draw_legend(parts, [("inside surface", "#22c55e"), ("outside <= 1m", "#facc15"), ("outside > 1m", "#ef4444"), ("PitLaneSurface", "#eab308")], 18, 76)
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def build_projection_candidates_svg(surface: Dict[str, Any], candidate_results: Sequence[Dict[str, Any]], output_path: Path) -> None:
    panel_w = 680
    panel_h = 520
    width = panel_w * 2
    height = panel_h * 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#080b10"/>']
    for panel_index, result in enumerate(candidate_results):
        col = panel_index % 2
        row = panel_index // 2
        ox = col * panel_w
        oy = row * panel_h
        bounds = _merge_bounds(surface.get("bounds"), result.get("bbox"))
        canvas = _build_svg_canvas(bounds, width=panel_w, height=panel_h, margin=38, offset=(ox, oy), background=False)
        sx = canvas["sx"]
        parts.append(f'<rect x="{ox + 8}" y="{oy + 8}" width="{panel_w - 16}" height="{panel_h - 16}" fill="#0b1020" stroke="#1e293b"/>')
        title_text = f"{result['projection']}: {result['label']}"
        parts.append(f'<text x="{ox + 20}" y="{oy + 30}" fill="#e2e8f0" font-size="14" font-family="monospace">{_xml_text(title_text)}</text>')
        metric_text = (
            f"inside={result['pointsInsideSurfaceCount']} "
            f"near<=1m={result['pointsWithin1mCount']} "
            f"avg={result['nearestDistanceAvg']} "
            f"p95={result['nearestDistanceP95']} "
            f"overlapAi={result['bboxOverlapWithPitLaneSurface']['ratioAi']}"
        )
        parts.append(
            f'<text x="{ox + 20}" y="{oy + 52}" fill="#94a3b8" font-size="11" font-family="monospace">'
            f'{_xml_text(metric_text)}</text>'
        )
        _draw_surface(parts, sx, surface, fill="#eab308", opacity=0.20)
        point_rows = result.get("points") or []
        _draw_centerline(parts, sx, [row_data["mapPosition"] for row_data in point_rows], stroke=PROJECTIONS[result["projection"]]["color"], dash="6,5", width=1.3)
        for row_data in point_rows[:: max(1, len(point_rows) // 220)]:
            x, y = sx(row_data["mapPosition"])
            distance = float(row_data["nearestDistance"])
            color = "#22c55e" if row_data["insideSurface"] else ("#facc15" if distance <= 1.0 else "#ef4444")
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.1" fill="{color}" fill-opacity="0.9"/>')
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def _merge_bounds(*bounds_items: Optional[Dict[str, float]]) -> Dict[str, float]:
    valid = [bounds for bounds in bounds_items if bounds]
    if not valid:
        return {"minX": -1.0, "maxX": 1.0, "minY": -1.0, "maxY": 1.0, "width": 2.0, "height": 2.0}
    min_x = min(float(bounds["minX"]) for bounds in valid)
    max_x = max(float(bounds["maxX"]) for bounds in valid)
    min_y = min(float(bounds["minY"]) for bounds in valid)
    max_y = max(float(bounds["maxY"]) for bounds in valid)
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "width": max_x - min_x, "height": max_y - min_y}


def _build_svg_canvas(
    bounds: Dict[str, float],
    *,
    width: int,
    height: int,
    margin: int = 34,
    offset: Tuple[int, int] = (0, 0),
    background: bool = True,
) -> Dict[str, Any]:
    min_x, max_x = float(bounds["minX"]), float(bounds["maxX"])
    min_y, max_y = float(bounds["minY"]), float(bounds["maxY"])
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)
    scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_y)
    ox, oy = offset

    def sx(point: Sequence[float]) -> Tuple[float, float]:
        x = ox + margin + (float(point[0]) - min_x) * scale
        y = oy + height - margin - (float(point[1]) - min_y) * scale
        return x, y

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    if background:
        parts.append('<rect width="100%" height="100%" fill="#080b10"/>')
    return {"parts": parts, "sx": sx}


def _draw_surface(parts: List[str], sx, surface: Dict[str, Any], *, fill: str, opacity: float) -> None:
    for triangle in surface.get("triangles", []):
        points = [sx(point) for point in triangle["vertices"]]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(f'<polygon points="{point_text}" fill="{fill}" fill-opacity="{opacity}" stroke="none"/>')


def _draw_centerline(parts: List[str], sx, points: Sequence[Sequence[float]], *, stroke: str, dash: str, width: float) -> None:
    if not points:
        return
    path_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    parts.append(f'<polyline points="{path_points}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-dasharray="{dash}" stroke-linejoin="round" stroke-linecap="round"/>')


def _draw_legend(parts: List[str], items: Sequence[Tuple[str, str]], x: int, y: int) -> None:
    for index, (label, color) in enumerate(items):
        yy = y + index * 19
        parts.append(f'<rect x="{x}" y="{yy - 10}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{x + 16}" y="{yy}" fill="#cbd5e1" font-size="12" font-family="monospace">{_xml_text(label)}</text>')


def main() -> None:
    track_name = sys.argv[1] if len(sys.argv) > 1 else "vhe_interlagos"
    track_config = sys.argv[2] if len(sys.argv) > 2 else "gp"
    output_dir = REPO_ROOT / "data" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_obj = TrackFileResolver().build_track_file_manifest(
        track_name,
        track_config,
        source="assetto_corsa",
        game_code="assetto_corsa",
    )
    manifest = manifest_obj.to_dict()
    pit_lane_path = (manifest.get("aiFiles") or {}).get("pit_lane")
    if not pit_lane_path:
        raise FileNotFoundError("TrackFileResolver did not resolve ai/pit_lane.ai")

    surface = build_track_surface_polygon_from_manifest(manifest, included_surfaces=["PITLANE"])
    if not surface.get("triangles"):
        raise RuntimeError("No PITLANE triangles were extracted from the resolved visual KN5")

    ai_line = parse_ai_line(pit_lane_path)
    if not ai_line["points"]:
        raise RuntimeError("pit_lane.ai did not contain any parsed AI points")

    surface_bounds = _surface_bounds(surface)
    candidate_results = []
    candidate_json = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": track_name,
        "trackConfig": track_config,
        "projectionNote": _svg_projection(),
        "manifest": {
            "mainVisual": (manifest.get("candidateGeometryFiles") or {}).get("mainVisual"),
            "pitLaneAi": pit_lane_path,
            "surfacesIni": manifest.get("surfacesIni"),
        },
        "pitLaneSurface": {
            "triangleCount": len(surface.get("triangles", [])),
            "meshCount": surface.get("meshCount"),
            "bounds": surface_bounds,
            "meshes": [
                {
                    "meshName": mesh.get("meshName"),
                    "capturedTriangles": mesh.get("capturedTriangles"),
                    "bounds": mesh.get("bounds"),
                    "matchedSurface": mesh.get("matchedSurface"),
                }
                for mesh in surface.get("meshes", [])
            ],
        },
        "pitLaneAi": {
            "path": ai_line["path"],
            "version": ai_line["version"],
            "declaredPointCount": ai_line["declaredPointCount"],
            "pointCount": ai_line["pointCount"],
            "diagnostics": ai_line["diagnostics"],
        },
        "candidates": [],
    }

    for projection_key in PROJECTIONS:
        result = analyze_projection(
            ai_line["points"],
            surface.get("triangles", []),
            projection_key,
            surface_bounds,
            include_points=True,
        )
        candidate_results.append(result)
        candidate_json["candidates"].append({key: value for key, value in result.items() if key != "points"})

    best = choose_best_projection(candidate_results)
    canonical = next(result for result in candidate_results if result["projection"] == "A")
    canonical_projected = [tuple(row["mapPosition"]) for row in canonical["points"]]
    raycast = diagnose_raycast(canonical_projected, surface)
    failure_cause, recommendation = infer_failure_cause(best, canonical, raycast)

    distance_svg_path = output_dir / "interlagos_pitlane_centerline_surface_distance.svg"
    projection_json_path = output_dir / "interlagos_pitlane_projection_candidates.json"
    projection_svg_path = output_dir / "interlagos_pitlane_projection_candidates.svg"
    analysis_json_path = output_dir / "interlagos_pitlane_raycast_failure_analysis.json"

    build_distance_svg(surface, canonical, distance_svg_path)
    build_projection_candidates_svg(surface, candidate_results, projection_svg_path)
    projection_json_path.write_text(json.dumps(candidate_json, ensure_ascii=False, indent=2), encoding="utf-8")

    analysis = {
        "generatedAt": candidate_json["generatedAt"],
        "trackName": track_name,
        "trackConfig": track_config,
        "projectionNote": _svg_projection(),
        "bestProjection": {
            key: value
            for key, value in best.items()
            if key != "points"
        },
        "canonicalProjection": {
            key: value
            for key, value in canonical.items()
            if key != "points"
        },
        "pitLaneSurface": candidate_json["pitLaneSurface"],
        "pitLaneAi": candidate_json["pitLaneAi"],
        "pointToSurfaceSamples": canonical["points"],
        "raycastDiagnostics": raycast,
        "raycastFailureCause": failure_cause,
        "recommendation": recommendation,
        "exports": {
            "distanceSvg": str(distance_svg_path),
            "projectionCandidatesJson": str(projection_json_path),
            "projectionCandidatesSvg": str(projection_svg_path),
            "raycastFailureAnalysisJson": str(analysis_json_path),
        },
    }
    analysis_json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "bestProjection": best["projection"],
                "canonicalInside": canonical["pointsInsideSurfaceCount"],
                "canonicalNearWithin1m": canonical["pointsWithin1mCount"],
                "canonicalAvgDistance": canonical["nearestDistanceAvg"],
                "canonicalP95Distance": canonical["nearestDistanceP95"],
                "raycastFailureCause": failure_cause,
                "exports": analysis["exports"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
