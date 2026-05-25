import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..kn5.track_edges_from_surface import parse_fast_lane_ai


ALIGNMENT_FILE = "interlagos_pit_lane_ai_alignment.json"
ALIGNMENT_SVG_FILE = "interlagos_pit_lane_ai_alignment.svg"
CONNECTION_POINTS_FILE = "interlagos_pit_lane_ai_connection_points.json"
CONNECTION_POINTS_SVG_FILE = "interlagos_pit_lane_ai_connection_points.svg"
PIT_ACCESS_FILE = "interlagos_pit_access_from_pit_lane_ai.json"
PIT_ACCESS_SVG_FILE = "interlagos_pit_access_from_pit_lane_ai.svg"
REPORT_FILE = "interlagos_pit_lane_ai_visual_integration_report.json"

PIT_VISUAL_NAME = "InterlagosPitLaneAiVisualIntegration"
CORRIDOR_WIDTH_M = 7.5
EXIT_MERGE_FINAL_WIDTH_M = 0.75


Point = Tuple[float, float]


def load_pit_visual_geometry(repo_root: Path) -> Optional[Dict[str, Any]]:
    path = repo_root / "data" / "debug" / PIT_ACCESS_FILE
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("visualGeometry")


def build_pit_lane_ai_visual_integration(repo_root: Path, output_dir: Path) -> Dict[str, Any]:
    main_path = repo_root / "data" / "debug" / "interlagos_track_only_fixed_geometry.json"
    main = json.loads(main_path.read_text(encoding="utf-8"))
    ai_paths = _resolve_ai_paths(repo_root)

    fast_lane = parse_fast_lane_ai(ai_paths["fast_lane"])
    pit_lane = parse_fast_lane_ai(ai_paths["pit_lane"])
    fast_points = [_point_from_ai(point) for point in fast_lane.get("points", [])]
    pit_points = [_point_from_ai(point) for point in pit_lane.get("points", [])]

    main_center = [_point_from_world(point) for point in main.get("centerline", [])]
    main_left = [_point_from_world(point) for point in main.get("boundsLeft", main.get("left_edge", []))]
    main_right = [_point_from_world(point) for point in main.get("boundsRight", main.get("right_edge", []))]
    main_widths = [float(value) for value in main.get("localWidth", [])]
    main_distances = _distances_open(main_center)

    if not fast_points or not pit_points or not main_center or not main_widths:
        raise ValueError("Interlagos pit lane AI integration requires main geometry, fast_lane.ai and pit_lane.ai")

    pit_to_main = _nearest_main_samples(pit_points, main_center, main_widths, main_distances)
    fast_to_main = _nearest_main_samples(fast_points, main_center, main_widths, main_distances)
    connection_points = _detect_connection_points(pit_points, pit_to_main)

    entry = _build_offset_geometry(
        "PitEntryAccessGeometry",
        pit_points[connection_points["pitEntryDivergencePoint"]["pitLaneIndex"] : connection_points["pitCorridorStartPoint"]["pitLaneIndex"] + 1],
        _smooth_widths(
            len(pit_points[connection_points["pitEntryDivergencePoint"]["pitLaneIndex"] : connection_points["pitCorridorStartPoint"]["pitLaneIndex"] + 1]),
            connection_points["pitEntryDivergencePoint"]["mainTrackWidth"],
            CORRIDOR_WIDTH_M,
        ),
    )
    corridor = _build_offset_geometry(
        "PitLaneCorridorVisualGeometry",
        pit_points[connection_points["pitCorridorStartPoint"]["pitLaneIndex"] : connection_points["pitCorridorEndPoint"]["pitLaneIndex"] + 1],
        [CORRIDOR_WIDTH_M]
        * (connection_points["pitCorridorEndPoint"]["pitLaneIndex"] - connection_points["pitCorridorStartPoint"]["pitLaneIndex"] + 1),
    )
    exit_start_index = connection_points["pitCorridorEndPoint"]["pitLaneIndex"]
    exit_end_index = connection_points["pitExitMergePoint"]["pitLaneIndex"]
    exit_segment = pit_points[exit_start_index : exit_end_index + 1]
    exit_widths, exit_merge_start_index = _exit_access_widths(
        exit_segment,
        pit_to_main[exit_start_index : exit_end_index + 1],
        absolute_start_index=exit_start_index,
    )
    connection_points["pitExitMergeStartPoint"] = _connection_payload(
        "pitExitMergeStartPoint",
        exit_merge_start_index,
        pit_points,
        pit_to_main,
    )
    exit_access = _build_offset_geometry(
        "PitExitAccessGeometry",
        exit_segment,
        exit_widths,
    )

    geometries = {
        "PitEntryAccessGeometry": entry,
        "PitLaneCorridorVisualGeometry": corridor,
        "PitExitAccessGeometry": exit_access,
    }
    validation = {
        "pitLaneAiLoaded": pit_lane.get("pointCount", 0) > 0,
        "pitLaneAiUsedAsGuideOnly": True,
        "pitLaneAiUsedAsPhysicalGeometry": False,
        "entryAccessGenerated": len(entry["centerline"]["x"]) > 1,
        "pitCorridorGenerated": len(corridor["centerline"]["x"]) > 1,
        "exitAccessGenerated": len(exit_access["centerline"]["x"]) > 1,
        "mainTrackDeformed": False,
        "pitExitKeptAsSeparateBranch": True,
        "mainTrackBoundaryIncludesPitExit": False,
        "exitMergeTapered": True,
        "boundaryLoopsUsedAsTrack": False,
        "rawTrianglesRendered": False,
        "holesRemaining": 0 if _max_visual_segment(geometries) <= 30.0 else 1,
        "linesCrossingTrack": _visual_geometries_self_intersect(geometries),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
    }
    metrics = {
        "fastLaneMainDistanceAvg": round(_avg([sample["distanceToMain"] for sample in fast_to_main]), 6),
        "fastLaneMainDistanceP95": round(_percentile([sample["distanceToMain"] for sample in fast_to_main], 0.95), 6),
        "pitLaneMainDistanceMin": round(min(sample["distanceToMain"] for sample in pit_to_main), 6),
        "pitLaneMainDistanceAvg": round(_avg([sample["distanceToMain"] for sample in pit_to_main]), 6),
        "pitLaneMainDistanceMax": round(max(sample["distanceToMain"] for sample in pit_to_main), 6),
        "maxVisualSegmentLength": round(_max_visual_segment(geometries), 6),
    }
    visual_geometry = {
        "name": PIT_VISUAL_NAME,
        "projection": "mapX = worldX, mapY = -worldZ",
        "source": "pit_lane.ai guide + MainTrackGeometry width",
        "pitLaneAiUsedAsGuideOnly": True,
        "pitLaneAiUsedAsPhysicalGeometry": False,
        "mainTrackDeformed": False,
        "corridorWidthMeters": CORRIDOR_WIDTH_M,
        "exitMergeFinalWidthMeters": EXIT_MERGE_FINAL_WIDTH_M,
        "pitExitKeptAsSeparateBranch": True,
        "mainTrackBoundaryIncludesPitExit": False,
        "connectionPoints": connection_points,
        "geometries": geometries,
        "validation": validation,
    }
    alignment = {
        "projection": "mapX = worldX, mapY = -worldZ",
        "mainTrackGeometry": main.get("geometryName", main.get("provider")),
        "fastLaneAi": {
            "path": fast_lane.get("path"),
            "pointCount": fast_lane.get("pointCount"),
            "diagnostics": fast_lane.get("diagnostics", []),
        },
        "pitLaneAi": {
            "path": pit_lane.get("path"),
            "pointCount": pit_lane.get("pointCount"),
            "diagnostics": pit_lane.get("diagnostics", []),
        },
        "metrics": metrics,
        "validation": {
            "fastLaneAlignedWithMainTrack": metrics["fastLaneMainDistanceP95"] <= 8.0,
            "pitLanePassesBoxesRegion": metrics["pitLaneMainDistanceMax"] >= 20.0,
            "mapSpaceConversion": "mapX = worldX, mapY = -worldZ",
            "mirroringCorrectionApplied": False,
        },
    }
    connection_payload = {
        "projection": "mapX = worldX, mapY = -worldZ",
        "connectionPoints": connection_points,
        "method": "pit_lane.ai distance/width ratio against MainTrackGeometry",
    }
    access_payload = {
        "visualGeometry": visual_geometry,
        "fastLaneAi": _polyline_payload(fast_points),
        "pitLaneAi": _polyline_payload(pit_points),
    }
    report = {
        "name": PIT_VISUAL_NAME,
        "generatedAt": datetime.utcnow().isoformat(),
        "validation": validation,
        "metrics": metrics,
        "connectionPoints": connection_points,
        "notes": [
            "fast_lane.ai remains the longitudinal guide for MainTrackGeometry.",
            "pit_lane.ai is used only as a visual guide for pit access and corridor centerlines.",
            "Pit exit is kept as a separate branch and tapers into a short merge; it is not used as a MainTrack edge.",
            "ProjectionEngine, mapPosition, lateralOffset and physics geometry are unchanged.",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ALIGNMENT_FILE).write_text(json.dumps(alignment, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / CONNECTION_POINTS_FILE).write_text(json.dumps(connection_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / PIT_ACCESS_FILE).write_text(json.dumps(access_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / REPORT_FILE).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    (output_dir / ALIGNMENT_SVG_FILE).write_text(
        _build_svg(main_left, main_right, fast_points, pit_points, geometries, connection_points, mode="alignment"),
        encoding="utf-8",
    )
    (output_dir / CONNECTION_POINTS_SVG_FILE).write_text(
        _build_svg(main_left, main_right, fast_points, pit_points, geometries, connection_points, mode="points"),
        encoding="utf-8",
    )
    (output_dir / PIT_ACCESS_SVG_FILE).write_text(
        _build_svg(main_left, main_right, fast_points, pit_points, geometries, connection_points, mode="access"),
        encoding="utf-8",
    )
    return {"alignment": alignment, "connectionPoints": connection_payload, "access": access_payload, "report": report}


def _resolve_ai_paths(repo_root: Path) -> Dict[str, str]:
    edge_debug = repo_root / "data" / "debug" / "track_edges_interval_raycast_vhe_interlagos.json"
    fast_path = None
    if edge_debug.exists():
        fast_path = json.loads(edge_debug.read_text(encoding="utf-8")).get("fastLaneAi")
    if not fast_path:
        fast_path = r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\gp\ai\fast_lane.ai"
    pit_path = str(Path(fast_path).with_name("pit_lane.ai"))
    return {"fast_lane": str(fast_path), "pit_lane": pit_path}


def _point_from_ai(point: Dict[str, Any]) -> Point:
    x, y = point["mapPosition"]
    return float(x), float(y)


def _point_from_world(point: Dict[str, Any]) -> Point:
    return float(point["x"]), -float(point.get("z", point.get("y", 0.0)))


def _distances_open(points: Sequence[Point]) -> List[float]:
    distances = [0.0]
    for index in range(1, len(points)):
        distances.append(distances[-1] + _distance(points[index - 1], points[index]))
    return distances


def _nearest_main_samples(
    points: Sequence[Point],
    main_center: Sequence[Point],
    main_widths: Sequence[float],
    main_distances: Sequence[float],
) -> List[Dict[str, Any]]:
    samples = []
    for point in points:
        best_distance_sq = float("inf")
        best_index = 0
        for index, main_point in enumerate(main_center):
            distance_sq = (point[0] - main_point[0]) ** 2 + (point[1] - main_point[1]) ** 2
            if distance_sq < best_distance_sq:
                best_distance_sq = distance_sq
                best_index = index
        distance = math.sqrt(best_distance_sq)
        half_width = max(float(main_widths[best_index]) * 0.5, 1e-6)
        samples.append(
            {
                "distanceToMain": distance,
                "nearestMainIndex": best_index,
                "nearestMainDistance": float(main_distances[best_index]),
                "mainTrackWidth": float(main_widths[best_index]),
                "distanceToHalfWidthRatio": distance / half_width,
            }
        )
    return samples


def _detect_connection_points(pit_points: Sequence[Point], pit_to_main: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    divergence = _first_stable_index(pit_to_main, 80, lambda sample: sample["distanceToHalfWidthRatio"] > 1.15, 8)
    corridor_start = _first_stable_index(
        pit_to_main,
        divergence,
        lambda sample: sample["distanceToMain"] > 12.0 and sample["distanceToHalfWidthRatio"] > 1.8,
        16,
    )
    exit_merge = _first_stable_index(
        pit_to_main,
        corridor_start,
        lambda sample: sample["distanceToMain"] <= 1.8 and sample["nearestMainDistance"] >= 1120.0,
        24,
    )
    corridor_end = _last_stable_index(
        pit_to_main,
        corridor_start,
        exit_merge,
        lambda sample: sample["distanceToMain"] > 12.0 and sample["distanceToHalfWidthRatio"] > 1.8,
        12,
    )

    return {
        "pitEntryDivergencePoint": _connection_payload("pitEntryDivergencePoint", divergence, pit_points, pit_to_main),
        "pitCorridorStartPoint": _connection_payload("pitCorridorStartPoint", corridor_start, pit_points, pit_to_main),
        "pitCorridorEndPoint": _connection_payload("pitCorridorEndPoint", corridor_end, pit_points, pit_to_main),
        "pitExitMergePoint": _connection_payload("pitExitMergePoint", exit_merge, pit_points, pit_to_main),
    }


def _first_stable_index(samples: Sequence[Dict[str, Any]], start: int, predicate, run_length: int) -> int:
    for index in range(max(0, start), max(0, len(samples) - run_length)):
        if all(predicate(sample) for sample in samples[index : index + run_length]):
            return index
    return max(0, min(len(samples) - 1, start))


def _last_stable_index(samples: Sequence[Dict[str, Any]], start: int, end: int, predicate, run_length: int) -> int:
    for index in range(max(start, end - run_length), start - 1, -1):
        window_start = max(start, index - run_length + 1)
        if all(predicate(sample) for sample in samples[window_start : index + 1]):
            return index
    return max(start, end - 1)


def _connection_payload(name: str, index: int, pit_points: Sequence[Point], pit_to_main: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    sample = pit_to_main[index]
    return {
        "name": name,
        "pitLaneIndex": int(index),
        "position": _xy_payload(pit_points[index]),
        "nearestMainIndex": int(sample["nearestMainIndex"]),
        "nearestMainDistance": round(float(sample["nearestMainDistance"]), 6),
        "distanceToMain": round(float(sample["distanceToMain"]), 6),
        "mainTrackWidth": round(float(sample["mainTrackWidth"]), 6),
        "distanceToHalfWidthRatio": round(float(sample["distanceToHalfWidthRatio"]), 6),
    }


def _build_offset_geometry(name: str, centerline: Sequence[Point], widths: Sequence[float]) -> Dict[str, Any]:
    normals = _normals_for_open_polyline(centerline)
    left = []
    right = []
    for point, normal, width in zip(centerline, normals, widths):
        half = float(width) * 0.5
        left.append((point[0] + normal[0] * half, point[1] + normal[1] * half))
        right.append((point[0] - normal[0] * half, point[1] - normal[1] * half))
    polygon = list(left) + list(reversed(right))
    return {
        "name": name,
        "centerline": _polyline_payload(centerline),
        "leftEdge": _polyline_payload(left),
        "rightEdge": _polyline_payload(right),
        "width": [round(float(value), 6) for value in widths],
        "polygon": _polyline_payload(polygon),
        "selfIntersects": _polygon_self_intersects(polygon),
    }


def _normals_for_open_polyline(points: Sequence[Point]) -> List[Point]:
    normals = []
    count = len(points)
    for index in range(count):
        if index == 0:
            prev_point, next_point = points[index], points[index + 1]
        elif index == count - 1:
            prev_point, next_point = points[index - 1], points[index]
        else:
            prev_point, next_point = points[index - 1], points[index + 1]
        dx = next_point[0] - prev_point[0]
        dy = next_point[1] - prev_point[1]
        length = math.hypot(dx, dy) or 1.0
        normals.append((-dy / length, dx / length))
    return normals


def _smooth_widths(count: int, start_width: float, end_width: float) -> List[float]:
    if count <= 1:
        return [round(float(end_width), 6)]
    widths = []
    for index in range(count):
        t = index / (count - 1)
        smooth = t * t * (3.0 - 2.0 * t)
        widths.append(float(start_width) + (float(end_width) - float(start_width)) * smooth)
    return widths


def _exit_access_widths(
    centerline: Sequence[Point],
    main_samples: Sequence[Dict[str, Any]],
    *,
    absolute_start_index: int,
) -> Tuple[List[float], int]:
    if not centerline:
        return [], absolute_start_index

    merge_start_relative = max(0, len(centerline) - 1)
    stable_count = 12
    for index in range(0, max(0, len(main_samples) - stable_count)):
        window = main_samples[index : index + stable_count]
        if all(sample["distanceToMain"] <= 2.2 and sample["nearestMainDistance"] >= 1040.0 for sample in window):
            merge_start_relative = index
            break

    widths: List[float] = []
    for index in range(len(centerline)):
        if index < merge_start_relative:
            widths.append(CORRIDOR_WIDTH_M)
            continue
        t = (index - merge_start_relative) / max(1, len(centerline) - 1 - merge_start_relative)
        smooth = t * t * (3.0 - 2.0 * t)
        widths.append(CORRIDOR_WIDTH_M + (EXIT_MERGE_FINAL_WIDTH_M - CORRIDOR_WIDTH_M) * smooth)
    return widths, absolute_start_index + merge_start_relative


def _polyline_payload(points: Sequence[Point]) -> Dict[str, Any]:
    return {
        "points": [[round(point[0], 6), round(point[1], 6)] for point in points],
        "x": [round(point[0], 6) for point in points],
        "y": [round(point[1], 6) for point in points],
    }


def _xy_payload(point: Point) -> Dict[str, float]:
    return {"x": round(point[0], 6), "y": round(point[1], 6)}


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _avg(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def _max_visual_segment(geometries: Dict[str, Dict[str, Any]]) -> float:
    max_segment = 0.0
    for geometry in geometries.values():
        points = [tuple(point) for point in geometry["centerline"]["points"]]
        for index in range(1, len(points)):
            max_segment = max(max_segment, _distance(points[index - 1], points[index]))
    return max_segment


def _visual_geometries_self_intersect(geometries: Dict[str, Dict[str, Any]]) -> bool:
    return any(bool(geometry.get("selfIntersects")) for geometry in geometries.values())


def _polygon_self_intersects(points: Sequence[Point]) -> bool:
    closed = list(points) + [points[0]]
    segments = [(closed[index], closed[index + 1]) for index in range(len(closed) - 1)]
    for i, first in enumerate(segments):
        first_bounds = _segment_bounds(first[0], first[1])
        for j in range(i + 1, len(segments)):
            if abs(i - j) <= 1 or (i == 0 and j == len(segments) - 1):
                continue
            if not _bounds_overlap(first_bounds, _segment_bounds(segments[j][0], segments[j][1])):
                continue
            if _segments_intersect(first[0], first[1], segments[j][0], segments[j][1]):
                return True
    return False


def _segment_bounds(a: Point, b: Point) -> Tuple[float, float, float, float]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def _bounds_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def overlaps(p: Point, q: Point, r: Point) -> bool:
        return (
            min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
            and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
        )

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 * o2 < -1e-9 and o3 * o4 < -1e-9:
        return True
    if abs(o1) <= 1e-9 and overlaps(a, c, b):
        return True
    if abs(o2) <= 1e-9 and overlaps(a, d, b):
        return True
    if abs(o3) <= 1e-9 and overlaps(c, a, d):
        return True
    if abs(o4) <= 1e-9 and overlaps(c, b, d):
        return True
    return False


def _build_svg(
    main_left: Sequence[Point],
    main_right: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_lane: Sequence[Point],
    geometries: Dict[str, Dict[str, Any]],
    connection_points: Dict[str, Dict[str, Any]],
    *,
    mode: str,
) -> str:
    width = 1400
    height = 1000
    margin = 55
    all_points: List[Point] = [*main_left, *main_right, *fast_lane, *pit_lane]
    for geometry in geometries.values():
        all_points.extend((float(x), float(y)) for x, y in geometry["polygon"]["points"])
    bounds = _bounds_payload(all_points)
    scale = min((width - margin * 2) / bounds["width"], (height - margin * 2) / bounds["height"])

    def tx(point: Point) -> Tuple[float, float]:
        x = margin + (point[0] - bounds["minX"]) * scale
        y = height - margin - (point[1] - bounds["minY"]) * scale
        return x, y

    def path(points: Sequence[Point], close: bool = False) -> str:
        if not points:
            return ""
        first = tx(points[0])
        parts = [f"M {first[0]:.2f} {first[1]:.2f}"]
        for point in points[1:]:
            x, y = tx(point)
            parts.append(f"L {x:.2f} {y:.2f}")
        if close:
            parts.append("Z")
        return " ".join(parts)

    main_poly = list(main_left) + list(reversed(main_right))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#070a12"/>',
        f'<text x="24" y="34" fill="#d7e7ef" font-family="Segoe UI, Arial" font-size="18">{PIT_VISUAL_NAME}</text>',
        '<text x="24" y="58" fill="#8fa3ad" font-family="Segoe UI, Arial" font-size="12">MainTrack gray / fast_lane purple dashed / pit_lane blue dashed / entry green / corridor yellow / exit orange</text>',
        f'<path d="{path(main_poly, close=True)}" fill="#6b7280" fill-opacity="0.42" stroke="#d1d5db" stroke-opacity="0.75" stroke-width="1.4"/>',
        f'<path d="{path(fast_lane, close=False)}" fill="none" stroke="#c084fc" stroke-width="1.3" stroke-dasharray="7 7" stroke-opacity="0.9"/>',
        f'<path d="{path(pit_lane, close=False)}" fill="none" stroke="#38bdf8" stroke-width="1.4" stroke-dasharray="6 6" stroke-opacity="0.9"/>',
    ]
    if mode == "access":
        style = {
            "PitEntryAccessGeometry": ("#22c55e", 0.56),
            "PitLaneCorridorVisualGeometry": ("#facc15", 0.54),
            "PitExitAccessGeometry": ("#fb923c", 0.58),
        }
        for name, geometry in geometries.items():
            color, opacity = style[name]
            polygon = [(float(x), float(y)) for x, y in geometry["polygon"]["points"]]
            center = [(float(x), float(y)) for x, y in geometry["centerline"]["points"]]
            parts.append(f'<path d="{path(polygon, close=True)}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="1.8" stroke-opacity="0.95"/>')
            parts.append(f'<path d="{path(center)}" fill="none" stroke="#111827" stroke-width="0.9" stroke-opacity="0.62"/>')

    if mode in {"points", "access"}:
        colors = {
            "pitEntryDivergencePoint": "#22c55e",
            "pitCorridorStartPoint": "#facc15",
            "pitCorridorEndPoint": "#f97316",
            "pitExitMergePoint": "#fb923c",
        }
        for name, point in connection_points.items():
            x, y = tx((float(point["position"]["x"]), float(point["position"]["y"])))
            color = colors.get(name, "#ffffff")
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}" stroke="#111827" stroke-width="2"/>')
            parts.append(f'<text x="{x + 10:.2f}" y="{y - 8:.2f}" fill="{color}" font-family="Segoe UI, Arial" font-size="13">{name}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _bounds_payload(points: Sequence[Point]) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "minX": min_x,
        "maxX": max_x,
        "minY": min_y,
        "maxY": max_y,
        "width": max(max_x - min_x, 1.0),
        "height": max(max_y - min_y, 1.0),
    }
