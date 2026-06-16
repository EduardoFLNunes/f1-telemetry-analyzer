from __future__ import annotations

from typing import Dict, Optional

from .models import CornerComparison, CornerMetrics
from .utils import circular_delta


def numeric_delta(player: Optional[float], reference: Optional[float]) -> Optional[float]:
    if player is None or reference is None:
        return None
    return float(player) - float(reference)


class ReferenceComparator:
    def compare(
        self,
        player_metrics: Dict[int, CornerMetrics],
        reference_metrics: Dict[int, CornerMetrics],
        track_length: float,
    ) -> Dict[int, CornerComparison]:
        comparisons: Dict[int, CornerComparison] = {}
        for corner_id, player in player_metrics.items():
            reference = reference_metrics.get(corner_id)
            if not reference:
                continue
            phase_delta = {}
            for phase, player_value in player.phase_line_deviation_m.items():
                phase_delta[phase] = numeric_delta(player_value, reference.phase_line_deviation_m.get(phase))

            comparisons[corner_id] = CornerComparison(
                corner_id=corner_id,
                segment_time_delta_s=numeric_delta(player.segment_time, reference.segment_time),
                entry_speed_delta_kmh=numeric_delta(player.entry_speed_kmh, reference.entry_speed_kmh),
                min_speed_delta_kmh=numeric_delta(player.min_speed_kmh, reference.min_speed_kmh),
                exit_speed_delta_kmh=numeric_delta(player.exit_speed_kmh, reference.exit_speed_kmh),
                brake_start_delta_m=circular_delta(player.brake_start_s, reference.brake_start_s, track_length),
                brake_release_delta_m=circular_delta(player.brake_release_s, reference.brake_release_s, track_length),
                apex_delta_m=circular_delta(player.apex_s, reference.apex_s, track_length),
                throttle_pickup_delta_m=circular_delta(player.throttle_pickup_s, reference.throttle_pickup_s, track_length),
                full_throttle_delta_m=circular_delta(player.full_throttle_s, reference.full_throttle_s, track_length),
                coasting_delta_m=numeric_delta(player.coasting_distance_m, reference.coasting_distance_m),
                lateral_offset_delta_m=numeric_delta(player.mean_abs_lateral_offset_m, reference.mean_abs_lateral_offset_m),
                line_deviation_delta_m=numeric_delta(player.mean_line_deviation_m, reference.mean_line_deviation_m),
                phase_line_deviation_delta_m=phase_delta,
            )
        return comparisons
