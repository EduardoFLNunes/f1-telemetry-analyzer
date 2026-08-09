"""Reject edge readings the track cannot physically have.

The interval raycast decides where the track ends one sample at a time, and
where it picks the wrong interval -- catching a run-off, or the apron beside the
road -- the edge steps outward for a stretch and back. On the map that reads as
blocks glued to the side of the band, which is what Interlagos draws at 300 m
and at 2100 m.

Two things make those blocks findable, and both were missing from the first
attempt at this:

Judge each side on its own. A block juts out on one side only, so the total
width dilutes it: a 6 m protrusion on a 13 m track is a 46% change in width but
a 92% change in that edge's offset.

Judge it against enough track. A block runs 20 to 30 m, so a 45 m window
contains mostly block and its median moves with the defect. Measured against
180 m the block cannot shift the reference it is being compared to.

What separates a block from a genuinely wide corner is how long it lasts. A
protrusion that persists for 100 m is the track; one that appears and vanishes
inside 60 m is the raycast losing the edge.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Long enough that a block cannot move the median it is judged against.
NEIGHBOURHOOD_METERS = 180.0
MIN_NEIGHBOURS = 25
# A protrusion has to clear both to count: a fraction of the local offset, and
# an absolute floor so narrow tracks are not over-corrected.
MAX_DEVIATION_RATIO = 0.30
MIN_DEVIATION_METERS = 1.0
# Past this length the wide stretch is the track, not a misread.
MAX_BLOCK_METERS = 60.0
# The shipped hand-authored geometry moves each edge by about 0.11 m per metre
# at its 99th percentile.
MAX_RATE = 0.15


def _distances(track_data: Dict[str, Any], count: int) -> np.ndarray:
    values = []
    for point in track_data.get("centerline") or []:
        values.append(float(point.get("distance", 0.0)) if isinstance(point, dict)
                      else float(getattr(point, "distance", 0.0)))
    if len(values) == count and values[-1] > 0:
        return np.array(values, dtype=float)
    return np.arange(count, dtype=float)


def _frame(track_data: Dict[str, Any], count: int) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    center, normals = [], []
    for point in track_data.get("centerline") or []:
        if isinstance(point, dict):
            x, z = point.get("x"), point.get("z")
            normal = point.get("normal") or {}
            nx, nz = normal.get("x"), normal.get("z")
        else:
            x, z = getattr(point, "x", None), getattr(point, "z", None)
            normal = getattr(point, "normal", None) or (0.0, 1.0)
            nx, nz = normal[0], normal[1]
        if x is None or z is None or nx is None or nz is None:
            return None
        center.append([float(x), -float(z)])
        normals.append([float(nx), -float(nz)])
    if len(center) != count:
        return None
    return np.array(center, dtype=float), np.array(normals, dtype=float)


def _edge_offsets(edge: List[Dict[str, Any]], center: np.ndarray, normals: np.ndarray) -> Optional[np.ndarray]:
    points = []
    for entry in edge:
        if not isinstance(entry, dict):
            return None
        points.append([float(entry["x"]), -float(entry.get("z", entry.get("y", 0.0)))])
    array = np.array(points, dtype=float)
    if len(array) != len(center):
        return None
    return ((array - center) * normals).sum(axis=1)


def _runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    out, start = [], None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            out.append((start, index - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def _limit_rate(values: np.ndarray, distance: np.ndarray) -> np.ndarray:
    limited = values.copy()
    for index in range(1, len(limited)):
        run = max(distance[index] - distance[index - 1], 1e-6)
        limited[index] = min(limited[index], limited[index - 1] + MAX_RATE * run)
    for index in range(len(limited) - 2, -1, -1):
        run = max(distance[index + 1] - distance[index], 1e-6)
        limited[index] = min(limited[index], limited[index + 1] + MAX_RATE * run)
    return limited


def _clean_side(offsets: np.ndarray, distance: np.ndarray) -> Tuple[np.ndarray, int]:
    """Pull short outward protrusions back to what the surrounding track shows."""
    magnitude = np.abs(offsets)
    reference = magnitude.copy()
    for index in range(len(magnitude)):
        window = np.abs(distance - distance[index]) <= NEIGHBOURHOOD_METERS
        if window.sum() >= MIN_NEIGHBOURS:
            reference[index] = float(np.median(magnitude[window]))

    excess = magnitude - reference
    flagged = (excess > np.maximum(reference * MAX_DEVIATION_RATIO, MIN_DEVIATION_METERS))
    # A wide stretch that lasts is the track; only short ones are misreads.
    for start, end in _runs(flagged):
        if distance[end] - distance[start] > MAX_BLOCK_METERS:
            flagged[start:end + 1] = False

    cleaned = np.where(flagged, reference, magnitude)
    cleaned = _limit_rate(cleaned, distance)
    return cleaned, int(flagged.sum())


def enforce_width_continuity(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Trim raycast blocks off each edge. Mutates track_data."""
    widths = np.array(track_data.get("localWidth") or [], dtype=float)
    left = track_data.get("boundsLeft") or track_data.get("left_edge") or []
    right = track_data.get("boundsRight") or track_data.get("right_edge") or []
    count = len(widths)
    if count < 30 or len(left) != count or len(right) != count:
        return {"status": "UNAVAILABLE", "reason": "width_or_edges_missing"}

    frame = _frame(track_data, count)
    if frame is None:
        return {"status": "UNAVAILABLE", "reason": "no_centerline_frame"}
    center, normals = frame

    left_offsets = _edge_offsets(left, center, normals)
    right_offsets = _edge_offsets(right, center, normals)
    if left_offsets is None or right_offsets is None:
        return {"status": "UNAVAILABLE", "reason": "edges_unreadable"}

    distance = _distances(track_data, count)
    left_clean, left_flagged = _clean_side(left_offsets, distance)
    right_clean, right_flagged = _clean_side(right_offsets, distance)

    left_delta = left_clean - np.abs(left_offsets)
    right_delta = right_clean - np.abs(right_offsets)
    moved = int(((np.abs(left_delta) > 0.05) | (np.abs(right_delta) > 0.05)).sum())
    if not moved:
        return {"status": "NO_CHANGE", "blocksLeft": 0, "blocksRight": 0, "adjustedSamples": 0}

    # Each edge slides along the normal from where it already is, so the shape
    # the raycast found survives and only the protrusion is trimmed.
    left_sign = 1.0 if float(np.median(left_offsets)) >= 0 else -1.0
    right_sign = 1.0 if float(np.median(right_offsets)) >= 0 else -1.0
    new_left = center + normals * (left_sign * left_clean)[:, None]
    new_right = center + normals * (right_sign * right_clean)[:, None]

    def payload(points: np.ndarray) -> List[Dict[str, float]]:
        return [{"x": float(x), "y": float(-y), "z": float(-y)} for x, y in points]

    widths_after = left_clean + right_clean
    track_data["boundsLeft"] = payload(new_left)
    track_data["left_edge"] = track_data["boundsLeft"]
    track_data["boundsRight"] = payload(new_right)
    track_data["right_edge"] = track_data["boundsRight"]
    track_data["localWidth"] = [float(value) for value in widths_after]
    track_data["widthMin"] = round(float(widths_after.min()), 6)
    track_data["widthAvg"] = round(float(widths_after.mean()), 6)
    track_data["widthMax"] = round(float(widths_after.max()), 6)

    report = {
        "status": "SMOOTHED",
        "blocksLeft": left_flagged,
        "blocksRight": right_flagged,
        "adjustedSamples": moved,
        "widthBefore": round(float(widths.mean()), 3),
        "widthAfter": round(float(widths_after.mean()), 3),
        "maxBefore": round(float(widths.max()), 3),
        "maxAfter": round(float(widths_after.max()), 3),
    }
    track_data.setdefault("metadata", {})["widthContinuity"] = report
    logger.info(
        "Track edge blocks trimmed: %s left, %s right, widest %.2f -> %.2f m",
        left_flagged, right_flagged, report["maxBefore"], report["maxAfter"],
    )
    return report


__all__ = ["enforce_width_continuity"]
