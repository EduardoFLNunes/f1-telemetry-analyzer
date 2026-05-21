from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"


Point = Tuple[float, float]


COLORS = {
    "main": "#8b95a7",
    "surface": "#eab308",
    "boundary": "#facc15",
    "raw": "#ffffff",
    "candidate_00_00": "#f59e0b",
    "candidate_05_05": "#22c55e",
    "candidate_08_08": "#d946ef",
    "current": "#22d3ee",
    "width": "#facc15",
    "distance": "#38bdf8",
    "angle": "#d946ef",
}


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _xml(value: Any) -> str:
    return escape(str(value), quote=False)


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _point_dict(point: Sequence[float]) -> Dict[str, float]:
    return {"x": _round(point[0]), "y": _round(point[1])}


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def _bounds(points: Iterable[Sequence[float]]) -> Optional[Dict[str, float]]:
    values = [(float(point[0]), float(point[1])) for point in points]
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs),
        "maxX": max(xs),
        "minY": min(ys),
        "maxY": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def _expand_bounds(bounds: Dict[str, float], pad: float) -> Dict[str, float]:
    return {
        "minX": bounds["minX"] - pad,
        "maxX": bounds["maxX"] + pad,
        "minY": bounds["minY"] - pad,
        "maxY": bounds["maxY"] + pad,
        "width": bounds["width"] + pad * 2,
        "height": bounds["height"] + pad * 2,
    }


def _merge_bounds(*bounds_items: Optional[Dict[str, float]]) -> Dict[str, float]:
    valid = [bounds for bounds in bounds_items if bounds]
    if not valid:
        return {"minX": -1.0, "maxX": 1.0, "minY": -1.0, "maxY": 1.0, "width": 2.0, "height": 2.0}
    min_x = min(float(bounds["minX"]) for bounds in valid)
    max_x = max(float(bounds["maxX"]) for bounds in valid)
    min_y = min(float(bounds["minY"]) for bounds in valid)
    max_y = max(float(bounds["maxY"]) for bounds in valid)
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "width": max_x - min_x, "height": max_y - min_y}


def map_to_svg(point: Sequence[float], bounds: Dict[str, float], x0: float, y0: float, width: float, height: float, padding: float = 28.0) -> Point:
    scale = min((width - padding * 2) / max(1.0, bounds["maxX"] - bounds["minX"]), (height - padding * 2) / max(1.0, bounds["maxY"] - bounds["minY"]))
    screen_x = x0 + padding + (float(point[0]) - float(bounds["minX"])) * scale
    screen_y = y0 + padding + (float(bounds["maxY"]) - float(point[1])) * scale
    return screen_x, screen_y


def _track_point(point: Dict[str, Any]) -> Point:
    return float(point["x"]), float(point.get("y", point.get("z", 0.0)))


def _xy_points(items: Sequence[Dict[str, Any]]) -> List[Point]:
    return [(float(point["x"]), float(point["y"])) for point in items]


def _polyline(points: Sequence[Sequence[float]], mapper, *, stroke: str, width: float, opacity: float = 1.0, dash: Optional[str] = None, marker: bool = False) -> str:
    if not points:
        return ""
    text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (mapper(point) for point in points))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    marker_attr = ' marker-end="url(#arrow)"' if marker else ""
    return f'<polyline points="{text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_attr}{marker_attr}/>'


def _polygon(points: Sequence[Sequence[float]], mapper, *, fill: str, opacity: float, stroke: str = "none", width: float = 1.0) -> str:
    if not points:
        return ""
    text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (mapper(point) for point in points))
    return f'<polygon points="{text}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'


def _point_to_segment_distance(point: Sequence[float], start: Sequence[float], end: Sequence[float]) -> float:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _nearest_polyline_distance(point: Sequence[float], polyline: Sequence[Sequence[float]]) -> float:
    if not polyline:
        return float("inf")
    if len(polyline) == 1:
        return _distance(point, polyline[0])
    return min(_point_to_segment_distance(point, polyline[index], polyline[index + 1]) for index in range(len(polyline) - 1))


