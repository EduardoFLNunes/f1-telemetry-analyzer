"""Reject width readings the track cannot physically have.

The interval raycast decides the track's width one sample at a time, and where
it picks the wrong interval -- catching a run-off, or losing half the road at a
bifurcation -- the width jumps. On Interlagos the extraction swings from 19.5 m
to 5 m and back at up to 1.82 m per metre travelled, which on the map reads as
the band breaking into disconnected blocks.

A track does not do that. Its width changes gradually, so a reading that
disagrees with its neighbours is a misread rather than a narrowing, and the
neighbours are the evidence for what belongs there instead.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# The window a reading is judged against, and how far it may sit from that
# window's median before it is treated as a misread.
NEIGHBOURHOOD_METERS = 45.0
MAX_DEVIATION_RATIO = 0.35
MIN_NEIGHBOURS = 7
# The shipped hand-authored geometry changes width by 0.22 m per metre at its
# 99th percentile, so this is generous rather than smoothing real detail away.
MAX_RATE = 0.25


def _distances(track_data: Dict[str, Any], count: int) -> np.ndarray:
    values = []
    for point in track_data.get("centerline") or []:
        values.append(float(point.get("distance", 0.0)) if isinstance(point, dict)
                      else float(getattr(point, "distance", 0.0)))
    if len(values) == count and values[-1] > 0:
        return np.array(values, dtype=float)
    return np.arange(count, dtype=float)


def _limit_rate(values: np.ndarray, distance: np.ndarray) -> np.ndarray:
    limited = values.copy()
    for index in range(1, len(limited)):
        run = max(distance[index] - distance[index - 1], 1e-6)
        limited[index] = min(limited[index], limited[index - 1] + MAX_RATE * run)
    for index in range(len(limited) - 2, -1, -1):
        run = max(distance[index + 1] - distance[index], 1e-6)
        limited[index] = min(limited[index], limited[index + 1] + MAX_RATE * run)
    return limited


def enforce_width_continuity(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Replace width outliers with what the surrounding track says. Mutates track_data.

    The edges move with the width, symmetrically about the band's own axis, so a
    corrected sample keeps whatever lateral offset the raycast found.
    """
    widths = np.array(track_data.get("localWidth") or [], dtype=float)
    left = track_data.get("boundsLeft") or track_data.get("left_edge") or []
    right = track_data.get("boundsRight") or track_data.get("right_edge") or []
    if len(widths) < 8 or len(left) != len(widths) or len(right) != len(widths):
        return {"status": "UNAVAILABLE", "reason": "width_or_edges_missing"}

    distance = _distances(track_data, len(widths))
    smoothed = widths.copy()
    outliers = 0
    for index in range(len(widths)):
        window = np.abs(distance - distance[index]) <= NEIGHBOURHOOD_METERS
        if window.sum() < MIN_NEIGHBOURS:
            continue
        median = float(np.median(widths[window]))
        if median <= 0:
            continue
        if abs(widths[index] - median) / median > MAX_DEVIATION_RATIO:
            smoothed[index] = median
            outliers += 1

    smoothed = _limit_rate(smoothed, distance)
    delta = smoothed - widths
    moved = int((np.abs(delta) > 0.05).sum())
    if not moved:
        return {"status": "NO_CHANGE", "outliers": 0, "adjustedSamples": 0}

    # Grow or shrink each sample about its own centre, so the band keeps the
    # position the raycast found and only its width changes.
    new_left, new_right = [], []
    for index, (lp, rp) in enumerate(zip(left, right)):
        lx, lz = float(lp["x"]), float(lp.get("z", lp.get("y", 0.0)))
        rx, rz = float(rp["x"]), float(rp.get("z", rp.get("y", 0.0)))
        mx, mz = (lx + rx) / 2.0, (lz + rz) / 2.0
        span = np.hypot(lx - rx, lz - rz)
        scale = (smoothed[index] / span) if span > 1e-6 else 1.0
        new_left.append({"x": mx + (lx - mx) * scale, "y": mz + (lz - mz) * scale,
                         "z": mz + (lz - mz) * scale})
        new_right.append({"x": mx + (rx - mx) * scale, "y": mz + (rz - mz) * scale,
                          "z": mz + (rz - mz) * scale})

    track_data["boundsLeft"] = new_left
    track_data["left_edge"] = new_left
    track_data["boundsRight"] = new_right
    track_data["right_edge"] = new_right
    track_data["localWidth"] = [float(value) for value in smoothed]
    track_data["widthMin"] = round(float(smoothed.min()), 6)
    track_data["widthAvg"] = round(float(smoothed.mean()), 6)
    track_data["widthMax"] = round(float(smoothed.max()), 6)

    report = {
        "status": "SMOOTHED",
        "outliers": outliers,
        "adjustedSamples": moved,
        "widthBefore": round(float(widths.mean()), 3),
        "widthAfter": round(float(smoothed.mean()), 3),
        "minBefore": round(float(widths.min()), 3),
        "minAfter": round(float(smoothed.min()), 3),
        "maxRateBefore": round(float(np.nanmax(np.abs(np.diff(widths)) / np.maximum(np.diff(distance), 1e-6))), 3),
        "maxRateAfter": round(float(np.nanmax(np.abs(np.diff(smoothed)) / np.maximum(np.diff(distance), 1e-6))), 3),
    }
    track_data.setdefault("metadata", {})["widthContinuity"] = report
    logger.info(
        "Track width continuity: %s outliers replaced, worst change %.2f -> %.2f m per metre",
        outliers, report["maxRateBefore"], report["maxRateAfter"],
    )
    return report


__all__ = ["enforce_width_continuity"]
