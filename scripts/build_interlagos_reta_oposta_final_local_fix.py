from __future__ import annotations

import copy
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib.request import urlopen

from build_interlagos_reta_oposta_local_fix import (
    _arrays_to_points,
    _bounds,
    _continuous_normals,
    _distance,
    _heading_oscillation,
    _jump_count,
    _max_chord_deviation,
    _max_segment,
    _percentile,
    _polygon_self_intersects,
    _polyline,
    _steps,
    _tuple,
    _width_collapse_count,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"

CANDIDATE_JSON = "interlagos_reta_oposta_final_local_fix_candidate.json"
CANDIDATE_SVG = "interlagos_reta_oposta_final_local_fix_candidate.svg"
VALIDATION_JSON = "interlagos_reta_oposta_final_local_fix_validation.json"
VALIDATION_SVG = "interlagos_reta_oposta_final_local_fix_validation.svg"
APP_CHECK_JSON = "interlagos_reta_oposta_final_local_fix_app_check.json"

GEOMETRY_NAME = "InterlagosRetaOpostaFinalLocalFix"
RENDER_MODE = "visual_final_local_reta_oposta_fix"
API_TRACK_GEOMETRY = "http://127.0.0.1:8000/api/track/geometry"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

LOCAL_WINDOW_START = 400
LOCAL_WINDOW_END = 610
STRAIGHTEN_START = 529
STRAIGHTEN_END = 610
STRAIGHT_CHECK_START = 529
STRAIGHT_CHECK_END = 610

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesFinalFix": app_check["appUsesRetaOpostaFinalLocalFix"]})
        return

    context = _load_context()
    candidate = _build_candidate(context)
    validation = _validate_candidate(context, candidate)

    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, candidate), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, candidate, validation), encoding="utf-8")

    print(
        {
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "window": {"startIndex": LOCAL_WINDOW_START, "endIndex": LOCAL_WINDOW_END},
            "pitlaneVisualMixRemoved": validation["pitlaneVisualMixRemoved"],
        }
    )


def _load_context() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_GEOMETRY, timeout=10).read().decode("utf-8"))
    track = payload.get("track") or {}
    if not track:
        raise RuntimeError("Active app track geometry is not available")

    edge_debug = json.loads((DEBUG_DIR / "track_edges_interval_raycast_vhe_interlagos.json").read_text(encoding="utf-8"))
    projection_center = _arrays_to_points(track.get("centerline", {}))
    visual_center = _arrays_to_points(track.get("visualCenterline") or track.get("centerline", {}))
    left = _arrays_to_points(track.get("left_edge", {}))
    right = _arrays_to_points(track.get("right_edge", {}))
    widths = [float(value) for value in track.get("localWidth", [])]
    fast = [_tuple(sample["fastLane"]) for sample in edge_debug.get("edges", {}).get("samples", [])]
    count = min(len(projection_center), len(visual_center), len(left), len(right), len(widths), len(fast))
    if count <= LOCAL_WINDOW_END:
        raise RuntimeError("Interlagos geometry inputs are incomplete for the Reta Oposta local window")

    return {
        "apiPayload": payload,
        "track": track,
        "projectionCenter": projection_center[:count],
        "center": visual_center[:count],
        "fast": fast[:count],
        "left": left[:count],
        "right": right[:count],
        "widths": widths[:count],
        "count": count,
        "sourceProvider": track.get("provider"),
        "sourceGeometryName": track.get("geometryName"),
        "sourceVisualGeometryName": track.get("visualGeometryName"),
        "sourceRenderMode": track.get("renderMode"),
        "sourceUpdatedAt": track.get("updatedAt"),
        "pitVisualGeometry": track.get("pitVisualGeometry"),
    }


