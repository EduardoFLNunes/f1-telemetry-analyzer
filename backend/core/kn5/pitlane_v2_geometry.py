from __future__ import annotations

import math
import struct
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .track_edges_from_surface import (
    _TriangleSurfaceIndex,
    _boundary_edges,
    _build_boundary_loops,
    _build_inside_intervals,
    _component_analysis,
    _line_intersections_with_loop_segments,
    _select_inside_interval,
    _segments_from_loops_with_metadata,
    _selected_triangle_indices,
)
from .track_surface_polygon import build_track_surface_polygon_from_manifest


PIT_MESH_NAMES = {"1pitlane001", "1pitlane002", "1pitlane003"}

Point = Tuple[float, float]


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _round_point(point: Sequence[float], digits: int = 6) -> List[float]:
    return [_round(point[0], digits), _round(point[1], digits)]


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def _length(points: Sequence[Sequence[float]]) -> float:
    return sum(_distance(points[index - 1], points[index]) for index in range(1, len(points)))


def _stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"min": None, "avg": None, "max": None}
    return {"min": _round(min(values)), "avg": _round(mean(values)), "max": _round(max(values))}


def _bounds(points: Sequence[Sequence[float]]) -> Dict[str, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {
        "minX": _round(min(xs)),
        "maxX": _round(max(xs)),
        "minY": _round(min(ys)),
        "maxY": _round(max(ys)),
        "width": _round(max(xs) - min(xs)),
        "height": _round(max(ys) - min(ys)),
    }


def _triangle_area(vertices: Sequence[Sequence[float]]) -> float:
    a, b, c = vertices
    return abs((float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (float(b[1]) - float(a[1])) * (float(c[0]) - float(a[0]))) * 0.5


def _map_to_world_xz(point: Sequence[float]) -> Dict[str, float]:
    world_z = -float(point[1])
    return {"x": float(point[0]), "y": world_z, "z": world_z}


def _loop_to_world_xz(loop: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in loop.items()
        if key != "points"
    } | {"points": [{"x": float(point[0]), "y": -float(point[1])} for point in loop.get("points", [])]}


def _parse_ai_block20(ai_path: Optional[str], *, map_y_sign: int = -1) -> Dict[str, Any]:
    if not ai_path:
        return {"path": None, "version": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "missing_ai"}]}
    path = Path(ai_path)
    if not path.exists():
        return {"path": str(path), "version": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "missing_ai_file"}]}
    data = path.read_bytes()
    if len(data) < 16:
        return {"path": str(path), "version": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "invalid_ai_file"}]}
    version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points = []
    for index in range(count):
        x, y, z, spline_distance, raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append(
            {
                "index": index,
                "worldPosition": [_round(x), _round(y), _round(z)],
                "mapPosition": [_round(x), _round(float(map_y_sign) * z)],
                "distance": _round(spline_distance),
                "rawIndex": int(raw_index),
            }
        )
    diagnostics = []
    if count != declared_count:
        diagnostics.append({"code": "ai_count_truncated", "declared": int(declared_count), "available": available})
    return {"path": str(path), "version": int(version), "declaredPointCount": int(declared_count), "pointCount": len(points), "points": points, "diagnostics": diagnostics}


def _contiguous_true_runs(flags: Sequence[bool]) -> List[List[int]]:
    runs: List[List[int]] = []
    current: List[int] = []
    for index, flag in enumerate(flags):
        if flag:
            current.append(index)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _open_tangent(points: Sequence[Dict[str, Any]], index: int) -> Point:
    count = len(points)
    if count < 2:
        return (1.0, 0.0)
    if index <= 0:
        a = points[0]["mapPosition"]
        b = points[1]["mapPosition"]
    elif index >= count - 1:
        a = points[count - 2]["mapPosition"]
        b = points[count - 1]["mapPosition"]
    else:
        a = points[index - 1]["mapPosition"]
        b = points[index + 1]["mapPosition"]
    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (1.0, 0.0)
    return (dx / length, dy / length)


