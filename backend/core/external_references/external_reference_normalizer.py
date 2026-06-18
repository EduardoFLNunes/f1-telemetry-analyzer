from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .external_reference_models import (
    CALIBRATION_UNCALIBRATED,
    COMPARABLE_LIMITED,
    REFERENCE_TYPE_EXTERNAL_F1,
    SOURCE_FASTF1,
    ExternalReferenceLap,
    ExternalReferenceMetadata,
    ExternalReferenceSample,
)


class ExternalReferenceNormalizer:
    def normalize_fastf1_telemetry(
        self,
        telemetry: Any,
        *,
        year: int,
        event: str,
        session: str,
        driver: Optional[str],
        team: Optional[str] = None,
        lap_number: Optional[int] = None,
        lap_time: Optional[float] = None,
        track: str = "Interlagos",
    ) -> ExternalReferenceLap:
        df = pd.DataFrame(telemetry).copy()
        if df.empty:
            raise ValueError("FastF1 telemetry is empty")

        elapsed = self._elapsed_seconds(df)
        x = self._series(df, "X", "x")
        y = self._series(df, "Y", "y")
        distance = self._distance(df, x, y)
        max_distance = float(np.nanmax(distance)) if len(distance) else 0.0
        if not math.isfinite(max_distance) or max_distance <= 0.0:
            raise ValueError("FastF1 telemetry has no usable distance channel")

        speed = self._series(df, "Speed", "speed", fallback=np.nan)
        throttle = self._control(self._series(df, "Throttle", "throttle", fallback=np.nan))
        brake = self._control(self._series(df, "Brake", "brake", fallback=np.nan))
        rpm = self._series(df, "RPM", "rpm", fallback=np.nan)
        gear = self._series(df, "nGear", "Gear", "gear", fallback=np.nan)

        samples = []
        for index in range(len(df)):
            progress = max(0.0, min(1.0, float(distance[index]) / max_distance))
            samples.append(
                ExternalReferenceSample(
                    progress=progress,
                    distance_m=float(distance[index]),
                    elapsed_s=float(elapsed[index]),
                    speed_kmh=self._finite(speed[index]),
                    throttle=self._finite(throttle[index]),
                    brake=self._finite(brake[index]),
                    rpm=self._finite(rpm[index]),
                    gear=self._finite_int(gear[index]),
                    x=self._finite(x[index]) if x is not None else None,
                    y=self._finite(y[index]) if y is not None else None,
                )
            )

        reference_id = self._reference_id(year, event, session, driver, lap_number, lap_time)
        metadata = ExternalReferenceMetadata(
            reference_id=reference_id,
            source=SOURCE_FASTF1,
            reference_type=REFERENCE_TYPE_EXTERNAL_F1,
            calibration_status=CALIBRATION_UNCALIBRATED,
            comparable_to_assetto=COMPARABLE_LIMITED,
            year=year,
            event=event,
            session=session,
            driver=driver or "FASTEST",
            team=team,
            lap_number=lap_number,
            lap_time=lap_time,
            track=track,
            imported_at=datetime.utcnow().isoformat() + "Z",
            sample_count=len(samples),
            provider_notes=[
                "External F1 telemetry is normalized by relative lap progress and must not replace an internal Assetto Corsa reference lap.",
            ],
        )
        return ExternalReferenceLap(metadata=metadata, samples=samples)

    def _elapsed_seconds(self, df: pd.DataFrame) -> np.ndarray:
        for key in ("Time", "time", "SessionTime", "session_time"):
            if key not in df:
                continue
            values = df[key]
            if pd.api.types.is_timedelta64_dtype(values):
                seconds = values.dt.total_seconds().to_numpy(dtype=float)
            elif pd.api.types.is_numeric_dtype(values):
                seconds = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
            else:
                converted = pd.to_timedelta(values, errors="coerce")
                if converted.notna().any():
                    seconds = converted.dt.total_seconds().to_numpy(dtype=float)
                else:
                    seconds = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
            if np.isfinite(seconds).any():
                first = seconds[np.isfinite(seconds)][0]
                return np.nan_to_num(seconds - first, nan=0.0)
        return np.arange(len(df), dtype=float)

    def _distance(self, df: pd.DataFrame, x: Optional[np.ndarray], y: Optional[np.ndarray]) -> np.ndarray:
        distance = self._series(df, "Distance", "distance")
        if distance is not None and np.isfinite(distance).any() and float(np.nanmax(distance)) > 0.0:
            return np.nan_to_num(distance, nan=0.0)
        if x is not None and y is not None and len(x) == len(y):
            dx = np.diff(np.nan_to_num(x, nan=0.0), prepend=np.nan_to_num(x[0], nan=0.0))
            dy = np.diff(np.nan_to_num(y, nan=0.0), prepend=np.nan_to_num(y[0], nan=0.0))
            return np.cumsum(np.hypot(dx, dy))
        return np.linspace(0.0, max(1.0, float(len(df) - 1)), len(df))

    @staticmethod
    def _series(df: pd.DataFrame, *keys: str, fallback: Any = None) -> Optional[np.ndarray]:
        for key in keys:
            if key in df:
                return pd.to_numeric(df[key], errors="coerce").to_numpy(dtype=float)
        if fallback is None:
            return None
        return np.full(len(df), fallback, dtype=float)

    @staticmethod
    def _control(values: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if values is None:
            return None
        result = values.astype(float)
        finite = result[np.isfinite(result)]
        if len(finite) and np.nanmax(finite) > 1.5:
            result = result / 100.0
        return np.clip(result, 0.0, 1.0)

    @staticmethod
    def _finite(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _finite_int(cls, value: Any) -> Optional[int]:
        number = cls._finite(value)
        return int(number) if number is not None else None

    @staticmethod
    def _reference_id(
        year: int,
        event: str,
        session: str,
        driver: Optional[str],
        lap_number: Optional[int],
        lap_time: Optional[float],
    ) -> str:
        base = "__".join(
            [
                "fastf1",
                str(year),
                _safe(event),
                _safe(session),
                _safe(driver or "fastest"),
                str(lap_number or "best"),
            ]
        )
        digest = hashlib.sha1(f"{base}:{lap_time}".encode("utf-8")).hexdigest()[:8]
        return f"{base}__{digest}"


def _safe(value: Any) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip())
    return cleaned.strip("_") or "unknown"