def _nearest_main_edge_distance(point: Sequence[float], main_track: Dict[str, Any]) -> float:
    left = [_track_point(item) for item in main_track.get("boundsLeft", [])]
    right = [_track_point(item) for item in main_track.get("boundsRight", [])]
    return min(_nearest_polyline_distance(point, left), _nearest_polyline_distance(point, right))


def _point_in_triangle(point: Sequence[float], triangle: Sequence[Sequence[float]], epsilon: float = 1e-6) -> bool:
    px, py = float(point[0]), float(point[1])
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


def _contained_ratio(points: Sequence[Sequence[float]], triangles: Sequence[Dict[str, Any]]) -> float:
    if not points:
        return 0.0
    inside = 0
    triangle_vertices = [triangle["vertices"] for triangle in triangles]
    for point in points:
        if any(_point_in_triangle(point, triangle) for triangle in triangle_vertices):
            inside += 1
    return inside / len(points)


def _raw_distance(raw_points: Sequence[Dict[str, Any]], index: int) -> float:
    if not raw_points:
        return 0.0
    index = max(0, min(index, len(raw_points) - 1))
    return float(raw_points[index].get("distance", 0.0))


def _candidate_by_name(minimal: Dict[str, Any], name: str) -> Dict[str, Any]:
    for candidate in minimal.get("candidates", []):
        if candidate.get("name") == name:
            return candidate
    raise KeyError(name)


def _candidate_start_end(candidate: Dict[str, Any]) -> Tuple[Point, Point]:
    points = _xy_points(candidate.get("pitCenterline", []))
    return points[0], points[-1]


def _candidate_indices(candidate: Dict[str, Any], raw_count: int) -> Tuple[int, int]:
    start = int(candidate.get("rawStartIndex", candidate.get("startTrimPoints", 0)))
    end = int(candidate.get("rawEndIndex", raw_count - 1 - int(candidate.get("endTrimPoints", 0))))
    return start, end


def _svg_header(width: int, height: int) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#080b10"/>',
    ]


def _draw_panel_title(parts: List[str], x: float, y: float, title: str, subtitle: str = "") -> None:
    parts.append(f'<text x="{x}" y="{y}" fill="#e2e8f0" font-size="15" font-family="monospace">{_xml(title)}</text>')
    if subtitle:
        parts.append(f'<text x="{x}" y="{y + 18}" fill="#94a3b8" font-size="10" font-family="monospace">{_xml(subtitle)}</text>')


def _draw_main(parts: List[str], main_track: Dict[str, Any], mapper) -> None:
    left = [_track_point(point) for point in main_track.get("boundsLeft", [])]
    right = [_track_point(point) for point in main_track.get("boundsRight", [])]
    if left and right:
        parts.append(_polygon(left + list(reversed(right)), mapper, fill=COLORS["main"], opacity=0.13, stroke=COLORS["main"], width=0.5))
    else:
        center = [_track_point(point) for point in main_track.get("centerline", [])]
        parts.append(_polyline(center, mapper, stroke=COLORS["main"], width=1.2, opacity=0.6))


def _draw_surface(parts: List[str], triangles: Sequence[Dict[str, Any]], mapper, opacity: float = 0.24) -> None:
    for triangle in triangles:
        parts.append(_polygon(triangle["vertices"], mapper, fill=COLORS["surface"], opacity=opacity))


def _draw_boundary(parts: List[str], loops: Sequence[Dict[str, Any]], mapper) -> None:
    for loop in loops:
        parts.append(_polyline(loop.get("points", []), mapper, stroke=COLORS["boundary"], width=1.6, opacity=0.85))


