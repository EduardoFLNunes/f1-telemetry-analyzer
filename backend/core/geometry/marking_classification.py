"""Tell the painted markings apart by what they mark.

`build_marking_geometry` returns the paint as connected components of rings and
says nothing about what any of it is: the line bounding the track, the lines
bounding the pit lane, and the paint around an access road all arrive the same.
The map needs them apart, because they read as different things to a driver.

The split is measured against the two lanes the game itself ships, `fast_lane.ai`
and `pit_lane.ai`, and against nothing else. In particular it does not use the
reconstructed corridor: that geometry exists to project telemetry, and asking it
to also justify the drawing is what produced a map that disagreed with the track.

Three verdicts, decided per segment of contour rather than per ring, because a
single painted line can be the track limit for part of its length and the pit
lane limit for the rest:

  * `boxes`   -- paint lying inside the pit corridor
  * `servico` -- paint that leaves the track band altogether, which is how an
                 access road opening reads: the limit line bulges out and back
  * `limite`  -- everything else, the paint that bounds the racing surface

Every threshold below came from measuring this data, not from taste; the reasons
are recorded at each constant.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


# `pit_lane.ai` starts on the racing line and only then peels off into the pits.
# Measured against the whole file, track paint looks like pit paint. Only the
# stretch this far from the racing line is the pit corridor proper -- on
# Interlagos that is one contiguous run of 1114 m out of 2065 m.
OFF_TRACK_M = 10.0

# How close paint must be to the corridor axis to be pit paint. The histogram of
# paint by distance from that axis has two populations: 5112 m between 1.0 and
# 4.5 m -- the pit lane's own lines, either side of the axis -- then a valley of
# 143 m across 5.5-7.5 m, then 1042 m between 7.5 and 9.0 m, which is the track
# limit line running parallel beyond the pit wall. The cut sits just past the
# first population: nothing outside the pit lane's own painted edge is pit paint.
IN_CORRIDOR_M = 5.0

# Where the track paint runs out. By the same method, the limite paint thins to
# 86 m between 18 and 20 m from the racing line and to 9 m between 20 and 22 m.
# Past that is a separate, smaller population: the access-road teeth.
TRACK_BAND_M = 18.0
TOOTH_CORE_M = 20.0

# A tooth can reach far enough that its tip comes back near the racing line,
# which momentarily reads as track paint again. Cores split by less than this
# much contour are the same tooth.
TOOTH_GAP_M = 60.0

# Verdict runs shorter than this are absorbed into their neighbours instead of
# being cut out, so short marks stay whole rather than being shaved into slivers.
MIN_RUN_M = 15.0

# A painted line does not change identity for a sliver of its length. Where the
# pit exit merges, the track limit line runs close enough to the corridor for a
# few dozen metres to pass the distance test -- an artefact of the convergence,
# not a stretch of pit paint. On Interlagos the contour that is genuinely part
# track and part pit lane comes out at 25% pit; the one that is track throughout
# came out at 3.5%.
MIN_PIT_SHARE = 0.10

LIMITE = "limite"
BOXES = "boxes"
SERVICO = "servico"


def _as_map_points(lane: Optional[Dict[str, Any]]) -> np.ndarray:
    if not lane:
        return np.empty((0, 2), dtype=float)
    coords = [point.get("mapPosition") for point in lane.get("points", []) or []]
    return np.array([c for c in coords if c], dtype=float)


def _distance_to_path(point: Sequence[float], path: np.ndarray) -> float:
    """Shortest distance from a point to an open polyline."""
    if len(path) < 2:
        return math.inf
    a = path[:-1]
    b = path[1:]
    d = b - a
    length2 = (d * d).sum(axis=1)
    length2[length2 == 0] = 1e-9
    rel = np.asarray(point, dtype=float) - a
    t = np.clip((rel * d).sum(axis=1) / length2, 0.0, 1.0)
    foot = a + d * t[:, None]
    delta = np.asarray(point, dtype=float) - foot
    return float(np.sqrt((delta * delta).sum(axis=1)).min())


def pit_corridor(pit_lane: Optional[Dict[str, Any]], fast_lane: Dict[str, Any]) -> np.ndarray:
    """The part of the pit path that has actually left the track."""
    pit = _as_map_points(pit_lane)
    fast = _as_map_points(fast_lane)
    if len(pit) < 2 or len(fast) < 2:
        return np.empty((0, 2), dtype=float)
    off = [index for index, point in enumerate(pit)
           if _distance_to_path(point, fast) > OFF_TRACK_M]
    if len(off) < 2:
        return np.empty((0, 2), dtype=float)
    return pit[off[0]: off[-1] + 1]


def _label_segments(ring: np.ndarray, corridor: np.ndarray, fast: np.ndarray) -> List[str]:
    labels = []
    count = len(ring)
    for index in range(count):
        a, b = ring[index], ring[(index + 1) % count]
        mid = (a + b) / 2.0
        to_track = _distance_to_path(mid, fast)
        to_pit = _distance_to_path(mid, corridor) if len(corridor) else math.inf
        if to_pit <= IN_CORRIDOR_M and to_pit < to_track:
            labels.append(BOXES)
        elif to_track > TRACK_BAND_M:
            labels.append(SERVICO)
        else:
            labels.append(LIMITE)
    return labels


def _segment_lengths(ring: np.ndarray) -> List[float]:
    count = len(ring)
    return [float(np.linalg.norm(ring[(index + 1) % count] - ring[index])) for index in range(count)]


def _runs(labels: Sequence[str], lengths: Sequence[float]) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    for index, label in enumerate(labels):
        if runs and runs[-1]["label"] == label:
            runs[-1]["end"] = index + 1
            runs[-1]["length"] += lengths[index]
        else:
            runs.append({"label": label, "start": index, "end": index + 1,
                         "length": lengths[index]})
    if len(runs) > 1 and runs[0]["label"] == runs[-1]["label"]:
        runs[0]["start"] = runs[-1]["start"]
        runs[0]["length"] += runs[-1]["length"]
        runs.pop()
    return runs


def _join_short_gaps(runs: List[Dict[str, Any]], label: str, max_gap: float) -> List[Dict[str, Any]]:
    """Two runs of `label` split by a short run of something else are one run."""
    if len(runs) < 3:
        return runs
    changed = True
    while changed and len(runs) > 2:
        changed = False
        for index, run in enumerate(runs):
            previous = runs[index - 1]
            following = runs[(index + 1) % len(runs)]
            if (run["label"] != label and previous["label"] == label
                    and following["label"] == label and run["length"] <= max_gap):
                run["label"] = label
                changed = True
                break
        if changed:
            runs = _merge(runs)
    return runs


def _merge(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for run in runs:
        if merged and merged[-1]["label"] == run["label"]:
            merged[-1]["end"] = run["end"]
            merged[-1]["length"] += run["length"]
        else:
            merged.append(dict(run))
    if len(merged) > 1 and merged[0]["label"] == merged[-1]["label"]:
        merged[0]["start"] = merged[-1]["start"]
        merged[0]["length"] += merged[-1]["length"]
        merged.pop()
    return merged


def _absorb_short_runs(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    while len(runs) > 1:
        shortest = min(runs, key=lambda run: run["length"])
        if shortest["length"] >= MIN_RUN_M:
            break
        index = runs.index(shortest)
        neighbour = runs[index - 1] if runs[index - 1]["length"] >= runs[
            (index + 1) % len(runs)]["length"] else runs[(index + 1) % len(runs)]
        shortest["label"] = neighbour["label"]
        runs = _merge(runs)
    return runs


def _span(run: Dict[str, Any], count: int) -> List[int]:
    if run["start"] < run["end"]:
        return list(range(run["start"], run["end"]))
    return list(range(run["start"], count)) + list(range(0, run["end"]))


def _relabel_by_majority(runs, labels, lengths, count) -> List[Dict[str, Any]]:
    """Absorption decides where the cuts fall; it must not decide the names."""
    for run in runs:
        weights: Dict[str, float] = {}
        for index in _span(run, count):
            weights[labels[index]] = weights.get(labels[index], 0.0) + lengths[index]
        run["label"] = max(weights, key=weights.get)
    return _merge(runs)


def _validate_pit_runs(runs, ring, corridor, count) -> List[Dict[str, Any]]:
    """A run only stays `boxes` if its paint really lies inside the pit lane."""
    if not len(corridor):
        for run in runs:
            if run["label"] == BOXES:
                run["label"] = LIMITE
        return _merge(runs)
    for run in runs:
        if run["label"] != BOXES:
            continue
        samples = []
        for index in _span(run, count):
            mid = (ring[index] + ring[(index + 1) % count]) / 2.0
            samples.append((_distance_to_path(mid, corridor),
                            float(np.linalg.norm(ring[(index + 1) % count] - ring[index]))))
        samples.sort()
        half = sum(weight for _, weight in samples) / 2.0
        running, median = 0.0, samples[-1][0]
        for distance, weight in samples:
            running += weight
            if running >= half:
                median = distance
                break
        if median > IN_CORRIDOR_M:
            run["label"] = LIMITE
    return _merge(runs)


def _drop_marginal_pit(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    total = sum(run["length"] for run in runs)
    pit = sum(run["length"] for run in runs if run["label"] == BOXES)
    if total > 0 and 0.0 < pit / total < MIN_PIT_SHARE:
        for run in runs:
            if run["label"] == BOXES:
                run["label"] = LIMITE
        return _merge(runs)
    return runs


def classify_marking_rings(
    marking_geometry: Dict[str, Any],
    fast_lane: Dict[str, Any],
    pit_lane: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """-> the same geometry with a `features` list of classified polylines.

    `polygons` is left untouched: the paint-agreement and paint-correction passes
    read it, and they are part of the measuring side of the system.
    """
    fast = _as_map_points(fast_lane)
    corridor = pit_corridor(pit_lane, fast_lane)
    features: List[Dict[str, Any]] = []
    if len(fast) < 2:
        marking_geometry["features"] = features
        marking_geometry["classification"] = {"status": "MISSING_FAST_LANE"}
        return marking_geometry

    for polygon_index, polygon in enumerate(marking_geometry.get("polygons", []) or []):
        for ring_index, raw_ring in enumerate(polygon.get("rings", []) or []):
            ring = np.array(raw_ring, dtype=float)
            if len(ring) < 3:
                continue
            ring_id = f"{polygon_index}.{ring_index}"
            lengths = _segment_lengths(ring)
            labels = _label_segments(ring, corridor, fast)

            runs = _runs(labels, lengths)
            runs = _join_short_gaps(runs, SERVICO, TOOTH_GAP_M)
            runs = _absorb_short_runs(runs)
            runs = _relabel_by_majority(runs, labels, lengths, len(ring))
            runs = _validate_pit_runs(runs, ring, corridor, len(ring))
            runs = _drop_marginal_pit(runs)

            if len(runs) == 1:
                features.append({
                    "id": ring_id,
                    "kind": runs[0]["label"],
                    "closed": True,
                    "lengthM": round(runs[0]["length"], 1),
                    "points": [[round(float(x), 3), round(float(y), 3)] for x, y in ring],
                })
                continue

            counters: Dict[str, int] = {}
            for run in runs:
                counters[run["label"]] = counters.get(run["label"], 0) + 1
                indices = _span(run, len(ring)) + [run["end"] % len(ring)]
                points = [ring[index % len(ring)] for index in indices]
                features.append({
                    "id": f'{ring_id}{run["label"][0]}{counters[run["label"]]}',
                    "kind": run["label"],
                    "closed": False,
                    "cutFrom": ring_id,
                    "lengthM": round(run["length"], 1),
                    "points": [[round(float(x), 3), round(float(y), 3)] for x, y in points],
                })

    totals: Dict[str, float] = {}
    for feature in features:
        totals[feature["kind"]] = totals.get(feature["kind"], 0.0) + feature["lengthM"]
    marking_geometry["features"] = features
    marking_geometry["classification"] = {
        "status": "OK",
        "featureCount": len(features),
        "cutCount": sum(1 for feature in features if feature.get("cutFrom")),
        "lengthByKind": {kind: round(length, 1) for kind, length in sorted(totals.items())},
        "pitCorridorLengthM": round(
            float(np.sum(np.linalg.norm(np.diff(corridor, axis=0), axis=1))), 1
        ) if len(corridor) > 1 else 0.0,
        "thresholds": {
            "offTrackM": OFF_TRACK_M,
            "inCorridorM": IN_CORRIDOR_M,
            "trackBandM": TRACK_BAND_M,
            "toothCoreM": TOOTH_CORE_M,
            "minRunM": MIN_RUN_M,
            "minPitShare": MIN_PIT_SHARE,
        },
    }
    return marking_geometry
