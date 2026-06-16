from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .models import (
    PHASE_APEX,
    PHASE_BRAKING,
    PHASE_ENTRY,
    PHASE_EXIT,
    PHASE_STRAIGHT_AFTER,
    CornerMetrics,
    CornerSegment,
)
from .utils import interpolate_elapsed_at_s, max_or_none, mean_or_none, min_or_none, window_mask


class CornerMetricsCalculator:
    def compute(self, lap_df: pd.DataFrame, segments: List[CornerSegment], track_length: float) -> Dict[int, CornerMetrics]:
        df = lap_df.copy()
        if df.empty:
            return {}
        return {segment.corner_id: self.compute_one(df, segment, track_length) for segment in segments}

    def compute_one(self, df: pd.DataFrame, segment: CornerSegment, track_length: float) -> CornerMetrics:
        entry_df = self._phase_df(df, segment, PHASE_ENTRY, track_length)
        braking_df = self._phase_df(df, segment, PHASE_BRAKING, track_length)
        apex_df = self._phase_df(df, segment, PHASE_APEX, track_length)
        exit_df = self._phase_df(df, segment, PHASE_EXIT, track_length)
        straight_df = self._phase_df(df, segment, PHASE_STRAIGHT_AFTER, track_length)
        corner_df = self._window_df(df, segment.start_s, segment.end_s, track_length)
        analysis_df = self._window_df(df, segment.phases[PHASE_ENTRY].start_s, segment.phases[PHASE_STRAIGHT_AFTER].end_s, track_length)

        brake_window = pd.concat([entry_df, braking_df, apex_df]).drop_duplicates().sort_index()
        throttle_window = pd.concat([apex_df, exit_df, straight_df]).drop_duplicates().sort_index()

        brake_start_s = self._first_threshold_s(brake_window, "brake", threshold=0.08)
        brake_release_s = self._last_threshold_s(brake_window, "brake", threshold=0.08)
        throttle_pickup_s = self._first_threshold_s(throttle_window, "throttle", threshold=0.25)
        full_throttle_s = self._first_threshold_s(throttle_window, "throttle", threshold=0.75)

        apex_s = self._apex_s(corner_df, segment.apex_s)
        entry_speed = self._speed_near_s(df, brake_start_s, track_length) or mean_or_none(entry_df["speed_kmh"]) or mean_or_none(braking_df["speed_kmh"])
        min_speed = min_or_none(corner_df["speed_kmh"]) or min_or_none(apex_df["speed_kmh"])
        exit_speed = mean_or_none(straight_df.head(max(1, min(8, len(straight_df))))["speed_kmh"]) or mean_or_none(exit_df.tail(max(1, min(8, len(exit_df))))["speed_kmh"])

        start_elapsed = interpolate_elapsed_at_s(df, segment.phases[PHASE_ENTRY].start_s, track_length)
        end_elapsed = interpolate_elapsed_at_s(df, segment.phases[PHASE_STRAIGHT_AFTER].end_s, track_length)
        segment_time = None
        if start_elapsed is not None and end_elapsed is not None and end_elapsed >= start_elapsed:
            segment_time = end_elapsed - start_elapsed

        phase_line = {
            phase: self._mean_abs_lateral(self._phase_df(df, segment, phase, track_length))
            for phase in (PHASE_ENTRY, PHASE_BRAKING, PHASE_APEX, PHASE_EXIT, PHASE_STRAIGHT_AFTER)
        }

        return CornerMetrics(
            corner_id=segment.corner_id,
            segment_time=segment_time,
            entry_speed_kmh=entry_speed,
            min_speed_kmh=min_speed,
            exit_speed_kmh=exit_speed,
            apex_s=apex_s,
            brake_start_s=brake_start_s,
            brake_peak=max_or_none(brake_window["brake"]) if "brake" in brake_window else None,
            brake_release_s=brake_release_s,
            throttle_pickup_s=throttle_pickup_s,
            full_throttle_s=full_throttle_s,
            coasting_distance_m=self._coasting_distance(analysis_df),
            mean_abs_lateral_offset_m=self._mean_abs_lateral(analysis_df),
            max_abs_lateral_offset_m=self._max_abs_lateral(analysis_df),
            mean_line_deviation_m=self._mean_abs_lateral(analysis_df),
            phase_line_deviation_m=phase_line,
            optional_channels={
                "steering": df.get("steering", pd.Series(dtype=float)).notna().any(),
                "gear": df.get("gear", pd.Series(dtype=float)).notna().any(),
                "rpm": df.get("rpm", pd.Series(dtype=float)).notna().any(),
                "lateralG": df.get("lateral_g", pd.Series(dtype=float)).notna().any(),
                "longitudinalG": df.get("longitudinal_g", pd.Series(dtype=float)).notna().any(),
                "yaw": df.get("yaw", pd.Series(dtype=float)).notna().any(),
                "yawRate": df.get("yaw_rate", pd.Series(dtype=float)).notna().any(),
            },
        )

    def _phase_df(self, df: pd.DataFrame, segment: CornerSegment, phase: str, track_length: float) -> pd.DataFrame:
        bounds = segment.phases[phase]
        return self._window_df(df, bounds.start_s, bounds.end_s, track_length)

    @staticmethod
    def _window_df(df: pd.DataFrame, start_s: float, end_s: float, track_length: float) -> pd.DataFrame:
        if df.empty or "s" not in df:
            return df.iloc[0:0]
        mask = window_mask(df["s"], start_s, end_s, track_length)
        return df.loc[mask].copy()

    @staticmethod
    def _first_threshold_s(df: pd.DataFrame, channel: str, threshold: float) -> Optional[float]:
        if df.empty or channel not in df:
            return None
        active = df[df[channel] >= threshold]
        if active.empty:
            return None
        return float(active.iloc[0]["s"])

    @staticmethod
    def _last_threshold_s(df: pd.DataFrame, channel: str, threshold: float) -> Optional[float]:
        if df.empty or channel not in df:
            return None
        active = df[df[channel] >= threshold]
        if active.empty:
            return None
        return float(active.iloc[-1]["s"])

    @staticmethod
    def _apex_s(df: pd.DataFrame, fallback_s: float) -> Optional[float]:
        if df.empty:
            return fallback_s
        if "speed_kmh" in df and df["speed_kmh"].notna().any():
            idx = df["speed_kmh"].astype(float).idxmin()
            return float(df.loc[idx, "s"])
        return fallback_s

    @staticmethod
    def _speed_near_s(df: pd.DataFrame, s_value: Optional[float], track_length: float) -> Optional[float]:
        if s_value is None or df.empty or "speed_kmh" not in df:
            return None
        s = df["s"].to_numpy(dtype=float)
        if track_length > 0:
            delta = np.abs(((s - s_value + track_length / 2.0) % track_length) - track_length / 2.0)
        else:
            delta = np.abs(s - s_value)
        mask = delta <= 12.0
        if not mask.any():
            return None
        value = float(df.loc[mask, "speed_kmh"].mean())
        return value if np.isfinite(value) else None

    @staticmethod
    def _coasting_distance(df: pd.DataFrame) -> float:
        if df.empty or "s_unwrapped" not in df:
            return 0.0
        coast = (df["throttle"] < 0.08) & (df["brake"] < 0.08)
        if coast.sum() < 2:
            return 0.0
        s = df["s_unwrapped"].to_numpy(dtype=float)
        active = coast.to_numpy(dtype=bool)
        distance = 0.0
        for idx in range(1, len(s)):
            if active[idx] and active[idx - 1]:
                step = s[idx] - s[idx - 1]
                if 0.0 <= step <= 80.0:
                    distance += step
        return float(max(0.0, distance))

    @staticmethod
    def _mean_abs_lateral(df: pd.DataFrame) -> Optional[float]:
        if df.empty or "L" not in df or df["L"].notna().sum() == 0:
            return None
        value = float(df["L"].abs().mean())
        return value if np.isfinite(value) else None

    @staticmethod
    def _max_abs_lateral(df: pd.DataFrame) -> Optional[float]:
        if df.empty or "L" not in df or df["L"].notna().sum() == 0:
            return None
        value = float(df["L"].abs().max())
        return value if np.isfinite(value) else None
