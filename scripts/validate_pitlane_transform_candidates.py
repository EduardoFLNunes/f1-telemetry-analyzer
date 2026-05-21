"""Debug-only transform validation for Interlagos 1pitlane* meshes.

This script does not alter runtime geometry. It reconstructs the original
world X/Z coordinates from the current debug surface export, tests candidate
2D map transforms, and compares them against MainTrackGeometry/fast_lane.ai.
"""
from __future__ import annotations

import html
import json
import math
import struct
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"

MAIN_TRACK_JSON = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PITLANE_SURFACE_JSON = DEBUG_DIR / "interlagos_pitlane_surface_boundary.json"
AI_VALIDATION_JSON = DEBUG_DIR / "ai_parser_validation.json"

OUTPUT_JSON = DEBUG_DIR / "interlagos_pitlane_transform_candidates.json"
OUTPUT_SVG = DEBUG_DIR / "interlagos_pitlane_transform_candidates.svg"
REPORT_JSON = DEBUG_DIR / "interlagos_pitlane_transform_validation_report.json"

STRAIGHT_CURVATURE_THRESHOLD = 0.006
SENNA_SOL_FAST_LANE_START_INDEX = 100
SENNA_SOL_FAST_LANE_END_INDEX = 260
BOUNDARY_PRECISION = 2
SLICE_SPACING_METERS = 2.0
MAX_REASONABLE_PIT_WIDTH = 35.0

Point = Tuple[float, float]
WorldXZ = Tuple[float, float]


TRANSFORMS = [
    ("A", "mapX = x, mapY = -z", lambda x, z: (x, -z)),
    ("B", "mapX = x, mapY = z", lambda x, z: (x, z)),
    ("C", "mapX = -x, mapY = -z", lambda x, z: (-x, -z)),
    ("D", "mapX = -x, mapY = z", lambda x, z: (-x, z)),
    ("E", "mapX = z, mapY = -x", lambda x, z: (z, -x)),
    ("F", "mapX = z, mapY = x", lambda x, z: (z, x)),
    ("G", "mapX = -z, mapY = -x", lambda x, z: (-z, -x)),
    ("H", "mapX = -z, mapY = x", lambda x, z: (-z, x)),
]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def point_payload(point: Point) -> Dict[str, float]:
    return {"x": round_value(point[0]), "y": round_value(point[1])}


def points_payload(points: Sequence[Point]) -> List[Dict[str, float]]:
    return [point_payload(point) for point in points]


def point_xy(point: Any) -> Point:
    if isinstance(point, dict):
        return (float(point["x"]), float(point.get("y", point.get("z", 0.0))))
    return (float(point[0]), float(point[1]))


def points_xy(points: Iterable[Any]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def normalize(vector: Point) -> Point:
    length = math.hypot(vector[0], vector[1])
    if length <= 1e-12:
        return (0.0, 0.0)
    return (vector[0] / length, vector[1] / length)


def angle_between(a: Point, b: Point) -> float:
    na = normalize(a)
    nb = normalize(b)
    value = max(-1.0, min(1.0, dot(na, nb)))
    return math.degrees(math.acos(value))


def undirected_angle_between(a: Point, b: Point) -> float:
    angle = angle_between(a, b)
    return min(angle, 180.0 - angle)


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def line_direction(points: Sequence[Point]) -> Point:
    if len(points) < 2:
        return (0.0, 0.0)
    return normalize(subtract(points[-1], points[0]))


def bbox(points: Sequence[Point]) -> Dict[str, Any]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "minX": round_value(min_x),
        "maxX": round_value(max_x),
        "minY": round_value(min_y),
        "maxY": round_value(max_y),
        "width": round_value(max_x - min_x),
        "height": round_value(max_y - min_y),
        "centroid": {
            "x": round_value(sum(xs) / len(xs)),
            "y": round_value(sum(ys) / len(ys)),
        },
    }


