"""Check the extracted track edges against the painted limit lines.

The white lines the circuit is painted with are the official track limit, and
they come out of the KN5 as marking geometry. That makes them a source of truth
independent of both the raycast extraction and any hand-authored geometry, so
they can say whether an extracted edge is actually in the right place.

They cannot *build* the edge: at Interlagos the usable paint covers only 18% of
the lap on the left and 7% on the right, so reconstructing from it would mean
interpolating most of the track blind. Verification is what the coverage
supports.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

# A boundary line runs at one half-width from the centre, and holds that
# relationship along its length. Pit and service markings sit at 2.7 to 12.4
# half-widths and wander, so the spread is what separates them -- a group can
# show a plausible median ratio while mixing sides, which the median alone
# cannot catch.
# Deliberately loose: this only has to exclude paint that is nowhere near the
# edge. Judging agreement with the same range as identification would let a
# genuinely wrong edge be reclassified as "not a boundary" and pass silently --
# a 20% narrowing did exactly that before this was widened.
BOUNDARY_RATIO_RANGE = (0.5, 2.0)
MAX_BOUNDARY_RATIO_SPREAD = 0.25
MIN_GROUP_POINTS = 20
# Below this there is too little paint on a side to say anything.
MIN_SIDE_COVERAGE_PERCENT = 3.0
# How far the edge may sit from the paint before it is called out.
AGREEMENT_RATIO_RANGE = (0.90, 1.10)


def _centerline_arrays(track_data: Dict[str, Any]):
    centerline = track_data.get("centerline") or []
    if not centerline:
        return None, None, None
    points, normals = [], []
    for point in centerline:
        if isinstance(point, dict):
            x, z = point.get("x"), point.get("z")
            normal = point.get("normal") or {}
            nx, nz = normal.get("x"), normal.get("z")
        else:
            x, z = getattr(point, "x", None), getattr(point, "z", None)
            normal = getattr(point, "normal", (0.0, 1.0))
            nx, nz = normal[0], normal[1]
        if x is None or z is None or nx is None or nz is None:
            continue
        points.append([float(x), -float(z)])
        normals.append([float(nx), -float(nz)])
    widths = np.array(track_data.get("localWidth") or [], dtype=float)
    if len(points) < 2 or not len(widths):
        return None, None, None
    return np.array(points, dtype=float), np.array(normals, dtype=float), widths


def _side_summary(indices: np.ndarray, ratios: np.ndarray, total_points: int) -> Dict[str, Any]:
    coverage = len(np.unique(indices)) / max(total_points, 1) * 100.0
    return {
        "points": int(len(indices)),
        "coveragePercent": round(float(coverage), 2),
        "ratioMedian": round(float(np.median(ratios)), 4),
        "ratioSpread": round(float(np.std(ratios)), 4),
    }


def evaluate_paint_agreement(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """How closely the extracted edges follow the painted limit lines."""
    center, normals, widths = _centerline_arrays(track_data)
    groups = ((track_data.get("markingGeometry") or {}).get("polygons")) or []
    if center is None or not groups:
        return {
            "status": "UNAVAILABLE",
            "reason": "no_centerline" if center is None else "no_marking_geometry",
            "sides": {},
            "issues": [],
        }

    per_side: Dict[str, Dict[str, List[np.ndarray]]] = {
        "left": {"indices": [], "ratios": []},
        "right": {"indices": [], "ratios": []},
    }
    boundary_groups = 0

    for group in groups:
        rings = group.get("rings") or ([group["points"]] if group.get("points") else [])
        if not rings:
            continue
        points = np.array(rings[0], dtype=float)
        if len(points) < MIN_GROUP_POINTS:
            continue
        deltas = points[:, None, :] - center[None, :, :]
        nearest = np.sqrt((deltas * deltas).sum(axis=2)).argmin(axis=1)
        offsets = ((points - center[nearest]) * normals[nearest]).sum(axis=1)
        half = np.where(widths[nearest] > 0, widths[nearest] / 2.0, np.nan)
        ratios = np.abs(offsets) / half

        for side, mask in (("left", offsets < 0), ("right", offsets > 0)):
            if mask.sum() < MIN_GROUP_POINTS:
                continue
            side_ratios = ratios[mask]
            median = float(np.nanmedian(side_ratios))
            spread = float(np.nanstd(side_ratios))
            if not (BOUNDARY_RATIO_RANGE[0] <= median <= BOUNDARY_RATIO_RANGE[1]):
                continue
            if spread >= MAX_BOUNDARY_RATIO_SPREAD:
                continue
            boundary_groups += 1
            per_side[side]["indices"].append(nearest[mask])
            per_side[side]["ratios"].append(side_ratios)

    sides: Dict[str, Any] = {}
    issues: List[str] = []
    measured_sides = 0
    for side, collected in per_side.items():
        if not collected["indices"]:
            sides[side] = {"points": 0, "coveragePercent": 0.0, "ratioMedian": None, "ratioSpread": None}
            continue
        indices = np.concatenate(collected["indices"])
        ratios = np.concatenate(collected["ratios"])
        summary = _side_summary(indices, ratios, len(center))
        if summary["coveragePercent"] >= MIN_SIDE_COVERAGE_PERCENT:
            measured_sides += 1
            low, high = AGREEMENT_RATIO_RANGE
            if not (low <= summary["ratioMedian"] <= high):
                issues.append(
                    f"{side} edge sits at {summary['ratioMedian']:.2f} of the painted limit"
                )
        sides[side] = summary

    if not measured_sides:
        status = "INSUFFICIENT_PAINT"
    elif issues:
        status = "DIVERGENT"
    else:
        status = "OK"

    return {
        "status": status,
        "boundaryGroups": boundary_groups,
        "measuredSides": measured_sides,
        "sides": sides,
        "issues": issues,
        "thresholds": {
            "agreementRatio": list(AGREEMENT_RATIO_RANGE),
            "minSideCoveragePercent": MIN_SIDE_COVERAGE_PERCENT,
        },
    }


_last_fingerprint: Optional[tuple] = None
_last_result: Optional[Dict[str, Any]] = None


def _fingerprint(track_data: Dict[str, Any]) -> tuple:
    groups = ((track_data.get("markingGeometry") or {}).get("polygons")) or []
    return (
        track_data.get("trackName") or track_data.get("name"),
        track_data.get("trackConfig"),
        track_data.get("generatedAt"),
        len(track_data.get("centerline") or []),
        len(groups),
    )


def evaluate_paint_agreement_cached(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same answer, computed once per loaded track.

    The full evaluation is ~0.2s on Interlagos, and the data-quality payload it
    feeds is polled continuously, so running it per request would stall the
    event loop. The result only changes when the geometry does.
    """
    global _last_fingerprint, _last_result
    fingerprint = _fingerprint(track_data)
    if fingerprint != _last_fingerprint or _last_result is None:
        _last_result = evaluate_paint_agreement(track_data)
        _last_fingerprint = fingerprint
    return _last_result


def reset_paint_agreement_cache() -> None:
    global _last_fingerprint, _last_result
    _last_fingerprint = None
    _last_result = None


__all__ = [
    "evaluate_paint_agreement",
    "evaluate_paint_agreement_cached",
    "reset_paint_agreement_cache",
]
