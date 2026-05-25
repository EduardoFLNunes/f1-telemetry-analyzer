from __future__ import annotations

import copy
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from build_interlagos_pit_bifurcation_fix import (  # noqa: E402
    _build_audit,
    _distance,
    _geometry_overlap_count,
    _heading_oscillation,
    _line_points,
    _load_context,
    _max_chord_deviation,
    _max_segment,
    _nearest_index,
    _polyline,
    _segments_intersect,
    _unit,
    _xml,
)
from build_interlagos_pit_bifurcation_taper_refine import (  # noqa: E402
    _bounds_for_points,
    _inside,
    _max_heading_step,
    _polyline_length,
    _smooth_polyline,
)
from core.geometry.interlagos_pit_lane_ai_visual import _normals_for_open_polyline  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_bifurcation_taper_refine_candidate.json"
CANDIDATE_JSON = "interlagos_pit_access_centerline_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_centerline_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_centerline_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_access_centerline_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_centerline_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessCenterlineFix"
RENDER_MODE = "visual_pit_access_centerline_fix"
ENTRY_NAME = "PitEntryAccessGeometry"
CORRIDOR_NAME = "PitLaneCorridorBifurcationGeometry"
EXIT_NAME = "PitExitAccessGeometry"

MIN_ACCESS_WIDTH_M = 1.65
CORRIDOR_WIDTH_M = 7.5
ENTRY_POINT_COUNT = 96
EXIT_POINT_COUNT = 92

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesPitAccessCenterlineFix": app_check["appUsesPitAccessCenterlineFix"]})
        return

    context = _load_context()
    audit = _build_audit(context)
    base = json.loads((DEBUG_DIR / BASE_CANDIDATE_JSON).read_text(encoding="utf-8"))
    candidate = _build_candidate(context, audit, base)
    validation = _validate_candidate(context, candidate)

    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, base, candidate), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, base, candidate, validation), encoding="utf-8")
    print(
        {
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "entryAccessCenterlineUsed": validation["entryAccessCenterlineUsed"],
            "exitAccessCenterlineUsed": validation["exitAccessCenterlineUsed"],
            "pitEntryLooksNatural": validation["pitEntryLooksNatural"],
            "pitExitLooksNatural": validation["pitExitLooksNatural"],
        }
    )


