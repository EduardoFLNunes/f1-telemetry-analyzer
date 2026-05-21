from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PIT_AREA_SURFACE_JSON = DEBUG_DIR / "interlagos_pit_area_surface.json"
PIT_AREA_COMPONENTS_JSON = DEBUG_DIR / "interlagos_pit_area_components.json"
PIT_AREA_CENTERLINES_JSON = DEBUG_DIR / "interlagos_pit_area_centerlines.json"
PIT_AREA_FINAL_REPORT_JSON = DEBUG_DIR / "interlagos_pit_area_final_report.json"

FINAL_JSON = DEBUG_DIR / "interlagos_pit_area_final_clean_validation.json"
FINAL_SVG = DEBUG_DIR / "interlagos_pit_area_final_clean_validation.svg"
ENTRY_ZOOM_SVG = DEBUG_DIR / "interlagos_pit_area_entry_access_clean_zoom.svg"
EXIT_ZOOM_SVG = DEBUG_DIR / "interlagos_pit_area_exit_access_clean_zoom.svg"

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def as_point(raw: Any, *, flip_y: bool = False) -> Optional[Point]:
    if isinstance(raw, dict):
        x = raw.get("x")
        y = raw.get("y", raw.get("z"))
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        x, y = raw[0], raw[1]
    else:
        return None
    try:
        point = (float(x), float(y))
    except (TypeError, ValueError):
        return None
    return (point[0], -point[1]) if flip_y else point


def points(raw_points: Iterable[Any], *, flip_y: bool = False) -> List[Point]:
    return [point for point in (as_point(raw, flip_y=flip_y) for raw in raw_points or []) if point is not None]


def triangle_points(triangle: Dict[str, Any]) -> List[Point]:
    return points(triangle.get("vertices", []))


def decimate(items: Sequence[Any], max_count: int) -> List[Any]:
    if len(items) <= max_count:
        return list(items)
    step = max(1, math.ceil(len(items) / max_count))
    return [item for index, item in enumerate(items) if index % step == 0][:max_count]