def bbox_overlap(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, float]:
    width = max(0.0, min(a["maxX"], b["maxX"]) - max(a["minX"], b["minX"]))
    height = max(0.0, min(a["maxY"], b["maxY"]) - max(a["minY"], b["minY"]))
    area = width * height
    area_a = max(1e-9, float(a["width"]) * float(a["height"]))
    area_b = max(1e-9, float(b["width"]) * float(b["height"]))
    return {
        "area": round_value(area),
        "ratioCandidate": round_value(area / area_a),
        "ratioMainTrack": round_value(area / area_b),
    }


def signed_curvature(points: Sequence[Point], index: int) -> float:
    count = len(points)
    a = points[(index - 1) % count]
    b = points[index]
    c = points[(index + 1) % count]
    v1 = subtract(b, a)
    v2 = subtract(c, b)
    turn = math.atan2(cross(v1, v2), dot(v1, v2))
    ds = max((distance(a, b) + distance(b, c)) / 2.0, 1e-6)
    return turn / ds


def circular_runs(indices: Sequence[int], count: int) -> List[List[int]]:
    if not indices:
        return []
    runs: List[List[int]] = []
    current = [indices[0]]
    for index in indices[1:]:
        if index == current[-1] + 1:
            current.append(index)
        else:
            runs.append(current)
            current = [index]
    runs.append(current)
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == count - 1:
        runs[0] = runs[-1] + runs[0]
        runs.pop()
    return runs


def circular_slice(points: Sequence[Point], run: Sequence[int]) -> List[Point]:
    return [points[index % len(points)] for index in run]


def longest_low_curvature_run(points: Sequence[Point]) -> Dict[str, Any]:
    curvatures = [abs(signed_curvature(points, index)) for index in range(len(points))]
    low_curvature_indices = [index for index, value in enumerate(curvatures) if value <= STRAIGHT_CURVATURE_THRESHOLD]
    runs = circular_runs(low_curvature_indices, len(points))
    best = max(runs, key=lambda run: polyline_length(circular_slice(points, run)))
    best_points = circular_slice(points, best)
    return {
        "startIndex": int(best[0] % len(points)),
        "endIndex": int(best[-1] % len(points)),
        "pointCount": len(best),
        "lengthMeters": round_value(polyline_length(best_points)),
        "curvatureThreshold": STRAIGHT_CURVATURE_THRESHOLD,
        "points": best_points,
    }


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a)
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, distance(point, projected)


def nearest_polyline_distance(point: Point, line: Sequence[Point]) -> float:
    return min(nearest_point_on_segment(point, line[index - 1], line[index])[1] for index in range(1, len(line)))


def distance_stats(points: Sequence[Point], line: Sequence[Point]) -> Dict[str, float]:
    distances = [nearest_polyline_distance(point, line) for point in points]
    ordered = sorted(distances)
    p95 = ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))]
    return {
        "min": round_value(ordered[0]),
        "avg": round_value(mean(ordered)),
        "p95": round_value(p95),
        "max": round_value(ordered[-1]),
    }


def parse_ai_block20(path: str) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points: List[Point] = []
    for index in range(count):
        x, _world_y, z, _spline_distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append((float(x), float(z)))
    return {
        "path": str(ai_path),
        "version": int(version),
        "declaredPointCount": int(declared_count),
        "pointCount": len(points),
        "points": points,
        "coordinateSpace": "x,z aligned to MainTrackGeometry",
    }


def quantized(point: Point, precision: int = BOUNDARY_PRECISION) -> Tuple[int, int]:
    scale = 10**precision
    return (int(round(point[0] * scale)), int(round(point[1] * scale)))


