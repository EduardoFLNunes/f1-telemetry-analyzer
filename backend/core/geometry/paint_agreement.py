"""Check the extracted track edges against the painted limit lines.

The white lines the circuit is painted with are the official track limit, and
they come out of the KN5 as marking geometry. That makes them a source of truth
independent of both the raycast extraction and any hand-authored geometry, so
they can say whether an extracted edge is actually in the right place.

They cannot *build* the edge: at Interlagos the usable paint covers only 18% of
the lap on the left and 7% on the right, so reconstructing from it would mean
interpolating most of the track blind. Verification is what the coverage
supports, and correcting what verification finds is
[paint_edge_correction][core.geometry.paint_edge_correction]'s job.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .paint_boundary_rings import (
    BOUNDARY_RATIO_RANGE,
    MAX_BOUNDARY_RATIO_SPREAD,
    build_track_frame,
    identify_boundary_rings,
)

# Below this there is too little paint on a side to say anything.
MIN_SIDE_COVERAGE_PERCENT = 3.0
# How far the edge may sit from the paint before it is called out.
AGREEMENT_RATIO_RANGE = (0.90, 1.10)


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
    frame = build_track_frame(track_data)
    has_paint = bool(((track_data.get("markingGeometry") or {}).get("polygons")))
    if frame is None or not has_paint:
        return {
            "status": "UNAVAILABLE",
            "reason": "no_centerline" if frame is None else "no_marking_geometry",
            "boundaryGroups": 0,
            "measuredSides": 0,
            "sides": {},
            "issues": [],
        }

    # Loose thresholds on purpose. Identification must not double as judgement:
    # with a tight range a genuinely wrong edge gets reclassified as "not a
    # boundary" and passes silently, which is exactly what a 20% narrowing did.
    rings = identify_boundary_rings(track_data, frame)
    half = frame.half_widths

    collected: Dict[str, Dict[str, List[np.ndarray]]] = {
        "left": {"indices": [], "ratios": []},
        "right": {"indices": [], "ratios": []},
    }
    for ring in rings:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratios = np.abs(ring.offsets) / np.where(half[ring.indices] > 0, half[ring.indices], np.nan)
        collected[ring.side]["indices"].append(ring.indices)
        collected[ring.side]["ratios"].append(ratios)

    sides: Dict[str, Any] = {}
    issues: List[str] = []
    measured_sides = 0
    for side, values in collected.items():
        if not values["indices"]:
            sides[side] = {"points": 0, "coveragePercent": 0.0, "ratioMedian": None, "ratioSpread": None}
            continue
        summary = _side_summary(
            np.concatenate(values["indices"]),
            np.concatenate(values["ratios"]),
            len(frame.center),
        )
        if summary["coveragePercent"] >= MIN_SIDE_COVERAGE_PERCENT:
            measured_sides += 1
            low, high = AGREEMENT_RATIO_RANGE
            if not (low <= summary["ratioMedian"] <= high):
                issues.append(f"{side} edge sits at {summary['ratioMedian']:.2f} of the painted limit")
        sides[side] = summary

    if not measured_sides:
        status = "INSUFFICIENT_PAINT"
    elif issues:
        status = "DIVERGENT"
    else:
        status = "OK"

    return {
        "status": status,
        "boundaryGroups": len(rings),
        "measuredSides": measured_sides,
        "sides": sides,
        "issues": issues,
        "thresholds": {
            "agreementRatio": list(AGREEMENT_RATIO_RANGE),
            "minSideCoveragePercent": MIN_SIDE_COVERAGE_PERCENT,
            "boundaryRatio": list(BOUNDARY_RATIO_RANGE),
            "maxBoundaryRatioSpread": MAX_BOUNDARY_RATIO_SPREAD,
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
