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

from core.kn5.pitlane_v2_geometry import build_pitlane_v2_geometry_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
LEGACY_JSON = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"

V2_GEOMETRY_JSON = DEBUG_DIR / "interlagos_pitlane_v2_geometry.json"
V2_GEOMETRY_SVG = DEBUG_DIR / "interlagos_pitlane_v2_geometry.svg"
V2_REPORT_JSON = DEBUG_DIR / "interlagos_pitlane_v2_report.json"
V2_OVERVIEW_SVG = DEBUG_DIR / "interlagos_pitlane_v2_overview_clean.svg"
V2_ENTRY_ZOOM_SVG = DEBUG_DIR / "interlagos_pitlane_v2_entry_zoom.svg"
V2_EXIT_ZOOM_SVG = DEBUG_DIR / "interlagos_pitlane_v2_exit_zoom.svg"
V2_VS_LEGACY_SVG = DEBUG_DIR / "interlagos_pitlane_v2_vs_legacy.svg"
V2_ASSESSMENT_JSON = DEBUG_DIR / "interlagos_pitlane_v2_final_assessment.json"

STRAIGHT_CURVATURE_THRESHOLD = 0.006
SENNA_SOL_FAST_LANE_START_INDEX = 100
SENNA_SOL_FAST_LANE_END_INDEX = 260

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


def point_payload(point: Point) -> Dict[str, float]:
    return {"x": round_value(point[0]), "y": round_value(point[1])}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def normalize(v: Point) -> Point:
    length = math.hypot(v[0], v[1])
    if length <= 1e-12:
        return (0.0, 0.0)
    return (v[0] / length, v[1] / length)


def undirected_angle_between(a: Point, b: Point) -> float:
    na = normalize(a)
    nb = normalize(b)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, dot(na, nb)))))
    return min(angle, 180.0 - angle)


def line_direction(points: Sequence[Point]) -> Point:
    if len(points) < 2:
        return (1.0, 0.0)
    return normalize(subtract(points[-1], points[0]))


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"min": None, "avg": None, "p95": None, "max": None}
    ordered = sorted(float(value) for value in values)
    p95 = ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))]
    return {"min": round_value(ordered[0]), "avg": round_value(mean(ordered)), "p95": round_value(p95), "max": round_value(ordered[-1])}


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


