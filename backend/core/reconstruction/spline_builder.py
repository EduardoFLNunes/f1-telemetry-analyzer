import numpy as np
from scipy.interpolate import CubicSpline
from typing import Tuple

class SplineBuilder:
    @staticmethod
    def build_closed_spline(points: np.ndarray) -> Tuple[CubicSpline, CubicSpline, np.ndarray]:
        """
        Builds a closed cubic spline from a sequence of points (x, z).
        Points should be (N, 2).
        Returns: (spline_x, spline_z, accumulated_distance)
        """
        if len(points) < 4:
            raise ValueError("At least 4 unique points are required to build a closed spline")

        if np.linalg.norm(points[0] - points[-1]) < 1e-6:
            points = points[:-1]

        diffs = np.diff(points, axis=0)
        dists = np.sqrt(np.sum(diffs**2, axis=1))

        loop_dist = np.sqrt(np.sum((points[-1] - points[0])**2))
        dists = np.append(dists, loop_dist)
        accum_dist = np.concatenate([[0], np.cumsum(dists)])

        keep = np.concatenate([[True], np.diff(accum_dist) > 1e-6])
        accum_dist = accum_dist[keep]
        if len(accum_dist) < 5:
            raise ValueError("Degenerate point set for periodic spline")

        valid_points = points[keep[:-1]]
        total_length = accum_dist[-1]

        s_periodic = accum_dist
        x_periodic = np.append(valid_points[:, 0], valid_points[0, 0])
        z_periodic = np.append(valid_points[:, 1], valid_points[0, 1])

        spline_x = CubicSpline(s_periodic, x_periodic, bc_type="periodic")
        spline_z = CubicSpline(s_periodic, z_periodic, bc_type="periodic")
        
        return spline_x, spline_z, accum_dist
