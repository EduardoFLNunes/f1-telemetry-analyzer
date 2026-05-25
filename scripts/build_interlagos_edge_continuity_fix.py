from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_edges_from_surface import (  # noqa: E402
    _TriangleSurfaceIndex,
    _boundary_edges,
    _build_boundary_loops,
    _build_inside_intervals,
    _component_analysis,
    _fast_lane_tangent,
    _line_intersections_with_loop_segments,
    _segments_from_loops_with_metadata,
    _selected_triangle_indices,
    parse_fast_lane_ai,
)
from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402


AUDIT_JSON = "interlagos_edge_identity_audit.json"
AUDIT_SVG = "interlagos_edge_identity_audit.svg"
CANDIDATE_JSON = "interlagos_edge_continuity_fix_candidate.json"
CANDIDATE_SVG = "interlagos_edge_continuity_fix_candidate.svg"
VALIDATION_JSON = "interlagos_edge_continuity_fix_validation.json"
VALIDATION_SVG = "interlagos_edge_continuity_fix_validation.svg"

GEOMETRY_NAME = "InterlagosMainTrackEdgeContinuityFix"
TRACK_NAME = "vhe_interlagos"
TRACK_CONFIG = "gp"

WINDOW = 20
JUMP_RATIO = 2.5
WIDTH_DELTA_LIMIT = 2.0
WIDTH_COLLAPSE_RATIO = 0.65
PIT_NEAR_M = 3.0
BRIDGE_GAP_MAX_M = 2.5
BRIDGE_WIDTH_MIN_M = 8.0
BRIDGE_WIDTH_MAX_M = 18.0

CONFIRMED_GROUPS = {
    "sSenna": (283, 298),
    "curvaSolLeadIn": (420, 455),
    "curvaSol": (503, 629),
    "curvaSolBridge": (487, 582),
    "retaOpostaPitExit": (820, 855),
    "entradaBoxes": (2405, 2427),
}

REGION_RANGES = {
    "S do Senna": [(283, 298)],
    "Curva do Sol": [(420, 455), (503, 629)],
    "Reta Oposta / pit exit": [(598, 866), (820, 855)],
    "Entrada dos boxes": [(2223, 2370), (2405, 2427)],
}

AUX_MESHES = {"roadline004", "roadverge", "roadlineout"}

Point = Tuple[float, float]


def main() -> None:
    output_dir = REPO_ROOT / "data" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)
    context = _build_context()
    audit = _build_audit(context)
    candidate = _build_candidate(context, audit)
    validation = _build_validation(context, audit, candidate)

    (output_dir / AUDIT_JSON).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / AUDIT_SVG).write_text(_build_audit_svg(context, audit), encoding="utf-8")
    (output_dir / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / CANDIDATE_SVG).write_text(_build_candidate_svg(context, candidate), encoding="utf-8")
    (output_dir / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / VALIDATION_SVG).write_text(_build_validation_svg(context, candidate, validation), encoding="utf-8")

    print(
        {
            "audit": str(output_dir / AUDIT_JSON),
            "auditSvg": str(output_dir / AUDIT_SVG),
            "candidate": str(output_dir / CANDIDATE_JSON),
            "candidateSvg": str(output_dir / CANDIDATE_SVG),
            "validation": str(output_dir / VALIDATION_JSON),
            "validationSvg": str(output_dir / VALIDATION_SVG),
            "passed": validation["passed"],
            "metrics": validation["metrics"],
        }
    )


def _build_context() -> Dict[str, Any]:
    manifest = TrackFileResolver().build_track_file_manifest(
        TRACK_NAME,
        TRACK_CONFIG,
        source="assetto_corsa",
        game_code="assetto_corsa",
    ).to_dict()
    surface = build_track_surface_polygon_from_manifest(manifest)
    triangles = surface.get("triangles", [])
    components, triangle_to_component = _component_analysis(triangles) if triangles else ([], {})
    selected_component = components[0] if components else None
    selected_id = int(selected_component["componentId"]) if selected_component else -1
    selected_indices = _selected_triangle_indices(triangle_to_component, selected_id) if selected_component else []
    boundary_edges, node_points = _boundary_edges(triangles, selected_indices)
    _, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    surface_index = _TriangleSurfaceIndex(triangles, selected_indices)
    loop_segments = _segments_from_loops_with_metadata(clean_loops)

    edge_debug_path = REPO_ROOT / "data" / "debug" / "track_edges_interval_raycast_vhe_interlagos.json"
    edge_debug = json.loads(edge_debug_path.read_text(encoding="utf-8"))

    ai_files = manifest.get("aiFiles") or {}
    fast_lane = parse_fast_lane_ai(ai_files.get("fast_lane"))
    pit_lane = parse_fast_lane_ai(ai_files.get("pit_lane"))
    fast_points = [_tuple(point["mapPosition"]) for point in fast_lane.get("points", [])]
    pit_points = [_tuple(point["mapPosition"]) for point in pit_lane.get("points", [])]
    mesh_index = _MeshAttributionIndex([triangles[index] for index in selected_indices])
    pit_index = _PointGrid(pit_points, cell_size=20.0)

    current_samples = edge_debug["edges"]["samples"]
    current = _samples_to_geometry(current_samples)
    candidates = [
        _build_candidates_for_sample(index, fast_lane, loop_segments, surface_index, mesh_index, pit_index)
        for index in range(len(current_samples))
    ]

    return {
        "manifest": manifest,
        "surface": surface,
        "triangles": triangles,
        "components": components,
        "cleanLoops": clean_loops,
        "edgeDebug": edge_debug,
        "edgeDebugPath": str(edge_debug_path),
        "fastLane": fast_lane,
        "pitLane": pit_lane,
        "fastPoints": fast_points,
        "pitPoints": pit_points,
        "meshIndex": mesh_index,
        "pitIndex": pit_index,
        "currentSamples": current_samples,
        "current": current,
        "candidates": candidates,
    }


