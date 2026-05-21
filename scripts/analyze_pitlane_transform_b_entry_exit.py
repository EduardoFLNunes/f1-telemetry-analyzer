"""Debug-only trim decision and entry/exit analysis for PitLane transform B."""
from __future__ import annotations

import html
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
AI_VALIDATION_JSON = DEBUG_DIR / "ai_parser_validation.json"
DERIVED_B_JSON = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry_transform_b.json"
TRIM_B_JSON = DEBUG_DIR / "interlagos_pitlane_trim_candidates_minimal_transform_b.json"
OLD_DERIVED_A_JSON = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry.json"

TRIM_DECISION_JSON = DEBUG_DIR / "interlagos_pitlane_transform_b_trim_decision.json"
TRIM_DECISION_SVG = DEBUG_DIR / "interlagos_pitlane_transform_b_trim_decision.svg"
ENTRY_EXIT_ANALYSIS_JSON = DEBUG_DIR / "interlagos_pitlane_transform_b_entry_exit_analysis.json"
ENTRY_EXIT_ANALYSIS_SVG = DEBUG_DIR / "interlagos_pitlane_transform_b_entry_exit_analysis.svg"
ENTRY_EXIT_REPORT_JSON = DEBUG_DIR / "interlagos_pitlane_transform_b_entry_exit_report.json"

STRAIGHT_CURVATURE_THRESHOLD = 0.006
SENNA_SOL_FAST_LANE_START_INDEX = 100
SENNA_SOL_FAST_LANE_END_INDEX = 260
ANALYSIS_WINDOW_METERS = 35.0

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def point_xy(point: Any) -> Point:
    if isinstance(point, dict):
        return (float(point["x"]), float(point.get("y", point.get("z", 0.0))))
    return (float(point[0]), float(point[1]))


def points_xy(points: Iterable[Any]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def point_payload(point: Point | Sequence[float]) -> Dict[str, float]:
    return {"x": round_value(float(point[0])), "y": round_value(float(point[1]))}


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


def undirected_angle_between(a: Point, b: Point) -> float:
    na = normalize(a)
    nb = normalize(b)
    value = max(-1.0, min(1.0, dot(na, nb)))
    angle = math.degrees(math.acos(value))
    return min(angle, 180.0 - angle)


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
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


def bbox(points: Sequence[Point]) -> Dict[str, Any]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "minX": round_value(min(xs)),
        "maxX": round_value(max(xs)),
        "minY": round_value(min(ys)),
        "maxY": round_value(max(ys)),
        "width": round_value(max(xs) - min(xs)),
        "height": round_value(max(ys) - min(ys)),
        "centroid": {"x": round_value(mean(xs)), "y": round_value(mean(ys))},
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


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a), 0.0
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, distance(point, projected), t


def nearest_polyline_info(point: Point, line: Sequence[Point]) -> Dict[str, Any]:
    best: Optional[Tuple[float, int, Point, float]] = None
    for index in range(1, len(line)):
        projected, dist, t = nearest_point_on_segment(point, line[index - 1], line[index])
        item = (dist, index - 1, projected, t)
        if best is None or item < best:
            best = item
    if best is None:
        return {"distance": None, "segmentIndex": None, "point": None, "t": None}
    dist, segment_index, projected, t = best
    return {
        "distance": round_value(dist),
        "segmentIndex": segment_index,
        "point": point_payload(projected),
        "t": round_value(t),
    }


def nearest_polyline_distance(point: Point, line: Sequence[Point]) -> float:
    info = nearest_polyline_info(point, line)
    return float(info["distance"])


def distance_stats(points: Sequence[Point], line: Sequence[Point]) -> Dict[str, float]:
    return stats([nearest_polyline_distance(point, line) for point in points])  # type: ignore[return-value]


def tangent_at_segment(line: Sequence[Point], segment_index: int) -> Point:
    if len(line) < 2:
        return (1.0, 0.0)
    index = max(0, min(segment_index, len(line) - 2))
    return normalize(subtract(line[index + 1], line[index]))


def endpoint_tangent(points: Sequence[Point], *, at_start: bool, target_distance: float = 12.0) -> Point:
    if len(points) < 2:
        return (1.0, 0.0)
    if at_start:
        origin = points[0]
        cumulative = 0.0
        for index in range(1, len(points)):
            cumulative += distance(points[index - 1], points[index])
            if cumulative >= target_distance:
                return normalize(subtract(points[index], origin))
        return normalize(subtract(points[-1], origin))
    origin = points[-1]
    cumulative = 0.0
    for index in range(len(points) - 2, -1, -1):
        cumulative += distance(points[index + 1], points[index])
        if cumulative >= target_distance:
            return normalize(subtract(origin, points[index]))
    return normalize(subtract(origin, points[0]))


