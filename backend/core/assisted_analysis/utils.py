from __future__ import annotations

import math
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd


def finite_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def finite_int(value: Any, default: int = 0) -> int:
    number = finite_float(value)
    if number is None:
        return default
    return int(number)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def circular_delta(player_s: Optional[float], reference_s: Optional[float], track_length: float) -> Optional[float]:
    if player_s is None or reference_s is None or track_length <= 0:
        return None
    delta = float(player_s) - float(reference_s)
    half = track_length / 2.0
    while delta > half:
        delta -= track_length
    while delta < -half:
        delta += track_length
    return delta


def distance_between(start_s: float, end_s: float, track_length: float) -> float:
    if track_length <= 0:
        return max(0.0, end_s - start_s)
    start = start_s % track_length
    end = end_s % track_length
    if end >= start:
        return end - start
    return (track_length - start) + end


def unwrap_distance_series(values: Iterable[float], track_length: float) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0 or track_length <= 0:
        return arr

    out = arr.copy()
    offset = 0.0
    prev = out[0]
    for idx in range(1, out.size):
        value = arr[idx] + offset
        if value < prev - track_length * 0.5:
            offset += track_length
            value = arr[idx] + offset
        elif value > prev + track_length * 0.5:
            offset -= track_length
            value = arr[idx] + offset
        out[idx] = value
        prev = value
    return out


def window_mask(values: pd.Series, start_s: float, end_s: float, track_length: float) -> pd.Series:
    if values.empty:
        return pd.Series([], dtype=bool, index=values.index)
    if track_length <= 0:
        low, high = sorted((start_s, end_s))
        return (values >= low) & (values <= high)

    start = start_s % track_length
    end = end_s % track_length
    s = values % track_length
    if end >= start:
        return (s >= start) & (s <= end)
    return (s >= start) | (s <= end)


def interpolate_elapsed_at_s(df: pd.DataFrame, s_value: float, track_length: float) -> Optional[float]:
    if df.empty or "elapsed_s" not in df or "s_unwrapped" not in df:
        return None
    elapsed = df["elapsed_s"].to_numpy(dtype=float)
    s = df["s_unwrapped"].to_numpy(dtype=float)
    if len(s) < 2 or not np.isfinite(s).all() or not np.isfinite(elapsed).all():
        return None

    target = float(s_value)
    if track_length > 0:
        candidates = [target + k * track_length for k in range(-2, 4)]
        target = min(candidates, key=lambda item: abs(item - float(np.median(s))))

    order = np.argsort(s)
    s_sorted = s[order]
    e_sorted = elapsed[order]
    if target < s_sorted[0] or target > s_sorted[-1]:
        nearest = int(np.argmin(np.abs(s_sorted - target)))
        return float(e_sorted[nearest]) if abs(s_sorted[nearest] - target) < max(25.0, track_length * 0.01) else None
    return float(np.interp(target, s_sorted, e_sorted))


