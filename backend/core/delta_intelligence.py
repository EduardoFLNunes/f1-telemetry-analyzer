"""
Live Delta Intelligence
Predictive lap timing and gain/loss decomposition.
"""
import numpy as np
from typing import Dict, Any, List, Optional
import time

class DeltaIntelligence:
    """
    Analyzes delta evolution and predicts end-of-lap performance.
    """
    def __init__(self, track_length: float):
        self.track_length = track_length
        self.sector_history: Dict[int, List[float]] = {1: [], 2: [], 3: []}
        self.current_lap_predicted_time = 0.0
        self.last_s = 0.0
        
    def process_frame(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates lap predictions and calculates rolling pace.
        """
        curr_s = frame["s"]
        curr_delta = frame["delta"]
        curr_time = frame["lap_time"]
        
        # 1. Gain/Loss Decomposition
        # (Implicitly handled by delta evolution)
        
        # 2. Predicted Lap Time
        # predicted = current_time + (remaining_distance / avg_speed_remaining)
        # Simplified: predicted = reference_lap_time + current_delta
        # In a more advanced version, we'd use sector averages for the remaining track.
        
        # 3. Sector Attribution
        sector = 1
        if curr_s > 2.0 * self.track_length / 3.0:
            sector = 3
        elif curr_s > self.track_length / 3.0:
            sector = 2
            
        return {
            "type": "delta_intelligence",
            "predicted_lap_time": curr_time + (self.track_length - curr_s) / max(frame["speed"], 1.0), # naive prediction
            "current_sector": sector,
            "is_improving": curr_delta < 0
        }

    def update_sector_history(self, sector: int, time_taken: float):
        self.sector_history[sector].append(time_taken)
        if len(self.sector_history[sector]) > 10:
            self.sector_history[sector].pop(0)
            
    def get_target_pace(self) -> float:
        """Returns the sum of best sector times."""
        target = 0.0
        for s in [1, 2, 3]:
            if self.sector_history[s]:
                target += min(self.sector_history[s])
        return target
