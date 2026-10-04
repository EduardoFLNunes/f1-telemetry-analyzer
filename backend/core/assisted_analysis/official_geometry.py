"""The official track geometry (ADR 0002), as the coach reads and projects on it.

The ML pipeline measures every lap on one grid: `ml.track.geometry.load_geometry`,
identified by `geometry_id`. The coach used to measure on the runtime's progress
`p`, which is a different ruler -- and depending on the cache a session was
recorded with, three different rulers, up to ~31 m apart. Recordings from
2026-08-09 carry no `p` at all, so their 56 laps never reached the coach.

ADR 0013 moves the coach onto the official geometry: `s` and `d` come from the
world position (`world_x`, `world_z`), projected on the grid the ML pipeline
exports (`ml.scripts.export_geometry`), both live and when the model is fitted.
The packaged backend never imports `ml`; it only reads the exported JSON.

The projection itself is not new. `core.spatial_engine.MapMatchingEngine` already
projects onto any polyline with temporal continuity (a candidate far from the
last `s` is penalised -- which is what separates the pit straight from the
return road beside it) and handles the finish line. Only the geometry changes:
it gets the official grid instead of the runtime centerline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

from ..projection.lateral_offset import to_left_positive
from ..spatial_engine import CanonicalTrackSpace, MapMatchingEngine

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = {"official-geometry-1"}
# The microsector edges must be the equal-distance ones: the coach turns `s`
# into a microsector with `int(s / length * 60)`.
EDGE_TOLERANCE_M = 1e-2


def geometry_path(runtime_root: Path, track: str) -> Path:
    """Next to the driver model, with the same sanitising, plus a suffix."""
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in (track or "unknown"))
    return Path(runtime_root) / "data" / "reference_models" / f"{safe}.geometry.json"


@dataclass
class OfficialGeometry:
    track: str
    geometry_id: str
    length: float
    x: np.ndarray
    z: np.ndarray
    s: np.ndarray
    edges: np.ndarray

    @property
    def microsectors(self) -> int:
        return int(self.edges.size - 1)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OfficialGeometry":
        if payload.get("version") not in SUPPORTED_VERSIONS:
            raise ValueError(f"unsupported geometry format {payload.get('version')!r}")
        if not payload.get("geometry_id"):
            raise ValueError("geometry file has no geometry_id")
        x = np.asarray(payload["x"], dtype=float)
        z = np.asarray(payload["z"], dtype=float)
        s = np.asarray(payload["s"], dtype=float)
        edges = np.asarray(payload["microsector_edges"], dtype=float)
        length = float(payload["track_length"])
        if not (x.size == z.size == s.size) or x.size < 10:
            raise ValueError("geometry arrays disagree in size")
        expected = np.linspace(0.0, length, edges.size)
        if edges.size < 2 or np.max(np.abs(edges - expected)) > EDGE_TOLERANCE_M:
            raise ValueError("microsector edges are not equal-distance")
        return cls(
            track=str(payload.get("track", "")),
            geometry_id=str(payload["geometry_id"]),
            length=length,
            x=x,
            z=z,
            s=s,
            edges=edges,
        )

    @classmethod
    def load(cls, path: Path) -> Optional["OfficialGeometry"]:
        path = Path(path)
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as error:  # a broken file must not take the app down
            logger.warning("Official geometry unreadable at %s: %s", path, error)
            return None

    def projector(self) -> "CoachProjector":
        return CoachProjector(self)


def find_official_geometry(roots: Iterable[Path], track: str) -> Optional[OfficialGeometry]:
    """First geometry found for this track, searching the roots in order."""
    for root in roots:
        if root is None:
            continue
        geometry = OfficialGeometry.load(geometry_path(Path(root), track))
        if geometry is not None:
            return geometry
    return None


# Hard continuity of the coach's projection (pedido 14). At 280 km/h and 60 Hz
# a sample moves 1.3 m; the limit there is ~7 m, and a one-second recording hole
# still allows ~120 m.
MAX_ADVANCE_FACTOR = 1.5
MAX_ADVANCE_MARGIN_M = 5.0


class CoachProjector:
    """World X/Z -> (s, d) on the official grid, one sample after another.

    `s` is put back on the exported ruler: the engine measures arc length as the
    sum of the polyline's chords, and the grid was built with a uniform step, so
    a single scale factor maps one onto the other. `d` is converted from the
    engine's right-positive normal to the ML convention, left-positive, through
    the one function that does that (ADR 0003).
    """

    def __init__(self, geometry: OfficialGeometry):
        self.geometry = geometry
        self.space = CanonicalTrackSpace(geometry.x, geometry.z)
        self.scale = geometry.length / self.space.total_length
        # Hard continuity (pedido 14): `s` never moves further between two
        # samples than speed * interval * 1.5 + 5 m. Only this instance -- the
        # map and the live panel keep the engine's default.
        self.engine = MapMatchingEngine(self.space, max_advance_factor=MAX_ADVANCE_FACTOR,
                                        max_advance_margin_m=MAX_ADVANCE_MARGIN_M)

    def reset(self) -> None:
        """Forget the last position (new session, or a jump the car really made)."""
        self.engine.last_s = None

    def project(
        self, x: float, z: float, speed_mps: Optional[float] = None, dt_s: Optional[float] = None
    ) -> Tuple[float, float]:
        # `velocity` only tunes a log line inside the engine; a large value keeps
        # it from warning on every legitimate jump (box exit, a reset).
        result = self.engine.project(float(x), float(z), velocity=1e6, speed_mps=speed_mps, dt_s=dt_s)
        s = float(result["s"]) * self.scale
        return s % self.geometry.length, float(to_left_positive(float(result["L"])))


# A projection jump: `s` moves further between two samples than the car can.
# Two conditions, so that a recording hole (time missing, the distance covered
# at a normal speed) is not mistaken for one -- `_has_hole` in the model handles
# holes. 120 m/s is 432 km/h, well above this car's 277 km/h top speed, and 30 m
# is far above the projection's own sample-to-sample noise (p99 0.04 m against
# the ML projection on valid laps).
MAX_IMPLIED_SPEED_MPS = 120.0
MIN_JUMP_M = 30.0


def projection_jumped(projected: pd.DataFrame, length: float) -> bool:
    """Whether the projected `s` of a lap jumps further than a car can move.

    Measured on lap 11 of 2026-08-16_03-30-14: the car went 43 m off the track,
    the nearest stretch of track became a different one, `s` jumped 120 m
    forward in one sample twice, and two microsectors came out at 0.009 s and
    0.013 s -- which then became the "best ever" there. A lap like that cannot
    be timed slice by slice, so it does not teach the model.
    """
    frame = projected[["s", "elapsed_s"]].apply(pd.to_numeric, errors="coerce").dropna() if "elapsed_s" in projected else None
    if frame is None or len(frame) < 2:
        return True
    s = frame["s"].to_numpy(dtype=float)
    t = frame["elapsed_s"].to_numpy(dtype=float)
    steps = np.mod(np.diff(s) + length / 2.0, length) - length / 2.0     # the finish line is not a jump
    dt = np.maximum(np.diff(t), 1e-3)
    jumps = (np.abs(steps) > MIN_JUMP_M) & (np.abs(steps) / dt > MAX_IMPLIED_SPEED_MPS)
    return bool(jumps.any())


def project_lap(df: pd.DataFrame, geometry: OfficialGeometry) -> pd.DataFrame:
    """A lap with `s`, `p` and `d` recomputed on the official geometry.

    Every lap is projected the same way whatever it was recorded with -- the
    runtime's `p` (when there is one) is ignored, which is what puts laps from
    different caches, and the 2026-08-09 laps that have no `p`, on one ruler.
    """
    out = df.copy()
    if out.empty or "x" not in out.columns or "z" not in out.columns:
        out["s"], out["p"], out["d"] = np.nan, np.nan, np.nan
        return out
    projector = geometry.projector()
    xs = pd.to_numeric(out["x"], errors="coerce").to_numpy(dtype=float)
    zs = pd.to_numeric(out["z"], errors="coerce").to_numpy(dtype=float)
    speed = (
        pd.to_numeric(out["speed_kmh"], errors="coerce").to_numpy(dtype=float) / 3.6
        if "speed_kmh" in out.columns else np.full(xs.size, np.nan)
    )
    clock = (
        pd.to_numeric(out["elapsed_s"], errors="coerce").to_numpy(dtype=float)
        if "elapsed_s" in out.columns else np.full(xs.size, np.nan)
    )
    s_values = np.full(xs.size, np.nan)
    d_values = np.full(xs.size, np.nan)
    previous_clock = None
    for index, (x, z) in enumerate(zip(xs, zs)):
        if np.isfinite(x) and np.isfinite(z):
            dt = clock[index] - previous_clock if previous_clock is not None and np.isfinite(clock[index]) else None
            s_values[index], d_values[index] = projector.project(
                x, z, speed_mps=float(speed[index]) if np.isfinite(speed[index]) else None, dt_s=dt
            )
            previous_clock = clock[index] if np.isfinite(clock[index]) else previous_clock
    out["s"] = s_values
    out["p"] = s_values / geometry.length
    out["d"] = d_values
    return out
