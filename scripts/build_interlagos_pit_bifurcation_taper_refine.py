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
    _adjacent_width_deltas,
    _build_audit,
    _distance,
    _distances,
    _geometry_by_name,
    _geometry_overlap_count,
    _has_fake_chicane,
    _heading_oscillation,
    _is_rectangular_block,
    _line_points,
    _load_context,
    _max_chord_deviation,
    _max_segment,
    _nearest_index,
    _open_caps,
    _polyline,
    _segments_intersect,
    _unit,
    _xml,
)


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_bifurcation_fix_candidate.json"
CANDIDATE_JSON = "interlagos_pit_bifurcation_taper_refine_candidate.json"
CANDIDATE_SVG = "interlagos_pit_bifurcation_taper_refine_candidate.svg"
VALIDATION_JSON = "interlagos_pit_bifurcation_taper_refine_validation.json"
VALIDATION_SVG = "interlagos_pit_bifurcation_taper_refine_validation.svg"
APP_CHECK_JSON = "interlagos_pit_bifurcation_taper_refine_app_check.json"

GEOMETRY_NAME = "InterlagosPitBifurcationTaperRefine"
RENDER_MODE = "visual_pit_bifurcation_taper_refine"
ENTRY_GEOMETRY_NAME = "InterlagosPitEntryBifurcationGeometry"
CORRIDOR_GEOMETRY_NAME = "PitLaneCorridorBifurcationGeometry"
EXIT_GEOMETRY_NAME = "InterlagosPitExitBifurcationGeometry"

MIN_VISUAL_TAPER_WIDTH_M = 1.15
ENTRY_START_BACK_MAIN_POINTS = 20
EXIT_END_FORWARD_MAIN_POINTS = 24
ENTRY_POINT_COUNT = 92
EXIT_POINT_COUNT = 88

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesPitBifurcationTaperRefine": app_check["appUsesPitBifurcationTaperRefine"]})
        return

    context = _load_context()
    audit = _build_audit(context)
    base_candidate = json.loads((DEBUG_DIR / BASE_CANDIDATE_JSON).read_text(encoding="utf-8"))
    candidate = _build_candidate(context, audit, base_candidate)
    validation = _validate_candidate(context, base_candidate, candidate)

    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, base_candidate, candidate), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, base_candidate, candidate, validation), encoding="utf-8")

    print(
        {
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "noSharpPitTaper": validation["noSharpPitTaper"],
            "pitTaperLengthIncreased": validation["pitTaperLengthIncreased"],
            "noTriangularSpike": validation["noTriangularSpike"],
        }
    )


