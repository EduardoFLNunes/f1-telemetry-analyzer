"""Measure the pit corridor's width from the paint instead of assuming it.

The corridor arrives from the pit lane builder at a flat 7.5 m for its whole
length -- minimum, median and maximum identical across all 726 samples, because
the width is a constant in the builder rather than anything read off the track.
The circuit paints the lane it means, and at Interlagos that paint says 5.3 m.

Only geometries whose declared width never varies are touched. A constant width
is the signature of an assumed one; a measured width has a distribution. That
also keeps this away from the entry and exit accesses, whose edges the asphalt
merge fills reuse -- moving those would tear the fill off the main track.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# A reading has to be a plausible lane edge, measured against the width the
# builder assumed.
MIN_HALF_RATIO = 0.35
MAX_HALF_RATIO = 2.0
# Same discipline as the main track edges: agree with your neighbours, and do
# not step.
NEIGHBOURHOOD_METERS = 25.0
MAX_DEVIATION_METERS = 1.2
MIN_NEIGHBOURS = 5
MAX_RATE = 0.12
# Below this the paint agrees with the builder closely enough to leave alone.
MIN_ADJUSTMENT_METERS = 0.25
CORRECTION_MARKER = "pitCorridorWidth"


def _points_of(obj: Any) -> Optional[np.ndarray]:
    if not isinstance(obj, dict):
        return None
    if "x" in obj and "y" in obj:
        x, y = obj.get("x") or [], obj.get("y") or []
        if len(x) != len(y) or len(x) < 2:
            return None
        return np.column_stack([np.array(x, dtype=float), np.array(y, dtype=float)])
    points = obj.get("points")
    if isinstance(points, list) and len(points) >= 2:
        array = np.array(points, dtype=float)
        return array[:, :2] if array.ndim == 2 else None
    return None


def _as_payload(points: np.ndarray) -> Dict[str, Any]:
    return {
        "points": [[float(x), float(y)] for x, y in points],
        "x": [float(v) for v in points[:, 0]],
        "y": [float(v) for v in points[:, 1]],
    }


def _lateral_normals(center: np.ndarray) -> np.ndarray:
    tangent = np.gradient(center, axis=0)
    length = np.sqrt((tangent ** 2).sum(axis=1, keepdims=True))
    tangent = tangent / np.maximum(length, 1e-9)
    return np.column_stack([-tangent[:, 1], tangent[:, 0]])


def _arc_length(center: np.ndarray) -> np.ndarray:
    steps = np.sqrt((np.diff(center, axis=0) ** 2).sum(axis=1))
    return np.concatenate([[0.0], np.cumsum(steps)])


def _marking_segments(track_data: Dict[str, Any]) -> np.ndarray:
    starts, ends = [], []
    for polygon in ((track_data.get("markingGeometry") or {}).get("polygons")) or []:
        rings = polygon.get("rings")
        if not rings and isinstance(polygon.get("points"), list):
            rings = [polygon["points"]]
        for ring in rings or []:
            points = np.array(ring, dtype=float)
            if points.ndim != 2 or len(points) < 2:
                continue
            points = points[:, :2]
            closed = np.vstack([points, points[:1]])
            starts.append(closed[:-1])
            ends.append(closed[1:])
    if not starts:
        return np.empty((0, 2, 2), dtype=float)
    return np.stack([np.vstack(starts), np.vstack(ends)], axis=1)


def _cast(center: np.ndarray, normals: np.ndarray, segments: np.ndarray,
          half: np.ndarray) -> Dict[str, np.ndarray]:
    """Nearest marking each side of the corridor, in metres from its centreline."""
    profile = {"left": np.full(len(center), np.nan), "right": np.full(len(center), np.nan)}
    if not len(segments):
        return profile
    seg_a = segments[:, 0, :]
    edge = segments[:, 1, :] - seg_a

    for index, (origin, normal) in enumerate(zip(center, normals)):
        near, far = half[index] * MIN_HALF_RATIO, half[index] * MAX_HALF_RATIO
        reachable = ((np.abs(seg_a[:, 0] - origin[0]) < far + 4.0)
                     & (np.abs(seg_a[:, 1] - origin[1]) < far + 4.0))
        if not reachable.any():
            continue
        a, e = seg_a[reachable], edge[reachable]
        rel = a - origin
        for side, sign in (("left", 1.0), ("right", -1.0)):
            direction = normal * sign
            denom = direction[0] * e[:, 1] - direction[1] * e[:, 0]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (rel[:, 0] * e[:, 1] - rel[:, 1] * e[:, 0]) / denom
                u = (rel[:, 0] * direction[1] - rel[:, 1] * direction[0]) / denom
            hit = np.isfinite(t) & (u >= 0.0) & (u <= 1.0) & (t >= near) & (t <= far)
            if hit.any():
                profile[side][index] = float(t[hit].min())
    return profile


def _steady(values: np.ndarray, arc: np.ndarray) -> np.ndarray:
    """Drop readings that disagree with the paint either side of them."""
    out = np.full_like(values, np.nan)
    known = np.where(~np.isnan(values))[0]
    for index in known:
        window = known[np.abs(arc[known] - arc[index]) <= NEIGHBOURHOOD_METERS]
        if len(window) < MIN_NEIGHBOURS:
            continue
        if abs(values[index] - float(np.median(values[window]))) <= MAX_DEVIATION_METERS:
            out[index] = values[index]
    return out


def _fill_and_smooth(measured: np.ndarray, fallback: np.ndarray, arc: np.ndarray) -> np.ndarray:
    """Interpolate across unpainted gaps, then stop the result from stepping."""
    known = np.where(~np.isnan(measured))[0]
    if not len(known):
        return fallback.copy()
    filled = np.interp(arc, arc[known], measured[known])

    for index in range(1, len(filled)):
        run = max(arc[index] - arc[index - 1], 1e-6)
        filled[index] = min(filled[index], filled[index - 1] + MAX_RATE * run)
        filled[index] = max(filled[index], filled[index - 1] - MAX_RATE * run)
    for index in range(len(filled) - 2, -1, -1):
        run = max(arc[index + 1] - arc[index], 1e-6)
        filled[index] = min(filled[index], filled[index + 1] + MAX_RATE * run)
        filled[index] = max(filled[index], filled[index + 1] - MAX_RATE * run)
    return filled


def _assumed_width(geometry: Dict[str, Any]) -> Optional[np.ndarray]:
    """The declared width, but only when it never varies."""
    widths = geometry.get("width")
    if not isinstance(widths, list) or len(widths) < 2:
        return None
    array = np.array(widths, dtype=float)
    if not np.isfinite(array).all():
        return None
    if float(array.max() - array.min()) > 1e-6:
        return None
    return array


def correct_pit_corridor_from_markings(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild constant-width pit geometry against the painted lane. Mutates track_data."""
    metadata = track_data.setdefault("metadata", {})
    if isinstance(metadata, dict) and metadata.get(CORRECTION_MARKER):
        return {"status": "ALREADY_APPLIED", **{
            key: value for key, value in metadata[CORRECTION_MARKER].items() if key != "status"
        }}

    geometries = ((track_data.get("pitVisualGeometry") or {}).get("geometries")) or {}
    if not geometries:
        return {"status": "NO_PIT_GEOMETRY", "corrected": {}}

    segments = _marking_segments(track_data)
    if not len(segments):
        return {"status": "NO_MARKINGS", "corrected": {}}

    corrected: Dict[str, Any] = {}
    skipped: List[str] = []
    for name, geometry in geometries.items():
        assumed = _assumed_width(geometry)
        center = _points_of(geometry.get("centerline"))
        if assumed is None or center is None or len(center) != len(assumed):
            skipped.append(name)
            continue

        half = assumed / 2.0
        normals = _lateral_normals(center)
        arc = _arc_length(center)
        profile = _cast(center, normals, segments, half)

        sides = {}
        for side in ("left", "right"):
            steady = _steady(profile[side], arc)
            sides[side] = {
                "measured": steady,
                "readings": int((~np.isnan(steady)).sum()),
            }
        if not any(sides[side]["readings"] for side in sides):
            skipped.append(name)
            continue

        left_half = _fill_and_smooth(sides["left"]["measured"], half, arc)
        right_half = _fill_and_smooth(sides["right"]["measured"], half, arc)
        width = left_half + right_half
        if float(np.median(np.abs(width - assumed))) < MIN_ADJUSTMENT_METERS:
            skipped.append(name)
            continue

        left_edge = center + normals * left_half[:, None]
        right_edge = center - normals * right_half[:, None]
        geometry["leftEdge"] = _as_payload(left_edge)
        geometry["rightEdge"] = _as_payload(right_edge)
        geometry["outerEdge"] = _as_payload(left_edge)
        geometry["innerEdge"] = _as_payload(right_edge)
        geometry["polygon"] = _as_payload(np.vstack([left_edge, right_edge[::-1]]))
        geometry["width"] = [float(value) for value in width]
        geometry["widthSource"] = "marking_geometry"

        corrected[name] = {
            "samples": int(len(center)),
            "readingsLeft": sides["left"]["readings"],
            "readingsRight": sides["right"]["readings"],
            "assumedWidth": round(float(assumed[0]), 3),
            "measuredWidthMedian": round(float(np.median(width)), 3),
            "measuredWidthMin": round(float(width.min()), 3),
            "measuredWidthMax": round(float(width.max()), 3),
        }

    if not corrected:
        return {"status": "NO_CHANGE", "corrected": {}, "skipped": skipped}

    report = {"status": "CORRECTED", "corrected": corrected, "skipped": skipped}
    for name, detail in corrected.items():
        logger.info(
            "Pit geometry %s width measured from paint: %.2f m assumed -> %.2f m median",
            name, detail["assumedWidth"], detail["measuredWidthMedian"],
        )
    if isinstance(metadata, dict):
        metadata[CORRECTION_MARKER] = report
    return report


__all__ = ["correct_pit_corridor_from_markings"]
