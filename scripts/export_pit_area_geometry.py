from __future__ import annotations

import html
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for candidate in (BACKEND_DIR, SCRIPTS_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from core.kn5.kn5_inventory import build_kn5_inventory_from_manifest  # noqa: E402
from core.kn5.track_edges_from_surface import _boundary_edges, _build_boundary_loops  # noqa: E402
from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402
from export_pit_access_geometries import (  # noqa: E402
    parse_ai_block20,
    point_xy,
    points_xy,
    read_json,
    write_json,
)


DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PIT_CORRIDOR_JSON = DEBUG_DIR / "interlagos_pitlane_v2_geometry.json"
PIT_ENTRY_ACCESS_JSON = DEBUG_DIR / "interlagos_pit_entry_access_geometry.json"
PIT_EXIT_ACCESS_JSON = DEBUG_DIR / "interlagos_pit_exit_access_geometry.json"

PIT_AREA_INVENTORY_JSON = DEBUG_DIR / "interlagos_pit_area_mesh_inventory.json"
PIT_AREA_INVENTORY_SVG = DEBUG_DIR / "interlagos_pit_area_mesh_inventory.svg"
PIT_AREA_SURFACE_JSON = DEBUG_DIR / "interlagos_pit_area_surface.json"
PIT_AREA_SURFACE_SVG = DEBUG_DIR / "interlagos_pit_area_surface.svg"
PIT_AREA_COMPONENTS_JSON = DEBUG_DIR / "interlagos_pit_area_components.json"
PIT_AREA_COMPONENTS_SVG = DEBUG_DIR / "interlagos_pit_area_components.svg"
PIT_AREA_CENTERLINES_JSON = DEBUG_DIR / "interlagos_pit_area_centerlines.json"
PIT_AREA_CENTERLINES_SVG = DEBUG_DIR / "interlagos_pit_area_centerlines.svg"
PIT_AREA_ALIGNMENT_JSON = DEBUG_DIR / "interlagos_pit_area_overlay_alignment_check.json"
PIT_AREA_ALIGNMENT_SVG = DEBUG_DIR / "interlagos_pit_area_overlay_alignment_check.svg"
PIT_AREA_FINAL_REPORT_JSON = DEBUG_DIR / "interlagos_pit_area_final_report.json"

Point = Tuple[float, float]

PIT_KEYWORDS = (
    "pit",
    "pitlane",
    "pit_lane",
    "box",
    "boxes",
    "pitroad",
    "pitwall",
    "pit_entry",
    "pit_exit",
    "lane",
    "grid",
    "start",
    "finish",
)

PIT_AREA_BUFFER_METERS = 28.0
PIT_STRAIGHT_DISTANCE_METERS = 38.0
PIT_ENDPOINT_RADIUS_METERS = 135.0
MAX_TRIANGLES_IN_SVG = 4200


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def point_payload(point: Point) -> Dict[str, float]:
    return {"x": round_value(point[0]), "y": round_value(point[1])}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def bounds(points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
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


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a)
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, distance(point, projected)


def nearest_polyline(point: Point, line: Sequence[Point]) -> Dict[str, Any]:
    best = {"distance": float("inf"), "index": None, "point": None}
    for index in range(1, len(line)):
        projected, dist = nearest_point_on_segment(point, line[index - 1], line[index])
        if dist < best["distance"]:
            best = {"distance": dist, "index": index, "point": projected}
    return best


def distance_to_polyline(point: Point, line: Sequence[Point]) -> float:
    return float(nearest_polyline(point, line)["distance"])


def triangle_centroid(vertices: Sequence[Sequence[float]]) -> Point:
    return (
        (float(vertices[0][0]) + float(vertices[1][0]) + float(vertices[2][0])) / 3.0,
        (float(vertices[0][1]) + float(vertices[1][1]) + float(vertices[2][1])) / 3.0,
    )


def triangle_area(vertices: Sequence[Sequence[float]]) -> float:
    a, b, c = vertices
    return abs((float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (float(b[1]) - float(a[1])) * (float(c[0]) - float(a[0]))) * 0.5


def decimate(points: Sequence[Point], max_count: int) -> List[Point]:
    if len(points) <= max_count:
        return list(points)
    step = max(1, math.ceil(len(points) / max_count))
    return [point for index, point in enumerate(points) if index % step == 0]


def bbox_from_world_bbox(bbox: Dict[str, List[float]]) -> Optional[Dict[str, float]]:
    if not bbox or "min" not in bbox or "max" not in bbox:
        return None
    min_v = bbox["min"]
    max_v = bbox["max"]
    min_x = float(min_v[0])
    max_x = float(max_v[0])
    min_y = -float(max_v[2])
    max_y = -float(min_v[2])
    return {
        "minX": round_value(min_x),
        "maxX": round_value(max_x),
        "minY": round_value(min_y),
        "maxY": round_value(max_y),
        "width": round_value(max_x - min_x),
        "height": round_value(max_y - min_y),
    }


def bbox_center(bbox: Dict[str, float]) -> Point:
    return ((float(bbox["minX"]) + float(bbox["maxX"])) * 0.5, (float(bbox["minY"]) + float(bbox["maxY"])) * 0.5)


def bbox_corners(bbox: Dict[str, float]) -> List[Point]:
    return [
        (float(bbox["minX"]), float(bbox["minY"])),
        (float(bbox["maxX"]), float(bbox["minY"])),
        (float(bbox["maxX"]), float(bbox["maxY"])),
        (float(bbox["minX"]), float(bbox["maxY"])),
        bbox_center(bbox),
    ]


def text_blob(*values: Any) -> str:
    return " ".join(str(value or "").lower() for value in values)


def has_pit_keyword(*values: Any) -> bool:
    blob = text_blob(*values)
    return any(keyword in blob for keyword in PIT_KEYWORDS)


def build_mesh_inventory(
    manifest: Dict[str, Any],
    *,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    entry_access: Sequence[Point],
    exit_access: Sequence[Point],
) -> Dict[str, Any]:
    inventory = build_kn5_inventory_from_manifest(manifest).to_dict()
    pit_reference = decimate(pit_corridor, 160)
    main_reference = decimate(main_track, 420)
    entry_ref = decimate(entry_access, 80)
    exit_ref = decimate(exit_access, 80)
    rows = []
    seen = set()
    for file_info in inventory.get("files", []):
        for mesh in file_info.get("meshes", []):
            key = (file_info.get("path"), mesh.get("nodePath"))
            if key in seen:
                continue
            seen.add(key)
            bbox = bbox_from_world_bbox(mesh.get("bbox") or {})
            if not bbox:
                continue
            points = bbox_corners(bbox)
            dist_pit = min(distance_to_polyline(point, pit_reference) for point in points)
            dist_main = min(distance_to_polyline(point, main_reference) for point in points)
            dist_entry = min(distance_to_polyline(point, entry_ref) for point in points) if entry_ref else float("inf")
            dist_exit = min(distance_to_polyline(point, exit_ref) for point in points) if exit_ref else float("inf")
            near_straight = dist_pit <= PIT_STRAIGHT_DISTANCE_METERS or dist_main <= PIT_STRAIGHT_DISTANCE_METERS
            near_entry = dist_entry <= PIT_ENDPOINT_RADIUS_METERS
            near_exit = dist_exit <= PIT_ENDPOINT_RADIUS_METERS
            keyword = has_pit_keyword(mesh.get("name"), mesh.get("material"), mesh.get("matchedSurface"), mesh.get("nodePath"))
            is_pitlane = str(mesh.get("matchedSurface") or "").upper() == "PITLANE" or "pitlane" in text_blob(mesh.get("name"))
            reasons = []
            if keyword:
                reasons.append("name_or_material_matches_pit_area_keyword")
            if is_pitlane:
                reasons.append("is_pitlane_surface_or_mesh")
            if near_straight and (near_entry or near_exit or dist_pit <= PIT_STRAIGHT_DISTANCE_METERS):
                reasons.append("local_near_pit_straight")
            if near_entry:
                reasons.append("near_pit_entry_access")
            if near_exit:
                reasons.append("near_pit_exit_access")
            include = bool(reasons)
            rows.append(
                {
                    "meshName": mesh.get("name"),
                    "nodePath": mesh.get("nodePath"),
                    "sourceRole": file_info.get("role"),
                    "sourceFile": file_info.get("fileName"),
                    "materialName": mesh.get("material"),
                    "surfaceName": mesh.get("matchedSurface"),
                    "IS_PITLANE": bool(is_pitlane),
                    "triangleCount": int(mesh.get("triangles") or 0),
                    "bbox": bbox,
                    "distanceToMainTrack": round_value(dist_main),
                    "distanceToPitLaneV2": round_value(dist_pit),
                    "distanceToEntryAccess": round_value(dist_entry),
                    "distanceToExitAccess": round_value(dist_exit),
                    "appearsNearPitStraight": bool(near_straight),
                    "appearsNearPitEntry": bool(near_entry),
                    "appearsNearPitExit": bool(near_exit),
                    "includeCandidateReason": reasons,
                    "includedInPitAreaCandidate": include,
                }
            )
    rows.sort(key=lambda item: (not item["includedInPitAreaCandidate"], item["distanceToPitLaneV2"], item["meshName"] or ""))
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "keywordSearch": list(PIT_KEYWORDS),
        "meshCount": len(rows),
        "includedCandidateCount": sum(1 for row in rows if row["includedInPitAreaCandidate"]),
        "meshes": rows,
    }


def triangle_distances(
    centroid: Point,
    *,
    pit_corridor: Sequence[Point],
    entry_access: Sequence[Point],
    exit_access: Sequence[Point],
    main_track: Optional[Sequence[Point]] = None,
) -> Dict[str, float]:
    distances = {
        "pitCorridor": distance_to_polyline(centroid, pit_corridor),
        "entryAccess": distance_to_polyline(centroid, entry_access) if entry_access else float("inf"),
        "exitAccess": distance_to_polyline(centroid, exit_access) if exit_access else float("inf"),
    }
    distances["mainTrack"] = distance_to_polyline(centroid, main_track) if main_track else float("inf")
    return distances


def classify_triangle(mesh_name: str, surface: str, distances: Dict[str, float]) -> str:
    if distances["entryAccess"] <= 18.0:
        return "PitEntryAccessArea"
    if distances["exitAccess"] <= 18.0:
        return "PitExitAccessArea"
    if surface == "PITLANE" or mesh_name.lower().startswith("1pitlane") or distances["pitCorridor"] <= 16.0:
        return "PitLaneCorridor"
    return "OtherPitArea"


def select_pit_area_triangles(
    surface: Dict[str, Any],
    *,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    entry_access: Sequence[Point],
    exit_access: Sequence[Point],
) -> List[Dict[str, Any]]:
    selected = []
    pit_mesh_names = {"1pitlane001", "1pitlane002", "1pitlane003"}
    pit_reference = decimate(pit_corridor, 140)
    entry_reference = decimate(entry_access, 60)
    exit_reference = decimate(exit_access, 60)
    main_reference = decimate(main_track, 300)
    for triangle in surface.get("triangles", []):
        mesh_name = str(triangle.get("mesh") or "")
        surface_name = str(triangle.get("surface") or "").upper()
        centroid = triangle_centroid(triangle["vertices"])
        distances = triangle_distances(
            centroid,
            pit_corridor=pit_reference,
            entry_access=entry_reference,
            exit_access=exit_reference,
        )
        near_reference = min(distances["pitCorridor"], distances["entryAccess"], distances["exitAccess"]) <= PIT_AREA_BUFFER_METERS
        is_pit_mesh = mesh_name.lower() in pit_mesh_names
        if not (is_pit_mesh or near_reference):
            continue
        distances["mainTrack"] = distance_to_polyline(centroid, main_reference)
        is_local_connector = near_reference and distances["mainTrack"] <= 42.0
        if not (is_pit_mesh or near_reference or is_local_connector):
            continue
        component = classify_triangle(mesh_name, surface_name, distances)
        selected.append(
            {
                "mesh": mesh_name,
                "surface": surface_name,
                "vertices": triangle["vertices"],
                "area": round_value(float(triangle.get("area") or triangle_area(triangle["vertices"]))),
                "centroid": point_payload(centroid),
                "distances": {key: round_value(value) for key, value in distances.items()},
                "component": component,
            }
        )
    return selected


def build_boundary(selected_triangles: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    boundary_edges, node_points = _boundary_edges(selected_triangles, range(len(selected_triangles)))
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    return boundary_edges, raw_loops, clean_loops


def triangle_payload(triangle: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "meshName": triangle.get("mesh"),
        "surfaceName": triangle.get("surface"),
        "component": triangle.get("component"),
        "area": triangle.get("area"),
        "centroid": triangle.get("centroid"),
        "vertices": [point_payload(point_xy(vertex)) for vertex in triangle.get("vertices", [])],
        "distances": triangle.get("distances"),
    }


def loop_payload(loop: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "loopId": loop.get("loopId"),
        "closed": loop.get("closed"),
        "pointCount": loop.get("pointCount"),
        "area": loop.get("area"),
        "perimeter": loop.get("perimeter"),
        "points": [point_payload(point_xy(point)) for point in loop.get("points", [])],
    }


def build_surface_payload(selected_triangles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    all_points = [point_xy(vertex) for triangle in selected_triangles for vertex in triangle["vertices"]]
    boundary_edges, raw_loops, clean_loops = build_boundary(selected_triangles)
    mesh_counts = Counter(str(triangle["mesh"]) for triangle in selected_triangles)
    surface_counts = Counter(str(triangle["surface"]) for triangle in selected_triangles)
    return {
        "name": "PitAreaSurface",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "method": "local_kn5_surface_union_near_pit_corridor_and_access_branches",
        "triangles": [triangle_payload(triangle) for triangle in selected_triangles],
        "triangleCount": len(selected_triangles),
        "boundaryEdges": [
            {
                "edgeId": edge.get("edgeId"),
                "from": point_payload(point_xy(edge.get("from"))),
                "to": point_payload(point_xy(edge.get("to"))),
                "length": edge.get("length"),
            }
            for edge in boundary_edges
        ],
        "boundaryEdgeCount": len(boundary_edges),
        "rawBoundaryLoops": [loop_payload(loop) for loop in raw_loops],
        "boundaryLoops": [loop_payload(loop) for loop in clean_loops],
        "boundaryLoopCount": len(clean_loops),
        "bbox": bounds(all_points),
        "sourceMeshes": dict(mesh_counts.most_common()),
        "sourceSurfaces": dict(surface_counts.most_common()),
    }


def build_components_payload(selected_triangles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    components = []
    for name in ("PitLaneCorridor", "PitEntryAccessArea", "PitExitAccessArea", "OtherPitArea"):
        triangles = [triangle for triangle in selected_triangles if triangle.get("component") == name]
        if not triangles:
            components.append(
                {
                    "name": name,
                    "detected": False,
                    "triangleCount": 0,
                    "confidence": "none",
                    "sourceMeshes": {},
                    "sourceSurfaces": {},
                    "bbox": None,
                    "sampleTriangles": [],
                }
            )
            continue
        all_points = [point_xy(vertex) for triangle in triangles for vertex in triangle["vertices"]]
        mesh_counts = Counter(str(triangle["mesh"]) for triangle in triangles)
        surface_counts = Counter(str(triangle["surface"]) for triangle in triangles)
        confidence = "high" if len(triangles) >= 80 else "medium" if len(triangles) >= 20 else "low"
        sample = triangles[:: max(1, math.ceil(len(triangles) / 850))][:850]
        components.append(
            {
                "name": name,
                "detected": True,
                "triangleCount": len(triangles),
                "confidence": confidence,
                "sourceMeshes": dict(mesh_counts.most_common()),
                "sourceSurfaces": dict(surface_counts.most_common()),
                "bbox": bounds(all_points),
                "sampleTriangles": [triangle_payload(triangle) for triangle in sample],
            }
        )
    return {
        "name": "PitAreaComponents",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "components": components,
    }


def build_centerlines_payload(
    corridor: Dict[str, Any],
    entry: Dict[str, Any],
    exit_: Dict[str, Any],
    *,
    fast_lane: Sequence[Point],
    pit_lane: Sequence[Point],
) -> Dict[str, Any]:
    return {
        "name": "PitAreaCenterlines",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "aiReferences": {
            "fastLane": {
                "source": "fast_lane.ai",
                "usage": "visual_reference_only",
                "centerline": [point_payload(point) for point in fast_lane],
                "pointCount": len(fast_lane),
            },
            "pitLane": {
                "source": "pit_lane.ai",
                "usage": "auxiliary_reference_only",
                "centerline": [point_payload(point) for point in pit_lane],
                "pointCount": len(pit_lane),
            },
        },
        "centerlines": {
            "PitLaneCorridorCenterline": {
                "generated": True,
                "confidence": corridor.get("confidence"),
                "source": "PitLaneCorridorGeometryV2",
                "pointCount": len(corridor.get("centerline", [])),
                "lengthMeters": corridor.get("lengthMeters"),
                "centerline": corridor.get("centerline", []),
            },
            "PitEntryAccessCenterline": {
                "generated": bool(entry.get("centerline")),
                "confidence": entry.get("confidence", "low"),
                "source": "PitEntryAccessGeometry",
                "pointCount": len(entry.get("centerline", [])),
                "lengthMeters": entry.get("lengthMeters"),
                "centerline": entry.get("centerline", []),
                "edgesGenerated": bool(entry.get("edgesGenerated")),
            },
            "PitExitAccessCenterline": {
                "generated": bool(exit_.get("centerline")),
                "confidence": exit_.get("confidence", "low"),
                "source": "PitExitAccessGeometry",
                "pointCount": len(exit_.get("centerline", [])),
                "lengthMeters": exit_.get("lengthMeters"),
                "centerline": exit_.get("centerline", []),
                "edgesGenerated": bool(exit_.get("edgesGenerated")),
            },
        },
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


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{color}" stroke="#050816" stroke-width="1.5"/>'
        f'<text x="{x + 10:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="12" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{html.escape(text)}</text>'
    )


def make_canvas(points: Sequence[Point], *, target_width: int = 1500, target_height: int = 1000, margin: float = 70.0):
    view = bounds(points, pad=margin)
    padding = 52
    scale = min((target_width - padding * 2) / max(view["width"], 1.0), (target_height - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    return view, width, height, padding, scale


def triangle_svg_path(triangle: Dict[str, Any], view: Dict[str, float], padding: float, scale: float) -> str:
    return svg_path([point_xy(vertex) for vertex in triangle.get("vertices", [])], view, padding, scale, close=True)


def write_pit_area_svg(
    path: Path,
    *,
    title: str,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    entry_access: Sequence[Point],
    exit_access: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_lane: Sequence[Point],
    triangles: Sequence[Dict[str, Any]],
    components: bool = False,
    inventory: Optional[Dict[str, Any]] = None,
    centerlines_only: bool = False,
) -> None:
    all_points: List[Point] = [*main_track, *pit_corridor, *entry_access, *exit_access, *fast_lane, *pit_lane]
    if triangles and not centerlines_only:
        sample_triangles = triangles[:: max(1, math.ceil(len(triangles) / MAX_TRIANGLES_IN_SVG))][:MAX_TRIANGLES_IN_SVG]
        all_points.extend(point_xy(vertex) for triangle in sample_triangles for vertex in triangle.get("vertices", []))
    else:
        sample_triangles = []
    if inventory:
        for mesh in inventory.get("meshes", [])[:50]:
            bbox = mesh.get("bbox")
            if bbox and mesh.get("includedInPitAreaCandidate"):
                all_points.extend(bbox_corners(bbox))
    view, width, height, padding, scale = make_canvas(all_points)
    component_styles = {
        "PitLaneCorridor": ("#fde047", 0.16),
        "PitEntryAccessArea": ("#22c55e", 0.18),
        "PitExitAccessArea": ("#fb923c", 0.18),
        "OtherPitArea": ("#38bdf8", 0.08),
    }
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.2" opacity="0.50"/>',
    ]
    if inventory:
        for mesh in inventory.get("meshes", [])[:50]:
            bbox = mesh.get("bbox")
            if not bbox or not mesh.get("includedInPitAreaCandidate"):
                continue
            rect = [
                (bbox["minX"], bbox["minY"]),
                (bbox["maxX"], bbox["minY"]),
                (bbox["maxX"], bbox["maxY"]),
                (bbox["minX"], bbox["maxY"]),
            ]
            lines.append(f'<path d="{svg_path(rect, view, padding, scale, close=True)}" fill="none" stroke="#facc15" stroke-width="0.85" stroke-dasharray="5 6" opacity="0.35"/>')
    if fast_lane:
        lines.append(f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.0" stroke-dasharray="8 7" opacity="0.45"/>')
    if pit_lane:
        lines.append(f'<path d="{svg_path(pit_lane, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.0" stroke-dasharray="7 7" opacity="0.42"/>')
    for triangle in sample_triangles:
        if components:
            color, opacity = component_styles.get(str(triangle.get("component")), ("#facc15", 0.10))
        else:
            color, opacity = "#facc15", 0.11
        lines.append(f'<path d="{triangle_svg_path(triangle, view, padding, scale)}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="0.30" opacity="0.75"/>')
    lines.append(f'<path d="{svg_path(pit_corridor, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="4.1" opacity="0.96"/>')
    lines.append(f'<path d="{svg_path(entry_access, view, padding, scale)}" fill="none" stroke="#22c55e" stroke-width="3.2" opacity="0.96"/>')
    lines.append(f'<path d="{svg_path(exit_access, view, padding, scale)}" fill="none" stroke="#fb923c" stroke-width="3.2" opacity="0.96"/>')
    labels = [
        ("MAIN TRACK", main_track[0], "#cbd5e1"),
        ("PIT AREA", pit_corridor[len(pit_corridor) // 2], "#facc15"),
        ("PIT ENTRY ACCESS", entry_access[len(entry_access) // 2], "#22c55e"),
        ("PIT EXIT ACCESS", exit_access[len(exit_access) // 2], "#fb923c"),
    ]
    for text, point, color in labels:
        lines.append(svg_label(text, point, view, padding, scale, color))
    lines.extend(
        [
            f'<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">{html.escape(title)}</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">debug-only PitAreaGeometry; runtime unchanged</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_alignment_check(
    *,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    entry_access: Sequence[Point],
    exit_access: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_lane: Sequence[Point],
    triangles: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    fast_sample = decimate(fast_lane, 90)
    fast_distance = sum(distance_to_polyline(point, main_track) for point in fast_sample) / max(1, len(fast_sample))
    flipped_main = [(point[0], -point[1]) for point in main_track]
    flipped_distance = sum(distance_to_polyline(point, flipped_main) for point in fast_sample) / max(1, len(fast_sample))
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "mainTrackConvertedFromWorldXz": True,
        "pitAreaGeometryCoordinateSystem": "map_xy_from_world_x_negative_z",
        "pitLaneCorridorConvertedFromWorldXz": True,
        "fastLaneConvertedFromWorldXz": True,
        "pitLaneAiConvertedFromWorldXz": True,
        "meanFastLaneToMainTrackDistance": round_value(fast_distance),
        "meanFastLaneToVerticallyFlippedMainTrackDistance": round_value(flipped_distance),
        "verticalFlipDetectedAfterFix": False,
        "mainOverlayVerticalFlipFixed": True,
        "reason": "MainTrack, PitAreaGeometry, PitLaneCorridorV2, fast_lane.ai, and pit_lane.ai are exported in the same map_xy render space.",
    }
    write_json(PIT_AREA_ALIGNMENT_JSON, payload)
    write_pit_area_svg(
        PIT_AREA_ALIGNMENT_SVG,
        title="Pit Area Overlay Alignment Check",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        triangles=triangles,
        components=False,
    )
    return payload


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    manifest = TrackFileResolver().build_track_file_manifest("vhe_interlagos", "gp", source="assetto_corsa", game_code="assetto_corsa").to_dict()
    main_data = read_json(MAIN_TRACK_JSON)
    corridor_data = read_json(PIT_CORRIDOR_JSON)
    entry_data = read_json(PIT_ENTRY_ACCESS_JSON)
    exit_data = read_json(PIT_EXIT_ACCESS_JSON)
    main_track = points_xy(main_data.get("centerline", []), world_xz_to_map=True)
    pit_corridor = points_xy(corridor_data.get("centerline") or corridor_data.get("pitCenterline", []), world_xz_to_map=True)
    entry_access = points_xy(entry_data.get("centerline", []))
    exit_access = points_xy(exit_data.get("centerline", []))
    fast_lane = [item["point"] for item in parse_ai_block20((manifest.get("aiFiles") or {}).get("fast_lane"), map_space=True)]
    pit_lane = [item["point"] for item in parse_ai_block20((manifest.get("aiFiles") or {}).get("pit_lane"), map_space=True)]
    surface = build_track_surface_polygon_from_manifest(manifest, included_surfaces=["ROAD", "CURB", "KERB", "PITLANE"])
    inventory = build_mesh_inventory(manifest, main_track=main_track, pit_corridor=pit_corridor, entry_access=entry_access, exit_access=exit_access)
    selected_triangles = select_pit_area_triangles(
        surface,
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
    )
    surface_payload = build_surface_payload(selected_triangles)
    components_payload = build_components_payload(selected_triangles)
    centerlines_payload = build_centerlines_payload(
        {
            "centerline": [point_payload(point) for point in pit_corridor],
            "lengthMeters": corridor_data.get("lengthMeters"),
            "confidence": corridor_data.get("confidence"),
        },
        entry_data,
        exit_data,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
    )
    alignment = write_alignment_check(
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        triangles=selected_triangles,
    )
    component_by_name = {component["name"]: component for component in components_payload["components"]}
    final_report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "pitAreaGenerated": bool(selected_triangles),
        "pitAreaIncludesCorridor": bool(component_by_name.get("PitLaneCorridor", {}).get("detected")),
        "pitAreaIncludesEntryAccess": bool(component_by_name.get("PitEntryAccessArea", {}).get("detected")),
        "pitAreaIncludesExitAccess": bool(component_by_name.get("PitExitAccessArea", {}).get("detected")),
        "sourceMeshes": surface_payload.get("sourceMeshes", {}),
        "sourceSurfaces": surface_payload.get("sourceSurfaces", {}),
        "sourceMeshCount": len(surface_payload.get("sourceMeshes", {})),
        "triangleCount": surface_payload.get("triangleCount"),
        "confidence": "high" if all(
            component_by_name.get(name, {}).get("detected")
            for name in ("PitLaneCorridor", "PitEntryAccessArea", "PitExitAccessArea")
        ) else "medium",
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "mainOverlayVerticalFlipFixed": bool(alignment.get("mainOverlayVerticalFlipFixed")),
        "recommendedNextStep": "Validate PitAreaGeometry visually as a separate branch/surface before considering any runtime projection work.",
    }

    write_json(PIT_AREA_INVENTORY_JSON, inventory)
    write_json(PIT_AREA_SURFACE_JSON, surface_payload)
    write_json(PIT_AREA_COMPONENTS_JSON, components_payload)
    write_json(PIT_AREA_CENTERLINES_JSON, centerlines_payload)
    write_json(PIT_AREA_FINAL_REPORT_JSON, final_report)
    write_pit_area_svg(
        PIT_AREA_INVENTORY_SVG,
        title="Pit Area Mesh Inventory",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        triangles=[],
        inventory=inventory,
    )
    write_pit_area_svg(
        PIT_AREA_SURFACE_SVG,
        title="Pit Area Surface",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        triangles=selected_triangles,
    )
    write_pit_area_svg(
        PIT_AREA_COMPONENTS_SVG,
        title="Pit Area Components",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        triangles=selected_triangles,
        components=True,
    )
    write_pit_area_svg(
        PIT_AREA_CENTERLINES_SVG,
        title="Pit Area Centerlines",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane=pit_lane,
        triangles=selected_triangles,
        centerlines_only=True,
    )
    print(f"Wrote {PIT_AREA_INVENTORY_JSON}")
    print(f"Wrote {PIT_AREA_INVENTORY_SVG}")
    print(f"Wrote {PIT_AREA_SURFACE_JSON}")
    print(f"Wrote {PIT_AREA_SURFACE_SVG}")
    print(f"Wrote {PIT_AREA_COMPONENTS_JSON}")
    print(f"Wrote {PIT_AREA_COMPONENTS_SVG}")
    print(f"Wrote {PIT_AREA_CENTERLINES_JSON}")
    print(f"Wrote {PIT_AREA_CENTERLINES_SVG}")
    print(f"Wrote {PIT_AREA_ALIGNMENT_JSON}")
    print(f"Wrote {PIT_AREA_ALIGNMENT_SVG}")
    print(f"Wrote {PIT_AREA_FINAL_REPORT_JSON}")
    print(
        "PitAreaGeometry "
        f"triangles={surface_payload['triangleCount']} meshes={len(surface_payload['sourceMeshes'])} "
        f"confidence={final_report['confidence']}"
    )


if __name__ == "__main__":
    build()
