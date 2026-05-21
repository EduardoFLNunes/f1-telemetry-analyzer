"""Debug-only loader for exported Interlagos pitlane geometry artifacts.

This module deliberately reads the previously generated JSON exports. It does
not derive new pitlane geometry, mutate runtime state, or integrate pitlane data
into the active TrackGeometry/projection pipeline.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


MAIN_TRACK_CACHE = "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
SURFACE_BOUNDARY_JSON = "interlagos_pitlane_surface_boundary.json"
SURFACE_DERIVED_JSON = "interlagos_pitlane_surface_derived_geometry.json"
TRIM_CANDIDATES_JSON = "interlagos_pitlane_trim_candidates_minimal.json"
SURFACE_BOUNDARY_TRANSFORM_B_JSON = "interlagos_pitlane_surface_boundary_transform_b.json"
SURFACE_DERIVED_TRANSFORM_B_JSON = "interlagos_pitlane_surface_derived_geometry_transform_b.json"
TRIM_CANDIDATES_TRANSFORM_B_JSON = "interlagos_pitlane_trim_candidates_minimal_transform_b.json"
SPATIAL_VALIDATION_TRANSFORM_B_JSON = "interlagos_pitlane_spatial_validation_transform_b.json"
TRANSFORM_B_REGENERATION_REPORT_JSON = "interlagos_pitlane_transform_b_regeneration_report.json"
MANUAL_TRIM_JSON = "interlagos_pitlane_trimmed_manual_05_05.json"
MANUAL_FINAL_REPORT_JSON = "interlagos_pitlane_manual_trim_final_report.json"
AGGRESSIVE_TRIM_JSON = "interlagos_pitlane_trimmed_geometry.json"
PIT_EXIT_ANALYSIS_JSON = "interlagos_pit_exit_core_problem_analysis.json"
MAINTRACK_EXIT_CANDIDATE_JSON = "interlagos_maintrack_pit_exit_zone_candidate.json"
PIT_EXIT_TRANSITION_JSON = "interlagos_pit_exit_transition_geometry.json"
ENTRY_EXIT_BREAKS_COMBINED_JSON = "interlagos_pit_entry_exit_breaks_combined_analysis.json"
MAINTRACK_ENTRY_CANDIDATE_JSON = "interlagos_maintrack_entry_zone_candidate.json"
MAINTRACK_EXIT_CANDIDATE_V2_JSON = "interlagos_maintrack_exit_zone_candidate_v2.json"
PIT_ENTRY_TRANSITION_CANDIDATES_JSON = "interlagos_pit_entry_transition_candidates.json"
PIT_EXIT_TRANSITION_CANDIDATES_V2_JSON = "interlagos_pit_exit_transition_candidates_v2.json"
ENTRY_EXIT_BREAKS_FINAL_REPORT_JSON = "interlagos_pit_entry_exit_breaks_final_report.json"
PITLANE_V2_GEOMETRY_JSON = "interlagos_pitlane_v2_geometry.json"
PITLANE_V2_REPORT_JSON = "interlagos_pitlane_v2_report.json"
PITLANE_V2_FINAL_ASSESSMENT_JSON = "interlagos_pitlane_v2_final_assessment.json"
PITLANE_OVERLAY_ALIGNMENT_CHECK_JSON = "interlagos_pitlane_debug_overlay_alignment_check.json"
PIT_ACCESS_LOCAL_MESH_INVENTORY_JSON = "interlagos_pit_access_local_mesh_inventory.json"
PIT_ENTRY_ACCESS_GEOMETRY_JSON = "interlagos_pit_entry_access_geometry.json"
PIT_EXIT_ACCESS_GEOMETRY_JSON = "interlagos_pit_exit_access_geometry.json"
PIT_ACCESS_FINAL_REPORT_JSON = "interlagos_pit_access_final_report.json"
PIT_AREA_MESH_INVENTORY_JSON = "interlagos_pit_area_mesh_inventory.json"
PIT_AREA_SURFACE_JSON = "interlagos_pit_area_surface.json"
PIT_AREA_COMPONENTS_JSON = "interlagos_pit_area_components.json"
PIT_AREA_CENTERLINES_JSON = "interlagos_pit_area_centerlines.json"
PIT_AREA_OVERLAY_ALIGNMENT_CHECK_JSON = "interlagos_pit_area_overlay_alignment_check.json"
PIT_AREA_FINAL_REPORT_JSON = "interlagos_pit_area_final_report.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _point_xy(point: Any, *, flip_y: bool = False) -> Optional[Dict[str, float]]:
    if point is None:
        return None
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        x, y = point[0], point[1]
    elif isinstance(point, dict):
        x = point.get("x")
        y = point.get("y", point.get("z"))
    else:
        return None
    try:
        x_float = float(x)
        y_float = float(y)
    except (TypeError, ValueError):
        return None
    if flip_y:
        y_float = -y_float
    return {"x": x_float, "y": y_float}


def _points_xy(points: Iterable[Any], *, flip_y: bool = False) -> List[Dict[str, float]]:
    return [point for point in (_point_xy(raw, flip_y=flip_y) for raw in points or []) if point is not None]


def _artifact_uses_world_xz(data: Dict[str, Any]) -> bool:
    projection = str(data.get("projection") or data.get("coordinateSystem") or "").lower()
    transform = data.get("transform") or {}
    output_system = str(transform.get("outputCoordinateSystem") or "").lower() if isinstance(transform, dict) else ""
    equivalent = str(transform.get("outputEquivalentTransform") or "").lower() if isinstance(transform, dict) else ""
    projection_compact = projection.replace(" ", "")
    equivalent_compact = equivalent.replace(" ", "")
    if "mapy=-worldz" in projection_compact or "negative_z" in projection:
        return False
    if "mapy=worldz" in projection_compact or "world_xz" in projection:
        return True
    if output_system == "world_xz" or "mapy=worldz" in equivalent_compact:
        return True
    return False


def _normalize_debug_points_in_dict(data: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    normalized = dict(data)
    for key in keys:
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = _points_xy(value)
    for key in ("pitManualEnd", "startPitPoint", "endMainMergePoint"):
        point = normalized.get(key)
        if isinstance(point, dict):
            normalized[key] = _point_xy(point)
    if isinstance(normalized.get("nearestMainPoint"), dict):
        nearest = dict(normalized["nearestMainPoint"])
        if isinstance(nearest.get("point"), dict):
            nearest["point"] = _point_xy(nearest["point"])
        normalized["nearestMainPoint"] = nearest
    if isinstance(normalized.get("directionCompatibleMergePoint"), dict):
        merge = dict(normalized["directionCompatibleMergePoint"])
        if isinstance(merge.get("point"), dict):
            merge["point"] = _point_xy(merge["point"])
        normalized["directionCompatibleMergePoint"] = merge
    return normalized


def _normalize_maintrack_candidate(data: Dict[str, Any]) -> Dict[str, Any]:
    return _normalize_debug_points_in_dict(data, ("originalSegment", "candidateSegment"))


def _normalize_transition_candidates(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(data)
    candidates = []
    for candidate in normalized.get("candidates", []) or []:
        item = dict(candidate)
        item["startPoint"] = _point_xy(item.get("startPoint"))
        item["endPoint"] = _point_xy(item.get("endPoint"))
        item["centerline"] = _points_xy(item.get("centerline", []))
        item["controlPoints"] = _points_xy(item.get("controlPoints", []))
        candidates.append(item)
    normalized["candidates"] = candidates
    return normalized


def _normalize_access_geometry(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data or data.get("_missing"):
        return data
    normalized = dict(data)
    flip_y = _artifact_uses_world_xz(normalized)
    for key in ("centerline", "leftEdge", "rightEdge"):
        if isinstance(normalized.get(key), list):
            normalized[key] = _points_xy(normalized.get(key), flip_y=flip_y)
    for key in ("startPoint", "endPoint"):
        if isinstance(normalized.get(key), dict):
            normalized[key] = _point_xy(normalized.get(key), flip_y=flip_y)
    for field in ("mainTrackConnection", "pitLaneConnection"):
        if isinstance(normalized.get(field), dict):
            item = dict(normalized[field])
            if isinstance(item.get("point"), dict):
                item["point"] = _point_xy(item["point"], flip_y=flip_y)
            normalized[field] = item
    footprint = dict(normalized.get("surfaceFootprint") or {})
    sample_triangles = []
    for triangle in footprint.get("sampleTriangles", []) or []:
        vertices = _points_xy(triangle.get("vertices", []), flip_y=flip_y)
        sample_triangles.append({**triangle, "vertices": vertices})
    if sample_triangles:
        footprint["sampleTriangles"] = sample_triangles
        normalized["surfaceFootprint"] = footprint
    normalized["renderCoordinateSystem"] = "map_xy_from_world_x_negative_z"
    return normalized


def _distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    return ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2) ** 0.5


def _polyline_length(points: List[Dict[str, float]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(_distance(points[index - 1], points[index]) for index in range(1, len(points)))


def _bounds_from_points(points: Iterable[Dict[str, float]]) -> Optional[Dict[str, float]]:
    pts = [point for point in points if point and isinstance(point.get("x"), (int, float)) and isinstance(point.get("y"), (int, float))]
    if not pts:
        return None
    xs = [point["x"] for point in pts]
    ys = [point["y"] for point in pts]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    return {
        "minX": min_x,
        "maxX": max_x,
        "minY": min_y,
        "maxY": max_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def _sample_items(items: List[Any], max_count: int) -> List[Any]:
    if len(items) <= max_count:
        return items
    step = max(1, (len(items) + max_count - 1) // max_count)
    return items[::step][:max_count]


def _normalize_triangle(triangle: Dict[str, Any], *, flip_y: bool = False) -> Dict[str, Any]:
    vertices = _points_xy(triangle.get("vertices", []), flip_y=flip_y)
    centroid = _point_xy(triangle.get("centroid"), flip_y=flip_y)
    if centroid is None and vertices:
        centroid = {
            "x": sum(point["x"] for point in vertices) / len(vertices),
            "y": sum(point["y"] for point in vertices) / len(vertices),
        }
    return {
        **triangle,
        "vertices": vertices,
        "centroid": centroid,
    }


def _normalize_boundary_loops(loops: Iterable[Dict[str, Any]], *, flip_y: bool = False) -> List[Dict[str, Any]]:
    return [
        {
            "loopId": loop.get("loopId"),
            "closed": loop.get("closed", True),
            "pointCount": loop.get("pointCount"),
            "area": loop.get("area"),
            "perimeter": loop.get("perimeter"),
            "points": _points_xy(loop.get("points", []), flip_y=flip_y),
        }
        for loop in loops or []
    ]


def _normalize_pit_area_surface(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data or data.get("_missing"):
        return data
    triangles = data.get("triangles", []) or []
    sample_triangles = [_normalize_triangle(triangle) for triangle in _sample_items(triangles, 2600)]
    return {
        "name": data.get("name", "PitAreaSurface"),
        "debugOnly": True,
        "runtimeChanged": bool(data.get("runtimeChanged", False)),
        "authoritativeGeometryChanged": bool(data.get("authoritativeGeometryChanged", False)),
        "coordinateSystem": data.get("coordinateSystem"),
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "method": data.get("method"),
        "triangleCount": int(data.get("triangleCount") or len(triangles)),
        "sampleTriangles": sample_triangles,
        "sampleTriangleCount": len(sample_triangles),
        "boundaryLoops": _normalize_boundary_loops(data.get("boundaryLoops", [])),
        "boundaryLoopCount": data.get("boundaryLoopCount"),
        "boundaryEdgeCount": data.get("boundaryEdgeCount"),
        "bbox": data.get("bbox"),
        "sourceMeshes": data.get("sourceMeshes", {}),
        "sourceSurfaces": data.get("sourceSurfaces", {}),
    }


def _normalize_pit_area_components(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data or data.get("_missing"):
        return data
    components = []
    for component in data.get("components", []) or []:
        item = dict(component)
        item["sampleTriangles"] = [
            _normalize_triangle(triangle)
            for triangle in _sample_items(component.get("sampleTriangles", []) or [], 900)
        ]
        components.append(item)
    return {
        **data,
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "components": components,
    }


def _normalize_pit_area_centerlines(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data or data.get("_missing"):
        return data
    normalized = dict(data)
    centerlines = {}
    for name, centerline in (data.get("centerlines") or {}).items():
        item = dict(centerline)
        item["centerline"] = _points_xy(item.get("centerline", []))
        centerlines[name] = item
    ai_references = {}
    for name, reference in (data.get("aiReferences") or {}).items():
        item = dict(reference)
        item["centerline"] = _points_xy(item.get("centerline", []))
        ai_references[name] = item
    normalized["centerlines"] = centerlines
    normalized["aiReferences"] = ai_references
    normalized["renderCoordinateSystem"] = "map_xy_from_world_x_negative_z"
    return normalized


def _geometry_from_artifact(data: Dict[str, Any], name: str, role: str) -> Dict[str, Any]:
    flip_y = _artifact_uses_world_xz(data)
    centerline = _points_xy(data.get("pitCenterline") or data.get("centerline") or [], flip_y=flip_y)
    left_edge = _points_xy(data.get("pitLeftEdge") or data.get("leftEdge") or data.get("left_edge") or [], flip_y=flip_y)
    right_edge = _points_xy(data.get("pitRightEdge") or data.get("rightEdge") or data.get("right_edge") or [], flip_y=flip_y)
    width = [float(value) for value in data.get("pitWidth", data.get("width", [])) if isinstance(value, (int, float))]
    if not width and left_edge and right_edge:
        width = [_distance(left, right) for left, right in zip(left_edge, right_edge)]

    length = data.get("lengthMeters", data.get("rawLengthMeters"))
    if not isinstance(length, (int, float)):
        length = _polyline_length(centerline)

    return {
        "name": name,
        "role": role,
        "centerline": centerline,
        "leftEdge": left_edge,
        "rightEdge": right_edge,
        "width": width,
        "pointCount": len(centerline),
        "lengthMeters": float(length or 0.0),
        "start": centerline[0] if centerline else None,
        "end": centerline[-1] if centerline else None,
        "bounds": _bounds_from_points([*centerline, *left_edge, *right_edge]),
        "widthStats": data.get("widthStats") or (data.get("metadata") or {}).get("widthStats") or {
            "min": data.get("widthMin"),
            "avg": data.get("widthAvg"),
            "max": data.get("widthMax"),
        },
        "source": data.get("source"),
        "provider": data.get("provider"),
        "method": data.get("method"),
        "transform": data.get("transform"),
        "confidence": data.get("confidence"),
        "openLoop": data.get("openLoop"),
        "runtimeChanged": data.get("runtimeChanged"),
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "projection": data.get("projection"),
        "metadata": data.get("metadata", {}),
        "diagnostics": data.get("diagnostics", []),
    }


def _candidate_geometry(candidate: Dict[str, Any]) -> Dict[str, Any]:
    geometry = _geometry_from_artifact(candidate, candidate.get("name", "candidate"), "trim_candidate")
    geometry.update(
        {
            "startTrimPoints": candidate.get("startTrimPoints"),
            "endTrimPoints": candidate.get("endTrimPoints"),
            "removedStartMeters": float(candidate.get("removedStartMeters") or 0.0),
            "removedEndMeters": float(candidate.get("removedEndMeters") or 0.0),
            "lengthRatioVsRaw": candidate.get("lengthRatioVsRaw"),
        }
    )
    return geometry


def _main_track_geometry(cache_data: Dict[str, Any]) -> Dict[str, Any]:
    centerline = _points_xy(cache_data.get("centerline", []), flip_y=True)
    left_edge = _points_xy(cache_data.get("boundsLeft", cache_data.get("left_edge", [])), flip_y=True)
    right_edge = _points_xy(cache_data.get("boundsRight", cache_data.get("right_edge", [])), flip_y=True)
    return {
        "name": cache_data.get("trackName", "vhe_interlagos"),
        "trackConfig": cache_data.get("trackConfig", "gp"),
        "centerline": centerline,
        "leftEdge": left_edge,
        "rightEdge": right_edge,
        "pointCount": len(centerline),
        "lengthMeters": float(cache_data.get("trackLength") or cache_data.get("length_meters") or 0.0),
        "bounds": cache_data.get("bounds") or _bounds_from_points([*centerline, *left_edge, *right_edge]),
        "provider": cache_data.get("provider"),
        "source": cache_data.get("source"),
        "cachePath": cache_data.get("cachePath"),
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
    }


def build_pitlane_debug_payload(repo_root: Path) -> Dict[str, Any]:
    debug_dir = repo_root / "data" / "debug"
    cache_dir = repo_root / "data" / "cache" / "tracks"

    raw_data = _read_json(debug_dir / SURFACE_DERIVED_JSON)
    manual_data = _read_json(debug_dir / MANUAL_TRIM_JSON)
    candidates_data = _read_json(debug_dir / TRIM_CANDIDATES_JSON)
    boundary_data = _read_json(debug_dir / SURFACE_BOUNDARY_JSON)
    raw_transform_b_data = _read_json(debug_dir / SURFACE_DERIVED_TRANSFORM_B_JSON)
    candidates_transform_b_data = _read_json(debug_dir / TRIM_CANDIDATES_TRANSFORM_B_JSON)
    boundary_transform_b_data = _read_json(debug_dir / SURFACE_BOUNDARY_TRANSFORM_B_JSON)
    spatial_validation_transform_b = _read_json(debug_dir / SPATIAL_VALIDATION_TRANSFORM_B_JSON)
    regeneration_report_transform_b = _read_json(debug_dir / TRANSFORM_B_REGENERATION_REPORT_JSON)
    manual_report = _read_json(debug_dir / MANUAL_FINAL_REPORT_JSON)
    aggressive_data = _read_json(debug_dir / AGGRESSIVE_TRIM_JSON)
    pit_exit_analysis = _read_json(debug_dir / PIT_EXIT_ANALYSIS_JSON)
    maintrack_exit_candidate = _read_json(debug_dir / MAINTRACK_EXIT_CANDIDATE_JSON)
    pit_exit_transition = _read_json(debug_dir / PIT_EXIT_TRANSITION_JSON)
    entry_exit_breaks = _read_json(debug_dir / ENTRY_EXIT_BREAKS_COMBINED_JSON)
    maintrack_entry_candidate = _read_json(debug_dir / MAINTRACK_ENTRY_CANDIDATE_JSON)
    maintrack_exit_candidate_v2 = _read_json(debug_dir / MAINTRACK_EXIT_CANDIDATE_V2_JSON)
    pit_entry_transition_candidates = _read_json(debug_dir / PIT_ENTRY_TRANSITION_CANDIDATES_JSON)
    pit_exit_transition_candidates_v2 = _read_json(debug_dir / PIT_EXIT_TRANSITION_CANDIDATES_V2_JSON)
    entry_exit_breaks_final_report = _read_json(debug_dir / ENTRY_EXIT_BREAKS_FINAL_REPORT_JSON)
    pitlane_v2_data = _read_json(debug_dir / PITLANE_V2_GEOMETRY_JSON)
    pitlane_v2_report = _read_json(debug_dir / PITLANE_V2_REPORT_JSON)
    pitlane_v2_assessment = _read_json(debug_dir / PITLANE_V2_FINAL_ASSESSMENT_JSON)
    overlay_alignment_check = _read_json(debug_dir / PITLANE_OVERLAY_ALIGNMENT_CHECK_JSON)
    pit_access_inventory = _read_json(debug_dir / PIT_ACCESS_LOCAL_MESH_INVENTORY_JSON)
    pit_entry_access = _normalize_access_geometry(_read_json(debug_dir / PIT_ENTRY_ACCESS_GEOMETRY_JSON))
    pit_exit_access = _normalize_access_geometry(_read_json(debug_dir / PIT_EXIT_ACCESS_GEOMETRY_JSON))
    pit_access_final_report = _read_json(debug_dir / PIT_ACCESS_FINAL_REPORT_JSON)
    pit_area_mesh_inventory = _read_json(debug_dir / PIT_AREA_MESH_INVENTORY_JSON)
    pit_area_surface = _normalize_pit_area_surface(_read_json(debug_dir / PIT_AREA_SURFACE_JSON))
    pit_area_components = _normalize_pit_area_components(_read_json(debug_dir / PIT_AREA_COMPONENTS_JSON))
    pit_area_centerlines = _normalize_pit_area_centerlines(_read_json(debug_dir / PIT_AREA_CENTERLINES_JSON))
    pit_area_overlay_alignment_check = _read_json(debug_dir / PIT_AREA_OVERLAY_ALIGNMENT_CHECK_JSON)
    pit_area_final_report = _read_json(debug_dir / PIT_AREA_FINAL_REPORT_JSON)
    main_track_data = _read_json(cache_dir / MAIN_TRACK_CACHE)

    pitlane_raw = _geometry_from_artifact(raw_data, "PitLaneGeometryRaw", "raw_surface_derived")
    pitlane_manual = _geometry_from_artifact(manual_data, "PitLaneGeometryTrimmedManual_05_05", "trimmed_manual")
    pitlane_v2 = _geometry_from_artifact(pitlane_v2_data, "PitLaneCorridorGeometryV2", "pitlane_surface_interval_v2")
    trim_candidates = [_candidate_geometry(candidate) for candidate in candidates_data.get("candidates", [])]
    pitlane_transform_b_raw = _geometry_from_artifact(raw_transform_b_data, "PitLaneGeometryTransformB", "debug_transform_b")
    trim_candidates_transform_b = [
        _candidate_geometry(candidate)
        for candidate in candidates_transform_b_data.get("candidates", [])
    ]
    transform_b_candidate_by_name = {candidate["name"]: candidate for candidate in trim_candidates_transform_b}

    selected = manual_data.get("manualTrimSelected") or (manual_data.get("metadata") or {}).get("manualTrimSelected") or "candidate_05_05"
    candidate_by_name = {candidate["name"]: candidate for candidate in trim_candidates}
    selected_candidate = candidate_by_name.get(selected)

    metadata = {
        "selectedManualTrim": selected,
        "manualTrimReason": manual_data.get("manualTrimReason") or (manual_data.get("metadata") or {}).get("manualTrimReason"),
        "aggressiveTrimRejected": bool(manual_data.get("aggressiveTrimRejected", True)),
        "runtimeChanged": bool(manual_data.get("runtimeChanged", False)),
        "readyForRuntimeIntegration": False,
        "pitLaneAiUsedForGeometry": bool(manual_data.get("pitLaneAiUsedForGeometry", False)),
        "rawPointCount": pitlane_raw["pointCount"],
        "trimmedPointCount": pitlane_manual["pointCount"],
        "rawLengthMeters": float(manual_data.get("rawLengthMeters") or pitlane_raw["lengthMeters"]),
        "trimmedLengthMeters": float(manual_data.get("lengthMeters") or pitlane_manual["lengthMeters"]),
        "removedStartMeters": float(manual_data.get("removedStartMeters") or 0.0),
        "removedEndMeters": float(manual_data.get("removedEndMeters") or 0.0),
        "aggressiveTrim": {
            "pointCount": len(aggressive_data.get("pitCenterline", [])),
            "lengthMeters": aggressive_data.get("lengthMeters"),
            "removedStartMeters": aggressive_data.get("removedStartMeters"),
            "removedEndMeters": aggressive_data.get("removedEndMeters"),
            "selectedStartIndex": aggressive_data.get("selectedStartIndex"),
            "selectedEndIndex": aggressive_data.get("selectedEndIndex"),
            "rejected": True,
        },
        "validationReport": manual_report.get("visualValidation", {}),
    }

    surface_boundary = boundary_data.get("pitBoundaryLoops", {})
    raw_loops = surface_boundary.get("rawLoops", []) if isinstance(surface_boundary, dict) else []
    surface = {
        "bounds": boundary_data.get("pitSurfaceBounds") or raw_data.get("pitSurfaceBounds"),
        "boundaryLoops": [
            {
                "loopId": loop.get("loopId"),
                "closed": loop.get("closed", True),
                "pointCount": loop.get("pointCount"),
                "area": loop.get("area"),
                "perimeter": loop.get("perimeter"),
                "points": _points_xy(loop.get("points", [])),
            }
            for loop in raw_loops
        ],
        "triangleCount": len(boundary_data.get("pitSurfaceTriangles", [])),
    }

    surface_boundary_transform_b = boundary_transform_b_data.get("pitBoundaryLoops", {})
    raw_loops_transform_b = surface_boundary_transform_b.get("rawLoops", []) if isinstance(surface_boundary_transform_b, dict) else []
    surface_transform_b = {
        "bounds": boundary_transform_b_data.get("pitSurfaceBounds") or raw_transform_b_data.get("pitSurfaceBounds"),
        "boundaryLoops": [
            {
                "loopId": loop.get("loopId"),
                "closed": loop.get("closed", True),
                "pointCount": loop.get("pointCount"),
                "area": loop.get("area"),
                "perimeter": loop.get("perimeter"),
                "points": _points_xy(loop.get("points", [])),
            }
            for loop in raw_loops_transform_b
        ],
        "triangleCount": len(boundary_transform_b_data.get("pitSurfaceTriangles", [])),
    }
    v2_loops = ((pitlane_v2_data.get("surface") or {}).get("cleanBoundaryLoops") or [])
    surface_v2 = {
        "bounds": pitlane_v2_data.get("bounds"),
        "boundaryLoops": [
            {
                "loopId": loop.get("loopId"),
                "closed": loop.get("closed", True),
                "pointCount": loop.get("pointCount"),
                "area": loop.get("area"),
                "perimeter": loop.get("perimeter"),
                "points": _points_xy(loop.get("points", []), flip_y=True),
            }
            for loop in v2_loops
        ],
        "triangleCount": (pitlane_v2_data.get("metrics") or {}).get("selectedComponentTriangleCount"),
        "sourceMeshNames": ((pitlane_v2_data.get("surface") or {}).get("sourceMeshNames") or []),
    }

    exports = {
        "overviewSvg": str(debug_dir / "interlagos_pitlane_visual_debug_overview.svg"),
        "entryZoomSvg": str(debug_dir / "interlagos_pitlane_visual_debug_entry_zoom.svg"),
        "exitZoomSvg": str(debug_dir / "interlagos_pitlane_visual_debug_exit_zoom.svg"),
        "pitlaneV2GeometryJson": str(debug_dir / PITLANE_V2_GEOMETRY_JSON),
        "pitlaneV2GeometrySvg": str(debug_dir / "interlagos_pitlane_v2_geometry.svg"),
        "pitlaneV2ReportJson": str(debug_dir / PITLANE_V2_REPORT_JSON),
        "pitlaneV2OverviewCleanSvg": str(debug_dir / "interlagos_pitlane_v2_overview_clean.svg"),
        "pitlaneV2EntryZoomSvg": str(debug_dir / "interlagos_pitlane_v2_entry_zoom.svg"),
        "pitlaneV2ExitZoomSvg": str(debug_dir / "interlagos_pitlane_v2_exit_zoom.svg"),
        "pitlaneV2VsLegacySvg": str(debug_dir / "interlagos_pitlane_v2_vs_legacy.svg"),
        "pitlaneV2FinalAssessmentJson": str(debug_dir / PITLANE_V2_FINAL_ASSESSMENT_JSON),
        "pitlaneOverlayAlignmentCheckJson": str(debug_dir / PITLANE_OVERLAY_ALIGNMENT_CHECK_JSON),
        "pitlaneOverlayAlignmentCheckSvg": str(debug_dir / "interlagos_pitlane_debug_overlay_alignment_check.svg"),
        "pitAccessLocalMeshInventoryJson": str(debug_dir / PIT_ACCESS_LOCAL_MESH_INVENTORY_JSON),
        "pitAccessLocalMeshInventorySvg": str(debug_dir / "interlagos_pit_access_local_mesh_inventory.svg"),
        "pitEntryAccessGeometryJson": str(debug_dir / PIT_ENTRY_ACCESS_GEOMETRY_JSON),
        "pitEntryAccessGeometrySvg": str(debug_dir / "interlagos_pit_entry_access_geometry.svg"),
        "pitExitAccessGeometryJson": str(debug_dir / PIT_EXIT_ACCESS_GEOMETRY_JSON),
        "pitExitAccessGeometrySvg": str(debug_dir / "interlagos_pit_exit_access_geometry.svg"),
        "pitAccessOverviewCleanSvg": str(debug_dir / "interlagos_pit_access_overview_clean.svg"),
        "pitEntryAccessZoomSvg": str(debug_dir / "interlagos_pit_entry_access_zoom.svg"),
        "pitExitAccessZoomSvg": str(debug_dir / "interlagos_pit_exit_access_zoom.svg"),
        "pitlaneV2CorridorPlusAccessSvg": str(debug_dir / "interlagos_pitlane_v2_corridor_plus_access.svg"),
        "pitAccessFinalReportJson": str(debug_dir / PIT_ACCESS_FINAL_REPORT_JSON),
        "pitAreaMeshInventoryJson": str(debug_dir / PIT_AREA_MESH_INVENTORY_JSON),
        "pitAreaMeshInventorySvg": str(debug_dir / "interlagos_pit_area_mesh_inventory.svg"),
        "pitAreaSurfaceJson": str(debug_dir / PIT_AREA_SURFACE_JSON),
        "pitAreaSurfaceSvg": str(debug_dir / "interlagos_pit_area_surface.svg"),
        "pitAreaComponentsJson": str(debug_dir / PIT_AREA_COMPONENTS_JSON),
        "pitAreaComponentsSvg": str(debug_dir / "interlagos_pit_area_components.svg"),
        "pitAreaCenterlinesJson": str(debug_dir / PIT_AREA_CENTERLINES_JSON),
        "pitAreaCenterlinesSvg": str(debug_dir / "interlagos_pit_area_centerlines.svg"),
        "pitAreaOverlayAlignmentCheckJson": str(debug_dir / PIT_AREA_OVERLAY_ALIGNMENT_CHECK_JSON),
        "pitAreaOverlayAlignmentCheckSvg": str(debug_dir / "interlagos_pit_area_overlay_alignment_check.svg"),
        "pitAreaFinalReportJson": str(debug_dir / PIT_AREA_FINAL_REPORT_JSON),
        "manualTrimSvg": str(debug_dir / "interlagos_pitlane_trimmed_manual_05_05.svg"),
        "manualVsCandidateSvg": str(debug_dir / "interlagos_pitlane_raw_vs_manual_05_05_vs_08_08.svg"),
        "pitExitAnalysisSvg": str(debug_dir / "interlagos_pit_exit_core_problem_analysis.svg"),
        "maintrackExitCandidateSvg": str(debug_dir / "interlagos_maintrack_pit_exit_zone_candidate.svg"),
        "pitExitTransitionSvg": str(debug_dir / "interlagos_pit_exit_transition_geometry.svg"),
        "entryExitBreaksCombinedAnalysisSvg": str(debug_dir / "interlagos_pit_entry_exit_breaks_combined_analysis.svg"),
        "maintrackEntryZoneCandidateSvg": str(debug_dir / "interlagos_maintrack_entry_zone_candidate.svg"),
        "maintrackExitZoneCandidateV2Svg": str(debug_dir / "interlagos_maintrack_exit_zone_candidate_v2.svg"),
        "pitEntryTransitionCandidatesSvg": str(debug_dir / "interlagos_pit_entry_transition_candidates.svg"),
        "pitExitTransitionCandidatesV2Svg": str(debug_dir / "interlagos_pit_exit_transition_candidates_v2.svg"),
        "entryExitBreaksFinalReportJson": str(debug_dir / "interlagos_pit_entry_exit_breaks_final_report.json"),
        "pitTransformBSurfaceBoundarySvg": str(debug_dir / "interlagos_pitlane_surface_boundary_transform_b.svg"),
        "pitTransformBDerivedGeometrySvg": str(debug_dir / "interlagos_pitlane_surface_derived_geometry_transform_b.svg"),
        "pitTransformBTrimCandidatesSvg": str(debug_dir / "interlagos_pitlane_trim_candidates_minimal_transform_b.svg"),
        "pitTransformBSpatialValidationSvg": str(debug_dir / "interlagos_pitlane_spatial_validation_transform_b.svg"),
        "pitTransformBRegenerationReportJson": str(debug_dir / TRANSFORM_B_REGENERATION_REPORT_JSON),
        "pitTransformBTrimDecisionSvg": str(debug_dir / "interlagos_pitlane_transform_b_trim_decision.svg"),
        "pitTransformBTrimDecisionJson": str(debug_dir / "interlagos_pitlane_transform_b_trim_decision.json"),
        "pitTransformBEntryExitAnalysisSvg": str(debug_dir / "interlagos_pitlane_transform_b_entry_exit_analysis.svg"),
        "pitTransformBEntryExitAnalysisJson": str(debug_dir / "interlagos_pitlane_transform_b_entry_exit_analysis.json"),
        "pitTransformBEntryExitReportJson": str(debug_dir / "interlagos_pitlane_transform_b_entry_exit_report.json"),
    }

    all_bounds_points = [
        *(pitlane_raw.get("leftEdge") or []),
        *(pitlane_raw.get("rightEdge") or []),
        *(pitlane_raw.get("centerline") or []),
        *(pitlane_manual.get("centerline") or []),
        *(pitlane_transform_b_raw.get("leftEdge") or []),
        *(pitlane_transform_b_raw.get("rightEdge") or []),
        *(pitlane_transform_b_raw.get("centerline") or []),
        *(pitlane_v2.get("leftEdge") or []),
        *(pitlane_v2.get("rightEdge") or []),
        *(pitlane_v2.get("centerline") or []),
    ]
    for loop in surface["boundaryLoops"]:
        all_bounds_points.extend(loop.get("points") or [])
    for loop in surface_transform_b["boundaryLoops"]:
        all_bounds_points.extend(loop.get("points") or [])
    for loop in surface_v2["boundaryLoops"]:
        all_bounds_points.extend(loop.get("points") or [])
    for loop in pit_area_surface.get("boundaryLoops", []) or []:
        all_bounds_points.extend(loop.get("points") or [])
    for centerline in (pit_area_centerlines.get("centerlines") or {}).values():
        all_bounds_points.extend(centerline.get("centerline") or [])

    return {
        "trackName": raw_data.get("trackName") or "vhe_interlagos",
        "trackConfig": raw_data.get("trackConfig") or "gp",
        "sourceOfTruth": [
            str(debug_dir / SURFACE_BOUNDARY_JSON),
            str(debug_dir / SURFACE_DERIVED_JSON),
            str(debug_dir / TRIM_CANDIDATES_JSON),
            str(debug_dir / SURFACE_BOUNDARY_TRANSFORM_B_JSON),
            str(debug_dir / SURFACE_DERIVED_TRANSFORM_B_JSON),
            str(debug_dir / TRIM_CANDIDATES_TRANSFORM_B_JSON),
            str(debug_dir / SPATIAL_VALIDATION_TRANSFORM_B_JSON),
            str(debug_dir / TRANSFORM_B_REGENERATION_REPORT_JSON),
            str(debug_dir / "interlagos_pitlane_transform_b_trim_decision.json"),
            str(debug_dir / "interlagos_pitlane_transform_b_entry_exit_analysis.json"),
            str(debug_dir / "interlagos_pitlane_transform_b_entry_exit_report.json"),
            str(debug_dir / PITLANE_V2_GEOMETRY_JSON),
            str(debug_dir / PITLANE_V2_REPORT_JSON),
            str(debug_dir / PITLANE_V2_FINAL_ASSESSMENT_JSON),
            str(debug_dir / PITLANE_OVERLAY_ALIGNMENT_CHECK_JSON),
            str(debug_dir / PIT_ACCESS_LOCAL_MESH_INVENTORY_JSON),
            str(debug_dir / PIT_ENTRY_ACCESS_GEOMETRY_JSON),
            str(debug_dir / PIT_EXIT_ACCESS_GEOMETRY_JSON),
            str(debug_dir / PIT_ACCESS_FINAL_REPORT_JSON),
            str(debug_dir / PIT_AREA_MESH_INVENTORY_JSON),
            str(debug_dir / PIT_AREA_SURFACE_JSON),
            str(debug_dir / PIT_AREA_COMPONENTS_JSON),
            str(debug_dir / PIT_AREA_CENTERLINES_JSON),
            str(debug_dir / PIT_AREA_OVERLAY_ALIGNMENT_CHECK_JSON),
            str(debug_dir / PIT_AREA_FINAL_REPORT_JSON),
            str(debug_dir / MANUAL_TRIM_JSON),
            str(debug_dir / MANUAL_FINAL_REPORT_JSON),
            str(debug_dir / ENTRY_EXIT_BREAKS_COMBINED_JSON),
            str(debug_dir / MAINTRACK_ENTRY_CANDIDATE_JSON),
            str(debug_dir / MAINTRACK_EXIT_CANDIDATE_V2_JSON),
            str(debug_dir / PIT_ENTRY_TRANSITION_CANDIDATES_JSON),
            str(debug_dir / PIT_EXIT_TRANSITION_CANDIDATES_V2_JSON),
            str(debug_dir / ENTRY_EXIT_BREAKS_FINAL_REPORT_JSON),
            str(cache_dir / MAIN_TRACK_CACHE),
        ],
        "canonicalMapSpace": "mapX=worldX,mapY=-worldZ",
        "renderCoordinateSystem": "map_xy_from_world_x_negative_z",
        "debugOnly": True,
        "runtimeChanged": False,
        "activePitlaneDebugVersion": "PitAreaGeometry",
        "mainTrack": _main_track_geometry(main_track_data),
        "pitAreaGeometry": {
            "active": True,
            "name": "PitAreaGeometry",
            "surface": pit_area_surface,
            "components": pit_area_components,
            "centerlines": pit_area_centerlines,
            "meshInventory": pit_area_mesh_inventory,
            "overlayAlignmentCheck": pit_area_overlay_alignment_check,
            "finalReport": pit_area_final_report,
            "provider": "debug_export",
            "method": pit_area_surface.get("method"),
            "sourceMeshes": pit_area_final_report.get("sourceMeshes", {}),
            "sourceMeshCount": pit_area_final_report.get("sourceMeshCount"),
            "triangleCount": pit_area_final_report.get("triangleCount") or pit_area_surface.get("triangleCount"),
            "corridorDetected": bool(pit_area_final_report.get("pitAreaIncludesCorridor")),
            "entryAccessDetected": bool(pit_area_final_report.get("pitAreaIncludesEntryAccess")),
            "exitAccessDetected": bool(pit_area_final_report.get("pitAreaIncludesExitAccess")),
            "confidence": pit_area_final_report.get("confidence"),
            "runtimeChanged": bool(pit_area_final_report.get("runtimeChanged", False)),
            "authoritativeGeometryChanged": bool(pit_area_final_report.get("authoritativeGeometryChanged", False)),
            "readyForRuntimeIntegration": bool(pit_area_final_report.get("readyForRuntimeIntegration", False)),
            "note": "Complete pit-area surface/branch for manual debug evaluation; not part of MainTrackGeometry or runtime projection.",
        },
        "pitLaneCorridorV2": {
            "active": True,
            "geometry": pitlane_v2,
            "surface": surface_v2,
            "provider": pitlane_v2_data.get("provider"),
            "method": pitlane_v2_data.get("method"),
            "transform": pitlane_v2_data.get("transform"),
            "confidence": pitlane_v2_data.get("confidence"),
            "openLoop": bool(pitlane_v2_data.get("openLoop", True)),
            "runtimeChanged": bool(pitlane_v2_data.get("runtimeChanged", False)),
            "readyForRuntimeIntegration": bool(pitlane_v2_data.get("readyForRuntimeIntegration", False)),
            "report": pitlane_v2_report,
            "assessment": pitlane_v2_assessment,
            "note": "Corridor only. Pit entry/exit access branches are exposed separately.",
        },
        "pitlaneV2": {
            "active": True,
            "geometry": pitlane_v2,
            "surface": surface_v2,
            "provider": pitlane_v2_data.get("provider"),
            "method": pitlane_v2_data.get("method"),
            "transform": pitlane_v2_data.get("transform"),
            "confidence": pitlane_v2_data.get("confidence"),
            "openLoop": bool(pitlane_v2_data.get("openLoop", True)),
            "runtimeChanged": bool(pitlane_v2_data.get("runtimeChanged", False)),
            "readyForRuntimeIntegration": bool(pitlane_v2_data.get("readyForRuntimeIntegration", False)),
            "report": pitlane_v2_report,
            "assessment": pitlane_v2_assessment,
            "note": "Alias for pitLaneCorridorV2; corridor only.",
        },
        "pitEntryAccess": pit_entry_access,
        "pitExitAccess": pit_exit_access,
        "pitAccessLocalMeshInventory": pit_access_inventory,
        "pitlaneOverlayAlignmentCheck": overlay_alignment_check,
        "pitAccessFinalReport": pit_access_final_report,
        "pitlaneLegacy": {
            "active": False,
            "geometry": pitlane_manual,
            "raw": pitlane_raw,
            "surface": surface,
            "transformB": {
                "raw": pitlane_transform_b_raw,
                "surface": surface_transform_b,
                "spatialValidation": spatial_validation_transform_b,
            },
            "runtimeChanged": False,
            "note": "Legacy/debug fallback only; hidden from the default PitLane Debug view.",
        },
        "pitlaneSurface": surface,
        "pitlaneRaw": pitlane_raw,
        "pitlaneTrimmedManual": pitlane_manual,
        "selectedCandidate": selected_candidate,
        "trimCandidates": trim_candidates,
        "pitlaneTransformB": {
            "transformUsed": "mapX=worldX,mapY=worldZ",
            "debugOnly": True,
            "runtimeChanged": False,
            "readyForRuntimeIntegration": False,
            "surface": surface_transform_b,
            "raw": pitlane_transform_b_raw,
            "trimCandidates": trim_candidates_transform_b,
            "highlightedCandidate": transform_b_candidate_by_name.get("candidate_05_05"),
            "spatialValidation": spatial_validation_transform_b,
            "regenerationReport": regeneration_report_transform_b,
        },
        "pitExitAnalysis": _normalize_debug_points_in_dict(
            pit_exit_analysis,
            (),
        ),
        "mainTrackExitZoneCandidate": _normalize_debug_points_in_dict(
            maintrack_exit_candidate,
            ("originalSegment", "candidateSegment"),
        ),
        "pitExitTransitionGeometry": _normalize_debug_points_in_dict(
            pit_exit_transition,
            ("centerline", "controlPoints"),
        ),
        "entryExitBreaksCombinedAnalysis": entry_exit_breaks,
        "mainTrackEntryZoneCandidate": _normalize_maintrack_candidate(maintrack_entry_candidate),
        "mainTrackExitZoneCandidateV2": _normalize_maintrack_candidate(maintrack_exit_candidate_v2),
        "pitEntryTransitionCandidates": _normalize_transition_candidates(pit_entry_transition_candidates),
        "pitExitTransitionCandidatesV2": _normalize_transition_candidates(pit_exit_transition_candidates_v2),
        "entryExitBreaksFinalReport": entry_exit_breaks_final_report,
        "validationMetadata": metadata,
        "bounds": _bounds_from_points(all_bounds_points),
        "exports": exports,
    }