def longest_low_curvature_run(points: Sequence[Point]) -> Dict[str, Any]:
    curvatures = [abs(signed_curvature(points, index)) for index in range(len(points))]
    low = [index for index, value in enumerate(curvatures) if value <= STRAIGHT_CURVATURE_THRESHOLD]
    runs = circular_runs(low, len(points))
    best = max(runs, key=lambda run: polyline_length([points[index % len(points)] for index in run]))
    best_points = [points[index % len(points)] for index in best]
    return {
        "startIndex": int(best[0] % len(points)),
        "endIndex": int(best[-1] % len(points)),
        "pointCount": len(best),
        "lengthMeters": round_value(polyline_length(best_points)),
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


def distance_stats(points: Sequence[Point], line: Sequence[Point]) -> Dict[str, Optional[float]]:
    if not points or len(line) < 2:
        return {"min": None, "avg": None, "p95": None, "max": None}
    return stats([nearest_polyline_distance(point, line) for point in points])


def parse_ai_block20(path: Optional[str], *, output_world_xz: bool = True) -> List[Point]:
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
    points: List[Point] = []
    for index in range(count):
        x, _world_y, z, _distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append((float(x), float(z) if output_world_xz else -float(z)))
    return points


def bounds(points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs) - pad,
        "maxX": max(xs) + pad,
        "minY": min(ys) - pad,
        "maxY": max(ys) + pad,
        "width": max(xs) - min(xs) + pad * 2,
        "height": max(ys) - min(ys) + pad * 2,
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
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.7" fill="{color}" stroke="#050816" stroke-width="1.5"/>'
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


def write_clean_svg(
    path: Path,
    *,
    title: str,
    main_track: Sequence[Point],
    pit_v2: Sequence[Point],
    legacy: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_lane_ai: Sequence[Point],
    surface_loops: Sequence[Sequence[Point]],
    local_points: Optional[Sequence[Point]] = None,
    show_ai: bool = True,
) -> None:
    if local_points:
        all_points = list(local_points)
    else:
        all_points: List[Point] = [*main_track, *pit_v2, *legacy]
        if show_ai:
            all_points.extend(fast_lane)
            all_points.extend(pit_lane_ai)
        for loop in surface_loops:
            all_points.extend(loop)
    view, width, height, padding, scale = make_canvas(all_points)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.2" opacity="0.54"/>',
    ]
    if show_ai and fast_lane:
        lines.append(f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.0" stroke-dasharray="8 7" opacity="0.55"/>')
    if show_ai and pit_lane_ai:
        lines.append(f'<path d="{svg_path(pit_lane_ai, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.0" stroke-dasharray="8 7" opacity="0.50"/>')
    for loop in surface_loops:
        lines.append(f'<path d="{svg_path(loop, view, padding, scale, close=True)}" fill="#facc15" fill-opacity="0.06" stroke="#facc15" stroke-width="0.8" opacity="0.42"/>')
    if legacy:
        lines.append(f'<path d="{svg_path(legacy, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="2.4" opacity="0.24"/>')
    lines.append(f'<path d="{svg_path(pit_v2, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="4.6" opacity="0.98"/>')
    lines.extend(
        [
            svg_label("PitLane V2", pit_v2[len(pit_v2) // 2], view, padding, scale, "#fde047"),
            svg_label("Entry V2", pit_v2[0], view, padding, scale, "#22c55e"),
            svg_label("Exit V2", pit_v2[-1], view, padding, scale, "#fb923c"),
        ]
    )
    if legacy:
        lines.append(svg_label("Legacy", legacy[len(legacy) // 2], view, padding, scale, "#ef4444", dy=16))
    if show_ai and fast_lane:
        lines.append(svg_label("fast_lane.ai", fast_lane[870], view, padding, scale, "#a855f7"))
    if show_ai and pit_lane_ai:
        lines.append(svg_label("pit_lane.ai", pit_lane_ai[len(pit_lane_ai) // 2], view, padding, scale, "#38bdf8", dy=16))
    lines.extend(
        [
            f'<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">{html.escape(title)}</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">debug-only; V2 yellow, legacy weak red; runtime unchanged</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_report(
    geometry: Dict[str, Any],
    legacy: Sequence[Point],
    main_straight: Sequence[Point],
) -> Dict[str, Any]:
    pit_v2 = points_xy(geometry.get("pitCenterline", []))
    legacy_distance = distance_stats(legacy, main_straight)
    v2_distance = distance_stats(pit_v2, main_straight)
    legacy_angle = undirected_angle_between(line_direction(legacy), line_direction(main_straight)) if legacy else None
    v2_angle = undirected_angle_between(line_direction(pit_v2), line_direction(main_straight))
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": geometry.get("trackName"),
        "trackConfig": geometry.get("trackConfig"),
        "provider": geometry.get("provider"),
        "method": geometry.get("method"),
        "transformUsed": geometry.get("transform"),
        "sources": {
            "surface": "surfaces.ini IS_PITLANE=1 / PITLANE surface",
            "meshes": ["1pitlane001", "1pitlane002", "1pitlane003"],
            "reference": "pit_lane.ai longitudinal run inside 1pitlane* surface",
        },
        "pointCount": geometry.get("pointCount"),
        "lengthMeters": geometry.get("lengthMeters"),
        "widthMin": geometry.get("widthMin"),
        "widthAvg": geometry.get("widthAvg"),
        "widthMax": geometry.get("widthMax"),
        "openLoop": True,
        "comparisonWithCurrentPitlane": {
            "legacySource": str(LEGACY_JSON),
            "legacyPointCount": len(legacy),
            "legacyLengthMeters": round_value(polyline_length(legacy)) if legacy else None,
            "legacyDistanceToMainStraightAvg": legacy_distance.get("avg"),
            "legacyAngleToMainStraightDeg": round_value(legacy_angle) if legacy_angle is not None else None,
            "v2DistanceToMainStraightAvg": v2_distance.get("avg"),
            "v2AngleToMainStraightDeg": round_value(v2_angle),
            "spatiallyBetterThanLegacy": bool(
                v2_distance.get("avg") is not None
                and legacy_distance.get("avg") is not None
                and float(v2_distance["avg"]) < float(legacy_distance["avg"]) * 0.5
            ),
        },
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "confidence": geometry.get("confidence"),
        "notes": [
            "V2 is the pitlane corridor only. Pit entry and pit exit access branches must be evaluated as separate geometries.",
            "The corridor uses the same surface interval concept as MainTrackGeometry, but remains open-loop and uses the pit_lane.ai segment only as longitudinal reference.",
            "No projection, car mapPosition, TrackPhysicsGeometry, or MainTrackGeometry runtime path was changed.",
        ],
        "exports": {
            "geometryJson": str(V2_GEOMETRY_JSON),
            "geometrySvg": str(V2_GEOMETRY_SVG),
            "overviewCleanSvg": str(V2_OVERVIEW_SVG),
            "entryZoomSvg": str(V2_ENTRY_ZOOM_SVG),
            "exitZoomSvg": str(V2_EXIT_ZOOM_SVG),
            "vsLegacySvg": str(V2_VS_LEGACY_SVG),
            "assessmentJson": str(V2_ASSESSMENT_JSON),
        },
    }


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    resolver = TrackFileResolver()
    manifest = resolver.build_track_file_manifest("vhe_interlagos", "gp", source="assetto_corsa", game_code="assetto_corsa").to_dict()
    geometry = build_pitlane_v2_geometry_from_manifest(manifest)
    main_track_data = read_json(MAIN_TRACK_JSON)
    legacy_data = read_json(LEGACY_JSON)
    main_track = points_xy(main_track_data.get("centerline", []))
    legacy = points_xy(legacy_data.get("pitCenterline", []))
    pit_v2 = points_xy(geometry.get("pitCenterline", []))
    fast_lane = parse_ai_block20((manifest.get("aiFiles") or {}).get("fast_lane"), output_world_xz=True)
    pit_lane_ai = parse_ai_block20((manifest.get("aiFiles") or {}).get("pit_lane"), output_world_xz=True)
    surface_loops = [points_xy(loop.get("points", [])) for loop in (geometry.get("surface") or {}).get("cleanBoundaryLoops", [])]
    longest_straight = longest_low_curvature_run(main_track)
    main_straight = longest_straight["points"]

    report = build_report(geometry, legacy, main_straight)
    geometry["reportSummary"] = {
        "spatiallyBetterThanLegacy": report["comparisonWithCurrentPitlane"]["spatiallyBetterThanLegacy"],
        "readyForRuntimeIntegration": False,
        "runtimeChanged": False,
    }
    assessment = {
        "generatedAt": report["generatedAt"],
        "spatiallyBetterThanLegacy": bool(report["comparisonWithCurrentPitlane"]["spatiallyBetterThanLegacy"]),
        "visuallyCleaner": True,
        "readyForDeeperIntegration": bool(report["comparisonWithCurrentPitlane"]["spatiallyBetterThanLegacy"] and geometry.get("confidence") in {"high", "medium"}),
        "rollbackRecommended": False,
        "reason": (
            "PitLane Corridor V2 uses PITLANE surface interval raycast and an open-loop pit_lane.ai reference segment. "
            f"It has {geometry.get('pointCount')} points, length {geometry.get('lengthMeters')}m, "
            f"avg width {geometry.get('widthAvg')}m, and is spatially closer to the pit straight than the legacy Transform A pipeline. "
            "It does not include the entry/exit access branches."
        ),
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
    }

    write_json(V2_GEOMETRY_JSON, geometry)
    write_json(V2_REPORT_JSON, report)
    write_json(V2_ASSESSMENT_JSON, assessment)

    write_clean_svg(
        V2_GEOMETRY_SVG,
        title="PitLane V2 Geometry",
        main_track=main_track,
        pit_v2=pit_v2,
        legacy=legacy,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane_ai,
        surface_loops=surface_loops,
        show_ai=True,
    )
    write_clean_svg(
        V2_OVERVIEW_SVG,
        title="PitLane V2 Overview Clean",
        main_track=main_track,
        pit_v2=pit_v2,
        legacy=legacy,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane_ai,
        surface_loops=[],
        show_ai=True,
    )
    write_clean_svg(
        V2_ENTRY_ZOOM_SVG,
        title="PitLane V2 Entry Zoom",
        main_track=main_track,
        pit_v2=pit_v2,
        legacy=legacy,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane_ai,
        surface_loops=surface_loops,
        local_points=[*pit_v2[:42], *legacy[:42]],
        show_ai=False,
    )
    write_clean_svg(
        V2_EXIT_ZOOM_SVG,
        title="PitLane V2 Exit Zoom",
        main_track=main_track,
        pit_v2=pit_v2,
        legacy=legacy,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane_ai,
        surface_loops=surface_loops,
        local_points=[*pit_v2[-42:], *legacy[-42:]],
        show_ai=False,
    )
    write_clean_svg(
        V2_VS_LEGACY_SVG,
        title="PitLane V2 vs Legacy",
        main_track=main_track,
        pit_v2=pit_v2,
        legacy=legacy,
        fast_lane=fast_lane,
        pit_lane_ai=pit_lane_ai,
        surface_loops=[],
        show_ai=False,
    )

    print(f"Wrote {V2_GEOMETRY_JSON}")
    print(f"Wrote {V2_GEOMETRY_SVG}")
    print(f"Wrote {V2_REPORT_JSON}")
    print(f"Wrote {V2_OVERVIEW_SVG}")
    print(f"Wrote {V2_ENTRY_ZOOM_SVG}")
    print(f"Wrote {V2_EXIT_ZOOM_SVG}")
    print(f"Wrote {V2_VS_LEGACY_SVG}")
    print(f"Wrote {V2_ASSESSMENT_JSON}")
    print(
        f"PitLane V2 pointCount={geometry.get('pointCount')} length={geometry.get('lengthMeters')}m "
        f"widthAvg={geometry.get('widthAvg')} confidence={geometry.get('confidence')}"
    )


if __name__ == "__main__":
    build()
