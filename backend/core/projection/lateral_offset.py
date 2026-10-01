"""Signed lateral offset of the car from the centerline, and its sign convention.

Two conventions exist in the project, and they are opposite:

* the runtime (this module) uses `normal = (-t_z, t_x)` in the world X/Z
  plane, which points to the driver's **right**. `lateralOffset`, `lateral_offset`
  and `L` in every recorded sample are therefore positive to the right;
* the offline `ml` pipeline measures `lateral` against a normal that points to
  the driver's **left** (verified against the track: its first detected corner
  after the line, at s ~ 300 m, comes out left-handed, as the S do Senna is).

Measured on recordings from May, June and August 2026: the recorded offset and
the `ml` lateral correlate at -0.95 to -0.99, and |ml + recorded| stays under
0.51 m at the 95th percentile -- the residue is the `ml` centerline smoothing,
not a sign problem.

The runtime convention is kept as it is: 11 GB of recordings already carry it,
and every runtime consumer either takes `abs()` or subtracts two offsets of the
same convention. What changes is that nothing converts by assumption any more:
`to_left_positive` is the one place that crosses from one to the other.
"""

import numpy as np
from typing import Tuple

# Side of the track a positive recorded offset is on, as seen by the driver.
RECORDED_OFFSET_POSITIVE_SIDE = "right"


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return np.array([1.0, 0.0], dtype=float)
    return vector / norm


def tangent_and_normal(segment_vector: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    tangent = normalize(segment_vector)
    normal = np.array([-tangent[1], tangent[0]], dtype=float)
    return tangent, normal


def signed_lateral_offset(world_point: np.ndarray, projected_point: np.ndarray, normal: np.ndarray) -> float:
    return float(np.dot(world_point - projected_point, normal))


def to_left_positive(recorded_offset):
    """Recorded (right-positive) offset -> left-positive, the `ml` convention."""
    if recorded_offset is None:
        return None
    return -recorded_offset