def parse_ai_block20(path: str) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points: List[Point] = []
    for index in range(count):
        x, _world_y, z, _distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append((float(x), float(z)))
    return {
        "path": str(ai_path),
        "version": int(version),
        "declaredPointCount": int(declared_count),
        "pointCount": len(points),
        "points": points,
    }


def candidate_by_name(trim_data: Dict[str, Any], name: str) -> Dict[str, Any]:
    for candidate in trim_data.get("candidates", []):
        if candidate.get("name") == name:
            return candidate
    raise KeyError(name)


def widths_from_edges(candidate: Dict[str, Any]) -> List[float]:
    left = points_xy(candidate.get("pitLeftEdge", []))
    right = points_xy(candidate.get("pitRightEdge", []))
    return [distance(a, b) for a, b in zip(left, right)]


def edge_window_indices(points: Sequence[Point], meters: float, *, from_end: bool = False) -> List[int]:
    if not points:
        return []
    if len(points) == 1:
        return [0]
    indices = [len(points) - 1] if from_end else [0]
    cumulative = 0.0
    if from_end:
        for index in range(len(points) - 2, -1, -1):
            cumulative += distance(points[index + 1], points[index])
            indices.append(index)
            if cumulative >= meters:
                break
        return sorted(indices)
    for index in range(1, len(points)):
        cumulative += distance(points[index - 1], points[index])
        indices.append(index)
        if cumulative >= meters:
            break
    return indices


def width_window_stats(candidate: Dict[str, Any], *, from_end: bool) -> Dict[str, Any]:
    center = points_xy(candidate.get("pitCenterline", []))
    widths = widths_from_edges(candidate)
    indices = edge_window_indices(center, ANALYSIS_WINDOW_METERS, from_end=from_end)
    values = [widths[index] for index in indices if index < len(widths)]
    length = polyline_length([center[index] for index in indices]) if len(indices) >= 2 else 0.0
    return {
        "windowMeters": ANALYSIS_WINDOW_METERS,
        "sampleCount": len(values),
        "actualWindowLength": round_value(length),
        "width": stats(values),
    }


def endpoint_metrics(
    point: Point,
    tangent: Point,
    main_center: Sequence[Point],
    main_left: Sequence[Point],
    main_right: Sequence[Point],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
) -> Dict[str, Any]:
    nearest_center = nearest_polyline_info(point, main_center)
    center_segment = int(nearest_center["segmentIndex"] or 0)
    main_tangent = tangent_at_segment(main_center, center_segment)
    nearest_left = nearest_polyline_info(point, main_left)
    nearest_right = nearest_polyline_info(point, main_right)
    edge_candidates = [
        ("left", nearest_left),
        ("right", nearest_right),
    ]
    nearest_edge_side, nearest_edge = min(
        edge_candidates,
        key=lambda item: float("inf") if item[1]["distance"] is None else float(item[1]["distance"]),
    )
    return {
        "point": point_payload(point),
        "distanceToMainCenterline": nearest_center,
        "distanceToMainEdges": {
            "left": nearest_left,
            "right": nearest_right,
            "nearestSide": nearest_edge_side,
            "nearestDistance": nearest_edge["distance"],
            "nearestPoint": nearest_edge["point"],
        },
        "tangent": point_payload(tangent),
        "mainTrackTangent": point_payload(main_tangent),
        "tangentAngleDiffToMainTrackDeg": round_value(undirected_angle_between(tangent, main_tangent)),
        "proximityToPitStraight": nearest_polyline_info(point, pit_straight),
        "proximityToSennaSol": nearest_polyline_info(point, senna_sol),
    }


