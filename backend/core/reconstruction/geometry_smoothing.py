import numpy as np
from scipy.signal import savgol_filter

class GeometrySmoothing:
    @staticmethod
    def remove_invalid(points: np.ndarray) -> np.ndarray:
        if points.size == 0:
            return points
        mask = np.isfinite(points).all(axis=1)
        return points[mask]

    @staticmethod
    def remove_duplicate_points(points: np.ndarray, min_spacing: float = 0.75) -> np.ndarray:
        if len(points) <= 1:
            return points

        kept = [points[0]]
        for point in points[1:]:
            if np.linalg.norm(point - kept[-1]) >= min_spacing:
                kept.append(point)
        return np.asarray(kept, dtype=float)

    @staticmethod
    def remove_distance_outliers(points: np.ndarray, max_jump_factor: float = 6.0) -> np.ndarray:
        if len(points) < 5:
            return points

        dists = np.linalg.norm(np.diff(points, axis=0), axis=1)
        positive = dists[dists > 0.05]
        if len(positive) == 0:
            return points

        median = np.median(positive)
        max_jump = max(median * max_jump_factor, 25.0)
        keep = np.ones(len(points), dtype=bool)
        keep[1:] = dists <= max_jump
        return points[keep]

    @staticmethod
    def smooth_points(points: np.ndarray, window_length: int = 11, polyorder: int = 3) -> np.ndarray:
        """
        Smooths a sequence of points using a Savitzky-Golay filter.
        points: (N, 2) or (N, 3)
        """
        if len(points) < 5:
            return points

        window_length = min(window_length, len(points) - 1 if len(points) % 2 == 0 else len(points))
        if window_length % 2 == 0:
            window_length -= 1
        if window_length <= polyorder:
            return points

        smoothed = np.zeros_like(points)
        for i in range(points.shape[1]):
            smoothed[:, i] = savgol_filter(points[:, i], window_length, polyorder, mode="wrap")
            
        return smoothed

    @staticmethod
    def resample_evenly(points: np.ndarray, step_meters: float = 2.0, closed: bool = True) -> np.ndarray:
        """
        Resamples points to be evenly spaced by distance.
        """
        if len(points) < 2:
            return points

        source = points
        if closed and np.linalg.norm(points[0] - points[-1]) > 1e-6:
            source = np.vstack([points, points[0]])

        diffs = np.diff(source, axis=0)
        dists = np.sqrt(np.sum(diffs**2, axis=1))
        accum_dist = np.concatenate([[0], np.cumsum(dists)])
        total_length = accum_dist[-1]

        if total_length <= 0:
            return points[:1]

        num_points = max(4, int(total_length / step_meters))
        new_distances = np.linspace(0, total_length, num_points, endpoint=not closed)

        new_points = np.zeros((num_points, points.shape[1]))
        for i in range(points.shape[1]):
            new_points[:, i] = np.interp(new_distances, accum_dist, source[:, i])
            
        return new_points