def boundary_edges(triangles: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    edge_counts: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = defaultdict(int)
    edge_points: Dict[Tuple[Tuple[int, int], Tuple[int, int]], Tuple[Point, Point]] = {}
    for triangle in triangles:
        points = triangle["vertices"]
        for start, end in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
            qa, qb = quantized(start), quantized(end)
            key = tuple(sorted((qa, qb)))
            edge_counts[key] += 1
            edge_points[key] = (start, end)
    edges = []
    for edge_id, (key, count) in enumerate(edge_counts.items()):
        if count != 1:
            continue
        start, end = edge_points[key]
        edges.append({"edgeId": edge_id, "keys": key, "from": start, "to": end, "length": distance(start, end)})
    return edges


def pca_axes(points: Sequence[Point]) -> Dict[str, Any]:
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    centered = [(point[0] - mean_x, point[1] - mean_y) for point in points]
    cov_xx = sum(point[0] * point[0] for point in centered) / max(1, len(centered) - 1)
    cov_xy = sum(point[0] * point[1] for point in centered) / max(1, len(centered) - 1)
    cov_yy = sum(point[1] * point[1] for point in centered) / max(1, len(centered) - 1)
    angle = 0.5 * math.atan2(2.0 * cov_xy, cov_xx - cov_yy)
    longitudinal = (math.cos(angle), math.sin(angle))
    if longitudinal[1] < 0:
        longitudinal = (-longitudinal[0], -longitudinal[1])
    lateral = (-longitudinal[1], longitudinal[0])
    projected_u = [point[0] * longitudinal[0] + point[1] * longitudinal[1] for point in centered]
    projected_v = [point[0] * lateral[0] + point[1] * lateral[1] for point in centered]
    return {
        "origin": (mean_x, mean_y),
        "longitudinalAxis": longitudinal,
        "lateralAxis": lateral,
        "uMin": min(projected_u),
        "uMax": max(projected_u),
        "vMin": min(projected_v),
        "vMax": max(projected_v),
    }


def to_uv(point: Point, axes: Dict[str, Any]) -> Point:
    delta = subtract(point, axes["origin"])
    return (dot(delta, axes["longitudinalAxis"]), dot(delta, axes["lateralAxis"]))


def from_uv(u_value: float, v_value: float, axes: Dict[str, Any]) -> Point:
    origin = axes["origin"]
    longitudinal = axes["longitudinalAxis"]
    lateral = axes["lateralAxis"]
    return (
        origin[0] + longitudinal[0] * u_value + lateral[0] * v_value,
        origin[1] + longitudinal[1] * u_value + lateral[1] * v_value,
    )


def intersections_at_u(edges: Sequence[Dict[str, Any]], axes: Dict[str, Any], u_value: float) -> List[Dict[str, Any]]:
    hits = []
    for edge in edges:
        start = edge["from"]
        end = edge["to"]
        au, av = to_uv(start, axes)
        bu, bv = to_uv(end, axes)
        if abs(bu - au) <= 1e-9:
            continue
        if not (min(au, bu) <= u_value <= max(au, bu)):
            continue
        t = (u_value - au) / (bu - au)
        if t < -1e-9 or t > 1.0 + 1e-9:
            continue
        v_value = av + (bv - av) * t
        hits.append({"v": float(v_value), "point": from_uv(u_value, v_value, axes), "edgeId": edge["edgeId"]})
    hits.sort(key=lambda hit: hit["v"])

    deduped: List[Dict[str, Any]] = []
    for hit in hits:
        if not deduped or abs(hit["v"] - deduped[-1]["v"]) > 0.03:
            deduped.append(hit)
    return deduped


def derive_surface_centerline(triangles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    vertices = [point for triangle in triangles for point in triangle["vertices"]]
    axes = pca_axes(vertices)
    edges = boundary_edges(triangles)
    sample_count = max(2, int(math.floor((axes["uMax"] - axes["uMin"]) / SLICE_SPACING_METERS)) + 1)
    samples = []
    previous_center = None
    cumulative = 0.0
    for sample_index in range(sample_count + 1):
        u_value = axes["uMin"] + (axes["uMax"] - axes["uMin"]) * sample_index / sample_count
        hits = intersections_at_u(edges, axes, u_value)
        intervals = []
        for hit_index in range(0, len(hits) - 1, 2):
            low = hits[hit_index]
            high = hits[hit_index + 1]
            width = high["v"] - low["v"]
            if width <= 0:
                continue
            intervals.append({"low": low, "high": high, "width": width})
        if not intervals:
            continue
        plausible = [interval for interval in intervals if interval["width"] <= MAX_REASONABLE_PIT_WIDTH]
        selected = max(plausible or intervals, key=lambda interval: interval["width"])
        left_v = selected["low"]["v"]
        right_v = selected["high"]["v"]
        center = from_uv(u_value, (left_v + right_v) * 0.5, axes)
        if previous_center is not None:
            cumulative += distance(previous_center, center)
        samples.append(
            {
                "index": len(samples),
                "centerline": center,
                "width": selected["width"],
                "distance": cumulative,
                "intersectionCount": len(hits),
                "intervalCount": len(intervals),
            }
        )
        previous_center = center
    centerline = [sample["centerline"] for sample in samples]
    return {
        "method": "surface_pca_cross_sections_debug_rederived",
        "boundaryEdgeCount": len(edges),
        "sampleCount": len(samples),
        "centerline": centerline,
        "length": polyline_length(centerline),
        "widthStats": stats([sample["width"] for sample in samples]),
        "axes": {
            "origin": point_payload(axes["origin"]),
            "longitudinalAxis": point_payload(axes["longitudinalAxis"]),
            "lateralAxis": point_payload(axes["lateralAxis"]),
            "uMin": round_value(axes["uMin"]),
            "uMax": round_value(axes["uMax"]),
            "vMin": round_value(axes["vMin"]),
            "vMax": round_value(axes["vMax"]),
        },
    }


def stats(values: Sequence[float]) -> Dict[str, float | None]:
    if not values:
        return {"min": None, "avg": None, "p95": None, "max": None}
    ordered = sorted(float(value) for value in values)
    p95 = ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))]
    return {
        "min": round_value(ordered[0]),
        "avg": round_value(mean(ordered)),
        "p95": round_value(p95),
        "max": round_value(ordered[-1]),
    }


