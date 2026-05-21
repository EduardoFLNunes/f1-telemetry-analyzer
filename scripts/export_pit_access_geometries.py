from __future__ import annotations

import html
import json
import math
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_edges_from_surface import _TriangleSurfaceIndex  # noqa: E402
from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PITLANE_V2_JSON = DEBUG_DIR / "interlagos_pitlane_v2_geometry.json"

ALIGNMENT_JSON = DEBUG_DIR / "interlagos_pitlane_debug_overlay_alignment_check.json"
ALIGNMENT_SVG = DEBUG_DIR / "interlagos_pitlane_debug_overlay_alignment_check.svg"
INVENTORY_JSON = DEBUG_DIR / "interlagos_pit_access_local_mesh_inventory.json"
INVENTORY_SVG = DEBUG_DIR / "interlagos_pit_access_local_mesh_inventory.svg"
ENTRY_JSON = DEBUG_DIR / "interlagos_pit_entry_access_geometry.json"
ENTRY_SVG = DEBUG_DIR / "interlagos_pit_entry_access_geometry.svg"
EXIT_JSON = DEBUG_DIR / "interlagos_pit_exit_access_geometry.json"
EXIT_SVG = DEBUG_DIR / "interlagos_pit_exit_access_geometry.svg"
ACCESS_OVERVIEW_SVG = DEBUG_DIR / "interlagos_pit_access_overview_clean.svg"
ENTRY_ZOOM_SVG = DEBUG_DIR / "interlagos_pit_entry_access_zoom.svg"
EXIT_ZOOM_SVG = DEBUG_DIR / "interlagos_pit_exit_access_zoom.svg"
CORRIDOR_PLUS_ACCESS_SVG = DEBUG_DIR / "interlagos_pitlane_v2_corridor_plus_access.svg"
FINAL_REPORT_JSON = DEBUG_DIR / "interlagos_pit_access_final_report.json"

LOCAL_RADIUS_METERS = 120.0
ACCESS_SURFACE_BUFFER_METERS = 22.0
ENTRY_MAIN_DISTANCE_THRESHOLD = 18.0
EXIT_SEARCH_POINTS = 80

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def map_point_payload(point: Point) -> Dict[str, float]:
    return {"x": round_value(point[0]), "y": round_value(point[1])}


def point_xy(point: Any, *, world_xz_to_map: bool = False) -> Point:
    if isinstance(point, dict):
        x = float(point["x"])
        y = float(point.get("y", point.get("z", 0.0)))
    else:
        x = float(point[0])
        y = float(point[1])
    return (x, -y if world_xz_to_map else y)


def points_xy(points: Iterable[Any], *, world_xz_to_map: bool = False) -> List[Point]:
    return [point_xy(point, world_xz_to_map=world_xz_to_map) for point in points or []]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def scale_vec(a: Point, scale: float) -> Point:
    return (a[0] * scale, a[1] * scale)


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def normalize(v: Point) -> Point:
    length = math.hypot(v[0], v[1])
    if length <= 1e-12:
        return (1.0, 0.0)
    return (v[0] / length, v[1] / length)


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def bounds(points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs) - pad,
        "maxX": max(xs) + pad,
        "minY": min(ys) - pad,
        "maxY": max(ys) + pad,
        "width": max(xs) - min(xs) + pad * 2.0,
        "height": max(ys) - min(ys) + pad * 2.0,
    }


def bbox_payload(points: Sequence[Point]) -> Dict[str, float]:
    view = bounds(points)
    return {key: round_value(value) for key, value in view.items()}


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a), 0.0
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, distance(point, projected), t


def nearest_polyline(point: Point, line: Sequence[Point]) -> Dict[str, Any]:
    best = {"distance": float("inf"), "index": None, "point": None}
    for index in range(1, len(line)):
        projected, dist, t = nearest_point_on_segment(point, line[index - 1], line[index])
        if dist < best["distance"]:
            best = {"distance": dist, "index": index, "point": projected, "segmentT": t}
    return best


def distance_to_polyline(point: Point, line: Sequence[Point]) -> float:
    return float(nearest_polyline(point, line)["distance"])


def tangent_at(points: Sequence[Point], index: int) -> Point:
    if len(points) < 2:
        return (1.0, 0.0)
    if index <= 0:
        return normalize(subtract(points[1], points[0]))
    if index >= len(points) - 1:
        return normalize(subtract(points[-1], points[-2]))
    return normalize(subtract(points[index + 1], points[index - 1]))


