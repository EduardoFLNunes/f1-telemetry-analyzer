from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .models import (
    PHASE_APEX,
    PHASE_BRAKING,
    PHASE_ENTRY,
    PHASE_EXIT,
    PHASE_STRAIGHT_AFTER,
    CornerSegment,
    PhaseBounds,
)
from .utils import finite_float


logger = logging.getLogger(__name__)


class CornerSegmenter:
    def segment(self, track_data: Optional[Dict[str, Any]], lap_df: pd.DataFrame) -> List[CornerSegment]:
        track_length = self._track_length(track_data, lap_df)
        distances, curvature = self._track_curvature_profile(track_data)
        if len(distances) < 10 or np.nanmax(np.abs(curvature)) <= 1e-8:
            distances, curvature = self._lap_curvature_profile(lap_df)

        if len(distances) < 10 or np.nanmax(np.abs(curvature)) <= 1e-8:
            return self._speed_minima_segments(lap_df, track_length)

        order = np.argsort(distances)
        distances = np.asarray(distances, dtype=float)[order]
        curvature = np.asarray(curvature, dtype=float)[order]
        track_length = track_length or float(max(distances[-1], 1.0))

        abs_curv = np.abs(np.nan_to_num(curvature, nan=0.0))
        window = max(3, min(21, int(len(abs_curv) / 120) | 1))
        kernel = np.ones(window, dtype=float) / window
        smooth = np.convolve(abs_curv, kernel, mode="same")
        positive = smooth[smooth > 0]
        if positive.size == 0:
            return self._speed_minima_segments(lap_df, track_length)

        threshold = max(float(np.quantile(positive, 0.70)), float(np.mean(positive) + 0.15 * np.std(positive)), 0.00045)
        active = smooth >= threshold
        ranges = self._active_ranges(distances, active, track_length)
        merged = self._merge_ranges(ranges, track_length, merge_gap_m=45.0)

        segments: List[CornerSegment] = []
        for start_s, end_s in merged:
            length = self._distance_between(start_s, end_s, track_length)
            if length < 18.0 or length > max(650.0, track_length * 0.18):
                continue
            mask = self._range_mask(distances, start_s, end_s, track_length)
            if not mask.any():
                continue
            idxs = np.where(mask)[0]
            peak_idx = idxs[int(np.argmax(smooth[idxs]))]
            apex_s = float(distances[peak_idx] % track_length)
            peak = float(smooth[peak_idx])
            corner_id = len(segments) + 1
            phases = self._phase_bounds(start_s, end_s, apex_s, track_length)
            segments.append(
                CornerSegment(
                    corner_id=corner_id,
                    start_s=float(start_s % track_length),
                    end_s=float(end_s % track_length),
                    apex_s=apex_s,
                    curvature_peak=peak,
                    phases=phases,
                )
            )

        if len(segments) < 2:
            fallback = self._speed_minima_segments(lap_df, track_length)
            return fallback or segments

        return segments[:24]

    def _track_curvature_profile(self, track_data: Optional[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        if not track_data:
            return np.array([]), np.array([])

        centerline = track_data.get("centerline", [])
        distances: List[float] = []
        curvature: List[float] = []
        if isinstance(centerline, dict):
            distances = [float(value) for value in centerline.get("distance", [])]
            curvature = [float(value) for value in centerline.get("curvature", track_data.get("curvature", []))]
        else:
            for point in centerline:
                if isinstance(point, dict):
                    distance = finite_float(point.get("distance"))
                    curv = finite_float(point.get("curvature"))
                else:
                    distance = finite_float(getattr(point, "distance", None))
                    curv = finite_float(getattr(point, "curvature", None))
                if distance is not None and curv is not None:
                    distances.append(distance)
                    curvature.append(curv)

        if len(distances) != len(curvature):
            curvature = track_data.get("curvature", [])
        if len(distances) != len(curvature):
            return np.array([]), np.array([])
        return np.asarray(distances, dtype=float), np.asarray(curvature, dtype=float)

    def _lap_curvature_profile(self, lap_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        needed = {"x", "z", "s"}
        if lap_df.empty or not needed.issubset(lap_df.columns):
            return np.array([]), np.array([])
        points = lap_df[["x", "z"]].astype(float).interpolate().ffill().bfill().to_numpy()
        if len(points) < 10:
            return np.array([]), np.array([])
        dx = np.gradient(points[:, 0])
        dz = np.gradient(points[:, 1])
        ddx = np.gradient(dx)
        ddz = np.gradient(dz)
        denom = np.power(dx * dx + dz * dz, 1.5)
        curvature = np.divide(dx * ddz - dz * ddx, denom, out=np.zeros_like(dx), where=denom > 1e-6)
        return lap_df["s"].to_numpy(dtype=float), curvature

    def _speed_minima_segments(self, lap_df: pd.DataFrame, track_length: float) -> List[CornerSegment]:
        if lap_df.empty or "speed_kmh" not in lap_df or "s" not in lap_df:
            return []
        df = lap_df.sort_values("s").reset_index(drop=True)
        speeds = df["speed_kmh"].rolling(7, center=True, min_periods=1).mean().to_numpy(dtype=float)
        if len(speeds) < 20 or np.nanmax(speeds) - np.nanmin(speeds) < 8.0:
            return []
        threshold = float(np.nanquantile(speeds, 0.35))
        minima = []
        for idx in range(3, len(speeds) - 3):
            if speeds[idx] <= threshold and speeds[idx] == np.nanmin(speeds[idx - 3:idx + 4]):
                minima.append(idx)
        segments = []
        last_s = -9999.0
        for idx in minima:
            apex_s = float(df.iloc[idx]["s"] % track_length)
            if abs(apex_s - last_s) < 120.0:
                continue
            last_s = apex_s
            start_s = apex_s - 75.0
            end_s = apex_s + 95.0
            corner_id = len(segments) + 1
            segments.append(
                CornerSegment(
                    corner_id=corner_id,
                    start_s=float(start_s % track_length),
                    end_s=float(end_s % track_length),
                    apex_s=apex_s,
                    curvature_peak=0.0,
                    phases=self._phase_bounds(start_s, end_s, apex_s, track_length),
                )
            )
            if len(segments) >= 18:
                break
        return segments

    def _phase_bounds(self, start_s: float, end_s: float, apex_s: float, track_length: float) -> Dict[str, PhaseBounds]:
        entry_start = start_s - 85.0
        braking_start = start_s - 55.0
        apex_start = apex_s - 18.0
        apex_end = apex_s + 18.0
        exit_end = end_s + 75.0
        straight_end = end_s + 190.0

        return {
            PHASE_ENTRY: self._bounds(entry_start, braking_start, track_length),
            PHASE_BRAKING: self._bounds(braking_start, apex_start, track_length),
            PHASE_APEX: self._bounds(apex_start, apex_end, track_length),
            PHASE_EXIT: self._bounds(apex_end, exit_end, track_length),
            PHASE_STRAIGHT_AFTER: self._bounds(exit_end, straight_end, track_length),
        }

    @staticmethod
    def _bounds(start_s: float, end_s: float, track_length: float) -> PhaseBounds:
        if track_length > 0:
            return PhaseBounds(start_s=float(start_s % track_length), end_s=float(end_s % track_length))
        return PhaseBounds(start_s=float(start_s), end_s=float(end_s))

    def _active_ranges(self, distances: np.ndarray, active: np.ndarray, track_length: float) -> List[Tuple[float, float]]:
        ranges: List[Tuple[float, float]] = []
        start_idx: Optional[int] = None
        for idx, flag in enumerate(active):
            if flag and start_idx is None:
                start_idx = idx
            elif not flag and start_idx is not None:
                ranges.append((float(distances[start_idx]), float(distances[max(start_idx, idx - 1)])))
                start_idx = None
        if start_idx is not None:
            ranges.append((float(distances[start_idx]), float(distances[-1])))

        if len(ranges) > 1 and track_length > 0:
            first = ranges[0]
            last = ranges[-1]
            wrap_gap = (first[0] + track_length) - last[1]
            if wrap_gap <= 45.0:
                ranges = [(last[0], first[1])] + ranges[1:-1]
        return ranges

    def _merge_ranges(self, ranges: List[Tuple[float, float]], track_length: float, merge_gap_m: float) -> List[Tuple[float, float]]:
        if not ranges:
            return []
        ranges = sorted(ranges, key=lambda item: item[0] % max(track_length, 1.0))
        merged = [ranges[0]]
        for start_s, end_s in ranges[1:]:
            prev_start, prev_end = merged[-1]
            gap = self._distance_between(prev_end, start_s, track_length)
            if gap <= merge_gap_m:
                merged[-1] = (prev_start, end_s)
            else:
                merged.append((start_s, end_s))
        return merged

    @staticmethod
    def _range_mask(distances: np.ndarray, start_s: float, end_s: float, track_length: float) -> np.ndarray:
        if track_length <= 0:
            low, high = sorted((start_s, end_s))
            return (distances >= low) & (distances <= high)
        start = start_s % track_length
        end = end_s % track_length
        s = distances % track_length
        if end >= start:
            return (s >= start) & (s <= end)
        return (s >= start) | (s <= end)

    @staticmethod
    def _distance_between(start_s: float, end_s: float, track_length: float) -> float:
        if track_length <= 0:
            return abs(end_s - start_s)
        start = start_s % track_length
        end = end_s % track_length
        if end >= start:
            return end - start
        return (track_length - start) + end

    @staticmethod
    def _track_length(track_data: Optional[Dict[str, Any]], lap_df: pd.DataFrame) -> float:
        if track_data:
            length = finite_float(track_data.get("trackLength", track_data.get("track_length")))
            if length and length > 0:
                return length
        if not lap_df.empty and "track_length" in lap_df:
            length = finite_float(lap_df["track_length"].dropna().max())
            if length and length > 0:
                return length
        if not lap_df.empty and "s" in lap_df:
            return float(max(lap_df["s"].max(), 1.0))
        return 1.0