def bounds(all_points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    pts = [point for point in all_points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    return {
        "minX": min(xs) - pad,
        "maxX": max(xs) + pad,
        "minY": min(ys) - pad,
        "maxY": max(ys) + pad,
    }


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def nearest_distance_to_points(point: Point, reference: Sequence[Point]) -> float:
    return min((distance(point, candidate) for candidate in reference), default=float("inf"))


def local_points(reference: Sequence[Point], focus: Sequence[Point], radius: float) -> List[Point]:
    focus_sample = decimate(focus, 80)
    return [point for point in reference if nearest_distance_to_points(point, focus_sample) <= radius]


def triangle_is_near(triangle: Dict[str, Any], focus: Sequence[Point], radius: float) -> bool:
    vertices = triangle_points(triangle)
    if not vertices:
        return False
    centroid = (
        sum(point[0] for point in vertices) / len(vertices),
        sum(point[1] for point in vertices) / len(vertices),
    )
    return nearest_distance_to_points(centroid, focus) <= radius


def component_triangles(components: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
    for component in components.get("components", []) or []:
        if component.get("name") == name:
            return list(component.get("sampleTriangles", []) or [])
    return []


def svg_transform(view: Dict[str, float], width: int, height: int, margin: int):
    span_x = max(view["maxX"] - view["minX"], 1.0)
    span_y = max(view["maxY"] - view["minY"], 1.0)
    scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_y)

    def transform(point: Point) -> Tuple[float, float]:
        x = margin + (point[0] - view["minX"]) * scale
        y = height - margin - (point[1] - view["minY"]) * scale
        return x, y

    return transform


def svg_path(points_: Sequence[Point], transform, *, close: bool = False) -> str:
    pts = [transform(point) for point in points_ if point is not None]
    if not pts:
        return ""
    commands = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in pts[1:])
    if close:
        commands.append("Z")
    return " ".join(commands)


def triangle_path(triangle: Dict[str, Any], transform) -> str:
    return svg_path(triangle_points(triangle), transform, close=True)


def svg_label(text: str, point: Point, transform, color: str) -> str:
    x, y = transform(point)
    label = html.escape(text)
    return (
        f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" fill="{color}" '
        'font-family="Consolas, monospace" font-size="13" font-weight="700" '
        f'paint-order="stroke" stroke="#05070b" stroke-width="3">{label}</text>'
    )


def midpoint(line: Sequence[Point]) -> Point:
    return line[len(line) // 2] if line else (0.0, 0.0)


def load_scene() -> Dict[str, Any]:
    main_track = points(read_json(MAIN_TRACK_JSON).get("centerline", []), flip_y=True)
    surface = read_json(PIT_AREA_SURFACE_JSON)
    components = read_json(PIT_AREA_COMPONENTS_JSON)
    centerlines = read_json(PIT_AREA_CENTERLINES_JSON)
    report = read_json(PIT_AREA_FINAL_REPORT_JSON)
    centerline_payload = centerlines.get("centerlines", {})
    ai_refs = centerlines.get("aiReferences", {})
    return {
        "mainTrack": main_track,
        "surface": surface,
        "surfaceTriangles": list(surface.get("triangles", []) or []),
        "entryTriangles": component_triangles(components, "PitEntryAccessArea"),
        "exitTriangles": component_triangles(components, "PitExitAccessArea"),
        "corridorTriangles": component_triangles(components, "PitLaneCorridor"),
        "corridor": points((centerline_payload.get("PitLaneCorridorCenterline") or {}).get("centerline", [])),
        "entry": points((centerline_payload.get("PitEntryAccessCenterline") or {}).get("centerline", [])),
        "exit": points((centerline_payload.get("PitExitAccessCenterline") or {}).get("centerline", [])),
        "fastLane": points((ai_refs.get("fastLane") or {}).get("centerline", [])),
        "pitLaneAi": points((ai_refs.get("pitLane") or {}).get("centerline", [])),
        "report": report,
        "components": components,
    }


def draw_clean_svg(path: Path, scene: Dict[str, Any], *, title: str, focus: Optional[str] = None) -> None:
    width, height, margin = 1500, 980, 40
    main_track = scene["mainTrack"]
    corridor = scene["corridor"]
    entry = scene["entry"]
    exit_ = scene["exit"]
    fast_lane = scene["fastLane"]
    pit_lane_ai = scene["pitLaneAi"]

    if focus == "entry":
        focus_line = entry
        pit_area_triangles = [
            triangle
            for triangle in [*scene["entryTriangles"], *scene["corridorTriangles"]]
            if triangle_is_near(triangle, focus_line, 82.0)
        ]
        view_points = [
            *focus_line,
            *local_points(corridor, focus_line, 100.0),
            *local_points(main_track, focus_line, 135.0),
            *(point for triangle in pit_area_triangles for point in triangle_points(triangle)),
        ]
        view = bounds(view_points, pad=42.0)
        surface_triangles = pit_area_triangles
    elif focus == "exit":
        focus_line = exit_
        pit_area_triangles = [
            triangle
            for triangle in [*scene["exitTriangles"], *scene["corridorTriangles"]]
            if triangle_is_near(triangle, focus_line, 82.0)
        ]
        view_points = [
            *focus_line,
            *local_points(corridor, focus_line, 100.0),
            *local_points(main_track, focus_line, 135.0),
            *(point for triangle in pit_area_triangles for point in triangle_points(triangle)),
        ]
        view = bounds(view_points, pad=42.0)
        surface_triangles = pit_area_triangles
    else:
        surface_triangles = decimate(scene["surfaceTriangles"], 4600)
        view = bounds(
            [
                *main_track,
                *corridor,
                *entry,
                *exit_,
                *(point for triangle in surface_triangles for point in triangle_points(triangle)),
            ],
            pad=34.0,
        )

    transform = svg_transform(view, width, height, margin)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#070a12"/>',
        f'<text x="24" y="30" fill="#e2e8f0" font-family="Consolas, monospace" font-size="15">{html.escape(title)}</text>',
        '<text x="24" y="50" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">debug/export only; runtime unchanged</text>',
    ]

    if main_track:
        lines.append(f'<path d="{svg_path(main_track, transform, close=True)}" fill="none" stroke="#8b949e" stroke-width="1.4" opacity="0.64"/>')
    if fast_lane:
        lines.append(f'<path d="{svg_path(fast_lane, transform, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.05" stroke-dasharray="8 8" opacity="0.55"/>')
    if pit_lane_ai:
        lines.append(f'<path d="{svg_path(pit_lane_ai, transform)}" fill="none" stroke="#22d3ee" stroke-width="1.45" stroke-dasharray="8 7" opacity="0.82"/>')

    for triangle in surface_triangles:
        path_data = triangle_path(triangle, transform)
        if path_data:
            lines.append(f'<path d="{path_data}" fill="#facc15" fill-opacity="0.075" stroke="#facc15" stroke-width="0.22" stroke-opacity="0.12"/>')

    for triangle in scene["corridorTriangles"]:
        if focus and not triangle_is_near(triangle, entry if focus == "entry" else exit_, 86.0):
            continue
        path_data = triangle_path(triangle, transform)
        if path_data:
            lines.append(f'<path d="{path_data}" fill="#facc15" fill-opacity="0.18" stroke="#facc15" stroke-width="0.28" stroke-opacity="0.24"/>')
    for triangle in scene["entryTriangles"]:
        if focus == "exit":
            continue
        if focus == "entry" and not triangle_is_near(triangle, entry, 86.0):
            continue
        path_data = triangle_path(triangle, transform)
        if path_data:
            lines.append(f'<path d="{path_data}" fill="#22c55e" fill-opacity="0.22" stroke="#22c55e" stroke-width="0.34" stroke-opacity="0.42"/>')
    for triangle in scene["exitTriangles"]:
        if focus == "entry":
            continue
        if focus == "exit" and not triangle_is_near(triangle, exit_, 86.0):
            continue
        path_data = triangle_path(triangle, transform)
        if path_data:
            lines.append(f'<path d="{path_data}" fill="#fb923c" fill-opacity="0.24" stroke="#fb923c" stroke-width="0.34" stroke-opacity="0.44"/>')

    if corridor:
        lines.append(f'<path d="{svg_path(corridor, transform)}" fill="none" stroke="#fde047" stroke-width="4.0" opacity="0.95"/>')
    if entry:
        lines.append(f'<path d="{svg_path(entry, transform)}" fill="none" stroke="#22c55e" stroke-width="4.0" opacity="0.96"/>')
    if exit_:
        lines.append(f'<path d="{svg_path(exit_, transform)}" fill="none" stroke="#fb923c" stroke-width="4.0" opacity="0.96"/>')

    labels = [
        ("PIT ENTRY ACCESS", midpoint(entry), "#86efac"),
        ("PIT CORRIDOR", midpoint(corridor), "#fef08a"),
        ("PIT EXIT ACCESS", midpoint(exit_), "#fed7aa"),
    ]
    for label, point, color in labels:
        if point:
            lines.append(svg_label(label, point, transform, color))

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    scene = load_scene()
    report = scene["report"]
    component_by_name = {component.get("name"): component for component in scene["components"].get("components", []) or []}
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "pitAreaGenerated": bool(report.get("pitAreaGenerated")),
        "pitAreaIncludesCorridor": bool(report.get("pitAreaIncludesCorridor")),
        "pitAreaIncludesEntryAccess": bool(report.get("pitAreaIncludesEntryAccess")),
        "pitAreaIncludesExitAccess": bool(report.get("pitAreaIncludesExitAccess")),
        "entryAccessConfidence": (component_by_name.get("PitEntryAccessArea") or {}).get("confidence"),
        "exitAccessConfidence": (component_by_name.get("PitExitAccessArea") or {}).get("confidence"),
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "sourceFiles": {
            "pitAreaSurface": str(PIT_AREA_SURFACE_JSON),
            "pitAreaComponents": str(PIT_AREA_COMPONENTS_JSON),
            "pitAreaCenterlines": str(PIT_AREA_CENTERLINES_JSON),
            "pitAreaFinalReport": str(PIT_AREA_FINAL_REPORT_JSON),
        },
        "exports": {
            "overviewSvg": str(FINAL_SVG),
            "entryZoomSvg": str(ENTRY_ZOOM_SVG),
            "exitZoomSvg": str(EXIT_ZOOM_SVG),
        },
    }
    write_json(FINAL_JSON, payload)
    draw_clean_svg(FINAL_SVG, scene, title="Interlagos PitAreaGeometry final clean validation")
    draw_clean_svg(ENTRY_ZOOM_SVG, scene, title="PitAreaGeometry entry access clean zoom", focus="entry")
    draw_clean_svg(EXIT_ZOOM_SVG, scene, title="PitAreaGeometry exit access clean zoom", focus="exit")
    print(f"Wrote {FINAL_JSON}")
    print(f"Wrote {FINAL_SVG}")
    print(f"Wrote {ENTRY_ZOOM_SVG}")
    print(f"Wrote {EXIT_ZOOM_SVG}")


if __name__ == "__main__":
    build()
