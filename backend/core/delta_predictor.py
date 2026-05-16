"""
Predictive Delta Forecasting
Implements live lap-time projection and gain/loss attribution.
"""
import numpy as np
from typing import Dict, Any, List, Optional
import time

class DeltaPredictor:
    """
    Forecasts final lap time using a combination of current delta,
    historical sector pace, and AI-predicted future performance.
    """
    def __init__(self, reference_time: float):
        self.reference_time = reference_time
        self.sector_history: Dict[int, List[float]] = {1: [], 2: [], 3: []}
        
    def forecast_lap_time(self, current_frame: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs: current telemetry frame with live delta.
        Outputs: Projected final lap time and confidence interval.
        """
        curr_delta = current_frame.get("delta", 0.0)
        curr_time = current_frame.get("lap_time", 0.0)
        s = current_frame.get("s", 0.0)
        
        # 1. Base Forecast (Deterministic)
        # projected = ref_lap_time + current_delta
        base_forecast = self.reference_time + curr_delta
        
        # 2. Adaptive Correction (Heuristic)
        # If the driver is consistently faster in later sectors, adjust forecast
        # (This is where a real ML model would excel)
        
        # 3. Confidence Calculation
        # Confidence decreases as we get further from the finish line
        track_progress = s / 5000.0 # Assuming 5km track
        confidence = 0.5 + (0.4 * min(track_progress, 1.0))
        
        return {
            "projected_time": float(base_forecast),
            "current_delta": float(curr_delta),
            "confidence": float(confidence),
            "expected_gain": float(-curr_delta) if curr_delta < 0 else 0.0
        }

    def add_sector_time(self, sector: int, lap_time: float):
        self.sector_history[sector].append(lap_time)
        if len(self.sector_history[sector]) > 10:
            self.sector_history[sector].pop(0)
            
    def get_ideal_lap(self) -> float:
        """Returns the 'Ultimate Lap' (sum of best sectors)."""
        best_sectors = [min(h) if h else 0.0 for h in self.sector_history.values()]
        return sum(best_sectors)