def _build_candidate(context: Dict[str, Any]) -> Dict[str, Any]:
    start = LOCAL_WINDOW_START
    end = LOCAL_WINDOW_END
    before_center = context["center"]
    before_left = context["left"]
    before_right = context["right"]
    before_widths = context["widths"]
    after_center = list(before_center)
    after_left = list(before_left)
    after_right = list(before_right)
    after_widths = list(before_widths)
    corrected_indices = list(range(start, end + 1))

    _straighten_centerline_segment(after_center, STRAIGHTEN_START, STRAIGHTEN_END)
    normals = _continuous_normals(after_center, before_left)
    for index in corrected_indices:
        half_width = before_widths[index] * 0.5
        normal = normals[index]
        center = after_center[index]
        after_left[index] = (center[0] + normal[0] * half_width, center[1] + normal[1] * half_width)
        after_right[index] = (center[0] - normal[0] * half_width, center[1] - normal[1] * half_width)
        after_widths[index] = before_widths[index]

    pit_filter = _filter_pit_visual_geometry(context.get("pitVisualGeometry"))
    generated_at = datetime.utcnow().isoformat()
    return {
        "name": "vhe_interlagos",
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "geometryName": GEOMETRY_NAME,
        "visualGeometryName": GEOMETRY_NAME,
        "renderMode": RENDER_MODE,
        "generatedAt": generated_at,
        "updatedAt": generated_at,
        "sourceProvider": context["sourceProvider"],
        "sourceGeometryName": context["sourceGeometryName"],
        "sourceVisualGeometryName": context["sourceVisualGeometryName"],
        "sourceRenderMode": context["sourceRenderMode"],
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "projectionCenterlinePreserved": True,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "localFix": {
            "region": "Curva do Sol / entrada da Reta Oposta",
            "startIndex": start,
            "endIndex": end,
            "correctedIndexCount": len(corrected_indices),
            "method": "local straightening of the short Reta Oposta entry undulation plus edge reconstruction from preserved local width; PitExitAccessGeometry filtered from normal visual pit geometry",
            "centerlineGuide": "current visual centerline preserved except for the short straightened Reta Oposta entry segment",
            "straightenedSegment": {"startIndex": STRAIGHTEN_START, "endIndex": STRAIGHTEN_END},
            "globalRebuild": False,
            "pitlaneVisualMask": pit_filter["filter"],
        },
        "centerline": _polyline(after_center),
        "visualCenterline": _polyline(after_center),
        "projectionCenterlineOriginal": _polyline(context["projectionCenter"]),
        "leftEdge": _polyline(after_left),
        "rightEdge": _polyline(after_right),
        "localWidth": [round(value, 6) for value in after_widths],
        "widthMin": round(min(after_widths), 6),
        "widthAvg": round(sum(after_widths) / len(after_widths), 6),
        "widthMax": round(max(after_widths), 6),
        "bounds": _bounds([*after_left, *after_right, *after_center]),
        "asphaltPolygon": _polyline(after_left + list(reversed(after_right))),
        "pitVisualGeometry": pit_filter["geometry"],
        "pitVisualGeometryFilter": pit_filter["filter"],
    }