def analyze_candidate(
    candidate: Dict[str, Any],
    main_center: Sequence[Point],
    main_left: Sequence[Point],
    main_right: Sequence[Point],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
) -> Dict[str, Any]:
    center = points_xy(candidate.get("pitCenterline", []))
    start_tangent = endpoint_tangent(center, at_start=True)
    end_tangent = endpoint_tangent(center, at_start=False)
    return {
        "name": candidate["name"],
        "pointCount": len(center),
        "lengthMeters": round_value(polyline_length(center)),
        "startTrimPoints": candidate.get("startTrimPoints"),
        "endTrimPoints": candidate.get("endTrimPoints"),
        "removedStartMeters": candidate.get("removedStartMeters"),
        "removedEndMeters": candidate.get("removedEndMeters"),
        "start": endpoint_metrics(center[0], start_tangent, main_center, main_left, main_right, pit_straight, senna_sol),
        "end": endpoint_metrics(center[-1], end_tangent, main_center, main_left, main_right, pit_straight, senna_sol),
        "first35m": width_window_stats(candidate, from_end=False),
        "last35m": width_window_stats(candidate, from_end=True),
        "fullCandidateDistanceToMainCenterline": distance_stats(center, main_center),
        "fullCandidateDistanceToMainLeftEdge": distance_stats(center, main_left),
        "fullCandidateDistanceToMainRightEdge": distance_stats(center, main_right),
        "fullCandidateProximityToPitStraight": distance_stats(center, pit_straight),
        "fullCandidateProximityToSennaSol": distance_stats(center, senna_sol),
        "selectedAutomatically": False,
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


def map_to_svg(point: Point, view: Dict[str, float], padding: float, scale: float) -> Point:
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


def svg_label(
    text: str,
    point: Point,
    view: Dict[str, float],
    padding: float,
    scale: float,
    color: str,
    *,
    dx: float = 10.0,
    dy: float = -8.0,
) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{color}" stroke="#050816" stroke-width="1.6"/>'
        f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" fill="{color}" font-size="12" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{html.escape(text)}</text>'
    )


