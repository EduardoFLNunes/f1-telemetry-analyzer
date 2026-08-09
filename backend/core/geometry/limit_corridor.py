"""Build a continuous track limit from the paint, the kerbs, and honest gaps.

The reconstruction has been treating the extracted asphalt as the core and the
paint as a correction on top. That is backwards. The asphalt comes out of a
raycast that loses the road at bifurcations and catches run-off beside it; the
painted limit is what the circuit itself declares, and the kerbs mark where the
surface ends by construction.

What kept the paint from being the core was the classifier, not the paint. It
demanded a ring behave like a limit along its whole length, so a line that is
the boundary for 500 m and a pit wall for 200 m was thrown away entire. Judging
rings by where they sit rather than by how consistent they stay takes Interlagos
from 3 usable rings to 18, and coverage from 28% of one side to 82%.

Nothing here invents certainty. Every sample records where its limit came from,
so a stretch held up by interpolation can be told apart from one measured
against paint.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .paint_boundary_rings import (
    TrackFrame,
    build_track_frame,
    cast_to_segments,
    edge_side_signs,
    kerb_limit_profile,
    _polygon_rings,
    _segments_of,
)

logger = logging.getLogger(__name__)

# A limit line sits about one half width out. This is where it may sit, not how
# steady it has to stay -- steadiness was the test that discarded 15 of the 18.
LIMIT_RATIO_MAX = 1.35
LIMIT_RATIO_MIN = 0.55
MIN_RING_POINTS = 6
# The ray window, as a fraction of the current half width.
MIN_HIT_RATIO = 0.45
MAX_HIT_RATIO = 2.2
PAINT_BAND_TOLERANCE_METERS = 0.6
# Beyond this an interpolated limit is a guess about a stretch nothing measured.
MAX_INTERPOLATED_GAP_METERS = 120.0
MAX_RATE = 0.15

PAINT = "paint"
KERB = "kerb"
ESTIMATED = "estimated"
UNKNOWN = "unknown"


def identify_limit_rings(track_data: Dict[str, Any], frame: TrackFrame) -> List[Dict[str, Any]]:
    """Rings sitting where a track limit sits, whatever they do elsewhere."""
    accepted = []
    half = frame.half_widths
    for group_index, polygon in enumerate(((track_data.get("markingGeometry") or {}).get("polygons")) or []):
        for ring_index, ring in enumerate(_polygon_rings(polygon)):
            points = np.array(ring, dtype=float)
            if points.ndim != 2 or len(points) < MIN_RING_POINTS:
                continue
            points = points[:, :2]
            step = max(1, len(points) // 80)
            sample = points[::step]
            deltas = sample[:, None, :] - frame.center[None, :, :]
            distance = np.sqrt((deltas * deltas).sum(axis=2))
            nearest = distance.argmin(axis=1)
            ratio = distance.min(axis=1) / np.maximum(half[nearest], 1e-6)
            median = float(np.median(ratio))
            if LIMIT_RATIO_MIN <= median <= LIMIT_RATIO_MAX:
                accepted.append({"group": group_index, "ring": ring_index,
                                 "ratio": round(median, 3), "points": len(points),
                                 "rings": [ring]})
    return accepted


def _fill_gaps(values: np.ndarray, source: List[str], distance: np.ndarray) -> np.ndarray:
    known = np.where(~np.isnan(values))[0]
    if not len(known):
        return values
    filled = values.copy()
    for left, right in zip(known[:-1], known[1:]):
        if right - left <= 1:
            continue
        span = distance[right] - distance[left]
        if span > MAX_INTERPOLATED_GAP_METERS:
            continue
        weights = (distance[left + 1:right] - distance[left]) / max(span, 1e-9)
        filled[left + 1:right] = values[left] * (1 - weights) + values[right] * weights
        for index in range(left + 1, right):
            source[index] = ESTIMATED
    # Before the first and after the last reading, hold the nearest value.
    filled[:known[0]] = values[known[0]]
    filled[known[-1] + 1:] = values[known[-1]]
    for index in range(0, known[0]):
        source[index] = ESTIMATED
    for index in range(known[-1] + 1, len(filled)):
        source[index] = ESTIMATED
    return filled


def _limit_rate(values: np.ndarray, distance: np.ndarray) -> np.ndarray:
    out = values.copy()
    for index in range(1, len(out)):
        run = max(distance[index] - distance[index - 1], 1e-6)
        out[index] = min(out[index], out[index - 1] + MAX_RATE * run)
        out[index] = max(out[index], out[index - 1] - MAX_RATE * run)
    for index in range(len(out) - 2, -1, -1):
        run = max(distance[index + 1] - distance[index], 1e-6)
        out[index] = min(out[index], out[index + 1] + MAX_RATE * run)
        out[index] = max(out[index], out[index + 1] - MAX_RATE * run)
    return out


def _distances(track_data: Dict[str, Any], count: int) -> np.ndarray:
    values = []
    for point in track_data.get("centerline") or []:
        values.append(float(point.get("distance", 0.0)) if isinstance(point, dict)
                      else float(getattr(point, "distance", 0.0)))
    if len(values) == count and values[-1] > 0:
        return np.array(values, dtype=float)
    return np.arange(count, dtype=float)


def build_limit_corridor(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """A limit distance for every sample and side, with where each one came from."""
    frame = build_track_frame(track_data)
    if frame is None:
        return {"status": "UNAVAILABLE", "reason": "no_centerline"}

    signs = edge_side_signs(track_data, frame)
    rings = identify_limit_rings(track_data, frame)
    count = len(frame.center)
    distance = _distances(track_data, count)

    paint = {side: np.full(count, np.nan) for side in signs}
    if rings:
        segments = _segments_of([{"rings": entry["rings"]} for entry in rings])
        paint = cast_to_segments(frame, segments, signs, MIN_HIT_RATIO, MAX_HIT_RATIO,
                                 band_tolerance=PAINT_BAND_TOLERANCE_METERS)
    kerb = kerb_limit_profile(track_data, frame, signs)

    sides: Dict[str, Any] = {}
    for side in signs:
        source = [UNKNOWN] * count
        values = np.full(count, np.nan)
        for index in range(count):
            painted, kerbed = paint[side][index], kerb[side][index]
            if not np.isnan(painted) and not np.isnan(kerbed):
                # Both are floors: the asphalt reaches the furthest either proves.
                values[index] = max(painted, kerbed)
                source[index] = PAINT if painted >= kerbed else KERB
            elif not np.isnan(painted):
                values[index] = painted
                source[index] = PAINT
            elif not np.isnan(kerbed):
                values[index] = kerbed
                source[index] = KERB

        measured = int(sum(1 for s in source if s in (PAINT, KERB)))
        values = _fill_gaps(values, source, distance)
        if np.isnan(values).any():
            sides[side] = {"status": "NO_LIMIT_FOUND", "measuredSamples": 0}
            continue
        values = _limit_rate(values, distance)

        sides[side] = {
            "status": "OK",
            "limit": [round(float(v), 4) for v in values],
            "source": source,
            "measuredSamples": measured,
            "measuredPercent": round(measured / count * 100.0, 1),
            "fromPaint": sum(1 for s in source if s == PAINT),
            "fromKerb": sum(1 for s in source if s == KERB),
            "estimated": sum(1 for s in source if s == ESTIMATED),
            "median": round(float(np.median(values)), 3),
        }

    usable = [s for s in sides.values() if s.get("status") == "OK"]
    report = {
        "status": "OK" if len(usable) == 2 else ("PARTIAL" if usable else "UNAVAILABLE"),
        "limitRings": len(rings),
        "sides": sides,
    }
    if usable:
        logger.info(
            "Limit corridor: %s rings, measured %s",
            len(rings),
            " / ".join(f"{name} {data.get('measuredPercent')}%" for name, data in sides.items()),
        )
    return report


REBUILD_MARKER = "limitCorridorRebuild"
# A limit that would move an edge further than this is a misread, not a track.
MAX_REBUILD_METERS = 6.0


def rebuild_edges_from_limit_corridor(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Put the edges where the limit says, wherever the limit was measured.

    Only measured samples move. On an estimated stretch there is nothing to
    reconstruct from, so the extraction's own edge stays -- taking an
    interpolated limit as authority would replace a real reading with a guess.

    Edges slide along the normal from where they already are rather than being
    redrawn from the centreline, so whatever shape the extraction found survives
    and only the distance changes.
    """
    metadata = track_data.setdefault("metadata", {})
    if isinstance(metadata, dict) and metadata.get(REBUILD_MARKER):
        return {"status": "ALREADY_APPLIED", **{
            key: value for key, value in metadata[REBUILD_MARKER].items() if key != "status"
        }}

    frame = build_track_frame(track_data)
    if frame is None:
        return {"status": "UNAVAILABLE", "reason": "no_centerline"}

    corridor = build_limit_corridor(track_data)
    if corridor["status"] == "UNAVAILABLE":
        return {"status": "NO_CORRIDOR"}

    count = len(frame.center)
    distance = _distances(track_data, count)
    signs = edge_side_signs(track_data, frame)
    keys = {"left": ("boundsLeft", "left_edge"), "right": ("boundsRight", "right_edge")}

    moved_total = 0
    details: Dict[str, Any] = {}
    for side, side_keys in keys.items():
        data = corridor["sides"].get(side) or {}
        if data.get("status") != "OK":
            details[side] = {"movedSamples": 0, "reason": data.get("status", "missing")}
            continue
        points = next((track_data.get(key) for key in side_keys if track_data.get(key)), None)
        if not points or len(points) != count:
            details[side] = {"movedSamples": 0, "reason": "edge_missing"}
            continue

        current = np.array([[float(p["x"]), -float(p.get("z", p.get("y", 0.0)))] for p in points])
        offsets = np.abs(((current - frame.center) * frame.normals).sum(axis=1))
        target = np.array(data["limit"], dtype=float)
        measured = np.array([s in (PAINT, KERB) for s in data["source"]])

        delta = np.where(measured, target - offsets, 0.0)
        delta[np.abs(delta) > MAX_REBUILD_METERS] = 0.0
        delta = _limit_rate(delta, distance)

        moved = int((np.abs(delta) > 0.05).sum())
        moved_total += moved
        if moved:
            updated = current + frame.normals * (signs[side] * delta)[:, None]
            payload = [{"x": float(x), "y": float(-y), "z": float(-y)} for x, y in updated]
            for key in side_keys:
                track_data[key] = payload
        details[side] = {
            "movedSamples": moved,
            "measuredPercent": data["measuredPercent"],
            "maxMeters": round(float(np.abs(delta).max()), 3) if moved else 0.0,
        }

    if not moved_total:
        return {"status": "NO_CHANGE", "sides": details}

    left = np.abs(((np.array([[float(p["x"]), -float(p.get("z", p.get("y", 0.0)))]
                              for p in track_data["boundsLeft"]]) - frame.center)
                   * frame.normals).sum(axis=1))
    right = np.abs(((np.array([[float(p["x"]), -float(p.get("z", p.get("y", 0.0)))]
                               for p in track_data["boundsRight"]]) - frame.center)
                    * frame.normals).sum(axis=1))
    widths = left + right
    track_data["localWidth"] = [float(value) for value in widths]
    track_data["widthMin"] = round(float(widths.min()), 6)
    track_data["widthAvg"] = round(float(widths.mean()), 6)
    track_data["widthMax"] = round(float(widths.max()), 6)

    report = {
        "status": "REBUILT",
        "limitRings": corridor["limitRings"],
        "movedSamples": moved_total,
        "widthAvg": round(float(widths.mean()), 3),
        "sides": details,
    }
    if isinstance(metadata, dict):
        metadata[REBUILD_MARKER] = report
    logger.info("Edges rebuilt from the limit corridor: %s samples moved", moved_total)
    return report


__all__ = ["build_limit_corridor", "identify_limit_rings", "rebuild_edges_from_limit_corridor"]