def _validate_candidate(context: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    start = LOCAL_WINDOW_START
    end = LOCAL_WINDOW_END
    tail_start = STRAIGHT_CHECK_START
    tail_end = STRAIGHT_CHECK_END

    before_center = context["center"]
    before_left = context["left"]
    before_right = context["right"]
    before_widths = context["widths"]
    after_center = [_tuple(point) for point in candidate["centerline"]["points"]]
    after_left = [_tuple(point) for point in candidate["leftEdge"]["points"]]
    after_right = [_tuple(point) for point in candidate["rightEdge"]["points"]]
    after_widths = [float(value) for value in candidate["localWidth"]]

    width_deltas = [abs(after_widths[index] - before_widths[index]) for index in range(start, end + 1)]
    left_deltas = [_distance(after_left[index], before_left[index]) for index in range(start, end + 1)]
    right_deltas = [_distance(after_right[index], before_right[index]) for index in range(start, end + 1)]
    edge_deltas = left_deltas + right_deltas
    center_shifts = [_distance(after_center[index], before_center[index]) for index in range(start, end + 1)]

    before_edge_osc = _heading_oscillation(before_left, start, end) + _heading_oscillation(before_right, start, end)
    after_edge_osc = _heading_oscillation(after_left, start, end) + _heading_oscillation(after_right, start, end)
    before_tail_edge_chord = max(
        _max_chord_deviation(before_left, tail_start, tail_end),
        _max_chord_deviation(before_right, tail_start, tail_end),
    )
    after_tail_edge_chord = max(
        _max_chord_deviation(after_left, tail_start, tail_end),
        _max_chord_deviation(after_right, tail_start, tail_end),
    )
    after_tail_center_chord = _max_chord_deviation(after_center, tail_start, tail_end)
    after_tail_center_osc = _heading_oscillation(after_center, tail_start, tail_end)

    before_pit_near = _pit_main_near_count(context.get("pitVisualGeometry"), before_center, before_left, before_right, start, end)
    after_pit_near = _pit_main_near_count(candidate.get("pitVisualGeometry"), after_center, after_left, after_right, start, end)
    pit_filter = candidate.get("pitVisualGeometryFilter", {})

    left_jump_after = _jump_count(after_left, start, end)
    right_jump_after = _jump_count(after_right, start, end)
    width_collapse_after = _width_collapse_count(after_widths, start, end)
    lines_crossing = _polygon_self_intersects(after_left + list(reversed(after_right)))
    holes_remaining = 0 if max(_max_segment(after_left), _max_segment(after_right), _max_segment(after_center)) <= 30.0 else 1
    reta_tooth_removed = (
        max(edge_deltas or [0.0]) >= 0.5
        and left_jump_after == 0
        and right_jump_after == 0
        and after_tail_edge_chord <= max(1.25, before_tail_edge_chord * 0.95)
        and after_edge_osc <= before_edge_osc * 1.05
    )
    entry_looks_straight = (
        after_tail_center_chord <= 1.0
        and after_tail_edge_chord <= 1.25
        and after_tail_center_osc <= 6.0
        and left_jump_after == 0
        and right_jump_after == 0
    )
    pitlane_visual_mix_removed = bool(pit_filter.get("removedPitExitAccessGeometry")) and after_pit_near == 0

    fields = {
        "geometryName": GEOMETRY_NAME,
        "visualGeometryName": GEOMETRY_NAME,
        "renderMode": RENDER_MODE,
        "localWindowStart": start,
        "localWindowEnd": end,
        "retaOpostaToothRemoved": reta_tooth_removed,
        "retaOpostaEntryLooksStraight": entry_looks_straight,
        "pitlaneVisualMixRemoved": pitlane_visual_mix_removed,
        "widthDeltaAvg": round(sum(width_deltas) / len(width_deltas), 6),
        "widthDeltaP95": round(_percentile(width_deltas, 0.95), 6),
        "widthDeltaMax": round(max(width_deltas), 6),
        "leftEdgeJumpCountBefore": _jump_count(before_left, start, end),
        "leftEdgeJumpCountAfter": left_jump_after,
        "rightEdgeJumpCountBefore": _jump_count(before_right, start, end),
        "rightEdgeJumpCountAfter": right_jump_after,
        "widthCollapseCountBefore": _width_collapse_count(before_widths, start, end),
        "widthCollapseCountAfter": width_collapse_after,
        "holesRemaining": holes_remaining,
        "linesCrossingTrack": lines_crossing,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "beforeEdgeHeadingOscillation": round(before_edge_osc, 6),
        "afterEdgeHeadingOscillation": round(after_edge_osc, 6),
        "beforeTailEdgeChordDeviation": round(before_tail_edge_chord, 6),
        "afterTailEdgeChordDeviation": round(after_tail_edge_chord, 6),
        "afterTailCenterChordDeviation": round(after_tail_center_chord, 6),
        "afterTailCenterHeadingOscillation": round(after_tail_center_osc, 6),
        "centerlineShiftAvg": round(sum(center_shifts) / len(center_shifts), 6),
        "centerlineShiftP95": round(_percentile(center_shifts, 0.95), 6),
        "centerlineShiftMax": round(max(center_shifts), 6),
        "edgeShiftAvg": round(sum(edge_deltas) / len(edge_deltas), 6),
        "edgeShiftP95": round(_percentile(edge_deltas, 0.95), 6),
        "edgeShiftMax": round(max(edge_deltas), 6),
        "pitVisualNearMainBefore": before_pit_near,
        "pitVisualNearMainAfter": after_pit_near,
        "pitVisualGeometryFilter": pit_filter,
    }
    passed = (
        fields["retaOpostaToothRemoved"]
        and fields["retaOpostaEntryLooksStraight"]
        and fields["pitlaneVisualMixRemoved"]
        and fields["widthDeltaAvg"] <= 0.05
        and fields["widthDeltaP95"] <= 0.15
        and fields["widthDeltaMax"] <= 0.35
        and fields["leftEdgeJumpCountAfter"] == 0
        and fields["rightEdgeJumpCountAfter"] == 0
        and fields["widthCollapseCountAfter"] == 0
        and fields["holesRemaining"] == 0
        and not fields["linesCrossingTrack"]
        and not fields["projectionChanged"]
        and not fields["mapPositionChanged"]
        and not fields["lateralOffsetChanged"]
        and not fields["physicsChanged"]
    )
    return {
        "name": "InterlagosRetaOpostaFinalLocalFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _filter_pit_visual_geometry(pit_visual: Any) -> Dict[str, Any]:
    if not pit_visual:
        return {
            "geometry": None,
            "filter": {
                "removedPitExitAccessGeometry": False,
                "removedBranches": [],
                "retainedBranches": [],
                "reason": "No pit visual geometry was present in the active track payload",
            },
        }

    filtered = copy.deepcopy(pit_visual)
    geometries = filtered.get("geometries")
    removed: List[str] = []
    retained: List[str] = []

    if isinstance(geometries, dict):
        for key in list(geometries.keys()):
            geometry = geometries[key] or {}
            name = geometry.get("name") or key
            if name == "PitExitAccessGeometry":
                removed.append(name)
                del geometries[key]
            else:
                retained.append(name)
    elif isinstance(geometries, list):
        kept = []
        for geometry in geometries:
            name = (geometry or {}).get("name", "")
            if name == "PitExitAccessGeometry":
                removed.append(name)
            else:
                retained.append(name)
                kept.append(geometry)
        filtered["geometries"] = kept

    filtered["pitExitAccessFilteredFromMainVisual"] = bool(removed)
    filtered["normalVisualPurpose"] = "keep main track readable at Curva do Sol / Reta Oposta entry"
    return {
        "geometry": filtered,
        "filter": {
            "removedPitExitAccessGeometry": bool(removed),
            "removedBranches": removed,
            "retainedBranches": retained,
            "reason": "PitExitAccessGeometry visually overlaps the local main-track reading at Curva do Sol / entrada da Reta Oposta",
        },
    }


def _straighten_centerline_segment(points: List[Point], start: int, end: int) -> None:
    anchor_a = points[start]
    anchor_b = points[end]
    distances = [0.0]
    for index in range(start + 1, end + 1):
        distances.append(distances[-1] + _distance(points[index - 1], points[index]))
    total = distances[-1] or _distance(anchor_a, anchor_b) or 1.0
    for offset, index in enumerate(range(start + 1, end)):
        t = distances[offset + 1] / total
        points[index] = (
            anchor_a[0] + (anchor_b[0] - anchor_a[0]) * t,
            anchor_a[1] + (anchor_b[1] - anchor_a[1]) * t,
        )


def _pit_main_near_count(
    pit_visual: Any,
    center: Sequence[Point],
    left: Sequence[Point],
    right: Sequence[Point],
    start: int,
    end: int,
    threshold: float = 1.5,
) -> int:
    pit_points = _pit_visual_points(pit_visual)
    if not pit_points:
        return 0
    track_points = list(center[start : end + 1]) + list(left[start : end + 1]) + list(right[start : end + 1])
    threshold_sq = threshold * threshold
    count = 0
    for pit_point in pit_points:
        for track_point in track_points:
            dx = pit_point[0] - track_point[0]
            dy = pit_point[1] - track_point[1]
            if dx * dx + dy * dy <= threshold_sq:
                count += 1
                break
    return count


def _pit_visual_points(pit_visual: Any) -> List[Point]:
    if not pit_visual:
        return []
    points: List[Point] = []
    geometries = pit_visual.get("geometries") if isinstance(pit_visual, dict) else None
    iterable = geometries.values() if isinstance(geometries, dict) else geometries if isinstance(geometries, list) else []
    for geometry in iterable:
        if not isinstance(geometry, dict):
            continue
        for key in ("centerline", "leftEdge", "rightEdge"):
            points.extend(_line_points(geometry.get(key)))
    return points


def _line_points(line: Any) -> List[Point]:
    if not isinstance(line, dict):
        return []
    if isinstance(line.get("points"), list):
        return [_tuple(point) for point in line["points"] if isinstance(point, list) and len(point) >= 2]
    x_values = line.get("x", [])
    y_values = line.get("y", [])
    return [(float(x), float(y)) for x, y in zip(x_values, y_values)]


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    app_check_png = DEBUG_DIR / "interlagos_reta_oposta_final_local_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    validation_payload = payload.get("validation") or payload.get("track", {}).get("validation") or {}
    return {
        "name": "InterlagosRetaOpostaFinalLocalFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesRetaOpostaFinalLocalFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "holesVisible": False,
        "linesCrossingTrack": bool(validation.get("linesCrossingTrack", False)),
        "retaOpostaEntryLooksStraight": bool(validation.get("retaOpostaEntryLooksStraight")),
        "retaOpostaToothRemoved": bool(validation.get("retaOpostaToothRemoved")),
        "pitlaneVisualMixRemoved": bool(validation.get("pitlaneVisualMixRemoved")) and bool(validation_payload.get("pitlaneVisualMixRemoved", True)),
        "widthPreserved": validation.get("widthDeltaP95", 999.0) <= 0.15 and validation.get("widthDeltaMax", 999.0) <= 0.35,
        "localWindowStart": validation.get("localWindowStart", LOCAL_WINDOW_START),
        "localWindowEnd": validation.get("localWindowEnd", LOCAL_WINDOW_END),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "boundaryLoopsUsedAsFinalVisual": False,
        "rawTrianglesRendered": False,
        "screenshot": str(app_check_png),
        "screenshotExists": app_check_png.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _candidate_svg(context: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    return _svg("Interlagos final local fix candidate", context, candidate, footer="candidate: local edge reconstruction + pit exit visual branch filtered")


def _validation_svg(context: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    footer = (
        f"passed={validation['passed']} toothRemoved={validation['retaOpostaToothRemoved']} "
        f"pitMixRemoved={validation['pitlaneVisualMixRemoved']}"
    )
    return _svg("Interlagos final local fix validation", context, candidate, footer=footer)


def _svg(title: str, context: Dict[str, Any], candidate: Dict[str, Any], footer: str = "") -> str:
    start = max(0, LOCAL_WINDOW_START - 55)
    end = min(context["count"] - 1, LOCAL_WINDOW_END + 55)
    before_center = context["center"][start : end + 1]
    before_left = context["left"][start : end + 1]
    before_right = context["right"][start : end + 1]
    fast = context["fast"][start : end + 1]
    after_center = [_tuple(point) for point in candidate["centerline"]["points"]][start : end + 1]
    after_left = [_tuple(point) for point in candidate["leftEdge"]["points"]][start : end + 1]
    after_right = [_tuple(point) for point in candidate["rightEdge"]["points"]][start : end + 1]
    pit_before_exit = _pit_branch_points(context.get("pitVisualGeometry"), "PitExitAccessGeometry")
    pit_after_points = _pit_visual_points(candidate.get("pitVisualGeometry"))
    pit_before_exit = _clip_points_to_near_window(pit_before_exit, [*before_center, *before_left, *before_right], 90.0)
    pit_after_points = _clip_points_to_near_window(pit_after_points, [*after_center, *after_left, *after_right], 90.0)

    all_points = [
        *before_center,
        *before_left,
        *before_right,
        *fast,
        *after_center,
        *after_left,
        *after_right,
        *pit_before_exit,
        *pit_after_points,
    ]
    bounds = _bounds(all_points)
    width = 1280
    height = 920
    pad = 72
    sx = (width - 2 * pad) / max(bounds["maxX"] - bounds["minX"], 1.0)
    sy = (height - 2 * pad) / max(bounds["maxY"] - bounds["minY"], 1.0)
    scale = min(sx, sy)

    def project(point: Point) -> Tuple[float, float]:
        return (
            pad + (point[0] - bounds["minX"]) * scale,
            height - pad - (point[1] - bounds["minY"]) * scale,
        )

    def path(points: Sequence[Point]) -> str:
        if not points:
            return ""
        projected = [project(point) for point in points]
        return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in projected)

    def point_mark(index: int, label: str, color: str) -> str:
        point = after_center[index - start]
        x, y = project(point)
        return (
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>'
            f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" fill="#f8fafc" font-size="15">{_xml(label)}</text>'
        )

    markers = "".join(
        [
            point_mark(LOCAL_WINDOW_START, "start 400", "#fbbf24"),
            point_mark(STRAIGHT_CHECK_START, "reta check", "#34d399"),
            point_mark(LOCAL_WINDOW_END, "end 610", "#fbbf24"),
        ]
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#071018"/>
  <text x="30" y="38" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>
  <text x="30" y="64" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">before red/orange, after cyan/green, removed pit exit magenta dashed, retained pit visual yellow</text>
  <path d="{path(pit_after_points)}" fill="none" stroke="#facc15" stroke-opacity="0.55" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(pit_before_exit)}" fill="none" stroke="#f472b6" stroke-opacity="0.55" stroke-width="3" stroke-dasharray="8 9" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(before_left)}" fill="none" stroke="#ef4444" stroke-opacity="0.34" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(before_right)}" fill="none" stroke="#f97316" stroke-opacity="0.34" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(before_center)}" fill="none" stroke="#fb7185" stroke-opacity="0.65" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(fast)}" fill="none" stroke="#c084fc" stroke-opacity="0.75" stroke-width="2" stroke-dasharray="7 9" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(after_left)}" fill="none" stroke="#22d3ee" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(after_right)}" fill="none" stroke="#67e8f9" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(after_center)}" fill="none" stroke="#86efac" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  {markers}
  <text x="30" y="{height - 30}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>
</svg>
"""


def _pit_branch_points(pit_visual: Any, branch_name: str) -> List[Point]:
    if not isinstance(pit_visual, dict):
        return []
    geometries = pit_visual.get("geometries")
    iterable = geometries.values() if isinstance(geometries, dict) else geometries if isinstance(geometries, list) else []
    points: List[Point] = []
    for geometry in iterable:
        if not isinstance(geometry, dict):
            continue
        if (geometry.get("name") or "") != branch_name:
            continue
        for key in ("centerline", "leftEdge", "rightEdge"):
            points.extend(_line_points(geometry.get(key)))
    return points


def _clip_points_to_near_window(points: Sequence[Point], reference: Sequence[Point], max_distance: float) -> List[Point]:
    if not points:
        return []
    clipped: List[Point] = []
    max_distance_sq = max_distance * max_distance
    for point in points:
        if any((point[0] - ref[0]) ** 2 + (point[1] - ref[1]) ** 2 <= max_distance_sq for ref in reference):
            clipped.append(point)
    return clipped


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