def mean_or_none(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    value = float(series.mean())
    return value if math.isfinite(value) else None


def max_or_none(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    value = float(series.max())
    return value if math.isfinite(value) else None


def min_or_none(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    value = float(series.min())
    return value if math.isfinite(value) else None


def normalize_lap_dataframe(raw_df: pd.DataFrame, track_length: Optional[float] = None) -> pd.DataFrame:
    df = raw_df.copy()
    if df.empty:
        return df

    def col(*names: str, default: Any = np.nan):
        for name in names:
            if name in df.columns:
                return df[name]
        return pd.Series([default] * len(df), index=df.index)

    out = pd.DataFrame(index=df.index)
    out["driver_id"] = col("driver_id", "driverId", default="player_1").fillna("player_1").astype(str)
    out["lap_number"] = pd.to_numeric(col("lap_number", "lap", default=0), errors="coerce").fillna(0).astype(int)

    raw_timestamp = pd.to_numeric(col("timestamp", default=np.nan), errors="coerce")
    raw_session = pd.to_numeric(col("sessionTime", "session_time", default=np.nan), errors="coerce")
    raw_lap_time = pd.to_numeric(col("lap_time", "lapTime", default=np.nan), errors="coerce")

    # Runtime frames use milliseconds for timestamp; JSONL envelope can use seconds.
    timestamp_seconds = raw_timestamp.where(raw_timestamp < 100_000_000_000, raw_timestamp / 1000.0)
    if raw_lap_time.notna().sum() > 2 and raw_lap_time.max(skipna=True) > raw_lap_time.min(skipna=True):
        elapsed = raw_lap_time - raw_lap_time.min(skipna=True)
    elif raw_session.notna().sum() > 2 and raw_session.max(skipna=True) > raw_session.min(skipna=True):
        elapsed = raw_session - raw_session.min(skipna=True)
    elif timestamp_seconds.notna().sum() > 2:
        elapsed = timestamp_seconds - timestamp_seconds.min(skipna=True)
    else:
        elapsed = pd.Series(np.arange(len(df), dtype=float) / 20.0, index=df.index)
    out["elapsed_s"] = pd.to_numeric(elapsed, errors="coerce").ffill().bfill().fillna(0.0)
    out["timestamp_s"] = timestamp_seconds

    speed_kmh = pd.to_numeric(col("speedKmh", "speed_kmh", default=np.nan), errors="coerce")
    raw_speed = pd.to_numeric(col("speed", default=np.nan), errors="coerce")
    if speed_kmh.notna().sum() == 0:
        raw_max = raw_speed.max(skipna=True)
        speed_kmh = raw_speed * 3.6 if pd.notna(raw_max) and raw_max < 85.0 else raw_speed
    out["speed_kmh"] = speed_kmh.fillna(0.0).clip(lower=0.0)
    out["speed_mps"] = out["speed_kmh"] / 3.6

    for channel in ("throttle", "brake"):
        values = pd.to_numeric(col(channel, default=0.0), errors="coerce").fillna(0.0)
        if values.max(skipna=True) > 1.5:
            values = values / 100.0
        out[channel] = values.clip(lower=0.0, upper=1.0)

    out["steering"] = pd.to_numeric(col("steering", default=np.nan), errors="coerce")
    out["gear"] = pd.to_numeric(col("gear", default=np.nan), errors="coerce")
    out["rpm"] = pd.to_numeric(col("rpm", "rpms", default=np.nan), errors="coerce")
    out["yaw"] = pd.to_numeric(col("yaw", "heading", default=np.nan), errors="coerce")
    out["yaw_rate"] = pd.to_numeric(col("yaw_rate", "yawRate", default=np.nan), errors="coerce")

    if "accel_g" in df.columns and not isinstance(df["accel_g"].dropna().head(1).iloc[0] if df["accel_g"].dropna().size else None, dict):
        out["longitudinal_g"] = pd.to_numeric(df["accel_g"], errors="coerce")
        out["lateral_g"] = np.nan
    else:
        accel = df["accel_g"] if "accel_g" in df.columns else pd.Series([None] * len(df), index=df.index)
        out["lateral_g"] = accel.apply(lambda item: finite_float(item.get("x")) if isinstance(item, dict) else None)
        out["longitudinal_g"] = accel.apply(lambda item: finite_float(item.get("z")) if isinstance(item, dict) else None)
    if "lateral_g" in df.columns or "lat_g" in df.columns:
        out["lateral_g"] = pd.to_numeric(col("lateral_g", "lat_g", default=np.nan), errors="coerce")
    if "longitudinal_g" in df.columns or "lon_g" in df.columns:
        out["longitudinal_g"] = pd.to_numeric(col("longitudinal_g", "lon_g", default=np.nan), errors="coerce")

    out["x"] = pd.to_numeric(col("world_x", "worldPositionX", "x", default=np.nan), errors="coerce")
    out["z"] = pd.to_numeric(col("world_z", "worldPositionZ", "z", default=np.nan), errors="coerce")
    out["L"] = pd.to_numeric(col("L", "lateralOffset", "lateral_offset", default=np.nan), errors="coerce")
    out["delta"] = pd.to_numeric(col("delta", default=np.nan), errors="coerce")
    out["corner_id"] = pd.to_numeric(col("corner_id", "cornerId", default=np.nan), errors="coerce")
    out["corner_type"] = col("corner_type", "cornerType", default=None)

    s = pd.to_numeric(col("s", "distanceAlongTrack", "distance_along_track", default=np.nan), errors="coerce")
    p = pd.to_numeric(col("p", "spline_t", "splinePosition", "normalizedSplinePosition", "lapProgress", default=np.nan), errors="coerce")
    length = finite_float(track_length, None)
    if s.notna().sum() == 0 and length and p.notna().sum() > 0:
        s = p * length
    if s.notna().sum() == 0 and out["x"].notna().sum() > 1 and out["z"].notna().sum() > 1:
        x = out["x"].ffill().bfill().to_numpy(dtype=float)
        z = out["z"].ffill().bfill().to_numpy(dtype=float)
        cumulative = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(z)))])
        s = pd.Series(cumulative, index=df.index)
        length = float(cumulative[-1]) if cumulative[-1] > 0 else length
    if length is None and s.notna().sum() > 1:
        length = float(max(s.max(skipna=True), 1.0))

    out["s"] = s.ffill().bfill().fillna(0.0)
    if length and length > 0:
        out["p"] = p.fillna((out["s"] % length) / length).clip(lower=0.0, upper=1.0)
        out["s_unwrapped"] = unwrap_distance_series(out["s"].to_numpy(dtype=float), length)
    else:
        out["p"] = p.fillna(0.0).clip(lower=0.0, upper=1.0)
        out["s_unwrapped"] = out["s"]
    out["track_length"] = length or float(max(out["s"].max(), 1.0))

    out = out.replace([np.inf, -np.inf], np.nan)
    return out.reset_index(drop=True)
