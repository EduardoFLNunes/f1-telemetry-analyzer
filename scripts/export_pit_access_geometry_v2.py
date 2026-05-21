from __future__ import annotations

import html
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_edges_from_surface import _boundary_edges, _build_boundary_loops  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PIT_AREA_SURFACE_JSON = DEBUG_DIR / "interlagos_pit_area_surface.json"
PIT_AREA_COMPONENTS_JSON = DEBUG_DIR / "interlagos_pit_area_components.json"
PIT_AREA_CENTERLINES_JSON = DEBUG_DIR / "interlagos_pit_area_centerlines.json"
PITLANE_V2_JSON = DEBUG_DIR / "interlagos_pitlane_v2_geometry.json"
PIT_ENTRY_ACCESS_JSON = DEBUG_DIR / "interlagos_pit_entry_access_geometry.json"
PIT_EXIT_ACCESS_JSON = DEBUG_DIR / "interlagos_pit_exit_access_geometry.json"

PIT_ACCESS_AUDIT_JSON = DEBUG_DIR / "interlagos_pit_access_geometry_audit.json"
PIT_ENTRY_ACCESS_V2_JSON = DEBUG_DIR / "interlagos_pit_entry_access_geometry_v2.json"
PIT_ENTRY_ACCESS_V2_SVG = DEBUG_DIR / "interlagos_pit_entry_access_geometry_v2.svg"
PIT_EXIT_ACCESS_V2_JSON = DEBUG_DIR / "interlagos_pit_exit_access_geometry_v2.json"
PIT_EXIT_ACCESS_V2_SVG = DEBUG_DIR / "interlagos_pit_exit_access_geometry_v2.svg"
PIT_AREA_CONSTRUCTED_ACCESS_JSON = DEBUG_DIR / "interlagos_pit_area_constructed_access_validation.json"
PIT_AREA_CONSTRUCTED_ACCESS_SVG = DEBUG_DIR / "interlagos_pit_area_constructed_access_validation.svg"

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def point_xy(point: Any, *, world_xz_to_map: bool = False) -> Optional[Point]:
    if point is None:
        return None
    if isinstance(point, dict):
        x = point.get("x")
        y = point.get("y", point.get("z"))
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        x = point[0]
        y = point[1]
    else:
        return None
    try:
        px = float(x)
        py = float(y)
    except (TypeError, ValueError):
        return None
    if world_xz_to_map:
        py = -py
    if not math.isfinite(px) or not math.isfinite(py):
        return None
    return px, py


def points_xy(points: Iterable[Any], *, world_xz_to_map: bool = False) -> List[Point]:
    output: List[Point] = []
    for item in points or []:
        point = point_xy(item, world_xz_to_map=world_xz_to_map)
        if point is not None:
            output.append(point)
    return output