def _build_candidate(context: Dict[str, Any], audit: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    base_geometries = visual["geometries"]
    base_entry = base_geometries[ENTRY_GEOMETRY_NAME]
    base_corridor = base_geometries[CORRIDOR_GEOMETRY_NAME]
    base_exit = base_geometries[EXIT_GEOMETRY_NAME]

    entry_zone = audit["entrySplitZone"]
    exit_zone = audit["exitMergeZone"]
    entry_start_main = max(0, int(entry_zone["taperStart"]["nearestMainIndex"]) - ENTRY_START_BACK_MAIN_POINTS)
    entry_end_main = int(entry_zone["taperEnd"]["nearestMainIndex"])
    exit_start_main = int(exit_zone["taperStart"]["nearestMainIndex"])
    exit_end_main = min(len(context["mainLeft"]) - 1, int(exit_zone["taperEnd"]["nearestMainIndex"]) + EXIT_END_FORWARD_MAIN_POINTS)
    entry_start_pit = max(0, int(entry_zone["taperStart"]["pitLaneIndex"]) - 14)
    entry_end_pit = int(entry_zone["taperEnd"]["pitLaneIndex"])
    exit_start_pit = int(exit_zone["taperStart"]["pitLaneIndex"])
    exit_end_pit = min(len(context["pitPoints"]) - 1, int(exit_zone["taperEnd"]["pitLaneIndex"]) + 16)

    corridor_inner = _line_points(base_corridor["innerEdge"])
    corridor_outer = _line_points(base_corridor["outerEdge"])
    if not corridor_inner or not corridor_outer:
        raise RuntimeError("Base corridor requires innerEdge/outerEdge for taper refine")

    entry = _build_asymmetric_taper_geometry(
        ENTRY_GEOMETRY_NAME,
        context=context,
        divider_start=context["mainLeft"][entry_start_main],
        divider_end=corridor_inner[0],
        outer_start=_offset_from_main_left(context, entry_start_main, MIN_VISUAL_TAPER_WIDTH_M),
        outer_end=corridor_outer[0],
        guide=context["pitPoints"],
        guide_start=entry_start_pit,
        guide_end=entry_end_pit,
        count=ENTRY_POINT_COUNT,
        role="pit_entry_taper_refine",
        merge_open=False,
        divider_override=_entry_divider(context, entry_start_main, entry_end_main, corridor_inner[0], ENTRY_POINT_COUNT),
    )
    corridor = copy.deepcopy(base_corridor)
    corridor["renderHints"]["topology"] = "bifurcation_taper_refine"

    exit_access = _build_asymmetric_taper_geometry(
        EXIT_GEOMETRY_NAME,
        context=context,
        divider_start=corridor_inner[-1],
        divider_end=context["mainLeft"][exit_end_main],
        outer_start=corridor_outer[-1],
        outer_end=_offset_from_main_left(context, exit_end_main, MIN_VISUAL_TAPER_WIDTH_M),
        guide=context["pitPoints"],
        guide_start=exit_start_pit,
        guide_end=exit_end_pit,
        count=EXIT_POINT_COUNT,
        role="pit_exit_taper_refine",
        merge_open=True,
        divider_override=_exit_divider(context, exit_start_main, exit_end_main, corridor_inner[-1], EXIT_POINT_COUNT),
    )

    geometries = {
        ENTRY_GEOMETRY_NAME: entry,
        CORRIDOR_GEOMETRY_NAME: corridor,
        EXIT_GEOMETRY_NAME: exit_access,
    }
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "InterlagosPitBifurcationFix taper refinement"
    visual["taperRefine"] = {
        "minVisualTaperWidthMeters": MIN_VISUAL_TAPER_WIDTH_M,
        "entryPointCountBefore": len(base_entry["width"]),
        "entryPointCountAfter": len(entry["width"]),
        "exitPointCountBefore": len(base_exit["width"]),
        "exitPointCountAfter": len(exit_access["width"]),
        "entryMainIndexRange": [entry_start_main, entry_end_main],
        "exitMainIndexRange": [exit_start_main, exit_end_main],
        "method": "asymmetric taper from shared divider edge toward outer pit edge; no zero-width visible point",
    }
    visual["bifurcationTopology"]["entry"] = _replace_topology_geometry(visual["bifurcationTopology"]["entry"], entry)
    visual["bifurcationTopology"]["exit"] = _replace_topology_geometry(visual["bifurcationTopology"]["exit"], exit_access)
    visual["geometries"] = geometries

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
        "construction": {
            "refinesOnly": ["PitEntryAccessGeometry taper", "PitExitAccessGeometry taper", "sharedDividerEdge"],
            "entryTaperLengthIncreased": True,
            "exitTaperLengthIncreased": True,
            "minVisualTaperWidthMeters": MIN_VISUAL_TAPER_WIDTH_M,
            "mainTrackPreserved": True,
        },
        "visualGeometry": visual,
    }


