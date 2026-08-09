"""Tell the painted track limit apart from every other line on the circuit.

A circuit is painted with a lot of white: limit lines, pit lane lines, grid
boxes, service markings. Only the limit line is usable as geometry, so both the
verification and the edge correction need the same answer to "which of these is
the edge?".

Two things identify it. It runs at roughly one half-width from the centre, and
it *keeps* that relationship along its length. The second is what does the work:
pit paint at Interlagos sits at 2.7 to 12.4 half-widths and wanders, and a
marking group can show a plausible median while mixing sides.

Rings, not groups. A single connected marking group can carry the limit line in
one ring and paint 20 m off-track in another -- group 0 at Interlagos has a
median ratio of 1.02 and a p90 gap of +21 m in the same breath.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Loose on purpose: this only has to exclude paint that is nowhere near the
# edge. Anything tighter would double as a judgement, and a genuinely wrong
# edge would be reclassified as "not a boundary" instead of being reported.
BOUNDARY_RATIO_RANGE = (0.5, 2.0)
MAX_BOUNDARY_RATIO_SPREAD = 0.25
MIN_RING_POINTS = 12
_CHUNK = 400


@dataclass
class BoundaryRing:
    group: int
    ring: int
    side: str                 # "left" | "right"
    indices: np.ndarray       # centreline index each accepted point belongs to
    offsets: np.ndarray       # signed lateral offset, map space
    ratio_median: float
    ratio_spread: float

    @property
    def point_count(self) -> int:
        return int(len(self.indices))


@dataclass
class TrackFrame:
    """Centreline in map space with its lateral frame, the basis for every measurement."""
    center: np.ndarray
    normals: np.ndarray
    widths: np.ndarray

    @property
    def half_widths(self) -> np.ndarray:
        return self.widths / 2.0

    def project(self, points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Nearest centreline index and signed lateral offset for each point."""
        indices, offsets = [], []
        for start in range(0, len(points), _CHUNK):
            block = points[start:start + _CHUNK]
            deltas = block[:, None, :] - self.center[None, :, :]
            nearest = np.sqrt((deltas * deltas).sum(axis=2)).argmin(axis=1)
            indices.append(nearest)
            offsets.append(((block - self.center[nearest]) * self.normals[nearest]).sum(axis=1))
        if not indices:
            return np.array([], dtype=int), np.array([], dtype=float)
        return np.concatenate(indices), np.concatenate(offsets)


def build_track_frame(track_data: Dict[str, Any]) -> Optional[TrackFrame]:
    """Map space mirrors Z, so both the points and the normals are negated."""
    centerline = track_data.get("centerline") or []
    widths = np.array(track_data.get("localWidth") or [], dtype=float)
    if not centerline or not len(widths):
        return None

    points, normals = [], []
    for point in centerline:
        if isinstance(point, dict):
            x, z = point.get("x"), point.get("z")
            normal = point.get("normal") or {}
            nx, nz = normal.get("x"), normal.get("z")
        else:
            x, z = getattr(point, "x", None), getattr(point, "z", None)
            normal = getattr(point, "normal", None) or (0.0, 1.0)
            nx, nz = normal[0], normal[1]
        if x is None or z is None or nx is None or nz is None:
            continue
        points.append([float(x), -float(z)])
        normals.append([float(nx), -float(nz)])

    if len(points) < 2 or len(points) != len(widths):
        return None
    return TrackFrame(np.array(points, dtype=float), np.array(normals, dtype=float), widths)


def edge_side_signs(track_data: Dict[str, Any], frame: TrackFrame) -> Dict[str, float]:
    """Which lateral direction each bounds array actually lies on.

    Nothing in the payload guarantees that boundsLeft sits at +normal. In the
    shipped Interlagos geometry it does, and hardcoding the opposite swapped the
    two edges: every point moved by roughly a full track width, the band crossed
    itself, and the map broke worst where the track is widest. So the sign is
    measured from the geometry rather than assumed.
    """
    signs: Dict[str, float] = {}
    for side, keys in (("left", ("boundsLeft", "left_edge")), ("right", ("boundsRight", "right_edge"))):
        points = next((track_data.get(key) for key in keys if track_data.get(key)), None)
        signs[side] = _median_side_sign(points, frame)

    # A degenerate or missing pair must not put both edges on one side.
    if signs["left"] == signs["right"]:
        signs = {"left": 1.0, "right": -1.0}
    return signs


