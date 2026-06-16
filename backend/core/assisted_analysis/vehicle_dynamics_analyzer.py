from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from .assisted_analysis_models import (
    PHASE_APEX,
    PHASE_BRAKING,
    PHASE_ENTRY,
    PHASE_EXIT,
    PHASE_STRAIGHT_AFTER,
    CornerSegment,
    PhaseDynamics,
    VehicleDynamicsProfile,
)
from .utils import max_or_none, mean_or_none, min_or_none, window_mask


PHASES = (PHASE_ENTRY, PHASE_BRAKING, PHASE_APEX, PHASE_EXIT, PHASE_STRAIGHT_AFTER)
G = 9.80665


class VehicleDynamicsAnalyzer:
    def prepare(self, lap_df: pd.DataFrame) -> pd.DataFrame:
        df = lap_df.copy()
        if df.empty:
            return df
        required = {
            "yaw_rate_derived",
            "lateral_g_derived",
            "longitudinal_g_combined",
            "brake_release_rate",
            "throttle_application_rate",
            "steering_rate",
            "trajectory_curvature",
            "friction_usage",
        }
        if required.issubset(df.columns):
            return df

        elapsed = pd.to_numeric(df.get("elapsed_s", pd.Series(np.arange(len(df)) / 20.0)), errors="coerce").ffill().bfill().fillna(0.0)
        dt = elapsed.diff().replace(0.0, np.nan).bfill().fillna(0.05).clip(lower=0.001, upper=1.0)
        df["dt_s"] = dt

        speed = pd.to_numeric(df.get("speed_mps", df.get("speed_kmh", 0.0) / 3.6), errors="coerce").fillna(0.0)
        df["longitudinal_g_derived"] = speed.diff().divide(dt).fillna(0.0) / G

        yaw = pd.to_numeric(df.get("yaw", np.nan), errors="coerce")
        yaw_delta = self._wrapped_angle_delta(yaw)
        yaw_rate = pd.to_numeric(self._series(df, "yaw_rate"), errors="coerce")
        df["yaw_rate_derived"] = yaw_rate.where(yaw_rate.notna(), yaw_delta.divide(dt)).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        steering = pd.to_numeric(self._series(df, "steering"), errors="coerce")
        df["steering_rate"] = steering.diff().divide(dt).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        throttle = pd.to_numeric(df.get("throttle", 0.0), errors="coerce").fillna(0.0)
        brake = pd.to_numeric(df.get("brake", 0.0), errors="coerce").fillna(0.0)
        df["throttle_application_rate"] = throttle.diff().clip(lower=0.0).divide(dt).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        df["brake_release_rate"] = (-brake.diff()).clip(lower=0.0).divide(dt).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        df["brake_application_rate"] = brake.diff().clip(lower=0.0).divide(dt).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        curvature = self._trajectory_curvature(df)
        df["trajectory_curvature"] = curvature
        lateral_g = pd.to_numeric(self._series(df, "lateral_g"), errors="coerce")
        derived_lat_g = (speed * speed * pd.Series(curvature, index=df.index)) / G
        df["lateral_g_derived"] = lateral_g.where(lateral_g.notna(), derived_lat_g).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        lon_g = pd.to_numeric(self._series(df, "longitudinal_g"), errors="coerce")
        df["longitudinal_g_combined"] = lon_g.where(lon_g.notna(), df["longitudinal_g_derived"]).fillna(0.0)
        df["friction_usage"] = np.hypot(df["lateral_g_derived"], df["longitudinal_g_combined"])
        df["combined_input"] = brake + throttle
        return df

    def analyze_corner(
        self,
        lap_df: pd.DataFrame,
        reference_df: pd.DataFrame,
        segment: CornerSegment,
        track_length: float,
    ) -> VehicleDynamicsProfile:
        df = self.prepare(lap_df)
        ref = self.prepare(reference_df)
        phases = {}
        for phase in PHASES:
            phases[phase] = self._phase_dynamics(df, ref, segment, phase, track_length)

        summary = {
            "frictionUsagePeak": max_or_none(df["friction_usage"]) if "friction_usage" in df else None,
            "maxYawRate": max_or_none(df["yaw_rate_derived"].abs()) if "yaw_rate_derived" in df else None,
            "maxSteeringRate": max_or_none(df["steering_rate"].abs()) if "steering_rate" in df else None,
            "maxBrakeReleaseRate": max_or_none(df["brake_release_rate"]) if "brake_release_rate" in df else None,
            "maxThrottleApplicationRate": max_or_none(df["throttle_application_rate"]) if "throttle_application_rate" in df else None,
        }
        return VehicleDynamicsProfile(
            corner_id=segment.corner_id,
            phases=phases,
            derived_channels={
                "yawRate": "yaw_rate" not in lap_df or lap_df["yaw_rate"].isna().all(),
                "lateralG": "lateral_g" not in lap_df or lap_df["lateral_g"].isna().all(),
                "longitudinalG": "longitudinal_g" not in lap_df or lap_df["longitudinal_g"].isna().all(),
                "brakeReleaseRate": True,
                "throttleApplicationRate": True,
                "steeringRate": True,
                "trajectoryCurvature": True,
                "frictionUsage": True,
            },
            summary=summary,
        )

    def _phase_dynamics(
        self,
        df: pd.DataFrame,
        reference_df: pd.DataFrame,
        segment: CornerSegment,
        phase: str,
        track_length: float,
    ) -> PhaseDynamics:
        bounds = segment.phases[phase]
        phase_df = df.loc[window_mask(df["s"], bounds.start_s, bounds.end_s, track_length)].copy()
        if phase_df.empty:
            return PhaseDynamics(phase=phase)

        line_deviation = self._reference_line_deviation(phase_df, reference_df, track_length)
        stability = self._stability_score(phase_df, line_deviation)
        return PhaseDynamics(
            phase=phase,
            max_lateral_g=max_or_none(phase_df["lateral_g_derived"].abs()),
            max_longitudinal_g=max_or_none(phase_df["longitudinal_g_combined"]),
            min_longitudinal_g=min_or_none(phase_df["longitudinal_g_combined"]),
            max_yaw_rate=max_or_none(phase_df["yaw_rate_derived"].abs()),
            mean_abs_yaw_rate=mean_or_none(phase_df["yaw_rate_derived"].abs()),
            max_steering_rate=max_or_none(phase_df["steering_rate"].abs()),
            mean_abs_steering=mean_or_none(pd.to_numeric(phase_df.get("steering", np.nan), errors="coerce").abs()),
            brake_release_rate=max_or_none(phase_df["brake_release_rate"]),
            throttle_application_rate=max_or_none(phase_df["throttle_application_rate"]),
            trajectory_curvature_peak=max_or_none(phase_df["trajectory_curvature"].abs()),
            friction_usage_peak=max_or_none(phase_df["friction_usage"]),
            reference_line_deviation_m=line_deviation,
            stability_score=stability,
        )

    @staticmethod
    def _trajectory_curvature(df: pd.DataFrame) -> np.ndarray:
        if not {"x", "z"}.issubset(df.columns) or len(df) < 5:
            return np.zeros(len(df), dtype=float)
        x = pd.to_numeric(df["x"], errors="coerce").interpolate().ffill().bfill().to_numpy(dtype=float)
        z = pd.to_numeric(df["z"], errors="coerce").interpolate().ffill().bfill().to_numpy(dtype=float)
        dx = np.gradient(x)
        dz = np.gradient(z)
        ddx = np.gradient(dx)
        ddz = np.gradient(dz)
        denom = np.power(dx * dx + dz * dz, 1.5)
        return np.divide(dx * ddz - dz * ddx, denom, out=np.zeros_like(dx), where=denom > 1e-6)

    @staticmethod
    def _wrapped_angle_delta(yaw: pd.Series) -> pd.Series:
        values = pd.to_numeric(yaw, errors="coerce")
        delta = values.diff()
        return ((delta + np.pi) % (2.0 * np.pi)) - np.pi

    @staticmethod
    def _reference_line_deviation(phase_df: pd.DataFrame, reference_df: pd.DataFrame, track_length: float) -> Optional[float]:
        if "L" not in phase_df or "L" not in reference_df or phase_df["L"].isna().all() or reference_df["L"].isna().all():
            return None
        if "s" not in phase_df or "s" not in reference_df:
            return None
        ref = reference_df[["s", "L"]].dropna().sort_values("s")
        if len(ref) < 2:
            return None
        ref_s = ref["s"].to_numpy(dtype=float)
        ref_l = ref["L"].to_numpy(dtype=float)
        player_s = phase_df["s"].to_numpy(dtype=float)
        if track_length > 0:
            ref_s = ref_s % track_length
            player_s = player_s % track_length
        order = np.argsort(ref_s)
        ref_s = ref_s[order]
        ref_l = ref_l[order]
        unique_s, unique_idx = np.unique(ref_s, return_index=True)
        if len(unique_s) < 2:
            return None
        ref_interp = np.interp(player_s, unique_s, ref_l[unique_idx], left=ref_l[unique_idx][0], right=ref_l[unique_idx][-1])
        deviation = np.abs(phase_df["L"].to_numpy(dtype=float) - ref_interp)
        value = float(np.nanmean(deviation))
        return value if np.isfinite(value) else None

    @staticmethod
    def _stability_score(phase_df: pd.DataFrame, line_deviation: Optional[float]) -> Optional[float]:
        if phase_df.empty:
            return None
        yaw = float(phase_df["yaw_rate_derived"].abs().mean()) if "yaw_rate_derived" in phase_df else 0.0
        steer_rate = float(phase_df["steering_rate"].abs().mean()) if "steering_rate" in phase_df else 0.0
        friction = float(phase_df["friction_usage"].max()) if "friction_usage" in phase_df else 0.0
        line = line_deviation or 0.0
        penalty = min(1.0, yaw / 1.3 * 0.35 + steer_rate / 5.0 * 0.25 + max(0.0, friction - 1.1) * 0.25 + line / 4.0 * 0.15)
        return max(0.0, 1.0 - penalty)

    @staticmethod
    def _series(df: pd.DataFrame, column: str) -> pd.Series:
        if column in df:
            return df[column]
        return pd.Series([np.nan] * len(df), index=df.index)