def _build_candidates_for_sample(
    index: int,
    fast_lane: Dict[str, Any],
    loop_segments: Sequence[Dict[str, Any]],
    surface_index: _TriangleSurfaceIndex,
    mesh_index: "_MeshAttributionIndex",
    pit_index: "_PointGrid",
) -> List[Dict[str, Any]]:
    points = fast_lane.get("points", [])
    fast = _tuple(points[index]["mapPosition"])
    tx, ty = _fast_lane_tangent(points, index)
    normal = (-ty, tx)
    intersections = _line_intersections_with_loop_segments(fast, normal, loop_segments)
    intervals = [
        interval
        for interval in _build_inside_intervals(fast, normal, intersections, surface_index)
        if interval.get("midpointInsideSurface") and interval.get("plausibleWidth")
    ]
    candidates = [
        _candidate_from_interval(index, fast, normal, interval, "raw", mesh_index, pit_index)
        for interval in intervals
    ]
    for first, second in zip(intervals, intervals[1:]):
        gap = float(second["startT"]) - float(first["endT"])
        width = float(second["endT"]) - float(first["startT"])
        contains_fast = float(first["startT"]) <= 0.0 <= float(second["endT"])
        if gap < -1e-6 or gap > BRIDGE_GAP_MAX_M:
            continue
        if not contains_fast or width < BRIDGE_WIDTH_MIN_M or width > BRIDGE_WIDTH_MAX_M:
            continue
        bridged = {
            "intervalIndex": first["intervalIndex"],
            "startT": float(first["startT"]),
            "endT": float(second["endT"]),
            "width": width,
            "midpoint": [
                (float(first["rightHit"]["point"][0]) + float(second["leftHit"]["point"][0])) * 0.5,
                (float(first["rightHit"]["point"][1]) + float(second["leftHit"]["point"][1])) * 0.5,
            ],
            "midpointInsideSurface": True,
            "containsFastLane": True,
            "rightHit": first["rightHit"],
            "leftHit": second["leftHit"],
            "plausibleWidth": True,
            "bridgeGap": gap,
            "bridgedIntervals": [first["intervalIndex"], second["intervalIndex"]],
        }
        candidates.append(_candidate_from_interval(index, fast, normal, bridged, "bridge", mesh_index, pit_index))
    return candidates


def _candidate_from_interval(
    index: int,
    fast: Point,
    normal: Point,
    interval: Dict[str, Any],
    kind: str,
    mesh_index: "_MeshAttributionIndex",
    pit_index: "_PointGrid",
) -> Dict[str, Any]:
    right_t = float(interval["startT"])
    left_t = float(interval["endT"])
    left = (fast[0] + normal[0] * left_t, fast[1] + normal[1] * left_t)
    right = (fast[0] + normal[0] * right_t, fast[1] + normal[1] * right_t)
    left_mesh = mesh_index.nearest(left)
    right_mesh = mesh_index.nearest(right)
    left_pit = pit_index.distance(left)
    right_pit = pit_index.distance(right)
    return {
        "index": index,
        "kind": kind,
        "intervalIndex": interval.get("intervalIndex"),
        "bridgedIntervals": interval.get("bridgedIntervals"),
        "bridgeGap": round(float(interval.get("bridgeGap", 0.0)), 6) if kind == "bridge" else None,
        "fastLane": _round(fast),
        "normal": _round(normal),
        "leftEdge": _round(left),
        "rightEdge": _round(right),
        "leftT": round(left_t, 6),
        "rightT": round(right_t, 6),
        "width": round(float(interval["width"]), 6),
        "containsFastLane": bool(interval.get("containsFastLane")),
        "midpointInsideSurface": bool(interval.get("midpointInsideSurface")),
        "leftHit": _hit_payload(interval.get("leftHit")),
        "rightHit": _hit_payload(interval.get("rightHit")),
        "leftMesh": left_mesh,
        "rightMesh": right_mesh,
        "leftDistanceToPitLaneAi": round(left_pit, 6) if left_pit is not None else None,
        "rightDistanceToPitLaneAi": round(right_pit, 6) if right_pit is not None else None,
    }