def _median_side_sign(points: Optional[Sequence[Any]], frame: TrackFrame) -> float:
    if not points or len(points) != len(frame.center):
        return 0.0
    offsets = []
    for index, point in enumerate(points):
        if isinstance(point, dict):
            x, z = point.get("x"), point.get("z", point.get("y"))
        else:
            x, z = getattr(point, "x", None), getattr(point, "z", None)
        if x is None or z is None:
            continue
        delta = np.array([float(x), -float(z)]) - frame.center[index]
        offsets.append(float(delta @ frame.normals[index]))
    if not offsets:
        return 0.0
    median = float(np.median(offsets))
    return 1.0 if median > 0 else (-1.0 if median < 0 else 0.0)


def _rings_of(track_data: Dict[str, Any]):
    groups = ((track_data.get("markingGeometry") or {}).get("polygons")) or []
    for group_index, group in enumerate(groups):
        rings = group.get("rings")
        if not rings and group.get("points"):
            rings = [group["points"]]
        for ring_index, ring in enumerate(rings or []):
            yield group_index, ring_index, ring


def identify_boundary_rings(
    track_data: Dict[str, Any],
    frame: Optional[TrackFrame] = None,
    ratio_range: Tuple[float, float] = BOUNDARY_RATIO_RANGE,
    max_spread: float = MAX_BOUNDARY_RATIO_SPREAD,
) -> List[BoundaryRing]:
    """Every painted ring that behaves like a track limit, one entry per side it covers.

    The thresholds are a parameter because the two callers need opposite things.
    Verification wants them loose, so a badly placed edge is reported rather than
    silently reclassified as "not a boundary". Correction treats the paint as
    ground truth and moves real geometry, so it wants them tight -- at the default
    range an inner marking at 0.56 half-widths qualified, and correcting to it cut
    a 180 m stretch of Interlagos from 11.9 m to 6.9 m wide.
    """
    frame = frame or build_track_frame(track_data)
    if frame is None:
        return []

    half = frame.half_widths
    signs = edge_side_signs(track_data, frame)
    found: List[BoundaryRing] = []
    for group_index, ring_index, ring in _rings_of(track_data):
        points = np.array(ring, dtype=float)
        if len(points) < MIN_RING_POINTS or points.ndim != 2 or points.shape[1] < 2:
            continue
        indices, offsets = frame.project(points[:, :2])
        with np.errstate(divide="ignore", invalid="ignore"):
            ratios = np.abs(offsets) / np.where(half[indices] > 0, half[indices], np.nan)

        # A side is named after the bounds array that lies on it, so a correction
        # measured here lands on the edge it was measured against.
        for side, sign in signs.items():
            mask = offsets * sign > 0
            if mask.sum() < MIN_RING_POINTS:
                continue
            side_ratios = ratios[mask]
            if not np.isfinite(side_ratios).any():
                continue
            median = float(np.nanmedian(side_ratios))
            spread = float(np.nanstd(side_ratios))
            if not (ratio_range[0] <= median <= ratio_range[1]):
                continue
            if spread >= max_spread:
                continue
            found.append(BoundaryRing(group_index, ring_index, side,
                                      indices[mask], offsets[mask], median, spread))
    return found


# How far past the first hit to keep looking for the same line's far side.
# The limit is the outer edge of the paint, and a painted line arrives as a
# band whose near edge the ray reaches first.
PAINT_BAND_TOLERANCE_METERS = 0.6
# Ignore hits implausibly close to the centre (a pit separator, a start box)
# or implausibly far (paint that survived classification but is not this edge).
MIN_HIT_RATIO = 0.45
MAX_HIT_RATIO = 2.2


def _polygon_rings(polygon: Dict[str, Any]) -> List[Any]:
    rings = polygon.get("rings")
    if rings:
        return list(rings)
    points = polygon.get("points")
    return [points] if isinstance(points, list) else []


def _segments_of(polygons: Sequence[Dict[str, Any]]) -> np.ndarray:
    starts, ends = [], []
    for polygon in polygons:
        for ring in _polygon_rings(polygon):
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