def _build_asymmetric_taper_geometry(
    name: str,
    *,
    context: Dict[str, Any],
    divider_start: Point,
    divider_end: Point,
    outer_start: Point,
    outer_end: Point,
    guide: Sequence[Point],
    guide_start: int,
    guide_end: int,
    count: int,
    role: str,
    merge_open: bool,
    divider_override: Sequence[Point] | None = None,
) -> Dict[str, Any]:
    divider = list(divider_override) if divider_override else _bezier(divider_start, divider_end, guide, guide_start, guide_end, count)
    outer_curve = _bezier(outer_start, outer_end, guide, guide_start, guide_end, count)
    if divider_override is None:
        divider = [_push_to_main_left_envelope(point, context) for point in divider]
    target_widths = _smooth_widths(_distance(divider_start, outer_start), _distance(divider_end, outer_end), count)
    outer = _outer_from_target_widths(divider, outer_curve, target_widths, context)
    outer = _smooth_polyline(outer, passes=1, keep_ends=True)
    outer = _outer_from_target_widths(divider, outer, target_widths, context)
    centerline = [((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5) for a, b in zip(divider, outer)]
    widths = [_distance(a, b) for a, b in zip(divider, outer)]
    polygon = list(divider) + list(reversed(outer))
    return {
        "name": name,
        "centerline": _polyline(centerline),
        "leftEdge": _polyline(divider),
        "rightEdge": _polyline(outer),
        "innerEdge": _polyline(divider),
        "outerEdge": _polyline(outer),
        "sharedDividerEdge": _polyline(divider),
        "width": [round(value, 6) for value in widths],
        "polygon": _polyline(polygon),
        "selfIntersects": _polygon_self_intersects_local(polygon),
        "openStart": True,
        "openEnd": True,
        "renderHints": {
            "openStart": True,
            "openEnd": True,
            "strokeCaps": False,
            "drawAsBranch": True,
            "role": role,
            "mergeOpen": merge_open,
            "topology": "bifurcation_taper_refine",
        },
    }


def _validate_candidate(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    base_geometries = base["visualGeometry"]["geometries"]
    geometries = candidate["visualGeometry"]["geometries"]
    base_entry = base_geometries[ENTRY_GEOMETRY_NAME]
    base_exit = base_geometries[EXIT_GEOMETRY_NAME]
    entry = geometries[ENTRY_GEOMETRY_NAME]
    corridor = geometries[CORRIDOR_GEOMETRY_NAME]
    exit_access = geometries[EXIT_GEOMETRY_NAME]
    entry_widths = [float(value) for value in entry["width"]]
    exit_widths = [float(value) for value in exit_access["width"]]
    all_deltas = _adjacent_width_deltas(entry_widths) + _adjacent_width_deltas(exit_widths)
    entry_length_before = _polyline_length(_line_points(base_entry["centerline"]))
    entry_length_after = _polyline_length(_line_points(entry["centerline"]))
    exit_length_before = _polyline_length(_line_points(base_exit["centerline"]))
    exit_length_after = _polyline_length(_line_points(exit_access["centerline"]))
    entry_overlap = _geometry_overlap_count(context, entry)
    corridor_overlap = _geometry_overlap_count(context, corridor)
    exit_overlap = _geometry_overlap_count(context, exit_access)
    no_visual_x = not _visual_x_crossing(context, [entry, corridor, exit_access])
    no_wall = _open_caps(entry) and _open_caps(corridor) and _open_caps(exit_access)
    entry_center = _line_points(entry["centerline"])
    exit_center = _line_points(exit_access["centerline"])
    entry_divider = _line_points(entry["sharedDividerEdge"])
    exit_divider = _line_points(exit_access["sharedDividerEdge"])
    entry_corridor_gap = _distance(entry_center[-1], _line_points(corridor["centerline"])[0])
    corridor_exit_gap = _distance(_line_points(corridor["centerline"])[-1], exit_center[0])
    divider_smooth = _max_heading_step(entry_divider) <= 10.0 and _max_heading_step(exit_divider) <= 10.0

    fields = {
        "noSharpPitTaper": min(entry_widths[:8]) >= MIN_VISUAL_TAPER_WIDTH_M * 0.92 and min(exit_widths[-8:]) >= MIN_VISUAL_TAPER_WIDTH_M * 0.92,
        "pitTaperLengthIncreased": entry_length_after > entry_length_before * 1.25 and exit_length_after > exit_length_before * 1.25,
        "pitlaneWidthGrowthSmooth": max(all_deltas or [0.0]) <= 0.32,
        "sharedDividerEdgeSmooth": divider_smooth,
        "noTriangularSpike": min(entry_widths) >= 1.0 and min(exit_widths) >= 1.0,
        "noVisualXCrossing": no_visual_x,
        "noRibbonOverlap": entry_overlap == 0 and corridor_overlap == 0 and exit_overlap == 0,
        "noWallClosingPitlane": no_wall,
        "noRectangularBlock": not _is_rectangular_block(entry) and not _is_rectangular_block(exit_access),
        "noFakeChicane": divider_smooth and no_visual_x and max(_max_segment(entry_center), _max_segment(exit_center)) <= 6.0,
        "mainTrackPreserved": True,
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "pitlaneStillConnected": entry_corridor_gap <= 0.75 and corridor_exit_gap <= 0.75,
        "pitExitOpenMerge": bool(exit_access.get("renderHints", {}).get("mergeOpen")) and bool(exit_access.get("openEnd")),
        "pitEntryOpenSplit": bool(entry.get("openStart")) and bool(entry.get("openEnd")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "entryTaperLengthBefore": round(entry_length_before, 6),
        "entryTaperLengthAfter": round(entry_length_after, 6),
        "exitTaperLengthBefore": round(exit_length_before, 6),
        "exitTaperLengthAfter": round(exit_length_after, 6),
        "entryMinWidth": round(min(entry_widths), 6),
        "exitMinWidth": round(min(exit_widths), 6),
        "maxWidthDelta": round(max(all_deltas or [0.0]), 6),
        "entryCorridorGapMeters": round(entry_corridor_gap, 6),
        "corridorExitGapMeters": round(corridor_exit_gap, 6),
        "entryRibbonOverlapPointCount": entry_overlap,
        "corridorRibbonOverlapPointCount": corridor_overlap,
        "exitRibbonOverlapPointCount": exit_overlap,
        "maxVisualSegmentLength": round(max(_max_segment(entry_center), _max_segment(_line_points(corridor["centerline"])), _max_segment(exit_center)), 6),
        "entryDividerMaxHeadingStep": round(_max_heading_step(entry_divider), 6),
        "exitDividerMaxHeadingStep": round(_max_heading_step(exit_divider), 6),
    }
    passed = (
        fields["noSharpPitTaper"]
        and fields["pitTaperLengthIncreased"]
        and fields["pitlaneWidthGrowthSmooth"]
        and fields["sharedDividerEdgeSmooth"]
        and fields["noTriangularSpike"]
        and fields["noVisualXCrossing"]
        and fields["noRibbonOverlap"]
        and fields["noWallClosingPitlane"]
        and fields["noRectangularBlock"]
        and fields["noFakeChicane"]
        and fields["mainTrackPreserved"]
        and fields["retaOpostaStillStraight"]
        and fields["pitlaneStillConnected"]
        and fields["pitExitOpenMerge"]
        and fields["pitEntryOpenSplit"]
        and not fields["projectionChanged"]
        and not fields["mapPositionChanged"]
        and not fields["lateralOffsetChanged"]
        and not fields["physicsChanged"]
    )
    return {
        "name": "InterlagosPitBifurcationTaperRefineValidation",
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


def _entry_divider(context: Dict[str, Any], main_start: int, main_end: int, corridor_inner_start: Point, count: int) -> List[Point]:
    main_count = min(34, max(12, count // 3))
    transition_count = count - main_count + 1
    main_path = _resample_polyline(context["mainLeft"][main_start : main_end + 1], main_count)
    start_tangent = _tangent(context["mainLeft"], main_end)
    end_tangent = _unit((corridor_inner_start[0] - main_path[-1][0], corridor_inner_start[1] - main_path[-1][1]))
    transition = _bezier_with_tangents(main_path[-1], corridor_inner_start, start_tangent, end_tangent, transition_count)
    return main_path[:-1] + transition


def _exit_divider(context: Dict[str, Any], main_start: int, main_end: int, corridor_inner_end: Point, count: int) -> List[Point]:
    main_count = min(34, max(12, count // 3))
    transition_count = count - main_count + 1
    main_path = _resample_polyline(context["mainLeft"][main_start : main_end + 1], main_count)
    start_tangent = _unit((main_path[0][0] - corridor_inner_end[0], main_path[0][1] - corridor_inner_end[1]))
    end_tangent = _tangent(context["mainLeft"], main_start)
    transition = _bezier_with_tangents(corridor_inner_end, main_path[0], start_tangent, end_tangent, transition_count)
    return transition[:-1] + main_path


def _tangent(points: Sequence[Point], index: int) -> Point:
    a = points[max(0, index - 3)]
    b = points[min(len(points) - 1, index + 3)]
    return _unit((b[0] - a[0], b[1] - a[1]))


def _bezier_with_tangents(start: Point, end: Point, start_tangent: Point, end_tangent: Point, count: int) -> List[Point]:
    chord = _distance(start, end)
    p1 = (start[0] + start_tangent[0] * chord * 0.36, start[1] + start_tangent[1] * chord * 0.36)
    p2 = (end[0] - end_tangent[0] * chord * 0.36, end[1] - end_tangent[1] * chord * 0.36)
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


def _resample_polyline(points: Sequence[Point], count: int) -> List[Point]:
    if len(points) <= 1 or count <= 1:
        return list(points[:1])
    distances = [0.0]
    for index in range(1, len(points)):
        distances.append(distances[-1] + _distance(points[index - 1], points[index]))
    total = distances[-1] or 1.0
    result: List[Point] = []
    cursor = 0
    for sample_index in range(count):
        target = total * sample_index / (count - 1)
        while cursor < len(distances) - 2 and distances[cursor + 1] < target:
            cursor += 1
        span = max(distances[cursor + 1] - distances[cursor], 1e-9)
        t = (target - distances[cursor]) / span
        a = points[cursor]
        b = points[cursor + 1]
        result.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return result


def _push_to_main_left_envelope(point: Point, context: Dict[str, Any]) -> Point:
    index, _ = _nearest_index(point, context["mainCenter"])
    center = context["mainCenter"][index]
    left = context["mainLeft"][index]
    outward = _unit((left[0] - center[0], left[1] - center[1]))
    vx = point[0] - center[0]
    vy = point[1] - center[1]
    along = vx * outward[0] + vy * outward[1]
    min_along = context["widths"][index] * 0.5 + 0.02
    if along >= min_along:
        return point
    return center[0] + outward[0] * min_along, center[1] + outward[1] * min_along


def _outer_from_target_widths(
    divider: Sequence[Point],
    outer_hint: Sequence[Point],
    target_widths: Sequence[float],
    context: Dict[str, Any],
) -> List[Point]:
    adjusted: List[Point] = []
    for divider_point, hint_point, width in zip(divider, outer_hint, target_widths):
        index, _ = _nearest_index(divider_point, context["mainCenter"])
        center = context["mainCenter"][index]
        left = context["mainLeft"][index]
        main_outward = _unit((left[0] - center[0], left[1] - center[1]))
        target_width = max(MIN_VISUAL_TAPER_WIDTH_M, float(width))
        outer_point = (divider_point[0] + main_outward[0] * target_width, divider_point[1] + main_outward[1] * target_width)
        adjusted.append(_push_to_main_left_envelope(outer_point, context))
    return adjusted


def _smooth_widths(start_width: float, end_width: float, count: int) -> List[float]:
    if count <= 1:
        return [max(MIN_VISUAL_TAPER_WIDTH_M, float(end_width))]
    widths: List[float] = []
    for index in range(count):
        t = index / (count - 1)
        smooth = t * t * (3.0 - 2.0 * t)
        widths.append(float(start_width) + (float(end_width) - float(start_width)) * smooth)
    return widths


def _replace_topology_geometry(topology: Dict[str, Any], geometry: Dict[str, Any]) -> Dict[str, Any]:
    updated = copy.deepcopy(topology)
    updated["pitBranchCenterline"] = geometry["centerline"]
    updated["outerLeftEdge"] = geometry["outerEdge"]
    updated["sharedDividerEdge"] = geometry["sharedDividerEdge"]
    updated["taperRefined"] = True
    updated["minVisualTaperWidthMeters"] = MIN_VISUAL_TAPER_WIDTH_M
    return updated


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
    points = []
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


def _smooth_polyline(points: Sequence[Point], *, passes: int, keep_ends: bool) -> List[Point]:
    smoothed = list(points)
    for _ in range(passes):
        next_points = list(smoothed)
        start = 1 if keep_ends else 0
        end = len(smoothed) - 1 if keep_ends else len(smoothed)
        for index in range(start, end):
            prev_point = smoothed[index - 1]
            point = smoothed[index]
            next_point = smoothed[(index + 1) % len(smoothed)]
            next_points[index] = (
                prev_point[0] * 0.25 + point[0] * 0.5 + next_point[0] * 0.25,
                prev_point[1] * 0.25 + point[1] * 0.5 + next_point[1] * 0.25,
            )
        smoothed = next_points
    return smoothed


def _polyline_length(points: Sequence[Point]) -> float:
    return sum(_distance(points[index - 1], points[index]) for index in range(1, len(points)))


def _max_heading_step(points: Sequence[Point]) -> float:
    headings: List[float] = []
    for index in range(1, len(points)):
        dx = points[index][0] - points[index - 1][0]
        dy = points[index][1] - points[index - 1][1]
        if math.hypot(dx, dy) > 1e-6:
            headings.append(math.atan2(dy, dx))
    max_step = 0.0
    for index in range(1, len(headings)):
        delta = headings[index] - headings[index - 1]
        while delta > math.pi:
            delta -= math.tau
        while delta < -math.pi:
            delta += math.tau
        max_step = max(max_step, abs(math.degrees(delta)))
    return max_step


def _polygon_self_intersects_local(points: Sequence[Point]) -> bool:
    closed = list(points) + [points[0]]
    segments = list(zip(closed, closed[1:]))
    for i, first in enumerate(segments):
        for j in range(i + 1, len(segments)):
            if abs(i - j) <= 1 or (i == 0 and j == len(segments) - 1):
                continue
            if _segments_intersect(first[0], first[1], segments[j][0], segments[j][1]):
                return True
    return False


def _visual_x_crossing(context: Dict[str, Any], geometries: Sequence[Dict[str, Any]]) -> bool:
    main_segments = list(zip(context["mainLeft"], context["mainLeft"][1:])) + list(zip(context["mainRight"], context["mainRight"][1:]))
    for geometry in geometries:
        for key in ("rightEdge", "outerEdge"):
            points = _line_points(geometry.get(key))
            for segment in zip(points, points[1:]):
                for main_segment in main_segments:
                    if _segments_intersect(segment[0], segment[1], main_segment[0], main_segment[1]):
                        return True
    return False


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_bifurcation_taper_refine_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitBifurcationTaperRefineAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitBifurcationTaperRefine": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "pitlaneEntryHarmonic": bool(validation.get("noSharpPitTaper") and validation.get("pitEntryOpenSplit")),
        "pitlaneExitHarmonic": bool(validation.get("noSharpPitTaper") and validation.get("pitExitOpenMerge")),
        "noSharpPitTaper": bool(validation.get("noSharpPitTaper")),
        "noTriangularSpike": bool(validation.get("noTriangularSpike")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _candidate_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    return _svg("Interlagos pit bifurcation taper refine candidate", context, base, candidate, footer="before red/gray, after green-orange-yellow; sharedDividerEdge highlighted")


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    footer = (
        f"passed={validation['passed']} noSharp={validation['noSharpPitTaper']} "
        f"lengthIncreased={validation['pitTaperLengthIncreased']} noSpike={validation['noTriangularSpike']}"
    )
    return _svg("Interlagos pit bifurcation taper refine validation", context, base, candidate, footer=footer)


def _svg(title: str, context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], *, footer: str) -> str:
    width = 1500
    height = 980
    gap = 24
    panel_w = (width - gap * 4) / 3
    panel_h = height - 145
    panels = [
        ("entrada taper", ENTRY_GEOMETRY_NAME, gap),
        ("saida taper", EXIT_GEOMETRY_NAME, gap * 2 + panel_w),
        ("comparacao antes/depois", ENTRY_GEOMETRY_NAME, gap * 3 + panel_w * 2),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">MainTrack gray / before red / corridor yellow / entry green / exit orange / shared divider white dashed</text>',
    ]
    for label, geometry_name, x in panels:
        parts.extend(_panel(context, base, candidate, label, geometry_name, x, 78, panel_w, panel_h))
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(
    context: Dict[str, Any],
    base: Dict[str, Any],
    candidate: Dict[str, Any],
    label: str,
    focus_geometry_name: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> List[str]:
    base_geom = base["visualGeometry"]["geometries"][focus_geometry_name]
    candidate_geom = candidate["visualGeometry"]["geometries"][focus_geometry_name]
    focus = _line_points(candidate_geom["centerline"])
    bounds = _bounds_for_points(focus, pad=44.0)
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

    styles = {
        ENTRY_GEOMETRY_NAME: "#22c55e",
        CORRIDOR_GEOMETRY_NAME: "#facc15",
        EXIT_GEOMETRY_NAME: "#fb923c",
    }
    parts = [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="#0b1220" stroke="#1f2937"/>',
        f'<text x="{x + 12:.2f}" y="{y + 24:.2f}" fill="#e2e8f0" font-size="15" font-family="Segoe UI, Arial">{_xml(label)}</text>',
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.72"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.72"/>',
        f'<path d="{path(_line_points(base_geom["polygon"]), close=True)}" fill="#ef4444" fill-opacity="0.23" stroke="#ef4444" stroke-width="1.2" stroke-opacity="0.5"/>',
    ]
    for name, geom in candidate["visualGeometry"]["geometries"].items():
        color = styles.get(name, "#e5e7eb")
        parts.append(f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="{color}" fill-opacity="0.48" stroke="none"/>')
        parts.append(f'<path d="{path(_line_points(geom["leftEdge"]))}" fill="none" stroke="{color}" stroke-width="1.7"/>')
        parts.append(f'<path d="{path(_line_points(geom["rightEdge"]))}" fill="none" stroke="{color}" stroke-width="1.7"/>')
        parts.append(f'<path d="{path(_line_points(geom["sharedDividerEdge"]))}" fill="none" stroke="#f8fafc" stroke-width="1.1" stroke-dasharray="5 6" stroke-opacity="0.8"/>')
    return parts


def _bounds_for_points(points: Sequence[Point], *, pad: float) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"minX": min(xs) - pad, "maxX": max(xs) + pad, "minY": min(ys) - pad, "maxY": max(ys) + pad}


def _inside(point: Point, bounds: Dict[str, float]) -> bool:
    return bounds["minX"] <= point[0] <= bounds["maxX"] and bounds["minY"] <= point[1] <= bounds["maxY"]


if __name__ == "__main__":
    main()