def _draw_direction_arrows(parts: List[str], points: Sequence[Sequence[float]], mapper, color: str) -> None:
    if len(points) < 3:
        return
    step = max(1, len(points) // 8)
    for index in range(step, len(points) - 1, step):
        a = points[index]
        b = points[min(len(points) - 1, index + 2)]
        parts.append(_polyline([a, b], mapper, stroke=color, width=1.7, opacity=0.95, marker=True))


def _draw_geometry_layers(
    parts: List[str],
    mapper,
    *,
    main_track: Dict[str, Any],
    triangles: Sequence[Dict[str, Any]],
    loops: Sequence[Dict[str, Any]],
    raw_center: Sequence[Sequence[float]],
    current_center: Sequence[Sequence[float]],
    candidate00: Dict[str, Any],
    candidate05: Dict[str, Any],
    candidate08: Dict[str, Any],
    include_surface: bool = True,
    include_main: bool = True,
) -> None:
    if include_main:
        _draw_main(parts, main_track, mapper)
    if include_surface:
        _draw_surface(parts, triangles, mapper)
        _draw_boundary(parts, loops, mapper)
    parts.append(_polyline(raw_center, mapper, stroke=COLORS["raw"], width=1.8, opacity=0.88, dash="7,5"))
    parts.append(_polyline(_xy_points(candidate00["pitCenterline"]), mapper, stroke=COLORS["candidate_00_00"], width=1.5, opacity=0.74, dash="5,6"))
    parts.append(_polyline(_xy_points(candidate05["pitCenterline"]), mapper, stroke=COLORS["candidate_05_05"], width=2.0, opacity=0.95))
    parts.append(_polyline(_xy_points(candidate08["pitCenterline"]), mapper, stroke=COLORS["candidate_08_08"], width=2.0, opacity=0.95))
    parts.append(_polyline(current_center, mapper, stroke=COLORS["current"], width=2.8, opacity=0.98))
    _draw_direction_arrows(parts, current_center, mapper, COLORS["current"])


def _label_point(parts: List[str], mapper, point: Sequence[float], label: str, color: str, dx: float = 7.0, dy: float = -7.0, radius: float = 4.5) -> None:
    x, y = mapper(point)
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{color}" fill-opacity="0.98"/>')
    parts.append(f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" fill="{color}" font-size="10" font-family="monospace">{_xml(label)}</text>')


def _draw_legend(parts: List[str], x: float, y: float) -> None:
    items = [
        ("MainTrackGeometry", COLORS["main"]),
        ("PitLaneSurface", COLORS["surface"]),
        ("raw centerline", COLORS["raw"]),
        ("current trimmed", COLORS["current"]),
        ("candidate_05_05", COLORS["candidate_05_05"]),
        ("candidate_08_08", COLORS["candidate_08_08"]),
    ]
    for index, (label, color) in enumerate(items):
        yy = y + index * 17
        parts.append(f'<rect x="{x}" y="{yy - 10}" width="10" height="10" fill="{color}" fill-opacity="0.9"/>')
        parts.append(f'<text x="{x + 16}" y="{yy}" fill="#cbd5e1" font-size="10" font-family="monospace">{_xml(label)}</text>')


def _draw_zoom_metrics(
    parts: List[str],
    x: float,
    y: float,
    *,
    title: str,
    rows: Sequence[Tuple[str, str, float, float]],
) -> None:
    parts.append(f'<rect x="{x - 8}" y="{y - 16}" width="342" height="{24 + len(rows) * 16}" fill="#020617" fill-opacity="0.76" stroke="#1e293b"/>')
    parts.append(f'<text x="{x}" y="{y}" fill="#e2e8f0" font-size="10" font-family="monospace">{_xml(title)}</text>')
    for index, (label, color, delta, main_dist) in enumerate(rows):
        yy = y + 16 + index * 16
        parts.append(f'<text x="{x}" y="{yy}" fill="{color}" font-size="9" font-family="monospace">{_xml(label)} delta={delta:.2f}m mainEdge={main_dist:.2f}m</text>')


def _draw_profile_panel(
    parts: List[str],
    profile: Sequence[Dict[str, Any]],
    markers: Dict[str, Tuple[int, int, str]],
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
) -> None:
    parts.append(f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" fill="#0b1020" stroke="#1e293b"/>')
    _draw_panel_title(parts, x0 + 14, y0 + 24, "PANEL 4 - LINEAR PITLANE PROFILE", "x-axis = raw pit index; series normalized independently")
    plot_x = x0 + 60
    plot_y = y0 + 70
    plot_w = width - 94
    plot_h = height - 118
    parts.append(f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" fill="#020617" stroke="#334155"/>')
    if not profile:
        return

    max_index = max(1, len(profile) - 1)
    series = {
        "width": [float(row["pitWidth"]) for row in profile],
        "distance": [float(row["distanceToMainCenterline"]) for row in profile],
        "angle": [float(row["tangentAngleDiffDeg"]) for row in profile],
    }

    def sx(index: int) -> float:
        return plot_x + (index / max_index) * plot_w

    def sy(value: float, values: Sequence[float]) -> float:
        min_value = min(values)
        max_value = max(values)
        if max_value - min_value <= 1e-9:
            return plot_y + plot_h * 0.5
        ratio = (value - min_value) / (max_value - min_value)
        return plot_y + plot_h - ratio * plot_h

    for key, color in (("width", COLORS["width"]), ("distance", COLORS["distance"]), ("angle", COLORS["angle"])):
        values = series[key]
        point_text = " ".join(f"{sx(index):.2f},{sy(value, values):.2f}" for index, value in enumerate(values))
        parts.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="1.8" stroke-opacity="0.95"/>')
        stats = f'{key}: min={min(values):.1f} avg={sum(values)/len(values):.1f} max={max(values):.1f}'
        parts.append(f'<text x="{plot_x + 8}" y="{plot_y + 18 + list(series).index(key) * 16}" fill="{color}" font-size="10" font-family="monospace">{_xml(stats)}</text>')

    for label, (start, end, color) in markers.items():
        for index, suffix in ((start, "S"), (end, "E")):
            x = sx(index)
            parts.append(f'<line x1="{x:.2f}" y1="{plot_y}" x2="{x:.2f}" y2="{plot_y + plot_h}" stroke="{color}" stroke-width="1.2" stroke-dasharray="5,4"/>')
            parts.append(f'<text x="{x + 3:.2f}" y="{plot_y + plot_h - 5}" fill="{color}" font-size="8" font-family="monospace">{_xml(label)} {suffix}</text>')

    parts.append(f'<text x="{plot_x}" y="{plot_y + plot_h + 28}" fill="#94a3b8" font-size="10" font-family="monospace">0</text>')
    parts.append(f'<text x="{plot_x + plot_w - 34}" y="{plot_y + plot_h + 28}" fill="#94a3b8" font-size="10" font-family="monospace">{len(profile) - 1}</text>')


def build_validation() -> Tuple[Dict[str, Any], str]:
    boundary = _load_json(DEBUG_DIR / "interlagos_pitlane_surface_boundary.json")
    raw = _load_json(DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry.json")
    minimal = _load_json(DEBUG_DIR / "interlagos_pitlane_trim_candidates_minimal.json")
    profile = _load_json(DEBUG_DIR / "interlagos_pitlane_trim_profile.json")
    trim_report = _load_json(DEBUG_DIR / "interlagos_pitlane_trim_report.json")
    current = _load_json(DEBUG_DIR / "interlagos_pitlane_trimmed_geometry.json")
    main = _load_json(CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json")

    triangles = boundary["pitSurfaceTriangles"]
    loops = boundary["pitBoundaryLoops"]["cleanLoops"]
    raw_center = _xy_points(raw["pitCenterline"])
    raw_left = _xy_points(raw["pitLeftEdge"])
    raw_right = _xy_points(raw["pitRightEdge"])
    current_center = _xy_points(current["pitCenterline"])
    current_left = _xy_points(current["pitLeftEdge"])
    current_right = _xy_points(current["pitRightEdge"])
    candidate00 = _candidate_by_name(minimal, "candidate_00_00")
    candidate05 = _candidate_by_name(minimal, "candidate_05_05")
    candidate08 = _candidate_by_name(minimal, "candidate_08_08")
    raw_count = len(raw_center)
    raw_length = float(minimal["rawLength"])
    current_start_index = int(trim_report["selectedStartIndex"])
    current_end_index = int(trim_report["selectedEndIndex"])
    current_length = float(trim_report["trimmedLength"])

    candidate05_start, candidate05_end = _candidate_start_end(candidate05)
    candidate08_start, candidate08_end = _candidate_start_end(candidate08)
    candidate00_start, candidate00_end = _candidate_start_end(candidate00)
    current_start, current_end = current_center[0], current_center[-1]
    raw_start, raw_end = raw_center[0], raw_center[-1]
    candidate05_start_index, candidate05_end_index = _candidate_indices(candidate05, raw_count)
    candidate08_start_index, candidate08_end_index = _candidate_indices(candidate08, raw_count)
    candidate00_start_index, candidate00_end_index = _candidate_indices(candidate00, raw_count)

    contained_points = current_center + current_left + current_right
    contained_ratio = _contained_ratio(contained_points, triangles)
    current_start_removed = _raw_distance(raw["pitCenterline"], current_start_index)
    current_end_removed = raw_length - _raw_distance(raw["pitCenterline"], current_end_index)
    candidate05_start_distance = float(candidate05["removedStartMeters"])
    candidate05_end_distance = float(candidate05["removedEndMeters"])
    candidate08_start_distance = float(candidate08["removedStartMeters"])
    candidate08_end_distance = float(candidate08["removedEndMeters"])

    trimmed_start_edge_distance = _nearest_main_edge_distance(current_start, main)
    trimmed_end_edge_distance = _nearest_main_edge_distance(current_end, main)

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runtimeChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "canonicalMapSpaceChanged": False,
        "candidateSelectedAutomatically": False,
        "rawPointCount": raw_count,
        "trimmedPointCount": len(current_center),
        "rawLengthMeters": _round(raw_length),
        "trimmedLengthMeters": _round(current_length),
        "trimmedStartIndex": current_start_index,
        "trimmedEndIndex": current_end_index,
        "trimmedStartDistanceFromRawStartMeters": _round(current_start_removed),
        "trimmedEndDistanceFromRawEndMeters": _round(current_end_removed),
        "trimmedContainedInSurfaceRatio": _round(contained_ratio),
        "trimmedStartToMainTrackMinDistance": _round(trimmed_start_edge_distance),
        "trimmedEndToMainTrackMinDistance": _round(trimmed_end_edge_distance),
        "candidate05StartDistance": _round(candidate05_start_distance),
        "candidate05EndDistance": _round(candidate05_end_distance),
        "candidate08StartDistance": _round(candidate08_start_distance),
        "candidate08EndDistance": _round(candidate08_end_distance),
        "candidateDistancesToCurrentTrimmed": {
            "candidate_05_05": {
                "startToCurrentTrimmedStartMeters": _round(abs(current_start_removed - candidate05_start_distance)),
                "endToCurrentTrimmedEndMeters": _round(abs(current_end_removed - candidate05_end_distance)),
                "startToMainTrackMinDistance": _round(_nearest_main_edge_distance(candidate05_start, main)),
                "endToMainTrackMinDistance": _round(_nearest_main_edge_distance(candidate05_end, main)),
            },
            "candidate_08_08": {
                "startToCurrentTrimmedStartMeters": _round(abs(current_start_removed - candidate08_start_distance)),
                "endToCurrentTrimmedEndMeters": _round(abs(current_end_removed - candidate08_end_distance)),
                "startToMainTrackMinDistance": _round(_nearest_main_edge_distance(candidate08_start, main)),
                "endToMainTrackMinDistance": _round(_nearest_main_edge_distance(candidate08_end, main)),
            },
        },
        "manualAssessmentHints": {
            "too_far_back_start": current_start_removed < 5.0,
            "too_far_forward_start": current_start_removed > 25.0,
            "too_far_back_end": current_end_removed > 25.0,
            "too_far_forward_end": current_end_removed < 5.0,
        },
        "notes": [
            "This report is debug/export only.",
            "Current trimmed geometry is shown for validation but no candidate is selected automatically.",
            "Distances named candidate05/08StartDistance and candidate05/08EndDistance are meters removed from raw start/end.",
        ],
        "exports": {
            "svg": str(DEBUG_DIR / "interlagos_pitlane_validation_final.svg"),
            "json": str(DEBUG_DIR / "interlagos_pitlane_validation_final.json"),
        },
    }

    width, height = 1800, 1360
    panel_w, panel_h = 870, 610
    gap = 24
    x_left, x_right = 24, 24 + panel_w + gap
    y_top, y_bottom = 72, 72 + panel_h + gap
    parts = _svg_header(width, height)
    parts.append('<text x="24" y="32" fill="#e2e8f0" font-size="18" font-family="monospace">Interlagos PitLaneGeometry final validation</text>')
    parts.append('<text x="24" y="54" fill="#94a3b8" font-size="11" font-family="monospace">debug/export only; no runtime changes; canonical map-space mapX=worldX,mapY=-worldZ</text>')

    main_bounds = main.get("bounds")
    surface_bounds = boundary.get("pitSurfaceBounds")
    overview_bounds = _expand_bounds(_merge_bounds(main_bounds, surface_bounds), 20.0)
    overview_map = lambda point: map_to_svg(point, overview_bounds, x_left, y_top, panel_w, panel_h, 28.0)
    parts.append(f'<rect x="{x_left}" y="{y_top}" width="{panel_w}" height="{panel_h}" fill="#0b1020" stroke="#1e293b"/>')
    _draw_panel_title(parts, x_left + 14, y_top + 24, "PANEL 1 - OVERVIEW GERAL", "pitlane relative to full MainTrackGeometry")
    _draw_geometry_layers(
        parts,
        overview_map,
        main_track=main,
        triangles=triangles,
        loops=loops,
        raw_center=raw_center,
        current_center=current_center,
        candidate00=candidate00,
        candidate05=candidate05,
        candidate08=candidate08,
    )
    _label_point(parts, overview_map, raw_start, "raw start", "#fdba74", dy=13)
    _label_point(parts, overview_map, raw_end, "raw end", "#93c5fd", dy=13)
    _label_point(parts, overview_map, current_start, "trimmed start", COLORS["current"], dy=-12)
    _label_point(parts, overview_map, current_end, "trimmed end", COLORS["current"], dy=-12)
    _draw_legend(parts, x_left + 16, y_top + panel_h - 112)

    start_points = raw_center[:36] + raw_left[:36] + raw_right[:36] + [current_start, candidate05_start, candidate08_start, candidate00_start]
    start_bounds = _expand_bounds(_merge_bounds(_bounds(start_points)), 18.0)
    start_map = lambda point: map_to_svg(point, start_bounds, x_right, y_top, panel_w, panel_h, 28.0)
    parts.append(f'<rect x="{x_right}" y="{y_top}" width="{panel_w}" height="{panel_h}" fill="#0b1020" stroke="#1e293b"/>')
    _draw_panel_title(parts, x_right + 14, y_top + 24, "PANEL 2 - ZOOM DA ENTRADA DA PITLANE", "start positions and distances to current trimmed")
    _draw_geometry_layers(
        parts,
        start_map,
        main_track=main,
        triangles=triangles,
        loops=loops,
        raw_center=raw_center,
        current_center=current_center,
        candidate00=candidate00,
        candidate05=candidate05,
        candidate08=candidate08,
    )
    _label_point(parts, start_map, raw_start, "raw start", "#fdba74", dy=13)
    _label_point(parts, start_map, current_start, "trimmed start", COLORS["current"], dy=-12)
    _label_point(parts, start_map, candidate05_start, "candidate_05_05 start", COLORS["candidate_05_05"], dy=22)
    _label_point(parts, start_map, candidate08_start, "candidate_08_08 start", COLORS["candidate_08_08"], dy=34)
    _draw_zoom_metrics(
        parts,
        x_right + 18,
        y_top + panel_h - 92,
        title="start distances",
        rows=[
            ("raw -> current", COLORS["current"], current_start_removed, trimmed_start_edge_distance),
            ("05 -> current", COLORS["candidate_05_05"], abs(current_start_removed - candidate05_start_distance), _nearest_main_edge_distance(candidate05_start, main)),
            ("08 -> current", COLORS["candidate_08_08"], abs(current_start_removed - candidate08_start_distance), _nearest_main_edge_distance(candidate08_start, main)),
        ],
    )

    end_points = raw_center[-36:] + raw_left[-36:] + raw_right[-36:] + [current_end, candidate05_end, candidate08_end, candidate00_end]
    end_bounds = _expand_bounds(_merge_bounds(_bounds(end_points)), 18.0)
    end_map = lambda point: map_to_svg(point, end_bounds, x_left, y_bottom, panel_w, panel_h, 28.0)
    parts.append(f'<rect x="{x_left}" y="{y_bottom}" width="{panel_w}" height="{panel_h}" fill="#0b1020" stroke="#1e293b"/>')
    _draw_panel_title(parts, x_left + 14, y_bottom + 24, "PANEL 3 - ZOOM DA SAIDA DA PITLANE", "end positions and distances to current trimmed")
    _draw_geometry_layers(
        parts,
        end_map,
        main_track=main,
        triangles=triangles,
        loops=loops,
        raw_center=raw_center,
        current_center=current_center,
        candidate00=candidate00,
        candidate05=candidate05,
        candidate08=candidate08,
    )
    _label_point(parts, end_map, raw_end, "raw end", "#93c5fd", dy=13)
    _label_point(parts, end_map, current_end, "trimmed end", COLORS["current"], dy=-12)
    _label_point(parts, end_map, candidate05_end, "candidate_05_05 end", COLORS["candidate_05_05"], dy=22)
    _label_point(parts, end_map, candidate08_end, "candidate_08_08 end", COLORS["candidate_08_08"], dy=34)
    _draw_zoom_metrics(
        parts,
        x_left + 18,
        y_bottom + panel_h - 92,
        title="end distances",
        rows=[
            ("raw -> current", COLORS["current"], current_end_removed, trimmed_end_edge_distance),
            ("05 -> current", COLORS["candidate_05_05"], abs(current_end_removed - candidate05_end_distance), _nearest_main_edge_distance(candidate05_end, main)),
            ("08 -> current", COLORS["candidate_08_08"], abs(current_end_removed - candidate08_end_distance), _nearest_main_edge_distance(candidate08_end, main)),
        ],
    )

    marker_data = {
        "current": (current_start_index, current_end_index, COLORS["current"]),
        "c05": (candidate05_start_index, candidate05_end_index, COLORS["candidate_05_05"]),
        "c08": (candidate08_start_index, candidate08_end_index, COLORS["candidate_08_08"]),
        "c00": (candidate00_start_index, candidate00_end_index, COLORS["candidate_00_00"]),
    }
    _draw_profile_panel(parts, profile.get("profile", []), marker_data, x0=x_right, y0=y_bottom, width=panel_w, height=panel_h)
    parts.append("</svg>")
    svg = "\n".join(part for part in parts if part)
    return report, svg


def main() -> None:
    report, svg = build_validation()
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / "interlagos_pitlane_validation_final.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / "interlagos_pitlane_validation_final.svg").write_text(svg, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