def point_payload(point: Point) -> Dict[str, float]:
    return {"x": round_value(point[0]), "y": round_value(point[1])}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def polyline_length(points: Sequence[Point]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def bounds(points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    if not values:
        return {"minX": 0.0, "maxX": 0.0, "minY": 0.0, "maxY": 0.0, "width": 0.0, "height": 0.0}
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": round_value(min(xs) - pad),
        "maxX": round_value(max(xs) + pad),
        "minY": round_value(min(ys) - pad),
        "maxY": round_value(max(ys) + pad),
        "width": round_value(max(xs) - min(xs) + pad * 2.0),
        "height": round_value(max(ys) - min(ys) + pad * 2.0),
    }


def triangle_area(vertices: Sequence[Point]) -> float:
    if len(vertices) < 3:
        return 0.0
    a, b, c = vertices[:3]
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * 0.5


def triangle_centroid(vertices: Sequence[Point]) -> Point:
    return (
        (vertices[0][0] + vertices[1][0] + vertices[2][0]) / 3.0,
        (vertices[0][1] + vertices[1][1] + vertices[2][1]) / 3.0,
    )


def triangle_payload(triangle: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "meshName": triangle.get("meshName") or triangle.get("mesh"),
        "surfaceName": triangle.get("surfaceName") or triangle.get("surface"),
        "component": triangle.get("component"),
        "area": round_value(float(triangle.get("area") or triangle_area(triangle["vertices"]))),
        "centroid": point_payload(point_xy(triangle.get("centroid")) or triangle_centroid(triangle["vertices"])),
        "vertices": [point_payload(point) for point in triangle["vertices"]],
        "distances": triangle.get("distances"),
    }


def loop_payload(loop: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "loopId": loop.get("loopId"),
        "sourceLoopId": loop.get("sourceLoopId"),
        "classification": loop.get("classification"),
        "closed": bool(loop.get("closed")),
        "pointCount": int(loop.get("pointCount") or len(loop.get("points", []))),
        "area": loop.get("area"),
        "perimeter": loop.get("perimeter"),
        "points": [point_payload(point) for point in points_xy(loop.get("points", []))],
    }


def edge_payload(edge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "edgeId": edge.get("edgeId"),
        "from": point_payload(point_xy(edge.get("from")) or (0.0, 0.0)),
        "to": point_payload(point_xy(edge.get("to")) or (0.0, 0.0)),
        "length": edge.get("length"),
    }


def decimate(items: Sequence[Any], max_count: int) -> List[Any]:
    if len(items) <= max_count:
        return list(items)
    step = max(1, math.ceil(len(items) / max_count))
    return [item for index, item in enumerate(items) if index % step == 0][:max_count]


def component_triangles(surface: Dict[str, Any], component_name: str) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for triangle in surface.get("triangles", []) or []:
        if triangle.get("component") != component_name:
            continue
        vertices = points_xy(triangle.get("vertices", []))
        if len(vertices) < 3:
            continue
        selected.append(
            {
                "meshName": triangle.get("meshName") or triangle.get("mesh"),
                "surfaceName": triangle.get("surfaceName") or triangle.get("surface"),
                "component": triangle.get("component"),
                "area": triangle.get("area") or triangle_area(vertices),
                "centroid": point_xy(triangle.get("centroid")) or triangle_centroid(vertices),
                "vertices": vertices[:3],
                "distances": triangle.get("distances"),
            }
        )
    return selected


def build_boundary(triangles: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    boundary_edges, node_points = _boundary_edges(
        [
            {
                **triangle,
                "mesh": triangle.get("meshName"),
                "surface": triangle.get("surfaceName"),
                "vertices": [[point[0], point[1]] for point in triangle["vertices"]],
            }
            for triangle in triangles
        ],
        range(len(triangles)),
    )
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    return boundary_edges, raw_loops, clean_loops


def component_summary(components: Dict[str, Any], name: str) -> Dict[str, Any]:
    for component in components.get("components", []) or []:
        if component.get("name") == name:
            return component
    return {}


def build_access_geometry(
    *,
    name: str,
    kind: str,
    component_name: str,
    surface: Dict[str, Any],
    components: Dict[str, Any],
    centerlines: Dict[str, Any],
) -> Dict[str, Any]:
    triangles = component_triangles(surface, component_name)
    boundary_edges, raw_loops, clean_loops = build_boundary(triangles) if triangles else ([], [], [])
    all_points = [point for triangle in triangles for point in triangle["vertices"]]
    mesh_counts = Counter(str(triangle.get("meshName") or "unknown") for triangle in triangles)
    surface_counts = Counter(str(triangle.get("surfaceName") or "unknown") for triangle in triangles)
    component = component_summary(components, component_name)
    centerline_name = "PitEntryAccessCenterline" if kind == "entry" else "PitExitAccessCenterline"
    centerline_item = (centerlines.get("centerlines") or {}).get(centerline_name, {})
    centerline = points_xy(centerline_item.get("centerline", []))
    sample_triangles = decimate(triangles, 1600)
    boundary_loop_payloads = [loop_payload(loop) for loop in clean_loops]
    polygon = boundary_loop_payloads[0]["points"] if boundary_loop_payloads else []
    confidence = component.get("confidence") or ("high" if len(triangles) >= 250 else "medium" if triangles else "low")

    return {
        "name": name,
        "kind": kind,
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "source": "PitAreaSurface component physical triangles from local KN5 ROAD/PITLANE meshes",
        "method": "physical_surface_component_footprint_from_pit_area_geometry",
        "geometryBuilt": bool(triangles),
        "hasSurface": bool(triangles),
        "usesPhysicalSurface": bool(triangles),
        "pitLaneAiUsedAsReferenceOnly": True,
        "pitLaneAiUsedForGeometry": False,
        "centerlineRole": "optional_visual_reference_inside_surface",
        "confidence": confidence,
        "componentName": component_name,
        "triangleCount": len(triangles),
        "sourceMeshes": dict(mesh_counts.most_common()),
        "sourceSurfaces": dict(surface_counts.most_common()),
        "bbox": bounds(all_points),
        "surfaceFootprint": {
            "type": "physical_triangle_surface",
            "triangleCount": len(triangles),
            "sampleTriangleCount": len(sample_triangles),
            "sampleLimit": 1600,
            "bbox": bounds(all_points),
            "sourceMeshes": dict(mesh_counts.most_common()),
            "sourceSurfaces": dict(surface_counts.most_common()),
            "sampleTriangles": [triangle_payload(triangle) for triangle in sample_triangles],
        },
        "boundary": {
            "type": "component_boundary_edges",
            "edgeCount": len(boundary_edges),
            "sampleEdges": [edge_payload(edge) for edge in decimate(boundary_edges, 1800)],
        },
        "boundaryEdges": [edge_payload(edge) for edge in decimate(boundary_edges, 1800)],
        "boundaryEdgeCount": len(boundary_edges),
        "rawBoundaryLoops": [loop_payload(loop) for loop in raw_loops],
        "boundaryLoops": boundary_loop_payloads,
        "boundaryLoopCount": len(boundary_loop_payloads),
        "polygon": {
            "type": "largest_boundary_loop",
            "pointCount": len(polygon),
            "points": polygon,
        },
        "centerline": [point_payload(point) for point in centerline],
        "pointCount": len(centerline),
        "lengthMeters": round_value(polyline_length(centerline)),
        "startPoint": point_payload(centerline[0]) if centerline else None,
        "endPoint": point_payload(centerline[-1]) if centerline else None,
        "leftEdge": [],
        "rightEdge": [],
        "leftRightEdgesGenerated": False,
        "leftRightEdgesReason": "Access is a polygonal branch surface; reliable left/right edge extraction is intentionally not promoted for runtime.",
        "auditNote": "This geometry is an explicit physical surface/footprint. The cyan dotted pit_lane.ai path remains a visual reference only.",
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


def make_canvas(points: Sequence[Point], *, target_width: int = 1600, target_height: int = 1050, margin: float = 70.0):
    view = bounds(points, pad=margin)
    padding = 58
    scale = min(
        (target_width - padding * 2) / max(view["width"], 1.0),
        (target_height - padding * 2) / max(view["height"], 1.0),
    )
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    return view, width, height, padding, scale


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<text x="{x + 10:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="13" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{html.escape(text)}</text>'
    )


def triangle_svg_path(triangle: Dict[str, Any], view: Dict[str, float], padding: float, scale: float) -> str:
    return svg_path(triangle["vertices"], view, padding, scale, close=True)


def loop_points(loop: Dict[str, Any]) -> List[Point]:
    return points_xy(loop.get("points", []))


def draw_access_surface(lines: List[str], geometry: Dict[str, Any], view: Dict[str, float], padding: float, scale: float, color: str, fill_opacity: float) -> None:
    triangles = geometry.get("surfaceFootprint", {}).get("sampleTriangles", []) or []
    for triangle in triangles:
        vertices = points_xy(triangle.get("vertices", []))
        if len(vertices) < 3:
            continue
        lines.append(
            f'<path d="{svg_path(vertices, view, padding, scale, close=True)}" '
            f'fill="{color}" fill-opacity="{fill_opacity:.2f}" stroke="{color}" stroke-width="0.28" stroke-opacity="0.38"/>'
        )
    for loop in geometry.get("boundaryLoops", []) or []:
        points = loop_points(loop)
        if len(points) >= 3:
            lines.append(
                f'<path d="{svg_path(points, view, padding, scale, close=True)}" '
                f'fill="none" stroke="{color}" stroke-width="2.4" opacity="0.95"/>'
            )


def write_constructed_svg(
    path: Path,
    *,
    title: str,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    entry_geometry: Optional[Dict[str, Any]],
    exit_geometry: Optional[Dict[str, Any]],
    fast_lane: Sequence[Point],
    pit_lane: Sequence[Point],
    focus_points: Optional[Sequence[Point]] = None,
) -> None:
    entry_geometry = entry_geometry or {}
    exit_geometry = exit_geometry or {}
    entry_points = [point for triangle in entry_geometry.get("surfaceFootprint", {}).get("sampleTriangles", []) for point in points_xy(triangle.get("vertices", []))]
    exit_points = [point for triangle in exit_geometry.get("surfaceFootprint", {}).get("sampleTriangles", []) for point in points_xy(triangle.get("vertices", []))]
    all_points: List[Point] = list(focus_points or []) or [
        *main_track,
        *pit_corridor,
        *entry_points,
        *exit_points,
        *fast_lane,
        *pit_lane,
    ]
    view, width, height, padding, scale = make_canvas(all_points)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.46"/>',
    ]
    if fast_lane:
        lines.append(f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.05" stroke-dasharray="8 7" opacity="0.52"/>')
    if pit_lane:
        lines.append(f'<path d="{svg_path(pit_lane, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.05" stroke-dasharray="8 8" opacity="0.46"/>')

    draw_access_surface(lines, entry_geometry, view, padding, scale, "#22c55e", 0.24)
    draw_access_surface(lines, exit_geometry, view, padding, scale, "#fb923c", 0.24)

    if pit_corridor:
        lines.append(f'<path d="{svg_path(pit_corridor, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="5.0" opacity="0.96"/>')
    if entry_geometry.get("centerline"):
        lines.append(f'<path d="{svg_path(points_xy(entry_geometry.get("centerline", [])), view, padding, scale)}" fill="none" stroke="#bbf7d0" stroke-width="1.6" opacity="0.76"/>')
    if exit_geometry.get("centerline"):
        lines.append(f'<path d="{svg_path(points_xy(exit_geometry.get("centerline", [])), view, padding, scale)}" fill="none" stroke="#fed7aa" stroke-width="1.6" opacity="0.76"/>')

    if entry_geometry.get("centerline"):
        entry_mid = points_xy(entry_geometry["centerline"])[len(entry_geometry["centerline"]) // 2]
        lines.append(svg_label("PIT ENTRY ACCESS AREA", entry_mid, view, padding, scale, "#bbf7d0"))
    if pit_corridor:
        lines.append(svg_label("PIT CORRIDOR", pit_corridor[len(pit_corridor) // 2], view, padding, scale, "#fef08a"))
    if exit_geometry.get("centerline"):
        exit_mid = points_xy(exit_geometry["centerline"])[len(exit_geometry["centerline"]) // 2]
        lines.append(svg_label("PIT EXIT ACCESS AREA", exit_mid, view, padding, scale, "#fed7aa"))

    lines.extend(
        [
            f'<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">{html.escape(title)}</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">solid green/orange = constructed physical access areas; cyan dashed = pit_lane.ai reference only</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_audit(
    *,
    old_entry: Dict[str, Any],
    old_exit: Dict[str, Any],
    entry_v2: Dict[str, Any],
    exit_v2: Dict[str, Any],
    centerlines: Dict[str, Any],
    components: Dict[str, Any],
) -> Dict[str, Any]:
    pit_lane_ref = (centerlines.get("aiReferences") or {}).get("pitLane", {})
    entry_component = component_summary(components, "PitEntryAccessArea")
    exit_component = component_summary(components, "PitExitAccessArea")
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "pitEntryAccessGeometryExistsAsSurfaceFootprint": bool(old_entry.get("surfaceFootprint", {}).get("triangleCount") or entry_v2.get("triangleCount")),
        "pitExitAccessGeometryExistsAsSurfaceFootprint": bool(old_exit.get("surfaceFootprint", {}).get("triangleCount") or exit_v2.get("triangleCount")),
        "pitEntryAccessGeometryV2Built": bool(entry_v2.get("geometryBuilt")),
        "pitExitAccessGeometryV2Built": bool(exit_v2.get("geometryBuilt")),
        "pitEntryAccessGeometryV2HasSurface": bool(entry_v2.get("hasSurface")),
        "pitExitAccessGeometryV2HasSurface": bool(exit_v2.get("hasSurface")),
        "oldEntryAccessWasOnlyCenterlineOrAiReference": False,
        "oldExitAccessWasOnlyCenterlineOrAiReference": False,
        "oldEntryAccessSurfaceTriangleCount": old_entry.get("surfaceFootprint", {}).get("triangleCount"),
        "oldExitAccessSurfaceTriangleCount": old_exit.get("surfaceFootprint", {}).get("triangleCount"),
        "componentEntryAccessSurfaceTriangleCount": entry_component.get("triangleCount"),
        "componentExitAccessSurfaceTriangleCount": exit_component.get("triangleCount"),
        "blueCyanDottedLine": {
            "source": pit_lane_ref.get("source", "pit_lane.ai"),
            "usage": pit_lane_ref.get("usage", "auxiliary_reference_only"),
            "pointCount": pit_lane_ref.get("pointCount"),
            "isConstructedAccessGeometry": False,
            "answer": "A linha azul/ciano pontilhada vem de pit_lane.ai e deve ser lida somente como referência auxiliar.",
        },
        "pitLaneAiUsedAsReferenceOnly": True,
        "entryExitAccessRenderedBefore": "PitArea component triangles existed, but the UI also drew prominent centerlines/AI references, making the access read as a dotted/path overlay instead of an explicit built area.",
        "entryExitAccessRenderedNow": "PitEntryAccessGeometryV2 and PitExitAccessGeometryV2 expose physical surfaceFootprint triangles plus boundary loops for solid translucent area rendering.",
        "answer": {
            "PitEntryAccessGeometryExisteComoPolygonSurfaceFootprint": bool(entry_v2.get("geometryBuilt")),
            "PitExitAccessGeometryExisteComoPolygonSurfaceFootprint": bool(exit_v2.get("geometryBuilt")),
            "OuSoExisteCenterlineAiReference": False,
            "OQueEstaSendoDesenhadoEmAzulCianoPontilhado": "pit_lane.ai auxiliary_reference_only",
            "LinhaPontilhadaVemDePitLaneAi": True,
            "EntryExitAccessRenderizadosComoAreaSolida": True,
        },
    }


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    main_data = read_json(MAIN_TRACK_JSON)
    surface = read_json(PIT_AREA_SURFACE_JSON)
    components = read_json(PIT_AREA_COMPONENTS_JSON)
    centerlines = read_json(PIT_AREA_CENTERLINES_JSON)
    corridor_data = read_json(PITLANE_V2_JSON)
    old_entry = read_json(PIT_ENTRY_ACCESS_JSON)
    old_exit = read_json(PIT_EXIT_ACCESS_JSON)

    main_track = points_xy(main_data.get("centerline", []), world_xz_to_map=True)
    corridor = points_xy(corridor_data.get("centerline", []), world_xz_to_map=True)
    fast_lane = points_xy(((centerlines.get("aiReferences") or {}).get("fastLane") or {}).get("centerline", []))
    pit_lane = points_xy(((centerlines.get("aiReferences") or {}).get("pitLane") or {}).get("centerline", []))

    entry_v2 = build_access_geometry(
        name="PitEntryAccessGeometryV2",
        kind="entry",
        component_name="PitEntryAccessArea",
        surface=surface,
        components=components,
        centerlines=centerlines,
    )
    exit_v2 = build_access_geometry(
        name="PitExitAccessGeometryV2",
        kind="exit",
        component_name="PitExitAccessArea",
        surface=surface,
        components=components,
        centerlines=centerlines,
    )
    audit = build_audit(old_entry=old_entry, old_exit=old_exit, entry_v2=entry_v2, exit_v2=exit_v2, centerlines=centerlines, components=components)
    validation = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "pitAreaGenerated": bool(surface.get("triangleCount")),
        "pitAreaIncludesCorridor": bool(component_summary(components, "PitLaneCorridor").get("detected")),
        "pitAreaIncludesEntryAccess": bool(entry_v2.get("geometryBuilt")),
        "pitAreaIncludesExitAccess": bool(exit_v2.get("geometryBuilt")),
        "entryAccessGeometryBuilt": bool(entry_v2.get("geometryBuilt")),
        "exitAccessGeometryBuilt": bool(exit_v2.get("geometryBuilt")),
        "entryAccessHasSurface": bool(entry_v2.get("hasSurface")),
        "exitAccessHasSurface": bool(exit_v2.get("hasSurface")),
        "entryAccessSource": entry_v2.get("source"),
        "exitAccessSource": exit_v2.get("source"),
        "entryAccessTriangleCount": entry_v2.get("triangleCount"),
        "exitAccessTriangleCount": exit_v2.get("triangleCount"),
        "entryAccessBoundaryLoopCount": entry_v2.get("boundaryLoopCount"),
        "exitAccessBoundaryLoopCount": exit_v2.get("boundaryLoopCount"),
        "entryAccessConfidence": entry_v2.get("confidence"),
        "exitAccessConfidence": exit_v2.get("confidence"),
        "pitLaneAiUsedAsReferenceOnly": True,
        "pitLaneAiUsedForGeometry": False,
        "constructedAccessSvg": str(PIT_AREA_CONSTRUCTED_ACCESS_SVG),
    }

    write_json(PIT_ENTRY_ACCESS_V2_JSON, entry_v2)
    write_json(PIT_EXIT_ACCESS_V2_JSON, exit_v2)
    write_json(PIT_ACCESS_AUDIT_JSON, audit)
    write_json(PIT_AREA_CONSTRUCTED_ACCESS_JSON, validation)

    entry_focus = points_xy(entry_v2.get("centerline", []))
    if entry_focus:
        entry_focus = [*entry_focus, *[point for triangle in entry_v2["surfaceFootprint"]["sampleTriangles"] for point in points_xy(triangle.get("vertices", []))]]
    exit_focus = points_xy(exit_v2.get("centerline", []))
    if exit_focus:
        exit_focus = [*exit_focus, *[point for triangle in exit_v2["surfaceFootprint"]["sampleTriangles"] for point in points_xy(triangle.get("vertices", []))]]

    write_constructed_svg(
        PIT_ENTRY_ACCESS_V2_SVG,
        title="PitEntryAccessGeometryV2 - constructed physical area",
        main_track=main_track,
        pit_corridor=corridor,
        entry_geometry=entry_v2,
        exit_geometry={},
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        focus_points=entry_focus,
    )
    write_constructed_svg(
        PIT_EXIT_ACCESS_V2_SVG,
        title="PitExitAccessGeometryV2 - constructed physical area",
        main_track=main_track,
        pit_corridor=corridor,
        entry_geometry={},
        exit_geometry=exit_v2,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        focus_points=exit_focus,
    )
    write_constructed_svg(
        PIT_AREA_CONSTRUCTED_ACCESS_SVG,
        title="PitArea constructed access validation",
        main_track=main_track,
        pit_corridor=corridor,
        entry_geometry=entry_v2,
        exit_geometry=exit_v2,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
    )

    print(f"Wrote {PIT_ACCESS_AUDIT_JSON}")
    print(f"Wrote {PIT_ENTRY_ACCESS_V2_JSON}")
    print(f"Wrote {PIT_ENTRY_ACCESS_V2_SVG}")
    print(f"Wrote {PIT_EXIT_ACCESS_V2_JSON}")
    print(f"Wrote {PIT_EXIT_ACCESS_V2_SVG}")
    print(f"Wrote {PIT_AREA_CONSTRUCTED_ACCESS_JSON}")
    print(f"Wrote {PIT_AREA_CONSTRUCTED_ACCESS_SVG}")
    print(
        "PitAccessGeometryV2 "
        f"entryTriangles={entry_v2['triangleCount']} exitTriangles={exit_v2['triangleCount']} "
        f"entryConfidence={entry_v2['confidence']} exitConfidence={exit_v2['confidence']}"
    )


if __name__ == "__main__":
    build()