def make_canvas(points: Sequence[Point], *, margin: float = 72.0, target_width: int = 1560, target_height: int = 1080):
    view = svg_bounds(points, margin=margin)
    padding = 52
    scale = min((target_width - padding * 2) / max(view["width"], 1.0), (target_height - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    return view, width, height, padding, scale


def draw_candidate_endpoints(lines: List[str], center: Sequence[Point], name: str, view: Dict[str, float], padding: float, scale: float) -> None:
    lines.append(svg_label(f"{name} start", center[0], view, padding, scale, "#22c55e"))
    lines.append(svg_label(f"{name} end", center[-1], view, padding, scale, "#fb923c"))


def write_trim_decision_svg(
    main_center: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
    raw_b: Sequence[Point],
    candidate_05: Sequence[Point],
    candidate_08: Sequence[Point],
    old_a: Sequence[Point],
) -> None:
    view, width, height, padding, scale = make_canvas([*main_center, *fast_lane, *pit_straight, *senna_sol, *raw_b, *candidate_05, *candidate_08, *old_a])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLane transform B trim decision</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_center, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.62"/>',
        f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.1" stroke-dasharray="8 7" opacity="0.70"/>',
        f'<path d="{svg_path(pit_straight, view, padding, scale)}" fill="none" stroke="#f8fafc" stroke-width="5.2" opacity="0.88"/>',
        f'<path d="{svg_path(senna_sol, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="4.0" opacity="0.84"/>',
        f'<path d="{svg_path(old_a, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="3.2" opacity="0.26"/>',
        f'<path d="{svg_path(raw_b, view, padding, scale)}" fill="none" stroke="#facc15" stroke-width="5.4" opacity="0.34"/>',
        f'<path d="{svg_path(candidate_05, view, padding, scale)}" fill="none" stroke="#22c55e" stroke-width="4.6" opacity="0.98"/>',
        f'<path d="{svg_path(candidate_08, view, padding, scale)}" fill="none" stroke="#d946ef" stroke-width="4.0" opacity="0.96"/>',
        svg_label("reta dos boxes", pit_straight[len(pit_straight) // 2], view, padding, scale, "#f8fafc"),
        svg_label("S do Senna / Curva do Sol", senna_sol[len(senna_sol) // 2], view, padding, scale, "#22d3ee"),
        svg_label("old invalid", old_a[len(old_a) // 2], view, padding, scale, "#ef4444"),
        svg_label("PitLane B raw", raw_b[len(raw_b) // 2], view, padding, scale, "#facc15"),
    ]
    draw_candidate_endpoints(lines, candidate_05, "05_05", view, padding, scale)
    draw_candidate_endpoints(lines, candidate_08, "08_08", view, padding, scale)
    lines.extend(
        [
            '<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">PitLane transform B trim decision: no automatic selection</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">green=05_05, magenta=08_08, red=old invalid transform A</text>',
            "</svg>",
        ]
    )
    TRIM_DECISION_SVG.write_text("\n".join(lines), encoding="utf-8")


def write_entry_exit_svg(
    main_center: Sequence[Point],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
    raw_b: Sequence[Point],
    candidate_05: Sequence[Point],
    candidate_08: Sequence[Point],
) -> None:
    view, width, height, padding, scale = make_canvas([*main_center, *pit_straight, *senna_sol, *raw_b, *candidate_05, *candidate_08])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLane transform B entry/exit analysis</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_center, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.62"/>',
        f'<path d="{svg_path(pit_straight, view, padding, scale)}" fill="none" stroke="#f8fafc" stroke-width="5.0" opacity="0.86"/>',
        f'<path d="{svg_path(senna_sol, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="3.8" opacity="0.82"/>',
        f'<path d="{svg_path(raw_b, view, padding, scale)}" fill="none" stroke="#facc15" stroke-width="5.2" opacity="0.70"/>',
        f'<path d="{svg_path(candidate_05, view, padding, scale)}" fill="none" stroke="#22c55e" stroke-width="4.4" opacity="0.98"/>',
        f'<path d="{svg_path(candidate_08, view, padding, scale)}" fill="none" stroke="#d946ef" stroke-width="3.8" opacity="0.96"/>',
        svg_label("PitLane B", raw_b[len(raw_b) // 2], view, padding, scale, "#facc15", dy=-26),
        svg_label("candidate_05_05", candidate_05[max(0, len(candidate_05) // 2 - 16)], view, padding, scale, "#22c55e", dy=-8),
        svg_label("candidate_08_08", candidate_08[min(len(candidate_08) - 1, len(candidate_08) // 2 + 16)], view, padding, scale, "#d946ef", dy=16),
        svg_label("reta dos boxes", pit_straight[len(pit_straight) // 2], view, padding, scale, "#f8fafc"),
        svg_label("S do Senna / Curva do Sol", senna_sol[len(senna_sol) // 2], view, padding, scale, "#22d3ee"),
    ]
    for name, center in (("00_00", raw_b), ("05_05", candidate_05), ("08_08", candidate_08)):
        lines.append(svg_label(f"{name} start", center[0], view, padding, scale, "#22c55e"))
        lines.append(svg_label(f"{name} end", center[-1], view, padding, scale, "#fb923c"))
    lines.extend(
        [
            '<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">PitLane transform B entry/exit analysis</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">start markers green, end markers orange; runtime unchanged</text>',
            "</svg>",
        ]
    )
    ENTRY_EXIT_ANALYSIS_SVG.write_text("\n".join(lines), encoding="utf-8")


def build() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    main_data = read_json(MAIN_TRACK_JSON)
    ai_data = read_json(AI_VALIDATION_JSON)
    derived_b = read_json(DERIVED_B_JSON)
    trim_b = read_json(TRIM_B_JSON)
    old_a = read_json(OLD_DERIVED_A_JSON)

    main_center = points_xy(main_data.get("centerline", []))
    main_left = points_xy(main_data.get("boundsLeft", []))
    main_right = points_xy(main_data.get("boundsRight", []))
    fast_lane = parse_ai_block20(ai_data["manifest"]["fastLaneAi"])["points"]
    longest_straight = longest_low_curvature_run(main_center)
    pit_straight = longest_straight["points"]
    senna_sol = fast_lane[SENNA_SOL_FAST_LANE_START_INDEX : SENNA_SOL_FAST_LANE_END_INDEX + 1]

    required_names = ["candidate_00_00", "candidate_05_05", "candidate_08_08", "candidate_10_10", "candidate_12_12"]
    present_names = [candidate.get("name") for candidate in trim_b.get("candidates", [])]
    missing_names = [name for name in required_names if name not in present_names]
    if missing_names:
        raise RuntimeError(f"Missing transform B trim candidates: {missing_names}")

    candidate_00 = candidate_by_name(trim_b, "candidate_00_00")
    candidate_05 = candidate_by_name(trim_b, "candidate_05_05")
    candidate_08 = candidate_by_name(trim_b, "candidate_08_08")
    raw_b_center = points_xy(derived_b.get("pitCenterline", []))
    old_a_center = points_xy(old_a.get("pitCenterline", []))
    center_05 = points_xy(candidate_05.get("pitCenterline", []))
    center_08 = points_xy(candidate_08.get("pitCenterline", []))

    analyses = {
        candidate["name"]: analyze_candidate(candidate, main_center, main_left, main_right, pit_straight, senna_sol)
        for candidate in (candidate_00, candidate_05, candidate_08)
    }

    trim_decision = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_transform_b_trim_decision",
        "selectedTransform": "B",
        "transformUsed": "mapX = worldX, mapY = worldZ",
        "oldTransformInvalidated": True,
        "debugOnly": True,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "selectedAutomatically": False,
        "recommendedManualTrimCandidate": None,
        "trimCandidatesValidation": {
            "source": str(TRIM_B_JSON),
            "requiredCandidates": required_names,
            "presentCandidates": present_names,
            "missingCandidates": missing_names,
            "valid": not missing_names,
        },
        "highlightedCandidates": ["candidate_05_05", "candidate_08_08"],
        "mainStraightCandidate": {
            "startIndex": longest_straight["startIndex"],
            "endIndex": longest_straight["endIndex"],
            "lengthMeters": longest_straight["lengthMeters"],
            "startPoint": point_payload(pit_straight[0]),
            "endPoint": point_payload(pit_straight[-1]),
        },
        "sennaSolCandidate": {
            "source": "fast_lane.ai x/z diagnostic segment",
            "startIndex": SENNA_SOL_FAST_LANE_START_INDEX,
            "endIndex": SENNA_SOL_FAST_LANE_END_INDEX,
            "startPoint": point_payload(senna_sol[0]),
            "endPoint": point_payload(senna_sol[-1]),
        },
        "candidates": [
            {
                "name": candidate["name"],
                "pointCount": candidate["pointCount"],
                "lengthMeters": candidate["length"],
                "removedStartMeters": candidate["removedStartMeters"],
                "removedEndMeters": candidate["removedEndMeters"],
                "startCoordinate": candidate["startCoordinate"],
                "endCoordinate": candidate["endCoordinate"],
                "highlightedForComparison": candidate["name"] in {"candidate_05_05", "candidate_08_08"},
            }
            for candidate in trim_b.get("candidates", [])
        ],
        "exports": {
            "json": str(TRIM_DECISION_JSON),
            "svg": str(TRIM_DECISION_SVG),
        },
    }

    entry_exit_analysis = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_transform_b_entry_exit_analysis",
        "selectedTransform": "B",
        "transformUsed": "mapX = worldX, mapY = worldZ",
        "oldTransformInvalidated": True,
        "debugOnly": True,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "selectedAutomatically": False,
        "recommendedManualTrimCandidate": None,
        "analysisWindowMeters": ANALYSIS_WINDOW_METERS,
        "mainStraightCandidate": trim_decision["mainStraightCandidate"],
        "sennaSolCandidate": trim_decision["sennaSolCandidate"],
        "candidates": analyses,
        "exports": {
            "json": str(ENTRY_EXIT_ANALYSIS_JSON),
            "svg": str(ENTRY_EXIT_ANALYSIS_SVG),
        },
    }

    report = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_transform_b_entry_exit_report",
        "selectedTransform": "B",
        "oldTransformInvalidated": True,
        "candidate_00_00": analyses["candidate_00_00"],
        "candidate_05_05": analyses["candidate_05_05"],
        "candidate_08_08": analyses["candidate_08_08"],
        "recommendedManualTrimCandidate": None,
        "selectedAutomatically": False,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "recommendedNextStep": "manual visual review of transform B trim endpoints, then revalidate pit entry/exit using the chosen B trim only",
        "exports": {
            "trimDecisionJson": str(TRIM_DECISION_JSON),
            "trimDecisionSvg": str(TRIM_DECISION_SVG),
            "entryExitAnalysisJson": str(ENTRY_EXIT_ANALYSIS_JSON),
            "entryExitAnalysisSvg": str(ENTRY_EXIT_ANALYSIS_SVG),
            "reportJson": str(ENTRY_EXIT_REPORT_JSON),
        },
    }

    write_json(TRIM_DECISION_JSON, trim_decision)
    write_json(ENTRY_EXIT_ANALYSIS_JSON, entry_exit_analysis)
    write_json(ENTRY_EXIT_REPORT_JSON, report)
    write_trim_decision_svg(main_center, fast_lane, pit_straight, senna_sol, raw_b_center, center_05, center_08, old_a_center)
    write_entry_exit_svg(main_center, pit_straight, senna_sol, raw_b_center, center_05, center_08)

    print(f"Wrote {TRIM_DECISION_JSON}")
    print(f"Wrote {TRIM_DECISION_SVG}")
    print(f"Wrote {ENTRY_EXIT_ANALYSIS_JSON}")
    print(f"Wrote {ENTRY_EXIT_ANALYSIS_SVG}")
    print(f"Wrote {ENTRY_EXIT_REPORT_JSON}")
    for name, analysis in analyses.items():
        print(
            f"{name}: startMain={analysis['start']['distanceToMainCenterline']['distance']:.3f}m "
            f"endMain={analysis['end']['distanceToMainCenterline']['distance']:.3f}m "
            f"startAngle={analysis['start']['tangentAngleDiffToMainTrackDeg']:.3f}deg "
            f"endAngle={analysis['end']['tangentAngleDiffToMainTrackDeg']:.3f}deg"
        )


if __name__ == "__main__":
    build()
