"""Decide whether a car is outside the reconstructed track limit.

The rule is four wheels past the line, so a point position is not enough: the
car's footprint has to be projected and each corner tested. Assetto Corsa
answers the same question itself through numberOfTyresOut, which makes this
measurable rather than merely plausible -- the detector can be scored against
the simulator sample by sample, and the score is the reconstruction's evidence.

Agreement is reported per limit source. A violation called on a stretch held up
by interpolation is worth less than one called against paint, and averaging the
two would hide exactly the weakness worth knowing about.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .limit_corridor import ESTIMATED, KERB, PAINT, build_limit_corridor
from .paint_boundary_rings import build_track_frame, edge_side_signs

logger = logging.getLogger(__name__)

# A single seater is about this big, and the corners are where the wheels are.
CAR_LENGTH_METERS = 4.8
CAR_WIDTH_METERS = 2.0
WHEELS_FOR_VIOLATION = 4


def car_corners(x: float, y: float, heading: float,
                length: float = CAR_LENGTH_METERS,
                width: float = CAR_WIDTH_METERS) -> List[Tuple[float, float]]:
    """The four wheel positions in map space.

    Map space mirrors Z, so the heading turns the other way here than it does
    in the world -- the same negation the car marker on the map needs.
    """
    angle = -heading
    cos, sin = np.cos(angle), np.sin(angle)
    half_l, half_w = length / 2.0, width / 2.0
    corners = []
    for dx, dy in ((half_l, half_w), (half_l, -half_w), (-half_l, half_w), (-half_l, -half_w)):
        corners.append((x + dx * cos - dy * sin, y + dx * sin + dy * cos))
    return corners


class TrackLimits:
    """The reconstructed limit, queryable at any point on the map."""

    def __init__(self, track_data: Dict[str, Any]):
        self.frame = build_track_frame(track_data)
        self.corridor = build_limit_corridor(track_data) if self.frame is not None else {"status": "UNAVAILABLE"}
        self.signs = edge_side_signs(track_data, self.frame) if self.frame is not None else {}
        self.available = (
            self.frame is not None
            and self.corridor.get("status") in {"OK", "PARTIAL"}
            and all((self.corridor["sides"].get(side) or {}).get("status") == "OK"
                    for side in ("left", "right"))
        )

    def _nearest(self, point: Tuple[float, float]) -> int:
        deltas = self.frame.center - np.array(point, dtype=float)
        return int(np.argmin((deltas * deltas).sum(axis=1)))

    def outside(self, point: Tuple[float, float]) -> Tuple[bool, str]:
        """Is this point past the limit, and what was the limit measured from?"""
        if not self.available:
            return False, "unavailable"
        index = self._nearest(point)
        offset = float((np.array(point, dtype=float) - self.frame.center[index]) @ self.frame.normals[index])
        side = "left" if offset * self.signs["left"] > 0 else "right"
        data = self.corridor["sides"][side]
        return abs(offset) > float(data["limit"][index]), data["source"][index]

    def wheels_outside(self, x: float, y: float, heading: float) -> Tuple[int, str]:
        """How many wheels are past the limit, and the weakest source relied on."""
        count = 0
        sources = []
        for corner in car_corners(x, y, heading):
            is_out, source = self.outside(corner)
            sources.append(source)
            count += int(is_out)
        # The weakest evidence governs how much the verdict is worth.
        for weakest in (ESTIMATED, KERB, PAINT):
            if weakest in sources:
                return count, weakest
        return count, sources[0] if sources else "unavailable"


def measure_agreement(track_data: Dict[str, Any], samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Score the geometric detector against what the simulator reported.

    Samples need a map position, a heading and tyres_out; anything missing one
    is counted as skipped rather than quietly treated as on-track.
    """
    limits = TrackLimits(track_data)
    if not limits.available:
        return {"status": "NO_LIMIT_CORRIDOR"}

    buckets: Dict[str, Dict[str, int]] = {}
    skipped = 0
    for sample in samples:
        position = sample.get("mapPosition") or {}
        x, y = position.get("x"), position.get("y")
        heading = sample.get("heading")
        reported = sample.get("tyres_out", sample.get("tyresOut"))
        if x is None or y is None or heading is None or reported is None:
            skipped += 1
            continue
        detected_wheels, source = limits.wheels_outside(float(x), float(y), float(heading))
        detected = detected_wheels >= WHEELS_FOR_VIOLATION
        actual = int(reported) >= WHEELS_FOR_VIOLATION
        bucket = buckets.setdefault(source, {"samples": 0, "agree": 0,
                                             "falseAlarm": 0, "missed": 0})
        bucket["samples"] += 1
        if detected == actual:
            bucket["agree"] += 1
        elif detected:
            bucket["falseAlarm"] += 1
        else:
            bucket["missed"] += 1

    total = sum(b["samples"] for b in buckets.values())
    if not total:
        return {"status": "NO_USABLE_SAMPLES", "skipped": skipped}

    for bucket in buckets.values():
        bucket["agreementPercent"] = round(bucket["agree"] / bucket["samples"] * 100.0, 2)
    agree = sum(b["agree"] for b in buckets.values())
    return {
        "status": "MEASURED",
        "samples": total,
        "skipped": skipped,
        "agreementPercent": round(agree / total * 100.0, 2),
        "falseAlarms": sum(b["falseAlarm"] for b in buckets.values()),
        "missed": sum(b["missed"] for b in buckets.values()),
        "bySource": buckets,
    }


__all__ = ["TrackLimits", "car_corners", "measure_agreement"]
