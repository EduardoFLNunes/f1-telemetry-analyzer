"""Pull the track edges out to the painted limit where the circuit says they belong.

Interlagos showed why this is needed. The raycast extraction lands on the paint
to within 0.17 m, but the hand-authored geometry the dash actually drew had
narrowed one corner from 15.4 m to 13.1 m -- the asphalt visibly stopped short
of the white line that was drawn right next to it.

The paint cannot rebuild an edge on its own: it covers about 20% of a lap on the
left and 7% on the right, so most of the track has nothing to snap to. What it
can do is correct the edge where it exists. So this does not replace the
extracted edge, it nudges it: a correction is measured only where paint is,
carried across short unpainted gaps, and eased back to the extracted edge
everywhere else. The shape still comes from the raycast; the paint only says how
wide.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .paint_boundary_rings import (
    MAX_BOUNDARY_RATIO_SPREAD,
    build_track_frame,
    identify_boundary_rings,
    painted_limit_profile,
)

logger = logging.getLogger(__name__)

# Correcting moves real geometry, so the line has to be unambiguously the limit.
# The lower bound is what does the work: the verification thresholds are
# deliberately loose and let an inner marking at 0.56 half-widths through, which
# is harmless when reporting and halves the track when correcting.
#
# The upper bound stays generous. A ring sitting well outside the edge is the
# symptom this exists to fix, and a track that is uniformly too narrow puts a
# genuine limit line at a ratio well above 1 -- the low spread is what says it is
# still a limit line and not stray paint.
CORRECTION_RATIO_RANGE = (0.85, 1.60)
MAX_CORRECTION_RATIO_SPREAD = MAX_BOUNDARY_RATIO_SPREAD
# A correction has to be believable. Paint that would move an edge by more than
# this is likelier to be a misread than a genuinely mismeasured track.
MAX_CORRECTION_METERS = 5.0
# One stray point is noise; a stretch of them is a defect.
MIN_PAINTED_RUN_SAMPLES = 4
# Unpainted gaps shorter than this are bridged, since the paint on both sides
# agrees about a stretch the extraction got wrong for one continuous reason.
MAX_BRIDGED_GAP_METERS = 25.0
# Past the end of the paint the correction fades out over this distance, so the
# edge never steps.
DECAY_METERS = 15.0
# Below this the correction is not worth the risk of moving a good edge. It also
# has to clear the width of the painted band itself: the limit is the line's
# outer edge and the extraction tends to land on its inner edge, a systematic
# ~0.25 m that is not an error worth rewriting the whole track for.
MIN_CORRECTION_METERS = 0.35


def _runs_of(mask: np.ndarray) -> List[tuple]:
    runs, start = [], None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def _spread_correction(delta: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """Carry the measured correction across short gaps and fade it out at the ends.

    Applying it only where paint exists would leave a step at every end of every
    painted stretch, which reads worse than the error being corrected.
    """
    known = ~np.isnan(delta)
    if not known.any():
        return np.zeros_like(delta)

    out = np.where(known, delta, 0.0)
    known_idx = np.where(known)[0]

    # Bridge short unpainted gaps between two corrections.
    for left, right in zip(known_idx[:-1], known_idx[1:]):
        if right - left <= 1:
            continue
        span = distance[right] - distance[left]
        if span > MAX_BRIDGED_GAP_METERS:
            continue
        weights = (distance[left + 1:right] - distance[left]) / max(span, 1e-9)
        out[left + 1:right] = delta[left] * (1 - weights) + delta[right] * weights

    # Fade out beyond the ends of each corrected stretch. Written into a
    # separate array so two nearby stretches cannot overwrite each other's
    # ramp -- whichever asks for more movement wins.
    filled = out != 0.0
    decay = np.zeros_like(out)
    for start, end in _runs_of(filled):
        for index in range(end + 1, len(out)):
            travelled = distance[index] - distance[end]
            if travelled >= DECAY_METERS or filled[index]:
                break
            value = out[end] * (1 - travelled / DECAY_METERS)
            if abs(value) > abs(decay[index]):
                decay[index] = value
        for index in range(start - 1, -1, -1):
            travelled = distance[start] - distance[index]
            if travelled >= DECAY_METERS or filled[index]:
                break
            value = out[start] * (1 - travelled / DECAY_METERS)
            if abs(value) > abs(decay[index]):
                decay[index] = value
    return np.where(filled, out, decay)


def _distance_array(track_data: Dict[str, Any], sample_count: int) -> np.ndarray:
    centerline = track_data.get("centerline") or []
    values = []
    for point in centerline:
        if isinstance(point, dict):
            values.append(float(point.get("distance", 0.0)))
        else:
            values.append(float(getattr(point, "distance", 0.0)))
    if len(values) == sample_count and values[-1] > 0:
        return np.array(values, dtype=float)
    return np.arange(sample_count, dtype=float)


def _edge_points(center: np.ndarray, normals: np.ndarray, half: np.ndarray, sign: float) -> List[Dict[str, float]]:
    """Map-space edge back to the world_xz dicts the cache and renderer expect."""
    points = center + normals * (sign * half)[:, None]
    return [{"x": float(x), "y": float(-y), "z": float(-y)} for x, y in points]


CORRECTION_MARKER = "paintEdgeCorrection"


def correct_edges_from_paint(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Widen the edges out to the painted limit. Mutates track_data.

    Runs once per geometry and records the fact in metadata. A second pass is
    not a no-op -- the ramps that ease each correction back into the extracted
    edge leave a small residual the next pass would correct again, walking the
    track wider on every load -- so the marker is the guard, not convergence.

    Returns a report of what moved and by how much, so the change is auditable
    rather than a silent rewrite of the geometry.
    """
    metadata = track_data.setdefault("metadata", {})
    if isinstance(metadata, dict) and metadata.get(CORRECTION_MARKER):
        return {"status": "ALREADY_APPLIED", **{
            key: value for key, value in metadata[CORRECTION_MARKER].items() if key != "status"
        }}

    frame = build_track_frame(track_data)
    if frame is None:
        return {"status": "UNAVAILABLE", "reason": "no_centerline", "sides": {}}

    rings = identify_boundary_rings(
        track_data, frame,
        ratio_range=CORRECTION_RATIO_RANGE,
        max_spread=MAX_CORRECTION_RATIO_SPREAD,
    )
    if not rings:
        return {"status": "NO_BOUNDARY_PAINT", "sides": {}, "correctedSamples": 0}

    sample_count = len(frame.center)
    distance = _distance_array(track_data, sample_count)
    profile = painted_limit_profile(track_data, frame, rings)
    half = frame.half_widths.copy()

    report_sides: Dict[str, Any] = {}
    corrections: Dict[str, np.ndarray] = {}

    for side in ("left", "right"):
        target = profile[side]
        delta = target - half
        # The paint is a floor on the width, not a ceiling. A limit line proves
        # the track reaches at least that far out; it does not prove the asphalt
        # stops there. Interlagos draws the pit access as part of the band on
        # purpose, and narrowing to the paint cut 180 m of it from 11.9 to 6.9 m.
        delta[delta < 0] = np.nan
        # Ignore paint that agrees already, and paint that disagrees so violently
        # it is more likely to be something else entirely.
        delta[delta < MIN_CORRECTION_METERS] = np.nan
        delta[delta > MAX_CORRECTION_METERS] = np.nan

        # A single disagreeing sample is noise; require a run.
        measured = ~np.isnan(delta)
        for start, end in _runs_of(measured):
            if end - start + 1 < MIN_PAINTED_RUN_SAMPLES:
                delta[start:end + 1] = np.nan

        spread = _spread_correction(delta, distance)
        corrections[side] = spread
        # Count what actually moved the edge, not the tails of the ramps.
        moved = np.abs(spread) > 0.05
        report_sides[side] = {
            "paintedSamples": int((~np.isnan(target)).sum()),
            "correctedSamples": int(moved.sum()),
            "maxCorrectionMeters": round(float(np.abs(spread).max()), 3) if moved.any() else 0.0,
            "meanCorrectionMeters": round(float(spread[moved].mean()), 3) if moved.any() else 0.0,
        }

    total_moved = int((np.abs(corrections["left"]) + np.abs(corrections["right"]) > 0.05).sum())
    if not total_moved:
        report = {
            "status": "NO_CHANGE",
            "boundaryRings": len(rings),
            "sides": report_sides,
            "correctedSamples": 0,
        }
        # Marked as well: reaching this point cost the full raycast, and the
        # answer will not change on the next load either.
        if isinstance(metadata, dict):
            metadata[CORRECTION_MARKER] = report
        return report

    left_half = np.maximum(half + corrections["left"], 0.5)
    right_half = np.maximum(half + corrections["right"], 0.5)
    widths = left_half + right_half

    # The normal points to the right in map space, so the left edge is negative.
    left_edge = _edge_points(frame.center, frame.normals, left_half, -1.0)
    right_edge = _edge_points(frame.center, frame.normals, right_half, 1.0)

    track_data["boundsLeft"] = left_edge
    track_data["left_edge"] = left_edge
    track_data["boundsRight"] = right_edge
    track_data["right_edge"] = right_edge
    track_data["localWidth"] = [float(value) for value in widths]
    track_data["widthMin"] = round(float(widths.min()), 6)
    track_data["widthAvg"] = round(float(widths.mean()), 6)
    track_data["widthMax"] = round(float(widths.max()), 6)

    # The dash draws asphaltPolygon, not the edges. Leaving it stale would
    # correct the numbers and change nothing on screen.
    if track_data.get("asphaltPolygon"):
        band = np.vstack([
            frame.center + frame.normals * (-left_half)[:, None],
            (frame.center + frame.normals * right_half[:, None])[::-1],
        ])
        track_data["asphaltPolygon"] = {
            "points": [[float(x), float(y)] for x, y in band],
            "x": [float(x) for x in band[:, 0]],
            "y": [float(y) for y in band[:, 1]],
        }

    report = {
        "status": "CORRECTED",
        "boundaryRings": len(rings),
        "correctedSamples": total_moved,
        "correctedPercent": round(total_moved / sample_count * 100.0, 2),
        "widthBefore": round(float(frame.widths.mean()), 3),
        "widthAfter": round(float(widths.mean()), 3),
        "sides": report_sides,
    }
    logger.info(
        "Track edges corrected against painted limits: %s samples (%.1f%%), width %.2f -> %.2f m",
        total_moved, report["correctedPercent"], report["widthBefore"], report["widthAfter"],
    )
    if isinstance(metadata, dict):
        metadata[CORRECTION_MARKER] = report
    return report


def paint_correction_enabled() -> bool:
    return os.getenv("AT_PAINT_EDGE_CORRECTION", "true").strip().lower() not in {"0", "false", "no", "off"}


__all__ = ["correct_edges_from_paint", "paint_correction_enabled"]