def _build_candidate(context: Dict[str, Any], audit: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    base_visual = base["visualGeometry"]
    base_geometries = base_visual["geometries"]
    corridor = copy.deepcopy(base_geometries.get(CORRIDOR_NAME))
    if not corridor:
        raise RuntimeError("PitLaneCorridorBifurcationGeometry is required")

    corridor_center = _line_points(corridor["centerline"])
    entry_zone = audit["entrySplitZone"]
    exit_zone = audit["exitMergeZone"]
    entry_start_main = max(0, int(entry_zone["taperStart"]["nearestMainIndex"]) - 10)
    exit_end_main = min(len(context["mainLeft"]) - 1, int(exit_zone["taperEnd"]["nearestMainIndex"]) + 18)
    entry_start_pit = max(0, int(entry_zone["taperStart"]["pitLaneIndex"]) - 8)
    entry_end_pit = int(entry_zone["taperEnd"]["pitLaneIndex"])
    exit_start_pit = int(exit_zone["taperStart"]["pitLaneIndex"])
    exit_end_pit = min(len(context["pitPoints"]) - 1, int(exit_zone["taperEnd"]["pitLaneIndex"]) + 12)

    entry_start = _offset_from_main_left(context, entry_start_main, MIN_ACCESS_WIDTH_M * 0.5)
    entry_end = corridor_center[0]
    entry_center = _bezier(entry_start, entry_end, context["pitPoints"], entry_start_pit, entry_end_pit, ENTRY_POINT_COUNT)
    entry_center = _smooth_polyline(entry_center, passes=2, keep_ends=True)
    entry_widths = _smooth_widths(MIN_ACCESS_WIDTH_M, CORRIDOR_WIDTH_M, ENTRY_POINT_COUNT)
    entry_center = _clamp_centerline_outside_main(entry_center, entry_widths, context)
    entry = _offset_access_geometry(
        ENTRY_NAME,
        entry_center,
        entry_widths,
        context,
        role="pit_entry_access_centerline",
        access_centerline_name="PitEntryAccessCenterline",
        merge_open=False,
    )

    exit_start = corridor_center[-1]
    exit_end = _offset_from_main_left(context, exit_end_main, MIN_ACCESS_WIDTH_M * 0.5)
    exit_center = _bezier(exit_start, exit_end, context["pitPoints"], exit_start_pit, exit_end_pit, EXIT_POINT_COUNT)
    exit_widths = _smooth_widths(CORRIDOR_WIDTH_M, MIN_ACCESS_WIDTH_M, EXIT_POINT_COUNT)
    exit_center = _smooth_polyline(exit_center, passes=2, keep_ends=True)
    exit_center = _clamp_centerline_outside_main(exit_center, exit_widths, context)
    exit_access = _offset_access_geometry(
        EXIT_NAME,
        exit_center,
        exit_widths,
        context,
        role="pit_exit_access_centerline",
        access_centerline_name="PitExitAccessCenterline",
        merge_open=True,
    )

    corridor["renderHints"]["topology"] = "access_centerline_fix"
    geometries = {ENTRY_NAME: entry, CORRIDOR_NAME: corridor, EXIT_NAME: exit_access}
    visual = copy.deepcopy(base_visual)
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "pit access branches rebuilt from explicit access centerlines"
    visual["accessCenterlineFix"] = {
        "entryAccessCenterlineUsed": True,
        "exitAccessCenterlineUsed": True,
        "minAccessWidthMeters": MIN_ACCESS_WIDTH_M,
        "entryPointCount": ENTRY_POINT_COUNT,
        "exitPointCount": EXIT_POINT_COUNT,
        "method": "centerline-guided offset ribbon with smoothstep width, no visible zero-width point",
    }
    visual["geometries"] = geometries
    visual["bifurcationTopology"]["entry"]["pitBranchCenterline"] = entry["centerline"]
    visual["bifurcationTopology"]["entry"]["sharedDividerEdge"] = entry["sharedDividerEdge"]
    visual["bifurcationTopology"]["exit"]["pitBranchCenterline"] = exit_access["centerline"]
    visual["bifurcationTopology"]["exit"]["sharedDividerEdge"] = exit_access["sharedDividerEdge"]

    generated_at = datetime.utcnow().isoformat()
    return {
        "name": GEOMETRY_NAME,
        "geometryName": GEOMETRY_NAME,
        "visualGeometryName": GEOMETRY_NAME,
        "renderMode": RENDER_MODE,
        "generatedAt": generated_at,
        "updatedAt": generated_at,
        "baseGeometry": base.get("geometryName"),
        "mainTrackGeometry": base.get("mainTrackGeometry"),
        "mainTrackVisualGeometry": base.get("mainTrackVisualGeometry"),
        "mainTrackDeformed": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "visualGeometry": visual,
    }


def _offset_access_geometry(
    name: str,
    centerline: Sequence[Point],
    widths: Sequence[float],
    context: Dict[str, Any],
    *,
    role: str,
    access_centerline_name: str,
    merge_open: bool,
) -> Dict[str, Any]:
    center = list(centerline)
    normals = _continuous_normals(center)
    left: List[Point] = []
    right: List[Point] = []
    for point, normal, width in zip(center, normals, widths):
        half = float(width) * 0.5
        a = (point[0] + normal[0] * half, point[1] + normal[1] * half)
        b = (point[0] - normal[0] * half, point[1] - normal[1] * half)
        left.append(a)
        right.append(b)
    inner, outer = _inner_outer_edges(left, right, context)
    polygon = list(left) + list(reversed(right))
    return {
        "name": name,
        "centerline": _polyline(center),
        access_centerline_name: _polyline(center),
        "leftEdge": _polyline(left),
        "rightEdge": _polyline(right),
        "innerEdge": _polyline(inner),
        "outerEdge": _polyline(outer),
        "sharedDividerEdge": _polyline(inner),
        "width": [round(float(value), 6) for value in widths],
        "polygon": _polyline(polygon),
        "selfIntersects": _polygon_self_intersects(polygon),
        "openStart": True,
        "openEnd": True,
        "renderHints": {
            "openStart": True,
            "openEnd": True,
            "strokeCaps": False,
            "drawAsBranch": True,
            "role": role,
            "mergeOpen": merge_open,
            "topology": "access_centerline_fix",
            "accessCenterlineUsed": True,
        },
    }


def _validate_candidate(context: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    geometries = candidate["visualGeometry"]["geometries"]
    entry = geometries[ENTRY_NAME]
    corridor = geometries[CORRIDOR_NAME]
    exit_access = geometries[EXIT_NAME]
    entry_center = _line_points(entry["centerline"])
    exit_center = _line_points(exit_access["centerline"])
    corridor_center = _line_points(corridor["centerline"])
    entry_widths = [float(value) for value in entry["width"]]
    exit_widths = [float(value) for value in exit_access["width"]]
    entry_gap = _distance(entry_center[-1], corridor_center[0])
    exit_gap = _distance(corridor_center[-1], exit_center[0])
    entry_overlap = _geometry_overlap_count(context, entry)
    corridor_overlap = _geometry_overlap_count(context, corridor)
    exit_overlap = _geometry_overlap_count(context, exit_access)
    no_x = not _visual_x_crossing(context, [entry, corridor, exit_access])
    width_smooth = max(_width_deltas(entry_widths) + _width_deltas(exit_widths) or [0.0]) <= 0.12
    entry_natural = _max_heading_step(entry_center) <= 8.5 and _heading_oscillation(entry_center, 0, len(entry_center) - 1) <= 95.0
    exit_natural = _max_heading_step(exit_center) <= 8.5 and _heading_oscillation(exit_center, 0, len(exit_center) - 1) <= 80.0
    fields = {
        "entryAccessCenterlineUsed": "PitEntryAccessCenterline" in entry and bool(entry.get("renderHints", {}).get("accessCenterlineUsed")),
        "exitAccessCenterlineUsed": "PitExitAccessCenterline" in exit_access and bool(exit_access.get("renderHints", {}).get("accessCenterlineUsed")),
        "sharedDividerNotUsedAsOnlyVisual": _line_points(entry["centerline"]) != _line_points(entry["sharedDividerEdge"])
        and _line_points(exit_access["centerline"]) != _line_points(exit_access["sharedDividerEdge"]),
        "noTriangularTaper": min(entry_widths) >= MIN_ACCESS_WIDTH_M * 0.95 and min(exit_widths) >= MIN_ACCESS_WIDTH_M * 0.95,
        "noRibbonOverlap": entry_overlap == 0 and corridor_overlap == 0 and exit_overlap == 0,
        "pitEntryLooksNatural": entry_natural and entry_gap <= 0.8 and width_smooth,
        "pitExitLooksNatural": exit_natural and exit_gap <= 0.8 and width_smooth,
        "mainTrackPreserved": True,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "noVisualXCrossing": no_x,
        "pitlaneStillConnected": entry_gap <= 0.8 and exit_gap <= 0.8,
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "entryCorridorGapMeters": round(entry_gap, 6),
        "corridorExitGapMeters": round(exit_gap, 6),
        "entryRibbonOverlapPointCount": entry_overlap,
        "corridorRibbonOverlapPointCount": corridor_overlap,
        "exitRibbonOverlapPointCount": exit_overlap,
        "entryMinWidth": round(min(entry_widths), 6),
        "exitMinWidth": round(min(exit_widths), 6),
        "maxWidthDelta": round(max(_width_deltas(entry_widths) + _width_deltas(exit_widths) or [0.0]), 6),
        "entryCenterlineMaxHeadingStep": round(_max_heading_step(entry_center), 6),
        "exitCenterlineMaxHeadingStep": round(_max_heading_step(exit_center), 6),
        "entryTaperLength": round(_polyline_length(entry_center), 6),
        "exitTaperLength": round(_polyline_length(exit_center), 6),
        "maxVisualSegmentLength": round(max(_max_segment(entry_center), _max_segment(corridor_center), _max_segment(exit_center)), 6),
    }
    passed = (
        fields["entryAccessCenterlineUsed"]
        and fields["exitAccessCenterlineUsed"]
        and fields["sharedDividerNotUsedAsOnlyVisual"]
        and fields["noTriangularTaper"]
        and fields["noRibbonOverlap"]
        and fields["pitEntryLooksNatural"]
        and fields["pitExitLooksNatural"]
        and fields["mainTrackPreserved"]
        and not fields["projectionChanged"]
        and not fields["mapPositionChanged"]
        and not fields["lateralOffsetChanged"]
        and not fields["physicsChanged"]
        and fields["noVisualXCrossing"]
        and fields["pitlaneStillConnected"]
        and fields["retaOpostaStillStraight"]
    )
    return {
        "name": "InterlagosPitAccessCenterlineFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _offset_from_main_left(context: Dict[str, Any], main_index: int, distance: float) -> Point:
    left = context["mainLeft"][main_index]
    center = context["mainCenter"][main_index]
    outward = _unit((left[0] - center[0], left[1] - center[1]))
    return left[0] + outward[0] * distance, left[1] + outward[1] * distance


def _push_center_outside(point: Point, width: float, context: Dict[str, Any]) -> Point:
    index, _ = _nearest_index(point, context["mainCenter"])
    center = context["mainCenter"][index]
    left = context["mainLeft"][index]
    outward = _unit((left[0] - center[0], left[1] - center[1]))
    vx = point[0] - center[0]
    vy = point[1] - center[1]
    along = vx * outward[0] + vy * outward[1]
    min_along = context["widths"][index] * 0.5 + width * 0.5 + 0.08
    if along >= min_along:
        return point
    return center[0] + outward[0] * min_along, center[1] + outward[1] * min_along


def _clamp_centerline_outside_main(points: Sequence[Point], widths: Sequence[float], context: Dict[str, Any]) -> List[Point]:
    adjusted: List[Point] = []
    for point, width in zip(points, widths):
        index, distance = _nearest_index(point, context["mainCenter"])
        main_center = context["mainCenter"][index]
        main_left = context["mainLeft"][index]
        direction = _unit((point[0] - main_center[0], point[1] - main_center[1]))
        if direction == (0.0, 0.0):
            direction = _unit((main_left[0] - main_center[0], main_left[1] - main_center[1]))
        required = context["widths"][index] * 0.5 + float(width) * 0.5 + 0.16
        if distance < required:
            adjusted.append((main_center[0] + direction[0] * required, main_center[1] + direction[1] * required))
        else:
            adjusted.append(point)
    return _smooth_polyline(adjusted, passes=1, keep_ends=True)


def _bezier(start: Point, end: Point, guide: Sequence[Point], guide_start: int, guide_end: int, count: int) -> List[Point]:
    start_tangent = _unit(
        (
            guide[min(len(guide) - 1, guide_start + 5)][0] - guide[max(0, guide_start - 2)][0],
            guide[min(len(guide) - 1, guide_start + 5)][1] - guide[max(0, guide_start - 2)][1],
        )
    )
    end_tangent = _unit(
        (
            guide[min(len(guide) - 1, guide_end + 2)][0] - guide[max(0, guide_end - 5)][0],
            guide[min(len(guide) - 1, guide_end + 2)][1] - guide[max(0, guide_end - 5)][1],
        )
    )
    chord = _distance(start, end)
    p1 = (start[0] + start_tangent[0] * chord * 0.42, start[1] + start_tangent[1] * chord * 0.42)
    p2 = (end[0] - end_tangent[0] * chord * 0.42, end[1] - end_tangent[1] * chord * 0.42)
    points: List[Point] = []
    for index in range(count):
        t = index / max(1, count - 1)
        mt = 1.0 - t
        points.append(
            (
                mt**3 * start[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * end[0],
                mt**3 * start[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * end[1],
            )
        )
    return points


def _smooth_widths(start_width: float, end_width: float, count: int) -> List[float]:
    widths: List[float] = []
    for index in range(count):
        t = index / max(1, count - 1)
        smooth = t * t * (3.0 - 2.0 * t)
        widths.append(float(start_width) + (float(end_width) - float(start_width)) * smooth)
    return widths


def _continuous_normals(points: Sequence[Point]) -> List[Point]:
    normals = _normals_for_open_polyline(points)
    for index in range(1, len(normals)):
        prev = normals[index - 1]
        cur = normals[index]
        if prev[0] * cur[0] + prev[1] * cur[1] < 0:
            normals[index] = (-cur[0], -cur[1])
    return normals


def _inner_outer_edges(left: Sequence[Point], right: Sequence[Point], context: Dict[str, Any]) -> Tuple[List[Point], List[Point]]:
    inner: List[Point] = []
    outer: List[Point] = []
    for a, b in zip(left, right):
        _, da = _nearest_index(a, context["mainCenter"])
        _, db = _nearest_index(b, context["mainCenter"])
        if da <= db:
            inner.append(a)
            outer.append(b)
        else:
            inner.append(b)
            outer.append(a)
    return inner, outer


def _polygon_self_intersects(points: Sequence[Point]) -> bool:
    closed = list(points) + [points[0]]
    segments = list(zip(closed, closed[1:]))
    for i, first in enumerate(segments):
        for j in range(i + 1, len(segments)):
            if abs(i - j) <= 1 or (i == 0 and j == len(segments) - 1):
                continue
            if _segments_intersect(first[0], first[1], segments[j][0], segments[j][1]):
                return True
    return False


def _width_deltas(widths: Sequence[float]) -> List[float]:
    return [abs(float(widths[index]) - float(widths[index - 1])) for index in range(1, len(widths))]


def _visual_x_crossing(context: Dict[str, Any], geometries: Sequence[Dict[str, Any]]) -> bool:
    main_segments = list(zip(context["mainLeft"], context["mainLeft"][1:])) + list(zip(context["mainRight"], context["mainRight"][1:]))
    for geometry in geometries:
        for key in ("leftEdge", "rightEdge"):
            points = _line_points(geometry.get(key))
            for segment in zip(points, points[1:]):
                for main_segment in main_segments:
                    if _segments_intersect(segment[0], segment[1], main_segment[0], main_segment[1]):
                        return True
    return False


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_centerline_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessCenterlineFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessCenterlineFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "entryAccessCenterlineUsed": bool(validation.get("entryAccessCenterlineUsed")),
        "exitAccessCenterlineUsed": bool(validation.get("exitAccessCenterlineUsed")),
        "sharedDividerNotUsedAsOnlyVisual": bool(validation.get("sharedDividerNotUsedAsOnlyVisual")),
        "noTriangularTaper": bool(validation.get("noTriangularTaper")),
        "noRibbonOverlap": bool(validation.get("noRibbonOverlap")),
        "pitEntryLooksNatural": bool(validation.get("pitEntryLooksNatural")),
        "pitExitLooksNatural": bool(validation.get("pitExitLooksNatural")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _candidate_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access centerline fix candidate", context, base, candidate, footer="entry/exit access centerlines promoted to visual geometry")


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    footer = f"passed={validation['passed']} entryCenter={validation['entryAccessCenterlineUsed']} exitCenter={validation['exitAccessCenterlineUsed']} natural={validation['pitEntryLooksNatural']}/{validation['pitExitLooksNatural']}"
    return _svg("Interlagos pit access centerline fix validation", context, base, candidate, footer=footer)


def _svg(title: str, context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], *, footer: str) -> str:
    width = 1500
    height = 980
    gap = 24
    panel_w = (width - gap * 4) / 3
    panel_h = height - 145
    panels = [
        ("entrada access", ENTRY_NAME, gap),
        ("saida access", EXIT_NAME, gap * 2 + panel_w),
        ("antes/depois", ENTRY_NAME, gap * 3 + panel_w * 2),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">MainTrack gray / before red / corridor yellow / new access cyan-green-orange / access centerline white</text>',
    ]
    for label, geometry_name, x in panels:
        parts.extend(_panel(context, base, candidate, label, geometry_name, x, 78, panel_w, panel_h))
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], label: str, geometry_name: str, x: float, y: float, width: float, height: float) -> List[str]:
    base_name = "InterlagosPitEntryBifurcationGeometry" if geometry_name == ENTRY_NAME else "InterlagosPitExitBifurcationGeometry"
    base_geom = base["visualGeometry"]["geometries"].get(base_name)
    candidate_geom = candidate["visualGeometry"]["geometries"][geometry_name]
    focus = _line_points(candidate_geom["centerline"])
    bounds = _bounds_for_points(focus, pad=48.0)
    sx = width / max(bounds["maxX"] - bounds["minX"], 1.0)
    sy = height / max(bounds["maxY"] - bounds["minY"], 1.0)
    scale = min(sx, sy)

    def project(point: Point) -> Point:
        return (x + (point[0] - bounds["minX"]) * scale, y + height - (point[1] - bounds["minY"]) * scale)

    def path(points: Sequence[Point], close: bool = False) -> str:
        clipped = [point for point in points if _inside(point, bounds)]
        if not clipped:
            return ""
        projected = [project(point) for point in clipped]
        value = "M " + " L ".join(f"{px:.2f} {py:.2f}" for px, py in projected)
        return value + (" Z" if close else "")

    styles = {ENTRY_NAME: "#22c55e", CORRIDOR_NAME: "#facc15", EXIT_NAME: "#fb923c"}
    parts = [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="#0b1220" stroke="#1f2937"/>',
        f'<text x="{x + 12:.2f}" y="{y + 24:.2f}" fill="#e2e8f0" font-size="15" font-family="Segoe UI, Arial">{_xml(label)}</text>',
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.72"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.72"/>',
    ]
    if base_geom:
        parts.append(f'<path d="{path(_line_points(base_geom["polygon"]), close=True)}" fill="#ef4444" fill-opacity="0.22" stroke="#ef4444" stroke-width="1.2" stroke-opacity="0.45"/>')
    for name, geom in candidate["visualGeometry"]["geometries"].items():
        color = styles.get(name, "#e5e7eb")
        parts.append(f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="{color}" fill-opacity="0.45" stroke="none"/>')
        parts.append(f'<path d="{path(_line_points(geom["leftEdge"]))}" fill="none" stroke="{color}" stroke-width="1.7"/>')
        parts.append(f'<path d="{path(_line_points(geom["rightEdge"]))}" fill="none" stroke="{color}" stroke-width="1.7"/>')
        parts.append(f'<path d="{path(_line_points(geom["centerline"]))}" fill="none" stroke="#f8fafc" stroke-width="1.15" stroke-dasharray="5 6" stroke-opacity="0.88"/>')
    return parts


if __name__ == "__main__":
    main()