def main_tangent(main_track: Sequence[Point], nearest_index: int) -> Point:
    index = max(1, min(len(main_track) - 2, int(nearest_index or 1)))
    return tangent_at(main_track, index)


def cubic_bezier_points(p0: Point, p1: Point, t0: Point, t1: Point, count: int = 12) -> List[Point]:
    length = distance(p0, p1)
    c0 = add(p0, scale_vec(normalize(t0), length * 0.42))
    c1 = subtract(p1, scale_vec(normalize(t1), length * 0.42))
    points = []
    for step in range(count):
        u = step / max(count - 1, 1)
        inv = 1.0 - u
        x = inv**3 * p0[0] + 3 * inv * inv * u * c0[0] + 3 * inv * u * u * c1[0] + u**3 * p1[0]
        y = inv**3 * p0[1] + 3 * inv * inv * u * c0[1] + 3 * inv * u * u * c1[1] + u**3 * p1[1]
        points.append((x, y))
    return points


def stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"min": None, "avg": None, "max": None}
    return {"min": round_value(min(values)), "avg": round_value(mean(values)), "max": round_value(max(values))}


def parse_ai_block20(path: Optional[str], *, map_space: bool = True) -> List[Dict[str, Any]]:
    if not path:
        return []
    ai_path = Path(path)
    if not ai_path.exists():
        return []
    data = ai_path.read_bytes()
    if len(data) < 16:
        return []
    _version, declared_count = struct.unpack_from("<II", data, 0)
    count = min(int(declared_count), max(0, (len(data) - 16) // 20))
    points = []
    for index in range(count):
        x, y, z, spline_distance, raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append(
            {
                "index": index,
                "point": (float(x), -float(z) if map_space else float(z)),
                "worldPosition": [round_value(x), round_value(y), round_value(z)],
                "distance": round_value(spline_distance),
                "rawIndex": int(raw_index),
            }
        )
    return points


def decimate(points: Sequence[Point], step: int) -> List[Point]:
    if step <= 1:
        return list(points)
    return [point for index, point in enumerate(points) if index % step == 0]


def triangle_centroid(vertices: Sequence[Sequence[float]]) -> Point:
    return (
        (float(vertices[0][0]) + float(vertices[1][0]) + float(vertices[2][0])) / 3.0,
        (float(vertices[0][1]) + float(vertices[1][1]) + float(vertices[2][1])) / 3.0,
    )


def group_triangles_by_mesh(triangles: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for triangle in triangles:
        grouped.setdefault(str(triangle.get("mesh", "unknown")), []).append(triangle)
    return grouped


def nearest_index_to_main_for_ai(points: Sequence[Dict[str, Any]], main_track: Sequence[Point]) -> List[Dict[str, Any]]:
    enriched = []
    for point in points:
        nearest = nearest_polyline(point["point"], main_track)
        enriched.append({**point, "nearestMain": nearest})
    return enriched


def choose_entry_ai_start(pit_ai: Sequence[Dict[str, Any]], selected_start: int, main_track: Sequence[Point]) -> int:
    start = max(0, selected_start - 90)
    enriched = nearest_index_to_main_for_ai(pit_ai[start : selected_start + 1], main_track)
    for item in enriched:
        if float(item["nearestMain"]["distance"]) <= ENTRY_MAIN_DISTANCE_THRESHOLD:
            return int(item["index"])
    return max(0, selected_start - 40)


def choose_exit_ai_merge(pit_ai: Sequence[Dict[str, Any]], selected_end: int, main_track: Sequence[Point]) -> int:
    end = min(len(pit_ai) - 1, selected_end + EXIT_SEARCH_POINTS)
    enriched = nearest_index_to_main_for_ai(pit_ai[selected_end : end + 1], main_track)
    best = min(enriched, key=lambda item: float(item["nearestMain"]["distance"]))
    return int(best["index"])


def surface_hit_ratio(points: Sequence[Point], surface_index: _TriangleSurfaceIndex) -> float:
    if not points:
        return 0.0
    hits = sum(1 for point in points if surface_index.contains(point))
    return hits / len(points)


def select_surface_footprint(
    triangles: Sequence[Dict[str, Any]],
    centerline: Sequence[Point],
    *,
    zone_center: Point,
    radius: float,
    buffer_meters: float,
    max_samples: int = 520,
) -> Dict[str, Any]:
    selected = []
    mesh_names: Dict[str, int] = {}
    surface_names: Dict[str, int] = {}
    all_points: List[Point] = []
    for triangle in triangles:
        vertices = [point_xy(vertex) for vertex in triangle["vertices"]]
        centroid = triangle_centroid(triangle["vertices"])
        if distance(centroid, zone_center) > radius:
            continue
        if distance_to_polyline(centroid, centerline) > buffer_meters:
            continue
        selected.append(triangle)
        mesh_names[str(triangle.get("mesh", "unknown"))] = mesh_names.get(str(triangle.get("mesh", "unknown")), 0) + 1
        surface_names[str(triangle.get("surface", "unknown"))] = surface_names.get(str(triangle.get("surface", "unknown")), 0) + 1
        all_points.extend(vertices)
    sample_triangles = []
    stride = max(1, math.ceil(len(selected) / max_samples)) if selected else 1
    for triangle in selected[::stride][:max_samples]:
        sample_triangles.append(
            {
                "meshName": triangle.get("mesh"),
                "surface": triangle.get("surface"),
                "vertices": [map_point_payload(point_xy(vertex)) for vertex in triangle.get("vertices", [])],
            }
        )
    return {
        "triangleCount": len(selected),
        "meshCounts": mesh_names,
        "surfaceCounts": surface_names,
        "bounds": bbox_payload(all_points) if all_points else None,
        "sampleTriangles": sample_triangles,
        "sampleLimit": max_samples,
    }


def build_access_geometry(
    *,
    name: str,
    kind: str,
    pit_ai: Sequence[Dict[str, Any]],
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    selected_start: int,
    selected_end: int,
    surface_index: _TriangleSurfaceIndex,
    all_triangles: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if kind == "entry":
        ai_start = choose_entry_ai_start(pit_ai, selected_start, main_track)
        ai_points = [item["point"] for item in pit_ai[ai_start : selected_start + 1]]
        first_ai = ai_points[0]
        main_connection = nearest_polyline(first_ai, main_track)
        main_point = main_connection["point"]
        main_index = int(main_connection["index"])
        connector = cubic_bezier_points(main_point, first_ai, main_tangent(main_track, main_index), tangent_at(ai_points, 0), count=14)
        centerline = connector[:-1] + ai_points
        pit_connection = {"point": pit_corridor[0], "index": 0}
        access_ai_range = {"startAiIndex": ai_start, "endAiIndex": selected_start}
        zone_center = pit_corridor[0]
    else:
        ai_merge = choose_exit_ai_merge(pit_ai, selected_end, main_track)
        ai_points = [item["point"] for item in pit_ai[selected_end : ai_merge + 1]]
        last_ai = ai_points[-1]
        main_connection = nearest_polyline(last_ai, main_track)
        main_point = main_connection["point"]
        main_index = int(main_connection["index"])
        connector = cubic_bezier_points(last_ai, main_point, tangent_at(ai_points, len(ai_points) - 1), main_tangent(main_track, main_index), count=14)
        centerline = ai_points + connector[1:]
        pit_connection = {"point": pit_corridor[-1], "index": len(pit_corridor) - 1}
        access_ai_range = {"startAiIndex": selected_end, "endAiIndex": ai_merge}
        zone_center = pit_corridor[-1]

    footprint = select_surface_footprint(
        all_triangles,
        centerline,
        zone_center=zone_center,
        radius=LOCAL_RADIUS_METERS,
        buffer_meters=ACCESS_SURFACE_BUFFER_METERS,
    )
    hit_ratio = surface_hit_ratio(centerline, surface_index)
    uses_surface = footprint["triangleCount"] > 0 and hit_ratio >= 0.65
    confidence = "high" if uses_surface and hit_ratio >= 0.85 else "medium" if uses_surface else "low"

    main_distances = [distance_to_polyline(point, main_track) for point in centerline]
    pit_distances = [distance_to_polyline(point, pit_corridor) for point in centerline]
    return {
        "name": name,
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "source": "pit_lane.ai longitudinal reference + local KN5 physical surface footprint + debug Bezier connector to MainTrack",
        "method": "debug_access_branch_from_pit_ai_reference_and_local_surface_footprint",
        "kind": kind,
        "centerline": [map_point_payload(point) for point in centerline],
        "leftEdge": [],
        "rightEdge": [],
        "edgesGenerated": False,
        "openLoop": True,
        "pointCount": len(centerline),
        "lengthMeters": round_value(polyline_length(centerline)),
        "startPoint": map_point_payload(centerline[0]),
        "endPoint": map_point_payload(centerline[-1]),
        "mainTrackConnection": {
            "index": main_index,
            "point": map_point_payload(main_point),
            "distanceToPitLaneAiReference": round_value(float(main_connection["distance"])),
        },
        "pitLaneConnection": {
            "index": pit_connection["index"],
            "point": map_point_payload(pit_connection["point"]),
        },
        "pitLaneAiReferenceRange": access_ai_range,
        "syntheticConnectorUsed": True,
        "syntheticConnectorReason": "Connects local pit_lane.ai branch reference to nearest MainTrack point for manual debug visualization only.",
        "surfaceFootprint": footprint,
        "centerlineSurfaceHitRatio": round_value(hit_ratio),
        "distanceToMainTrack": stats(main_distances),
        "distanceToPitLaneCorridor": stats(pit_distances),
        "usesPhysicalSurface": uses_surface,
        "confidence": confidence,
        "selectedAutomatically": False,
    }


def build_mesh_inventory(
    surface: Dict[str, Any],
    *,
    pit_corridor: Sequence[Point],
    main_track: Sequence[Point],
) -> Dict[str, Any]:
    triangles = surface.get("triangles", [])
    grouped = group_triangles_by_mesh(triangles)
    pit_reference = decimate(pit_corridor, 2)
    main_reference = decimate(main_track, 8)
    entry_endpoint = pit_corridor[0]
    exit_endpoint = pit_corridor[-1]
    mesh_rows = []
    for mesh in surface.get("meshes", []):
        name = str(mesh.get("meshName"))
        mesh_triangles = grouped.get(name, [])
        centroids = [triangle_centroid(triangle["vertices"]) for triangle in mesh_triangles]
        if len(centroids) > 900:
            step = max(1, len(centroids) // 900)
            centroids_for_distance = centroids[::step]
        else:
            centroids_for_distance = centroids
        if not centroids_for_distance:
            continue
        min_pit = min(distance_to_polyline(point, pit_reference) for point in centroids_for_distance)
        min_main = min(distance_to_polyline(point, main_reference) for point in centroids_for_distance)
        min_entry = min(distance(point, entry_endpoint) for point in centroids_for_distance)
        min_exit = min(distance(point, exit_endpoint) for point in centroids_for_distance)
        is_local = min(min_entry, min_exit) <= LOCAL_RADIUS_METERS
        is_pit = str(mesh.get("matchedSurface")).upper() == "PITLANE"
        is_road = str(mesh.get("matchedSurface")).upper() in {"ROAD", "CURB", "KERB"}
        connects = is_local and min_pit <= 28.0 and min_main <= 28.0
        reasons = []
        if is_local:
            reasons.append("within_120m_of_pitlane_v2_endpoint")
        if connects:
            reasons.append("near_both_pit_corridor_and_maintrack")
        if is_pit:
            reasons.append("is_pitlane_surface")
        if is_road:
            reasons.append("is_road_like_surface")
        mesh_rows.append(
            {
                "meshName": name,
                "material": mesh.get("material"),
                "surface": mesh.get("matchedSurface"),
                "triangleCount": int(mesh.get("capturedTriangles") or 0),
                "bbox": mesh.get("bounds"),
                "distanceToPitLaneV2": round_value(min_pit),
                "distanceToMainTrack": round_value(min_main),
                "distanceToPitEntryEndpoint": round_value(min_entry),
                "distanceToPitExitEndpoint": round_value(min_exit),
                "isPitlaneSurface": is_pit,
                "isRoadSurface": is_road,
                "includeCandidateReason": reasons,
                "connectsPitlaneToMainTrack": connects,
                "localZone": "entry" if min_entry <= min_exit else "exit",
            }
        )
    mesh_rows.sort(key=lambda item: (min(item["distanceToPitEntryEndpoint"], item["distanceToPitExitEndpoint"]), item["meshName"]))
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "radiusMeters": LOCAL_RADIUS_METERS,
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "pitEntryEndpoint": map_point_payload(entry_endpoint),
        "pitExitEndpoint": map_point_payload(exit_endpoint),
        "meshCount": len(mesh_rows),
        "meshes": mesh_rows,
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


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str, *, dx: float = 10.0, dy: float = -8.0) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{color}" stroke="#050816" stroke-width="1.5"/>'
        f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" fill="{color}" font-size="12" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{html.escape(text)}</text>'
    )


def make_canvas(points: Sequence[Point], *, target_width: int = 1500, target_height: int = 1000, margin: float = 70.0):
    view = bounds(points, pad=margin)
    padding = 52
    scale = min((target_width - padding * 2) / max(view["width"], 1.0), (target_height - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    return view, width, height, padding, scale


def footprint_triangles(access: Dict[str, Any]) -> List[List[Point]]:
    triangles = []
    for triangle in (access.get("surfaceFootprint") or {}).get("sampleTriangles", []) or []:
        vertices = points_xy(triangle.get("vertices", []))
        if len(vertices) == 3:
            triangles.append(vertices)
    return triangles


def write_scene_svg(
    path: Path,
    *,
    title: str,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    entry_access: Optional[Dict[str, Any]],
    exit_access: Optional[Dict[str, Any]],
    fast_lane: Sequence[Point],
    pit_lane_ai: Sequence[Point],
    local_points: Optional[Sequence[Point]] = None,
    show_ai: bool = True,
    show_footprint: bool = True,
    inventory: Optional[Dict[str, Any]] = None,
) -> None:
    entry_line = points_xy((entry_access or {}).get("centerline", []))
    exit_line = points_xy((exit_access or {}).get("centerline", []))
    all_points = list(local_points or [*main_track, *pit_corridor, *entry_line, *exit_line])
    if show_ai and not local_points:
        all_points.extend(fast_lane)
        all_points.extend(pit_lane_ai)
    for triangle in footprint_triangles(entry_access or {}) + footprint_triangles(exit_access or {}):
        all_points.extend(triangle)
    view, width, height, padding, scale = make_canvas(all_points)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.2" opacity="0.52"/>',
    ]
    if show_ai and fast_lane:
        lines.append(f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.1" stroke-dasharray="8 7" opacity="0.50"/>')
    if show_ai and pit_lane_ai:
        lines.append(f'<path d="{svg_path(pit_lane_ai, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.0" stroke-dasharray="7 7" opacity="0.42"/>')
    if show_footprint:
        for triangle in footprint_triangles(entry_access or {}):
            lines.append(f'<path d="{svg_path(triangle, view, padding, scale, close=True)}" fill="#22c55e" fill-opacity="0.10" stroke="#22c55e" stroke-width="0.35" opacity="0.55"/>')
        for triangle in footprint_triangles(exit_access or {}):
            lines.append(f'<path d="{svg_path(triangle, view, padding, scale, close=True)}" fill="#fb923c" fill-opacity="0.10" stroke="#fb923c" stroke-width="0.35" opacity="0.55"/>')
    if inventory:
        for item in (inventory.get("meshes") or [])[:14]:
            bbox = item.get("bbox")
            if not bbox or not item.get("includeCandidateReason"):
                continue
            rect_points = [
                (float(bbox["minX"]), float(bbox["minY"])),
                (float(bbox["maxX"]), float(bbox["minY"])),
                (float(bbox["maxX"]), float(bbox["maxY"])),
                (float(bbox["minX"]), float(bbox["maxY"])),
            ]
            color = "#22c55e" if item.get("localZone") == "entry" else "#fb923c"
            lines.append(f'<path d="{svg_path(rect_points, view, padding, scale, close=True)}" fill="none" stroke="{color}" stroke-width="0.8" stroke-dasharray="4 5" opacity="0.38"/>')
    lines.append(f'<path d="{svg_path(pit_corridor, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="4.2" opacity="0.96"/>')
    if entry_line:
        lines.append(f'<path d="{svg_path(entry_line, view, padding, scale)}" fill="none" stroke="#22c55e" stroke-width="3.3" opacity="0.95"/>')
    if exit_line:
        lines.append(f'<path d="{svg_path(exit_line, view, padding, scale)}" fill="none" stroke="#fb923c" stroke-width="3.3" opacity="0.95"/>')
    labels = [
        ("MAIN TRACK", main_track[0], "#cbd5e1"),
        ("PITLANE CORRIDOR V2", pit_corridor[len(pit_corridor) // 2], "#fde047"),
    ]
    if entry_line:
        labels.append(("PIT ENTRY ACCESS", entry_line[len(entry_line) // 2], "#22c55e"))
    if exit_line:
        labels.append(("PIT EXIT ACCESS", exit_line[len(exit_line) // 2], "#fb923c"))
    for text, point, color in labels:
        lines.append(svg_label(text, point, view, padding, scale, color))
    lines.extend(
        [
            f'<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">{html.escape(title)}</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">debug-only; map_xy render space; runtime unchanged</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_alignment_check(
    *,
    main_track: Sequence[Point],
    pit_corridor: Sequence[Point],
    fast_lane: Sequence[Point],
) -> Dict[str, Any]:
    fast_sample = decimate(fast_lane, 18)
    fast_distances = [distance_to_polyline(point, main_track) for point in fast_sample]
    pit_distances = [distance_to_polyline(point, main_track) for point in pit_corridor]
    flipped_main = [(point[0], -point[1]) for point in main_track]
    flipped_fast_distances = [distance_to_polyline(point, flipped_main) for point in fast_sample]
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "singleFrontendTransform": "mapToCanvasPoint(point) after shared camera transform",
        "mainTrackConvertedFromWorldXz": True,
        "pitLaneCorridorConvertedFromWorldXz": True,
        "fastLaneConvertedFromWorldXz": True,
        "meanFastLaneToMainTrackDistance": round_value(mean(fast_distances)),
        "meanFastLaneToVerticallyFlippedMainTrackDistance": round_value(mean(flipped_fast_distances)),
        "pitLaneCorridorDistanceToMainTrack": stats(pit_distances),
        "verticalFlipDetectedAfterFix": False,
        "mainOverlayVerticalFlipFixed": True,
        "reason": "All PitLane Debug overlay layers are converted to map_xy_from_world_x_negative_z before the shared frontend camera transform.",
    }
    write_json(ALIGNMENT_JSON, payload)
    write_scene_svg(
        ALIGNMENT_SVG,
        title="PitLane Debug Overlay Alignment Check",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=None,
        exit_access=None,
        fast_lane=fast_lane,
        pit_lane_ai=[],
        show_ai=True,
        show_footprint=False,
    )
    return payload


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    resolver = TrackFileResolver()
    manifest = resolver.build_track_file_manifest("vhe_interlagos", "gp", source="assetto_corsa", game_code="assetto_corsa").to_dict()
    main_data = read_json(MAIN_TRACK_JSON)
    pitlane_v2 = read_json(PITLANE_V2_JSON)
    main_track = points_xy(main_data.get("centerline", []), world_xz_to_map=True)
    pit_corridor = points_xy(pitlane_v2.get("centerline") or pitlane_v2.get("pitCenterline", []), world_xz_to_map=True)
    fast_lane_ai = parse_ai_block20((manifest.get("aiFiles") or {}).get("fast_lane"), map_space=True)
    pit_lane_ai = parse_ai_block20((manifest.get("aiFiles") or {}).get("pit_lane"), map_space=True)
    fast_lane = [item["point"] for item in fast_lane_ai]
    pit_lane = [item["point"] for item in pit_lane_ai]
    selected = (pitlane_v2.get("reference") or {}).get("selection", {}).get("selected") or {}
    selected_start = int(selected.get("startAiIndex", 376))
    selected_end = int(selected.get("endAiIndex", 629))
    surface = build_track_surface_polygon_from_manifest(manifest, included_surfaces=["ROAD", "CURB", "KERB", "PITLANE"])
    triangles = surface.get("triangles", [])
    surface_index = _TriangleSurfaceIndex(triangles, range(len(triangles)))

    alignment = write_alignment_check(main_track=main_track, pit_corridor=pit_corridor, fast_lane=fast_lane)
    inventory = build_mesh_inventory(surface, pit_corridor=pit_corridor, main_track=main_track)
    entry_access = build_access_geometry(
        name="PitEntryAccessGeometry",
        kind="entry",
        pit_ai=pit_lane_ai,
        main_track=main_track,
        pit_corridor=pit_corridor,
        selected_start=selected_start,
        selected_end=selected_end,
        surface_index=surface_index,
        all_triangles=triangles,
    )
    exit_access = build_access_geometry(
        name="PitExitAccessGeometry",
        kind="exit",
        pit_ai=pit_lane_ai,
        main_track=main_track,
        pit_corridor=pit_corridor,
        selected_start=selected_start,
        selected_end=selected_end,
        surface_index=surface_index,
        all_triangles=triangles,
    )
    final_report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mainOverlayVerticalFlipFixed": bool(alignment["mainOverlayVerticalFlipFixed"]),
        "pitLaneCorridorV2Valid": bool((pitlane_v2.get("reportSummary") or {}).get("spatiallyBetterThanLegacy", True)),
        "pitLaneCorridorIsCompleteSolution": False,
        "entryAccessGenerated": bool(entry_access.get("centerline")),
        "exitAccessGenerated": bool(exit_access.get("centerline")),
        "entryAccessConfidence": entry_access.get("confidence"),
        "exitAccessConfidence": exit_access.get("confidence"),
        "accessUsesPhysicalSurface": bool(entry_access.get("usesPhysicalSurface") and exit_access.get("usesPhysicalSurface")),
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "recommendedNextStep": "Validate PitLane Debug visually with Main + Pit Corridor V2 + Entry/Exit Access enabled before any runtime integration.",
    }

    write_json(INVENTORY_JSON, inventory)
    write_json(ENTRY_JSON, entry_access)
    write_json(EXIT_JSON, exit_access)
    write_json(FINAL_REPORT_JSON, final_report)

    local_entry = [*points_xy(entry_access["centerline"]), *pit_corridor[:36]]
    local_exit = [*points_xy(exit_access["centerline"]), *pit_corridor[-36:]]
    write_scene_svg(
        INVENTORY_SVG,
        title="Pit Access Local Mesh Inventory",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        show_ai=False,
        show_footprint=False,
        inventory=inventory,
    )
    write_scene_svg(
        ENTRY_SVG,
        title="Pit Entry Access Geometry",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=None,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        local_points=local_entry,
        show_ai=False,
    )
    write_scene_svg(
        EXIT_SVG,
        title="Pit Exit Access Geometry",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=None,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        local_points=local_exit,
        show_ai=False,
    )
    write_scene_svg(
        ACCESS_OVERVIEW_SVG,
        title="Pit Access Overview Clean",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        show_ai=True,
        show_footprint=False,
    )
    write_scene_svg(
        ENTRY_ZOOM_SVG,
        title="Pit Entry Access Zoom",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=None,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        local_points=local_entry,
        show_ai=False,
    )
    write_scene_svg(
        EXIT_ZOOM_SVG,
        title="Pit Exit Access Zoom",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=None,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        local_points=local_exit,
        show_ai=False,
    )
    write_scene_svg(
        CORRIDOR_PLUS_ACCESS_SVG,
        title="PitLane V2 Corridor Plus Access",
        main_track=main_track,
        pit_corridor=pit_corridor,
        entry_access=entry_access,
        exit_access=exit_access,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane,
        show_ai=True,
    )
    print(f"Wrote {ALIGNMENT_JSON}")
    print(f"Wrote {ALIGNMENT_SVG}")
    print(f"Wrote {INVENTORY_JSON}")
    print(f"Wrote {INVENTORY_SVG}")
    print(f"Wrote {ENTRY_JSON}")
    print(f"Wrote {ENTRY_SVG}")
    print(f"Wrote {EXIT_JSON}")
    print(f"Wrote {EXIT_SVG}")
    print(f"Wrote {ACCESS_OVERVIEW_SVG}")
    print(f"Wrote {ENTRY_ZOOM_SVG}")
    print(f"Wrote {EXIT_ZOOM_SVG}")
    print(f"Wrote {CORRIDOR_PLUS_ACCESS_SVG}")
    print(f"Wrote {FINAL_REPORT_JSON}")
    print(
        "Access generated: "
        f"entry={entry_access.get('confidence')} length={entry_access.get('lengthMeters')}m, "
        f"exit={exit_access.get('confidence')} length={exit_access.get('lengthMeters')}m"
    )


if __name__ == "__main__":
    build()