def transform_triangles(
    world_triangles: Sequence[Dict[str, Any]],
    transform,
) -> List[Dict[str, Any]]:
    transformed = []
    for triangle in world_triangles:
        vertices = [transform(x, z) for x, z in triangle["worldXZ"]]
        transformed.append(
            {
                "mesh": triangle["mesh"],
                "surface": triangle.get("surface", "PITLANE"),
                "vertices": vertices,
                "area": triangle_area(vertices),
            }
        )
    return transformed


def triangle_area(vertices: Sequence[Point]) -> float:
    a, b, c = vertices
    return abs(cross(subtract(b, a), subtract(c, a))) * 0.5


def recover_world_triangles(surface_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    world_triangles = []
    for triangle in surface_data.get("pitSurfaceTriangles", []):
        world_xz: List[WorldXZ] = []
        for vertex in triangle.get("vertices", []):
            # The source debug surface was projected as mapX=worldX,mapY=-worldZ.
            # For transform validation, recover world X/Z and re-project candidates.
            world_xz.append((float(vertex[0]), -float(vertex[1])))
        world_triangles.append(
            {
                "mesh": triangle.get("mesh"),
                "surface": triangle.get("surface", "PITLANE"),
                "worldXZ": world_xz,
            }
        )
    return world_triangles


def all_triangle_points(triangles: Sequence[Dict[str, Any]]) -> List[Point]:
    return [point for triangle in triangles for point in triangle["vertices"]]


def transform_score(
    distance_to_straight: Dict[str, float],
    angle_diff: float,
    distance_to_senna_sol: Dict[str, float],
    appears_in_infield: bool,
    overlap: Dict[str, float],
) -> float:
    infield_penalty = 180.0 if appears_in_infield else 0.0
    overlap_penalty = 60.0 * max(0.0, 0.15 - overlap["ratioCandidate"])
    return round_value(
        distance_to_straight["avg"]
        + distance_to_straight["p95"] * 0.35
        + angle_diff * 6.0
        + distance_to_senna_sol["avg"] * 0.05
        + infield_penalty
        + overlap_penalty
    )


def appears_in_infield(
    candidate_bbox: Dict[str, Any],
    main_bbox: Dict[str, Any],
    distance_to_straight: Dict[str, float],
    distance_to_senna_sol: Dict[str, float],
    distance_to_main: Dict[str, float],
) -> bool:
    centroid = candidate_bbox["centroid"]
    centroid_inside_main_bbox = (
        main_bbox["minX"] <= centroid["x"] <= main_bbox["maxX"]
        and main_bbox["minY"] <= centroid["y"] <= main_bbox["maxY"]
    )
    return bool(
        centroid_inside_main_bbox
        and distance_to_main["avg"] <= 35.0
        and distance_to_straight["avg"] >= 100.0
        and distance_to_senna_sol["avg"] >= 100.0
    )


def evaluate_transform(
    key: str,
    label: str,
    transform,
    world_triangles: Sequence[Dict[str, Any]],
    main_track: Sequence[Point],
    main_bbox: Dict[str, Any],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
) -> Dict[str, Any]:
    transformed_triangles = transform_triangles(world_triangles, transform)
    transformed_points = all_triangle_points(transformed_triangles)
    candidate_bbox = bbox(transformed_points)
    derived = derive_surface_centerline(transformed_triangles)
    centerline = derived["centerline"]
    distance_to_straight = distance_stats(centerline, pit_straight)
    distance_to_senna_sol = distance_stats(centerline, senna_sol)
    distance_to_main = distance_stats(centerline, main_track)
    angle_diff = undirected_angle_between(line_direction(centerline), line_direction(pit_straight))
    overlap = bbox_overlap(candidate_bbox, main_bbox)
    infield = appears_in_infield(candidate_bbox, main_bbox, distance_to_straight, distance_to_senna_sol, distance_to_main)
    score = transform_score(distance_to_straight, angle_diff, distance_to_senna_sol, infield, overlap)

    return {
        "transform": key,
        "label": label,
        "sourceMeshes": "1pitlane001/1pitlane002/1pitlane003",
        "sourceVertices": "world X/Z reconstructed from current debug surface projection",
        "selectedAutomatically": False,
        "runtimeChanged": False,
        "geometryChanged": False,
        "triangleCount": len(transformed_triangles),
        "centerlinePointCount": len(centerline),
        "centerlineLength": round_value(polyline_length(centerline)),
        "bbox": candidate_bbox,
        "bboxOverlapWithMainTrackGeometry": overlap,
        "distanceToMainStraight": distance_to_straight,
        "distanceToSennaSolRegion": distance_to_senna_sol,
        "distanceToAnyMainTrackSegment": distance_to_main,
        "pitlaneLongitudinalAngleDiffToMainStraightDeg": round_value(angle_diff),
        "appearsInInfield": infield,
        "score": score,
        "widthStats": derived["widthStats"],
        "derivation": {
            "method": derived["method"],
            "boundaryEdgeCount": derived["boundaryEdgeCount"],
            "sampleCount": derived["sampleCount"],
            "axes": derived["axes"],
        },
        "centerline": points_payload(centerline),
    }


def svg_bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs) - margin,
        "maxX": max(xs) + margin,
        "minY": min(ys) - margin,
        "maxY": max(ys) + margin,
        "width": max(xs) - min(xs) + margin * 2,
        "height": max(ys) - min(ys) + margin * 2,
    }