def _interpolate_open_samples(samples: List[Dict[str, Any]]) -> int:
    valid_indices = [index for index, sample in enumerate(samples) if sample.get("valid")]
    if not valid_indices:
        return 0
    interpolated = 0
    for index, sample in enumerate(samples):
        if sample.get("valid"):
            continue
        prev_candidates = [valid for valid in valid_indices if valid < index]
        next_candidates = [valid for valid in valid_indices if valid > index]
        if not prev_candidates or not next_candidates:
            continue
        prev_index = prev_candidates[-1]
        next_index = next_candidates[0]
        span = next_index - prev_index
        if span <= 0:
            continue
        alpha = (index - prev_index) / span
        prev_sample = samples[prev_index]
        next_sample = samples[next_index]
        for field in ("leftEdge", "rightEdge", "centerline"):
            a = prev_sample.get(field)
            b = next_sample.get(field)
            if not a or not b:
                continue
            sample[field] = _round_point([float(a[0]) + (float(b[0]) - float(a[0])) * alpha, float(a[1]) + (float(b[1]) - float(a[1])) * alpha])
        if prev_sample.get("localWidth") is not None and next_sample.get("localWidth") is not None:
            sample["localWidth"] = _round(float(prev_sample["localWidth"]) + (float(next_sample["localWidth"]) - float(prev_sample["localWidth"])) * alpha)
        sample["valid"] = bool(sample.get("centerline") and sample.get("leftEdge") and sample.get("rightEdge"))
        sample["interpolated"] = bool(sample["valid"])
        if sample["valid"]:
            interpolated += 1
    return interpolated


def _enforce_orientation(samples: List[Dict[str, Any]]) -> int:
    swapped = 0
    for sample in samples:
        if not sample.get("leftEdge") or not sample.get("rightEdge"):
            continue
        normal = sample["normal"]
        ref = sample["reference"]
        left = sample["leftEdge"]
        right = sample["rightEdge"]
        left_dot = (left[0] - ref[0]) * normal[0] + (left[1] - ref[1]) * normal[1]
        right_dot = (right[0] - ref[0]) * normal[0] + (right[1] - ref[1]) * normal[1]
        if left_dot <= right_dot:
            sample["leftEdge"], sample["rightEdge"] = sample["rightEdge"], sample["leftEdge"]
            swapped += 1
        sample["centerline"] = _round_point(
            [
                (float(sample["leftEdge"][0]) + float(sample["rightEdge"][0])) * 0.5,
                (float(sample["leftEdge"][1]) + float(sample["rightEdge"][1])) * 0.5,
            ]
        )
        sample["localWidth"] = _round(_distance(sample["leftEdge"], sample["rightEdge"]))
    return swapped


def _run_open_interval_raycast(reference_points: Sequence[Dict[str, Any]], clean_loops: Sequence[Dict[str, Any]], surface_index: _TriangleSurfaceIndex) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    loop_segments = _segments_from_loops_with_metadata(clean_loops)
    samples: List[Dict[str, Any]] = []
    if not reference_points or not loop_segments:
        return [], {"valid": 0, "invalid": len(reference_points), "reason": "missing_reference_or_boundary"}
    for local_index, reference in enumerate(reference_points):
        map_position = reference["mapPosition"]
        tx, ty = _open_tangent(reference_points, local_index)
        normal = [-ty, tx]
        intersections = _line_intersections_with_loop_segments(map_position, normal, loop_segments)
        intervals = _build_inside_intervals(map_position, normal, intersections, surface_index)
        selected_interval, correction_reason = _select_inside_interval(intervals)
        valid = selected_interval is not None
        left_edge = right_edge = centerline = None
        local_width = None
        if selected_interval:
            left_t = float(selected_interval["endT"])
            right_t = float(selected_interval["startT"])
            left_edge = [float(map_position[0]) + float(normal[0]) * left_t, float(map_position[1]) + float(normal[1]) * left_t]
            right_edge = [float(map_position[0]) + float(normal[0]) * right_t, float(map_position[1]) + float(normal[1]) * right_t]
            centerline = [(left_edge[0] + right_edge[0]) * 0.5, (left_edge[1] + right_edge[1]) * 0.5]
            local_width = float(selected_interval["width"])
        samples.append(
            {
                "index": local_index,
                "sourceAiIndex": reference.get("index"),
                "sourceAiDistance": reference.get("distance"),
                "reference": _round_point(map_position),
                "tangent": _round_point([tx, ty]),
                "normal": _round_point(normal),
                "leftEdge": _round_point(left_edge) if left_edge else None,
                "rightEdge": _round_point(right_edge) if right_edge else None,
                "centerline": _round_point(centerline) if centerline else None,
                "localWidth": _round(local_width) if local_width is not None and valid else None,
                "valid": bool(valid),
                "interpolated": False,
                "invalidReason": None if valid else correction_reason,
                "allIntersectionCount": len(intersections),
                "intervalCount": len(intervals),
                "selectedIntervalContainsReference": bool(selected_interval and selected_interval.get("containsFastLane")),
                "correctionReason": correction_reason,
            }
        )
    metrics = {"valid": sum(1 for sample in samples if sample["valid"]), "invalid": sum(1 for sample in samples if not sample["valid"])}
    return samples, metrics