def cast_to_segments(
    frame: TrackFrame,
    segments: np.ndarray,
    signs: Dict[str, float],
    min_ratio: float,
    max_ratio: float,
    band_tolerance: Optional[float] = None,
) -> Dict[str, np.ndarray]:
    """Distance from the centreline to the first thing the lateral normal hits.

    With a band tolerance the far side of the same stripe wins, which is what a
    painted line needs -- the limit is its outer edge. Without one the nearest
    hit wins, which is what a kerb needs: its inner edge is where the asphalt
    ends, and its outer edge is already off the track.
    """
    profile = {side: np.full(len(frame.center), np.nan) for side in signs}
    if not len(segments):
        return profile

    seg_a = segments[:, 0, :]
    edge = segments[:, 1, :] - seg_a
    half = frame.half_widths

    for index, (origin, normal) in enumerate(zip(frame.center, frame.normals)):
        limit = half[index]
        if not np.isfinite(limit) or limit <= 0:
            continue
        near, far = limit * min_ratio, limit * max_ratio
        reachable = ((np.abs(seg_a[:, 0] - origin[0]) < far + 5.0)
                     & (np.abs(seg_a[:, 1] - origin[1]) < far + 5.0))
        if not reachable.any():
            continue
        a, e = seg_a[reachable], edge[reachable]
        rel = a - origin

        for side, sign in signs.items():
            direction = normal * sign
            denom = direction[0] * e[:, 1] - direction[1] * e[:, 0]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (rel[:, 0] * e[:, 1] - rel[:, 1] * e[:, 0]) / denom
                u = (rel[:, 0] * direction[1] - rel[:, 1] * direction[0]) / denom
            hit = np.isfinite(t) & (u >= 0.0) & (u <= 1.0) & (t >= near) & (t <= far)
            if not hit.any():
                continue
            distances = t[hit]
            first = distances.min()
            if band_tolerance is None:
                profile[side][index] = float(first)
            else:
                profile[side][index] = float(distances[distances <= first + band_tolerance].max())
    return profile


def kerb_limit_profile(
    track_data: Dict[str, Any],
    frame: TrackFrame,
    signs: Dict[str, float],
    min_ratio: float = 0.6,
    max_ratio: float = 2.5,
) -> Dict[str, np.ndarray]:
    """Where the kerbs say the racing surface ends.

    A kerb marks the edge of the track by construction, and it covers different
    parts of a lap than the paint does: at Interlagos the painted limit is
    missing for 2970 m straight on one side, while kerbs are present for 43% of
    the lap. Its inner edge is the one that matters, so the nearest hit wins.
    """
    polygons = ((track_data.get("kerbGeometry") or {}).get("polygons")) or []
    return cast_to_segments(frame, _segments_of(polygons), signs, min_ratio, max_ratio)


def _ring_segments(track_data: Dict[str, Any], boundary_rings: Sequence[BoundaryRing]) -> np.ndarray:
    """Segments of every accepted ring, as (start, end) pairs in map space."""
    wanted = {(ring.group, ring.ring) for ring in boundary_rings}
    starts, ends = [], []
    for group_index, ring_index, ring in _rings_of(track_data):
        if (group_index, ring_index) not in wanted:
            continue
        points = np.array(ring, dtype=float)[:, :2]
        if len(points) < 2:
            continue
        closed = np.vstack([points, points[:1]])
        starts.append(closed[:-1])
        ends.append(closed[1:])
    if not starts:
        return np.empty((0, 2, 2), dtype=float)
    return np.stack([np.vstack(starts), np.vstack(ends)], axis=1)


def painted_limit_profile(
    track_data: Dict[str, Any],
    frame: TrackFrame,
    boundary_rings: Sequence[BoundaryRing],
) -> Dict[str, np.ndarray]:
    """Per centreline sample, how far out the paint puts the limit on each side.

    Cast the lateral normal and intersect the painted lines, rather than
    assigning each painted point to its nearest sample. Point density then stops
    mattering: a sparsely tesselated line still yields a limit at every sample it
    spans, which is the difference between correcting a corner and skipping it.
    """
    return cast_to_segments(
        frame,
        _ring_segments(track_data, boundary_rings),
        edge_side_signs(track_data, frame),
        MIN_HIT_RATIO,
        MAX_HIT_RATIO,
        band_tolerance=PAINT_BAND_TOLERANCE_METERS,
    )


__all__ = [
    "BoundaryRing",
    "TrackFrame",
    "build_track_frame",
    "identify_boundary_rings",
    "painted_limit_profile",
    "BOUNDARY_RATIO_RANGE",
    "MAX_BOUNDARY_RATIO_SPREAD",
]