def map_to_svg(point: Point, view: Dict[str, float], padding: float, scale: float) -> Tuple[float, float]:
    return padding + (point[0] - view["minX"]) * scale, padding + (view["maxY"] - point[1]) * scale


def svg_path(points: Sequence[Point], view: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
    if not points:
        return ""
    x, y = map_to_svg(points[0], view, padding, scale)
    parts = [f"M {x:.2f} {y:.2f}"]
    for point in points[1:]:
        x, y = map_to_svg(point, view, padding, scale)
        parts.append(f"L {x:.2f} {y:.2f}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    safe = html.escape(text)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.6" fill="{color}" stroke="#050816" stroke-width="1.6"/>'
        f'<text x="{x + 10:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="13" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{safe}</text>'
    )


def payload_points(points: Sequence[Dict[str, float]]) -> List[Point]:
    return [(float(point["x"]), float(point["y"])) for point in points]


def write_svg(
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
    candidates: Sequence[Dict[str, Any]],
    best_key: str,
) -> None:
    candidate_lines = {candidate["transform"]: payload_points(candidate["centerline"]) for candidate in candidates}
    all_points: List[Point] = [*main_track, *fast_lane, *pit_straight, *senna_sol]
    for line in candidate_lines.values():
        all_points.extend(line)
    view = svg_bounds(all_points, margin=76.0)
    padding = 52
    target_width = 1560
    target_height = 1100
    scale = min((target_width - padding * 2) / max(view["width"], 1.0), (target_height - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)

    weak_colors = {
        "C": "#f472b6",
        "D": "#fb923c",
        "E": "#60a5fa",
        "F": "#c084fc",
        "G": "#14b8a6",
        "H": "#eab308",
    }

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos pitlane transform candidates</title>",
        "<desc>Debug-only A-H transform validation. Runtime and authoritative geometry unchanged.</desc>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.62"/>',
        f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.10" stroke-dasharray="8 7" opacity="0.72"/>',
        f'<path d="{svg_path(pit_straight, view, padding, scale)}" fill="none" stroke="#f8fafc" stroke-width="5.2" opacity="0.90"/>',
        f'<path d="{svg_path(senna_sol, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="4.2" opacity="0.85"/>',
    ]

    for candidate in candidates:
        key = candidate["transform"]
        if key in {"A", best_key}:
            continue
        color = weak_colors.get(key, "#64748b")
        line = candidate_lines[key]
        lines.append(
            f'<path d="{svg_path(line, view, padding, scale)}" fill="none" stroke="{color}" stroke-width="2.1" opacity="0.28"/>'
        )

    current_line = candidate_lines["A"]
    best_line = candidate_lines[best_key]
    lines.extend(
        [
            f'<path d="{svg_path(current_line, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="4.8" opacity="0.94"/>',
            f'<path d="{svg_path(best_line, view, padding, scale)}" fill="none" stroke="#22c55e" stroke-width="5.2" opacity="0.98"/>',
            svg_label("MainTrackGeometry", main_track[520], view, padding, scale, "#94a3b8"),
            svg_label("fast_lane.ai", fast_lane[870], view, padding, scale, "#a855f7"),
            svg_label("reta dos boxes", pit_straight[len(pit_straight) // 2], view, padding, scale, "#f8fafc"),
            svg_label("S do Senna / Curva do Sol", senna_sol[len(senna_sol) // 2], view, padding, scale, "#22d3ee"),
            svg_label("transformacao atual A", current_line[len(current_line) // 2], view, padding, scale, "#ef4444"),
            svg_label(f"melhor candidata {best_key}", best_line[len(best_line) // 2], view, padding, scale, "#22c55e"),
        ]
    )

    legend_x = 24
    legend_y = 24
    legend_width = 520
    legend_height = 28 + 22 * (len(candidates) + 2)
    lines.extend(
        [
            f'<rect x="{legend_x}" y="{legend_y}" width="{legend_width}" height="{legend_height}" rx="7" fill="#0f172a" fill-opacity="0.88" stroke="#334155"/>',
            f'<text x="{legend_x + 14}" y="{legend_y + 24}" fill="#e2e8f0" font-size="14" font-family="Consolas, monospace">Debug transform validation: 1pitlane* mesh centerlines</text>',
        ]
    )
    for index, candidate in enumerate(candidates):
        y = legend_y + 52 + index * 22
        key = candidate["transform"]
        color = "#ef4444" if key == "A" else "#22c55e" if key == best_key else weak_colors.get(key, "#64748b")
        suffix = " current" if key == "A" else " best" if key == best_key else ""
        text = (
            f'{key}{suffix}: avg {candidate["distanceToMainStraight"]["avg"]:.1f}m, '
            f'p95 {candidate["distanceToMainStraight"]["p95"]:.1f}m, '
            f'angle {candidate["pitlaneLongitudinalAngleDiffToMainStraightDeg"]:.2f}deg, '
            f'score {candidate["score"]:.1f}'
        )
        lines.extend(
            [
                f'<line x1="{legend_x + 14}" y1="{y - 4}" x2="{legend_x + 42}" y2="{y - 4}" stroke="{color}" stroke-width="4" opacity="0.96"/>',
                f'<text x="{legend_x + 52}" y="{y}" fill="#e2e8f0" font-size="12" font-family="Consolas, monospace">{html.escape(text)}</text>',
            ]
        )

    lines.append("</svg>")
    OUTPUT_SVG.write_text("\n".join(lines), encoding="utf-8")


def confidence_for(best: Dict[str, Any], current: Dict[str, Any]) -> str:
    best_distance = best["distanceToMainStraight"]["avg"]
    best_angle = best["pitlaneLongitudinalAngleDiffToMainStraightDeg"]
    current_distance = current["distanceToMainStraight"]["avg"]
    if best_distance <= 35.0 and best_angle <= 5.0 and not best["appearsInInfield"] and current_distance > best_distance * 4.0:
        return "high"
    if best_distance <= 60.0 and best_angle <= 10.0 and not best["appearsInInfield"]:
        return "medium"
    return "low"


def build() -> None:
    main_data = read_json(MAIN_TRACK_JSON)
    surface_data = read_json(PITLANE_SURFACE_JSON)
    ai_data = read_json(AI_VALIDATION_JSON)

    main_track = points_xy(main_data["centerline"])
    main_bbox = bbox(main_track)
    longest_straight = longest_low_curvature_run(main_track)
    pit_straight = longest_straight["points"]

    manifest = ai_data["manifest"]
    fast_ai = parse_ai_block20(manifest["fastLaneAi"])
    fast_lane = fast_ai["points"]
    senna_sol = fast_lane[SENNA_SOL_FAST_LANE_START_INDEX : SENNA_SOL_FAST_LANE_END_INDEX + 1]

    world_triangles = recover_world_triangles(surface_data)
    mesh_counts: Dict[str, int] = defaultdict(int)
    for triangle in world_triangles:
        mesh_counts[str(triangle.get("mesh"))] += 1

    candidates = [
        evaluate_transform(key, label, transform, world_triangles, main_track, main_bbox, pit_straight, senna_sol)
        for key, label, transform in TRANSFORMS
    ]
    candidates_sorted = sorted(candidates, key=lambda candidate: candidate["score"])
    best = candidates_sorted[0]
    current = next(candidate for candidate in candidates if candidate["transform"] == "A")
    confidence = confidence_for(best, current)

    best_reason = (
        f"Transform {best['transform']} has the lowest score, mean distance "
        f"{best['distanceToMainStraight']['avg']:.1f}m to the pit straight, p95 "
        f"{best['distanceToMainStraight']['p95']:.1f}m, angle difference "
        f"{best['pitlaneLongitudinalAngleDiffToMainStraightDeg']:.2f}deg, and "
        f"appearsInInfield={best['appearsInInfield']}. Current transform A is "
        f"{current['distanceToMainStraight']['avg']:.1f}m from the pit straight with "
        f"{current['pitlaneLongitudinalAngleDiffToMainStraightDeg']:.2f}deg angle difference."
    )

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_pitlane_transform_validation",
        "debugOnly": True,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "selectedAutomatically": False,
        "aiGeneratedImageUsedAsGeometryReference": False,
        "aiGeneratedImageIgnored": True,
        "sourceVertexNote": (
            "interlagos_pitlane_surface_boundary.json stores 1pitlane* vertices after the current "
            "debug projection mapX=worldX,mapY=-worldZ. This script reconstructs world X/Z as "
            "worldX=mapX, worldZ=-mapY and then applies transforms A-H. worldY is irrelevant for "
            "the requested 2D map-space validation."
        ),
        "currentTransform": {
            "transform": "A",
            "label": "mapX = x, mapY = -z",
        },
        "bestTransformCandidate": {
            "transform": best["transform"],
            "label": best["label"],
            "selectedAutomatically": False,
            "score": best["score"],
        },
        "confidence": confidence,
        "reason": best_reason,
        "mainTrackGeometry": {
            "path": str(MAIN_TRACK_JSON),
            "pointCount": len(main_track),
            "bbox": main_bbox,
        },
        "fastLaneAi": {
            "path": fast_ai["path"],
            "pointCount": fast_ai["pointCount"],
            "coordinateSpace": fast_ai["coordinateSpace"],
        },
        "mainStraightCandidate": {
            "source": "MainTrackGeometry longest low-curvature run",
            "startIndex": longest_straight["startIndex"],
            "endIndex": longest_straight["endIndex"],
            "pointCount": longest_straight["pointCount"],
            "lengthMeters": longest_straight["lengthMeters"],
            "curvatureThreshold": longest_straight["curvatureThreshold"],
            "startPoint": point_payload(pit_straight[0]),
            "endPoint": point_payload(pit_straight[-1]),
        },
        "sennaSolCandidate": {
            "source": "fast_lane.ai x/z diagnostic segment",
            "startIndex": SENNA_SOL_FAST_LANE_START_INDEX,
            "endIndex": SENNA_SOL_FAST_LANE_END_INDEX,
            "pointCount": len(senna_sol),
            "startPoint": point_payload(senna_sol[0]),
            "endPoint": point_payload(senna_sol[-1]),
        },
        "sourceMeshes": {
            "path": str(PITLANE_SURFACE_JSON),
            "projectionRecordedInSource": surface_data.get("projection"),
            "triangleCount": len(world_triangles),
            "meshTriangleCounts": dict(sorted(mesh_counts.items())),
        },
        "candidates": candidates,
        "exports": {
            "json": str(OUTPUT_JSON),
            "svg": str(OUTPUT_SVG),
            "report": str(REPORT_JSON),
        },
    }

    report = {
        "generatedAt": payload["generatedAt"],
        "trackName": payload["trackName"],
        "trackConfig": payload["trackConfig"],
        "debugOnly": True,
        "currentTransform": payload["currentTransform"],
        "bestTransformCandidate": payload["bestTransformCandidate"],
        "confidence": confidence,
        "currentDistanceToMainStraightAvg": current["distanceToMainStraight"]["avg"],
        "bestDistanceToMainStraightAvg": best["distanceToMainStraight"]["avg"],
        "currentAngleDiff": current["pitlaneLongitudinalAngleDiffToMainStraightDeg"],
        "bestAngleDiff": best["pitlaneLongitudinalAngleDiffToMainStraightDeg"],
        "likelyRootCause": "current 1pitlane* map-space transform uses inverted Z relative to MainTrackGeometry/fast_lane.ai",
        "recommendedFix": (
            "Do not apply automatically. For a future manual/runtime review, validate replacing the 1pitlane* "
            f"extraction map transform with {best['transform']} ({best['label']}) before regenerating any official PitLaneGeometry."
        ),
        "reason": best_reason,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "selectedAutomatically": False,
        "exports": payload["exports"],
    }

    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_svg(main_track, fast_lane, pit_straight, senna_sol, candidates, best["transform"])

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_SVG}")
    print(f"Wrote {REPORT_JSON}")
    print(
        f"Best transform {best['transform']} avg={best['distanceToMainStraight']['avg']:.3f}m "
        f"angle={best['pitlaneLongitudinalAngleDiffToMainStraightDeg']:.3f}deg confidence={confidence}"
    )


if __name__ == "__main__":
    build()