def _slice_reference_on_surface(pit_lane_ai: Dict[str, Any], surface_index: _TriangleSurfaceIndex) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    points = pit_lane_ai.get("points", [])
    inside_flags = [surface_index.contains(point["mapPosition"]) for point in points]
    runs = _contiguous_true_runs(inside_flags)
    if not runs:
        return [], {"strategy": "largest_contiguous_inside_surface_run", "insideCount": 0, "selected": None}
    selected = max(runs, key=len)
    return [points[index] for index in selected], {
        "strategy": "largest_contiguous_inside_surface_run",
        "insideCount": sum(1 for flag in inside_flags if flag),
        "runCount": len(runs),
        "selected": {
            "startAiIndex": int(selected[0]),
            "endAiIndex": int(selected[-1]),
            "pointCount": len(selected),
            "startAiDistance": points[selected[0]].get("distance"),
            "endAiDistance": points[selected[-1]].get("distance"),
        },
    }


def _payload_points(samples: Sequence[Dict[str, Any]], field: str) -> List[Dict[str, float]]:
    return [_map_to_world_xz(sample[field]) for sample in samples if sample.get(field)]


def _reference_payload(points: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "index": int(point["index"]),
            "distance": point.get("distance"),
            "mapPosition": {"x": float(point["mapPosition"][0]), "y": float(point["mapPosition"][1])},
            "worldPosition": {"x": float(point["mapPosition"][0]), "y": -float(point["mapPosition"][1])},
        }
        for point in points
    ]


