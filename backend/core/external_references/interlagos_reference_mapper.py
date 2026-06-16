from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .external_reference_models import ExternalReferenceLap


class InterlagosReferenceMapper:
    def build_context(
        self,
        reference: ExternalReferenceLap,
        *,
        corners: List[Dict[str, Any]],
        track_length: float,
    ) -> Dict[str, Any]:
        macro_corners = [
            self._corner_context(reference, corner, track_length)
            for corner in corners
        ]
        macro_corners = [item for item in macro_corners if item]
        return {
            "available": True,
            "metadata": reference.metadata.to_api(),
            "normalization": {
                "basis": "relative_lap_progress",
                "distanceComparison": "percent_of_lap_distance",
                "speedComparison": "relative_profile_shape",
                "absoluteTimeComparison": "disabled",
                "absoluteSpeedComparison": "limited_context_only",
            },
            "comparabilityNotice": (
                "FastF1 is real Formula 1 telemetry. It is used only as an external macro context for Interlagos "
                "and does not replace the player's validated internal reference lap."
            ),
            "macroCornerContext": macro_corners,
        }

    def _corner_context(
        self,
        reference: ExternalReferenceLap,
        corner: Dict[str, Any],
        track_length: float,
    ) -> Optional[Dict[str, Any]]:
        if track_length <= 0.0 or not reference.samples:
            return None
        start_p = max(0.0, min(1.0, float(corner.get("startS") or 0.0) / track_length))
        end_p = max(0.0, min(1.0, float(corner.get("endS") or 0.0) / track_length))
        if end_p <= start_p:
            return None
        samples = [sample for sample in reference.samples if start_p <= sample.progress <= end_p]
        if len(samples) < 3:
            return None

        speed = np.asarray([sample.speed_kmh for sample in samples if sample.speed_kmh is not None], dtype=float)
        brake_samples = [sample for sample in samples if sample.brake is not None and sample.brake >= 0.2]
        throttle_samples = [sample for sample in samples if sample.throttle is not None and sample.throttle >= 0.2]
        min_speed = float(np.min(speed)) if len(speed) else None
        entry_speed = samples[0].speed_kmh
        exit_speed = samples[-1].speed_kmh
        brake_start = brake_samples[0].progress if brake_samples else None
        throttle_pickup = throttle_samples[0].progress if throttle_samples else None

        return {
            "cornerId": corner.get("cornerId"),
            "name": corner.get("name"),
            "progressStart": start_p,
            "progressEnd": end_p,
            "externalEntrySpeedKmh": entry_speed,
            "externalMinSpeedKmh": min_speed,
            "externalExitSpeedKmh": exit_speed,
            "externalBrakeStartProgress": brake_start,
            "externalThrottlePickupProgress": throttle_pickup,
            "summary": self._summary(entry_speed, min_speed, exit_speed, brake_start, throttle_pickup),
        }

    @staticmethod
    def _summary(
        entry_speed: Optional[float],
        min_speed: Optional[float],
        exit_speed: Optional[float],
        brake_start: Optional[float],
        throttle_pickup: Optional[float],
    ) -> str:
        pieces = []
        if entry_speed is not None and min_speed is not None:
            pieces.append(f"external speed profile drops from {entry_speed:.0f} to {min_speed:.0f} km/h")
        if brake_start is not None:
            pieces.append(f"braking zone appears near {brake_start * 100:.1f}% lap progress")
        if throttle_pickup is not None:
            pieces.append(f"throttle returns near {throttle_pickup * 100:.1f}% lap progress")
        if exit_speed is not None:
            pieces.append(f"exit trend reaches {exit_speed:.0f} km/h")
        return "; ".join(pieces) or "external macro profile available"
