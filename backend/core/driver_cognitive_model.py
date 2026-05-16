"""
Driver Cognitive Model
Models real-time behavioral metrics like confidence, aggression, and smoothness.
"""
import numpy as np
from typing import Dict, Any, List

class DriverCognitiveModel:
    """
    Maintains a rolling profile of driver behavior using behavioral telemetry.
    Uses EWMA (Exponentially Weighted Moving Average) for smoothing.
    """
    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha # Smoothing factor
        
        # Behavioral Indices (0-1)
        self.confidence_score = 0.5
        self.aggression_index = 0.5
        self.smoothness_index = 0.5
        self.consistency_score = 0.5
        
        # Internal state for raw metric tracking
        self.last_inputs = {"throttle": 0.0, "brake": 0.0, "steer": 0.0}
        self.correction_frequency = 0.0 # Steering micro-corrections

    def update(self, frame: Dict[str, Any]) -> Dict[str, float]:
        """
        Updates cognitive metrics based on current telemetry frame.
        """
        throttle = frame.get("throttle", 0.0)
        brake = frame.get("brake", 0.0)
        steer = frame.get("steer", 0.0)
        
        # 1. Calculate Input Gradients
        dt_throttle = abs(throttle - self.last_inputs["throttle"])
        dt_brake = abs(brake - self.last_inputs["brake"])
        dt_steer = abs(steer - self.last_inputs["steer"])
        
        # 2. Aggression Index (Rate of change of inputs)
        inst_aggression = min((dt_throttle + dt_brake + dt_steer * 2.0) * 5.0, 1.0)
        self.aggression_index = self._ewma(self.aggression_index, inst_aggression)
        
        # 3. Smoothness Index (Inverse of high-frequency corrections)
        inst_smoothness = 1.0 - min(dt_steer * 10.0, 1.0)
        self.smoothness_index = self._ewma(self.smoothness_index, inst_smoothness)
        
        # 4. Confidence Score (Braking and throttle commitment)
        inst_confidence = 1.0
        # Hesitation = oscillations in 0.2-0.8 range
        if 0.2 < throttle < 0.8 and dt_throttle > 0.05:
            inst_confidence -= 0.3
        if 0.2 < brake < 0.8 and dt_brake > 0.05:
            inst_confidence -= 0.3
            
        self.confidence_score = self._ewma(self.confidence_score, max(inst_confidence, 0.0))
        
        self.last_inputs = {"throttle": throttle, "brake": brake, "steer": steer}
        
        return self.get_metrics()

    def _ewma(self, current: float, new: float) -> float:
        return self.alpha * new + (1.0 - self.alpha) * current

    def get_metrics(self) -> Dict[str, float]:
        return {
            "confidence": float(self.confidence_score),
            "aggression": float(self.aggression_index),
            "smoothness": float(self.smoothness_index),
            "consistency": float(self.consistency_score)
        }