def _sample_payload(samples: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload = []
    cumulative = 0.0
    previous: Optional[Sequence[float]] = None
    for sample in samples:
        center = sample.get("centerline")
        if center and previous:
            cumulative += _distance(previous, center)
        if center:
            previous = center
        payload.append(
            {
                **sample,
                "distance": _round(cumulative),
                "centerlineWorld": _map_to_world_xz(center) if center else None,
                "leftEdgeWorld": _map_to_world_xz(sample["leftEdge"]) if sample.get("leftEdge") else None,
                "rightEdgeWorld": _map_to_world_xz(sample["rightEdge"]) if sample.get("rightEdge") else None,
            }
        )
    return payload


def build_pitlane_v2_geometry_from_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics: List[Dict[str, Any]] = []
    surface = build_track_surface_polygon_from_manifest(manifest, included_surfaces=["PITLANE"])
    all_triangles = surface.get("triangles", [])
    pit_triangles = [
        triangle
        for triangle in all_triangles
        if str(triangle.get("mesh", "")).lower() in PIT_MESH_NAMES
    ]
    if not pit_triangles:
        raise RuntimeError("No 1pitlane001/1pitlane002/1pitlane003 PITLANE triangles found")
    components, triangle_to_component = _component_analysis(pit_triangles)
    selected_component = components[0] if components else None
    selected_component_id = int(selected_component["componentId"]) if selected_component else -1
    selected_indices = _selected_triangle_indices(triangle_to_component, selected_component_id) if selected_component else []
    boundary_edges, node_points = _boundary_edges(pit_triangles, selected_indices)
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    surface_index = _TriangleSurfaceIndex(pit_triangles, selected_indices)

    pit_lane_ai = _parse_ai_block20((manifest.get("aiFiles") or {}).get("pit_lane"), map_y_sign=-1)
    reference_points, reference_selection = _slice_reference_on_surface(pit_lane_ai, surface_index)
    diagnostics.extend(surface.get("diagnostics", []))
    diagnostics.extend(pit_lane_ai.get("diagnostics", []))
    if not reference_points:
        diagnostics.append({"code": "missing_pitlane_reference_run", "message": "pit_lane.ai did not intersect the 1pitlane* surface in internal map-space"})

    samples, raycast_metrics = _run_open_interval_raycast(reference_points, clean_loops, surface_index)
    original_invalid = int(raycast_metrics.get("invalid", 0))
    interpolated = _interpolate_open_samples(samples)
    orientation_swaps = _enforce_orientation(samples)
    valid_samples = [sample for sample in samples if sample.get("valid") and sample.get("centerline")]
    center_map = [sample["centerline"] for sample in valid_samples]
    left_map = [sample["leftEdge"] for sample in valid_samples]
    right_map = [sample["rightEdge"] for sample in valid_samples]
    widths = [float(sample["localWidth"]) for sample in valid_samples if sample.get("localWidth") is not None]
    width_stats = _stats(widths)
    length_meters = _length(center_map)
    centerline_world = _payload_points(valid_samples, "centerline")
    left_edge_world = _payload_points(valid_samples, "leftEdge")
    right_edge_world = _payload_points(valid_samples, "rightEdge")

    metrics = {
        "referencePointCount": len(reference_points),
        "validRaycastSamples": len(valid_samples),
        "invalidRaycastSamples": original_invalid,
        "interpolatedSamples": interpolated,
        "orientationSwaps": orientation_swaps,
        "validRatio": _round(len(valid_samples) / max(1, len(reference_points))),
        "width": width_stats,
        "openLoopEndpointDistance": _round(_distance(center_map[0], center_map[-1])) if len(center_map) > 1 else None,
        "boundaryLoopCount": len(clean_loops),
        "rawBoundaryLoopCount": len(raw_loops),
        "selectedComponentTriangleCount": selected_component.get("triangleCount") if selected_component else 0,
        "selectedComponentArea": selected_component.get("area") if selected_component else 0,
    }
    confidence = "high" if metrics["validRatio"] >= 0.98 and width_stats["avg"] and 4.0 <= width_stats["avg"] <= 20.0 else "medium"

    return {
        "trackName": manifest.get("trackNameFromSharedMemory"),
        "trackConfig": manifest.get("trackConfigFromSharedMemory"),
        "name": "PitLaneCorridorGeometryV2",
        "debugOnly": True,
        "runtimeChanged": False,
        "readyForRuntimeIntegration": False,
        "source": "PITLANE surface 1pitlane001/1pitlane002/1pitlane003 + pit_lane.ai longitudinal reference; corridor only, access branches are separate debug geometries",
        "provider": "pitlane_surface_interval_v2",
        "method": "open_loop_pitlane_surface_interval_raycast",
        "transform": {
            "internalMapSpace": "mapX = worldX, mapY = -worldZ",
            "outputCoordinateSystem": "world_xz",
            "outputEquivalentTransform": "mapX = worldX, mapY = worldZ",
            "sharedWithMainTrack": True,
            "note": "The KN5 surface helper uses the same internal map-space as MainTrackGeometry; output points are converted to world_xz like the main track cache.",
        },
        "openLoop": True,
        "closedLoop": False,
        "pointCount": len(center_map),
        "lengthMeters": _round(length_meters),
        "widthMin": width_stats["min"],
        "widthAvg": width_stats["avg"],
        "widthMax": width_stats["max"],
        "centerline": centerline_world,
        "leftEdge": left_edge_world,
        "rightEdge": right_edge_world,
        "width": widths,
        "pitCenterline": centerline_world,
        "pitLeftEdge": left_edge_world,
        "pitRightEdge": right_edge_world,
        "pitWidth": widths,
        "bounds": _bounds([[point["x"], point["y"]] for point in centerline_world + left_edge_world + right_edge_world]),
        "surface": {
            "source": surface.get("source"),
            "includedSurfaceKeys": ["PITLANE"],
            "sourceMeshNames": sorted(PIT_MESH_NAMES),
            "allPitSurfaceTriangleCount": len(all_triangles),
            "selectedMeshTriangleCount": len(pit_triangles),
            "selectedComponentId": selected_component_id,
            "components": components,
            "cleanBoundaryLoops": [_loop_to_world_xz(loop) for loop in clean_loops],
            "rawBoundaryLoopSummary": [{key: value for key, value in loop.items() if key != "points"} for loop in raw_loops],
        },
        "reference": {
            "aiFile": pit_lane_ai.get("path"),
            "aiUsage": "longitudinal_reference_only_not_authoritative_geometry",
            "selection": reference_selection,
            "points": _reference_payload(reference_points),
        },
        "samples": _sample_payload(valid_samples),
        "metrics": metrics,
        "confidence": confidence,
        "diagnostics": diagnostics,
    }