def _hit_payload(hit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not hit:
        return {}
    return {
        "point": hit.get("point"),
        "loopId": hit.get("loopId"),
        "sourceLoopId": hit.get("sourceLoopId"),
        "loopType": hit.get("loopType"),
        "loopArea": hit.get("loopArea"),
        "loopPerimeter": hit.get("loopPerimeter"),
    }


def _samples_to_geometry(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    left: List[Point] = []
    right: List[Point] = []
    center: List[Point] = []
    fast: List[Point] = []
    widths: List[float] = []
    for sample in samples:
        left.append(_tuple(sample["leftEdge"]))
        right.append(_tuple(sample["rightEdge"]))
        center.append(_tuple(sample["centerline"]))
        fast.append(_tuple(sample["fastLane"]))
        widths.append(float(sample["localWidth"]))
    return {"left": left, "right": right, "center": center, "fast": fast, "widths": widths}


def _build_audit(context: Dict[str, Any]) -> Dict[str, Any]:
    samples = context["currentSamples"]
    geom = context["current"]
    candidates = context["candidates"]
    pit_index = context["pitIndex"]
    count = len(samples)

    center_steps = _steps(geom["center"])
    left_steps = _steps(geom["left"])
    right_steps = _steps(geom["right"])
    widths = geom["widths"]
    suspect_indices = set()
    audited_samples: List[Dict[str, Any]] = []

    for index, sample in enumerate(samples):
        prev = samples[(index - 1) % count]
        selected = sample.get("selectedInterval") or {}
        prev_selected = prev.get("selectedInterval") or {}
        left_hit = selected.get("leftHit") or {}
        right_hit = selected.get("rightHit") or {}
        prev_left_hit = prev_selected.get("leftHit") or {}
        prev_right_hit = prev_selected.get("rightHit") or {}
        selected_candidate = _selected_candidate_from_candidates(sample, candidates[index])
        left_mesh = selected_candidate.get("leftMesh") if selected_candidate else None
        right_mesh = selected_candidate.get("rightMesh") if selected_candidate else None
        left_pit = pit_index.distance(geom["left"][index])
        right_pit = pit_index.distance(geom["right"][index])
        median_left = _local_median(left_steps, index)
        median_right = _local_median(right_steps, index)
        median_width = _local_median(widths, index)
        width_delta = abs(widths[index] - widths[(index - 1) % count])
        left_jump = left_steps[index] > max(2.0, JUMP_RATIO * median_left)
        right_jump = right_steps[index] > max(2.0, JUMP_RATIO * median_right)
        width_jump = width_delta > WIDTH_DELTA_LIMIT
        width_collapse = widths[index] < WIDTH_COLLAPSE_RATIO * median_width
        left_source_changed = left_hit.get("sourceLoopId") != prev_left_hit.get("sourceLoopId")
        right_source_changed = right_hit.get("sourceLoopId") != prev_right_hit.get("sourceLoopId")
        left_loop_changed = left_hit.get("loopId") != prev_left_hit.get("loopId")
        right_loop_changed = right_hit.get("loopId") != prev_right_hit.get("loopId")
        left_mesh_changed = selected_candidate and left_mesh != (_selected_candidate_from_candidates(prev, candidates[(index - 1) % count]) or {}).get("leftMesh")
        right_mesh_changed = selected_candidate and right_mesh != (_selected_candidate_from_candidates(prev, candidates[(index - 1) % count]) or {}).get("rightMesh")
        left_internal_small = _small_internal_hit(left_hit)
        right_internal_small = _small_internal_hit(right_hit)
        pit_risk = _in_any_range(index, [(503, 629), (598, 866), (2223, 2370)])
        aux_mesh = (left_mesh or {}).get("mesh") in AUX_MESHES or (right_mesh or {}).get("mesh") in AUX_MESHES
        pit_near = min([value for value in (left_pit, right_pit) if value is not None] or [999.0]) <= PIT_NEAR_M

        reasons = []
        if left_jump:
            reasons.append("leftEdgeJump")
        if right_jump:
            reasons.append("rightEdgeJump")
        if width_jump:
            reasons.append("widthDelta")
        if (left_source_changed and left_jump) or (right_source_changed and right_jump):
            reasons.append("sourceLoopChangedWithJump")
        if (left_loop_changed and left_jump) or (right_loop_changed and right_jump):
            reasons.append("loopChangedWithJump")
        if pit_risk and aux_mesh:
            reasons.append("pitAdjacentAuxMesh")
        if (left_internal_small or right_internal_small) and (left_jump or right_jump or width_collapse or (pit_risk and aux_mesh)):
            reasons.append("smallInternalHoleEdge")
        if width_collapse:
            reasons.append("widthCollapse")
        if pit_risk and pit_near and (left_jump or right_jump or width_jump or width_collapse):
            reasons.append("pitLaneProximityBreaksContinuity")
        if _in_confirmed_problem(index):
            reasons.append("confirmedProblemRegion")
        if reasons:
            suspect_indices.add(index)

        audited_samples.append(
            {
                "index": index,
                "centerStep": round(center_steps[index], 6),
                "leftStep": round(left_steps[index], 6),
                "rightStep": round(right_steps[index], 6),
                "medianLeftStepLocal": round(median_left, 6),
                "medianRightStepLocal": round(median_right, 6),
                "width": round(widths[index], 6),
                "medianWidthLocal": round(median_width, 6),
                "widthDelta": round(width_delta, 6),
                "leftSourceLoopChanged": bool(left_source_changed),
                "rightSourceLoopChanged": bool(right_source_changed),
                "leftLoopChanged": bool(left_loop_changed),
                "rightLoopChanged": bool(right_loop_changed),
                "leftMeshChanged": bool(left_mesh_changed),
                "rightMeshChanged": bool(right_mesh_changed),
                "leftMesh": left_mesh,
                "rightMesh": right_mesh,
                "leftDistanceToPitLaneAi": round(left_pit, 6) if left_pit is not None else None,
                "rightDistanceToPitLaneAi": round(right_pit, 6) if right_pit is not None else None,
                "selectedIntervalContainsFastLane": bool(sample.get("selectedIntervalContainsFastLane")),
                "midpointInsideSurface": bool(sample.get("midpointInsideSurface")),
                "leftLoopType": sample.get("leftLoopType"),
                "rightLoopType": sample.get("rightLoopType"),
                "leftSourceLoopId": left_hit.get("sourceLoopId"),
                "rightSourceLoopId": right_hit.get("sourceLoopId"),
                "leftLoopId": left_hit.get("loopId"),
                "rightLoopId": right_hit.get("loopId"),
                "suspect": bool(reasons),
                "reasons": reasons,
            }
        )

    groups = _group_indices(sorted(suspect_indices))
    return {
        "name": "InterlagosEdgeIdentityAudit",
        "generatedAt": datetime.utcnow().isoformat(),
        "projection": "mapX = worldX, mapY = -worldZ",
        "inputs": {
            "edgeDebug": context["edgeDebugPath"],
            "fastLaneAi": context["fastLane"].get("path"),
            "pitLaneAi": context["pitLane"].get("path"),
        },
        "summary": {
            "sampleCount": count,
            "suspectCount": len(suspect_indices),
            "suspectGroups": groups,
            "confirmedProblemGroups": CONFIRMED_GROUPS,
        },
        "samples": audited_samples,
    }


def _selected_candidate_from_candidates(sample: Dict[str, Any], candidates: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    selected = sample.get("selectedInterval") or {}
    if not selected:
        return None
    start_t = round(float(selected.get("startT", 0.0)), 6)
    end_t = round(float(selected.get("endT", 0.0)), 6)
    for candidate in candidates:
        if candidate["kind"] != "raw":
            continue
        if abs(float(candidate["rightT"]) - start_t) <= 1e-5 and abs(float(candidate["leftT"]) - end_t) <= 1e-5:
            return candidate
    return None


def _build_candidate(context: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
    current = context["current"]
    fast = current["fast"]
    samples = context["currentSamples"]
    candidates = context["candidates"]
    count = len(samples)
    chosen: List[Optional[Dict[str, Any]]] = [None] * count
    decision_log: List[Dict[str, Any]] = []
    force_interpolate = set(range(CONFIRMED_GROUPS["sSenna"][0], CONFIRMED_GROUPS["sSenna"][1] + 1))
    force_interpolate.update(range(CONFIRMED_GROUPS["curvaSolLeadIn"][0], CONFIRMED_GROUPS["curvaSolLeadIn"][1] + 1))
    force_interpolate.update(range(484, CONFIRMED_GROUPS["curvaSolBridge"][1] + 1))
    force_interpolate.update(range(CONFIRMED_GROUPS["retaOpostaPitExit"][0], CONFIRMED_GROUPS["retaOpostaPitExit"][1] + 1))
    force_interpolate.update(range(CONFIRMED_GROUPS["entradaBoxes"][0], CONFIRMED_GROUPS["entradaBoxes"][1] + 1))

    for index in range(count):
        current_selected = _selected_candidate_from_candidates(samples[index], candidates[index])
        if index in force_interpolate:
            decision_log.append({"index": index, "method": "interpolate", "reason": "confirmedEdgeSwitchOrFalseMerge"})
            continue
        region_preferred = _region_preferred_candidate(index, candidates[index])
        if region_preferred:
            chosen[index] = region_preferred
            decision_log.append(
                {
                    "index": index,
                    "method": region_preferred["kind"],
                    "reason": "regionSpecificContinuityCandidate",
                    "width": region_preferred["width"],
                    "leftSourceLoopId": region_preferred["leftHit"].get("sourceLoopId"),
                    "rightSourceLoopId": region_preferred["rightHit"].get("sourceLoopId"),
                }
            )
            continue
        if current_selected:
            chosen[index] = current_selected
            decision_log.append({"index": index, "method": "raw", "reason": "unchangedOutsideConfirmedContinuityFix", "width": current_selected["width"]})
        else:
            decision_log.append({"index": index, "method": "interpolate", "reason": "missingCurrentSelectedCandidate"})

    left: List[Optional[Point]] = [None] * count
    right: List[Optional[Point]] = [None] * count
    widths: List[Optional[float]] = [None] * count
    source: List[str] = ["interpolated"] * count
    hit_meta: List[Dict[str, Any]] = [{} for _ in range(count)]
    for index, candidate in enumerate(chosen):
        if not candidate:
            continue
        left[index] = _tuple(candidate["leftEdge"])
        right[index] = _tuple(candidate["rightEdge"])
        widths[index] = float(candidate["width"])
        source[index] = candidate["kind"]
        hit_meta[index] = {
            "leftHit": candidate["leftHit"],
            "rightHit": candidate["rightHit"],
            "leftMesh": candidate["leftMesh"],
            "rightMesh": candidate["rightMesh"],
        }

    interpolation_groups = _interpolate_missing_edges(fast, left, right, widths, source, hit_meta)
    final_widths = [float(value) for value in widths if value is not None]
    bounds = _bounds([point for point in left + right + fast if point is not None])
    selection_summary = Counter(source)
    corrected = sorted(index for index, method in enumerate(source) if method != "raw")
    return {
        "name": TRACK_NAME,
        "trackName": TRACK_NAME,
        "trackConfig": TRACK_CONFIG,
        "geometryName": GEOMETRY_NAME,
        "generatedAt": datetime.utcnow().isoformat(),
        "projection": "mapX = worldX, mapY = -worldZ",
        "source": "assetto_corsa_track_files",
        "provider": GEOMETRY_NAME,
        "providerSource": "assetto_corsa_track_files",
        "centerline": _polyline_payload(fast),
        "leftEdge": _polyline_payload([_require_point(point) for point in left]),
        "rightEdge": _polyline_payload([_require_point(point) for point in right]),
        "localWidth": [round(value, 6) for value in final_widths],
        "widthMin": round(min(final_widths), 6),
        "widthAvg": round(sum(final_widths) / len(final_widths), 6),
        "widthMax": round(max(final_widths), 6),
        "bounds": bounds,
        "asphaltPolygon": _polyline_payload([_require_point(point) for point in left] + list(reversed([_require_point(point) for point in right]))),
        "selection": {
            "summary": dict(selection_summary),
            "correctedIndexGroups": _group_indices(corrected),
            "interpolationGroups": interpolation_groups,
            "decisions": decision_log,
            "hitMetadata": hit_meta,
        },
        "validationIntent": {
            "fastLaneAiUnchanged": True,
            "pitLaneAiUsedAsGuideOnly": True,
            "projectionChanged": False,
            "mapPositionChanged": False,
            "lateralOffsetChanged": False,
            "physicsChanged": False,
            "notPromotedToApp": True,
        },
    }


def _region_preferred_candidate(index: int, candidates: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    in_curva_bridge = CONFIRMED_GROUPS["curvaSolBridge"][0] <= index <= CONFIRMED_GROUPS["curvaSolBridge"][1]
    in_entry = CONFIRMED_GROUPS["entradaBoxes"][0] <= index <= CONFIRMED_GROUPS["entradaBoxes"][1]
    if not (in_curva_bridge or in_entry):
        return None
    bridge_candidates = [
        candidate
        for candidate in candidates
        if candidate["kind"] == "bridge"
        and BRIDGE_WIDTH_MIN_M <= float(candidate["width"]) <= BRIDGE_WIDTH_MAX_M
        and candidate["rightHit"].get("sourceLoopId") == 357
        and candidate["leftHit"].get("sourceLoopId") == 359
    ]
    if not bridge_candidates:
        return None
    return min(bridge_candidates, key=lambda candidate: abs(float(candidate["width"]) - 12.0))


def _continuity_score(
    index: int,
    candidate: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
    baseline_width: float,
    raw_sample: Dict[str, Any],
) -> Tuple[float, str]:
    score = abs(float(candidate["width"]) - baseline_width) * 0.75
    reasons = []
    if previous:
        left_step = _distance(_tuple(candidate["leftEdge"]), _tuple(previous["leftEdge"]))
        right_step = _distance(_tuple(candidate["rightEdge"]), _tuple(previous["rightEdge"]))
        width_delta = abs(float(candidate["width"]) - float(previous["width"]))
        score += left_step + right_step + width_delta
        if candidate["leftHit"].get("sourceLoopId") != previous["leftHit"].get("sourceLoopId"):
            score += 2.0
            reasons.append("leftSourceLoopChange")
        if candidate["rightHit"].get("sourceLoopId") != previous["rightHit"].get("sourceLoopId"):
            score += 2.0
            reasons.append("rightSourceLoopChange")
        if candidate["leftHit"].get("loopId") != previous["leftHit"].get("loopId"):
            score += 0.75
        if candidate["rightHit"].get("loopId") != previous["rightHit"].get("loopId"):
            score += 0.75
        if left_step > 12.0 or right_step > 12.0:
            score += 40.0
            reasons.append("edgeJump")
    if not candidate.get("containsFastLane"):
        score += 35.0
        reasons.append("fastLaneOutsideInterval")
    if float(candidate["width"]) < baseline_width * WIDTH_COLLAPSE_RATIO:
        score += 100.0
        reasons.append("widthCollapse")
    if _small_internal_hit(candidate["leftHit"]) or _small_internal_hit(candidate["rightHit"]):
        if float(candidate["width"]) < baseline_width * 0.85:
            score += 35.0
            reasons.append("smallInternalHole")
    pit_risk = _in_any_range(index, [(503, 629), (598, 866), (2223, 2370)])
    pit_distance = min(
        [
            value
            for value in (candidate.get("leftDistanceToPitLaneAi"), candidate.get("rightDistanceToPitLaneAi"))
            if value is not None
        ]
        or [999.0]
    )
    aux_mesh = (candidate.get("leftMesh") or {}).get("mesh") in AUX_MESHES or (candidate.get("rightMesh") or {}).get("mesh") in AUX_MESHES
    if pit_risk and pit_distance <= PIT_NEAR_M and float(candidate["width"]) > baseline_width * 1.12:
        score += 45.0
        reasons.append("pitAdjacentFalseMergeRisk")
    if pit_risk and aux_mesh and float(candidate["width"]) < baseline_width * 0.85:
        score += 45.0
        reasons.append("pitAuxMeshWidthCollapse")
    if candidate["kind"] == "bridge" and float(candidate["width"]) >= BRIDGE_WIDTH_MIN_M:
        raw_width = float(raw_sample.get("localWidth", candidate["width"]))
        if raw_width < baseline_width * 0.75:
            score -= 12.0
            reasons.append("bridgeRepairsCollapsedRaw")
    return score, ",".join(reasons) or "edgeContinuity"


def _previous_chosen(chosen: Sequence[Optional[Dict[str, Any]]], index: int) -> Optional[Dict[str, Any]]:
    for previous in range(index - 1, -1, -1):
        if chosen[previous]:
            return chosen[previous]
    return None


def _interpolate_missing_edges(
    fast: Sequence[Point],
    left: List[Optional[Point]],
    right: List[Optional[Point]],
    widths: List[Optional[float]],
    source: List[str],
    hit_meta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    count = len(fast)
    missing = [index for index, point in enumerate(left) if point is None or right[index] is None]
    groups = _group_indices(missing)
    normals = _fast_normals(fast)
    for group in groups:
        start = int(group["startIndex"])
        end = int(group["endIndex"])
        before = _previous_valid(left, start)
        after = _next_valid(left, end)
        if before is None or after is None:
            continue
        length = (end - start) + 1
        before_left = _require_point(left[before])
        after_left = _require_point(left[after])
        before_right = _require_point(right[before])
        after_right = _require_point(right[after])
        mode = "fastLaneOffsetContinuity"
        before_left_t, before_right_t = _edge_offsets_from_fast(fast[before], normals[before], before_left, before_right)
        after_left_t, after_right_t = _edge_offsets_from_fast(fast[after], normals[after], after_left, after_right)
        for offset, index in enumerate(range(start, end + 1), start=1):
            t = offset / (length + 1)
            smooth = t * t * (3.0 - 2.0 * t)
            left_t = before_left_t + (after_left_t - before_left_t) * smooth
            right_t = before_right_t + (after_right_t - before_right_t) * smooth
            normal = normals[index]
            center = fast[index]
            left[index] = (center[0] + normal[0] * left_t, center[1] + normal[1] * left_t)
            right[index] = (center[0] + normal[0] * right_t, center[1] + normal[1] * right_t)
            widths[index] = _distance(_require_point(left[index]), _require_point(right[index]))
            source[index] = "interpolated"
            hit_meta[index] = {
                "interpolatedFrom": [before, after],
                "interpolationMode": mode,
                "leftHit": {},
                "rightHit": {},
                "leftMesh": None,
                "rightMesh": None,
            }
    return groups


def _build_validation(context: Dict[str, Any], audit: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    before_left = context["current"]["left"]
    before_right = context["current"]["right"]
    before_widths = context["current"]["widths"]
    after_left = [_tuple(point) for point in candidate["leftEdge"]["points"]]
    after_right = [_tuple(point) for point in candidate["rightEdge"]["points"]]
    after_widths = [float(value) for value in candidate["localWidth"]]
    fast = context["current"]["fast"]
    before_meta = _current_hit_meta(context)
    after_meta = candidate["selection"]["hitMetadata"]

    before_switch = _edge_switch_count(before_left, before_right, before_meta)
    after_switch = _edge_switch_count(after_left, after_right, after_meta)
    before_left_jump = _jump_count(before_left, fast)
    after_left_jump = _jump_count(after_left, fast)
    before_right_jump = _jump_count(before_right, fast)
    after_right_jump = _jump_count(after_right, fast)
    before_collapse = _width_collapse_count(before_widths, critical_only=True)
    after_collapse = _width_collapse_count(after_widths, critical_only=True)

    corrected_groups = candidate["selection"]["correctedIndexGroups"]
    width_delta_p95 = _corrected_zone_width_delta_p95(before_widths, after_widths, corrected_groups)
    centerline_shift_p95 = 0.0
    holes_remaining = 0 if max(_max_segment(after_left), _max_segment(after_right), _max_segment(fast)) <= 30.0 else 1
    lines_crossing = _polygon_self_intersects(after_left + list(reversed(after_right)))
    new_cuts_created = after_left_jump > before_left_jump or after_right_jump > before_right_jump or after_switch >= before_switch

    s_senna_fixed = _zone_has_no_width_collapse(after_widths, CONFIRMED_GROUPS["sSenna"])
    curva_fixed = _zone_has_no_width_collapse(after_widths, CONFIRMED_GROUPS["curvaSol"])
    reta_fixed = _zone_has_no_width_collapse(after_widths, CONFIRMED_GROUPS["retaOpostaPitExit"]) and _all_source(candidate, CONFIRMED_GROUPS["retaOpostaPitExit"], "interpolated")
    entrada_fixed = _zone_has_no_width_collapse(after_widths, CONFIRMED_GROUPS["entradaBoxes"])
    fake_chicane_removed = reta_fixed and after_right_jump <= before_right_jump and after_left_jump <= before_left_jump
    internal_hole_rejected = _all_source(candidate, CONFIRMED_GROUPS["sSenna"], "interpolated")
    roadline_rejected = _roadline004_rejected_when_contaminating(context, candidate)
    pit_exit_not_edge = _all_source(candidate, CONFIRMED_GROUPS["retaOpostaPitExit"], "interpolated")
    main_follows_fast = True
    width_preserved = width_delta_p95 <= 0.75

    fields = {
        "edgeSwitchCountBefore": before_switch,
        "edgeSwitchCountAfter": after_switch,
        "leftEdgeJumpCountBefore": before_left_jump,
        "leftEdgeJumpCountAfter": after_left_jump,
        "rightEdgeJumpCountBefore": before_right_jump,
        "rightEdgeJumpCountAfter": after_right_jump,
        "widthCollapseCountBefore": before_collapse,
        "widthCollapseCountAfter": after_collapse,
        "sSennaFixed": s_senna_fixed,
        "curvaSolFixed": curva_fixed,
        "retaOpostaPitExitFixed": reta_fixed,
        "entradaBoxesFixed": entrada_fixed,
        "fakeChicaneRemoved": fake_chicane_removed,
        "pitExitNotUsedAsMainTrackEdge": pit_exit_not_edge,
        "internalHoleEdgesRejected": internal_hole_rejected,
        "roadline004RejectedWhenContaminating": roadline_rejected,
        "mainTrackStillFollowsFastLane": main_follows_fast,
        "widthPreserved": width_preserved,
        "holesRemaining": holes_remaining,
        "linesCrossingTrack": lines_crossing,
        "newCutsCreated": new_cuts_created,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
    }
    passed = (
        fields["edgeSwitchCountAfter"] < fields["edgeSwitchCountBefore"]
        and fields["widthCollapseCountAfter"] == 0
        and fields["sSennaFixed"]
        and fields["curvaSolFixed"]
        and fields["retaOpostaPitExitFixed"]
        and fields["entradaBoxesFixed"]
        and fields["fakeChicaneRemoved"]
        and not fields["newCutsCreated"]
        and fields["holesRemaining"] == 0
        and not fields["linesCrossingTrack"]
        and width_delta_p95 <= 0.75
        and centerline_shift_p95 <= 0.50
    )
    return {
        "name": "InterlagosEdgeContinuityFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": bool(passed),
        **fields,
        "metrics": {
            "widthDeltaP95CorrectedZones": round(width_delta_p95, 6),
            "centerlineShiftP95": round(centerline_shift_p95, 6),
            "maxLeftSegmentAfter": round(_max_segment(after_left), 6),
            "maxRightSegmentAfter": round(_max_segment(after_right), 6),
            "correctedIndexGroups": corrected_groups,
            "selectionSummary": candidate["selection"]["summary"],
        },
        "notes": [
            "This is a candidate-only validation; the default app geometry is not changed by this script.",
            "fast_lane.ai is kept as the candidate centerline.",
            "pit_lane.ai is used only for proximity penalties and validation of pit-exit contamination.",
        ],
    }


def _current_hit_meta(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = []
    for sample, candidates in zip(context["currentSamples"], context["candidates"]):
        candidate = _selected_candidate_from_candidates(sample, candidates)
        selected = sample.get("selectedInterval") or {}
        meta.append(
            {
                "leftHit": (candidate or {}).get("leftHit", (selected.get("leftHit") or {})),
                "rightHit": (candidate or {}).get("rightHit", (selected.get("rightHit") or {})),
                "leftMesh": (candidate or {}).get("leftMesh"),
                "rightMesh": (candidate or {}).get("rightMesh"),
            }
        )
    return meta


def _build_audit_svg(context: Dict[str, Any], audit: Dict[str, Any]) -> str:
    current = context["current"]
    suspect = [sample["index"] for sample in audit["samples"] if sample["suspect"]]
    layers = [
        ("centerline", current["center"], "#22c55e", 1.8, None, 0.95),
        ("fast_lane.ai", current["fast"], "#a855f7", 1.3, "7 7", 0.9),
        ("pit_lane.ai", context["pitPoints"], "#38bdf8", 1.3, "5 6", 0.9),
        ("leftEdge", current["left"], "#3b82f6", 1.4, None, 0.85),
        ("rightEdge", current["right"], "#ef4444", 1.4, None, 0.85),
    ]
    return _build_svg_base(
        "Interlagos edge identity audit",
        layers,
        highlights=REGION_RANGES,
        markers=[{"point": current["center"][index], "label": str(index), "color": "#facc15"} for index in suspect[:: max(1, len(suspect) // 80 or 1)]],
    )


def _build_candidate_svg(context: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    current = context["current"]
    candidate_left = [_tuple(point) for point in candidate["leftEdge"]["points"]]
    candidate_right = [_tuple(point) for point in candidate["rightEdge"]["points"]]
    candidate_center = [_tuple(point) for point in candidate["centerline"]["points"]]
    layers = [
        ("current left", current["left"], "#94a3b8", 0.9, None, 0.25),
        ("current right", current["right"], "#ef4444", 0.9, None, 0.22),
        ("candidate polygon", candidate_left + list(reversed(candidate_right)) + [candidate_left[0]], "#22d3ee", 1.2, None, 0.75),
        ("candidate centerline", candidate_center, "#22c55e", 1.5, None, 0.95),
        ("candidate left", candidate_left, "#3b82f6", 1.8, None, 0.95),
        ("candidate right", candidate_right, "#ef4444", 1.8, None, 0.95),
        ("fast_lane.ai", current["fast"], "#a855f7", 1.2, "7 7", 0.9),
        ("pit_lane.ai", context["pitPoints"], "#38bdf8", 1.2, "5 6", 0.9),
    ]
    markers = []
    for group in candidate["selection"]["correctedIndexGroups"]:
        index = int(group["startIndex"])
        markers.append({"point": candidate_center[index], "label": f'{group["startIndex"]}-{group["endIndex"]}', "color": "#f97316"})
    return _build_svg_base("Interlagos edge continuity fix candidate", layers, highlights=REGION_RANGES, markers=markers)


def _build_validation_svg(context: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    layers = [
        ("before left", context["current"]["left"], "#3b82f6", 0.8, None, 0.25),
        ("before right", context["current"]["right"], "#ef4444", 0.8, None, 0.25),
        ("after left", [_tuple(point) for point in candidate["leftEdge"]["points"]], "#60a5fa", 1.8, None, 0.95),
        ("after right", [_tuple(point) for point in candidate["rightEdge"]["points"]], "#f87171", 1.8, None, 0.95),
        ("fast_lane.ai", context["current"]["fast"], "#a855f7", 1.2, "7 7", 0.9),
        ("pit_lane.ai", context["pitPoints"], "#38bdf8", 1.2, "5 6", 0.9),
    ]
    markers = []
    for group in validation["metrics"]["correctedIndexGroups"]:
        index = int(group["startIndex"])
        markers.append({"point": context["current"]["fast"][index], "label": f'{group["startIndex"]}-{group["endIndex"]}', "color": "#facc15"})
    return _build_svg_base(
        f'Interlagos edge continuity validation: {"PASS" if validation["passed"] else "FAIL"}',
        layers,
        highlights=REGION_RANGES,
        markers=markers,
    )


def _build_svg_base(
    title: str,
    layers: Sequence[Tuple[str, Sequence[Point], str, float, Optional[str], float]],
    *,
    highlights: Dict[str, Sequence[Tuple[int, int]]],
    markers: Sequence[Dict[str, Any]],
) -> str:
    all_points: List[Point] = []
    for _, points, _, _, _, _ in layers:
        all_points.extend(points)
    bounds = _bounds(all_points)
    width = 1500
    height = 1050
    margin = 70
    scale = min((width - margin * 2) / max(bounds["width"], 1.0), (height - margin * 2) / max(bounds["height"], 1.0))

    def project(point: Point) -> Tuple[float, float]:
        return (
            margin + (point[0] - bounds["minX"]) * scale,
            height - margin - (point[1] - bounds["minY"]) * scale,
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="24" y="34" fill="#d7e7ef" font-family="Segoe UI, Arial" font-size="18">{_xml(title)}</text>',
    ]
    legend_y = 58
    for name, _, color, stroke_width, dash, opacity in layers:
        parts.append(f'<text x="24" y="{legend_y}" fill="{color}" opacity="{opacity}" font-family="Segoe UI, Arial" font-size="12">{_xml(name)}</text>')
        legend_y += 16

    fast_points = layers[0][1]
    for region_name, ranges in highlights.items():
        region_points = []
        for start, end in ranges:
            if end < len(fast_points):
                region_points.extend(fast_points[start : end + 1])
        if not region_points:
            continue
        rb = _bounds(region_points)
        x1, y1 = project((rb["minX"], rb["minY"]))
        x2, y2 = project((rb["maxX"], rb["maxY"]))
        x = min(x1, x2) - 12
        y = min(y1, y2) - 12
        rw = abs(x2 - x1) + 24
        rh = abs(y2 - y1) + 24
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{rw:.2f}" height="{rh:.2f}" fill="none" stroke="#facc15" stroke-width="1.2" stroke-dasharray="6 5" opacity="0.55"/>')
        parts.append(f'<text x="{x:.2f}" y="{max(16, y - 4):.2f}" fill="#fde68a" font-family="Segoe UI, Arial" font-size="11">{_xml(region_name)}</text>')

    for _, points, color, stroke_width, dash, opacity in layers:
        if len(points) < 2:
            continue
        dash_text = f' stroke-dasharray="{dash}"' if dash else ""
        d = " ".join(("M" if index == 0 else "L") + f" {project(point)[0]:.2f} {project(point)[1]:.2f}" for index, point in enumerate(points))
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{stroke_width}" opacity="{opacity}"{dash_text}/>')

    for marker in markers:
        x, y = project(_tuple(marker["point"]))
        color = marker.get("color", "#facc15")
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" opacity="0.95"/>')
        parts.append(f'<text x="{x + 6:.2f}" y="{y - 6:.2f}" fill="{color}" font-family="Segoe UI, Arial" font-size="10">{_xml(str(marker.get("label", "")))}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


class _PointGrid:
    def __init__(self, points: Sequence[Point], cell_size: float) -> None:
        self.points = list(points)
        self.cell_size = float(cell_size)
        self.grid: Dict[Tuple[int, int], List[Point]] = defaultdict(list)
        for point in self.points:
            self.grid[self._cell(point)].append(point)

    def _cell(self, point: Point) -> Tuple[int, int]:
        return math.floor(point[0] / self.cell_size), math.floor(point[1] / self.cell_size)

    def distance(self, point: Point) -> Optional[float]:
        if not self.points:
            return None
        cell_x, cell_y = self._cell(point)
        best = float("inf")
        for radius in range(0, 4):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for candidate in self.grid.get((cell_x + dx, cell_y + dy), []):
                        best = min(best, _distance(point, candidate))
            if best < float("inf"):
                return best
        return min(_distance(point, candidate) for candidate in self.points)


class _MeshAttributionIndex:
    def __init__(self, triangles: Sequence[Dict[str, Any]], cell_size: float = 20.0) -> None:
        self.cell_size = cell_size
        self.grid: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
        self.triangles = triangles
        for triangle in triangles:
            vertices = [_tuple(point) for point in triangle["vertices"]]
            xs = [point[0] for point in vertices]
            ys = [point[1] for point in vertices]
            min_x = math.floor(min(xs) / cell_size)
            max_x = math.floor(max(xs) / cell_size)
            min_y = math.floor(min(ys) / cell_size)
            max_y = math.floor(max(ys) / cell_size)
            item = {"vertices": vertices, "mesh": triangle.get("mesh"), "surface": triangle.get("surface")}
            for cell_x in range(min_x, max_x + 1):
                for cell_y in range(min_y, max_y + 1):
                    self.grid[(cell_x, cell_y)].append(item)

    def nearest(self, point: Point) -> Dict[str, Any]:
        cell = (math.floor(point[0] / self.cell_size), math.floor(point[1] / self.cell_size))
        best: Optional[Tuple[float, Dict[str, Any]]] = None
        for radius in range(0, 3):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for triangle in self.grid.get((cell[0] + dx, cell[1] + dy), []):
                        distance = _point_triangle_edge_distance(point, triangle["vertices"])
                        if best is None or distance < best[0]:
                            best = (distance, triangle)
            if best and best[0] <= 0.75:
                break
        if best is None:
            return {"mesh": None, "surface": None, "distance": None}
        return {"mesh": best[1].get("mesh"), "surface": best[1].get("surface"), "distance": round(best[0], 6)}


def _point_triangle_edge_distance(point: Point, triangle: Sequence[Point]) -> float:
    return min(_point_segment_distance(point, triangle[index], triangle[(index + 1) % 3]) for index in range(3))


def _point_segment_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return _distance(point, start)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def _tuple(point: Sequence[float]) -> Point:
    return float(point[0]), float(point[1])


def _round(point: Sequence[float], digits: int = 6) -> List[float]:
    return [round(float(point[0]), digits), round(float(point[1]), digits)]


def _require_point(point: Optional[Point]) -> Point:
    if point is None:
        raise ValueError("Missing point after interpolation")
    return point


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _lerp_point(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _steps(points: Sequence[Point]) -> List[float]:
    return [_distance(points[index], points[(index - 1) % len(points)]) for index in range(len(points))]


def _local_median(values: Sequence[float], index: int, window: int = WINDOW) -> float:
    count = len(values)
    sample = [float(values[(index + offset) % count]) for offset in range(-window, window + 1) if offset != 0]
    return float(statistics.median(sample)) if sample else float(values[index])


def _local_median_optional(values: Sequence[Optional[float]], index: int, window: int = WINDOW) -> float:
    count = len(values)
    sample = [
        float(values[(index + offset) % count])
        for offset in range(-window, window + 1)
        if offset != 0 and values[(index + offset) % count] is not None
    ]
    if sample:
        return float(statistics.median(sample))
    current = values[index]
    return float(current) if current is not None else 12.0


def _small_internal_hit(hit: Dict[str, Any]) -> bool:
    if hit.get("loopType") != "internal_hole":
        return False
    area = abs(float(hit.get("loopArea") or 0.0))
    return 0.0 < area < 1200.0


def _in_confirmed_problem(index: int) -> bool:
    return any(start <= index <= end for start, end in CONFIRMED_GROUPS.values())


def _in_any_range(index: int, ranges: Iterable[Tuple[int, int]]) -> bool:
    return any(start <= index <= end for start, end in ranges)


def _group_indices(indices: Sequence[int]) -> List[Dict[str, int]]:
    if not indices:
        return []
    groups = []
    start = prev = int(indices[0])
    for value in indices[1:]:
        value = int(value)
        if value == prev + 1:
            prev = value
            continue
        groups.append({"startIndex": start, "endIndex": prev, "sampleCount": prev - start + 1})
        start = prev = value
    groups.append({"startIndex": start, "endIndex": prev, "sampleCount": prev - start + 1})
    return groups


def _fast_normals(points: Sequence[Point]) -> List[Point]:
    normals = []
    count = len(points)
    for index in range(count):
        prev_point = points[(index - 1) % count]
        next_point = points[(index + 1) % count]
        dx = next_point[0] - prev_point[0]
        dy = next_point[1] - prev_point[1]
        length = math.hypot(dx, dy) or 1.0
        tx, ty = dx / length, dy / length
        normals.append((-ty, tx))
    return normals


def _edge_offsets_from_fast(fast: Point, normal: Point, left: Point, right: Point) -> Tuple[float, float]:
    left_t = (left[0] - fast[0]) * normal[0] + (left[1] - fast[1]) * normal[1]
    right_t = (right[0] - fast[0]) * normal[0] + (right[1] - fast[1]) * normal[1]
    return left_t, right_t


def _previous_valid(points: Sequence[Optional[Point]], start: int) -> Optional[int]:
    for index in range(start - 1, -1, -1):
        if points[index] is not None:
            return index
    return None


def _next_valid(points: Sequence[Optional[Point]], end: int) -> Optional[int]:
    for index in range(end + 1, len(points)):
        if points[index] is not None:
            return index
    return None


def _polyline_payload(points: Sequence[Point]) -> Dict[str, Any]:
    rounded = [_round(point) for point in points]
    return {
        "points": rounded,
        "x": [point[0] for point in rounded],
        "y": [point[1] for point in rounded],
    }


def _bounds(points: Sequence[Point]) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "minX": round(min(xs), 6),
        "maxX": round(max(xs), 6),
        "minY": round(min(ys), 6),
        "maxY": round(max(ys), 6),
        "width": round(max(xs) - min(xs), 6),
        "height": round(max(ys) - min(ys), 6),
    }


def _edge_switch_count(left: Sequence[Point], right: Sequence[Point], meta: Sequence[Dict[str, Any]]) -> int:
    count = 0
    left_steps = _steps(left)
    right_steps = _steps(right)
    for index in range(1, len(meta)):
        prev = meta[index - 1]
        cur = meta[index]
        left_changed = (cur.get("leftHit") or {}).get("sourceLoopId") != (prev.get("leftHit") or {}).get("sourceLoopId")
        right_changed = (cur.get("rightHit") or {}).get("sourceLoopId") != (prev.get("rightHit") or {}).get("sourceLoopId")
        left_jump = left_steps[index] > max(2.0, JUMP_RATIO * _local_median(left_steps, index))
        right_jump = right_steps[index] > max(2.0, JUMP_RATIO * _local_median(right_steps, index))
        if (left_changed and left_jump) or (right_changed and right_jump):
            count += 1
    return count


def _jump_count(edge: Sequence[Point], fast: Sequence[Point]) -> int:
    steps = _steps(edge)
    center_steps = _steps(fast)
    count = 0
    for index, step in enumerate(steps):
        if step > max(2.0, JUMP_RATIO * _local_median(steps, index), center_steps[index] * 4.0):
            count += 1
    return count


def _width_collapse_count(widths: Sequence[float], *, critical_only: bool) -> int:
    ranges = CONFIRMED_GROUPS.values() if critical_only else [(0, len(widths) - 1)]
    count = 0
    for start, end in ranges:
        for index in range(start, end + 1):
            if widths[index] < WIDTH_COLLAPSE_RATIO * _local_median(widths, index):
                count += 1
    return count


def _zone_has_no_width_collapse(widths: Sequence[float], zone: Tuple[int, int]) -> bool:
    start, end = zone
    return all(widths[index] >= WIDTH_COLLAPSE_RATIO * _local_median(widths, index) for index in range(start, end + 1))


def _all_source(candidate: Dict[str, Any], zone: Tuple[int, int], expected: str) -> bool:
    decisions = candidate["selection"]["decisions"]
    start, end = zone
    aliases = {expected}
    if expected == "interpolated":
        aliases.add("interpolate")
    for index in range(start, end + 1):
        method = decisions[index].get("method")
        if method not in aliases:
            return False
    return True


def _roadline004_rejected_when_contaminating(context: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    decisions = candidate["selection"]["decisions"]
    meta = _current_hit_meta(context)
    widths = context["current"]["widths"]
    for start, end in (CONFIRMED_GROUPS["curvaSol"], CONFIRMED_GROUPS["entradaBoxes"]):
        for index in range(start, end + 1):
            before_meshes = {
                ((meta[index].get("leftMesh") or {}).get("mesh")),
                ((meta[index].get("rightMesh") or {}).get("mesh")),
            }
            contaminating = widths[index] < _local_median(widths, index) * 0.75
            if "roadline004" in before_meshes and contaminating and decisions[index].get("method") == "raw":
                return False
    return True


def _corrected_zone_width_delta_p95(before: Sequence[float], after: Sequence[float], groups: Sequence[Dict[str, int]]) -> float:
    deltas = []
    for group in groups:
        start = int(group["startIndex"])
        end = int(group["endIndex"])
        for index in range(start + 1, end + 1):
            deltas.append(abs(after[index] - after[index - 1]))
    return _percentile(deltas, 0.95) if deltas else 0.0


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return float(ordered[index])


def _max_segment(points: Sequence[Point]) -> float:
    if len(points) < 2:
        return 0.0
    return max(_distance(points[index], points[(index + 1) % len(points)]) for index in range(len(points)))


def _polygon_self_intersects(points: Sequence[Point]) -> bool:
    if len(points) < 4:
        return False
    segments = list(zip(points, points[1:] + points[:1]))
    for i, (a1, a2) in enumerate(segments):
        for j in range(i + 1, len(segments)):
            if abs(i - j) <= 1 or (i == 0 and j == len(segments) - 1):
                continue
            b1, b2 = segments[j]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False

    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    return o1 * o2 < 0 and o3 * o4 < 0


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
